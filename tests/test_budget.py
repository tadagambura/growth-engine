from datetime import date

from gme.budget import BudgetGuard, Policy

TODAY = date(2026, 11, 22)


def guard(**kw):
    return BudgetGuard(Policy(**{"portfolio_monthly": 10, "portfolio_daily": 1, "default_app_monthly": 2, **kw}))


def test_within_limits_is_allowed():
    assert guard().check("stackup", "ai", 0.10, TODAY).allowed


def test_daily_cap_blocks():
    g = guard()
    g.record("stackup", "ai", 0.95, TODAY)
    d = g.check("stackup", "ai", 0.10, TODAY)
    assert not d.allowed and "daily" in d.reason


def test_per_app_cap_blocks_even_when_portfolio_has_room():
    g = guard(portfolio_daily=100)
    for day in range(1, 5):
        g.record("stackup", "ai", 0.5, date(2026, 11, day))
    assert not g.check("stackup", "ai", 0.01, TODAY).allowed
    assert g.check("worthit", "ai", 0.01, TODAY).allowed


def test_monthly_cap_resets_next_month():
    g = guard(portfolio_daily=100, default_app_monthly=100)
    g.record("stackup", "ai", 10, TODAY)
    assert not g.check("stackup", "ai", 0.01, TODAY).allowed
    assert g.check("stackup", "ai", 0.01, date(2026, 12, 1)).allowed


def test_ads_are_refused_while_switched_off():
    d = guard().check("stackup", "ads", 0.01, TODAY)
    assert not d.allowed and "switched off" in d.reason


def test_policy_cannot_be_reassigned():
    g = guard()
    try:
        g.policy = Policy(portfolio_monthly=1_000_000)  # type: ignore[misc]
    except AttributeError:
        pass
    assert g.policy.portfolio_monthly == 10


def test_negative_estimates_rejected():
    assert not guard().check("stackup", "ai", -5, TODAY).allowed
