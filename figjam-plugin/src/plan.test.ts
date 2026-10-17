/**
 * Plugin side of the FigJam board contract.
 *
 * Reads tests/fixtures/figjam-board-v1.json, which bristlenose/board_manifest.py
 * writes and tests/test_board_fixture_contract.py pins. If either side drifts,
 * one of the two suites fails with the case named. Whether a board *looks*
 * right — stickies growing, nothing overlapping — is checked by hand in a real
 * FigJam file; mocking Figma would only return what the assertion wants.
 */

import { describe, expect, it } from "vitest";
import additive from "../../tests/fixtures/figjam-board-v1-additive.json";
import plain from "../../tests/fixtures/figjam-board-v1.json";
import { REFUSAL_TEXT, Refusal, parseBoard, safeClipUrl } from "./board";
import { planBoard, rgb } from "./plan";

const text = (doc: unknown) => JSON.stringify(doc);
const plan = (doc: unknown) => planBoard(parseBoard(text(doc)));
const sets = (p: ReturnType<typeof planBoard>) => p.frames.flatMap((f) => f.columns.flatMap((c) => c.quotes));
/** The sticky of each quote that carries its attribution: its last part. */
const quotes = (p: ReturnType<typeof planBoard>) => sets(p).map((q) => q.parts[q.parts.length - 1]);
const edited = (change: (d: any) => void) => {
  const d = structuredClone(plain);
  change(d);
  return d;
};
const refusal = (doc: unknown): string => {
  try {
    parseBoard(typeof doc === "string" ? doc : text(doc));
  } catch (e) {
    if (e instanceof Refusal) return e.kind;
    throw e;
  }
  return "accepted";
};

describe("the version-1 fixture", () => {
  it("plans every quote the file says it holds", () => {
    const p = plan(plain);
    expect(quotes(p)).toHaveLength(8);
    expect(p.expectedQuotes).toBe(8);
    expect(p.frames.map((f) => f.columns.length)).toEqual([2, 1]);
  });

  it("draws a file with keys it has never seen exactly as the plain one", () => {
    expect(plan(additive)).toEqual(plan(plain));
  });

  it("draws a square file square, and a rectangle as FigJam's wide sticky", () => {
    expect(plan(plain).wide).toBe(false);
    expect(plan(edited((d) => (d.sticky_shape = "rectangle"))).wide).toBe(true);
  });

  it("keeps Bristlenose's order", () => {
    const first = plan(plain).frames[0].columns[0].quotes.map((q) => q.parts.at(-1)!.characters.split("\n").at(-1));
    expect(first).toEqual(["— P1 · 00:42 · ▶ clip", "— P2 · 1:02:05", "— P3 · 00:09"]);
  });

  it("bolds the column label and nothing after it", () => {
    const h = plan(plain).frames[0].columns[0].header;
    expect(h.characters).toBe("Checkout\n3 quotes");
    expect(h.characters.slice(...h.bold!)).toBe("Checkout");
  });

  it("puts the attribution in italics exactly, even after emoji and rare CJK", () => {
    for (const q of quotes(plan(plain))) {
      const line = q.characters.slice(...q.italic!);
      expect(line.startsWith("— P")).toBe(true);
      expect(q.characters.slice(0, q.italic![0] - 1).endsWith("”")).toBe(true);
    }
  });

  it("links only the clip label, and only where there is a clip", () => {
    const qs = quotes(plan(plain));
    const linked = qs.filter((q) => q.link);
    expect(linked).toHaveLength(2);
    expect(linked[0].characters.slice(...linked[0].link!.range)).toBe("▶ clip");
    expect(linked[0].link!.url).toBe("https://clips.example/study/s1-p1-42.mp4");
    expect(plan(plain).clipHosts).toEqual(["clips.example"]);
  });

  it("fills with FigJam's palette colours, exactly", () => {
    const p = plan(plain);
    expect(p.frames[0].columns[0].header.fill).toBe("#FFA8DB");
    expect(quotes(p)[0].fill).toBe("#FFE299");
    expect(rgb("#FFA8DB")).toEqual({ r: 1, g: 0xa8 / 255, b: 0xdb / 255 });
  });
});

