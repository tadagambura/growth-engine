import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from gme import daily
from gme.postiz import PostizPublisher
from gme.scriptwriter import BeatText, Script, cta_text

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 12, 1, 6, 30, tzinfo=timezone.utc)


def make_env(tmp_path, monkeypatch):
    monkeypatch.setattr(daily, "make_client", lambda *_: None)
    return daily.build_env(ROOT, tmp_path, secrets={})


def fake_producer(ok=True):
    calls = []

    def producer(slot, fmt, atom, cfg, writer, voice_cfg, client, usage, content, today, out_dir, work_dir, occasion=None, last_demo=None):
        calls.append((slot, occasion))
        beats = [BeatText(b["beat"], cta_text(content, slot.cta_id, cfg.name) if b["beat"] == "cta" else f"{b['beat']} words.",
                          tuple(b["acts"]), b["layout"], 3.0) for b in fmt["beats"]]
        out_dir.mkdir(parents=True, exist_ok=True)
        mp4 = out_dir / f"{slot.day}.mp4"
        mp4.write_bytes(b"x")
        return SimpleNamespace(mp4=mp4, script=Script(fmt["id"], atom.id, beats, "A caption.", "A title", "model"), voiced=False,
                               duration=25.0, notes=[])
    return producer, calls


def test_a_day_is_planned_queued_for_every_platform_published_and_not_repeated(tmp_path, monkeypatch):
    env = make_env(tmp_path, monkeypatch)
    prod, calls = fake_producer()
    monkeypatch.setattr(daily.videoqa, "check_file", lambda *a, **k: [])
    out = daily.run_day(env, date(2026, 12, 1), NOW, producer=prod)
    assert out["status"] == "ok" and out["app"] == "stackup" and len(calls) == 1
    assert len(out["posts"]) == 8 and all(p["status"] == "approved" for p in out["posts"])      # automatic mode, all platforms
    assert (tmp_path / "outbox.jsonl").exists() is (len(out["published"]["published"]) > 0)       # due posts are logged
    assert daily.run_day(env, date(2026, 12, 1), NOW, producer=prod)["status"] == "already done"
    nxt = daily.run_day(env, date(2026, 12, 2), NOW, producer=prod)
    assert nxt["atom"] != out["atom"]                                                              # history keeps atoms from repeating


def test_a_failing_video_retries_then_safe_mode_then_alerts_and_posts_nothing(tmp_path, monkeypatch):
    env = make_env(tmp_path, monkeypatch)
    sent = []
    env.bot = SimpleNamespace(send=lambda t: sent.append(t))
    prod, calls = fake_producer()
    monkeypatch.setattr(daily.videoqa, "check_file", lambda *a, **k: ["the picture looks frozen"])
    out = daily.run_day(env, date(2026, 12, 1), NOW, producer=prod)
    assert out["status"] == "failed" and len(calls) == 3 and sent and "frozen" in sent[0]
    assert env.queue.pending() == [] and env.queue.due(NOW) == []


def test_pause_queues_but_never_publishes(tmp_path, monkeypatch):
    env = make_env(tmp_path, monkeypatch)
    (tmp_path / "PAUSED").write_text("x")
    prod, _ = fake_producer()
    monkeypatch.setattr(daily.videoqa, "check_file", lambda *a, **k: [])
    out = daily.run_day(env, date(2026, 12, 1), datetime(2026, 12, 1, 18, 0, tzinfo=timezone.utc), producer=prod)
    assert out["paused"] and out["published"]["published"] == [] and not (tmp_path / "outbox.jsonl").exists()


def test_greeting_day_uses_the_brand_account_fixed_words_and_no_sales(tmp_path, monkeypatch):
    env = make_env(tmp_path, monkeypatch)
    prod, calls = fake_producer()
    monkeypatch.setattr(daily.videoqa, "check_file", lambda *a, **k: [])
    out = daily.run_day(env, date(2027, 6, 1), NOW, producer=prod)
    assert out["status"] == "ok" and out["app"] == "kaoticchainz" and out["format"] == "greeting"
    assert calls[0][0].cta_id == "follow" and not any("waitlist" in json.dumps(p) for p in out["posts"])


def test_post_time_is_after_work_on_weekdays_and_mid_morning_at_weekends():
    assert daily.post_time(date(2026, 12, 1)).hour == 17          # winter: London = UTC
    assert daily.post_time(date(2026, 12, 5)).hour == 10


def test_safe_mode_rescues_the_day_with_no_model_and_no_voice(tmp_path, monkeypatch):
    env = make_env(tmp_path, monkeypatch)
    sent = []
    env.bot = SimpleNamespace(send=lambda t: sent.append(t))
    good, calls = fake_producer()
    seen = []

    def producer(slot, fmt, atom, cfg, writer, voice_cfg, client, usage, content, today, out_dir, work_dir, occasion=None, last_demo=None):
        seen.append((writer.transport, client))
        if len(seen) < 3:
            raise RuntimeError("render crashed")
        return good(slot, fmt, atom, cfg, writer, voice_cfg, client, usage, content, today, out_dir, work_dir, occasion)

    monkeypatch.setattr(daily.videoqa, "check_file", lambda *a, **k: [])
    out = daily.run_day(env, date(2026, 12, 1), NOW, producer=producer)
    assert out["status"] == "ok" and seen[2] == (None, None)                 # third attempt: no model, no voice
    assert any("safe mode" in n for n in out["notes"]) and sent


def test_a_real_publisher_only_gets_posts_for_connected_channels(tmp_path, monkeypatch):
    env = make_env(tmp_path, monkeypatch)
    env.publisher = PostizPublisher({"integrations": {"bluesky": "abc", "x": ""}}, lambda *a, **k: [])
    prod, _ = fake_producer()
    monkeypatch.setattr(daily.videoqa, "check_file", lambda *a, **k: [])
    out = daily.run_day(env, date(2026, 12, 1), NOW, producer=prod)
    assert [p["platform"] for p in out["posts"]] == ["bluesky"]
