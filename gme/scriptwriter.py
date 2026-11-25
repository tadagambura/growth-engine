"""Script writer: turns (slot, format, atom) into the spoken lines of one video.

The structure is fixed by the format's beat sheet. A model only fills short named slots (hook, problem,
turn, demo, payoff, plus a caption and a title), with thinking off, strict JSON, and a hard word limit
per slot. Every line is then checked by plain code. If the model fails, is refused, is over budget, or
breaks a rule three times, the script is built from the atom's own words with no model at all, so a
video always exists. Formats marked deterministic (quiz time) never call a model.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from . import dates, qa
from .atoms import Atom
from .budget import BudgetGuard
from .config import AppConfig

Transport = Callable[[dict, dict], dict]       # (headers, body) -> parsed JSON response
URL = re.compile(r"https?://|www\.", re.I)
HASHTAG = re.compile(r"#\w+")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
NUM = re.compile(r"\d[\d,.]*")


@dataclass(frozen=True)
class BeatText:
    beat: str
    text: str
    acts: tuple[str, ...]
    layout: str
    seconds: float


@dataclass
class Script:
    format_id: str
    atom_id: str
    beats: list[BeatText]
    caption: str
    title: str
    source: str                                # "model" | "template" | "evergreen"
    cost_gbp: float = 0.0
    problems: list[str] = field(default_factory=list)   # why earlier attempts were rejected

    @property
    def spoken(self) -> str:
        return " ".join(b.text for b in self.beats if b.text)


def max_words(seconds: float, wps: float) -> int:
    return max(3, int(seconds * wps))


def trim_words(text: str, limit: int) -> str:
    """Trim to a word limit, preferring a sentence boundary."""
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    cut = " ".join(words[:limit])
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if end > len(cut) * 0.5:
        return cut[:end + 1]
    return cut.rstrip(",;:") + "."


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def cta_text(content: dict, cta_id: str, app_name: str) -> str:
    cta = next(c for c in content["ctas"] if c["id"] == cta_id)
    return cta["text"].replace("{app}", app_name) + " " + content.get("sign_off", "")


def _letters(options: list[str]) -> str:
    names = ["A", "B", "C", "D", "E"]
    parts = [f"{names[i]}, {o.rstrip('.')}" for i, o in enumerate(options)]
    return "; ".join(parts[:-1]) + "; or " + parts[-1] if len(parts) > 1 else parts[0]


def fixed_lines(fmt: dict, atom: Atom, wps: float) -> dict[str, str]:
    """Lines for deterministic formats, copied from the atom (the quiz format)."""
    q = atom.quiz or {}
    fill = {"greeting": atom.body, "question": q.get("q", ""), "options": _letters(q.get("options", [])),
            "answer": q.get("options", [""])[q.get("answer", 0)].rstrip("."), "explain": q.get("explain", "")}
    out = {}
    for b in fmt["beats"]:
        if "fixed" in b:
            limit = max_words(b["seconds"], wps)
            text = b["fixed"]
            for k, v in fill.items():
                text = text.replace("{" + k + "}", v)
            out[b["beat"]] = text if b.get("notrim") else trim_words(text, limit + (25 if b["beat"] == "payoff" else 8))
    return out


def evergreen_lines(fmt: dict, atom: Atom, app_name: str, wps: float) -> dict[str, str]:
    """No-model fallback built only from the atom's own words."""
    sents = sentences(atom.body) or [atom.title]
    hooks = {"card": f"{atom.title}. Quick one.", "lesson": f"{atom.title}. Quick one.",
             "feature": f"Here's an {app_name} thing you might miss.", "game": f"Game time: {atom.title}.",
             "activity": f"Try this today: {atom.title}.", "usecase": f"A day with {app_name}.",
             "moment": f"Okay so, this is {app_name} in real life."}
    lines = {"hook": hooks.get(atom.kind, f"{atom.title}."), "problem": sents[0], "turn": "Okay, let me show you.",
             "demo": sents[1] if len(sents) > 1 else f"{atom.title}, right here in {app_name}.",
             "payoff": sents[-1] if len(sents) > 2 else "Small steps. Real progress."}
    out = {}
    for b in fmt["beats"]:
        if b["slot"]:
            out[b["slot"]] = trim_words(lines.get(b["slot"], atom.title), max_words(b["seconds"], wps) + 6)
    return out


