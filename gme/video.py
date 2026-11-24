"""Produce one video: script -> voice -> beat timings -> captions -> demo footage -> render.

Everything between the script and the file is plain code. The voice (ElevenLabs) is the only paid step
besides the script; if it fails or is over its limit the video is still made, silent, with captions timed
to an estimated speaking pace, so a day is never skipped.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import captions as cap
from .atoms import Atom
from .config import AppConfig
from .scriptwriter import Script, Writer
from .voice import VoiceConfig, VoiceError, VoiceUsage, Word, synthesize

ROOT = Path(__file__).resolve().parent.parent
LEAD = 0.3          # seconds of picture before the voice starts
TAIL = 1.2          # seconds held after the last word (the end card)
FPS = 30


class VideoError(RuntimeError):
    pass


@dataclass
class VideoResult:
    mp4: Path
    srt: Path
    meta: Path
    script: Script
    voiced: bool
    duration: float
    demo: str | None = None
    notes: list[str] = field(default_factory=list)


def estimate_words(text: str, wps: float, start: float = 0.0) -> tuple[Word, ...]:
    """Evenly timed words for the silent fallback (about wps words a second, longer words take longer)."""
    toks = text.split()
    total = max(1, sum(len(t) + 2 for t in toks))
    span = len(toks) / wps
    t, out = start, []
    for tok in toks:
        d = span * (len(tok) + 2) / total
        out.append(Word(tok, t, t + d))
        t += d
    return tuple(out)


def beat_windows(script: Script, voice_text: str, char_starts, char_ends, voice_end: float) -> list[tuple[float, float]]:
    """Where each beat begins and ends in the voice track, found from the per-character timings."""
    spans, pos = [], 0
    for b in script.beats:
        i = voice_text.find(b.text, pos)
        if i < 0:
            raise VideoError(f"beat '{b.beat}' not found in the spoken text")
        spans.append((i, i + len(b.text) - 1))
        pos = i + len(b.text)
    out = []
    for k, (i, j) in enumerate(spans):
        start = char_starts[i]
        nxt = char_starts[spans[k + 1][0]] if k + 1 < len(spans) else voice_end
        out.append((start, max(nxt, char_ends[j])))
    return out


def pick_demo(atom: Atom, beat_seconds: float, avoid: str | None) -> tuple[str, Path, float] | None:
    """The recorded walk-through for this atom. Features, use cases, moments and games only get footage that is
    explicitly mapped to them (never a mismatched screen); cards and lessons use their kind's clip."""
    cfgp = ROOT / f"configs/journeys/{atom.app_id}.json"
    if not cfgp.exists():
        return None
    cfg = json.loads(cfgp.read_text())
    if atom.id in cfg.get("atoms", {}):
        names = [cfg["atoms"][atom.id]]
    elif atom.kind in cfg.get("strict_kinds", []):
        return None
    else:
        names = cfg["map"].get(atom.kind) or []
    best = None
    for n in names:
        meta, mp4 = ROOT / f"assets/demos/{atom.app_id}/{n}.json", ROOT / f"assets/demos/{atom.app_id}/{n}.mp4"
        if not (meta.exists() and mp4.exists()):
            continue
        secs = json.loads(meta.read_text())["seconds"]
        score = abs(math.log(secs / max(beat_seconds, 0.5))) + (0.4 if n == avoid else 0)
        if best is None or score < best[0]:
            best = (score, n, mp4, secs)
    return None if best is None else (best[1], best[2], best[3])


def extract_demo_frames(mp4: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps={FPS},scale=462:1000", "-q:v", "3",
                        str(out_dir / "f%05d.jpg")], capture_output=True)
    if r.returncode:
        raise VideoError("could not extract demo frames: " + r.stderr.decode()[:200])
    return len(list(out_dir.glob("f*.jpg")))


