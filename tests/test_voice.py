import base64
import json
from datetime import date
from types import SimpleNamespace

import pytest

from gme import captions
from gme.voice import (VoiceError, VoiceUsage, Word, design_previews, load_voice_config, save_voice, synthesize,
                       words_from_alignment)

pytest.importorskip("elevenlabs")
TODAY = date(2026, 12, 1)
CFG = load_voice_config("configs/voice.json")
CHOSEN = CFG.__class__(**{**CFG.__dict__, "voice_id": "voice123"})
TEXT = "Ran out of money? Check £14 before payday."


def fake_alignment(text, step=0.05):
    return SimpleNamespace(characters=list(text), character_start_times_seconds=[i * step for i in range(len(text))],
                           character_end_times_seconds=[(i + 1) * step for i in range(len(text))])


class FakeClient:
    def __init__(self):
        self.calls = []
        self.text_to_speech = SimpleNamespace(convert_with_timestamps=self._tts)
        self.text_to_voice = SimpleNamespace(design=self._design, create=lambda **kw: SimpleNamespace(voice_id="saved1"))

    def _tts(self, voice_id, **kw):
        self.calls.append((voice_id, kw))
        return SimpleNamespace(audio_base_64=base64.b64encode(b"fake-mp3").decode(), alignment=fake_alignment(kw["text"]),
                               normalized_alignment=None)

    def _design(self, **kw):
        p = lambda i: SimpleNamespace(audio_base_64=base64.b64encode(b"p%d" % i).decode(), generated_voice_id=f"gv{i}",
                                      duration_secs=4.5)
        return SimpleNamespace(previews=[p(1), p(2), p(3)])


def test_config_is_owner_controlled_and_starts_with_no_voice():
    assert CFG.voice_id == "" and CFG.model_id == "eleven_v4" and CFG.monthly_character_limit == 100000
    assert len(CFG.design_preview_text) >= 100 and len(CFG.design_description) >= 20


def test_alignment_becomes_words_with_start_and_end():
    w = words_from_alignment(list("hi there"), [0, .1, .2, .3, .4, .5, .6, .7], [.1, .2, .3, .4, .5, .6, .7, .8])
    assert w == (Word("hi", 0, .2), Word("there", .3, .8))
    with pytest.raises(VoiceError):
        words_from_alignment(["a"], [0], [])


def test_synthesize_writes_audio_returns_timings_and_counts_characters(tmp_path):
    usage = VoiceUsage(tmp_path / "usage.json")
    client = FakeClient()
    r = synthesize(TEXT, tmp_path / "v.mp3", CHOSEN, client, usage, TODAY)
    assert (tmp_path / "v.mp3").read_bytes() == b"fake-mp3"
    assert r.characters == len(TEXT) and [w.text for w in r.words][:2] == ["Ran", "out"]
    assert r.duration == pytest.approx(len(TEXT) * 0.05)
    assert client.calls[0][0] == "voice123" and client.calls[0][1]["model_id"] == "eleven_v4"
    assert VoiceUsage(tmp_path / "usage.json").used(TODAY) == len(TEXT)       # survives a restart


def test_refuses_without_a_voice_over_the_limit_or_when_empty(tmp_path):
    usage = VoiceUsage(tmp_path / "u.json")
    with pytest.raises(VoiceError, match="no voice chosen"):
        synthesize(TEXT, tmp_path / "a.mp3", CFG, FakeClient(), usage, TODAY)
    with pytest.raises(VoiceError, match="nothing to say"):
        synthesize("  ", tmp_path / "a.mp3", CHOSEN, FakeClient(), usage, TODAY)
    with pytest.raises(VoiceError, match="over the"):
        synthesize("x" * 2000, tmp_path / "a.mp3", CHOSEN, FakeClient(), usage, TODAY)
    tight = CHOSEN.__class__(**{**CHOSEN.__dict__, "monthly_character_limit": 50})
    synthesize(TEXT, tmp_path / "a.mp3", tight, FakeClient(), usage, TODAY)
    with pytest.raises(VoiceError, match="monthly voice limit"):
        synthesize(TEXT, tmp_path / "b.mp3", tight, FakeClient(), usage, TODAY)
    assert synthesize(TEXT, tmp_path / "c.mp3", tight, FakeClient(), usage, date(2027, 1, 2)).characters  # new month resets


def test_previews_and_saving_the_chosen_voice(tmp_path):
    found = design_previews(CFG, FakeClient(), tmp_path)
    assert [f[0] for f in found] == ["gv1", "gv2", "gv3"] and found[0][1].read_bytes() == b"p1"
    assert save_voice(CFG, FakeClient(), "gv2") == "saved1"


def test_captions_are_short_timed_and_highlight_numbers(tmp_path):
    r = synthesize(TEXT, tmp_path / "v.mp3", CHOSEN, FakeClient(), VoiceUsage(tmp_path / "u.json"), TODAY)
    caps = captions.chunk(r.words)
    assert [c.text for c in caps] == ["Ran out of", "money?", "Check £14 before", "payday."]
    assert all(len(c.text.split()) <= 3 for c in caps)
    assert all(a.end <= b.start + 1e-9 for a, b in zip(caps, caps[1:]))           # never overlap
    assert all(c.end - c.start >= 0.35 - 1e-9 for c in caps)
    assert caps[2].emphasis == (1,)                                               # the £14 (second word)
    data = json.loads(json.dumps(captions.to_json(caps)))
    assert data[0]["text"] == "Ran out of" and "00:00:00,000 -->" in captions.to_srt(caps)
