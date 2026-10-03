/**
 * badgeStyle — a badge's resolved look, measured from the real component, for
 * the Mac app to paint natively (docs/design-search.md §7a).
 *
 * The rule: a badge drawn natively in the search menu or a token chip must be
 * indistinguishable from the same badge on a quote card. So the SPA renders a
 * hidden probe of the real `Badge` / `PersonBadge`, reads what the browser
 * resolved, and sends the values; Swift holds no palette copy (a hex table in
 * Swift would be a second source that drifts — the Welcome screen's sentiment
 * chips are that copy).
 *
 * Colours: the theme writes tag colours as `oklch(...)` and WebKit keeps them
 * as oklch in computed style, so the probe does not hand Swift a CSS string to
 * parse. It paints each colour into a display-P3 canvas and sends the
 * components: SwiftUI's `Color(.displayP3, red:green:blue:opacity:)` takes them
 * as they are, and P3 holds everything sRGB does.
 *
 * Two halves: `readBadgeStyle` is pure (a style declaration in, a style out) so
 * it is tested with fabricated values; `probeBadgeStyles` renders and measures,
 * which only a real browser engine can do — jsdom has no layout and no canvas.
 */

import { createElement, type ReactElement } from "react";
import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";

import { Badge } from "../components/Badge";
import { PersonBadge } from "../components/PersonBadge";
import { getTagBg } from "./colours";
import { fold } from "./searchMatch";
import type { TagResponse } from "./types";

/** A colour in the display-P3 space, each component 0…1. */
export interface P3Colour {
  r: number;
  g: number;
  b: number;
  a: number;
}

export interface BadgeStyle {
  /** Null when the badge has no fill (transparent). */
  bg: P3Colour | null;
  fg: P3Colour;
  border: { colour: P3Colour; widthPx: number } | null;
  /** "mono" when the badge uses the theme's monospace stack. */
  fontFamily: "mono" | "body";
  sizePx: number;
  weight: number;
  padX: number;
  padY: number;
  radius: number;
}

/** A person badge has two halves: the code, and the name when it is shown. */
export interface PersonBadgeStyle {
  code: BadgeStyle;
  name: BadgeStyle | null;
}

export interface BadgeStyles {
  /** By folded tag name. */
  tags: Record<string, BadgeStyle>;
  /** By speaker code. */
  people: Record<string, PersonBadgeStyle>;
}

/** The parts of a computed style the reader needs (a `CSSStyleDeclaration`
 *  satisfies it; tests pass a plain object). */
export type StyleSource = Pick<
  CSSStyleDeclaration,
  | "backgroundColor"
  | "color"
  | "borderTopWidth"
  | "borderTopStyle"
  | "borderTopColor"
  | "fontFamily"
  | "fontSize"
  | "fontWeight"
  | "paddingLeft"
  | "paddingTop"
  | "borderTopLeftRadius"
>;

export interface ReadContext {
  /** CSS colour → display-P3 components, or null if it cannot be resolved. */
  toP3: (css: string) => P3Colour | null;
  /** The resolved value of `--bn-font-mono`, to recognise the mono stack. */
  monoFamily: string;
}

const px = (v: string): number => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
};

const TRANSPARENT = /^(transparent|rgba\(0,\s*0,\s*0,\s*0\))$/i;

