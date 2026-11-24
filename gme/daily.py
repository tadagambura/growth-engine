"""The daily run: plan today's video, make it, check it, queue it for every platform, publish what is due.

Runs unattended (systemd timer on the N95). Safe to run twice: a day that is already done is skipped.
Every failure is logged and sent to Telegram; nothing here ever asks a human to approve a post.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import video, videoqa
from .atoms import Atom, load_atoms
from .budget import BudgetGuard, load_policy
from .config import AppConfig, load_all
from .planner import Slot, load_json, make_plan
from .posts import build_post
from .publisher import DryRunPublisher, publish_due
from .queue import Queue
from .scriptwriter import Writer, cta_text, evergreen_lines, http_transport
from .seasons import Calendar
from .telegram import TelegramBot
from .voice import VoiceUsage, load_voice_config, make_client

ROOT = Path(__file__).resolve().parent.parent
LONDON = ZoneInfo("Europe/London")
VIDEO_PLATFORMS = {"tiktok", "instagram", "youtube", "facebook", "threads", "bluesky", "x", "pinterest"}   # the blog takes text, not video


class LogPublisher(DryRunPublisher):
    """Until Postiz is connected: records exactly what would be posted, where, to data/outbox.jsonl."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def publish(self, post) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"post": post.id, "app": post.app_id, "platform": post.platform, "text": post.text,
                                "media": post.media, "at": post.scheduled_for.isoformat()}, ensure_ascii=False) + "\n")
        return f"log-{post.id}"


@dataclass
class Env:
    root: Path
    home: Path
    content: dict
    models: dict
    formats: dict[str, dict]
    atoms: dict[str, Atom]
    apps: dict[str, AppConfig]
    cal: Calendar
    guard: BudgetGuard
    writer: Writer
    voice_cfg: object
    voice_client: object | None
    usage: VoiceUsage
    queue: Queue
    publisher: object
    bot: TelegramBot | None = None


def read_secrets(path: str | None = None) -> dict[str, str]:
    """Keys from the environment first, then the owner's secrets file (never printed or logged)."""
    out = {k: v for k, v in os.environ.items() if k.endswith(("_KEY", "_TOKEN", "_ID"))}
    p = Path(path or os.environ.get("GME_SECRETS", Path.home() / ".config/app-portfolio/secrets.env"))
    if p.exists():
        for line in p.read_text().splitlines():
            m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
            if m and m.group(1) not in out:
                out[m.group(1)] = m.group(2).strip().strip("\"'")
    return out


def build_env(root: Path = ROOT, home: Path | None = None, secrets: dict | None = None) -> Env:
    home = Path(home or os.environ.get("GME_HOME", root / "data")); home.mkdir(parents=True, exist_ok=True)
    sec = secrets if secrets is not None else read_secrets()
    content, models = load_json(root / "configs/content.json"), load_json(root / "configs/models.json")
    formats = {f["id"]: f for f in load_json(root / "configs/formats.json")["formats"]}
    atoms = {a.id: a for items in load_atoms(root / "configs/atoms").values() for a in items}
    guard = BudgetGuard(load_policy(root / "configs/policy.json"), path=home / "ledger.json")
    transport = http_transport(sec["ANTHROPIC_API_KEY"], models["api_version"]) if sec.get("ANTHROPIC_API_KEY") else None
    try:
        client = make_client(str(root / ".env"))
    except Exception:
        client = None
    bot = TelegramBot(sec["TELEGRAM_BOT_TOKEN"], int(sec["TELEGRAM_CHAT_ID"])) if sec.get("TELEGRAM_BOT_TOKEN") and sec.get("TELEGRAM_CHAT_ID") else None
    return Env(root, home, content, models, formats, atoms, load_all(root / "configs/apps"), Calendar.load(root / "configs/seasons.json"),
               guard, Writer(models, content, guard, transport), load_voice_config(root / "configs/voice.json"), client,
               VoiceUsage(home / "voice-usage.json"), Queue(str(home / "queue.db")), LogPublisher(home / "outbox.jsonl"), bot)


def post_time(day: date) -> datetime:
    """17:30 London on weekdays, 10:30 at weekends (defaults, tuned later from results)."""
    t = time(10, 30) if day.weekday() >= 5 else time(17, 30)
    return datetime.combine(day, t, tzinfo=LONDON).astimezone(timezone.utc)


