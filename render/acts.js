// Kaos's acts. One function per id in configs/acts.json: (w, tl, m, t, dur, ctx) schedules the movement on
// the world's timeline starting at second t for dur seconds. Uses only FluidStick's own helpers, so Kaos
// moves exactly like he does on the website. ctx = { cx: stage centre x, state: {} shared between acts }.
(() => {
  const { E, COL, INK } = FS;
  const lerp = (a, b, k) => a + (b - a) * k;

  // the phone prop Kaos pulls out in tap_phone; any act that needs the hand puts it away first
  const drawPhone = (c) => {
    c.fillStyle = INK; c.strokeStyle = INK; c.lineWidth = 1.2; c.beginPath(); c.roundRect(-4.2, -7.5, 8.4, 15, 1.8); c.fill();
    c.fillStyle = COL.lime; c.beginPath(); c.roundRect(-3.3, -6.5, 6.6, 12.5, 1); c.fill();
    c.fillStyle = INK; c.beginPath(); c.arc(0, 5.2, 0.6, 0, Math.PI * 2); c.fill();
  };
  const stowPhone = (ctx, tl, t) => { if (ctx.state.phone) tl.at(t, () => { const p = ctx.state.phone; p.alpha = 0; p.held = null; p.state = "static"; }); };
  const handFree = (m, tl, t, k) => m.relax(tl, t, k);
  const head = (m) => m.pose.head;
  const wiggle = (tl, t, dur, fn, every = 0.5) => { for (let k = 0, x = t; x < t + dur - 0.05; k++, x += every) fn(k, x); };

  const ACTS = {
    talk(w, tl, m, t, d, ctx) {
      m.face_(tl, t, "neutral"); stowPhone(ctx, tl, t);
      m.to(tl, t, 0.3, { look: [ctx.cx + 60, 52], lean: 0.04 });
      wiggle(tl, t + 0.15, d, (k, x) => {
        const up = k % 2 === 0;
        m.reach(tl, x, 0.4, "r", [ctx.cx + (up ? 16 : 11), up ? 56 : 66], -4);
        if (k % 3 === 2) m.reach(tl, x + 0.1, 0.4, "l", [ctx.cx - 14, 62], -4);
      }, 0.9);
      handFree(m, tl, t + d, "r"); handFree(m, tl, t + d, "l");
    },
    shock(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "shock");
      m.to(tl, t, 0.12, { lean: -0.3, crouch: -3 }, E.out); m.to(tl, t + 0.12, 0.4, { lean: -0.12, crouch: 0 });
      m.reach(tl, t, 0.2, "l", [ctx.cx - 15, 50], 6, E.back); m.reach(tl, t, 0.2, "r", [ctx.cx + 15, 50], 6, E.back);
      m.relax(tl, t + Math.min(d, 1.2), "l"); m.relax(tl, t + Math.min(d, 1.2), "r");
      m.face_(tl, t + Math.min(d, 1.2), "neutral");
    },
    panic(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "ohno"); tl.at(t, () => { m.sweat = 1; });
      wiggle(tl, t, d, (k, x) => {
        const s = k % 2 ? 1 : -1;
        m.to(tl, x, 0.22, { rx: ctx.cx + s * 7, lean: 0.12 * s }, E.io);
        m.reach(tl, x, 0.2, "l", [ctx.cx - 18 + s * 6, k % 2 ? 40 : 70], -6); m.reach(tl, x, 0.2, "r", [ctx.cx + 18 + s * 6, k % 2 ? 70 : 40], -6);
      }, 0.25);
      m.to(tl, t + d, 0.2, { rx: ctx.cx, lean: 0 }); handFree(m, tl, t + d, "l"); handFree(m, tl, t + d, "r");
      tl.at(t + d, () => { m.sweat = 0; }); m.face_(tl, t + d, "neutral");
    },
    think(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "huh");
      const h = head(m); m.reach(tl, t, 0.4, "r", [h.x + 3, h.y + 9], -4);
      m.to(tl, t, 0.4, { look: [ctx.cx + 20, 8], tilt: 0.1 });
      tl.at(t + 0.5, () => w.text("...", h.x + 12, h.y - 16, Math.max(0.8, d - 0.5), INK, 12));
      m.to(tl, t + d, 0.25, { tilt: 0 }); handFree(m, tl, t + d, "r"); m.face_(tl, t + d, "neutral");
    },
    walk_in(w, tl, m, t, d, ctx) {
      m.face_(tl, t, "happy"); m.walk(tl, t, Math.min(d, 1.6), ctx.cx);
      m.face_(tl, t + Math.min(d, 1.6), "neutral");
    },
    tap_phone(w, tl, m, t, d, ctx) {
      m.face_(tl, t, "neutral");
      if (!ctx.state.phone) { ctx.state.phone = w.prop(drawPhone, { z: 2, x: ctx.cx + 12, y: 60 }); ctx.state.phone.alpha = 0; }
      const ph = ctx.state.phone; tl.at(t, () => { ph.alpha = 1; ph.attach(m, "r", 0, -2, 0); });
      m.carry(tl, t, "r", 11, -42);
      m.to(tl, t + 0.1, 0.4, { look: [ctx.cx + 12, 62], lean: 0.08 });
      wiggle(tl, t + 0.5, d - 0.5, (k, x) => { m.reach(tl, x, 0.2, "l", [ctx.cx + 13, k % 2 ? 56 : 52], -3); }, 0.35);
      m.face_(tl, t + Math.min(d, 1.0), "happy");
    },
    present(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "happy");
      m.reach(tl, t, 0.5, "r", [ctx.cx + 38, 34], -12, E.back); m.to(tl, t, 0.5, { look: [ctx.cx + 80, 20], lean: 0.1 });
      m.to(tl, t + d - 0.3, 0.3, { lean: 0 }); handFree(m, tl, t + d, "r");
    },
    point(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); tl.at(t, () => { m.grip.r = "point"; });
      m.reach(tl, t, 0.35, "r", [ctx.cx + 34, 44], -8, E.back); m.to(tl, t, 0.35, { look: [ctx.cx + 70, 24], lean: 0.08 });
      wiggle(tl, t + 0.4, d - 0.4, (k, x) => m.reach(tl, x, 0.25, "r", [ctx.cx + 34 + (k % 2 ? 3 : -2), 44 + (k % 2 ? 2 : -2)], -2), 0.5);
      m.to(tl, t + d - 0.2, 0.2, { lean: 0 }); handFree(m, tl, t + d, "r");
    },
    celebrate(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "happy");
      m.reach(tl, t, 0.25, "l", [ctx.cx - 12, 30], 6, E.back); m.reach(tl, t + 0.05, 0.25, "r", [ctx.cx + 12, 30], 6, E.back);
      m.hop(tl, t + 0.05, 12, 0.45); tl.at(t + 0.3, () => w.confetti(ctx.cx, 60));
      if (d > 1.6) m.hop(tl, t + 0.95, 9, 0.4);
      m.relax(tl, t + Math.min(d, 1.8), "l"); m.relax(tl, t + Math.min(d, 1.8), "r");
    },
    facepalm(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "ohno");
      const h = head(m); m.reach(tl, t, 0.25, "r", [h.x + 1, h.y + 2], -6, E.back);
      m.to(tl, t, 0.25, { tilt: -0.12, crouch: 2 });
      wiggle(tl, t + 0.4, d - 0.4, (k, x) => m.to(tl, x, 0.25, { tilt: k % 2 ? -0.12 : -0.04 }), 0.3);
      m.to(tl, t + d, 0.25, { tilt: 0, crouch: 0 }); handFree(m, tl, t + d, "r"); m.face_(tl, t + d, "neutral");
    },
    shrug(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "huh");
      m.reach(tl, t, 0.3, "l", [ctx.cx - 20, 60], -6); m.reach(tl, t, 0.3, "r", [ctx.cx + 20, 60], -6);
      m.to(tl, t, 0.3, { crouch: -2, tilt: 0.06 }); m.to(tl, t + d - 0.3, 0.3, { crouch: 0, tilt: 0 });
      handFree(m, tl, t + d, "l"); handFree(m, tl, t + d, "r"); m.face_(tl, t + d, "neutral");
    },
    wave(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "happy");
      wiggle(tl, t, d, (k, x) => m.reach(tl, x, 0.22, "r", [ctx.cx + (k % 2 ? 22 : 12), 34], -4), 0.3);
      m.to(tl, t, 0.3, { look: [ctx.cx + 60, 50] });
    },
    sigh(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "sleepy");
      m.to(tl, t, 0.5, { crouch: 3, lean: -0.05 }); m.to(tl, t + 0.6, 0.5, { crouch: 0, lean: 0 }); m.face_(tl, t + 0.9, "happy");
      tl.at(t + 0.2, () => w.text("phew", head(m).x + 12, head(m).y - 14, 0.9, INK, 10));
    },
    lean_in(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "huh");
      m.to(tl, t, 0.4, { lean: 0.28, look: [ctx.cx + 70, 54] }); m.reach(tl, t + 0.2, 0.3, "r", [ctx.cx + 14, 54], -4);
      m.to(tl, t + d - 0.3, 0.3, { lean: 0 }); handFree(m, tl, t + d, "r"); m.face_(tl, t + d, "neutral");
    },
    nod(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "happy");
      wiggle(tl, t, d, (k, x) => m.to(tl, x, 0.2, { tilt: k % 2 ? 0.02 : 0.12, crouch: k % 2 ? 0 : 1.5 }), 0.4);
      m.to(tl, t + d, 0.2, { tilt: 0, crouch: 0 });
    },
    dance(w, tl, m, t, d, ctx) {
      stowPhone(ctx, tl, t); m.face_(tl, t, "happy");
      wiggle(tl, t, d, (k, x) => {
        m.hop(tl, x, 6, 0.3); m.reach(tl, x, 0.25, "l", [ctx.cx - 14, k % 2 ? 40 : 62], -4); m.reach(tl, x, 0.25, "r", [ctx.cx + 14, k % 2 ? 62 : 40], -4);
      }, 0.7);
      handFree(m, tl, t + d, "l"); handFree(m, tl, t + d, "r");
    },
  };
  window.KAOS_ACTS = ACTS;
})();
