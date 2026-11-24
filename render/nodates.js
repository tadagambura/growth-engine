// Videos get reused, so recorded app screens carry no dates. Injected into the page while recording.
// Changes only text-node contents, so the app can keep re-rendering underneath.
(() => {
  const WD = "(?:Mon|Tues?|Wed(?:nes)?|Thu(?:rs)?|Fri|Sat(?:ur)?|Sun)(?:day)?";
  const MON = "(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\\b";
  const DATE = `(?:\\b${WD},?\\s+)?(?:\\b\\d{1,2}(?:st|nd|rd|th)?\\s+${MON}(?:,?\\s+20\\d\\d)?|\\b${MON}\\s+(?:20\\d\\d|\\d{1,2}(?:st|nd|rd|th)?\\b(?:,?\\s+20\\d\\d)?)|\\b(?:0?[1-9]|[12]\\d|3[01])/(?:0?[1-9]|1[0-2])/(?:\\d{4}|\\d\\d)\\b|\\b20\\d\\d-\\d\\d-\\d\\d\\b)`;
  const RULES = [`\\s*·?\\s*\\bchecked\\s+${DATE}`, `\\s*\\(\\s*${DATE}\\s*\\)`, `${DATE},\\s*`, DATE].map((r) => new RegExp(r, "g"));
  const scrub = (s) => {
    if (s.trim() === "1 January") return "New Year";                           // a quick-pick button: keep it labelled
    const out = RULES.reduce((t, r) => t.replace(r, ""), s);
    return out === s ? s : out.replace(/ {2,}/g, " ").trim() || " ";
  };
  globalThis.__scrubDates = scrub;
  if (typeof document === "undefined") return;
  const texts = (el) => { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), out = []; while (w.nextNode()) out.push(w.currentNode); return out; };
  const sweep = () => {
    for (const el of document.querySelectorAll("body *:not(script):not(style)")) {
      const nodes = [...el.childNodes].filter((n) => n.nodeType === 3);
      if (!nodes.length) continue;
      const whole = nodes.map((n) => n.data).join(""), clean = scrub(whole);      // a date can be split across nodes
      if (clean !== whole) nodes.forEach((n, i) => { const v = i ? "" : clean; if (n.data !== v) n.data = v; });
    }
    // calendar strips: a day labelled with a date ("Tuesday 24 November: 1 of 1 done") shows its day number
    for (const el of document.querySelectorAll("[aria-label]")) {
      const label = el.getAttribute("aria-label");
      if (scrub(label) !== label) for (const n of texts(el)) if (/^\s*\d{1,2}\s*$/.test(n.data)) n.data = " ";
    }
  };
  new MutationObserver(sweep).observe(document, { subtree: true, childList: true, characterData: true });
})();
