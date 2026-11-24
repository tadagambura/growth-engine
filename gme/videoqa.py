"""Quality gate for a finished video (constitution section 9). Plain code, no model.

A video only goes to the queue if this returns no problems. Checks the file itself (size, length,
loudness, not blank, not frozen) and the script it was built from (every beat present, one CTA, clean text).
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path

from . import dates, qa
from .config import AppConfig
from .scriptwriter import Script


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=120)


def probe(path: Path) -> dict:
    r = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    return json.loads(r.stdout or "{}")


def loudness(path: Path) -> float | None:
    """Integrated loudness in LUFS (EBU R128), or None if it can't be measured."""
    r = _run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"])
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", r.stderr.decode(errors="ignore"))
    return float(m[-1]) if m else None


def sample_frame(path: Path, t: float) -> bytes:
    r = _run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", "scale=48:48,format=gray",
              "-f", "rawvideo", "-"])
    return r.stdout


def check_file(path: Path, voiced: bool, min_s: float, max_s: float) -> list[str]:
    problems: list[str] = []
    if not path.exists() or path.stat().st_size < 100_000:
        return ["video file is missing or too small"]
    info = probe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not v or (v.get("width"), v.get("height")) != (1080, 1920) or v.get("codec_name") != "h264":
        problems.append("video must be H.264 at 1080x1920")
    dur = float(info.get("format", {}).get("duration", 0))
    if not (min_s <= dur <= max_s):
        problems.append(f"duration {dur:.1f}s is outside {min_s:.0f} to {max_s:.0f}s")
    if voiced:
        if not a:
            problems.append("voiced video has no audio track")
        else:
            lufs = loudness(path)
            if lufs is None or not (-20 <= lufs <= -9):
                problems.append(f"loudness {lufs} LUFS is outside -20 to -9")
    frames = [sample_frame(path, dur * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    for i, fr in enumerate(frames):
        if len(fr) < 2000 or statistics.pstdev(fr) < 6:
            problems.append(f"frame {i + 1} of 5 looks blank")
    if len({hashlib.md5(f).hexdigest() for f in frames}) < 3:
        problems.append("the picture looks frozen")
    return problems


def check_script(script: Script, fmt: dict, cfg: AppConfig, cta_text: str, spoken_limit_words: int = 130) -> list[str]:
    problems: list[str] = []
    want = [b["beat"] for b in fmt["beats"]]
    got = [b.beat for b in script.beats]
    if want != got:
        problems.append(f"beats {got} do not match the format {want}")
    ctas = [b for b in script.beats if b.beat == "cta"]
    if len(ctas) != 1 or ctas[0].text != cta_text:
        problems.append("there must be exactly one CTA, matching the plan")
    for b in script.beats:
        if not b.text.strip():
            problems.append(f"beat {b.beat} has no text")
    if len(script.spoken.split()) > spoken_limit_words:
        problems.append(f"script is {len(script.spoken.split())} words (max {spoken_limit_words})")
    for label, text in (("spoken text", script.spoken), ("caption", script.caption), ("title", script.title)):
        problems += [f"{label}: {p}" for p in qa.check(text, "youtube", cfg) if "limit" not in p]
        problems += [f"{label}: mentions the date '{d}' (videos get reused)" for d in dates.find(text)]
    return problems
