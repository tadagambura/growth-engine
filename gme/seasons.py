"""Kaos's costume calendar: which costume to wear on a given day, resolved by plain date maths.

No model is involved. The calendar lives in configs/seasons.json. Specific events (priority 100)
beat softer ones (exam season, back to school), which beat the four plain seasons.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


def easter(year: int) -> date:
    """Western Easter Sunday (Anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th given weekday (Monday = 0) of a month."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _md(year: int, text: str) -> date:
    month, day = (int(x) for x in text.split("-"))
    return date(year, month, day)


def window(rule: dict, year: int) -> tuple[date, date]:
    """The (start, end) of a rule for the year in which it starts."""
    kind = rule["type"]
    if kind == "fixed":
        start = _md(year, rule["start"])
        end = _md(year, rule["end"])
        if end < start:
            end = _md(year + 1, rule["end"])
        return start, end
    if kind == "dated":      # explicit checked dates per year; no entry means no occurrence that year
        pair = rule["dates"].get(str(year))
        if pair is None:
            return date.max, date.max
        return date.fromisoformat(pair[0]), date.fromisoformat(pair[1])
    if kind == "easter":
        base = easter(year)
    elif kind == "nth_weekday":
        base = nth_weekday(year, rule["month"], rule["weekday"], rule["n"])
    else:
        raise ValueError(f"unknown rule type '{kind}'")
    return base + timedelta(days=rule["start"]), base + timedelta(days=rule["end"])


@dataclass(frozen=True)
class Greeting:
    id: str
    name: str
    text: str
    day: date


@dataclass(frozen=True)
class Occasion:
    id: str
    name: str
    costume: str
    priority: int
    start: date
    end: date


class Calendar:
    def __init__(self, raw: dict):
        self._items = [(e, "event") for e in raw["events"]] + [(s, "season") for s in raw["seasons"]]
        self._greetings = raw.get("greetings", {}).get("items", [])
        ids = [e["id"] for e, _ in self._items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate ids in seasons file")

    @classmethod
    def load(cls, path: str | Path) -> "Calendar":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def _occasions(self, year: int) -> list[Occasion]:
        out = []
        for item, _kind in self._items:
            start, end = window(item["rule"], year)
            out.append(Occasion(item["id"], item.get("name", item["id"]), item["costume"],
                                item["priority"], start, end))
        return out

    def active(self, day: date) -> list[Occasion]:
        """Everything whose window covers the day, highest priority first."""
        found = [o for y in (day.year - 1, day.year) for o in self._occasions(y) if o.start <= day <= o.end]
        return sorted(found, key=lambda o: (-o.priority, o.start, o.id))

    def costume_for(self, day: date) -> str:
        return self.active(day)[0].costume

    def upcoming(self, day: date, within_days: int = 21) -> list[Occasion]:
        """Events (priority 50+) starting in the next few days, so videos can tease them."""
        found = [o for y in (day.year, day.year + 1) for o in self._occasions(y)
                 if o.priority >= 50 and day < o.start <= day + timedelta(days=within_days)]
        return sorted(found, key=lambda o: o.start)

    def greeting_for(self, day: date) -> Greeting | None:
        """The fixed-wording greeting for this day, if it is one we mark (replaces the day's normal video)."""
        for g in self._greetings:
            start, end = window(g["rule"], day.year)
            if start <= day <= end:
                return Greeting(g["id"], g["name"], g["text"], day)
        return None

    def years_missing_dates(self, year: int) -> list[str]:
        """Greetings with a 'dated' rule and no checked date for this year (the engine alerts the owner in September)."""
        return [g["id"] for g in self._greetings
                if g["rule"]["type"] == "dated" and str(year) not in g["rule"]["dates"]]
