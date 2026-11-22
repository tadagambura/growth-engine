"""Budget guard: deterministic spending limits that no AI can change.

Every paid call (AI tokens, X posts, ads) asks the guard first and records what it spent.
Limits come from the owner-controlled policy, never from model output. When a limit is hit
the answer is simply "no", and the caller falls back (local model, evergreen content) or waits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Policy:
    """Owner-set limits in GBP. Loaded from a file the engine can read but not write."""
    portfolio_monthly: float = 10.0
    portfolio_daily: float = 1.0
    per_app_monthly: dict[str, float] = field(default_factory=dict)
    default_app_monthly: float = 2.0
    ads_enabled: bool = False


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@dataclass
class Ledger:
    """Spend records: (day, app_id, category, gbp). Persisted by the caller."""
    entries: list[tuple[date, str, str, float]] = field(default_factory=list)

    def total(self, *, month: tuple[int, int] | None = None, day: date | None = None,
              app_id: str | None = None) -> float:
        s = 0.0
        for d, app, _cat, gbp in self.entries:
            if month and (d.year, d.month) != month:
                continue
            if day and d != day:
                continue
            if app_id and app != app_id:
                continue
            s += gbp
        return s


class BudgetGuard:
    def __init__(self, policy: Policy, ledger: Ledger | None = None):
        self._policy = policy
        self.ledger = ledger or Ledger()

    @property
    def policy(self) -> Policy:
        return self._policy  # read-only: there is deliberately no setter

    def check(self, app_id: str, category: str, estimated_gbp: float, today: date) -> Decision:
        if estimated_gbp < 0:
            return Decision(False, "negative estimate rejected")
        if category == "ads" and not self._policy.ads_enabled:
            return Decision(False, "paid ads are switched off by the owner")
        month = (today.year, today.month)
        checks = [
            (self.ledger.total(month=month), self._policy.portfolio_monthly, "portfolio monthly cap"),
            (self.ledger.total(day=today), self._policy.portfolio_daily, "portfolio daily cap"),
            (self.ledger.total(month=month, app_id=app_id),
             self._policy.per_app_monthly.get(app_id, self._policy.default_app_monthly),
             f"{app_id} monthly cap"),
        ]
        for spent, cap, name in checks:
            if spent + estimated_gbp > cap + 1e-9:
                return Decision(False, f"{name} reached (£{spent:.2f} of £{cap:.2f})")
        return Decision(True, "within limits")

    def record(self, app_id: str, category: str, actual_gbp: float, today: date) -> None:
        self.ledger.entries.append((today, app_id, category, max(0.0, actual_gbp)))

    def usage_share(self, today: date) -> float:
        """Share of the monthly portfolio cap used; alerts fire at 0.5, 0.8 and 1.0."""
        return self.ledger.total(month=(today.year, today.month)) / self._policy.portfolio_monthly
