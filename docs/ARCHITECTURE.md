# Architecture

The Growth & Maintenance Engine (GME) markets and maintains a portfolio of small consumer
apps with as little human time and money as possible. Apps join as config files
(`configs/apps/<app_id>.json`). This is the public, generic design; machine-specific
deployment notes are kept privately.

## Principles

1. **Plain code first.** Scheduling, publishing, analytics, budgets, dedup and links never
   use AI (`gme.router.TIER0`).
2. **Cheapest model that does the job.** Bulk text uses a cheap API model in batch; stronger
   models only for strategy and weekly analysis; a local GPU model is the fallback.
3. **Limits live in code, not prompts.** The budget guard (`gme.budget`) decides; models
   can't raise limits, switch on ads, or touch credentials.
4. **Home hardware is the factory, never the shop.** Apps run on managed cloud hosting;
   the engine and media studio run at home and catch up from their queue after any outage.
5. **Official APIs only.** No fake accounts, engagement bots or device farms.
6. **Every automatic fix is logged; repeated failures escalate** to the owner.

## Components

```
always-on host (low-power mini PC)          GPU worker (desktop, night shift)
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
| Model router with local fallback | Built (`gme.router`), tested |
| Database schema, queue, scheduler | Next |
| Postiz integration, Telegram alerts | Next |
| GPU worker and creative templates | Next |
| Analytics collectors, weekly report | Phase 2 |
| Research, optimisation, app scoring | Phases 3–5 |
| Paid ads | Phase 6, off by default |