def _history(home: Path) -> list[Slot]:
    p = home / "history.json"
    return [Slot(**s) for s in json.loads(p.read_text())] if p.exists() else []


def _alert(env: Env, text: str) -> None:
    if env.bot:
        try:
            env.bot.send(text)
        except Exception:
            pass


def greeting_atom(env: Env, greeting_id: str, day: date) -> Atom:
    g = env.cal.greeting_for(day)
    return Atom(id=f"greeting:{g.id}", app_id="kaoticchainz", kind="greeting", title=g.name, body=g.text, reviewed=True)


def run_day(env: Env, day: date, now: datetime | None = None, producer=video.produce) -> dict:
    now = now or datetime.now(timezone.utc)
    done_marker = env.home / "done" / f"{day.isoformat()}.json"
    if done_marker.exists():
        return {"status": "already done", "day": day.isoformat()}
    paused = (env.home / "PAUSED").exists()

    history = _history(env.home)
    atoms_by_app: dict[str, list[Atom]] = {}
    for a in env.atoms.values():
        atoms_by_app.setdefault(a.app_id, []).append(a)
    plan = make_plan(day, 1, env.content, {"formats": [f for f in env.formats.values()]}, atoms_by_app, env.cal, history)
    if not plan.slots:
        return {"status": "nothing planned", "day": day.isoformat()}
    slot = plan.slots[0]

    if slot.greeting_id:
        cfg, atom, fmt = env.apps["kaoticchainz"], greeting_atom(env, slot.greeting_id, day), env.formats["greeting"]
        slot = Slot(**{**asdict(slot), "app_id": "kaoticchainz", "atom_id": atom.id, "kind": "greeting", "format_id": "greeting"})
    else:
        cfg, atom, fmt = env.apps[slot.app_id], env.atoms[slot.atom_id], env.formats[slot.format_id]
    occasion = (env.cal.active(day)[0].name if env.cal.active(day) and env.cal.active(day)[0].priority >= 90 else None)

    result, problems = None, []
    for attempt in (1, 2):
        try:
            result = producer(slot, fmt, atom, cfg, env.writer, env.voice_cfg, env.voice_client, env.usage, env.content, day,
                              env.home / "videos", env.home / "work" / day.isoformat(), occasion=occasion)
        except Exception as e:
            problems = [f"production failed: {type(e).__name__}: {e}"[:300]]
            continue
        cta = cta_text(env.content, slot.cta_id, cfg.name)
        problems = videoqa.check_script(result.script, fmt, cfg, cta) + videoqa.check_file(
            result.mp4, result.voiced, env.content["video_seconds"]["min"], env.content["video_seconds"]["max"])
        if not problems:
            break
        result = None
    if result is None:
        _alert(env, f"Daily video for {day} failed twice, nothing posted today.\n" + "\n".join(problems[:5]))
        return {"status": "failed", "day": day.isoformat(), "problems": problems}

    posts = []
    for platform, per_week in cfg.platforms.items():
        if per_week <= 0 or platform not in VIDEO_PLATFORMS:
            continue
        text = build_post(platform, result.script, cfg, day.isoformat(), cta)
        try:
            p = env.queue.add(cfg, platform, text, post_time(day), now, media=str(result.mp4))
            posts.append({"platform": platform, "post": p.id, "status": p.status, "problems": list(p.problems)})
        except Exception as e:
            posts.append({"platform": platform, "error": str(e)})
    apps = {a.app_id: a for a in env.apps.values()}
    published = publish_due(env.queue, env.publisher, apps, now, paused=paused)

    (env.home / "history.json").write_text(json.dumps([asdict(s) for s in history + [slot]], indent=1))
    done_marker.parent.mkdir(parents=True, exist_ok=True)
    summary = {"status": "ok", "day": day.isoformat(), "app": cfg.app_id, "format": fmt["id"], "atom": atom.id, "voiced": result.voiced,
               "script": result.script.source, "video": str(result.mp4), "duration": round(result.duration, 1), "notes": result.notes,
               "posts": posts, "published": published, "paused": paused}
    done_marker.write_text(json.dumps(summary, indent=1))
    bad = [p for p in posts if p.get("error") or p.get("status") == "qa_failed"]
    if bad or result.notes:
        _alert(env, f"{day}: video made, with notes.\n" + "\n".join(result.notes + [json.dumps(b) for b in bad])[:900])
    return summary
