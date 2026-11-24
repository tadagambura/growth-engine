"""Videos get reused, so they carry no dates. Finds calendar dates and years in text.

A study's year ("a 2024 review") can be dropped without changing the fact. Anything else with a date
("since 15 July 2026", "the 2026 to 2027 tax year") goes stale, so that content is not used in videos.
"""
from __future__ import annotations

import re

_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
          r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\b")
_DATE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}"
    rf"|\b{_MONTH}\s+(?:\d{{1,2}}(?:st|nd|rd|th)?|(?:19|20)\d\d)\b"
    rf"|\b(?:[Ii]n|[Ss]ince|[Ff]rom|[Uu]ntil|[Bb]y|[Tt]his|[Nn]ext|[Ll]ast)\s+{_MONTH}"
    r"|\b(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])/(?:\d{4}|\d\d)\b|\b(?:19|20)\d\d-\d\d-\d\d\b"
    r"|(?<![£$€\d,.])\b(?:19|20)\d\d\b(?![,.]\d)(?!\s*(?:steps|words|ml|calories|kcal|pages)\b)")
_STUDY_YEAR = re.compile(
    r"\b([Aa]n?|[Tt]he)\s+(?:19|20)\d\d\s+(?=(?:[A-Z][\w-]*\s+){0,3}(?:study|review|paper|trial|survey|experiment|analysis|meta-analysis|report)\b)")


def undate(text: str) -> str:
    """Drop a study's year: "In a 1997 study" becomes "In a study"."""
    return _STUDY_YEAR.sub(r"\1 ", text)


def find(text: str) -> list[str]:
    return [m.group(0) for m in _DATE.finditer(text)]
