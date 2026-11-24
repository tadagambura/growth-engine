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


def test_category_caps_are_separate_from_each_other():
    g = guard(portfolio_monthly=20, portfolio_daily=100, default_app_monthly=100, category_monthly={"ai": 10, "video": 10})
    g.record("stackup", "ai", 9.9, date(2026, 11, 1))
    assert not g.check("stackup", "ai", 0.5, TODAY).allowed          # ai is full
    assert g.check("stackup", "video", 5.0, TODAY).allowed           # video is untouched
    assert "ai monthly cap" in g.check("stackup", "ai", 0.5, TODAY).reason


def test_revenue_tiers_only_raise_caps_and_never_lower_them():
    from gme.budget import load_policy
    p = load_policy("configs/policy.json")
    assert p.category_monthly == {"ai": 10.0, "video": 10.0}
    assert p.at_revenue(50).category_monthly == {"ai": 10.0, "video": 10.0}
    mid = p.at_revenue(350)
    assert mid.category_monthly == {"ai": 25.0, "video": 30.0} and mid.portfolio_monthly >= 55
    assert p.at_revenue(5000).category_monthly["video"] == 80.0
    assert p.at_revenue(0).category_monthly == p.category_monthly      # the base policy is untouched


def test_ledger_survives_a_restart(tmp_path):
    path = tmp_path / "ledger.json"
    g = BudgetGuard(Policy(portfolio_monthly=10, portfolio_daily=100, default_app_monthly=100), path=path)
    g.record("stackup", "ai", 9.5, TODAY)
    g2 = BudgetGuard(Policy(portfolio_monthly=10, portfolio_daily=100, default_app_monthly=100), path=path)
    assert g2.ledger.total(month=(2026, 11)) == 9.5
    assert not g2.check("stackup", "ai", 1.0, TODAY).allowed
