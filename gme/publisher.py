"""Publishing: take due, approved posts and send them. The only place that talks to a platform.

`Publisher` is the seam. DryRunPublisher records what would go out and is the default, so the
engine can run end to end with no keys. The Postiz publisher is added once the N95 stack is up
and the pinned Postiz version's API has been checked against a real instance.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .config import AppConfig
from .queue import Post, Queue


class Publisher(Protocol):
    def publish(self, post: Post) -> str:
        """Send the post and return the platform's id for it. Raise on failure."""


class DryRunPublisher:
    def __init__(self) -> None:
        self.sent: list[Post] = []

    def publish(self, post: Post) -> str:
        self.sent.append(post)
        return f"dryrun-{post.id}"


def publish_due(queue: Queue, publisher: Publisher, apps: dict[str, AppConfig], now: datetime) -> dict[str, list[int]]:
    """Publish everything due. An app only publishes while it is 'active' and its mode is not 'off'."""
    result: dict[str, list[int]] = {"published": [], "failed": [], "skipped": []}
    for post in queue.due(now):
        cfg = apps.get(post.app_id)
        if cfg is None or cfg.status != "active" or cfg.publishing_mode == "off":
            result["skipped"].append(post.id)
            continue
        try:
            external = publisher.publish(post)
        except Exception as e:  # one bad post must not stop the rest
            queue.mark_failed(post.id, f"{type(e).__name__}: {e}", now)
            result["failed"].append(post.id)
        else:
            queue.mark_published(post.id, external, now)
            result["published"].append(post.id)
    return result
