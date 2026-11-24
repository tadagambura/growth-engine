# The video engine

One command makes, checks and queues the day's video for every platform: `python -m gme run-day`.

```
planner → script writer → voice → beat timings → captions → demo footage → render → QA → queue → publish
 (code)     (cheap model)   (ElevenLabs) (code)     (code)     (recorded)    (code)  (code)  (code)  (Postiz*)
```
\* Until Postiz is connected (`configs/postiz.json` → `enabled: true`) the publisher writes what it would post to `data/outbox.jsonl`.

| Step | Where | Notes |
|---|---|---|
| Plan | `gme/planner.py`, `configs/content.json`, `configs/formats.json`, `configs/atoms/` | Weekly rhythm, spotlight app, least recently used atom and format, costume, CTA. History keeps repeats away. |
| Script | `gme/scriptwriter.py`, `configs/models.json` | Haiku 5.5, thinking off, strict JSON, validated; evergreen fallback with no model. About £0.0003 a video. |
| Voice | `gme/voice.py`, `configs/voice.json` | Will (ElevenLabs premade). Monthly character guard. Silent fallback if it fails. |
| Timings | `gme/video.py` | Beat start and end come from the voice's per-character timings. |
| Captions | `gme/captions.py` | 2 to 3 words at a time, JSON for the renderer, SRT for platforms. |
| Footage | `render/capture.mjs`, `configs/journeys/`, `assets/demos/` | Real app web builds recorded with Playwright. Only footage mapped to an atom is used. |
| Render | `render/render.mjs`, `render/video.js`, `render/acts.js`, `render/vendor/` | Headless Chrome draws each frame (Kaos, costume, captions, phone), ffmpeg encodes and mixes. |
| QA | `gme/videoqa.py`, `gme/qa.py` | File checks (size, length, loudness, not blank, not frozen) and script checks. A failure is retried once, then alerted. |
| Posts | `gme/posts.py` | Per-platform text, one CTA, tracked link, at most 3 hashtags. |
| Publish | `gme/postiz.py`, `configs/postiz.json` | Uploads the video once, then posts to each connected channel (TikTok, Instagram, YouTube, Facebook, Threads, Bluesky, X, Pinterest). Written from the Postiz docs; needs one live check (`python -m gme postiz channels`). |
| Run | `gme/daily.py`, `deploy/n95/` | systemd timers: make at 06:30 London, publish every 10 minutes. |

## No dates
Videos get reused, so none carries a date: recordings are scrubbed (`render/nodates.js`), scripts and captions are rejected if they name a date or year, and content whose facts depend on a date is skipped (`gme/dates.py`). Tracking links in post text still carry the day.

## Commands
```bash
python -m gme status                 # what the engine is doing
python -m gme plan --days 180        # preview the calendar
python -m gme run-day --date 2026-12-02
python -m gme publish-due
python -m gme pause | resume         # kill switch
python -m gme costume --date 2026-12-31
```

## Install on a new host
`deploy/n95/install-engine.sh` (Ubuntu): Python venv with the `voice` extra, Node, ffmpeg, Chromium via Playwright, the two systemd timers and a Telegram alert on failure.

## Updating the pieces
| What changed | Do |
|---|---|
| Kaos or a costume | `scripts/sync_render_vendor.sh "<path to master App Portfolio>"` |
| Content (cards, lessons, features) | `python3 scripts/export_atoms.py "<path to master>"` |
| An app's screens | `node render/capture.mjs --app <app> --dist "<app>/dist"` (build the web export first) |
| Look of the video | `render/video.js` (layout), `render/acts.js` (Kaos's moves) |

## Known limits
- Games have no footage yet (they need a recorded journey through the Arcade); game videos use the stage layout.
- Three apps have footage (StackUp, LoopDay, AfterHours). The rest use the stage layout until recorded.
- Only New Year has a costume drawn; other days show plain Kaos until each costume is added.
- Posting is a log until Postiz is running, each platform is connected in it, the channel ids are in `configs/postiz.json` and `enabled` is true. TikTok and YouTube may only accept private or draft posts until their API apps are audited.
- If a video fails QA twice, a third attempt in safe mode (no model, no voice) makes the day's video from the atom's own words; if that fails too the day is skipped and the owner is alerted.
