from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from gme.atoms import Atom, load_atoms, usable
from gme.planner import make_plan, plan_from_files

ROOT = Path(__file__).resolve().parent.parent


def test_plan_is_deterministic_and_covers_every_day():
    a = plan_from_files(ROOT, date(2026, 12, 1), 180)
    b = plan_from_files(ROOT, date(2026, 12, 1), 180)
    assert a.to_json() == b.to_json()
    assert len(a.slots) == 180


def test_weekly_rhythm_and_spotlight():
    p = plan_from_files(ROOT, date(2026, 12, 1), 14)          # 1 Dec 2026 is a Tuesday
    by_day = {s.day: s for s in p.slots}
    assert by_day["2026-12-01"].day_type == "feature" and by_day["2026-12-02"].day_type == "card"
    assert by_day["2026-12-05"].day_type == "kaos_life" and by_day["2026-12-06"].day_type == "recap"
    assert by_day["2026-12-01"].app_id == "stackup"
    assert by_day["2026-12-08"].app_id == "loopday"               # spotlight rotates weekly
    assert by_day["2026-12-05"].app_id != by_day["2026-12-04"].app_id   # Saturday is a cameo of another app


def test_costume_follows_the_calendar_and_cta_is_waitlist_before_launch():
    p = plan_from_files(ROOT, date(2026, 12, 20), 14)
    assert {s.day: s.costume for s in p.slots}["2026-12-25"] == "christmas"
    assert {s.day: s.costume for s in p.slots}["2026-12-31"] == "newyear"
    assert all(s.cta_id != "store" for s in p.slots)


def test_atoms_respect_their_repeat_window_and_formats_vary():
    from gme.planner import load_json
    by_kind = load_json(ROOT / "configs/content.json")["repeat_days"]["atom_by_kind"]
    p = plan_from_files(ROOT, date(2026, 12, 1), 180)
    last: dict[str, tuple[date, str]] = {}
    for s in p.slots:
        if not s.atom_id:
            continue
        d = date.fromisoformat(s.day)
        if s.atom_id in last:
            gap = (d - last[s.atom_id][0]).days
            assert gap >= 7, (s.atom_id, s.day)
            if gap < 30:                       # a quick repeat must be told in a different format
                assert last[s.atom_id][1] != s.format_id, (s.atom_id, s.day)
        last[s.atom_id] = (d, s.format_id)
    fmts = Counter(s.format_id for s in p.slots)
    assert len(fmts) >= 5 and max(fmts.values()) < 90


def test_unreviewed_sensitive_money_atoms_are_skipped_until_reviewed():
    risky = Atom("x:1", "x", "lesson", "Your ISA allowance", "Put money in an ISA", reviewed=False)
    fine = Atom("x:2", "x", "lesson", "Sleep tips", "Go to bed earlier", reviewed=False)
    terms = ["isa", "tax"]
    assert not usable(risky, True, terms) and usable(fine, True, terms) and not usable(fine, False, terms)
    assert usable(Atom("x:3", "x", "lesson", "ISA", "ISA", reviewed=True), True, terms)


def test_greeting_days_replace_the_normal_video():
    p = plan_from_files(ROOT, date(2027, 6, 1), 1)
    assert p.slots[0].format_id == "greeting" and p.slots[0].greeting_id == "pride"


def test_a_new_app_joins_on_its_date_and_history_is_respected():
    p = plan_from_files(ROOT, date(2027, 1, 11), 14)
    assert "afterhours" not in {s.app_id for s in p.slots if s.day < "2027-01-18"}
    first = plan_from_files(ROOT, date(2026, 12, 1), 5)
    nxt = plan_from_files(ROOT, date(2026, 12, 6), 5, history=first.slots)
    assert not ({s.atom_id for s in first.slots} & {s.atom_id for s in nxt.slots})


def test_every_planned_atom_exists_and_quiz_format_only_with_a_quiz():
    atoms = {a.id: a for items in load_atoms(ROOT / "configs/atoms").values() for a in items}
    for s in plan_from_files(ROOT, date(2026, 12, 1), 180).slots:
        if s.atom_id:
            assert s.atom_id in atoms
            if s.format_id == "quiz_time":
                assert atoms[s.atom_id].quiz
