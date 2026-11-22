"""Model router: the cheapest thing that does the job.

Tier 0 tasks never touch a model. Paid tiers ask the budget guard first and fall back to the
local GPU model when the budget says no or the API is down.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .budget import BudgetGuard

TIER0 = {"schedule", "publish", "analytics", "budget", "dedup_exact", "utm", "notify", "link_check"}


@dataclass(frozen=True)
class Route:
    tier: str
    model: str | None
    where: str
    batch: bool
    note: str = ""


ROUTES: dict[str, Route] = {
    "captions":       Route("api-cheap", "claude-haiku-5-5", "api", True),
    "hooks":          Route("api-cheap", "claude-haiku-5-5", "api", True),
    "scripts":        Route("api-cheap", "claude-haiku-5-5", "api", True),
    "qa_text":        Route("api-cheap", "claude-haiku-5-5", "api", True),
    "weekly_report":  Route("api-mid", "claude-sonnet-5-5", "api", True),
    "strategy":       Route("api-mid", "claude-sonnet-5-5", "api", False, "launch and quarterly only"),
    "qa_visual":      Route("local", "qwen2.5vl:7b", "gpu", False),
    "embed":          Route("local", "nomic-embed-text", "gpu", False),
}
LOCAL_FALLBACK = Route("local", "qwen3:14b", "gpu", False, "fallback")


class Tier0Task(ValueError):
    """Raised when someone tries to use a model for a job plain code does."""


def route(task: str, *, app_id: str, estimated_gbp: float, guard: BudgetGuard, today: date,
          api_up: bool = True) -> Route:
    if task in TIER0:
        raise Tier0Task(f"'{task}' is a plain-code task; no model allowed")
    r = ROUTES.get(task)
    if r is None:
        raise KeyError(f"no route for task '{task}'")
    if r.where != "api":
        return r
    if not api_up:
        return LOCAL_FALLBACK
    if not guard.check(app_id, "ai", estimated_gbp, today).allowed:
        return LOCAL_FALLBACK
    return r