def produce(slot, fmt: dict, atom: Atom, cfg: AppConfig, writer: Writer, voice_cfg: VoiceConfig, client,
            usage: VoiceUsage, content: dict, today: date, out_dir: Path, work_dir: Path,
            occasion: str | None = None, last_demo: str | None = None) -> VideoResult:
    notes: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    script = writer.write(slot, fmt, atom, cfg, today, occasion=occasion)
    if script.source == "evergreen":
        notes.append("script fell back to evergreen: " + "; ".join(script.problems[:3]))
    wps = content["words_per_second"]

    # ---- voice (or a silent estimate) ----
    spoken = " ".join(b.text for b in script.beats)
    voiced = False
    audio = None
    try:
        res = synthesize(spoken, work_dir / "voice.mp3", voice_cfg, client, usage, today)
        windows = [(a + LEAD, b + LEAD) for a, b in beat_windows(script, res.text, res.char_starts, res.char_ends, res.duration)]
        words = tuple(Word(w.text, w.start + LEAD, w.end + LEAD) for w in res.words)
        audio, voiced, voice_end = res.audio_path, True, res.duration + LEAD
    except Exception as e:     # no voice chosen, over the limit, no key, API down: carry on silently
        notes.append(f"silent fallback: {type(e).__name__}: {e}"[:200])
        t, windows, words_l = LEAD, [], []
        for b in script.beats:
            ws = estimate_words(b.text, wps, t)
            windows.append((t, ws[-1].end if ws else t + 1)); words_l += ws; t = windows[-1][1]
        words, voice_end = tuple(words_l), t
    # the first beat starts at 0 so the picture is never empty; the last runs on into the end card
    windows[0] = (0.0, windows[0][1])
    total = voice_end + TAIL
    windows[-1] = (windows[-1][0], total)

    # ---- demo footage for the demo beat ----
    demo_plan, demo_name = None, None
    plan_beats = []
    for b, (s, e) in zip(script.beats, windows):
        layout = b.layout
        if layout == "demo":
            picked = pick_demo(atom, e - s, last_demo)
            if picked:
                demo_name, mp4, secs = picked
                n = extract_demo_frames(mp4, work_dir / "demo")
                demo_plan = {"dir": str(work_dir / "demo"), "count": n, "fps": FPS, "seconds": secs}
            else:
                layout = "stage"
                notes.append("no matching demo footage for this atom: used the stage layout")
        plan_beats.append({"beat": b.beat, "start": round(s, 3), "end": round(e, 3), "layout": layout,
                           "acts": list(b.acts), "text": b.text})
    caps = cap.chunk(words)
    themes = json.loads((ROOT / "configs/themes.json").read_text())
    plan = {"fps": FPS, "total": round(total, 3), "title": script.title, "appName": cfg.name,
            "stageColor": themes["apps"].get(cfg.app_id, themes["default"]), "costume": slot.costume,
            "logoFile": "vendor/logo-mark.svg", "seed": date.fromisoformat(slot.day).toordinal(),
            "beats": plan_beats, "captions": cap.to_json(caps)}
    if demo_plan:
        plan["demo"] = demo_plan
    stem = f"{slot.day}-{cfg.app_id}-{fmt['id']}"
    plan_path = work_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=1))

    # ---- render ----
    mp4 = out_dir / f"{stem}.mp4"
    if not (ROOT / "render/node_modules").exists() and not shutil.which("playwright"):
        notes.append("render/node_modules missing: run `npm install` in render/ (or set PLAYWRIGHT_DIR)")
    cmd = ["node", str(ROOT / "render/render.mjs"), "--plan", str(plan_path), "--out", str(mp4)]
    if audio:
        cmd += ["--audio", str(audio), "--audio-delay", str(LEAD)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode or not mp4.exists():
        raise VideoError("render failed: " + (r.stderr or r.stdout)[-400:])
    srt = out_dir / f"{stem}.srt"
    srt.write_text(cap.to_srt(caps))
    meta = out_dir / f"{stem}.json"
    meta.write_text(json.dumps({"slot": slot.__dict__, "script": {"source": script.source, "title": script.title,
                                "caption": script.caption, "beats": [b.__dict__ | {"acts": list(b.acts)} for b in script.beats],
                                "cost_gbp": script.cost_gbp, "problems": script.problems},
                                "voiced": voiced, "duration": total, "demo": demo_name, "notes": notes}, indent=1, default=str))
    return VideoResult(mp4, srt, meta, script, voiced, total, demo_name, notes)