# ---------- the model call ----------
# In a lesson or card, the facts are advice, not things the app does: "StackUp shows your statement" is invented.
ADVICE_KINDS = {"lesson", "card"}


def claims_a_feature(text: str, app_name: str) -> bool:
    verbs = r"(?:shows|tracks|imports|connects|syncs|reads|scans|calculates|adds|lists|finds|pulls|sorts|checks|tells|does)"
    return bool(re.search(rf"\b{re.escape(app_name)}\s+{verbs}\b(?!\s+(?:me\s+)?(?:(?:a|the|this|today's)\s+)?(?:\w+\s+)?(?:lesson|tip|quiz)\b)",
                          text, re.I))


def schema_for(slots: list[str]) -> dict:
    props = {s: {"type": "string"} for s in slots + ["caption", "title"]}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def system_prompt(app_name: str, cfg: AppConfig) -> str:
    adult = ("This app is adults only (18+): flirty and cheeky is fine, but hints only. Never explicit, never about "
             "bodies or sex. " if cfg.min_age >= 18 else "")
    return (
        f"You write short spoken lines for Kaos, a quick, over-caffeinated, self-deprecating stickman who uses the "
        f"{app_name} app. Kaos is the one speaking, so write in first person (I, me, my) and never say the word Kaos. "
        f"Plain American English, no British-only slang. Warm and funny, never mean, never preachy. "
        f"{adult}"
        "Each line is spoken aloud: short sentences, and never more than its max_words. "
        "Use ONLY the facts in ATOM. Never invent numbers, prices, features, results or testimonials. "
        "Never mention a date, month or year: videos get reused. "
        "The app does only what ATOM says the app does. When ATOM is a lesson or card, its advice is something I do "
        "myself: never say the app shows, tracks, reads or calculates it. "
        "No hashtags, emojis, links or all-caps shouting. No advice about the viewer's own money, health or relationships. "
        f"Voice and tone: {cfg.brand_voice} "
        "Return only the JSON object."
    )


ROLE_HINTS = {
    "hook": "a stop-the-scroll opening: relatable, funny or surprising",
    "problem": "the relatable problem or setup this atom speaks to",
    "turn": "Kaos reaches for the app, one short line",
    "demo": "what the app shows or does, using the atom, as if narrating the screen",
    "payoff": "the win, the lesson or the punchline",
}


def user_prompt(fmt: dict, atom: Atom, app_name: str, tagline: str, wps: float, occasion: str | None,
                trend: str | None) -> str:
    beats = [{"slot": b["slot"], "role": ROLE_HINTS.get(b["slot"], b["slot"]), "max_words": max_words(b["seconds"], wps)}
             for b in fmt["beats"] if b["slot"]]
    payload = {
        "app": {"name": app_name, "tagline": tagline},
        "format": fmt["name"],
        "ATOM": {"kind": atom.kind, "title": atom.title, "body": atom.body,
                 **({"quiz": atom.quiz} if atom.quiz else {})},
        "lines_to_write": beats,
        "caption": "one friendly line, max 22 words, no hashtags",
        "title": "the hook as a title, max 9 words",
    }
    if occasion:
        payload["today_is"] = occasion + " (a light nod is fine, do not force it)"
    if trend:
        payload["trend_pattern"] = trend
    return json.dumps(payload, ensure_ascii=False)


def http_transport(api_key: str, version: str) -> Transport:
    def call(headers: dict, body: dict) -> dict:
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json", "x-api-key": api_key,
                                              "anthropic-version": version, **headers})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (fixed https host)
            return json.loads(r.read())
    return call