function normaliseFamily(f: string): string {
  return f.replace(/["']/g, "").replace(/\s*,\s*/g, ",").trim().toLowerCase();
}

/** A badge's style from what the browser resolved for it. */
export function readBadgeStyle(cs: StyleSource, ctx: ReadContext): BadgeStyle {
  const fg = ctx.toP3(cs.color) ?? { r: 0, g: 0, b: 0, a: 1 };
  const bg = TRANSPARENT.test(cs.backgroundColor.trim()) ? null : ctx.toP3(cs.backgroundColor);
  const borderWidth = px(cs.borderTopWidth);
  const borderColour =
    borderWidth > 0 && cs.borderTopStyle !== "none" && cs.borderTopStyle !== "hidden"
      ? ctx.toP3(cs.borderTopColor)
      : null;
  const family = normaliseFamily(cs.fontFamily);
  const mono = normaliseFamily(ctx.monoFamily);
  return {
    bg: bg && bg.a > 0 ? bg : null,
    fg,
    border: borderColour && borderColour.a > 0 ? { colour: borderColour, widthPx: borderWidth } : null,
    fontFamily: mono && family === mono ? "mono" : "body",
    sizePx: px(cs.fontSize),
    weight: Math.round(px(cs.fontWeight)) || 400,
    padX: px(cs.paddingLeft),
    padY: px(cs.paddingTop),
    radius: px(cs.borderTopLeftRadius),
  };
}

// ── Measuring the real components ────────────────────────────────────────

let p3Context: CanvasRenderingContext2D | null | undefined;

/** Paint a CSS colour into a 1×1 display-P3 canvas and read it back. */
export function cssColourToP3(css: string): P3Colour | null {
  if (p3Context === undefined) {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      p3Context = canvas.getContext("2d", { colorSpace: "display-p3", willReadFrequently: true });
    } catch {
      p3Context = null;
    }
  }
  const ctx = p3Context;
  if (!ctx) return null;
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = "#000";
  ctx.fillStyle = css; // an unparseable value leaves the black, which we detect below
  if (ctx.fillStyle === "#000000" && !/^(#000|#000000|black|rgb\(0,\s*0,\s*0\))$/i.test(css.trim())) {
    return null;
  }
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1, { colorSpace: "display-p3" }).data;
  return { r: r / 255, g: g / 255, b: b / 255, a: a / 255 };
}

/**
 * Render the real badges for these tags and people, hidden, inside `host` (the
 * app root, so `[data-person-display]` and the palette apply exactly as on a
 * card), and measure them. Returns empty maps where measuring is impossible.
 */
export function probeBadgeStyles(
  host: HTMLElement,
  subjects: { tags: Pick<TagResponse, "name" | "colour_set" | "colour_index">[]; people: { code: string; name: string | null }[] },
  ctx: ReadContext = { toP3: cssColourToP3, monoFamily: rootMonoFamily(host) },
): BadgeStyles {
  const out: BadgeStyles = { tags: {}, people: {} };
  if (subjects.tags.length === 0 && subjects.people.length === 0) return out;

  // Same ancestry as a card's badge row; invisible and out of the flow, but
  // laid out (visibility, not display:none), so computed lengths are real.
  const probe = document.createElement("div");
  probe.className = "quote-card bn-badge-probe";
  probe.setAttribute("aria-hidden", "true");
  probe.style.cssText = "position:fixed;left:-10000px;top:0;visibility:hidden;pointer-events:none;";
  host.appendChild(probe);
  const root = createRoot(probe);
  try {
    const elements: ReactElement[] = [
      ...subjects.tags.map((t) =>
        createElement(Badge, {
          key: `t:${t.name}`,
          text: t.name,
          variant: "user",
          colour: t.colour_set ? getTagBg(t.colour_set, t.colour_index) : undefined,
          "data-testid": `probe-tag-${fold(t.name)}`,
        }),
      ),
      ...subjects.people.map((p) =>
        createElement(
          "span",
          { key: `p:${p.code}`, "data-probe-person": p.code },
          createElement(PersonBadge, { code: p.code, role: roleOf(p.code), name: p.name ?? undefined }),
        ),
      ),
    ];
    flushSync(() => root.render(createElement("div", { className: "badges" }, elements)));

    for (const t of subjects.tags) {
      const el = probe.querySelector(`[data-testid="probe-tag-${CSS.escape(fold(t.name))}"]`);
      if (el) out.tags[fold(t.name)] = readBadgeStyle(getComputedStyle(el), ctx);
    }
    for (const p of subjects.people) {
      const wrap = probe.querySelector(`[data-probe-person="${CSS.escape(p.code)}"]`);
      const codeEl = wrap?.querySelector(".bn-speaker-badge-code");
      if (!codeEl) continue;
      const nameEl = wrap?.querySelector(".bn-speaker-badge-name");
      const nameShown = nameEl && getComputedStyle(nameEl).display !== "none";
      out.people[p.code] = {
        code: readBadgeStyle(getComputedStyle(codeEl), ctx),
        name: nameShown ? readBadgeStyle(getComputedStyle(nameEl), ctx) : null,
      };
    }
  } finally {
    root.unmount();
    probe.remove();
  }
  return out;
}

function roleOf(code: string): "participant" | "moderator" | "observer" {
  return code.startsWith("m") ? "moderator" : code.startsWith("o") ? "observer" : "participant";
}

function rootMonoFamily(host: HTMLElement): string {
  return getComputedStyle(host).getPropertyValue("--bn-font-mono").trim();
}
