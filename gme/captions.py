"""Word timings -> burned-in captions: 2 to 4 words at a time, timed to the voice. Pure code, no model."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .voice import Word

STRONG_END = re.compile(r"[.!?]$")
SOFT_END = re.compile(r"[,;:]$")


@dataclass(frozen=True)
class Caption:
    text: str
    start: float
    end: float
    emphasis: tuple[int, ...]     # indexes of words to colour (numbers, money, ALL CAPS)


def _emphatic(word: str) -> bool:
    core = re.sub(r"[^\w£$€%]", "", word)
    return bool(re.search(r"\d|[£$€%]", core)) or (len(core) >= 3 and core.isupper())


def chunk(words: tuple[Word, ...], max_words: int = 3, max_chars: int = 22, max_gap: float = 0.6,
          min_len: float = 0.35) -> list[Caption]:
    """Split into short caption chunks. Breaks at sentence ends, long pauses and size limits."""
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for i, w in enumerate(words):
        if cur and (len(cur) >= max_words or len(" ".join(x.text for x in cur + [w])) > max_chars
                    or w.start - cur[-1].end > max_gap):
            groups.append(cur)
            cur = []
        cur.append(w)
        if STRONG_END.search(w.text) or (SOFT_END.search(w.text) and len(cur) >= 2):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    caps: list[Caption] = []
    for gi, g in enumerate(groups):
        start, end = g[0].start, g[-1].end
        nxt = groups[gi + 1][0].start if gi + 1 < len(groups) else None
        if end - start < min_len:                      # keep it on screen long enough to read
            end = start + min_len
        if nxt is not None:                            # never overlap the next caption
            end = min(end, nxt)
        caps.append(Caption(" ".join(x.text for x in g), start, end,
                            tuple(i for i, x in enumerate(g) if _emphatic(x.text))))
    return caps


def to_json(caps: list[Caption]) -> list[dict]:
    """What the renderer reads: [{text, start, end, emphasis}]."""
    return [{"text": c.text, "start": round(c.start, 3), "end": round(c.end, 3), "emphasis": list(c.emphasis)} for c in caps]


def _srt_time(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(caps: list[Caption]) -> str:
    """SubRip file, for platforms that take uploaded captions (YouTube, Facebook)."""
    return "\n".join(f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n" for i, c in enumerate(caps, 1))
