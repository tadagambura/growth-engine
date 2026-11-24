// VENDORED from the master App Portfolio repo (scripts/sync_render_vendor.sh). Do not edit here.
// FluidStick: articulated stick figures for the Kaotic Chainz site.
// Layers: timeline (intent) -> springs (follow-through/overlap) -> rig (2-bone IK) -> physics props -> vector render.
// Canvas 2D, no dependencies, fixed 120 Hz timestep. Add ?debug=1 (or press "d") to see the rig.
const FS = (() => {
  "use strict";
  const PI = Math.PI;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const E = {
    lin: (t) => t,
    io: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    out: (t) => 1 - Math.pow(1 - t, 3),
    in: (t) => t * t * t,
    back: (t) => { const c = 1.9, c3 = c + 1; return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
  };
  const INK = "#141414", SKIN = "#fff3dc";
  const COL = { tomato: "#ff4d2e", lime: "#c6f432", sun: "#ffc93c", mint: "#2ec4b6", sky: "#4d8dff", pink: "#ff7ab6", leaf: "#2f9e44", paper: "#fff8ec" };
  const H = 120, GROUND = 106, GRAV = 520, DT = 1 / 120;
  let DEBUG = /[?&]debug=1/.test(location.search);
  addEventListener("keydown", (e) => { if (e.key === "d" && !/input|textarea/i.test(e.target.tagName)) DEBUG = !DEBUG; });

  // ---------- springs: every animated value lags its target a little ----------
  class Spring {
    constructor(v, k = 120, c = 18) { this.v = v; this.t = v; this.vel = 0; this.k = k; this.c = c; }
    step(dt) { const a = this.k * (this.t - this.v) - this.c * this.vel; this.vel += a * dt; this.v += this.vel * dt; }
    snap(v) { this.v = this.t = v; this.vel = 0; }
  }
  const V = (x, y) => ({ x, y });

  // two-bone IK: returns {j (joint), e (end)}; pick() chooses between the two elbow/knee solutions
  function ik(base, target, a, b, pick) {
    const dx = target.x - base.x, dy = target.y - base.y;
    const d = clamp(Math.hypot(dx, dy), Math.abs(a - b) + 0.01, a + b - 0.01);
    const ang = Math.atan2(dy, dx), off = Math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1));
    const j1 = V(base.x + a * Math.cos(ang + off), base.y + a * Math.sin(ang + off));
    const j2 = V(base.x + a * Math.cos(ang - off), base.y + a * Math.sin(ang - off));
    const e = V(base.x + d * Math.cos(ang), base.y + d * Math.sin(ang));
    return { j: pick(j1, j2), e };
  }

  // ---------- timeline: intent, expressed as tweens of spring targets ----------
  class Timeline {
    constructor() { this.t = 0; this.ev = []; }
    at(t, fn) { this.ev.push({ t, fn }); return this; }
    tw(t, dur, init, apply, ease = E.io) { this.ev.push({ t, dur, init, apply, ease }); return this; }
    step(dt) {
      this.t += dt;
      for (const e of this.ev) {
        if (e.done || this.t < e.t) continue;
        if (!e.dur) { e.fn(); e.done = true; continue; }
        if (!e.started) { e.s = e.init(); e.started = true; }
        const k = clamp((this.t - e.t) / e.dur, 0, 1);
        e.apply(e.ease(k), e.s);
        if (k >= 1) e.done = true;
      }
    }
  }

  // ---------- the character ----------
  class Man {
    constructor(w, { x = 60, face = 1, s = 1, col = INK, hat = null } = {}) {
      this.w = w; this.face = face; this.s = s; this.col = col; this.hat = hat;
      const S = (v, k, c) => new Spring(v, k, c);
      this.rx = S(x, 70, 14); this.floor = S(GROUND, 90, 14);
      this.crouch = S(0, 130, 13); this.lean = S(0, 85, 10); this.tilt = S(0, 60, 7); this.squash = S(1, 220, 13);
      this.look = { x: S(x + 30 * face, 110, 18), y: S(50, 110, 18) };
      this.hand = { l: { x: S(x - 8, 170, 19), y: S(80, 170, 19) }, r: { x: S(x + 8, 170, 19), y: S(80, 170, 19) } };
      this.free = { l: true, r: true };          // free = hangs/swings naturally; false = following a target
      this.grip = { l: "open", r: "open" };
      this.feet = { l: this.mkFoot(x - 6 * s), r: this.mkFoot(x + 6 * s) };
      this.carryOff = { l: null, r: null }; this.pin = null; this.cross = false;
      this.walking = false; this.moon = false; this.expr = "neutral"; this.sweat = 0; this.lift = 0; this.mouthOpen = 0;
      this.pose = {};
      this.solve();
      for (const k of ["l", "r"]) { this.hand[k].x.snap(this.rest(k).x); this.hand[k].y.snap(this.rest(k).y); }
    }
    mkFoot(x) { return { x, lift: 0, swing: null }; }
    springs() { return [this.rx, this.floor, this.crouch, this.lean, this.tilt, this.squash, this.look.x, this.look.y, this.hand.l.x, this.hand.l.y, this.hand.r.x, this.hand.r.y]; }
    rest(k) {
      const p = this.pose, sd = k === "l" ? -1 : 1, sh = p.sh || V(this.rx.v, this.floor.v - 52);
      const swingX = this.walking ? -(this.feet[k].x - this.rx.v) * 0.7 : 0;
      return V(sh.x + sd * 6 * this.s * this.face + swingX - this.rx.vel * 0.04, sh.y + 25 * this.s);
    }
    step(dt) {
      for (const sp of this.springs()) sp.step(dt);
      for (const k of ["l", "r"]) {
        if (this.free[k]) { const r = this.rest(k); this.hand[k].x.t = r.x; this.hand[k].y.t = r.y; }
        else if (this.carryOff[k]) { const o = this.carryOff[k]; this.hand[k].x.t = this.rx.v + o[0] * this.face; this.hand[k].y.t = this.floor.v + o[1]; }
      }
      this.stepFeet(dt);
      this.solve();
    }
    // feet plant and only move during a swing: no skating
    stepFeet(dt) {
      const s = this.s, fl = this.feet.l, fr = this.feet.r, px = this.rx.v;
      for (const f of [fl, fr]) {
        if (f.swing) {
          f.swing.t += dt / f.swing.dur;
          const k = clamp(f.swing.t, 0, 1);
          f.x = lerp(f.swing.from, f.swing.to, E.io(k)); f.lift = Math.sin(PI * k) * 5 * s * (f.swing.hop || 1);
          if (k >= 1) { f.swing = null; f.lift = 0; }
        }
      }
      if (this.pin) { fl.x = lerp(fl.x, this.pin[0], 0.2); fr.x = lerp(fr.x, this.pin[1], 0.2); fl.lift = lerp(fl.lift, this.pin[2] || 0, 0.2); fr.lift = lerp(fr.lift, this.pin[2] || 0, 0.2); return; }
      if (this.moon) { // the moonwalk deliberately slides, heel-toe alternating
        const ph = this.w.time * 7; fl.lift = Math.max(0, Math.sin(ph)) * 3 * s; fr.lift = Math.max(0, -Math.sin(ph)) * 3 * s;
        fl.x = px - 4 * s + Math.sin(ph) * 6 * s; fr.x = px + 4 * s - Math.sin(ph) * 6 * s; return;
      }
      if (fl.swing || fr.swing) return;
      const dir = Math.sign(this.rx.vel) || this.face, spd = Math.abs(this.rx.vel);
      if (this.walking || spd > 4) {
        // cadence and stride adapt to speed so the planted foot never gets dragged
        const dur = clamp(10 * s / Math.max(spd, 1), 0.13, 0.28), reach = spd * dur * 0.95 + 3 * s;
        const back = (fl.x - px) * dir < (fr.x - px) * dir ? fl : fr;
        if ((px - back.x) * dir > 4 * s || Math.abs(px - back.x) > 13 * s) back.swing = { from: back.x, to: px + dir * reach, t: 0, dur };
      } else {
        // settle: step feet back under the hips, one at a time
        const want = { l: px - 6 * s, r: px + 6 * s };
        for (const k of ["l", "r"]) { const f = this.feet[k]; if (Math.abs(f.x - want[k]) > 3.5 * s) { f.swing = { from: f.x, to: want[k], t: 0, dur: 0.22 }; break; } }
      }
    }
    solve() {
      const s = this.s, P = this.pose, fy = this.floor.v;
      const spread = Math.abs(this.feet.l.x - this.feet.r.x);
      const bob = Math.max(0, spread - 10 * s) * 0.12;
      const pel = V(this.rx.v, fy - 33.4 * s + this.crouch.v + bob - this.lift);
      const L = 25 * s * this.squash.v, a = this.lean.v;
      const chest = V(pel.x + Math.sin(a) * L, pel.y - Math.cos(a) * L);
      const ha = a + this.tilt.v;
      const neck = V(chest.x + Math.sin(ha) * 3 * s, chest.y - Math.cos(ha) * 3 * s);
      const head = V(neck.x + Math.sin(ha) * 9 * s, neck.y - Math.cos(ha) * 9 * s);
      const sh = V(lerp(pel.x, chest.x, 0.86), lerp(pel.y, chest.y, 0.86));
      Object.assign(P, { pel, chest, neck, head, sh, ha });
      const armPick = (j1, j2) => {
        const sc = (j) => j.y + 0.7 * Math.abs(j.x - pel.x);
        return sc(j1) > sc(j2) ? j1 : j2;
      };
      for (const k of ["l", "r"]) {
        const r = ik(sh, V(this.hand[k].x.v, this.hand[k].y.v), 12.5 * s, 12.5 * s, armPick);
        P["el" + k] = r.j; P["ha" + k] = r.e;
        const f = this.feet[k];
        const legPick = (j1, j2) => ((j1.x - pel.x) * this.face > (j2.x - pel.x) * this.face ? j1 : j2);
        const hip = V(pel.x + (k === "l" ? -1.5 : 1.5) * s, pel.y);
        const rl = ik(hip, V(f.x, fy - f.lift), 17 * s, 17 * s, legPick);
        P["hip" + k] = hip; P["kn" + k] = rl.j; P["an" + k] = rl.e;
        if (this.cross) {   // cross-legged: knees fall outward, shins cross in front
          const sd = k === "l" ? -1 : 1;
          P["kn" + k] = V(pel.x + sd * 12 * s, pel.y + 2 * s); P["an" + k] = V(pel.x - sd * 4 * s, pel.y + 7 * s);
        }
      }
    }
    handPos(k) { return this.pose["ha" + k]; }
    forearm(k) { const e = this.pose["el" + k], h = this.pose["ha" + k]; return Math.atan2(h.y - e.y, h.x - e.x); }

    // ---- intent helpers (all take the scene timeline) ----
    to(tl, t, dur, o, ease = E.io) {
      const keys = Object.keys(o);
      tl.tw(t, dur, () => keys.map((k) => (k === "look" ? [this.look.x.t, this.look.y.t] : this[k].t)), (e, s0) => keys.forEach((k, i) => {
        if (k === "look") { this.look.x.t = lerp(s0[i][0], o.look[0], e); this.look.y.t = lerp(s0[i][1], o.look[1], e); }
        else this[k].t = lerp(s0[i], o[k], e);
      }), ease);
      return this;
    }
    reach(tl, t, dur, k, p, arc = -8, ease = E.io) {
      const h = this.hand[k];
      tl.tw(t, dur, () => { this.free[k] = false; this.carryOff[k] = null; return [h.x.t, h.y.t]; }, (e, s0) => {
        const mx = (s0[0] + p[0]) / 2, my = (s0[1] + p[1]) / 2 + arc;      // curved path, not a straight line
        h.x.t = (1 - e) * (1 - e) * s0[0] + 2 * (1 - e) * e * mx + e * e * p[0];
        h.y.t = (1 - e) * (1 - e) * s0[1] + 2 * (1 - e) * e * my + e * e * p[1];
      }, ease);
      return this;
    }
    relax(tl, t, k) { tl.at(t, () => { this.free[k] = true; this.carryOff[k] = null; this.grip[k] = "open"; }); return this; }
    carry(tl, t, k, dx = 9, dy = -32) { tl.at(t, () => { this.free[k] = false; this.carryOff[k] = [dx, dy]; }); return this; }
    walk(tl, t, dur, x) {
      tl.at(t, () => { this.walking = true; this.face = Math.sign(x - this.rx.t) || this.face; });
      this.to(tl, t, dur, { rx: x }, E.io);
      tl.at(t + dur, () => { this.walking = false; });
      return this;
    }
    hop(tl, t, h = 14, dur = 0.5) { // anticipation crouch -> launch -> fall -> impact squash -> settle
      this.to(tl, t, 0.14, { crouch: 5 * this.s }, E.out);
      tl.tw(t + 0.14, dur, () => 0, (e) => { this.lift = Math.sin(PI * e) * h; }, E.lin);
      this.to(tl, t + 0.14, 0.1, { crouch: -2 }, E.out);
      tl.at(t + 0.14 + dur, () => { this.lift = 0; this.crouch.vel += 60; this.squash.vel -= 1.5; this.w.puff(this.rx.v, this.floor.v); });
      this.to(tl, t + 0.18 + dur, 0.25, { crouch: 0 }, E.out);
      return this;
    }
    sit(tl, t, dur = 0.6) { tl.at(t, () => { this.pin = [this.rx.t - 11 * this.s, this.rx.t + 11 * this.s, 0]; }); tl.at(t + dur * 0.7, () => { this.cross = true; }); return this.to(tl, t, dur, { crouch: 25 * this.s }); }
    lie(tl, t, dur = 0.8, f = this.face) { tl.at(t, () => { this.pin = [this.rx.t + 26 * f * this.s, this.rx.t + 30 * f * this.s, 2]; }); return this.to(tl, t, dur, { crouch: 27 * this.s, lean: -1.45 * f }); }
    stand(tl, t, dur = 0.6) { tl.at(t, () => { this.pin = null; this.cross = false; }); return this.to(tl, t, dur, { crouch: 0, lean: 0 }); }
    face_(tl, t, expr) { tl.at(t, () => { this.expr = expr; }); return this; }
    say(tl, t, txt, dur = 1.4, col = INK) { tl.at(t, () => this.w.text(txt, this.pose.head.x + 14 * this.face, this.pose.head.y - 14, dur, col)); return this; }

    // ---- render: bendy limbs that pass through every joint ----
    draw(c) {
      const P = this.pose, s = this.s;
      c.save(); c.lineCap = "round"; c.lineJoin = "round"; c.strokeStyle = this.col;
      // ground shadow
      c.fillStyle = "rgba(0,0,0,.13)"; c.beginPath();
      const hgt = clamp(1 - (this.floor.v - 32 * s - P.pel.y) / 60, 0.4, 1);
      c.ellipse(P.pel.x, this.floor.v + 1.5, 13 * s * hgt, 2.4 * s * hgt, 0, 0, PI * 2); c.fill();
      const bend = (a, j, b, w) => { const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2; c.lineWidth = w; c.beginPath(); c.moveTo(a.x, a.y); c.quadraticCurveTo(j.x + (j.x - mx) * 0.55, j.y + (j.y - my) * 0.55, b.x, b.y); c.stroke(); };
      const back = this.face > 0 ? "l" : "r", front = back === "l" ? "r" : "l";
      const leg = (k) => { bend(P["hip" + k], P["kn" + k], P["an" + k], 3.6 * s); if (this.cross) return; const a = P["an" + k], f = this.feet[k];
        c.lineWidth = 3.4 * s; c.beginPath(); c.moveTo(a.x - 1 * s * this.face, a.y); c.lineTo(a.x + 4.5 * s * this.face, a.y - f.lift * 0.15); c.stroke(); };
      const arm = (k) => { bend(P.sh, P["el" + k], P["ha" + k], 3.3 * s); this.drawHand(c, k); };
      leg(back); arm(back);
      // spine curves against the direction of travel (drag), so the body never moves as one rigid block
      const drag = clamp(-this.rx.vel * 0.012 - this.lean.vel * 0.4, -2.4, 2.4) * s;
      const mid = V((P.pel.x + P.neck.x) / 2 + drag, (P.pel.y + P.neck.y) / 2);
      c.lineWidth = 3.8 * s; c.beginPath(); c.moveTo(P.pel.x, P.pel.y); c.quadraticCurveTo(mid.x, mid.y, P.neck.x, P.neck.y); c.stroke();
      leg(front);
      this.drawHead(c);
      arm(front);
      c.restore();
      if (DEBUG) this.debug(c);
    }
    drawHand(c, k) {
      const h = this.pose["ha" + k], s = this.s, g = this.grip[k], ang = this.forearm(k);
      c.fillStyle = this.col;
      if (g === "fist") { c.beginPath(); c.arc(h.x, h.y, 2.6 * s, 0, PI * 2); c.fill(); return; }
      if (g === "grip") { // fingers wrap around whatever is held
        c.lineWidth = 2.2 * s; c.beginPath(); c.arc(h.x + Math.cos(ang) * 1.5 * s, h.y + Math.sin(ang) * 1.5 * s, 2.6 * s, ang + 0.9, ang + 2 * PI - 0.9); c.stroke(); return;
      }
      if (g === "point") { c.lineWidth = 2 * s; c.beginPath(); c.moveTo(h.x, h.y); c.lineTo(h.x + Math.cos(ang) * 4.5 * s, h.y + Math.sin(ang) * 4.5 * s); c.stroke(); }
      c.beginPath(); c.arc(h.x, h.y, 2.1 * s, 0, PI * 2); c.fill();
    }
    drawHead(c) {
      const P = this.pose, s = this.s, hd = P.head, r = 8 * s;
      c.lineWidth = 3.2 * s; c.fillStyle = SKIN; c.beginPath(); c.arc(hd.x, hd.y, r, 0, PI * 2); c.fill(); c.stroke();
      // eyes track the look target
      const lx = this.look.x.v - hd.x, ly = this.look.y.v - hd.y, ld = Math.hypot(lx, ly) || 1;
      const ex = (lx / ld) * 2.6 * s, ey = (ly / ld) * 2 * s, ox = hd.x + ex, oy = hd.y + ey - 0.8 * s;
      c.fillStyle = this.col; c.strokeStyle = this.col; c.lineWidth = 1.2 * s;
      const e = this.expr, gap = 2.6 * s;
      if (e === "zen" || e === "sleepy" || e === "happy") {
        const up = e === "happy" ? -1 : 1;
        for (const d of [-gap, gap]) { c.beginPath(); c.arc(ox + d, oy, 1.4 * s, up < 0 ? PI : 0, up < 0 ? 2 * PI : PI); c.stroke(); }
      } else {
        const big = e === "shock" || e === "ohno" ? 1.6 : 1.15;
        for (const d of [-gap, gap]) { c.beginPath(); c.arc(ox + d, oy, big * s, 0, PI * 2); c.fill(); }
      }
      if (e === "shock" || e === "ohno" || e === "huh") { // brows
        for (const d of [-gap, gap]) { c.beginPath(); c.moveTo(ox + d - 1.6 * s, oy - 3.4 * s - (e === "huh" && d > 0 ? 1.2 * s : 0)); c.lineTo(ox + d + 1.6 * s, oy - 3.8 * s); c.stroke(); }
      }
      const mx = hd.x + ex * 0.8, my = hd.y + 3.6 * s + ey * 0.5;
      if (this.mouthOpen > 0.06) {   // talking: an open mouth that follows the voice (set mouthOpen 0..1 each frame)
        c.fillStyle = this.col; c.beginPath(); c.ellipse(mx, my, (1.3 + 0.7 * this.mouthOpen) * s, (0.5 + 2.3 * this.mouthOpen) * s, 0, 0, PI * 2); c.fill();
      } else {
      c.beginPath();
      if (e === "happy" || e === "zen") c.arc(mx, my - 1 * s, 2.4 * s, 0.15 * PI, 0.85 * PI);
      else if (e === "shock" || e === "ohno") { c.arc(mx, my, 1.6 * s, 0, PI * 2); c.stroke(); c.beginPath(); }
      else if (e === "sleepy") { c.moveTo(mx - 1.4 * s, my); c.lineTo(mx + 1.4 * s, my); }
      else if (e === "huh") { c.moveTo(mx - 1.6 * s, my + 0.6 * s); c.quadraticCurveTo(mx, my - 0.8 * s, mx + 1.8 * s, my + 0.4 * s); }
      else { c.moveTo(mx - 1.5 * s, my); c.quadraticCurveTo(mx, my + 1 * s, mx + 1.5 * s, my); }
      c.stroke();
      }
      if (this.sweat > 0) { c.fillStyle = COL.sky; c.beginPath(); const sx = hd.x - 7 * s * this.face, sy = hd.y - 4 * s + (1 - this.sweat) * 6; c.moveTo(sx, sy - 3 * s); c.quadraticCurveTo(sx + 2.4 * s, sy + 1 * s, sx, sy + 1.6 * s); c.quadraticCurveTo(sx - 2.4 * s, sy + 1 * s, sx, sy - 3 * s); c.fill(); }
      if (this.hat) this.hat(c, hd, P.ha, s);
    }
    debug(c) {
      const P = this.pose; c.save(); c.lineWidth = 0.8;
      for (const [k, p] of Object.entries(P)) if (p && p.x !== undefined) { c.fillStyle = "#e03131"; c.beginPath(); c.arc(p.x, p.y, 1.3, 0, PI * 2); c.fill(); }
      c.strokeStyle = "#1c7ed6";
      for (const k of ["l", "r"]) { c.beginPath(); c.arc(this.hand[k].x.t, this.hand[k].y.t, 2.5, 0, PI * 2); c.stroke(); }
      c.fillStyle = "#2f9e44"; for (const k of ["l", "r"]) { const f = this.feet[k]; c.fillRect(f.x - 2, this.floor.v - 1, 4, f.swing ? 1 : 3); }
      const com = V((P.pel.x + P.chest.x) / 2, (P.pel.y + P.chest.y) / 2); c.strokeStyle = "#f08c00"; c.beginPath(); c.arc(com.x, com.y, 3, 0, PI * 2); c.stroke();
      c.restore();
    }
  }

  // ---------- props: gravity, bounce, friction, held-in-hand ----------
  class Prop {
    constructor(w, draw, { x = 0, y = 0, r = 3, bounce = 0.35, fric = 0.82, rot = 0, mass = 1, z = 1, ...rest } = {}) {
      Object.assign(this, { w, draw, x, y, vx: 0, vy: 0, r, bounce, fric, rot, vr: 0, mass, z, state: "static", held: null, alpha: 1, scale: 1 }, rest);
    }
    attach(man, k, ox = 0, oy = 0, rot = null) { this.state = "held"; this.held = { man, k, ox, oy, rot }; man.grip[k] = "grip"; return this; }
    release(vx = null, vy = null) {
      if (this.held) {
        const { man, k } = this.held, h = man.hand[k];
        this.vx = vx ?? h.x.vel * 0.9; this.vy = vy ?? h.y.vel * 0.9; this.vr = this.vx * 0.05;
        man.grip[k] = "open";
      } else { this.vx = vx ?? 0; this.vy = vy ?? 0; }
      this.held = null; this.state = "free"; return this;
    }
    step(dt) {
      if (this.state === "held") {
        const { man, k, ox, oy, rot } = this.held, h = man.handPos(k), a = man.forearm(k);
        this.x = h.x + ox; this.y = h.y + oy; this.rot = rot === null ? a * 0.25 : rot;
      } else if (this.state === "free") {
        this.vy += GRAV * this.mass * dt; this.x += this.vx * dt; this.y += this.vy * dt; this.rot += this.vr * dt;
        const floor = (this.floorAt ? this.floorAt(this.x) : GROUND) - this.r;
        if (this.y > floor) {
          this.y = floor;
          if (Math.abs(this.vy) > 30) { this.w.puff(this.x, floor + this.r, 0.5); this.onLand && this.onLand(this); this.vx *= this.fric; this.vr *= 0.7; }
          else { this.vx *= 0.996; this.vr *= 0.99; }      // resting contact: gentle rolling friction, not an impact every frame
          this.vy = -this.vy * this.bounce; if (Math.abs(this.vy) < 12) this.vy = 0;
        }
        if (this.x < this.r || this.x > this.w.W - this.r) { this.vx = -this.vx * 0.5; this.x = clamp(this.x, this.r, this.w.W - this.r); }
      }
      this.tick && this.tick(this, dt);
    }
    render(c) { c.save(); c.globalAlpha *= this.alpha; c.translate(this.x, this.y); c.rotate(this.rot); c.scale(this.scale, this.scale); this.draw(c, this); c.restore();
      if (DEBUG) { c.strokeStyle = "#1c7ed6"; c.lineWidth = 0.6; c.beginPath(); c.arc(this.x, this.y, this.r, 0, PI * 2); c.stroke(); } }
  }

  // ---------- the world a scene happens in ----------
  class World {
    constructor(W) { this.W = W; this.cx = W / 2; this.time = 0; this.men = []; this.props = []; this.fx = []; this.tl = new Timeline(); this.ground = true; this.shake = 0; }
    X(x) { return this.cx - 110 + x; }   // scenes are authored on a 220-wide stage, centred
    man(o) { const m = new Man(this, o); this.men.push(m); return m; }
    prop(draw, o) { const p = new Prop(this, draw, o); this.props.push(p); return p; }
    text(txt, x, y, dur = 1.3, col = INK, size = 11) { x = clamp(x, txt.length * size * 0.28 + 4, this.W - txt.length * size * 0.28 - 4); this.fx.push({ kind: "text", txt, x, y, t: 0, dur, col, size }); }
    puff(x, y, n = 1) { for (let i = 0; i < 5 * n; i++) this.fx.push({ kind: "puff", x: x + (Math.random() - 0.5) * 10, y, vx: (Math.random() - 0.5) * 40, vy: -Math.random() * 20, t: 0, dur: 0.45, r: 2 + Math.random() * 2 }); }
    confetti(x, y, n = 26) { const cs = [COL.tomato, COL.sun, COL.mint, COL.sky, COL.pink, COL.lime]; for (let i = 0; i < n; i++) this.fx.push({ kind: "conf", x, y, vx: (Math.random() - 0.5) * 160, vy: -80 - Math.random() * 120, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 20, t: 0, dur: 1.6, col: cs[i % cs.length] }); }
    stars(x, y) { for (let i = 0; i < 5; i++) { const a = (i / 5) * PI * 2; this.fx.push({ kind: "star", x, y, vx: Math.cos(a) * 40, vy: Math.sin(a) * 40 - 20, t: 0, dur: 0.7 }); } }
    step(dt) {
      this.time += dt; this.tl.step(dt);
      for (const m of this.men) m.step(dt);
      for (const p of this.props) p.step(dt);
      for (const f of this.fx) { f.t += dt; if (f.vx !== undefined) { f.x += f.vx * dt; f.y += f.vy * dt; if (f.kind === "conf") { f.vy += 260 * dt; f.vx *= 0.99; f.rot += f.vr * dt; } } }
      this.fx = this.fx.filter((f) => f.t < f.dur);
      this.shake *= 0.9;
    }
    draw(c) {
      if (this.shake > 0.3) c.translate((Math.random() - 0.5) * this.shake, (Math.random() - 0.5) * this.shake);
      if (this.night) { c.save(); c.fillStyle = "rgba(20,24,48,.82)"; c.fillRect(0, 0, this.W, H); c.fillStyle = "#fff8d0"; c.beginPath(); c.arc(this.W - 26, 22, 9, 0, PI * 2); c.fill(); c.restore(); }
      if (this.rain) { c.save(); c.strokeStyle = "rgba(77,141,255,.6)"; c.lineWidth = 1; for (let i = 0; i < 40; i++) { const x = (i * 37 + this.time * 30) % this.W, y = (i * 53 + this.time * 160) % H; c.beginPath(); c.moveTo(x, y); c.lineTo(x - 2, y + 5); c.stroke(); } c.restore(); }
      if (this.ground) { c.save(); c.strokeStyle = INK; c.globalAlpha = 0.5; c.lineWidth = 2; c.setLineDash([1, 6]); c.lineCap = "round"; c.beginPath(); c.moveTo(6, GROUND + 0.5); c.lineTo(this.W - 6, GROUND + 0.5); c.stroke(); c.restore(); }
      const layers = [...this.props.filter((p) => p.z < 1), ...this.men, ...this.props.filter((p) => p.z >= 1)];
      for (const o of layers) (o.render ? o.render(c) : o.draw(c));
      for (const f of this.fx) {
        const k = f.t / f.dur; c.save();
        if (f.kind === "text") { c.globalAlpha = k < 0.15 ? k / 0.15 : 1 - Math.max(0, (k - 0.7) / 0.3); c.fillStyle = f.col; c.font = `400 ${f.size}px "Bagel Fat One", sans-serif`; c.textAlign = "center"; c.fillText(f.txt, f.x, f.y - k * 10); }
        else if (f.kind === "puff") { c.globalAlpha = (1 - k) * 0.5; c.fillStyle = "#8a8378"; c.beginPath(); c.arc(f.x, f.y, f.r * (1 + k * 1.5), 0, PI * 2); c.fill(); }
        else if (f.kind === "conf") { c.globalAlpha = 1 - Math.max(0, (k - 0.7) / 0.3); c.translate(f.x, f.y); c.rotate(f.rot); c.fillStyle = f.col; c.fillRect(-2, -1, 4, 2.4); }
        else if (f.kind === "flash") { c.globalAlpha = (1 - k) * 0.85; c.fillStyle = "#fff"; c.fillRect(0, 0, this.W, H); }
        else if (f.kind === "star") { c.globalAlpha = 1 - k; c.translate(f.x, f.y); c.rotate(k * 4); c.fillStyle = COL.sun; c.strokeStyle = INK; c.lineWidth = 1; star(c, 3.2); c.fill(); c.stroke(); }
        c.restore();
      }
    }
  }
  function star(c, r) { c.beginPath(); for (let i = 0; i < 10; i++) { const a = (i / 10) * PI * 2 - PI / 2, rr = i % 2 ? r * 0.45 : r; c.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); } c.closePath(); }

  // ---------- a card's stage: cycles through all its scenes ----------
  function mount(canvas, scenes, { cap, dots, auto = true } = {}) {
    const ctx = canvas.getContext("2d");
    const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let idx = 0, world = null, scene = null, acc = 0, last = 0, visible = false, running = false, hold = 0, fade = 0, W = 220, scale = 1;
    const size = () => {
      const r = canvas.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
      canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
      scale = (r.height * dpr) / H; W = Math.max(200, (r.width * dpr) / scale);
    };
    let holdEnd = false;
    const custom = (sObj, { hold = false } = {}) => {   // one-off scene (e.g. Thirsty's death); optionally freeze on its last frame
      scene = sObj; holdEnd = hold; world = new World(W); scene.build(world, world.tl); fade = 1; hold_ = 0;
      if (cap) cap.textContent = scene.title;
      if (calm) { for (let t = 0; t < scene.dur; t += DT) world.step(DT); draw(); }
    };
    let hold_ = 0;
    const load = (i) => {
      holdEnd = false;
      idx = (i + scenes.length) % scenes.length; scene = scenes[idx];
      world = new World(W); scene.build(world, world.tl); fade = 0; hold = 0;
      if (cap) cap.textContent = `${idx + 1}/${scenes.length} · ${scene.title}`;
      if (dots) [...dots.children].forEach((d, j) => d.classList.toggle("on", j === idx));
      if (calm) { for (let t = 0; t < scene.dur * 0.62; t += DT) world.step(DT); draw(); }
    };
    function draw() {
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(scale, 0, 0, scale, 0, 0); ctx.globalAlpha = calm ? 1 : Math.min(1, fade);
      world.draw(ctx);
    }
    function frame(now) {
      if (!visible || document.hidden || calm) { running = false; return; }
      const dt = Math.min(0.05, (now - (last || now)) / 1000); last = now; acc += dt; fade += dt * 5;
      while (acc >= DT) { if (!(holdEnd && world.time >= scene.dur)) world.step(DT); acc -= DT; }
      if (world.time >= scene.dur && auto && !holdEnd) { hold += dt; if (hold > 0.5) load(scenes.indexOf(scene) >= 0 ? idx + 1 : idx); }
      if (holdEnd && world.time >= scene.dur) world.time = scene.dur;   // frozen until told otherwise
      draw(); requestAnimationFrame(frame);
    }
    const start = () => { if (!running && !calm) { running = true; last = 0; requestAnimationFrame(frame); } };
    if (dots) { dots.innerHTML = scenes.map((s, j) => `<button type="button" aria-label="Scene ${j + 1}: ${s.title}"></button>`).join(""); [...dots.children].forEach((b, j) => b.addEventListener("click", () => { load(j); start(); })); }
    canvas.addEventListener("click", () => { load(idx + 1); start(); });
    new IntersectionObserver((es) => { visible = es[0].isIntersecting; if (visible) start(); }, { threshold: 0.2 }).observe(canvas);
    new ResizeObserver(() => { size(); load(idx); }).observe(canvas);
    document.addEventListener("visibilitychange", () => start());
    size(); load(0);
    return { play(i) { load(i); start(); }, custom(sObj, o) { custom(sObj, o); start(); }, next() { load(idx + 1); start(); }, get world() { return world; } };
  }

  return { mount, Man, Prop, World, Timeline, E, COL, INK, SKIN, GROUND, star, clamp, lerp, PI };
})();
