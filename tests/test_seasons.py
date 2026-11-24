from datetime import date

from gme.seasons import Calendar, easter, nth_weekday

CAL = Calendar.load("configs/seasons.json")


def test_easter_and_thanksgiving_maths():
    assert easter(2027) == date(2027, 3, 28)
    assert easter(2026) == date(2026, 4, 5)
    assert nth_weekday(2026, 11, 3, 4) == date(2026, 11, 26)


def test_costume_follows_the_calendar():
    assert CAL.costume_for(date(2026, 12, 31)) == "newyear"
    assert CAL.costume_for(date(2027, 1, 5)) == "newyear"            # window wraps the new year
    assert CAL.costume_for(date(2027, 1, 20)) == "winter"
    assert CAL.costume_for(date(2027, 3, 27)) == "easter"
    assert CAL.costume_for(date(2027, 2, 9)) == "pancake"            # Shrove Tuesday 2027
    assert CAL.costume_for(date(2026, 11, 26)) == "thanksgiving"
    assert CAL.costume_for(date(2026, 11, 28)) == "blackfriday"
    assert CAL.costume_for(date(2026, 10, 31)) == "halloween"
    assert CAL.costume_for(date(2026, 12, 25)) == "christmas"
    assert CAL.costume_for(date(2027, 7, 14)) == "summer"


def test_every_day_of_two_years_has_a_costume_and_specific_beats_season():
    d = date(2026, 12, 1)
    for _ in range(730):
        assert CAL.costume_for(d)
        d = date.fromordinal(d.toordinal() + 1)
    assert [o.id for o in CAL.active(date(2027, 5, 20))][0] == "exam_season"


def test_upcoming_lets_videos_tease_events():
    ids = [o.id for o in CAL.upcoming(date(2026, 10, 15), 21)]
    assert "halloween" in ids and "christmas" not in ids
