"""Control link: `python -m gme <command>`. This is how the owner (or Claude, over SSH) talks to the engine.

  status   what the engine is doing: today's costume, apps, queue counts, paused or not
  pause    stop all publishing (a flag file; the scheduler checks it before every run)
  resume   start publishing again
  costume  Kaos's costume for a date (default today), plus what's coming up

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gme", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status"); sub.add_parser("pause"); sub.add_parser("resume")
    c = sub.add_parser("costume"); c.add_argument("--date", help="YYYY-MM-DD")
    a = ap.parse_args(argv)
    h = home()
    if a.cmd == "pause":
        (h / "PAUSED").write_text(date.today().isoformat())
        print("paused: nothing will publish until `gme resume`")
    elif a.cmd == "resume":
        (h / "PAUSED").unlink(missing_ok=True)
        print("resumed")
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
