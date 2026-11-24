#!/usr/bin/env node
// Render one Kaos video from a plan file.
//   node render/render.mjs --plan plan.json --out video.mp4 [--audio voice.mp3] [--still 2.5 --out frame.png]
// Needs: Node 20+, ffmpeg, Chrome or Chromium (CHROME_PATH, default /usr/bin/google-chrome), playwright-core
// (npm install in render/). The plan is written by gme/video.py; see docs/VIDEO.md.
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, existsSync, createReadStream, statSync, writeFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i < 0 ? d : process.argv[i + 1]; };
const plan = JSON.parse(readFileSync(resolve(arg("plan")), "utf8"));
const out = resolve(arg("out", "video.mp4"));
const audio = arg("audio") ? resolve(arg("audio")) : null;
const delay = Number(arg("audio-delay", 0));
const still = arg("still") !== undefined ? Number(arg("still")) : null;

async function loadChromium() {
  const dirs = [process.env.PLAYWRIGHT_DIR, join(HERE, "node_modules"), join(HERE, "../node_modules"), join(HERE, "../../../node_modules"), join(HERE, "../../../stackup/node_modules")].filter(Boolean);
  for (const d of dirs) for (const name of ["playwright-core", "playwright"]) {
    try { return (await import(pathToFileURL(join(d, name, "index.mjs")).href)).chromium; } catch {}
  }
  console.error("playwright-core not found: run `npm install` in render/ or set PLAYWRIGHT_DIR"); process.exit(1);
}

// mouth openness 0..1 per frame from the voice's loudness
function mouthEnvelope(file, fps, frames) {
  const r = spawnSync("ffmpeg", ["-v", "error", "-i", file, "-f", "f32le", "-ac", "1", "-ar", "8000", "-"], { maxBuffer: 1 << 28 });
  if (r.status !== 0) return new Array(frames).fill(0);
  const f = new Float32Array(r.stdout.buffer, r.stdout.byteOffset, Math.floor(r.stdout.length / 4));
  const win = Math.round(8000 / fps), vals = [];
  for (let i = 0; i < frames; i++) { let s = 0, c = 0; for (let j = i * win; j < Math.min(f.length, (i + 1) * win); j++) { s += f[j] * f[j]; c++; } vals.push(c ? Math.sqrt(s / c) : 0); }
  const sorted = [...vals].sort((a, b) => a - b), ref = sorted[Math.floor(sorted.length * 0.9)] || 1e-6;
  let prev = 0; return vals.map((v) => { const k = Math.min(1, v / ref); const o = v < ref * 0.12 ? 0 : k; prev = 0.45 * prev + 0.55 * o; return Math.round(prev * 100) / 100; });
}

const MIME = { ".html": "text/html", ".js": "text/javascript", ".woff2": "font/woff2", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".png": "image/png" };
const roots = { "/render/": HERE, "/demo/": plan.demo ? resolve(plan.demo.dir) : HERE };
const server = createServer((req, res) => {
  const u = decodeURIComponent(req.url.split("?")[0]);
  for (const [prefix, root] of Object.entries(roots)) {
    if (u.startsWith(prefix)) {
      const p = resolve(root, "." + u.slice(prefix.length - 1));
      if (p.startsWith(root) && existsSync(p) && statSync(p).isFile()) { res.writeHead(200, { "content-type": MIME[extname(p)] || "application/octet-stream" }); return createReadStream(p).pipe(res); }
    }
  }
  res.writeHead(404); res.end();
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;

const fps = plan.fps || 30, frames = Math.ceil(plan.total * fps);
plan.mouth = plan.mouth || (audio ? mouthEnvelope(audio, fps, frames) : new Array(frames).fill(0));
if (plan.demo) plan.demo.url = `${base}/demo`;
if (plan.logoFile) plan.logo = `${base}/render/${plan.logoFile}`;

const chromium = await loadChromium();
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
page.on("pageerror", (e) => { console.error("page error:", e.message); process.exitCode = 1; });
await page.goto(`${base}/render/video.html`);
const info = await page.evaluate((p) => window.video.setup(p), plan);

if (still !== null) {                          // one frame, for checking the look
  const n = Math.round(still * fps); let b64;
  for (let i = 0; i <= n; i++) b64 = await page.evaluate((k) => window.video.frame(k), i);
  writeFileSync(out, Buffer.from(b64, "base64")); console.log(`still ${still}s -> ${out}`);
} else {
  const args = ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-"];
  if (audio) args.push("-i", audio);
  args.push("-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast");
  if (audio) args.push("-c:a", "aac", "-b:a", "160k", "-af", (delay > 0 ? `adelay=${Math.round(delay * 1000)}:all=1,` : "") + "loudnorm=I=-14:TP=-1.5:LRA=11,apad", "-shortest");
  args.push("-movflags", "+faststart", out);
  const ff = spawn("ffmpeg", args, { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((r) => ff.on("close", r));
  for (let n = 0; n < info.frames; n++) {
    const b64 = await page.evaluate((k) => window.video.frame(k), n);
    if (!ff.stdin.write(Buffer.from(b64, "base64"))) await new Promise((r) => ff.stdin.once("drain", r));
  }
  ff.stdin.end();
  const code = await done;
  console.log(code === 0 ? `ok ${out} (${info.frames} frames, ${(info.frames / fps).toFixed(1)}s)` : `FAILED ${out}`);
  if (code !== 0) process.exitCode = 1;
}
await browser.close(); server.close();
