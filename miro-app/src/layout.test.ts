import { describe, expect, it } from "vitest";
import boardFixture from "../../tests/fixtures/figjam-board-v1.json";
import layoutFixture from "../../tests/fixtures/miro-inboard-layout-v1.json";
import { parseBoard } from "../../figjam-plugin/src/board";
import { escapeHtml, fitMiroSticky, MIRO_STICKY_MAX, planBoard, textWidth } from "./layout";

// The board file Bristlenose writes, and what Send to Miro does with the same columns
// (tests/test_miro_inboard_layout_contract.py writes the second from bristlenose.board_layout).
const BOARD_FILE = JSON.stringify(boardFixture);
const LAYOUT = layoutFixture as { shapes: Record<string, any> };

const r = (v: number) => Math.round(v * 1000) / 1000;

describe.each(["rectangle", "square"])("the %s layout is Send to Miro's", (shape) => {
  const board = { ...parseBoard(BOARD_FILE), stickyShape: shape };
  const plan = planBoard(board);
  const expected = LAYOUT.shapes[shape];

  it("has the same size and title", () => {
    expect(plan.shape).toBe(shape);
    expect([r(plan.width), r(plan.height)]).toEqual([expected.width, expected.height]);
    expect({ ...plan.title, fontSize: undefined }).toEqual({ ...expected.title, font_size: undefined, fontSize: undefined });
    expect(plan.title.fontSize).toBe(expected.title.font_size);
  });

  it("has the same frames", () => {
    expect(plan.frames.map((f) => ({ ...f, x: r(f.x), y: r(f.y), width: r(f.width), height: r(f.height) }))).toEqual(
      expected.frames,
    );
  });

  it("has the same stickies, in the same order, with the same content", () => {
    expect(plan.stickies.length).toBe(expected.stickies.length);
    plan.stickies.forEach((s, i) => {
      const e = expected.stickies[i];
      expect({ kind: s.kind, x: r(s.x), y: r(s.y), width: r(s.width), height: r(s.height), colour: s.colour })
        .toEqual({ kind: e.kind, x: e.x, y: e.y, width: e.width, height: e.height, colour: e.colour });
      expect(s.content).toBe(e.content);
      expect(s.set === null).toBe(e.set === null);
    });
  });

  it("groups the same stickies into sets", () => {
    const groups = (sets: (number | null)[]) => {
      const out: number[][] = [];
      sets.forEach((s, i) => {
        if (s === null) return;
        (out[s] ??= []).push(i);
      });
      return out.filter(Boolean);
    };
    expect(groups(plan.stickies.map((s) => s.set))).toEqual(groups(expected.stickies.map((s: { set: number | null }) => s.set)));
  });

  it("marks one last sticky per quote, and counts every quote", () => {
    expect(plan.stickies.filter((s) => s.last).length).toBe(plan.expectedQuotes);
    expect(plan.expectedQuotes).toBe(8);
  });
});

describe("text width counts as Python does", () => {
  it("counts wide characters twice and astral ones once per code point", () => {
    expect(textWidth("abc")).toBe(3);
    expect(textWidth("駅の")).toBe(4);
    expect(textWidth("𠮷")).toBe(2); // one code point, two UTF-16 units, wide
    expect(textWidth("👩🏽‍💻")).toBe(7); // 👩 2 + 🏽 2 + ZWJ 1 + 💻 2
    expect(textWidth("𝒜")).toBe(1); // astral but narrow: one code point, not two UTF-16 units
  });
});

describe("escaping", () => {
  it("is Python's html.escape with quote=True", () => {
    expect(escapeHtml(`<a href="x">Tom's & co</a>`)).toBe("&lt;a href=&quot;x&quot;&gt;Tom&#x27;s &amp; co&lt;/a&gt;");
  });

  it("puts a clip address with quotes or angle brackets into the attribute escaped", () => {
    const board = parseBoard(BOARD_FILE);
    board.frames[0].columns[0].quotes[0].clipUrl = 'https://clips.example/a"b<c>d&e';
    const content = planBoard(board).stickies[1].content;
    expect(content).toContain('href="https://clips.example/a&quot;b&lt;c&gt;d&amp;e"');
    expect(content).not.toMatch(/href="[^"]*"[^>]*"/);
  });

  it("leaves out a clip link that is not a plain web address, and counts it", () => {
    const board = parseBoard(BOARD_FILE);
    board.frames[0].columns[0].quotes[0].clipUrl = "javascript:alert(1)";
    const plan = planBoard(board);
    expect(plan.stickies[1].content).not.toContain("<a ");
    expect(plan.droppedLinks).toBe(1);
  });

  it("never lets a quote's own markup through", () => {
    const board = parseBoard(BOARD_FILE);
    board.frames[0].columns[0].quotes[0].parts = ['<img src=x onerror="alert(1)">'];
    expect(planBoard(board).stickies[1].content).toContain("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
  });
});

describe("the title", () => {
  it("is escaped, as Send to Miro escapes it", () => {
    const board = parseBoard(BOARD_FILE);
    board.title = "A & B <c>";
    expect(planBoard(board).title.content).toBe("A &amp; B &lt;c&gt;");
  });
});

describe("colours", () => {
  it("draws a token Miro has no name for as light yellow, and counts it", () => {
    const board = parseBoard(BOARD_FILE);
    board.frames[0].columns[0].quotes[0].colour = "mauve";
    const plan = planBoard(board);
    expect(plan.stickies[1].colour).toBe("light_yellow");
    expect(plan.unknownColours).toBe(1);
  });
});

describe("Miro's 6,000-character limit", () => {
  it("cuts only what is too long, measured after escaping", () => {
    const out = fitMiroSticky("&".repeat(2000), "<br><i>x</i>");
    expect([...out].length).toBeLessThanOrEqual(MIRO_STICKY_MAX);
    expect(out.endsWith("…<br><i>x</i>")).toBe(true);
    expect(fitMiroSticky("short", "")).toBe("short");
  });
});
