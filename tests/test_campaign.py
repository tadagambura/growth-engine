import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from gme.campaign import CampaignError, add_campaign
from gme.cli import main
from gme.config import load_all
from gme.queue import Queue

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGN = json.loads((ROOT / "configs/campaigns/launch-week.json").read_text())
APPS = load_all(ROOT / "configs/apps")
BEFORE = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
EVERY = ("tiktok", "instagram", "youtube", "facebook", "threads", "bluesky", "x", "pinterest")


def videos(tmp_path):
    for p in CAMPAIGN["posts"]:
        (tmp_path / p["media"]).write_bytes(b"mp4")
    return tmp_path


def test_every_launch_post_passes_qa_on_every_platform(tmp_path):
    out = add_campaign(CAMPAIGN, Queue(), APPS, videos(tmp_path), lambda p: True, BEFORE)
    assert out["qa_failed"] == []
    wanted = sum(1 for e in CAMPAIGN["posts"] for p in EVERY if p in APPS[e["app"]].platforms)
    assert len(out["added"]) == wanted


def test_only_connected_platforms_get_posts_with_the_right_text(tmp_path):
    q = Queue()
    add_campaign(CAMPAIGN, q, APPS, videos(tmp_path), lambda p: p == "bluesky", BEFORE)
    posts = q.due(datetime(2026, 12, 1, tzinfo=timezone.utc))
    assert [p.platform for p in posts] == ["bluesky"] * len(CAMPAIGN["posts"])
    assert posts[0].text == CAMPAIGN["posts"][0]["short"]
    assert posts[0].scheduled_for == datetime(2026, 11, 26, 17, 30, tzinfo=timezone.utc)


def test_importing_twice_adds_nothing_and_past_days_are_skipped(tmp_path):
    q, media = Queue(), videos(tmp_path)
    later = datetime(2026, 11, 27, 18, tzinfo=timezone.utc)
    first = add_campaign(CAMPAIGN, q, APPS, media, lambda p: p == "bluesky", later)
    again = add_campaign(CAMPAIGN, q, APPS, media, lambda p: p == "bluesky", later)
    assert len(first["added"]) == 3 and len(first["past"]) == 3
    assert again["added"] == [] and len(again["already_queued"]) == 3


def test_a_missing_video_adds_nothing(tmp_path):
    q = Queue()
    with pytest.raises(CampaignError, match="videos missing"):
        add_campaign(CAMPAIGN, q, APPS, tmp_path, lambda p: True, BEFORE)
    assert q.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0


def test_the_command_refuses_while_posting_is_off(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GME_HOME", str(tmp_path))
    log_only = SimpleNamespace(publisher=object())              # the dry-run publisher has no channels
    monkeypatch.setattr("gme.daily.build_env", lambda *a, **k: log_only)
    assert main(["campaign", "launch-week"]) == 1
    assert "posting is off" in capsys.readouterr().err
