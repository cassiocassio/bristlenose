/**
 * The keyline lab's spec: every handle, and the shipped CSS each one maps to.
 *
 * Colour-lab rule ("retune in the lab, then change both"): each handle is one
 * value in a shipped rule. `ruleEdits(SHIPPED)` is, declaration for
 * declaration, what `atoms/badge.css` and `molecules/threshold-review.css` say
 * today; `keylineLab/spec.test.ts` reads both files and fails when they part.
 * Change the CSS and SHIPPED together.
 *
 * Three surfaces carry the tentative keyline:
 *   quote    `.badge-proposed`                    every tentative tag (quote cards, Screens)
 *   row      `.badge.threshold-tag-tentative`     the review dialog's tentative rows
 *   counter  `.threshold-zone-counter--tentative` the review dialog's tentative counter
 *
 * Techniques. `dashed`, `dotted` and `solid` are the CSS border styles: the
 * browser decides dash length, and Chromium and WebKit decide differently,
 * most of all round a `border-radius`. `drawn` keeps the shipped 1px border as
 * a transparent edge (so nothing moves) and draws the line in a `::before`
 * masked by an SVG rounded rectangle, where dash, gap and cap are ours and both
 * engines draw the same thing.
 */

export type Technique = "dashed" | "dotted" | "drawn" | "solid";
export type Ink = "current" | "text" | "muted" | "accent" | "border";
export type Cap = "butt" | "round";
export type Surface = "quote" | "row" | "counter";

export interface Keyline {
  technique: Technique;
  /** Line width in CSS px (0.5 is one device pixel on a 2x screen). */
  width: number;
  /** Dash and gap along the edge, CSS px. `drawn` only. */
  dash: number;
  gap: number;
  /** Dash ends. `drawn` only; round with a 0 dash draws dots. */
  cap: Cap;
  ink: Ink;
  /** How much of the ink shows, 0–100 (100 is the ink itself; below it, mixed with transparent). */
  strength: number;
}

export interface LabSpec {
  quote: { line: Keyline; rest: number; trough: number; peak: number; hover: number };
  row: { linked: boolean; line: Keyline };
  counter: { linked: boolean; line: Keyline; trough: number; peak: number };
}

const SHIPPED_LINE: Keyline = {
  technique: "dashed",
  width: 1,
  dash: 3,
  gap: 3,
  cap: "butt",
  ink: "current",
  strength: 100,
};

/** Today's spec, as shipped (25 Nov 2026). The test pins it to the CSS files. */
export const SHIPPED: LabSpec = {
  quote: { line: SHIPPED_LINE, rest: 0.72, trough: 0.5, peak: 0.78, hover: 1 },
  row: { linked: true, line: SHIPPED_LINE },
  counter: { linked: true, line: SHIPPED_LINE, trough: 0.5, peak: 0.78 },
};

export const SELECTORS: Record<Surface, string> = {
  quote: ".badge-proposed",
  row: ".badge.threshold-tag-tentative",
  counter: ".threshold-zone-counter--tentative",
};

export const FILES = {
  badge: "bristlenose/theme/atoms/badge.css",
  review: "bristlenose/theme/molecules/threshold-review.css",
} as const;
export type ThemeFile = (typeof FILES)[keyof typeof FILES];

const FILE_OF: Record<Surface, ThemeFile> = { quote: FILES.badge, row: FILES.review, counter: FILES.review };

/** One change to the shipped theme: declarations on a rule, a keyframes rewrite, or a new rule. */
export type Edit =
  | { kind: "style"; file: ThemeFile; selector: string; decls: Record<string, string> }
  | { kind: "keyframes"; file: ThemeFile; name: string; frames: Array<[string, Record<string, string>]> }
  | { kind: "new"; file: ThemeFile; selector: string; after: string; decls: Record<string, string> };

export interface Env {
  /** `--bn-radius-sm` in px, read from the loaded theme (the SVG needs a number). */
  radius: number;
}

export const DEFAULT_ENV: Env = { radius: 3 };

