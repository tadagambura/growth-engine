# Growth Engine: Spec

One shared, low-cost, largely autonomous marketing system for every app in the
portfolio. Apps are added as **config files**, not as new systems.

The full brief is the owner's master prompt (kept in the private portfolio repo as
`docs/prompts/01-growth-engine-master-prompt.md`). This spec is the working summary.

## The loop

Research → Strategy → Content → QA → Scheduling → Publishing → Measurement → Learning → Optimisation

Runs on a schedule, in batches. The owner approves strategy, budgets and major
changes, and reads one weekly report. Everything routine is automated.

## Hard rules (from the brief)

- **Cost first.** Targets: AI ≤ £10/month at the start, total running cost £10–£25/month.
  No paid service gets added quietly.
- **No AI where plain code works.** Scheduling, publishing, analytics, budgets, UTM
  links and dedup are deterministic code (Tier 0). AI only writes and judges content,
  in batches, using the cheapest model that does the job.
- **Budgets are enforced by code, not AI.** AI can't raise limits, switch on ads,
  touch payment details or turn off monitoring.
- **Paid ads off by default.** They need explicit owner activation.
- **No spam.** No fake testimonials, fake stats, fake engagement, or automated Reddit
  promotion. Content should read like a small, honest brand.
- **No single point of failure.** The GPU desktop is an optional worker; the system
  keeps running (cheap API fallback, evergreen content) when it's off.
- **Proportionate.** No Kubernetes, no swarm of always-on agents, one automation platform.

## Hardware

| Machine | Role |
|---|---|
| Mini PC (Intel N95, 16 GB) | Always-on host: scheduler, database, publishing, monitoring, dashboard |
| Desktop (i7-13th gen, RTX 3060 12 GB) | Optional worker: local LLM, image/video rendering, batch jobs when free |

## Functions (scheduled workflows, not always-on agents)

| Function | Mostly | AI? |
|---|---|---|
| Market research | Targeted weekly pulls (search trends, Reddit read-only, competitors) | Cheap model to summarise |
| Strategist | Stored strategy per app, revisited quarterly | Strong model, rarely |
| Content creator | Batch generation from content pillars | Cheap/local model |
| Creative production | Templates → images/carousels/video (HTML/SVG render, FFmpeg) | None for routine work |
| QA | Deterministic checks first, AI judge second, max retries | Cheap/local model |
| Publishing | Queue, official APIs only, retries, dedup | None |
| Growth analyst | Metrics collection + comparisons | Cheap model for weekly summary |
| Budget & risk | Caps, kill switches, alerts | **Never AI** |

## Phases

| Phase | What | Tied to |
|---|---|---|
| 1. Foundation | Host on the N95, database, secrets, monitoring, budget tracking | Before StackUp launch |
| 2. Pilot app | StackUp config, pillars, templates, generation, QA, publishing, analytics | StackUp |
| 3. Autonomous organic | Scheduled research, batch generation, auto-publish, weekly report | StackUp live |
| 4. Portfolio | Multi-app configs, separate queues and analytics, cross-promotion rules | App 2 onboarded |
| 5. Optimisation | Bounded experiments, template/pillar learning, app scoring (kill/continue/scale) | Several apps live |
| 6. Paid ads | Integrations, hard caps, approval gates | Only once organic works |

## Open decisions (to research with current pricing/API docs at build time)

- Orchestrator: n8n self-hosted vs plain Python workers + cron (or a hybrid)
- Database: SQLite vs PostgreSQL for the first phase
- AI models and pricing per tier
- Which platforms allow official automated publishing, and on what account types
- Notification channel (Telegram / Discord / email)
- Social accounts: per app, shared, or hybrid

## Deliverables owed (from the brief §24)

Architecture, diagram, tech selection, cost model (1/5/10/25/50 apps), hardware plan,
workflows, DB schema, onboarding process, content system, platform matrix, security
model, monitoring, dashboard, roadmap, operational runbook. Produced during phase 1,
with researched, current figures (not guesses).
