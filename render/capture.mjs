#!/usr/bin/env node
// Record scripted walk-throughs of an app's web build into assets/demos/<app>/<journey>.mp4.
//   node render/capture.mjs --app stackup --dist "/path/to/stackup/dist" [--journey safe_to_spend]
// Run it when an app's screens change (not daily): the daily pipeline only reads the saved clips.
import { spawnSync } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, statSync, createReadStream, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url)), ROOT = resolve(HERE, "..");
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i < 0 ? d : process.argv[i + 1]; };
const app = arg("app"), dist = resolve(arg("dist")), only = arg("journey");
const cfg = JSON.parse(readFileSync(join(ROOT, `configs/journeys/${app}.json`), "utf8"));
const forbidden = new Set(cfg.forbidden_testids || []);
const outDir = join(ROOT, "assets/demos", app); mkdirSync(outDir, { recursive: true });

async function loadChromium() {
  const dirs = [process.env.PLAYWRIGHT_DIR, join(HERE, "node_modules"), join(ROOT, "node_modules"), join(HERE, "../../../node_modules"), join(HERE, "../../../stackup/node_modules")].filter(Boolean);
  for (const d of dirs) for (const name of ["playwright-core", "playwright"]) { try { return (await import(pathToFileURL(join(d, name, "index.mjs")).href)).chromium; } catch {} }
  console.error("playwright-core not found"); process.exit(1);
}
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".woff2": "font/woff2", ".ico": "image/x-icon", ".wasm": "application/wasm" };
const server = createServer((req, res) => {
  const u = decodeURIComponent(req.url.split("?")[0]); let p = resolve(dist, "." + u);
  if (!p.startsWith(dist) || !existsSync(p) || !statSync(p).isFile()) p = join(dist, "index.html");   // single-page app fallback
  res.writeHead(200, { "content-type": MIME[extname(p)] || "application/octet-stream" }); createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;
const chromium = await loadChromium();
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });

for (const [name, steps] of Object.entries(cfg.journeys)) {
  if (only && name !== only) continue;
  const tmp = join(outDir, `.tmp-${name}`); rmSync(tmp, { recursive: true, force: true }); mkdirSync(tmp, { recursive: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, recordVideo: { dir: tmp, size: { width: 390, height: 844 } } });
  const page = await context.newPage(); const t0 = Date.now(); let mark = 0.7; const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    for (const s of steps) {
      if (s.mark) mark = Math.max(0.7, (Date.now() - t0) / 1000 - 0.35);
      else if (s.goto) await page.goto(base + s.goto);
      else if (s.wait) await page.waitForTimeout(s.wait);
      else if (s.click) { if (forbidden.has(s.click)) throw new Error(`forbidden test id ${s.click}`); await page.getByTestId(s.click).click({ timeout: 8000 }); await page.waitForTimeout(450); }
      else if (s.fill) { await page.getByTestId(s.fill[0]).fill(s.fill[1], { timeout: 8000 }); await page.waitForTimeout(450); }
    }
  } catch (e) { console.error(`${app}/${name}: ${e.message.split("\n")[0]}`); process.exitCode = 1; }
  await context.close();
  const webm = readdirSync(tmp).find((f) => f.endsWith(".webm"));
  if (webm && !errors.length || webm) {
    const mp4 = join(outDir, `${name}.mp4`);
    const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", String(mark.toFixed(2)), "-i", join(tmp, webm), "-vf", "fps=30", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4]);
    const probe = spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).stdout.toString().trim();
    writeFileSync(join(outDir, `${name}.json`), JSON.stringify({ app, journey: name, seconds: Number(probe), width: 390, height: 844, pageErrors: errors }, null, 1));
    console.log(`${app}/${name}: ${probe}s${errors.length ? `  (${errors.length} page errors)` : ""}`);
  }
  rmSync(tmp, { recursive: true, force: true });
}
await browser.close(); server.close();
