"""Content queue (SQLite, standard library only) with an enforced approval flow.

States:  draft -> pending_approval | approved | qa_failed
         pending_approval -> approved | rejected
         approved -> published | failed
         failed -> approved   (retry)

The app's publishing_mode decides the route: 'off' refuses new posts, 'approval' waits for the
owner, 'automatic' goes straight to approved. QA always runs first and cannot be skipped.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from . import qa
from .config import AppConfig

TRANSITIONS = {
    "draft": {"pending_approval", "approved", "qa_failed"},
    "pending_approval": {"approved", "rejected"},
    "approved": {"published", "failed"},
    "failed": {"approved"},
    "qa_failed": set(), "rejected": set(), "published": set(),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  app_id TEXT NOT NULL, platform TEXT NOT NULL, text TEXT NOT NULL,
  media TEXT, scheduled_for TEXT NOT NULL, status TEXT NOT NULL,
  problems TEXT NOT NULL DEFAULT '[]', external_id TEXT, error TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS posts_due ON posts(status, scheduled_for);
"""


class QueueError(ValueError):
    pass


@dataclass(frozen=True)
class Post:
    id: int
    app_id: str
    platform: str
    text: str
    media: str | None
    scheduled_for: datetime
    status: str
    problems: tuple[str, ...]
    external_id: str | None
    error: str | None


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise QueueError("datetimes must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


def _row(r: sqlite3.Row) -> Post:
    return Post(r["id"], r["app_id"], r["platform"], r["text"], r["media"],
                datetime.fromisoformat(r["scheduled_for"]), r["status"],
                tuple(json.loads(r["problems"])), r["external_id"], r["error"])


class Queue:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def _set(self, post_id: int, status: str, *, now: datetime, **extra) -> Post:
        cur = self.get(post_id)
        if status not in TRANSITIONS[cur.status]:
            raise QueueError(f"post {post_id}: cannot go from {cur.status} to {status}")
        cols = {"status": status, "updated_at": _iso(now), **extra}
        self.db.execute(f"UPDATE posts SET {', '.join(f'{k} = ?' for k in cols)} WHERE id = ?",
                        [*cols.values(), post_id])
        self.db.commit()
        return self.get(post_id)

    def get(self, post_id: int) -> Post:
        r = self.db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if r is None:
            raise QueueError(f"no post {post_id}")
        return _row(r)

    def add(self, cfg: AppConfig, platform: str, text: str, scheduled_for: datetime, now: datetime,
            media: str | None = None) -> Post:
        """Run QA, then route by the app's publishing mode."""
        if cfg.publishing_mode == "off":
            raise QueueError(f"{cfg.app_id}: publishing is off")
        if platform not in cfg.platforms:
            raise QueueError(f"{cfg.app_id} is not set up for {platform}")
        problems = qa.check(text, platform, cfg)
        cur = self.db.execute(
            "INSERT INTO posts (app_id, platform, text, media, scheduled_for, status, problems, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
            (cfg.app_id, platform, text, media, _iso(scheduled_for), json.dumps(problems), _iso(now), _iso(now)))
        self.db.commit()
        pid = cur.lastrowid
        if problems:
            return self._set(pid, "qa_failed", now=now)
        return self._set(pid, "approved" if cfg.publishing_mode == "automatic" else "pending_approval", now=now)

    def approve(self, post_id: int, now: datetime) -> Post:
        return self._set(post_id, "approved", now=now)

    def reject(self, post_id: int, now: datetime) -> Post:
        return self._set(post_id, "rejected", now=now)

    def mark_published(self, post_id: int, external_id: str, now: datetime) -> Post:
        return self._set(post_id, "published", now=now, external_id=external_id, error=None)

    def mark_failed(self, post_id: int, error: str, now: datetime) -> Post:
        return self._set(post_id, "failed", now=now, error=error[:500])

    def retry(self, post_id: int, now: datetime) -> Post:
        return self._set(post_id, "approved", now=now)

    def due(self, now: datetime) -> list[Post]:
        rows = self.db.execute("SELECT * FROM posts WHERE status = 'approved' AND scheduled_for <= ? "
                               "ORDER BY scheduled_for, id", (_iso(now),)).fetchall()
        return [_row(r) for r in rows]

    def pending(self) -> list[Post]:
        return [_row(r) for r in self.db.execute(
            "SELECT * FROM posts WHERE status = 'pending_approval' ORDER BY scheduled_for, id")]

    def depth(self, app_id: str, now: datetime) -> int:
        """Posts still to go out (approved or awaiting approval): used to warn when the queue runs low."""
        return self.db.execute("SELECT COUNT(*) FROM posts WHERE app_id = ? AND status IN ('approved','pending_approval') "
                               "AND scheduled_for > ?", (app_id, _iso(now))).fetchone()[0]
