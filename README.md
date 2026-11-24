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
| `gme/router.py` | Model routing: home GPU first (09:00–21:00, quiet at night), small API for quality |
| `configs/apps/` | One JSON config per app (StackUp first) |
| `tests/` | Tests for all of the above |

## Run the tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

---

Part of the App Portfolio. Licence: all rights reserved (see `LICENSE`).
