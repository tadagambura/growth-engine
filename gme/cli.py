"""Control link: `python -m gme <command>`. This is how the owner (or Claude, over SSH) talks to the engine.

  status   what the engine is doing: today's costume, apps, queue counts, paused or not
  pause    stop all publishing (a flag file; the scheduler checks it before every run)
  resume   start publishing again
  costume  Kaos's costume for a date (default today), plus what's coming up
  plan     Build the content calendar (default 180 days from the start date) and save it to data/calendar.json
  run-day  Make, check, queue and publish today's video (what the timer runs). --date YYYY-MM-DD for another day
  voice    Kaos's voice: `voice previews` (makes 3 samples, spends a little credit), `voice save <id>`
           (keeps the one you picked), `voice say "text"` (speaks a line and writes captions)

Data lives in $GME_HOME (default ./data): the queue database and the PAUSED flag.
The CLI cannot change spending limits or the constitution: those are files changed by reviewed commits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from .config import load_all
from .queue import Queue
from .seasons import Calendar

ROOT = Path(__file__).resolve().parent.parent


def home() -> Path:
    h = Path(os.environ.get("GME_HOME", ROOT / "data"))
    h.mkdir(parents=True, exist_ok=True)
    return h


def is_paused(h: Path) -> bool:
    return (h / "PAUSED").exists()


def status(h: Path, today: date) -> dict:
    cal = Calendar.load(ROOT / "configs/seasons.json")
    apps = load_all(ROOT / "configs/apps")
    db = h / "queue.db"
    counts: dict[str, int] = {}
    if db.exists():
        for status_, n in Queue(str(db)).db.execute("SELECT status, COUNT(*) FROM posts GROUP BY status"):
            counts[status_] = n
    return {"date": today.isoformat(), "paused": is_paused(h), "costume": cal.costume_for(today),
            "upcoming": [o.id for o in cal.upcoming(today)],
            "apps": {k: {"status": v.status, "publishing": v.publishing_mode} for k, v in apps.items()},
            "queue": counts}


def _voice(a, h: Path) -> int:
    from . import captions
    from .voice import (VoiceError, VoiceUsage, design_previews, load_voice_config, make_client, save_voice,
                        synthesize)
    cfg = load_voice_config(ROOT / "configs/voice.json")
    try:
        client = make_client(str(ROOT / ".env"))
        if a.vcmd == "previews":
            for gid, path, secs in design_previews(cfg, client, h / "voice-previews"):
                print(f"{gid}  {secs:.1f}s  {path}")
            print("Listen, pick one, then: python -m gme voice save <id>")
        elif a.vcmd == "save":
            print("voice_id:", save_voice(cfg, client, a.generated_voice_id))
            print("Put it in configs/voice.json and commit it (the engine never writes that file).")
        else:
            r = synthesize(a.text, a.out, cfg, client, VoiceUsage(h / "voice-usage.json"), date.today())
            Path(a.out).with_suffix(".captions.json").write_text(
                json.dumps(captions.to_json(captions.chunk(r.words)), indent=2))
            print(f"{a.out}  {r.duration:.1f}s  {r.characters} characters")
    except VoiceError as e:
        print(f"voice: {e}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gme", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status"); sub.add_parser("pause"); sub.add_parser("resume")
    c = sub.add_parser("costume"); c.add_argument("--date", help="YYYY-MM-DD")
    rd = sub.add_parser("run-day"); rd.add_argument("--date")
    sub.add_parser("publish-due")
    pl = sub.add_parser("plan"); pl.add_argument("--days", type=int); pl.add_argument("--from", dest="start")
    v = sub.add_parser("voice"); vs = v.add_subparsers(dest="vcmd", required=True)
    vs.add_parser("previews"); vsave = vs.add_parser("save"); vsave.add_argument("generated_voice_id")
    vsay = vs.add_parser("say"); vsay.add_argument("text"); vsay.add_argument("--out", default="kaos-line.mp3")
    a = ap.parse_args(argv)
    h = home()
    if a.cmd == "pause":
        (h / "PAUSED").write_text(date.today().isoformat())
        print("paused: nothing will publish until `gme resume`")
    elif a.cmd == "resume":
        (h / "PAUSED").unlink(missing_ok=True)
        print("resumed")
    elif a.cmd == "run-day":
        from .daily import build_env, run_day
        out = run_day(build_env(ROOT, h), date.fromisoformat(a.date) if a.date else date.today())
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["status"] in ("ok", "already done", "nothing planned") else 1
    elif a.cmd == "publish-due":
        from datetime import datetime, timezone
        from .daily import build_env
        from .publisher import publish_due
        env = build_env(ROOT, h)
        print(json.dumps(publish_due(env.queue, env.publisher, env.apps, datetime.now(timezone.utc), paused=is_paused(h))))
    elif a.cmd == "plan":
        from .planner import plan_from_files
        p = plan_from_files(ROOT, date.fromisoformat(a.start) if a.start else None, a.days)
        (h / "calendar.json").write_text(p.to_json())
        print(f"planned {len(p.slots)} videos: {p.slots[0].day} to {p.slots[-1].day} -> {h / 'calendar.json'}")
    elif a.cmd == "voice":
        return _voice(a, h)
    elif a.cmd == "costume":
        day = date.fromisoformat(a.date) if a.date else date.today()
        cal = Calendar.load(ROOT / "configs/seasons.json")
        print(json.dumps({"date": day.isoformat(), "costume": cal.costume_for(day),
                          "active": [o.id for o in cal.active(day)], "upcoming": [o.id for o in cal.upcoming(day)]}))
    else:
        print(json.dumps(status(h, date.today()), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
