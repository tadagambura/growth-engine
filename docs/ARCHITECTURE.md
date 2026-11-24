# Architecture

The Growth & Maintenance Engine (GME) markets and maintains a portfolio of small consumer
apps with as little human time and money as possible. Apps join as config files
(`configs/apps/<app_id>.json`). This is the public, generic design; machine-specific
deployment notes are kept privately.

## Principles

1. **Plain code first.** Scheduling, publishing, analytics, budgets, dedup and links never
   use AI (`gme.router.TIER0`).
2. **Home GPU first, small API for quality.** The local GPU writes first drafts and checks
   creatives inside its working hours (09:00–21:00; quiet hours mean no GPU work). A cheap API
   model checks public posts; stronger models only for strategy and the weekly report. Due jobs
   outside GPU hours use the API if the budget allows, otherwise they wait.
3. **Limits live in code, not prompts.** The budget guard (`gme.budget`) decides; models
   can't raise limits, switch on ads, or touch credentials.
4. **Home hardware is the factory, never the shop.** Apps run on managed cloud hosting;
   the engine and media studio run at home and catch up from their queue after any outage.
5. **Official APIs only.** No fake accounts, engagement bots or device farms.
6. **Every automatic fix is logged; repeated failures escalate** to the owner.

## Components

```
always-on host (low-power mini PC)          GPU worker (desktop, 09:00–21:00)  
┌────────────────────────────────────┐      ┌───────────────────────────────────┐
│ scheduler      research collector  │ jobs │ image generation (local model)    │
│ content queue  QA (rules + model)  │─────▶│ TTS voiceovers, captions (whisper)│
│ budget guard   analytics collector │◀─────│ video renders (Remotion, FFmpeg)  │
│ maintenance checks  weekly report  │assets│ visual QA (vision model)          │
│ PostgreSQL · Redis · Postiz        │      │ embeddings, local LLM fallback    │
│ Telegram alerts and approvals      │      └───────────────────────────────────┘
└──────────────┬─────────────────────┘
               │ Postiz (self-hosted) → YouTube · Instagram · Facebook · Threads ·
               │                        Pinterest · TikTok · Bluesky · X · blog
               ▼
        Claude API (batch, capped) · PostHog · RevenueCat · Sentry · store APIs
```

## The loop

Research → strategy (stored, rarely revisited) → batch content → creatives → QA →
queue (7 days ready, 14 days scheduled, 30 days evergreen fallback) → publish → measure →
bounded optimisation → weekly owner report.

## Maintenance (the "M")

Crash monitoring, store-review reply drafts, support triage, dependency updates via
CI-gated PRs, backend health, platform-token expiry, content-accuracy review dates
(e.g. tax rules every April), budget alerts at 50/80/100%, and self-checks of the engine.

## Status

| Piece | State |
|---|---|
| App config schema + validation | Built (`gme.config`), tested |
| Budget guard | Built (`gme.budget`), tested |
| Costume calendar (`gme.seasons`), category budgets and revenue tiers (`gme.budget`, `configs/policy.json`), control CLI (`gme.cli`) | Built, tested |
| Model router: GPU hours, quiet hours, API fallback | Built (`gme.router`), tested |
| Content queue with enforced approval flow (`gme.queue`), deterministic QA (`gme.qa`) | Built, tested (SQLite; scheduler loop still to do) |
| N95 deploy kit (Postiz pinned, engine DB, tunnel, backups) | Built (`deploy/n95`), config validated |
| Telegram alerts and approve/reject buttons (`gme.telegram`), publisher seam with dry run (`gme.publisher`) | Built, tested with fake transport |
| Postiz publisher | Next: needs a running Postiz on the N95 to check the pinned version's API |
| GPU worker and creative templates | Next |
| Analytics collectors, weekly report | Phase 2 |
| Research, optimisation, app scoring | Phases 3–5 |
| Paid ads | Phase 6, off by default |