/** The effective keyline of a surface: a linked surface follows the quote card's. */
export function lineOf(spec: LabSpec, surface: Surface): Keyline {
  if (surface === "row" && spec.row.linked) return spec.quote.line;
  if (surface === "counter" && spec.counter.linked) return spec.quote.line;
  return spec[surface].line;
}

/** A number as the theme writes one: no trailing zeros, at most two places. */
export function num(n: number): string {
  return String(Math.round(n * 100) / 100);
}

export function px(n: number): string {
  return `${num(n)}px`;
}

const INK_VAR: Record<Exclude<Ink, "current">, string> = {
  text: "--bn-colour-text",
  muted: "--bn-colour-muted",
  accent: "--bn-colour-accent",
  border: "--bn-colour-border",
};

export function inkColour(line: Keyline): string {
  const base = line.ink === "current" ? "currentColor" : `var(${INK_VAR[line.ink]})`;
  return line.strength >= 100 ? base : `color-mix(in srgb, ${base} ${num(line.strength)}%, transparent)`;
}

/** The SVG mask for `drawn`: a rounded rectangle on the edge, stroked twice the width so the
 *  half inside the box is the line (the half outside is clipped by the box's own rounding). */
export function maskUrl(line: Keyline, env: Env): string {
  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg'><rect width='100%' height='100%' rx='${num(env.radius)}' ` +
    `fill='none' stroke='black' stroke-width='${num(line.width * 2)}' ` +
    `stroke-dasharray='${num(line.dash)} ${num(line.gap)}' stroke-linecap='${line.cap}'/></svg>`;
  const escaped = svg.replace(/%/g, "%25").replace(/</g, "%3C").replace(/>/g, "%3E").replace(/#/g, "%23");
  return `url("data:image/svg+xml,${escaped}")`;
}

function lineEdits(surface: Surface, line: Keyline, env: Env): Edit[] {
  const selector = SELECTORS[surface];
  const file = FILE_OF[surface];
  if (line.technique !== "drawn") {
    return [{ kind: "style", file, selector, decls: { border: `${px(line.width)} ${line.technique} ${inkColour(line)}` } }];
  }
  // Keep the shipped 1px edge, so the tag is the size it is today, and draw over it.
  const decls: Record<string, string> = { border: "1px solid transparent" };
  if (surface !== "quote") decls.position = "relative"; // .badge-proposed already has it
  const mask = `${maskUrl(line, env)} 0 0 / 100% 100% no-repeat`;
  return [
    { kind: "style", file, selector, decls },
    {
      kind: "new",
      file,
      selector: `${selector}::before`,
      after: selector,
      decls: {
        content: '""',
        position: "absolute",
        inset: "-1px",
        "border-radius": "inherit",
        "background-color": inkColour(line),
        "pointer-events": "none",
        "-webkit-mask": mask,
        mask,
      },
    },
  ];
}

const DEPTH = "var(--bn-proposed-pulse-depth)";

/** `calc(rest - swing * depth)`, written the way badge.css writes it. */
function swing(rest: number, to: number): string {
  const d = to - rest;
  return `calc(${num(rest)} ${d < 0 ? "-" : "+"} ${num(Math.abs(d))} * ${DEPTH})`;
}

/** Every change the spec makes to the shipped theme, in file order. */
export function ruleEdits(spec: LabSpec, env: Env = DEFAULT_ENV): Edit[] {
  const q = spec.quote;
  const quoteLine = lineEdits("quote", q.line, env);
  const [quoteBase, ...quoteNew] = quoteLine;
  return [
    // atoms/badge.css
    {
      kind: "keyframes",
      file: FILES.badge,
      name: "bn-proposed-pulse",
      frames: [
        ["0%", { opacity: num(spec.counter.trough) }],
        ["50%", { opacity: num(spec.counter.peak) }],
        ["100%", { opacity: num(spec.counter.trough) }],
      ],
    },
    {
      kind: "keyframes",
      file: FILES.badge,
      name: "bn-proposed-breathe",
      frames: [
        ["0%", { opacity: swing(q.rest, q.trough) }],
        ["50%", { opacity: swing(q.rest, q.peak) }],
        ["100%", { opacity: swing(q.rest, q.trough) }],
      ],
    },
    quoteBase.kind === "style" ? { ...quoteBase, decls: { opacity: num(q.rest), ...quoteBase.decls } } : quoteBase,
    ...quoteNew,
    { kind: "style", file: FILES.badge, selector: ".badge-proposed:hover", decls: { opacity: `${num(q.hover)} !important` } },
    // molecules/threshold-review.css
    ...lineEdits("counter", lineOf(spec, "counter"), env),
    ...lineEdits("row", lineOf(spec, "row"), env),
  ];
}

function block(selector: string, decls: Record<string, string>, indent = ""): string {
  const body = Object.entries(decls).map(([p, v]) => `${indent}    ${p}: ${v};`).join("\n");
  return `${indent}${selector} {\n${body}\n${indent}}`;
}

/** The edits as CSS to drop into the two files, grouped by file. */
export function dropInCss(spec: LabSpec, env: Env = DEFAULT_ENV): string {
  const edits = ruleEdits(spec, env);
  const out: string[] = [];
  for (const file of Object.values(FILES)) {
    out.push(`/* ── ${file.replace("bristlenose/theme/", "")} ── */`);
    for (const e of edits.filter((x) => x.file === file)) {
      if (e.kind === "style") {
        out.push(`/* in the shipped rule, these lines (its other lines stay) */\n${block(e.selector, e.decls)}`);
      } else if (e.kind === "new") {
        out.push(`/* new rule, after ${e.after} */\n${block(e.selector, e.decls)}`);
      } else {
        const frames = e.frames.map(([k, d]) => block(k, d, "    ")).join("\n");
        out.push(`/* the whole keyframe */\n@keyframes ${e.name} {\n${frames}\n}`);
      }
    }
  }
  return out.join("\n\n");
}

// ── URL form ────────────────────────────────────────────────────────

const TECHNIQUES: Technique[] = ["dashed", "dotted", "drawn", "solid"];
const INKS: Ink[] = ["current", "text", "muted", "accent", "border"];
const CAPS: Cap[] = ["butt", "round"];

function clamp(v: unknown, lo: number, hi: number, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : fallback;
}

function pick<T extends string>(v: unknown, allowed: T[], fallback: T): T {
  return allowed.includes(v as T) ? (v as T) : fallback;
}

function readLine(v: unknown, d: Keyline): Keyline {
  const o = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  return {
    technique: pick(o.technique, TECHNIQUES, d.technique),
    width: clamp(o.width, 0.25, 3, d.width),
    dash: clamp(o.dash, 0, 12, d.dash),
    gap: clamp(o.gap, 0.5, 12, d.gap),
    cap: pick(o.cap, CAPS, d.cap),
    ink: pick(o.ink, INKS, d.ink),
    strength: clamp(o.strength, 0, 100, d.strength),
  };
}

/** A spec from the `k` URL parameter; anything missing or out of range is the shipped value. */
export function parseSpec(raw: string | null): LabSpec {
  let o: Record<string, Record<string, unknown>> = {};
  try {
    const v: unknown = raw ? JSON.parse(raw) : {};
    if (v && typeof v === "object") o = v as typeof o;
  } catch {
    // a hand-edited URL: fall back to the shipped spec
  }
  const q = o.quote ?? {};
  const r = o.row ?? {};
  const c = o.counter ?? {};
  const s = SHIPPED;
  return {
    quote: {
      line: readLine(q.line, s.quote.line),
      rest: clamp(q.rest, 0, 1, s.quote.rest),
      trough: clamp(q.trough, 0, 1, s.quote.trough),
      peak: clamp(q.peak, 0, 1, s.quote.peak),
      hover: clamp(q.hover, 0, 1, s.quote.hover),
    },
    row: { linked: r.linked !== false, line: readLine(r.line, s.row.line) },
    counter: {
      linked: c.linked !== false,
      line: readLine(c.line, s.counter.line),
      trough: clamp(c.trough, 0, 1, s.counter.trough),
      peak: clamp(c.peak, 0, 1, s.counter.peak),
    },
  };
}

export function isShipped(spec: LabSpec): boolean {
  return JSON.stringify(ruleEdits(spec)) === JSON.stringify(ruleEdits(SHIPPED));
}
