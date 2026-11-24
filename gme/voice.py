"""Kaos's voice: text to speech with exact word timings (ElevenLabs), plus a monthly character guard.

The ElevenLabs SDK is an optional extra (`pip install -e ".[voice]"`) and is only imported when a real
client is needed, so the rest of the engine stays dependency-free and every test runs with a fake client.
The API key is read from ELEVENLABS_API_KEY (loaded from .env); it never appears in code, config or logs.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

MAX_TEXT_CHARS = 1500       # a 60 s video is about 900 characters; anything longer is a bug


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceConfig:
    voice_id: str
    model_id: str
    output_format: str
    stability: float
    similarity_boost: float
    monthly_character_limit: int
    design_name: str
    design_description: str
    design_preview_text: str


def load_voice_config(path: str | Path) -> VoiceConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    d = raw.get("design", {})
    return VoiceConfig(
        voice_id=raw.get("voice_id", ""), model_id=raw["model_id"], output_format=raw["output_format"],
        stability=float(raw["stability"]), similarity_boost=float(raw["similarity_boost"]),
        monthly_character_limit=int(raw["monthly_character_limit"]),
        design_name=d.get("name", "Kaos"), design_description=d.get("description", ""),
        design_preview_text=d.get("preview_text", ""))


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class VoiceResult:
    audio_path: Path
    characters: int
    duration: float
    words: tuple[Word, ...]
    char_starts: tuple[float, ...] = ()      # per-character timings, for locating where each beat begins
    char_ends: tuple[float, ...] = ()
    text: str = ""


class VoiceUsage:
    """Characters used per month, saved in a small JSON file, so the plan's allowance is never exceeded."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, int] = json.loads(self.path.read_text()) if self.path.exists() else {}

    @staticmethod
    def _key(day: date) -> str:
        return f"{day.year}-{day.month:02d}"

    def used(self, day: date) -> int:
        return self._data.get(self._key(day), 0)

    def allow(self, characters: int, limit: int, day: date) -> bool:
        return self.used(day) + characters <= limit

    def add(self, characters: int, day: date) -> None:
        self._data[self._key(day)] = self.used(day) + characters
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))


def words_from_alignment(characters: list[str], starts: list[float], ends: list[float]) -> tuple[Word, ...]:
    """Group per-character timings into words (runs of non-space characters)."""
    if not (len(characters) == len(starts) == len(ends)):
        raise VoiceError("alignment lists have different lengths")
    words: list[Word] = []
    buf, t0, t1 = "", 0.0, 0.0
    for ch, s, e in zip(characters, starts, ends):
        if ch.isspace():
            if buf:
                words.append(Word(buf, t0, t1))
                buf = ""
            continue
        if not buf:
            t0 = s
        buf += ch
        t1 = e
    if buf:
        words.append(Word(buf, t0, t1))
    return tuple(words)


def make_client(env_path: str = ".env"):
    """A real ElevenLabs client. Needs the `voice` extra and ELEVENLABS_API_KEY (loaded from .env)."""
    import os
    try:
        from dotenv import load_dotenv
    except ImportError as e:  # pragma: no cover
        raise VoiceError('install the voice extra: pip install -e ".[voice]"') from e
    load_dotenv(env_path)            # first: the SDK reads the environment when it is imported
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        raise VoiceError(f"ELEVENLABS_API_KEY not found (looked in the environment and {env_path})")
    from elevenlabs import ElevenLabs
    return ElevenLabs(api_key=key)


def synthesize(text: str, out_path: str | Path, cfg: VoiceConfig, client, usage: VoiceUsage,
               today: date) -> VoiceResult:
    """Speak `text` in Kaos's voice and return the audio file plus word timings for captions."""
    body = text.strip()
    if not cfg.voice_id:
        raise VoiceError("no voice chosen yet: run `python -m gme voice previews`, pick one, then `voice save`")
    if not body:
        raise VoiceError("nothing to say")
    if len(body) > MAX_TEXT_CHARS:
        raise VoiceError(f"{len(body)} characters is over the {MAX_TEXT_CHARS} limit for one video")
    if not usage.allow(len(body), cfg.monthly_character_limit, today):
        raise VoiceError(f"monthly voice limit reached ({usage.used(today)} of {cfg.monthly_character_limit} characters)")
    from elevenlabs import VoiceSettings
    resp = client.text_to_speech.convert_with_timestamps(
        cfg.voice_id, text=body, model_id=cfg.model_id, output_format=cfg.output_format,
        voice_settings=VoiceSettings(stability=cfg.stability, similarity_boost=cfg.similarity_boost))
    align = resp.alignment or resp.normalized_alignment
    if align is None:
        raise VoiceError("ElevenLabs returned no timing data")
    words = words_from_alignment(list(align.characters), list(align.character_start_times_seconds),
                                 list(align.character_end_times_seconds))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(resp.audio_base_64))
    usage.add(len(body), today)
    return VoiceResult(out, len(body), words[-1].end if words else 0.0, words,
                       tuple(align.character_start_times_seconds), tuple(align.character_end_times_seconds), body)


def design_previews(cfg: VoiceConfig, client, out_dir: str | Path) -> list[tuple[str, Path, float]]:
    """Ask ElevenLabs for voice previews from Kaos's description. Returns (generated_voice_id, mp3 path, seconds).
    This spends a small amount of credit; the owner picks one, then `save_voice` keeps it."""
    res = client.text_to_voice.design(voice_description=cfg.design_description, text=cfg.design_preview_text)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    found = []
    for i, p in enumerate(res.previews, 1):
        path = out / f"kaos-preview-{i}.mp3"
        path.write_bytes(base64.b64decode(p.audio_base_64))
        found.append((p.generated_voice_id, path, float(p.duration_secs)))
    return found


def save_voice(cfg: VoiceConfig, client, generated_voice_id: str) -> str:
    """Keep the chosen preview as a permanent voice and return its voice_id (the owner commits it to voice.json)."""
    voice = client.text_to_voice.create(voice_name=cfg.design_name, voice_description=cfg.design_description,
                                        generated_voice_id=generated_voice_id)
    return voice.voice_id