def validate(lines: dict, slots: list[str], limits: dict[str, int], atom: Atom, cfg: AppConfig) -> list[str]:
    problems: list[str] = []
    allowed_numbers = set(NUM.findall(" ".join([atom.title, atom.body, json.dumps(atom.quiz or {}),
                                                 " ".join(cfg.approved_claims)])))
    for key in slots + ["caption", "title"]:
        text = str(lines.get(key, "")).strip()
        if not text:
            problems.append(f"{key} is empty")
            continue
        limit = limits.get(key, 30 if key == "caption" else 12)
        if len(text.split()) > int(limit * 1.2) + 1:
            problems.append(f"{key} is {len(text.split())} words (max {limit})")
        if URL.search(text) or HASHTAG.search(text) or EMOJI.search(text):
            problems.append(f"{key} has a link, hashtag or emoji")
        if atom.kind in ADVICE_KINDS and claims_a_feature(text, cfg.name):
            problems.append(f"{key} says the app does something this {atom.kind} does not claim")
        if dates.find(text):
            problems.append(f"{key} mentions a date or year")
        for n in NUM.findall(text):
            if n not in allowed_numbers and n.strip(".,") not in {x.strip(".,") for x in allowed_numbers}:
                problems.append(f"{key} uses the number {n}, which is not in the atom")
        if key in slots and re.search(r"\bkaos\b", text, re.I):
            problems.append(f"{key} refers to Kaos in the third person (write as Kaos, in first person)")
        problems += [f"{key}: {p}" for p in qa.check(text, "tiktok", cfg) if "limit" not in p]
    return problems


@dataclass
class Writer:
    cfg_models: dict                  # configs/models.json
    content: dict                     # configs/content.json
    guard: BudgetGuard | None = None
    transport: Transport | None = None

    def _cost_gbp(self, usage: dict) -> float:
        m = self.cfg_models["scripting"]
        usd = (usage.get("input_tokens", 0) * m["input_per_mtok_usd"] + usage.get("output_tokens", 0) * m["output_per_mtok_usd"]) / 1e6
        return usd * self.cfg_models["gbp_per_usd"]

    def _ask(self, system: str, user: str, slots: list[str], extra_note: str = "") -> tuple[dict, float]:
        m = self.cfg_models["scripting"]
        body = {"model": m["model"], "max_tokens": m["max_tokens"], "system": system,
                "messages": [{"role": "user", "content": user + extra_note}],
                "thinking": {"type": m["thinking"]},
                "output_config": {"effort": m["effort"], "format": {"type": "json_schema", "schema": schema_for(slots)}}}
        res = self.transport({}, body)
        if res.get("stop_reason") in ("refusal", "max_tokens"):
            raise ValueError(f"model stopped: {res.get('stop_reason')}")
        text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
        return json.loads(text), self._cost_gbp(res.get("usage", {}))

    def write(self, slot, fmt: dict, atom: Atom, cfg: AppConfig, today: date, occasion: str | None = None,
              trend: str | None = None) -> Script:
        wps = self.content["words_per_second"]
        slots = [b["slot"] for b in fmt["beats"] if b["slot"]]
        limits = {b["slot"]: max_words(b["seconds"], wps) for b in fmt["beats"] if b["slot"]}
        cta = cta_text(self.content, slot.cta_id, cfg.name)
        caption = f"{atom.title}. {cfg.tagline}"
        title = atom.title[:70]
        problems: list[str] = []
        cost = 0.0
        lines: dict[str, str] | None = None
        source = "evergreen"

        if fmt.get("deterministic"):
            lines, source = fixed_lines(fmt, atom, wps), "template"
        elif self.transport and self.guard:
            m = self.cfg_models["scripting"]
            note = ""
            for _ in range(m["max_attempts"]):
                est = 0.002
                if not self.guard.check(cfg.app_id, "ai", est, today).allowed:
                    problems.append("AI budget reached")
                    break
                try:
                    got, spent = self._ask(system_prompt(cfg.name, cfg),
                                           user_prompt(fmt, atom, cfg.name, cfg.tagline, wps, occasion, trend), slots, note)
                except Exception as e:           # network, refusal, bad JSON: fall back, never crash
                    problems.append(f"{type(e).__name__}: {e}"[:200])
                    break
                cost += spent
                self.guard.record(cfg.app_id, "ai", spent, today)
                bad = validate(got, slots, limits, atom, cfg)
                if not bad:
                    lines, source = got, "model"
                    caption, title = got["caption"].strip(), got["title"].strip()
                    break
                problems += bad
                note = "\n\nYour last answer was rejected: " + "; ".join(bad[:4]) + ". Fix these and answer again."
        if lines is None:
            lines = evergreen_lines(fmt, atom, cfg.name, wps)
            source = "evergreen"
        beats = []
        for b in fmt["beats"]:
            text = cta if b["beat"] == "cta" else lines.get(b["slot"] or b["beat"], "")
            beats.append(BeatText(b["beat"], text, tuple(b["acts"]), b["layout"], float(b["seconds"])))
        return Script(fmt["id"], atom.id, beats, caption, title, source, cost, problems)
