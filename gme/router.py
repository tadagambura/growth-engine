"""Model router: the cheapest thing that does the job.

Owner's rules:
- Tier 0 tasks never touch a model.
- The home GPU does the volume (first drafts, visual QA, embeddings), but only inside its
  working window (09:00-21:00 by default). Quiet hours mean no GPU work at all.
- The Claude API is a small, capped quality layer. It also covers a due job when the GPU is
  outside its window or busy, if the budget allows. Otherwise the job waits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .budget import BudgetGuard

TIER0 = {"schedule", "publish", "analytics", "budget", "dedup_exact", "utm", "notify", "link_check"}


@dataclass(frozen=True)
class GpuWindow:
    """Hours the GPU may work (local time, end exclusive). Default 09:00-21:00."""
    start_hour: int = 9
    end_hour: int = 21

    def __post_init__(self):
        if not (0 <= self.start_hour < self.end_hour <= 24):
            raise ValueError("GPU window must be within one day, start before end")

    def is_open(self, now: datetime) -> bool:
        return self.start_hour <= now.hour < self.end_hour


@dataclass(frozen=True)
class Route:
    tier: str
    model: str | None
    where: str                      # "gpu", "api" or "wait"
    batch: bool
    fallback: str | None = None     # API model to use if the GPU can't take a due job
    note: str = ""


HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"
ROUTES: dict[str, Route] = {
    "captions":      Route("local", "qwen3:14b", "gpu", False, fallback=HAIKU),
    "hooks":         Route("local", "qwen3:14b", "gpu", False, fallback=HAIKU),
    "scripts":       Route("local", "qwen3:14b", "gpu", False, fallback=HAIKU),
    "qa_visual":     Route("local", "qwen2.5vl:7b", "gpu", False),
    "embed":         Route("local", "nomic-embed-text", "gpu", False),
    "qa_text":       Route("api-cheap", HAIKU, "api", True),
    "polish":        Route("api-cheap", HAIKU, "api", True),
    "weekly_report": Route("api-mid", SONNET, "api", True),
    "strategy":      Route("api-mid", SONNET, "api", False, note="launch and quarterly only"),
}
WAIT = Route("wait", None, "wait", False, note="queued until the GPU window opens or budget allows")
LOCAL_TEXT = Route("local", "qwen3:14b", "gpu", False, note="API unavailable or over budget")


class Tier0Task(ValueError):
    """Raised when someone tries to use a model for a job plain code does."""


def route(task: str, *, app_id: str, estimated_gbp: float, guard: BudgetGuard, now: datetime,
          window: GpuWindow = GpuWindow(), gpu_busy: bool = False, api_up: bool = True,
          due_now: bool = False) -> Route:
    if task in TIER0:
        raise Tier0Task(f"'{task}' is a plain-code task; no model allowed")
    r = ROUTES.get(task)
    if r is None:
        raise KeyError(f"no route for task '{task}'")
    today: date = now.date()
    gpu_ok = window.is_open(now) and not gpu_busy

    def api_allowed() -> bool:
        return api_up and guard.check(app_id, "ai", estimated_gbp, today).allowed

    if r.where == "gpu":
        if gpu_ok:
            return r
        if due_now and r.fallback and api_allowed():
            return Route("api-cheap", r.fallback, "api", True, note="GPU unavailable, job due")
        return WAIT
    # API task
    if api_allowed():
        return r
    if task in {"qa_text", "polish"} and gpu_ok:
        return LOCAL_TEXT
    return WAIT
