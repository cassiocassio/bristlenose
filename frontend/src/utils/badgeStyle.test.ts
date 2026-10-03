/**
 * badgeStyle — what the Mac app is told a badge looks like (design-search §7a).
 *
 * jsdom resolves no theme CSS, does no layout and has no canvas, so the values
 * a real WebKit resolves can only be checked in the app (the §7a human QA with
 * Digital Color Meter). What is pinned here: the reader turns a resolved style
 * into the wire shape correctly, and the probe renders the REAL components,
 * finds every badge it was asked for, and leaves nothing behind.
 */

import { afterEach, describe, expect, it } from "vitest";

import contractJson from "../../../tests/fixtures/search-bridge-contract.json";
import {
  probeBadgeStyles,
  readBadgeStyle,
  type BadgeStyle,
  type BadgeStyles,
  type ReadContext,
  type StyleSource,
} from "./badgeStyle";

const MONO = `"SF Mono", ui-monospace, Menlo, monospace`;

/** rgb()/rgba() → components, as a stand-in for the canvas in a browser. */
const toP3: ReadContext["toP3"] = (css) => {
  const m = /rgba?\(([^)]+)\)/.exec(css);
  if (!m) return null;
  const [r, g, b, a = "1"] = m[1].split(/[,\s/]+/).filter(Boolean);
  return { r: +r / 255, g: +g / 255, b: +b / 255, a: +a };
};

function style(over: Partial<StyleSource> = {}): StyleSource {
  return {
    backgroundColor: "rgb(230, 240, 255)",
    color: "rgb(20, 30, 40)",
    borderTopWidth: "0px",
    borderTopStyle: "none",
    borderTopColor: "rgb(0, 0, 0)",
    fontFamily: "-apple-system, sans-serif",
    fontSize: "12px",
    fontWeight: "500",
    paddingLeft: "6px",
    paddingTop: "1.5px",
    paddingRight: "6px",
    paddingBottom: "1.5px",
    lineHeight: "16px",
    borderTopLeftRadius: "4px",
    ...over,
  };
}

describe("readBadgeStyle", () => {
  const ctx: ReadContext = { toP3, monoFamily: MONO };

  it("turns resolved values into the wire shape", () => {
    expect(readBadgeStyle(style(), ctx)).toEqual({
      bg: { r: 230 / 255, g: 240 / 255, b: 1, a: 1 },
      fg: { r: 20 / 255, g: 30 / 255, b: 40 / 255, a: 1 },
      border: null,
      fontFamily: "body",
      sizePx: 12,
      weight: 500,
      padX: 6,
      padY: 1.5,
      padRight: 6,
      padBottom: 1.5,
      lineHeightPx: 16,
      radius: 4,
    });
  });

  it("sends each side's padding and the line box, so a one-sided name half matches", () => {
    const name = readBadgeStyle(style({ paddingLeft: "0px", paddingRight: "1.6px", lineHeight: "15.5px" }), ctx);
    expect([name.padX, name.padRight, name.lineHeightPx]).toEqual([0, 1.6, 15.5]);
    // "normal" is a font metric, not a length: sent as unknown, not as 0.
    expect(readBadgeStyle(style({ lineHeight: "normal" }), ctx).lineHeightPx).toBeNull();
  });

  it("a transparent fill is no fill", () => {
    expect(readBadgeStyle(style({ backgroundColor: "rgba(0, 0, 0, 0)" }), ctx).bg).toBeNull();
    expect(readBadgeStyle(style({ backgroundColor: "transparent" }), ctx).bg).toBeNull();
  });

  it("a border counts only when it is drawn", () => {
    const drawn = style({ borderTopWidth: "1px", borderTopStyle: "solid", borderTopColor: "rgb(200, 0, 0)" });
    expect(readBadgeStyle(drawn, ctx).border).toEqual({ colour: { r: 200 / 255, g: 0, b: 0, a: 1 }, widthPx: 1 });
    expect(readBadgeStyle({ ...drawn, borderTopStyle: "none" }, ctx).border).toBeNull();
    expect(readBadgeStyle({ ...drawn, borderTopWidth: "0px" }, ctx).border).toBeNull();
  });

  it("recognises the theme's mono stack however the browser spaces or quotes it", () => {
    expect(readBadgeStyle(style({ fontFamily: `'SF Mono',ui-monospace,  Menlo, monospace` }), ctx).fontFamily).toBe("mono");
    expect(readBadgeStyle(style({ fontFamily: "Menlo, monospace" }), ctx).fontFamily).toBe("body");
  });

  it("an unresolvable colour degrades instead of throwing, and says so", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const s = readBadgeStyle(style({ color: "var(--nope)", backgroundColor: "var(--nope)" }), ctx);
    expect(s.fg).toEqual({ r: 0, g: 0, b: 0, a: 1 });
    expect(s.bg).toBeNull();
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("var(--nope)"));
    warn.mockRestore();
  });
});

