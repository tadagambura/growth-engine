"""The planner: a deterministic content calendar. No model, no randomness: same inputs, same plan.

For each day it applies, in order: a greeting if the day is one we mark; the weekly rhythm (what type
of video today); the spotlight app for the week; the least recently used usable atom of the right
kind; the least recently used format that fits the atom; the costume for the date; and a CTA.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from .atoms import Atom, load_atoms, usable
from .seasons import Calendar

FAR_PAST = date(2000, 1, 1)


@dataclass(frozen=True)
class Slot:
    day: str                      # ISO date
    day_type: str                 # explainer | feature | card | games | kaos_life | recap | greeting
    app_id: str | None
    atom_id: str | None
    kind: str | None
    format_id: str                # a format id, or "greeting"
    costume: str
    cta_id: str
    greeting_id: str | None = None


@dataclass
class Plan:
    slots: list[Slot]

    def to_json(self) -> str:
        return json.dumps([asdict(s) for s in self.slots], indent=1, ensure_ascii=False)


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _eligible_formats(formats: list[dict], day_type: str, atom: Atom) -> list[dict]:
    fit = [f for f in formats if day_type in f["day_types"] and atom.kind in f["kinds"]
           and (f.get("needs") != "quiz" or atom.quiz)]
    if fit:
        return fit
    return [f for f in formats if atom.kind in f["kinds"] and (f.get("needs") != "quiz" or atom.quiz)]


def make_plan(start: date, days: int, content: dict, formats: dict, atoms: dict[str, list[Atom]], cal: Calendar,
              history: list[Slot] | None = None) -> Plan:
    fmts = formats["formats"]
    rules = content["repeat_days"]
    last_atom: dict[str, date] = {}
    last_format: dict[str, date] = {}
    atom_formats: dict[str, set[str]] = {}
    for s in history or []:                      # what already went out keeps its place in the history
        d = date.fromisoformat(s.day)
        if s.atom_id:
            last_atom[s.atom_id] = max(d, last_atom.get(s.atom_id, FAR_PAST))
            atom_formats.setdefault(s.atom_id, set()).add(s.format_id)
        last_format[s.format_id] = max(d, last_format.get(s.format_id, FAR_PAST))
    store_live = content.get("store_live", {})
    ctas = content["ctas"]
    slots: list[Slot] = []

    for i in range(days):
        day = start + timedelta(days=i)
        costume = cal.costume_for(day)
        cta = ctas[(day.toordinal()) % len(ctas)]
        g = cal.greeting_for(day)
        if g:
            slots.append(Slot(day.isoformat(), "greeting", None, None, None, "greeting", costume, "follow", g.id))
            continue
        day_type = content["weekday_types"][str(day.weekday())]
        live = [p["app_id"] for p in content["promoted"] if date.fromisoformat(p["from"]) <= day]
        if not live:
            continue
        week = (day - start).days // 7 // max(1, content.get("spotlight_weeks", 1))
        spotlight = live[week % len(live)]
        app_id = live[(week + 1) % len(live)] if day_type == "kaos_life" and len(live) > 1 else spotlight

        kinds = content["day_type_kinds"][day_type]
        pool = [a for a in atoms.get(app_id, []) if a.kind in kinds
                and usable(a, content["allow_unreviewed"], content["sensitive_terms_when_unreviewed"])
                and _eligible_formats(fmts, day_type, a)]
        if not pool:                              # nothing of that kind: any usable atom of the app
            pool = [a for a in atoms.get(app_id, [])
                    if usable(a, content["allow_unreviewed"], content["sensitive_terms_when_unreviewed"])
                    and _eligible_formats(fmts, day_type, a)]
        if not pool:
            continue
        pool.sort(key=lambda a: (last_atom.get(a.id, FAR_PAST), a.id))
        by_kind = rules.get("atom_by_kind", {})
        fresh = [a for a in pool if (day - last_atom.get(a.id, FAR_PAST)).days >= by_kind.get(a.kind, rules["atom"])]
        atom = (fresh or pool)[0]

        options = _eligible_formats(fmts, day_type, atom)
        used = atom_formats.get(atom.id, set())
        options.sort(key=lambda f: (f["id"] in used, last_format.get(f["id"], FAR_PAST), f["id"]))
        fmt = options[0]

        # the store CTA only once the app is live on a store
        if cta["when"] == "after_store" and not store_live.get(app_id):
            cta = ctas[0] if ctas[0]["when"] == "before_store" else cta
        if cta["when"] == "before_store" and store_live.get(app_id):
            cta = next(c for c in ctas if c["when"] == "after_store")

        slots.append(Slot(day.isoformat(), day_type, app_id, atom.id, atom.kind, fmt["id"], costume, cta["id"]))
        last_atom[atom.id] = day
        last_format[fmt["id"]] = day
        atom_formats.setdefault(atom.id, set()).add(fmt["id"])
    return Plan(slots)


def plan_from_files(root: str | Path, start: date | None = None, days: int | None = None,
                    history: list[Slot] | None = None) -> Plan:
    root = Path(root)
    content = load_json(root / "configs/content.json")
    return make_plan(start or date.fromisoformat(content["start_date"]), days or content["horizon_days"], content,
                     load_json(root / "configs/formats.json"), load_atoms(root / "configs/atoms"),
                     Calendar.load(root / "configs/seasons.json"), history)
