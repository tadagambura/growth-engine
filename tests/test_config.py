import json
from pathlib import Path

import pytest

from gme.config import ConfigError, load_all, parse

APPS = Path(__file__).parent.parent / "configs" / "apps"


def base():
    return json.loads((APPS / "stackup.json").read_text())


def test_all_shipped_configs_are_valid():
    apps = load_all(APPS)
    assert "stackup" in apps
    assert apps["stackup"].budgets.ads_enabled is False


def test_pillar_shares_must_sum_to_one():
    raw = base()
    raw["pillars"]["Direct promotion"] = 0.5
    with pytest.raises(ConfigError, match="sum to 1.0"):
        parse(raw)


def test_unknown_platform_rejected():
    raw = base()
    raw["platforms"]["myspace"] = 3
    with pytest.raises(ConfigError, match="unknown platforms"):
        parse(raw)


def test_ads_cannot_be_enabled_on_a_draft_app():
    raw = base()
    raw["budgets"]["ads_enabled"] = True
    with pytest.raises(ConfigError, match="ads can only be enabled"):
        parse(raw)


def test_every_problem_is_reported_at_once():
    raw = base()
    raw["tone"] = "Shouty"
    raw["status"] = "live"
    with pytest.raises(ConfigError) as e:
        parse(raw)
    assert len(e.value.problems) == 2
