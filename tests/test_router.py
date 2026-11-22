from datetime import datetime

import pytest

from gme.budget import BudgetGuard, Policy
from gme.router import HAIKU, LOCAL_TEXT, WAIT, GpuWindow, Tier0Task, route

DAY = datetime(2026, 11, 23, 11, 0)
NIGHT = datetime(2026, 11, 23, 23, 30)
EARLY = datetime(2026, 11, 23, 7, 59)


def g(**kw):
    return BudgetGuard(Policy(**kw))


def r(task, now=DAY, **kw):
    return route(task, app_id="stackup", estimated_gbp=0.01, guard=kw.pop("guard", g()), now=now, **kw)


def test_plain_code_tasks_never_get_a_model():
    with pytest.raises(Tier0Task):
        r("schedule")


def test_daytime_drafts_run_on_the_gpu():
    assert r("captions").where == "gpu"


@pytest.mark.parametrize("now", [NIGHT, EARLY])
def test_quiet_hours_mean_no_gpu_work(now):
    assert r("captions", now=now) == WAIT
    assert r("qa_visual", now=now) == WAIT


def test_due_job_at_night_uses_haiku_if_budget_allows():
    out = r("captions", now=NIGHT, due_now=True)
    assert out.where == "api" and out.model == HAIKU


def test_due_job_at_night_waits_when_over_budget():
    assert r("captions", now=NIGHT, due_now=True, guard=g(portfolio_monthly=0.001)) == WAIT


def test_busy_gpu_defers_daytime_work():
    assert r("captions", gpu_busy=True) == WAIT


def test_quality_check_uses_haiku():
    assert r("qa_text").model == HAIKU


def test_quality_check_falls_back_to_local_in_the_day_when_over_budget():
    assert r("qa_text", guard=g(portfolio_monthly=0.001)) == LOCAL_TEXT


def test_quality_check_waits_at_night_when_over_budget():
    assert r("qa_text", now=NIGHT, guard=g(portfolio_monthly=0.001)) == WAIT


def test_window_is_configurable_and_validated():
    assert GpuWindow(8, 22).is_open(datetime(2026, 1, 1, 21, 30))
    with pytest.raises(ValueError):
        GpuWindow(21, 9)
