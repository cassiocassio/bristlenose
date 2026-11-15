// Nudge a whole palette coherently. One implementation, used by the browser lab (live) and by
// workbench.py (via node) when an iteration is saved or promoted, so what you see is what ships.
//
// A palette table is { "--bn-token": { light, dark } }. A KNOB moves a whole family of tokens
// together in OKLCH, RELATIVE to the base: hue shifts are added, chroma is scaled, lightness is
// offset. Because every token moves by the same relation, the base's own internal relationships
// (card one step off the page, border a step off the card, hover tinted toward the accent) survive.
// A contrast guard then nudges text-bearing tokens just far enough to keep their targets.

const D2R = Math.PI / 180;

// ── colour maths: sRGB <-> OKLab <-> OKLCH, with gamut clipping by chroma reduction ──
const lin = (v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const gam = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);

export function hexToLch(hex) {
  const n = parseInt(hex.slice(1), 16);
  const r = lin(((n >> 16) & 255) / 255), g = lin(((n >> 8) & 255) / 255), b = lin((n & 255) / 255);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  return { L, C: Math.hypot(A, B), h: ((Math.atan2(B, A) / D2R) + 360) % 360 };
}

function lchToRgb({ L, C, h }) {
  const A = C * Math.cos(h * D2R), B = C * Math.sin(h * D2R);
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

export function lchToHex(c) {
  let { L, C, h } = c;
  L = Math.min(1, Math.max(0, L)); C = Math.max(0, C);
  let rgb = lchToRgb({ L, C, h });
  for (let i = 0; i < 40 && rgb.some((v) => v < -0.0005 || v > 1.0005); i++) rgb = lchToRgb({ L, C: (C *= 0.93), h });
  return "#" + rgb.map((v) => Math.round(255 * gam(Math.min(1, Math.max(0, v)))).toString(16).padStart(2, "0")).join("");
}

export const lum = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * lin(((n >> 16) & 255) / 255) + 0.7152 * lin(((n >> 8) & 255) / 255) + 0.0722 * lin((n & 255) / 255);
};
export const contrast = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
// APCA-W3 0.0.98G lightness contrast (Lc): perceptual, polarity-aware, calibrated for reading text.
// Informational: WCAG 3 is a draft. Rough reading targets: 90 body at small sizes, 75 body, 60 secondary, 45 large/meta.
const yAPCA = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  const y = 0.2126729 * (((n >> 16) & 255) / 255) ** 2.4 + 0.7151522 * (((n >> 8) & 255) / 255) ** 2.4 + 0.072175 * ((n & 255) / 255) ** 2.4;
  return y < 0.022 ? y + (0.022 - y) ** 1.414 : y;
};
export function apca(fg, bg) {
  const yt = yAPCA(fg), yb = yAPCA(bg);
  if (Math.abs(yb - yt) < 0.0005) return 0;
  if (yb > yt) { const s = (yb ** 0.56 - yt ** 0.57) * 1.14; return s < 0.1 ? 0 : (s - 0.027) * 100; }
  const s = (yb ** 0.65 - yt ** 0.62) * 1.14; return s > -0.1 ? 0 : -(s + 0.027) * 100;
}
export const isHex = (v) => /^#[0-9a-f]{6}$/i.test(v);

