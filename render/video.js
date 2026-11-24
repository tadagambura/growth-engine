// Draws one frame of a Kaos video at a time. render.mjs calls window.video.setup(plan) once, then
// window.video.frame(n) for n = 0..frames-1 and pipes the JPEGs into ffmpeg. Deterministic: seeded
// random numbers and fixed 1/120 s physics steps, so the same plan always gives the same video.
(() => {
  const FW = 1080, FH = 1920, SW = 220, SH = 120;
  const INK = "#141414", PAPER = "#f6f1e7", TOMATO = "#ff4d2e", LIME = "#c6f432";
  const cv = document.getElementById("c"), x = cv.getContext("2d");
  let P, w, m, ctx, fps, frameNo, logo, demo = null;

  function seed(s) { let a = s >>> 0; Math.random = () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const wrap = (text, maxW, font) => { x.font = font; const words = text.split(" "), lines = []; let cur = ""; for (const wd of words) { const t = cur ? cur + " " + wd : wd; if (x.measureText(t).width > maxW && cur) { lines.push(cur); cur = wd; } else cur = t; } if (cur) lines.push(cur); return lines; };
  const loadImg = (src) => new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src; });

  async function setup(plan) {
    P = plan; fps = plan.fps; seed(plan.seed || 7);
    await document.fonts.load('64px "Bagel Fat One"');
    logo = plan.logo ? await loadImg(plan.logo) : null;
    const startsWalking = (plan.beats[0].acts || [])[0] === "walk_in";
    w = new FS.World(SW);
    m = w.man({ x: w.X(startsWalking ? -12 : 110) });
    if (plan.costume) FS.dress(m, plan.costume);
    ctx = { cx: w.X(110), state: {} };
    for (const b of plan.beats) {                       // spread each beat's acts evenly across the beat
      const per = (b.end - b.start) / b.acts.length;
      b.acts.forEach((a, i) => { const f = window.KAOS_ACTS[a]; if (f) f(w, w.tl, m, b.start + i * per, per, ctx); });
    }
    if (plan.demo) {
      const d = plan.demo; const imgs = [];
      for (let i = 1; i <= d.count; i++) imgs.push(loadImg(`${d.url}/f${String(i).padStart(5, "0")}.jpg`));
      demo = { ...d, imgs: await Promise.all(imgs) };
    }
    frameNo = 0;
    return { frames: Math.ceil(plan.total * fps) };
  }

  const beatAt = (t) => P.beats.find((b) => t >= b.start && t < b.end) || P.beats[P.beats.length - 1];
  const capAt = (t) => P.captions.find((c) => t >= c.start && t < c.end);

  function card(x0, y0, wd, ht, r, fill) {
    x.save(); x.fillStyle = INK; x.beginPath(); x.roundRect(x0 - 10, y0 - 10, wd + 20, ht + 20, r + 8); x.fill();
    x.beginPath(); x.roundRect(x0, y0, wd, ht, r); x.clip(); x.fillStyle = fill; x.fillRect(x0, y0, wd, ht); x.restore();
  }
  // The stage is zoomed in on Kaos: a 164 x 90 window of the 220 x 120 world, centred on him.
  const WIN = { x: 110 - 82, y: 20, w: 164, h: 90 };
  function stage(x0, y0, scale, fill) {
    const wd = WIN.w * scale, ht = WIN.h * scale;
    card(x0, y0, wd, ht, 34, fill);
    x.save(); x.beginPath(); x.roundRect(x0, y0, wd, ht, 34); x.clip(); x.translate(x0, y0); x.scale(scale, scale); x.translate(-WIN.x, -WIN.y); w.draw(x); x.restore();
  }
  function caption(c, cy, size) {
    const font = `${size}px "Bagel Fat One"`; x.font = font; x.textAlign = "left"; x.textBaseline = "alphabetic";
    const words = c.text.split(" "), gap = size * 0.28;
    const widths = words.map((t) => x.measureText(t).width), total = widths.reduce((a, b) => a + b, 0) + gap * (words.length - 1);
    let px = (FW - total) / 2;
    x.lineJoin = "round"; x.lineWidth = size * 0.2; x.strokeStyle = INK;
    words.forEach((t, i) => { x.strokeText(t, px, cy); x.fillStyle = c.emphasis.includes(i) ? LIME : "#ffffff"; x.fillText(t, px, cy); px += widths[i] + gap; });
  }
  function footer(dark) {
    x.textAlign = "center"; x.font = '38px "Bagel Fat One"'; x.fillStyle = dark ? PAPER : INK;
    x.fillText("A Kaotic Chainz Production", FW / 2, FH - 130);
    if (logo) x.drawImage(logo, FW / 2 - 36, FH - 112, 72, 72);
  }
  function pill(text, cx, cy, fill) {
    x.font = '46px "Bagel Fat One"'; const wd = x.measureText(text).width + 70;
    x.save(); x.translate(cx, cy); x.rotate(-0.03); x.fillStyle = INK; x.beginPath(); x.roundRect(-wd / 2 + 6, -38 + 6, wd, 76, 38); x.fill();
    x.fillStyle = fill; x.strokeStyle = INK; x.lineWidth = 5; x.beginPath(); x.roundRect(-wd / 2, -38, wd, 76, 38); x.fill(); x.stroke();
    x.fillStyle = INK; x.textAlign = "center"; x.fillText(text, 0, 16); x.restore();
  }

  function frame(n) {
    const t = n / fps;
    while (frameNo < n) { for (let i = 0; i < 4; i++) w.step(1 / 120); frameNo++; }
    m.mouthOpen = P.mouth[n] || 0;
    const b = beatAt(t), layout = b.layout;
    x.setTransform(1, 0, 0, 1, 0, 0); x.textBaseline = "alphabetic";

    if (layout === "endcard") {
      x.fillStyle = INK; x.fillRect(0, 0, FW, FH);
      stage(40, 250, 6.1, P.stageColor);
      x.textAlign = "center"; x.fillStyle = LIME;
      wrap(b.text, FW - 160, '70px "Bagel Fat One"').forEach((l, i) => { x.font = '70px "Bagel Fat One"'; x.fillStyle = i === 0 ? LIME : PAPER; x.fillText(l, FW / 2, 1020 + i * 86); });
      footer(true);
      return cv.toDataURL("image/jpeg", 0.92).slice(23);
    }

    x.fillStyle = PAPER; x.fillRect(0, 0, FW, FH);
    x.textAlign = "center"; x.fillStyle = INK;
    if (layout === "demo" && demo) {
      x.font = '56px "Bagel Fat One"'; wrap(P.title, FW - 140, '56px "Bagel Fat One"').slice(0, 1).forEach((l) => x.fillText(l, FW / 2, 140));
      const pw = 434, ph = 940, px = (FW - pw) / 2, py = 215;
      x.save(); x.fillStyle = INK; x.beginPath(); x.roundRect(px - 16, py - 16, pw + 32, ph + 32, 64); x.fill(); x.restore();
      const dur = Math.max(0.1, b.end - b.start), rate = Math.min(2, Math.max(0.7, demo.seconds / dur));
      const idx = Math.min(demo.imgs.length - 1, Math.floor((t - b.start) * rate * demo.fps));
      const img = demo.imgs[idx];
      x.save(); x.beginPath(); x.roundRect(px, py, pw, ph, 48); x.clip(); x.fillStyle = "#fff"; x.fillRect(px, py, pw, ph);
      if (img) x.drawImage(img, px, py, pw, ph); x.restore();
      stage((FW - WIN.w * 3.3) / 2, 1370, 3.3, P.stageColor);
      const c = capAt(t); if (c) caption(c, 1290, 76);
      footer(false);
    } else {
      x.font = '80px "Bagel Fat One"';
      wrap(P.title, FW - 140, '80px "Bagel Fat One"').slice(0, 3).forEach((l, i) => { x.font = '80px "Bagel Fat One"'; x.fillText(l, FW / 2, 250 + i * 92); });
      stage(40, 560, 6.1, P.stageColor);
      const c = capAt(t); if (c) caption(c, 1340, 96);
      pill(P.appName, FW / 2, 1580, P.stageColor);
      footer(false);
    }
    return cv.toDataURL("image/jpeg", 0.92).slice(23);
  }

  window.video = { setup, frame };
})();
