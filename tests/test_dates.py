from pathlib import Path

from gme import dates
from gme.atoms import load_atoms, usable

ROOT = Path(__file__).resolve().parents[1]


def test_finds_calendar_dates_and_years():
    for text in ("Since 15 July 2026, it changed", "in December", "From April 2026", "the 2026 to 2027 tax year",
                 "checked Mon 23 Nov", "on 2026-12-02", "back in 2019"):
        assert dates.find(text), text


def test_leaves_ordinary_numbers_and_words():
    for text in ("£2,000 saved", "£2026 target", "Walk 2000 steps", "You may march on", "52 weeks, £1,378",
                 "Bills on the 28th", "The 50/30/20 idea", "Skip Monday if you like"):
        assert dates.find(text) == [], text


def test_study_year_is_dropped_but_tax_year_is_kept():
    assert dates.undate("In a 1997 study, people talked.") == "In a study, people talked."
    assert dates.undate("A 2009 UCL study found it.") == "A UCL study found it."
    assert dates.find(dates.undate("In the 2026 to 2027 tax year"))


def test_no_usable_atom_carries_a_date():
    for atoms in load_atoms(ROOT / "configs/atoms").values():
        for a in atoms:
            if usable(a, True, []):
                assert dates.find(f"{a.title} {a.body} {a.quiz or ''}") == [], a.id
