from datetime import date

import pytest

from gme.budget import BudgetGuard, Policy
from gme.router import LOCAL_FALLBACK, Tier0Task, route

TODAY = date(2026, 11, 22)


def test_plain_code_tasks_never_get_a_model():
    with pytest.raises(Tier0Task):
        route("schedule", app_id="stackup", estimated_gbp=0, guard=BudgetGuard(Policy()), today=TODAY)


def test_captions_go_to_haiku_batch():
    r = route("captions", app_id="stackup", estimated_gbp=0.01, guard=BudgetGuard(Policy()), today=TODAY)
    assert r.model == "claude-haiku-5-5" and r.batch


def test_falls_back_to_local_when_budget_says_no():
    g = BudgetGuard(Policy(portfolio_monthly=0.01))
    r = route("captions", app_id="stackup", estimated_gbp=1, guard=g, today=TODAY)
    assert r == LOCAL_FALLBACK


def test_falls_back_to_local_when_api_down():
    r = route("weekly_report", app_id="stackup", estimated_gbp=0.01, guard=BudgetGuard(Policy()),
              today=TODAY, api_up=False)
    assert r == LOCAL_FALLBACK


def test_visual_qa_stays_on_the_gpu():
    r = route("qa_visual", app_id="stackup", estimated_gbp=0, guard=BudgetGuard(Policy()), today=TODAY)
    assert r.where == "gpu"
