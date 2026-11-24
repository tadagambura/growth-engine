// VENDORED from the master App Portfolio repo (scripts/sync_render_vendor.sh). Do not edit here.
// Kaos's costumes. Each is a hat callback: called by the stickman as a method, so `this` is the man
// (face direction, scale). Load after fluidstick.js. The engine picks the costume by date
// (growth-maintenance-engine configs/seasons.json); `status` says whether the art exists yet.
(() => {
  const INK = "#141414", TOMATO = "#ff4d2e", LIME = "#c6f432";
  const cap = (c, hd, s, face, body, brim) => {          // baseball cap, brim in the facing direction
    c.save(); c.lineWidth = 1.6 * s; c.strokeStyle = INK; c.lineJoin = "round";
    c.fillStyle = body; c.beginPath(); c.arc(hd.x, hd.y - 0.8 * s, 8.6 * s, Math.PI * 1.03, Math.PI * 1.97); c.closePath(); c.fill(); c.stroke();
    c.fillStyle = brim; c.beginPath();
    c.moveTo(hd.x + face * 2 * s, hd.y - 4.6 * s); c.quadraticCurveTo(hd.x + face * 9 * s, hd.y - 6.2 * s, hd.x + face * 14 * s, hd.y - 2.4 * s);
    c.quadraticCurveTo(hd.x + face * 9 * s, hd.y - 1.4 * s, hd.x + face * 2 * s, hd.y - 1.8 * s); c.closePath(); c.fill(); c.stroke(); c.restore();
  };
  const shades = (c, hd, s, face) => {                   // dark lenses over the eyes
    c.save(); c.fillStyle = INK; c.strokeStyle = INK; c.lineWidth = 1.1 * s; const cx = hd.x + face * 1.2 * s, y = hd.y - 0.2 * s;
    for (const d of [-3, 3]) { c.beginPath(); c.ellipse(cx + d * s, y, 2.9 * s, 2.1 * s, 0, 0, Math.PI * 2); c.fill(); }
    c.beginPath(); c.moveTo(cx - 0.4 * s, y - 0.2 * s); c.lineTo(cx + 0.4 * s, y - 0.2 * s); c.stroke();
    c.beginPath(); c.moveTo(cx - 5.8 * s, y - 0.3 * s); c.lineTo(hd.x - 8 * s, y - 0.6 * s); c.stroke();
    c.strokeStyle = LIME; c.lineWidth = 0.7 * s; c.beginPath(); c.moveTo(cx - 4.4 * s, y - 1 * s); c.lineTo(cx - 3.2 * s, y - 1.5 * s); c.moveTo(cx + 1.6 * s, y - 1 * s); c.lineTo(cx + 2.8 * s, y - 1.5 * s); c.stroke(); c.restore();
  };
  // ---- shared drawing helpers (all costumes are drawn with the ink outline, in the head's local space) ----
  const stroke = (c, s) => { c.lineWidth = 1.5 * s; c.strokeStyle = INK; c.lineJoin = "round"; c.lineCap = "round"; };
  const poly = (c, pts, fill, s) => { stroke(c, s); c.fillStyle = fill; c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) c.lineTo(p[0], p[1]); c.closePath(); c.fill(); c.stroke(); };
  const dot = (c, x, y, r, fill, s) => { stroke(c, s); c.fillStyle = fill; c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill(); c.stroke(); };
  const ell = (c, x, y, rx, ry, fill, s, rot = 0) => { stroke(c, s); c.fillStyle = fill; c.beginPath(); c.ellipse(x, y, rx, ry, rot, 0, Math.PI * 2); c.fill(); c.stroke(); };
  const rect = (c, x, y, w, h, r, fill, s) => { stroke(c, s); c.fillStyle = fill; c.beginPath(); c.roundRect(x, y, w, h, r); c.fill(); c.stroke(); };
  const beanie = (c, hd, s, f, body, band, pom) => {
    c.save(); stroke(c, s); c.fillStyle = body; c.beginPath(); c.arc(hd.x, hd.y - 1 * s, 8.8 * s, Math.PI * 1.05, Math.PI * 1.95); c.closePath(); c.fill(); c.stroke();
    rect(c, hd.x - 9 * s, hd.y - 5.2 * s, 18 * s, 3.6 * s, 1.5 * s, band, s); if (pom) dot(c, hd.x, hd.y - 9.8 * s, 2.3 * s, pom, s); c.restore();
  };
  const cone = (c, hd, s, f, body, trim, tip, bend) => {   // tall pointed hat (santa, witch, jester base)
    c.save(); poly(c, [[hd.x - 8.5 * s, hd.y - 4 * s], [hd.x + bend * f * s, hd.y - 17 * s], [hd.x + 8.5 * s, hd.y - 4 * s]], body, s);
    if (trim) rect(c, hd.x - 9.5 * s, hd.y - 6 * s, 19 * s, 3.8 * s, 1.8 * s, trim, s); if (tip) dot(c, hd.x + bend * f * s, hd.y - 17.5 * s, 2.4 * s, tip, s); c.restore();
  };
  const glasses = (c, hd, s, f, fill, round) => {
    c.save(); stroke(c, s); const cx = hd.x + f * 1.2 * s, y = hd.y - 0.2 * s;
    for (const d of [-3, 3]) { c.fillStyle = fill; c.beginPath(); c.ellipse(cx + d * s, y, 2.9 * s, 2.5 * s, 0, 0, Math.PI * 2); round ? c.stroke() : (c.fill(), c.stroke()); }
    c.beginPath(); c.moveTo(cx - 0.4 * s, y); c.lineTo(cx + 0.4 * s, y); c.stroke(); c.restore();
  };
  const heart = (c, x, y, r, fill, s) => { stroke(c, s); c.fillStyle = fill; c.beginPath(); c.moveTo(x, y + r * 0.9); c.bezierCurveTo(x - r * 1.6, y - r * 0.2, x - r * 0.7, y - r * 1.3, x, y - r * 0.4); c.bezierCurveTo(x + r * 0.7, y - r * 1.3, x + r * 1.6, y - r * 0.2, x, y + r * 0.9); c.fill(); c.stroke(); };

  const COSTUMES = {
    newyear: { status: "done", draw(c, hd) { shades(c, hd, this.s, this.face); cap(c, hd, this.s, this.face, TOMATO, LIME); } },
    christmas: { status: "done", draw(c, hd) { const s = this.s, f = this.face; cone(c, hd, s, f, TOMATO, "#fff", "#fff", -6); } },
    halloween: { status: "done", draw(c, hd) { const s = this.s, f = this.face; ell(c, hd.x, hd.y - 4.2 * s, 12 * s, 2.4 * s, "#3b2a55", s); cone(c, hd, s, f, "#3b2a55", null, null, 5); rect(c, hd.x - 6 * s, hd.y - 7.6 * s, 12 * s, 3 * s, 1 * s, "#ff8a1e", s); } },
    easter: { status: "done", draw(c, hd) { const s = this.s; for (const d of [-1, 1]) { ell(c, hd.x + d * 4 * s, hd.y - 14 * s, 2.6 * s, 7.5 * s, "#fff", s, d * 0.18); ell(c, hd.x + d * 4 * s, hd.y - 14 * s, 1.1 * s, 5.2 * s, "#ff9ec7", 0.01, d * 0.18); } } },
    valentines: { status: "done", draw(c, hd) { const s = this.s, f = this.face, cx = hd.x + f * 1.2 * s; heart(c, cx - 3 * s, hd.y - 0.3 * s, 3.1 * s, "#ff3d6e", s); heart(c, cx + 3 * s, hd.y - 0.3 * s, 3.1 * s, "#ff3d6e", s); heart(c, hd.x, hd.y - 11 * s, 2.6 * s, "#ff3d6e", s); } },
    pancake: { status: "done", draw(c, hd) { const s = this.s; rect(c, hd.x - 7 * s, hd.y - 6 * s, 14 * s, 3.6 * s, 1 * s, "#fff", s); for (const d of [-4.5, 0, 4.5]) dot(c, hd.x + d * s, hd.y - 10 * s, 4 * s, "#fff", s); rect(c, hd.x - 7 * s, hd.y - 8.5 * s, 14 * s, 3 * s, 0.5 * s, "#fff", 0.01); } },
    stpatricks: { status: "done", draw(c, hd) { const s = this.s; ell(c, hd.x, hd.y - 5 * s, 10 * s, 2 * s, "#1f9e4a", s); rect(c, hd.x - 6 * s, hd.y - 14 * s, 12 * s, 9.5 * s, 1 * s, "#1f9e4a", s); rect(c, hd.x - 6 * s, hd.y - 8 * s, 12 * s, 2.6 * s, 0.4 * s, INK, s); rect(c, hd.x - 1.6 * s, hd.y - 8.2 * s, 3.2 * s, 3 * s, 0.5 * s, "#ffc93c", 0.01); } },
    flowers: { status: "done", draw(c, hd) { const s = this.s, cols = [TOMATO, "#ffc93c", "#ff7ab6", "#fff"]; for (let i = 0; i < 5; i++) { const a = Math.PI * (1.12 + i * 0.19); dot(c, hd.x + Math.cos(a) * 8.6 * s, hd.y + Math.sin(a) * 8.2 * s, 2.3 * s, cols[i % 4], s); dot(c, hd.x + Math.cos(a) * 8.6 * s, hd.y + Math.sin(a) * 8.2 * s, 0.7 * s, "#ffc93c", 0.01); } } },
    jester: { status: "done", draw(c, hd) { const s = this.s; poly(c, [[hd.x - 8 * s, hd.y - 4 * s], [hd.x - 11 * s, hd.y - 15 * s], [hd.x - 2 * s, hd.y - 7 * s], [hd.x + 2 * s, hd.y - 7 * s], [hd.x + 11 * s, hd.y - 15 * s], [hd.x + 8 * s, hd.y - 4 * s]], "#7a4dff", s); dot(c, hd.x - 11 * s, hd.y - 15.5 * s, 2 * s, "#ffc93c", s); dot(c, hd.x + 11 * s, hd.y - 15.5 * s, 2 * s, "#ffc93c", s); rect(c, hd.x - 9 * s, hd.y - 6 * s, 18 * s, 3 * s, 1 * s, "#ffc93c", s); } },
    earth: { status: "done", draw(c, hd) { const s = this.s; for (let i = 0; i < 5; i++) { const a = Math.PI * (1.15 + i * 0.175); ell(c, hd.x + Math.cos(a) * 8.4 * s, hd.y + Math.sin(a) * 8 * s, 3 * s, 1.5 * s, "#2f9e44", s, a + Math.PI / 2); } } },
    exams: { status: "done", draw(c, hd) { const s = this.s, f = this.face; glasses(c, hd, s, f, "#fff", true); stroke(c, s); c.fillStyle = "#ffc93c"; c.save(); c.translate(hd.x - f * 6.5 * s, hd.y - 2.5 * s); c.rotate(-0.5 * f); c.beginPath(); c.roundRect(-0.9 * s, -6 * s, 1.8 * s, 9 * s, 0.4 * s); c.fill(); c.stroke(); c.restore(); } },
    dadhat: { status: "done", draw(c, hd) { const s = this.s, f = this.face; stroke(c, s); c.fillStyle = "#7a5b3a"; c.beginPath(); c.ellipse(hd.x, hd.y - 4.8 * s, 9.6 * s, 4.4 * s, 0, Math.PI, Math.PI * 2); c.closePath(); c.fill(); c.stroke(); rect(c, hd.x - 9 * s, hd.y - 5.6 * s, 18 * s, 2 * s, 1 * s, "#5c4429", s); poly(c, [[hd.x + f * 4 * s, hd.y - 5 * s], [hd.x + f * 12 * s, hd.y - 4.4 * s], [hd.x + f * 4 * s, hd.y - 3.2 * s]], "#5c4429", s); } },
    backtoschool: { status: "done", draw(c, hd) { const s = this.s, f = this.face; glasses(c, hd, s, f, "#fff", true); poly(c, [[hd.x - 9 * s, hd.y - 5 * s], [hd.x, hd.y - 8.5 * s], [hd.x + 9 * s, hd.y - 5 * s], [hd.x, hd.y - 2.5 * s]], INK, s); rect(c, hd.x - 4.5 * s, hd.y - 5.6 * s, 9 * s, 3 * s, 0.6 * s, INK, s); c.save(); stroke(c, s); c.beginPath(); c.moveTo(hd.x + 9 * s, hd.y - 5 * s); c.lineTo(hd.x + 10.5 * s, hd.y + 1 * s); c.stroke(); dot(c, hd.x + 10.5 * s, hd.y + 1.6 * s, 1.1 * s, "#ffc93c", s); c.restore(); } },
    bonfire: { status: "done", draw(c, hd) { const s = this.s; beanie(c, hd, s, this.face, "#d6452a", "#ffc93c", "#ffc93c"); } },
    thanksgiving: { status: "done", draw(c, hd) { const s = this.s; beanie(c, hd, s, this.face, "#d97a1d", "#7a4a1d", null); for (const [i, col] of [[-1, TOMATO], [0, "#ffc93c"], [1, "#2f9e44"]]) ell(c, hd.x + i * 2.6 * s, hd.y - 12 * s, 1.5 * s, 4.4 * s, col, s, i * 0.35); } },
    blackfriday: { status: "done", draw(c, hd) { const s = this.s, f = this.face; shades(c, hd, s, f); rect(c, hd.x - 8 * s, hd.y - 8.6 * s, 16 * s, 4.6 * s, 1 * s, TOMATO, s); stroke(c, s); c.fillStyle = "#fff"; c.font = `700 ${3.6 * s}px sans-serif`; c.textAlign = "center"; c.fillText("SALE", hd.x, hd.y - 5 * s); } },
    winter: { status: "done", draw(c, hd) { const s = this.s; beanie(c, hd, s, this.face, "#4d8dff", "#fff", "#fff"); } },
    spring: { status: "done", draw(c, hd) { const s = this.s; stroke(c, s); c.fillStyle = "#ffe14d"; c.beginPath(); c.ellipse(hd.x, hd.y - 4.4 * s, 9.5 * s, 4.6 * s, 0, Math.PI, Math.PI * 2); c.closePath(); c.fill(); c.stroke(); rect(c, hd.x - 9.5 * s, hd.y - 5 * s, 19 * s, 2.2 * s, 1 * s, "#2ec4b6", s); for (const d of [-4, 4]) dot(c, hd.x + d * s, hd.y - 9.5 * s, 1.5 * s, "#ff7ab6", s); } },
    summer: { status: "done", draw(c, hd) { const s = this.s; ell(c, hd.x, hd.y - 4.4 * s, 15 * s, 3 * s, "#f2c566", s); stroke(c, s); c.fillStyle = "#f2c566"; c.beginPath(); c.ellipse(hd.x, hd.y - 5 * s, 7.5 * s, 6 * s, 0, Math.PI, Math.PI * 2); c.closePath(); c.fill(); c.stroke(); rect(c, hd.x - 7.5 * s, hd.y - 7.4 * s, 15 * s, 2.4 * s, 1 * s, TOMATO, s); } },
    autumn: { status: "done", draw(c, hd) { const s = this.s; beanie(c, hd, s, this.face, "#c4561f", "#7a4a1d", null); ell(c, hd.x + 4 * s, hd.y - 10.4 * s, 3 * s, 1.6 * s, "#ffa01e", s, -0.6); } },
  };
  FS.costumes = COSTUMES;
  // Put a costume on the first man in the world (Kaos). Other characters keep their own look.
  FS.dress = (man, id) => { const k = COSTUMES[id]; if (k && k.draw && !man.hat) man.hat = k.draw; return !!(k && k.draw); };
})();
