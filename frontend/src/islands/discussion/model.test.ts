import { describe, expect, it } from "vitest";
import fixture from "./fixture.json";
import {
  capNames,
  litTurns,
  markOf,
  mergedEntries,
  plannedEntries,
  sessionColumn,
  sessionForFocus,
  shownSession,
  wirePath,
  type NavRow,
} from "./model";
import type { DiscussionData, DiscussionItem, DiscussionQuote, DiscussionTurn } from "./types";

const data = fixture as unknown as DiscussionData;

function item(over: Partial<DiscussionItem>): DiscussionItem {
  return { id: "i", terse: "t", verbatim: "v", source: "asked", placed: "", role: "core", asks: [], ...over };
}

function turn(id: string, sec: number, item: string | null): DiscussionTurn {
  return { id, session: "s1", sec, time: "", text: id, kind: item ? "planned" : "chat", item };
}

function quote(key: string, sec: number): DiscussionQuote {
  return { key, session: "s1", participant: "p1", name: "", sec, time: "", text: key,
    after_item: null, section: null, how: "agree" };
}

function tiny(turns: DiscussionTurn[], quotes: DiscussionQuote[]): DiscussionData {
  return { version: 1, guide: false, sessions: [{ id: "s1", number: 1, participants: [], duration: "", seconds: 600 }],
    spine: [], sections: [], standalone: [], turns, quotes };
}

describe("markOf", () => {
  it("dot for asked as planned, hollow for never asked, plus for anything unplanned", () => {
    expect(markOf(item({ source: "both" }))).toBe("dot");
    expect(markOf(item({ source: "planned" }))).toBe("hollow");
    expect(markOf(item({ source: "asked" }))).toBe("plus");
    expect(markOf(item({ source: "asked", placed: "flow" }))).toBe("plus");
  });
});

describe("navigator entries", () => {
  it("Merged lists every section and item, badging instruction sections only", () => {
    const e = mergedEntries(data);
    const heads = e.filter((x) => x.type === "head");
    expect(heads.map((h) => h.title)).toEqual(data.sections.map((s) => s.title));
    const emergent = data.sections.find((s) => s.origin === "emergent")!;
    expect(heads.find((h) => h.id === emergent.id)).not.toHaveProperty("badge", expect.anything());
    expect(heads.some((h) => h.type === "head" && h.badge === "instruction")).toBe(true);
    const rows = e.filter((x): x is NavRow => x.type === "row");
    expect(rows.length).toBe(data.sections.reduce((n, s) => n + s.items.length, 0));
  });

  it("Planned shows the guide as written, every line with the solid dot", () => {
    const rows = plannedEntries(data).filter((x): x is NavRow => x.type === "row");
    expect(rows.length).toBe(data.spine.reduce((n, s) => n + s.items.length, 0));
    expect(new Set(rows.map((r) => r.mark))).toEqual(new Set(["dot"]));
  });

  it("a planned line takes its sessions from the merged item with the same id; never asked has none", () => {
    const rows = plannedEntries(data).filter((x): x is NavRow => x.type === "row");
    const neverAsked = data.sections.flatMap((s) => s.items).find((i) => i.source === "planned")!;
    expect(rows.find((r) => r.id === neverAsked.id)!.sessions).toEqual([]);
    const asked = data.sections.flatMap((s) => s.items).find((i) => i.source === "both")!;
    expect(rows.find((r) => r.id === asked.id)!.sessions.length).toBeGreaterThan(0);
  });

  it("orders a row's sessions by the session list, not by when they were asked", () => {
    const d = { ...data, sessions: data.sessions.slice().reverse() };
    const rows = mergedEntries(d).filter((x): x is NavRow => x.type === "row" && x.sessions.length > 1);
    const order = d.sessions.map((s) => s.id);
    for (const r of rows) expect(r.sessions).toEqual(order.filter((s) => r.sessions.includes(s)));
  });
});

