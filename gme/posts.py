"""Per-platform post text for a finished video: caption, one CTA line, a tracked link, at most 3 hashtags.

The same video goes everywhere; only this text changes (constitution section 10). Links use the UTM
scheme in docs/growth/UTM_LINKS.md of the master repo.
"""
from __future__ import annotations

import re
from urllib.parse import urlencode

from . import qa
from .config import AppConfig
from .scriptwriter import Script

NO_LINK = {"tiktok", "instagram"}          # links are not clickable in these captions: point to the bio instead
SITE = "https://kaoticchainz.com"


def tracked_link(cfg: AppConfig, platform: str, day: str) -> str:
    base = cfg.links.get("web") or f"{SITE}/"
    q = urlencode({"utm_source": platform, "utm_medium": "post", "utm_campaign": f"{cfg.app_id}-launch", "utm_content": day})
    return f"{base}{'&' if '?' in base else '?'}{q}"


def hashtags(cfg: AppConfig) -> str:
    tags = ["#" + re.sub(r"\W", "", cfg.name)]
    for k in cfg.keywords:
        tag = "#" + re.sub(r"\W", "", k.title().replace(" ", ""))
        if len(tag) > 3 and tag not in tags:
            tags.append(tag)
    return " ".join(tags[: cfg.hashtags_max])


def fit(caption: str, room: int) -> str:
    """Shorten to whole sentences; only if the first one is too long, cut at a word and mark it."""
    kept = ""
    for sentence in re.split(r"(?<=[.!?])\s+", caption):
        longer = f"{kept} {sentence}".strip()
        if len(longer) > room:
            break
        kept = longer
    return kept or caption[: max(20, room - 1)].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def build_post(platform: str, script: Script, cfg: AppConfig, day: str, cta_line: str) -> str:
    link = "" if platform in NO_LINK else tracked_link(cfg, platform, day)
    tail = "\n".join(x for x in (cta_line, link, hashtags(cfg)) if x)
    limit = qa.LIMITS.get(platform, 2000)
    caption = script.caption.strip()
    room = limit - len(tail) - 2
    if len(caption) > room:                       # trim the caption, never the CTA, link or tags
        caption = fit(caption, room)
    return f"{caption}\n\n{tail}"
