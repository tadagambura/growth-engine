"""App configuration: every app joins the engine as one validated JSON file.

Validation is strict and deterministic. A config that fails validation is never loaded,
so a typo can't switch on publishing or spending by accident.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PLATFORMS = {"tiktok", "instagram", "facebook", "threads", "youtube", "pinterest", "bluesky", "x", "blog"}
STATUSES = {"draft", "active", "paused", "retired"}
TONES = {"Full drama", "Playful", "Calm"}
PUBLISHING_MODES = {"off", "approval", "automatic"}


class ConfigError(ValueError):
    """Raised with every problem found, not just the first."""

    def __init__(self, app_id: str, problems: list[str]):
        self.problems = problems
        super().__init__(f"{app_id}: " + "; ".join(problems))


@dataclass(frozen=True)
class Budgets:
    ai_monthly_gbp: float
    ads_enabled: bool = False
    ads_monthly_gbp: float = 0.0


@dataclass(frozen=True)
class AppConfig:
    app_id: str
    name: str
    status: str
    tagline: str
    audience: str
    brand_voice: str
    tone: str
    pillars: dict[str, float]          # pillar -> share of content (sums to 1.0)
    platforms: dict[str, int]          # platform -> posts per week
    publishing_mode: str
    budgets: Budgets
    links: dict[str, str] = field(default_factory=dict)
    approved_claims: tuple[str, ...] = ()
    banned_phrases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    competitors: tuple[str, ...] = ()
    hashtags_max: int = 3


def _problems(raw: dict) -> list[str]:
    p: list[str] = []
    required = ["app_id", "name", "status", "tagline", "audience", "brand_voice", "tone",
                "pillars", "platforms", "publishing_mode", "budgets"]
    p += [f"missing '{k}'" for k in required if k not in raw]
    if p:
        return p
    if not str(raw["app_id"]).replace("-", "").isalnum() or raw["app_id"] != raw["app_id"].lower():
        p.append("app_id must be lowercase letters, digits and hyphens")
    if raw["status"] not in STATUSES:
        p.append(f"status must be one of {sorted(STATUSES)}")
    if raw["tone"] not in TONES:
        p.append(f"tone must be one of {sorted(TONES)}")
    if raw["publishing_mode"] not in PUBLISHING_MODES:
        p.append(f"publishing_mode must be one of {sorted(PUBLISHING_MODES)}")
    pillars = raw["pillars"]
    if not isinstance(pillars, dict) or not pillars:
        p.append("pillars must be a non-empty object of pillar -> share")
    elif abs(sum(pillars.values()) - 1.0) > 0.001:
        p.append(f"pillar shares must sum to 1.0 (got {sum(pillars.values()):.3f})")
    bad = set(raw["platforms"]) - PLATFORMS
    if bad:
        p.append(f"unknown platforms {sorted(bad)}")
    if any((not isinstance(v, int)) or v < 0 or v > 70 for v in raw["platforms"].values()):
        p.append("posts per week must be whole numbers between 0 and 70")
    b = raw["budgets"]
    if b.get("ai_monthly_gbp", -1) < 0:
        p.append("budgets.ai_monthly_gbp must be set and not negative")
    if b.get("ads_enabled") and raw["status"] != "active":
        p.append("ads can only be enabled for an active app")
    return p


def parse(raw: dict) -> AppConfig:
    problems = _problems(raw)
    if problems:
        raise ConfigError(str(raw.get("app_id", "?")), problems)
    b = raw["budgets"]
    return AppConfig(
        app_id=raw["app_id"], name=raw["name"], status=raw["status"], tagline=raw["tagline"],
        audience=raw["audience"], brand_voice=raw["brand_voice"], tone=raw["tone"],
        pillars=dict(raw["pillars"]), platforms=dict(raw["platforms"]),
        publishing_mode=raw["publishing_mode"],
        budgets=Budgets(ai_monthly_gbp=float(b["ai_monthly_gbp"]),
                        ads_enabled=bool(b.get("ads_enabled", False)),
                        ads_monthly_gbp=float(b.get("ads_monthly_gbp", 0.0))),
        links=dict(raw.get("links", {})),
        approved_claims=tuple(raw.get("approved_claims", ())),
        banned_phrases=tuple(raw.get("banned_phrases", ())),
        keywords=tuple(raw.get("keywords", ())),
        competitors=tuple(raw.get("competitors", ())),
        hashtags_max=int(raw.get("hashtags_max", 3)),
    )


def load(path: str | Path) -> AppConfig:
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))


def load_all(directory: str | Path) -> dict[str, AppConfig]:
    apps = {}
    for f in sorted(Path(directory).glob("*.json")):
        cfg = load(f)
        if cfg.app_id != f.stem:
            raise ConfigError(cfg.app_id, [f"file name '{f.name}' must match app_id"])
        apps[cfg.app_id] = cfg
    return apps