describe("probeBadgeStyles", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  const subjects = {
    tags: [
      { name: "Zoning", colour_set: "ux", colour_index: 0 },
      { name: "Café \"quotes\"", colour_set: "", colour_index: 0 },
    ],
    people: [
      { code: "p3", name: "Zoë" },
      { code: "p9", name: null },
    ],
  };

  it("measures every badge it was asked for, from the real components", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const styles = probeBadgeStyles(host, subjects, { toP3, monoFamily: MONO });

    expect(Object.keys(styles.tags).sort()).toEqual(["cafe quotes", "zoning"]); // folded keys, like the search ids (quote marks fold to spaces)
    expect(Object.keys(styles.people).sort()).toEqual(["p3", "p9"]);
    expect(styles.people.p3.name).not.toBeNull();
    expect(styles.people.p9.name).toBeNull();
  });

  it("leaves nothing in the document", () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    probeBadgeStyles(host, subjects, { toP3, monoFamily: MONO });
    expect(host.childElementCount).toBe(0);
  });

  it("asked for nothing, renders nothing", () => {
    const host = document.createElement("div");
    expect(probeBadgeStyles(host, { tags: [], people: [] })).toEqual({ tags: {}, people: {} });
    expect(host.childElementCount).toBe(0);
  });
});

describe("the search-badge-styles wire (search-bridge-contract.json)", () => {
  const wire = (contractJson as unknown as { web_to_native: { search_badge_styles: { wire: BadgeStyles } } })
    .web_to_native.search_badge_styles.wire;
  const fixtureStyles: BadgeStyle[] = [
    ...Object.values(wire.tags),
    ...Object.values(wire.people).flatMap((p) => (p.name ? [p.code, p.name] : [p.code])),
  ];
  const keys = (o: object) => Object.keys(o).sort();
  const ctx: ReadContext = { toP3, monoFamily: MONO };

  it("every style in the fixture has exactly the fields the reader sends", () => {
    const read = readBadgeStyle(style({ borderTopWidth: "1px", borderTopStyle: "solid" }), ctx);
    expect(read.border).not.toBeNull(); // so the border's own fields are compared too
    for (const s of fixtureStyles) {
      expect(keys(s)).toEqual(keys(read));
      expect(keys(s.fg)).toEqual(keys(read.fg));
      if (s.bg) expect(keys(s.bg)).toEqual(keys(read.fg));
      if (s.border) {
        expect(keys(s.border)).toEqual(keys(read.border!));
        expect(keys(s.border.colour)).toEqual(keys(read.fg));
      }
    }
    expect(fixtureStyles.length).toBeGreaterThanOrEqual(4);
  });

  it("the fixture covers no fill, a border, and a code-only person", () => {
    expect(fixtureStyles.some((s) => s.bg === null)).toBe(true);
    expect(fixtureStyles.some((s) => s.border !== null)).toBe(true);
    expect(Object.values(wire.people).some((p) => p.name === null)).toBe(true);
  });
});
