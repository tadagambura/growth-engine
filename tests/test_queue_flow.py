from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from gme import qa
from gme.config import load
from gme.publisher import DryRunPublisher, publish_due
from gme.queue import Queue, QueueError
from gme.telegram import TelegramBot, apply_decisions

NOW = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)
CFG = replace(load("configs/apps/stackup.json"), status="draft", publishing_mode="approval")
ACTIVE = replace(CFG, status="active")
AUTO = replace(ACTIVE, publishing_mode="automatic")
GOOD = "Week 1 of the 52-week challenge is £1. Start tiny. #StackUp"


def test_qa_catches_banned_phrase_hashtags_and_foreign_links():
    assert qa.check(GOOD, "x", CFG) == []
    assert any("banned" in p for p in qa.check("Guaranteed savings", "x", CFG))
    assert any("hashtags" in p for p in qa.check("a #a #b #c #d", "x", CFG))
    assert any("not one of" in p for p in qa.check("see https://evil.example/x", "x", CFG))
    assert any("limit" in p for p in qa.check("x" * 300, "x", CFG))
    assert qa.check("   ", "x", CFG) == ["post is empty"]


def test_approval_mode_waits_for_owner_then_publishes_only_when_active():
    q = Queue()
    p = q.add(CFG, "bluesky", GOOD, NOW, NOW)
    assert p.status == "pending_approval" and q.due(NOW) == []
    q.approve(p.id, NOW)
    pub = DryRunPublisher()
    # the app is still a draft, so nothing goes out
    assert publish_due(q, pub, {"stackup": CFG}, NOW)["skipped"] == [p.id] and pub.sent == []
    assert publish_due(q, pub, {"stackup": ACTIVE}, NOW)["published"] == [p.id]
    assert q.get(p.id).status == "published" and q.get(p.id).external_id == f"dryrun-{p.id}"


def test_qa_failure_never_reaches_the_owner_or_a_platform():
    q = Queue()
    p = q.add(ACTIVE, "bluesky", "Guaranteed to get rich", NOW, NOW)
    assert p.status == "qa_failed" and q.pending() == []
    with pytest.raises(QueueError):
        q.approve(p.id, NOW)


def test_automatic_mode_skips_approval_but_not_qa():
    q = Queue()
    assert q.add(AUTO, "bluesky", GOOD, NOW, NOW).status == "approved"
    assert q.add(AUTO, "bluesky", "risk-free!", NOW, NOW).status == "qa_failed"


def test_off_mode_and_unknown_platform_are_refused():
    q = Queue()
    with pytest.raises(QueueError):
        q.add(replace(ACTIVE, publishing_mode="off"), "bluesky", GOOD, NOW, NOW)
    with pytest.raises(QueueError):
        q.add(ACTIVE, "myspace", GOOD, NOW, NOW)


def test_future_posts_wait_and_failures_dont_block_others():
    q = Queue()
    later = q.add(AUTO, "bluesky", GOOD, NOW + timedelta(days=1), NOW)
    bad = q.add(AUTO, "bluesky", GOOD + " one", NOW, NOW)
    ok = q.add(AUTO, "bluesky", GOOD + " two", NOW, NOW)

    class Flaky(DryRunPublisher):
        def publish(self, post):
            if post.id == bad.id:
                raise RuntimeError("platform down")
            return super().publish(post)

    out = publish_due(q, Flaky(), {"stackup": AUTO}, NOW)
    assert out["failed"] == [bad.id] and out["published"] == [ok.id]
    assert q.get(later.id).status == "approved"
    assert "platform down" in q.get(bad.id).error
    q.retry(bad.id, NOW)
    assert q.get(bad.id).status == "approved"


def test_naive_datetimes_are_rejected():
    with pytest.raises(QueueError):
        Queue().add(AUTO, "x", GOOD, datetime(2026, 12, 1), NOW)


def test_telegram_only_obeys_the_owner_and_applies_decisions():
    sent = []
    bot = TelegramBot("TOKEN", 42, transport=lambda m, p: sent.append((m, p)) or {"result": []})
    q = Queue()
    p = q.add(CFG, "bluesky", GOOD, NOW, NOW)
    bot.request_approval(p)
    kb = sent[0][1]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in kb] == [f"approve:{p.id}", f"reject:{p.id}"]
    mine = {"callback_query": {"data": f"approve:{p.id}", "message": {"chat": {"id": 42}}}}
    stranger = {"callback_query": {"data": f"approve:{p.id}", "message": {"chat": {"id": 99}}}}
    junk = {"callback_query": {"data": "approve:abc", "message": {"chat": {"id": 42}}}}
    assert bot.decisions([stranger, junk]) == []
    notes = apply_decisions(bot, q, bot.decisions([mine, mine]), NOW)
    assert q.get(p.id).status == "approved"
    assert "could not approve" in notes[1]      # the second tap is reported, not fatal
    assert "TOKEN" not in repr(bot)


def test_pause_skips_everything_and_keeps_posts_queued():
    q = Queue()
    p = q.add(AUTO, "bluesky", GOOD, NOW, NOW)
    pub = DryRunPublisher()
    assert publish_due(q, pub, {"stackup": AUTO}, NOW, paused=True)["skipped"] == [p.id]
    assert pub.sent == [] and q.get(p.id).status == "approved"
    assert publish_due(q, pub, {"stackup": AUTO}, NOW)["published"] == [p.id]