describe("sessionColumn", () => {
  it("each quote answers the last question asked at or before it", () => {
    const col = sessionColumn(tiny([turn("a", 10, "x"), turn("b", 50, "y")], [quote("q1", 20), quote("q2", 60)]), "s1");
    expect(col.groups.map((g) => g.asks.map((a) => [a.turn.id, a.answers.map((q) => q.key)]))).toEqual([
      [["a", ["q1"]]],
      [["b", ["q2"]]],
    ]);
  });

  it("questions that drew no quotes fold forward into the next question that did", () => {
    const col = sessionColumn(tiny([turn("a", 10, "x"), turn("b", 20, "y"), turn("c", 30, "z")], [quote("q", 35)]), "s1");
    expect(col.groups).toHaveLength(1);
    expect(col.groups[0].asks.map((a) => a.turn.id)).toEqual(["a", "b", "c"]);
    expect(col.groups[0].trailing).toBe(false);
  });

  it("unanswered questions at the end form a trailing group; quotes before any question are set apart", () => {
    const col = sessionColumn(tiny([turn("a", 10, "x"), turn("b", 50, "y")], [quote("q0", 5), quote("q1", 20)]), "s1");
    expect(col.before.map((q) => q.key)).toEqual(["q0"]);
    expect(col.groups[1]).toMatchObject({ trailing: true });
  });

  it("non-question turns never appear in the column", () => {
    const col = sessionColumn(tiny([turn("a", 10, "x"), turn("chat", 15, null)], [quote("q", 20)]), "s1");
    expect(col.groups[0].asks.map((a) => a.turn.id)).toEqual(["a"]);
  });

  it("every quote in the fixture lands somewhere exactly once", () => {
    for (const s of data.sessions) {
      const col = sessionColumn(data, s.id);
      const placed = col.before.length + col.groups.reduce((n, g) => n + g.asks.reduce((m, a) => m + a.answers.length, 0), 0);
      expect(placed).toBe(data.quotes.filter((q) => q.session === s.id).length);
    }
  });
});

describe("capNames", () => {
  const list = (n: string[]) => (n.length < 2 ? n.join("") : `${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}`);
  const others = (f: string, n: number) => `${f} and ${n} others`;
  const p = (...names: string[]) => names.map((name, i) => ({ code: `p${i}`, name }));
  it("names up to two in full, then the first and a count", () => {
    expect(capNames(p("Simon"), list, others)).toBe("Simon");
    expect(capNames(p("Sarah", "Mike"), list, others)).toBe("Sarah and Mike");
    expect(capNames(p("Bettina", "Priya", "Christopher", "Anneliese", "Oluwaseun"), list, others)).toBe("Bettina and 4 others");
  });
});

describe("focus", () => {
  it("a row lights every ask of its item in the current session; a question lights only itself", () => {
    const d = tiny([turn("a", 10, "x"), turn("b", 50, "x"), turn("c", 60, "y")], []);
    expect([...litTurns(d, "s1", { item: "x", turn: null })]).toEqual(["a", "b"]);
    expect([...litTurns(d, "s1", { item: "x", turn: "b" })]).toEqual(["b"]);
    expect(litTurns(d, "s1", null).size).toBe(0);
  });

  it("a row the current session never asked jumps to the first session that did", () => {
    expect(sessionForFocus("s1", ["s2", "s3"])).toBe("s2");
    expect(sessionForFocus("s3", ["s2", "s3"])).toBe("s3");
    expect(sessionForFocus("s1", [])).toBe("s1");
  });

  it("a collapsed badge row shows the current session when it is there, else the first", () => {
    expect(shownSession("s3", ["s1", "s3"])).toBe("s3");
    expect(shownSession("s2", ["s1", "s3"])).toBe("s1");
  });
});

describe("wirePath", () => {
  it("joins two on-screen ends across the gutter", () => {
    expect(wirePath({ y: 10, off: 0 }, { y: 40, off: 0 }, 56)).toEqual({ d: "M0,10 h8 L48,40 h8", stub: false });
  });
  it("draws a stub from the on-screen end when the other is scrolled away", () => {
    expect(wirePath({ y: 10, off: 0 }, { y: 900, off: 1 }, 56)!.stub).toBe(true);
    expect(wirePath({ y: -50, off: -1 }, { y: 40, off: 0 }, 56)!.d.startsWith("M56,40")).toBe(true);
  });
  it("draws nothing when both ends are off screen", () => {
    expect(wirePath({ y: -5, off: -1 }, { y: 900, off: 1 }, 56)).toBeNull();
  });
});
