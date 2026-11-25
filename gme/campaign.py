"""Ready-made posts: queue a hand-written run of videos and captions alongside the daily engine.

A campaign file lists one entry per day. Each entry goes to every platform that is connected and set
up for its app, through the same QA gate as everything else. Videos live in $GME_HOME/campaigns/<name>/.
Importing twice adds nothing new.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import AppConfig
from .queue import Queue

SHORT_TEXT = {"x", "bluesky"}                       # everyone else takes the longer caption
VIDEO_PLATFORMS = ("tiktok", "instagram", "youtube", "facebook", "threads", "bluesky", "x", "pinterest")


class CampaignError(ValueError):
    pass


def add_campaign(campaign: dict, queue: Queue, apps: dict[str, AppConfig], media_dir: Path,
                 connected, now: datetime) -> dict:
    """Queue every future post. Raises before adding anything if the campaign cannot be run as written."""
    missing = [p["media"] for p in campaign["posts"] if not (media_dir / p["media"]).is_file()]
    if missing:
        raise CampaignError(f"videos missing from {media_dir}: {', '.join(missing)}")
    unknown = sorted({p["app"] for p in campaign["posts"]} - set(apps))
    if unknown:
        raise CampaignError(f"unknown app: {', '.join(unknown)}")
    out: dict[str, list] = {"added": [], "already_queued": [], "past": [], "qa_failed": []}
    for entry in campaign["posts"]:
        cfg = apps[entry["app"]]
        when = datetime.fromisoformat(f'{entry["date"]}T{campaign["time_utc"]}').replace(tzinfo=timezone.utc)
        for platform in VIDEO_PLATFORMS:
            if platform not in cfg.platforms or not connected(platform):
                continue
            label = f'{entry["date"]} {platform}'
            media = str(media_dir / entry["media"])
            if when <= now:
                out["past"].append(label)
                continue
            if queue.db.execute("SELECT 1 FROM posts WHERE platform = ? AND media = ?", (platform, media)).fetchone():
                out["already_queued"].append(label)
                continue
            post = queue.add(cfg, platform, entry["short" if platform in SHORT_TEXT else "long"], when, now, media=media)
            if post.status == "qa_failed":
                out["qa_failed"].append(f'{label}: {"; ".join(post.problems)}')
            else:
                out["added"].append(label)
    return out
