"""Deterministic quality gate for posts. Runs before anything reaches the owner or a platform.

Rules only, no model: a post that fails is never queued for approval. A model-based check
(Haiku for public posts) can sit on top later, but it can never overrule a failure here.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .config import AppConfig

# Conservative character limits per platform (text posts or captions).
LIMITS = {"x": 280, "bluesky": 300, "threads": 500, "pinterest": 500, "instagram": 2200,
          "tiktok": 2200, "facebook": 5000, "youtube": 5000, "blog": 20000}
ALWAYS_ALLOWED_HOSTS = {"kaoticchainz.com", "www.kaoticchainz.com"}
URL = re.compile(r"https?://[^\s)]+", re.I)
HASHTAG = re.compile(r"(?<!\w)#\w+")


def check(text: str, platform: str, cfg: AppConfig) -> list[str]:
    """Return every problem found (empty list = passes)."""
    problems: list[str] = []
    body = text.strip()
    if not body:
        return ["post is empty"]
    if platform not in LIMITS:
        problems.append(f"unknown platform '{platform}'")
    elif len(body) > LIMITS[platform]:
        problems.append(f"{len(body)} characters is over the {platform} limit of {LIMITS[platform]}")
    lowered = body.lower()
    for phrase in cfg.banned_phrases:
        if phrase.lower() in lowered:
            problems.append(f"contains banned phrase '{phrase}'")
    tags = HASHTAG.findall(body)
    if len(tags) > cfg.hashtags_max:
        problems.append(f"{len(tags)} hashtags (max {cfg.hashtags_max})")
    allowed = set(ALWAYS_ALLOWED_HOSTS)
    for link in cfg.links.values():
        if link:
            allowed.add((urlparse(link).hostname or "").lower())
    for url in URL.findall(body):
        host = (urlparse(url).hostname or "").lower()
        if host not in allowed:
            problems.append(f"link to {host} is not one of this app's own links")
    return problems
