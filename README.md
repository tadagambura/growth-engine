# Growth & Maintenance Engine

One low-cost, largely autonomous system that **markets and maintains** every app in the
portfolio. Each app joins as a config file; the engine researches, writes, renders, checks,
publishes, measures and looks after the apps, and only asks its owner when it matters.

## Status

Foundation in progress (Phase 0). Design: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
The original brief is summarised in [`docs/SPEC.md`](docs/SPEC.md).

## What's here

| Path | What |
|---|---|
| `gme/config.py` | App config schema and strict validation |
| `gme/budget.py` | Budget guard: deterministic caps no AI can change |
| `gme/qa.py` | Deterministic post checks: banned phrases, hashtags, length, foreign links |
| `gme/queue.py` | SQLite content queue with an enforced approval flow |
| `gme/telegram.py` | Telegram alerts, Approve/Reject buttons, owner-only decisions |
| `gme/publisher.py` | Publisher seam, dry-run publisher and `publish_due` |
| `gme/seasons.py` | Kaos's costume calendar (`configs/seasons.json`), pure date maths |
| `gme/cli.py` | Control link: `python -m gme status / pause / resume / costume` |
| `configs/policy.json` | Owner's spend caps: £10 AI, £10 video, growth tiers |
| `gme/voice.py` | Kaos's voice via ElevenLabs: speech with exact word timings, monthly character guard, voice previews (`configs/voice.json`) |
| `gme/captions.py` | Word timings to 2-4 word captions (JSON for the renderer, SRT for platforms) |
| `gme/atoms.py`, `scripts/export_atoms.py` | Content atoms (cards, lessons, features, games...) exported from the master repo |
| `gme/planner.py` | Deterministic 6-month content calendar: rhythm, spotlight app, least-recently-used atom and format, costume, CTA |
| `configs/formats.json`, `configs/acts.json`, `configs/content.json` | Standard video formats (beat sheets), Kaos act vocabulary, owner's content policy |
| `gme/scriptwriter.py`, `configs/models.json` | Fills fixed beat-sheet slots with a cheap model (thinking off, strict JSON, validated, evergreen fallback) |
| `gme/router.py` | Model routing: home GPU first (09:00–21:00, quiet at night), small API for quality |
| `configs/apps/` | One JSON config per app (StackUp first) |
| `tests/` | Tests for all of the above |

## Run the tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,voice]"
pytest
```

---

Part of the App Portfolio. Licence: all rights reserved (see `LICENSE`).
