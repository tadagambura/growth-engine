#!/usr/bin/env python3
"""Export content atoms from the master App Portfolio repo into configs/atoms/<app>.json.

The engine runs on its own host and never sees the private master repo, so atoms are exported here
and committed. Re-run this whenever the master content changes:

    python3 scripts/export_atoms.py "/path/to/App Portfolio"

An atom is one real thing in an app that a video can show: a card, lesson, feature, game, activity or
signature moment. Nothing is invented here; every field is copied from the master files.
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "configs" / "atoms"


def src_of(item):
    s = item.get("source") or {}
    return {"name": s.get("name", ""), "url": s.get("url", "")} if isinstance(s, dict) else {"name": str(s), "url": ""}


def main(master: Path) -> None:
    content, arcade = master / "docs/pilots/content", master / "arcade/apps"
    portfolio = json.loads((master / "docs/portfolio.json").read_text())["apps"] if isinstance(
        json.loads((master / "docs/portfolio.json").read_text()), dict) else json.loads((master / "docs/portfolio.json").read_text())
    atoms: dict[str, list[dict]] = {}

    def add(app, atom):
        atoms.setdefault(app, []).append(atom)

    for a in portfolio:
        slug = a["slug"]
        for i, f in enumerate(a.get("features", []), 1):
            add(slug, {"id": f"{slug}:feature-{i:02d}", "kind": "feature", "title": f.split(":")[0][:80], "body": f,
                       "source": {"name": "App spec", "url": ""}, "reviewed": True})
        for i, m in enumerate((a.get("tone") or {}).get("moments", []), 1):
            add(slug, {"id": f"{slug}:moment-{i:02d}", "kind": "moment", "title": m.split(":")[0][:80], "body": m,
                       "source": {"name": "App spec", "url": ""}, "reviewed": True})
        if a.get("usecase"):
            add(slug, {"id": f"{slug}:usecase", "kind": "usecase", "title": "A day with " + a["name"], "body": a["usecase"],
                       "source": {"name": "App spec", "url": ""}, "reviewed": True})

    for f in sorted(content.glob("*.json")):
        d = json.loads(f.read_text())
        app = f.stem.split("-")[0]
        key = next((k for k, v in d.items() if isinstance(v, list)), None)
        if not key or key == "decks" or f.stem == "thirsty-plants":
            continue
        for it in d[key]:
            kind = {"lessons": "lesson", "cards": "card", "activities": "activity"}.get(key, "card")
            body = it.get("body") or it.get("summary") or ""
            atom = {"id": f"{app}:{it['id']}", "kind": kind, "title": it["title"], "body": body,
                    "topic": it.get("topic", ""), "source": src_of(it), "checked": d.get("checked", ""),
                    "reviewed": bool(d.get("reviewed", False)), "tags": it.get("tags", [])}
            if it.get("quiz"):
                q = it["quiz"]
                atom["quiz"] = {"q": q["q"], "options": q["options"], "answer": q["answer"], "explain": q.get("explain", "")}
            if kind == "activity":
                atom["steps"] = it.get("steps", [])
                atom["minutes"] = it.get("minutes")
            add(app, atom)

    for f in sorted(arcade.glob("*.json")):
        d = json.loads(f.read_text())
        for g in d.get("games", []):
            add(d["app"], {"id": f"{d['app']}:game-{g['id']}", "kind": "game", "title": g["name"],
                           "body": f"{g['how']} {g.get('teaches', '')}".strip(), "seconds": g.get("seconds"),
                           "source": {"name": "App spec", "url": ""}, "reviewed": bool(d.get("reviewed", False))})

    OUT.mkdir(parents=True, exist_ok=True)
    for app, items in sorted(atoms.items()):
        (OUT / f"{app}.json").write_text(json.dumps({"app_id": app, "atoms": items}, indent=1, ensure_ascii=False) + "\n")
        print(f"{app:12} {len(items):4} atoms  " + ", ".join(f"{k}:{sum(1 for x in items if x['kind'] == k)}" for k in sorted({x['kind'] for x in items})))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
