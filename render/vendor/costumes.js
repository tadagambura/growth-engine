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
  const COSTUMES = {
    newyear: { status: "done", draw(c, hd) { shades(c, hd, this.s, this.face); cap(c, hd, this.s, this.face, TOMATO, LIME); } },
    // Designed in the constitution (docs/growth/CONSTITUTION.md), art still to do:
    valentines: { status: "todo" }, pancake: { status: "todo" }, stpatricks: { status: "todo" }, flowers: { status: "todo" },
    jester: { status: "todo" }, easter: { status: "todo" }, earth: { status: "todo" }, exams: { status: "todo" }, dadhat: { status: "todo" },
    backtoschool: { status: "todo" }, halloween: { status: "todo" }, bonfire: { status: "todo" }, thanksgiving: { status: "todo" },
    blackfriday: { status: "todo" }, christmas: { status: "todo" }, winter: { status: "todo" }, spring: { status: "todo" },
    summer: { status: "todo" }, autumn: { status: "todo" },
  };
  FS.costumes = COSTUMES;
  // Put a costume on the first man in the world (Kaos). Other characters keep their own look.
  FS.dress = (man, id) => { const k = COSTUMES[id]; if (k && k.draw && !man.hat) man.hat = k.draw; return !!(k && k.draw); };
})();