describe("a long quote as a set of two or three stickies", () => {
  const trio = () => sets(plan(plain)).find((q) => q.parts.length === 3)!;

  it("draws each part as its own sticky, in order, with nothing added or lost", () => {
    const fixtureParts = plain.frames.flatMap((f) => f.columns.flatMap((c) => c.quotes)).find((q) => q.parts.length === 3)!.parts;
    const t = trio();
    expect(t.parts.slice(0, 2).map((p) => p.characters)).toEqual(fixtureParts.slice(0, 2));
    expect(t.parts[2].characters.startsWith(fixtureParts[2])).toBe(true);
    expect(sets(plan(plain)).map((q) => q.parts.length).sort()).toEqual([1, 1, 1, 1, 1, 1, 2, 3]);
  });

  it("puts the attribution, italics and link on the last part only", () => {
    const t = trio();
    expect(t.parts.slice(0, 2).every((p) => !p.italic && !p.link && !p.small)).toBe(true);
    expect(t.parts[2].characters.slice(...t.parts[2].italic!)).toBe("— P6 · 21:50");
    const pair = sets(plan(plain)).find((q) => q.parts.length === 2)!;
    expect(pair.parts[1].link?.url).toBe("https://clips.example/study/s2-p2-845.mp4");
  });

  it("names the set by its attribution, so it can be found in the layers list", () => {
    expect(trio().name).toBe("— P6 · 21:50");
  });

  it("refuses a quote with no parts", () => {
    expect(refusal(edited((d) => (d.frames[0].columns[0].quotes[0].parts = [])))).toBe("malformed");
  });
});

describe("refusing a file it would draw wrong", () => {
  it("refuses a file a newer Bristlenose says needs a newer plugin", () => {
    expect(refusal(edited((d) => (d.min_reader_version = 2)))).toBe("too_new");
  });

  it("refuses what is not a board", () => {
    expect(refusal("{not json")).toBe("not_json");
    expect(refusal({ format: "something-else" })).toBe("not_a_board");
    expect(refusal([1, 2])).toBe("not_a_board");
  });

  it("refuses a colour it has no hex for, or a hex that isn't one", () => {
    expect(refusal(edited((d) => (d.frames[0].columns[0].quotes[0].colour = "violet")))).toBe("malformed");
    expect(refusal(edited((d) => (d.palette.light_pink = "pink")))).toBe("malformed");
  });

  it("refuses counts that disagree, rather than build part of a board", () => {
    expect(refusal(edited((d) => (d.totals.quotes = 7)))).toBe("malformed");
    expect(refusal(edited((d) => d.frames[0].columns[0].quotes.pop()))).toBe("malformed");
  });

  it("refuses a field of the wrong type", () => {
    expect(refusal(edited((d) => (d.frames[0].columns[0].quotes[0].parts = [5])))).toBe("malformed");
    expect(refusal(edited((d) => (d.frames[0].columns[0].quotes[0].clip_url = { href: "x" })))).toBe("malformed");
  });

  it("says each refusal in one plain sentence", () => {
    for (const sentence of Object.values(REFUSAL_TEXT)) {
      expect(sentence).toMatch(/^[A-Z].*\.$/);
      expect(sentence).not.toMatch(/undefined|null|error|exception|refusal/i);
    }
  });
});

describe("clip links from a file that may have been edited", () => {
  it("draws only plain web addresses", () => {
    expect(safeClipUrl("https://x.example/c.mp4")).toEqual({ href: "https://x.example/c.mp4", host: "x.example" });
    expect(safeClipUrl("http://NAS.local:8080/clips/a b.mp4")).toBeNull(); // a space
    expect(safeClipUrl("http://NAS.local:8080/clips/a.mp4")?.host).toBe("nas.local:8080");
    for (const bad of ["javascript:alert(1)", "data:text/html,x", "file:///etc/passwd",
                       "https://user:pw@x.example/c.mp4", "https://x.example\\@evil/", "//x.example/c",
                       "not a url", "", null]) {
      expect(safeClipUrl(bad)).toBeNull();
    }
  });

  it("drops a bad link and counts it, but still draws the quote", () => {
    const p = plan(edited((d) => (d.frames[0].columns[0].quotes[0].clip_url = "javascript:alert(1)")));
    expect(quotes(p)).toHaveLength(8);
    expect(quotes(p).filter((q) => q.link)).toHaveLength(1);
    expect(p.droppedLinks).toBe(1);
  });
});

describe("the Figma sandbox, not Node", () => {
  // Figma's main thread lacks browser globals Node has, so a test that passes
  // here can still fail in FigJam. The first build lost every clip link that
  // way (`URL` is not defined there). Plan the fixture with them removed.
  it("plans the fixture without URL, URLSearchParams or structuredClone", () => {
    const g = globalThis as Record<string, unknown>;
    const missing = ["URL", "URLSearchParams", "structuredClone"] as const;
    const saved = missing.map((k) => g[k]);
    try {
      for (const k of missing) g[k] = undefined;
      const p = planBoard(parseBoard(text(plain)));
      expect(p.clipHosts).toEqual(["clips.example"]);
      expect(quotes(p).filter((q) => q.link)).toHaveLength(2);
    } finally {
      missing.forEach((k, i) => (g[k] = saved[i]));
    }
  });
});
