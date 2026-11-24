"""Content atoms: the real things in each app that a video can show (a card, lesson, feature, game, ...).

Atoms are exported from the master repo into configs/atoms/<app>.json by scripts/export_atoms.py.
Nothing is invented here, and a video may only claim what its atom says.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Atom:
    id: str
    app_id: str
    kind: str                    # feature | usecase | moment | card | lesson | activity | game
    title: str
    body: str
    source_name: str = ""
    source_url: str = ""
    checked: str = ""
    reviewed: bool = False
    quiz: dict | None = None
    tags: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict, compare=False, hash=False)


def _atom(app: str, raw: dict) -> Atom:
    s = raw.get("source") or {}
    return Atom(id=raw["id"], app_id=app, kind=raw["kind"], title=raw["title"], body=raw["body"],
                source_name=s.get("name", ""), source_url=s.get("url", ""), checked=raw.get("checked", ""),
                reviewed=bool(raw.get("reviewed", False)), quiz=raw.get("quiz"), tags=tuple(raw.get("tags", ())),
                extra={k: raw[k] for k in ("steps", "minutes", "seconds", "topic") if k in raw})


def load_atoms(directory: str | Path) -> dict[str, list[Atom]]:
    out: dict[str, list[Atom]] = {}
    for f in sorted(Path(directory).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["app_id"]] = [_atom(d["app_id"], a) for a in d["atoms"]]
    return out


def usable(atom: Atom, allow_unreviewed: bool, sensitive_terms: list[str]) -> bool:
    """Reviewed atoms always pass. Unreviewed ones pass only if allowed and free of sensitive money or legal terms."""
    if atom.reviewed:
        return True
    if not allow_unreviewed:
        return False
    text = f"{atom.title} {atom.body}".lower()
    words = set(text.replace(",", " ").replace(".", " ").replace("£", " ").split())
    for term in sensitive_terms:
        t = term.lower()
        if (" " in t and t in text) or t in words:
            return False
    return True