// Apply fn(lch) -> lch to every colour inside a CSS value (hex or rgba(); alpha kept).
const COLOUR = /#[0-9a-fA-F]{6}\b|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)/g;
export function mapValue(value, fn) {
  return value.replace(COLOUR, (m) => {
    if (m[0] === "#") return lchToHex(fn(hexToLch(m)));
    const [r, g, b, a] = m.match(/[\d.]+/g).map(Number);
    const hex = lchToHex(fn(hexToLch("#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join(""))));
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}${a === undefined ? "" : ", " + a})`;
  });
}

// A single colour value -> {hex, alpha}, or null for compound values (shadows, rings).
export function parseColour(v) {
  v = v.trim();
  if (isHex(v)) return { hex: v.toLowerCase(), alpha: null };
  const m = v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (!m) return null;
  return { hex: "#" + [m[1], m[2], m[3]].map((x) => (+x).toString(16).padStart(2, "0")).join(""), alpha: m[4] === undefined ? null : +m[4] };
}
export function formatColour(hex, alpha) {
  if (alpha === null || alpha === undefined) return hex;
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// ── the families ──
const t = (...names) => names.map((n) => "--bn-" + n);
export const FAMILIES = {
  paper: t("colour-bg", "colour-quote-bg", "colour-paper", "colour-sheet", "colour-inspector-bg", "colour-badge-bg",
    "colour-badge-bg-paper", "colour-user-tag-bg", "colour-hover", "group-none", "bar-none", "selection-bg-inactive",
    "nav-selection-bg", "colour-border", "colour-border-hover", "colour-icon-idle", "minimap-quote",
    "minimap-heading", "colour-starred", "coverage-omitted", "selection-border-inactive"),
  ink: t("colour-text", "colour-muted", "colour-badge-text", "colour-user-tag-text"),
  accent: t("colour-accent", "selection-border", "colour-suggestion", "selection-bg", "colour-suggestion-bg",
    "glow-colour", "glow-colour-strong", "minimap-viewport-bg", "minimap-viewport-border", "focus-ring", "coverage-report"),
  negative: t("colour-negative", "crop-handle-colour", "crop-handle-hover"),
  positive: t("colour-positive", "colour-active-bg"),
  caution: t("colour-warning", "colour-highlight", "colour-crop-bg", "colour-cited-bg", "coverage-moderator"),
};
// Surfaces whose distance from the page ("how far a card sits off the page") the step knob scales.
const STEPPED = t("colour-quote-bg", "colour-paper", "colour-sheet", "colour-inspector-bg", "colour-badge-bg",
  "colour-badge-bg-paper", "colour-user-tag-bg", "colour-hover", "nav-selection-bg", "selection-bg-inactive", "group-none");

// ── the knobs: name -> [label, min, max, step, neutral, what it does] ──
export const KNOBS = {
  paperHue:    ["Paper hue", -180, 180, 1, 0, "degrees added to every neutral: surfaces, borders, badges, hover"],
  paperChroma: ["Paper chroma", 0, 2.5, 0.05, 1, "multiplier on the neutrals' colour: 0 = grey, 1 = Edo as shipped"],
  paperLift:   ["Ground lightness", -0.08, 0.08, 0.005, 0, "lightness added to the page and every neutral with it"],
  surfaceStep: ["Surface steps", 0.3, 2.5, 0.05, 1, "how far cards and chrome sit off the page (scales every step)"],
  inkHue:      ["Ink hue", -40, 40, 1, 0, "degrees added to body, muted and badge text"],
  inkChroma:   ["Ink chroma", 0, 2.5, 0.05, 1, "multiplier on the ink's colour"],
  accentHue:   ["Accent hue", -30, 30, 1, 0, "degrees added to the accent and everything tinted from it"],
  accentChroma:["Accent chroma", 0.3, 1.8, 0.05, 1, "multiplier on the accent's vividness"],
  accentLight: ["Accent lightness", -0.08, 0.08, 0.005, 0, "lightness added to the accent family"],
  semChroma:   ["Signal chroma", 0.3, 1.6, 0.05, 1, "multiplier on negative, positive and caution"],
};
const MODES = ["light", "dark"];
// Every knob is per-appearance: knobs.light.paperHue / knobs.dark.paperHue.
export const neutralKnobs = () => ({ light: Object.fromEntries(Object.entries(KNOBS).map(([k, v]) => [k, v[4]])),
                                      dark: Object.fromEntries(Object.entries(KNOBS).map(([k, v]) => [k, v[4]])) });

const GUARD = [ // [fg, bg, target]: what the app puts text on
  ["colour-text", "colour-bg", 4.5], ["colour-text", "colour-quote-bg", 4.5], ["colour-text", "colour-paper", 4.5],
  ["colour-muted", "colour-bg", 4.5], ["colour-muted", "colour-quote-bg", 4.5], ["colour-muted", "colour-inspector-bg", 4.5],
  ["colour-accent", "colour-bg", 4.5], ["colour-accent", "colour-quote-bg", 4.5], ["colour-accent", "nav-selection-bg", 4.5],
  ["colour-badge-text", "colour-badge-bg", 4.5], ["colour-negative", "colour-bg", 4.5], ["colour-positive", "colour-active-bg", 3.0],
].map(([f, b, c]) => ["--bn-" + f, "--bn-" + b, c]);
export const PAIRS = GUARD;

export function applyKnobs(base, knobs, overrides = {}) {
  const out = JSON.parse(JSON.stringify(base));
  const notes = [];
  for (const mode of MODES) {
    const k = { ...Object.fromEntries(Object.entries(KNOBS).map(([n, v]) => [n, v[4]])), ...(knobs?.[mode] ?? {}) };
    const bgL = hexToLch(base["--bn-colour-bg"][mode]).L;
    const move = (names, fn) => names.forEach((n) => { if (out[n]) out[n][mode] = mapValue(out[n][mode], fn); });
    move(FAMILIES.paper, (c) => ({ L: c.L + k.paperLift, C: c.C * k.paperChroma, h: c.h + k.paperHue }));
    move(STEPPED, (c) => ({ ...c, L: bgL + k.paperLift + (c.L - k.paperLift - bgL) * k.surfaceStep }));
    move(FAMILIES.ink, (c) => ({ ...c, C: c.C * k.inkChroma, h: c.h + k.inkHue }));
    move(FAMILIES.accent, (c) => ({ L: c.L + k.accentLight, C: c.C * k.accentChroma, h: c.h + k.accentHue }));
    move([...FAMILIES.negative, ...FAMILIES.positive, ...FAMILIES.caution], (c) => ({ ...c, C: c.C * k.semChroma }));
    // contrast guard: move the foreground's lightness away from its ground until the target holds
    for (const [fg, bg, target] of GUARD) {
      const f = out[fg]?.[mode], b = out[bg]?.[mode];
      if (!isHex(f) || !isHex(b) || contrast(f, b) >= target) continue;
      const c = hexToLch(f), dir = hexToLch(b).L > 0.6 ? -1 : 1;
      let cur = f;
      for (let i = 0; i < 80 && contrast(cur, b) < target; i++) cur = lchToHex({ ...c, L: (c.L += dir * 0.005) });
      notes.push(`${fg.slice(5)} on ${bg.slice(5)} (${mode}): ${f} -> ${cur} to hold ${target}:1`);
      out[fg][mode] = cur;
    }
    // single-token overrides win over the families and the guard: a deliberate choice is not second-guessed
    // (the lab's contrast table still flags it if it breaks a text pair)
    for (const [tok, o] of Object.entries(overrides ?? {})) if (out[tok] && o[mode] !== undefined) out[tok][mode] = o[mode];
  }
  return { table: out, notes };
}

export function toCss(table, key) {
  const sel = `[data-color-theme="${key}"]`;
  const names = Object.keys(table);
  const ld = (c) => {
    if (c.light === c.dark) return c.light;
    const mm = c.light.startsWith("0 0 0 ") && c.dark.startsWith("0 0 0 ") ? [c.light.split(" rgba"), c.dark.split(" rgba")] : null;
    if (mm && mm[0][0] === mm[1][0]) return `${mm[0][0]} light-dark(rgba${mm[0][1]}, rgba${mm[1][1]})`;
    return `light-dark(${c.light}, ${c.dark})`;
  };
  return `${sel} {\n${names.map((n) => `  ${n}: ${ld(table[n])};`).join("\n")}\n}\n`;
}

export function matrix(table) {
  return PAIRS.map(([fg, bg, target]) => {
    const row = { label: `${fg.slice(5)} on ${bg.slice(5)}`, target };
    for (const m of MODES) {
      const ok = isHex(table[fg][m]) && isHex(table[bg][m]);
      row[m] = ok ? contrast(table[fg][m], table[bg][m]) : null;
      row[m + "Lc"] = ok ? apca(table[fg][m], table[bg][m]) : null;
    }
    return row;
  });
}

// ── node entry: `node knobs.mjs base.json knobs.json` -> {table, notes} on stdout ──
if (typeof process !== "undefined" && process.argv?.[1]?.endsWith("knobs.mjs")) {
  const fs = await import("node:fs");
  const [base, kn, ov] = process.argv.slice(2).map((p) => JSON.parse(fs.readFileSync(p, "utf8")));
  process.stdout.write(JSON.stringify(applyKnobs(base, kn, ov ?? {})));
}
