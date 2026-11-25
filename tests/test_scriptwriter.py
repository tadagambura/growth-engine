import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from gme.atoms import load_atoms
from gme.budget import BudgetGuard, Policy
from gme.config import load
from gme.planner import Slot, load_json
from gme.scriptwriter import Writer, fixed_lines, max_words, trim_words, validate, claims_a_feature

ROOT = Path(__file__).resolve().parent.parent
CONTENT, MODELS = load_json(ROOT / "configs/content.json"), load_json(ROOT / "configs/models.json")
FORMATS = {f["id"]: f for f in load_json(ROOT / "configs/formats.json")["formats"]}
ATOMS = {a.id: a for items in load_atoms(ROOT / "configs/atoms").values() for a in items}
STACKUP = load(ROOT / "configs/apps/stackup.json")
TODAY = date(2026, 12, 1)
SLOT = Slot("2026-12-01", "feature", "stackup", "stackup:feature-01", "feature", "explainer", "winter", "waitlist")


def guard(**kw):
    return BudgetGuard(Policy(portfolio_monthly=20, portfolio_daily=5, default_app_monthly=10,
                              category_monthly={"ai": kw.get("ai", 10)}))


def reply(lines, usage=None, stop="end_turn"):
    return {"content": [{"type": "text", "text": json.dumps(lines)}], "stop_reason": stop,
            "usage": usage or {"input_tokens": 1500, "output_tokens": 300}}


GOOD = {"hook": "Payday is days away.", "problem": "And your balance is already looking nervous.",
        "turn": "Okay, let me check.", "demo": "StackUp shows what is safe to spend until payday.",
        "payoff": "Turns out, I can afford this.", "caption": "Know what is safe to spend before payday.",
        "title": "What is safe to spend?"}


def writer(responses, **kw):
    calls = []

    def transport(headers, body):
        calls.append(body)
        r = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r
    return Writer(MODELS, CONTENT, kw.get("guard", guard()), transport), calls


def test_good_model_output_becomes_a_script_with_cost_and_the_right_request():
    w, calls = writer([reply(GOOD)])
    atom = ATOMS[SLOT.atom_id]
    s = w.write(SLOT, FORMATS["explainer"], atom, STACKUP, TODAY, occasion="Christmas")
    assert s.source == "model" and s.problems == []
    assert [b.beat for b in s.beats] == ["hook", "problem", "turn", "demo", "payoff", "cta"]
    assert s.beats[-1].text.startswith("Join the waitlist") and s.beats[-1].text.endswith("Stay chained.")
    assert 0 < s.cost_gbp < 0.001
    body = calls[0]
    assert body["model"] == "claude-haiku-5-5" and body["thinking"] == {"type": "disabled"}
    assert "temperature" not in body and body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert "Christmas" in body["messages"][0]["content"]


def test_a_bad_answer_is_retried_with_the_reasons_then_accepted():
    bad = dict(GOOD, demo="Save £999 with this #hack https://x.example")
    w, calls = writer([reply(bad), reply(GOOD)])
    s = w.write(SLOT, FORMATS["explainer"], ATOMS[SLOT.atom_id], STACKUP, TODAY)
    assert s.source == "model" and len(calls) == 2 and s.problems
    assert "rejected" in calls[1]["messages"][0]["content"]


def test_three_bad_answers_fall_back_to_evergreen_with_no_more_spend():
    w, calls = writer([reply(dict(GOOD, hook="Guaranteed riches today"))])
    s = w.write(SLOT, FORMATS["explainer"], ATOMS[SLOT.atom_id], STACKUP, TODAY)
    assert s.source == "evergreen" and len(calls) == 3 and all(b.text for b in s.beats)


def test_refusal_error_or_empty_budget_never_crash_and_fall_back():
    for r in (reply(GOOD, stop="refusal"), RuntimeError("network down")):
        w, _ = writer([r])
        assert w.write(SLOT, FORMATS["explainer"], ATOMS[SLOT.atom_id], STACKUP, TODAY).source == "evergreen"
    g = guard(ai=0.0)
    w, calls = writer([reply(GOOD)], guard=g)
    s = w.write(SLOT, FORMATS["explainer"], ATOMS[SLOT.atom_id], STACKUP, TODAY)
    assert s.source == "evergreen" and calls == [] and "budget" in " ".join(s.problems)


def test_invented_numbers_and_explicit_words_are_rejected():
    atom = ATOMS[SLOT.atom_id]
    limits = {"hook": 6, "problem": 16, "turn": 9, "demo": 29, "payoff": 13}
    slots = list(limits)
    assert validate(GOOD, slots, limits, atom, STACKUP) == []
    assert any("not in the atom" in p for p in validate(dict(GOOD, hook="Save 4000 pounds now"), slots, limits, atom, STACKUP))
    ah = load(ROOT / "configs/apps/afterhours.json")
    assert any("explicit" in p for p in validate(dict(GOOD, hook="Get naked tonight"), slots, limits, atom, ah))


def test_quiz_format_is_deterministic_and_needs_no_model():
    atom = next(a for a in ATOMS.values() if a.id.startswith("stackup:l") and a.quiz)
    w, calls = writer([reply(GOOD)])
    slot = replace(SLOT, atom_id=atom.id, format_id="quiz_time", kind="lesson")
    s = w.write(slot, FORMATS["quiz_time"], atom, STACKUP, TODAY)
    assert calls == [] and s.source == "template" and s.cost_gbp == 0
    assert atom.quiz["q"] in s.spoken and "The answer:" in s.spoken
    assert max_words(6, 2.3) == 13 and len(trim_words("one two three four five six", 3).split()) <= 3


def test_every_format_can_build_an_evergreen_script_for_every_atom_kind():
    w = Writer(MODELS, CONTENT)            # no transport: always evergreen
    for atom in ATOMS.values():
        if atom.app_id != "stackup" and atom.app_id != "loopday":
            continue
        for fmt in FORMATS.values():
            if atom.kind not in fmt["kinds"] or (fmt.get("needs") == "quiz" and not atom.quiz):
                continue
            s = w.write(replace(SLOT, atom_id=atom.id, kind=atom.kind), fmt, atom, STACKUP, TODAY)
            assert all(b.text for b in s.beats), (fmt["id"], atom.id)


def test_lines_must_be_first_person():
    atom = ATOMS[SLOT.atom_id]
    limits = {"hook": 6, "problem": 16, "turn": 9, "demo": 29, "payoff": 13}
    assert any("third person" in p for p in validate(dict(GOOD, turn="Kaos opens StackUp."), list(limits), limits, atom, STACKUP))


def test_a_lesson_may_not_be_turned_into_an_app_feature():
    assert claims_a_feature("StackUp shows last month's card statement.", "StackUp")
    assert claims_a_feature("StackUp calculates it for me.", "StackUp")
    assert not claims_a_feature("StackUp shows me today's lesson.", "StackUp")
    assert not claims_a_feature("So I opened StackUp to learn it.", "StackUp")
