import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixture.json";
import { DiscussionLens, DiscussionView } from "./DiscussionLens";
import { joinNames } from "./loadDiscussion";
import i18n from "../../i18n";
import enDesktop from "@locales/en/desktop.json";
import { _resetPlatformCache } from "../../utils/platform";
import { _resetEmbeddedCache } from "../../utils/embedded";
import { resetLensState } from "./lensState";
import { cellQuotes, itemAnswers, quoteTurns, shadeStep, yieldThirds } from "./model";
import { discussionGuideState, resetDiscussionGuide, setDiscussionGuideOpen, setPendingGuide, toggleDiscussionGuide } from "./guidePanel";
import type { DiscussionData } from "./types";
import { getQuotesSnapshot, HIDE_DURATION, hideQuotes, initFromQuotes, resetStore } from "../../contexts/QuotesContext";
import { FocusProvider, useFocus } from "../../contexts/FocusContext";
import type { QuoteResponse } from "../../utils/types";

const data = fixture as unknown as DiscussionData;

/** The report's own quotes for a record, as /quotes carries them: the store the lens's cards read
 *  (quoteCardHost.tsx). A record quote with no report id is one the report does not hold. */
function quotesFor(d: DiscussionData): QuoteResponse[] {
  return d.quotes.filter((q) => q.dom_id).map((q) => ({
    dom_id: q.dom_id!, text: q.text, verbatim_excerpt: q.text, participant_id: q.participant,
    session_id: q.session, speaker_name: q.name || q.participant, start_timecode: q.sec,
    end_timecode: q.sec + 5, sentiment: q.sentiment ?? null, intensity: 1, researcher_context: null,
    quote_type: "screen_specific", topic_label: "", is_starred: false, is_hidden: false, edited_text: null,
    tags: [], deleted_badges: [], proposed_tags: [], segment_index: 0,
  }));
}

/** The record the store was last seeded from: what the mocked /quotes answers with. */
let seeded: DiscussionData = data;
function seed(d: DiscussionData) {
  seeded = d;
  resetStore();
  initFromQuotes(quotesFor(d));
}
/** The mocked network: /quotes from the seeded record, nothing else. */
function route(path: string): Promise<unknown> {
  if (path === "/quotes") {
    return Promise.resolve({ sections: [{ quotes: quotesFor(seeded) }], themes: [], unjoined: [], has_moderator: true });
  }
  return Promise.resolve(undefined);
}
/** Render the lens on a record, its quotes in the store. */
function view(d: DiscussionData) {
  seed(d);
  return render(<DiscussionView data={d} />);
}

function nav() {
  return screen.getByRole("navigation", { name: "Discussion guide" });
}

function heading() {
  return screen.getByRole("heading", { level: 1 }).textContent;
}

/** Pick a session by its digit key (the lens opens on All once there are two sessions). */
function onSession(n: number) {
  fireEvent.keyDown(document, { key: String(n) });
}

/** jsdom lays nothing out, and the navigator's measure (bar → strip → grid) is chosen by
 *  measuring. This gives the guide a content width and the one-digit probe head a width, and
 *  stands in for the ResizeObserver the lens re-measures through. Restore in a finally. */
function layout(nav: number, probe = 19) {
  const size = { nav, probe };
  const cw = vi.spyOn(Element.prototype, "clientWidth", "get").mockImplementation(function (this: Element) {
    return this.classList.contains("dl-nav") ? size.nav : 0;
  });
  const rect = vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const w = this.closest(".dl-head-probe") ? size.probe : 0;
    return { width: w, height: 0, top: 0, left: 0, right: w, bottom: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
  });
  const observers: (() => void)[] = [];
  const real = globalThis.ResizeObserver;
  globalThis.ResizeObserver = class {
    constructor(cb: () => void) { observers.push(cb); }
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  return {
    resize(next: Partial<typeof size>) {
      Object.assign(size, next);
      act(() => observers.forEach((cb) => cb()));
    },
    restore() {
      cw.mockRestore();
      rect.mockRestore();
      globalThis.ResizeObserver = real;
    },
  };
}

beforeEach(() => {
  resetLensState();
  resetDiscussionGuide();
  document.getElementById("bn-app-root")?.remove();
  seed(data);
  api.apiGet.mockImplementation(route);
  api.getCodebook.mockResolvedValue({ groups: [], all_tag_names: [] });
});

describe("DiscussionView", () => {
  it("opens on Merged and All: each question once, every session's answers under it", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Normalised questions" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "All sessions" })).toHaveAttribute("aria-checked", "true");
    expect(heading()).toBe("All sessions");
    const asked = data.sections.flatMap((s) => s.items).filter((i) => i.asks.length);
    expect(container.querySelectorAll(".dl-content .dl-item")).toHaveLength(asked.length);
    const answers = itemAnswers(data);
    for (const it of asked) {
      const block = container.querySelector(`.dl-item[data-item="${it.id}"]`)!;
      // one block per session with a quote to show, each led by that session's badge; a
      // question with none is its heading alone (decided 19 Oct 2026)
      const drew = data.sessions.filter((s) => cellQuotes(answers, it.id, s.id) > 0);
      expect(block.querySelectorAll(".dl-group")).toHaveLength(drew.length);
      expect(block.classList.contains("empty")).toBe(drew.length === 0);
    }
    // absence is the guide's cells' to show: no "Not asked in", no "No quotes from this question"
    expect(screen.queryByText(/Not asked in/)).toBeNull();
    expect(screen.queryByText(/No quotes from this question/)).toBeNull();
  });

  it("All loses no quote: before the first question, under a question, or under an unclassified ask", () => {
    // one asked turn the model never classified (its answers go with it), and one quote before
    // the first question — the two places a quote can sit outside the guide's questions
    const t = data.turns.find((x) => x.session === "s1" && x.item
      && data.quotes.some((q) => q.session === "s1" && q.sec >= x.sec))!;
    const first = Math.min(...data.turns.filter((x) => x.session === "s2").map((x) => x.sec));
    const early = { ...data.quotes.find((q) => q.session === "s2")!, key: "early", dom_id: "q-early-1", sec: Math.max(0, first - 30), text: "Before anything was asked" };
    const d: DiscussionData = {
      ...data,
      turns: data.turns.map((x) => (x.id === t.id ? { ...x, kind: "unclassified" as const, item: null } : x)),
      quotes: [...data.quotes, early],
    };
    const { container } = view(d);
    const cards = container.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)");
    expect(cards).toHaveLength(d.quotes.length);
    expect(screen.getByText("Before anything was asked")).toBeInTheDocument();
    expect(container.querySelector(`.dl-leftovers .dl-ask[data-turn="${t.id}"]`)!.textContent).toContain("not classified");
    // the header says what the session lines say, summed
    expect(container.querySelector(".dl-meta .dl-stats")!.textContent).toContain(`${d.quotes.length} quotes`);
  });

  it("All is the same evidence whichever navigator tab is showing", () => {
    const { container } = render(<DiscussionView data={data} />);
    const count = () => container.querySelectorAll(".dl-content .dl-item").length;
    const quotes = () => container.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)").length;
    const before = [count(), quotes()];
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    expect([count(), quotes()]).toEqual(before);
  });

  it("a session that could not be read is never said to be 'not asked'", () => {
    const sessions = data.sessions.map((s, i) => (i === 0 ? { ...s, state: "no_moderator" as const } : s));
    // as the stage writes it: the session's turns unclassified, and no question records an ask there
    const d = {
      ...data, sessions,
      turns: data.turns.map((t) => (t.session === "s1" ? { ...t, item: null, kind: "unclassified" as const } : t)),
      sections: data.sections.map((sec) => ({
        ...sec, items: sec.items.map((it) => ({ ...it, asks: it.asks.filter((a) => a.session !== "s1") })),
      })),
    };
    const L = layout(800);
    try {
    const { container } = render(<DiscussionView data={d} />);
    // no "Not asked in" line at all since 19 Oct 2026; its cells say "not classified" (below)
    expect(screen.queryByText(/Not asked in/)).toBeNull();
    // and its quotes are not "before the first question": it had none
    const beforePart = [...container.querySelectorAll(".dl-part")].find((h) => h.textContent === "Before the first question");
    expect(beforePart?.parentElement?.querySelector(".dl-from")?.textContent ?? "").not.toMatch(/^#1/);
    const s1 = d.quotes.filter((q) => q.session === "s1").length;
    expect(container.querySelectorAll(".dl-leftovers blockquote.quote-card:not(.dl-ask)").length).toBeGreaterThanOrEqual(s1);
    const cells = [...container.querySelectorAll(".dl-row .dl-cell")].filter((c) => c.getAttribute("aria-label")?.startsWith("#1"));
    expect(cells.length).toBeGreaterThan(0);
    for (const c of cells) expect(c.getAttribute("aria-label")).toMatch(/not classified$/);
    } finally {
      L.restore();
    }
  });

  it("a session shows that session's questions and quotes, in the order they were asked", () => {
    const { container } = render(<DiscussionView data={data} />);
    onSession(1);
    expect(heading()).toBe("Session 1");
    const asked = data.turns.filter((t) => t.session === "s1" && t.item).length;
    expect(container.querySelectorAll(".dl-content .dl-ask")).toHaveLength(asked);
    const quotes = data.quotes.filter((q) => q.session === "s1").length;
    expect(container.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)")).toHaveLength(quotes);
  });

  it("Merged shows the promoted new section, without a badge (as mocked up)", () => {
    render(<DiscussionView data={data} />);
    const emergent = data.sections.find((s) => s.origin === "emergent")!;
    const head = within(nav()).getByText(emergent.title, { exact: false });
    expect(head.closest(".toc-heading")!.querySelector(".badge")).toBeNull();
  });

  it("Planned shows the guide as written, every line with the solid dot", () => {
    const { container } = render(<DiscussionView data={data} />);
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    const rows = container.querySelectorAll(".dl-nav .dl-row");
    expect(rows).toHaveLength(data.spine.reduce((n, s) => n + s.items.length, 0));
    expect(container.querySelectorAll(".dl-nav .dl-dot.hollow")).toHaveLength(0);
    expect(container.querySelectorAll(".dl-nav .dl-row .dl-mk .dl-dot")).toHaveLength(rows.length);
  });

  it("a header session switches the column and marks itself as here", () => {
    render(<DiscussionView data={data} />);
    const s2 = data.sessions[1];
    const btn = screen.getByRole("radio", { name: new RegExp(`^#${s2.number}`) });
    fireEvent.click(btn);
    expect(heading()).toBe(`Session ${s2.number}`);
    expect(btn).toHaveAttribute("aria-checked", "true");
    // option C: the navigator's selection vocabulary, no ring
    expect(btn.querySelector(".bn-person-badge-here .bn-person-badge")).not.toBeNull();
    expect(btn.querySelector(".bn-person-badge-highlighted")).toBeNull();
  });

  it("digit keys pick a session, unless another handler already claimed the key", () => {
    render(<DiscussionView data={data} />);
    fireEvent.keyDown(document, { key: "3" });
    expect(heading()).toBe("Session 3");
    const ev = new KeyboardEvent("keydown", { key: "1", bubbles: true, cancelable: true });
    ev.preventDefault();
    act(() => {
      document.dispatchEvent(ev);
    });
    expect(heading()).toBe("Session 3");
  });

  it("clicking a row locks focus on its questions; clicking again or Esc clears it", () => {
    const { container } = render(<DiscussionView data={data} />);
    const it = data.sections.flatMap((s) => s.items).find((i) => i.asks.some((a) => a.session === "s1"))!;
    const row = container.querySelector(`.dl-row[data-id="${it.id}"] .dl-row-btn`)!;
    fireEvent.click(row);
    expect(container.querySelector(".dl-lens")).toHaveClass("has-focus");
    const hot = [...container.querySelectorAll(".dl-ask.hot")].map((e) => (e as HTMLElement).dataset.item);
    expect(hot.length).toBeGreaterThan(0);
    expect(new Set(hot)).toEqual(new Set([it.id]));
    fireEvent.click(row);
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
    fireEvent.click(row);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
  });

  it("View ▸ Next/Previous Question steps the navigator's focus through asked questions, wrapping", () => {
    const { container } = render(<DiscussionView data={data} />);
    const menu = (action: string) =>
      act(() => {
        window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action } }));
      });
    const focused = () => (container.querySelector(".dl-ask.hot") as HTMLElement | null)?.dataset.item;
    const rows = [...container.querySelectorAll<HTMLElement>(".dl-nav .dl-row")]
      .map((r) => r.dataset.id!)
      .filter((id) => data.sections.flatMap((s) => s.items).find((i) => i.id === id)!.asks.length > 0);
    expect(rows.length).toBeGreaterThan(2);
    menu("nextQuestion");
    expect(focused()).toBe(rows[0]);
    menu("nextQuestion");
    expect(focused()).toBe(rows[1]);
    menu("previousQuestion");
    menu("previousQuestion");
    expect(focused()).toBe(rows[rows.length - 1]);
  });

  it("focusing a row the current session never asked jumps to a session that did", () => {
    const { container } = render(<DiscussionView data={data} />);
    onSession(1);
    const elsewhere = data.sections.flatMap((s) => s.items)
      .find((i) => i.asks.length && !i.asks.some((a) => a.session === "s1"))!;
    const first = data.sessions.find((s) => elsewhere.asks.some((a) => a.session === s.id))!;
    fireEvent.click(container.querySelector(`.dl-row[data-id="${elsewhere.id}"] .dl-row-btn`)!);
    expect(heading()).toBe(`Session ${first.number}`);
    expect(container.querySelector(".dl-ask.hot")).not.toBeNull();
  });

  it("clicking a question focuses that one ask, and its quotes, only", () => {
    const { container } = render(<DiscussionView data={data} />);
    const answered = container.querySelector(".dl-group .dl-ask + .dl-card")!
      .previousElementSibling as HTMLElement;
    fireEvent.click(within(answered).getByRole("button", { pressed: false }));
    expect(container.querySelectorAll(".dl-ask.hot")).toHaveLength(1);
    const lit = container.querySelectorAll(`.dl-card.hot[data-for="${answered.dataset.turn}"]`);
    expect(lit.length).toBeGreaterThan(0);
  });

  it("a session's cell in a row opens that session at that question; a not-asked cell does nothing", () => {
    const L = layout(800);
    try {
    const { container } = render(<DiscussionView data={data} />);
    const multi = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const target = data.sessions.find((s) => s.id !== "s1" && multi.asks.some((a) => a.session === s.id))!;
    const cells = within(container.querySelector(`.dl-row[data-id="${multi.id}"] .dl-cells`) as HTMLElement);
    const cell = cells.getByRole("button", { name: new RegExp(`^#${target.number} `) });
    expect(cell.tabIndex).toBe(-1); // reached from the session bar, not one tab stop per session
    expect(container.querySelector(".dl-cells.lit")).toBeNull(); // All lights no column
    fireEvent.click(cell);
    expect(heading()).toBe(`Session ${target.number}`);
    expect(container.querySelector(`.dl-row[data-id="${multi.id}"]`)).toHaveClass("active");
    expect(cell).toHaveClass("here");
    // The selected column: every strip carries the band at that session's index. Arriving from
    // All it appears; only a move from one session to another slides.
    const strips = () => [...container.querySelectorAll<HTMLElement>(".dl-nav .dl-cells")];
    const at = (sid: string) => String(data.sessions.findIndex((s) => s.id === sid));
    expect(strips().length).toBeGreaterThan(0);
    for (const st of strips()) {
      expect(st).toHaveClass("lit");
      expect(st).not.toHaveClass("slide");
      expect(st.style.getPropertyValue("--dl-here")).toBe(at(target.id));
    }
    const other = data.sessions.find((s) => s.id !== target.id && multi.asks.some((a) => a.session === s.id))!;
    fireEvent.click(cells.getByRole("button", { name: new RegExp(`^#${other.number} `) }));
    for (const st of strips()) {
      expect(st).toHaveClass("slide");
      expect(st.style.getPropertyValue("--dl-here")).toBe(at(other.id));
    }
    fireEvent.click(cells.getByRole("button", { name: new RegExp(`^#${target.number} `) }));
    const elsewhere = data.sections.flatMap((s) => s.items).find((i) => i.asks.length && !i.asks.some((a) => a.session === "s1"))!;
    const notAsked = container.querySelector(`.dl-row[data-id="${elsewhere.id}"] .dl-cell[aria-disabled="true"]`)!;
    expect(notAsked.getAttribute("aria-label")).toMatch(/Not asked$/);
    fireEvent.click(notAsked);
    expect(heading()).toBe(`Session ${target.number}`);
      } finally {
      L.restore();
    }
  });

  it("a row describes where it was asked and what it drew, as a count, never a fraction", () => {
    const { container } = render(<DiscussionView data={data} />);
    const answers = itemAnswers(data);
    const it = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const asked = new Set(it.asks.map((a) => a.session)).size;
    const quotes = data.sessions.reduce((n, sess) => n + cellQuotes(answers, it.id, sess.id), 0);
    const btn = container.querySelector(`.dl-row[data-id="${it.id}"] .dl-row-btn`)!;
    const said = btn.getAttribute("aria-describedby")!.split(" ").map((id) => document.getElementById(id)!.textContent);
    expect(said).toEqual([`Asked in ${asked} sessions`, `${quotes} ${quotes === 1 ? "quote" : "quotes"}`]);
    expect(said.join(" ")).not.toMatch(/ of /);
  });

  it("a cell's label says what the session gave: a count, who of a group, or asked with none", () => {
    const answers = itemAnswers(data);
    // a group session: s1 has three people, and its quotes come from p1 only
    const group = { ...data, sessions: data.sessions.map((s, i) => (i === 0 ? { ...s, participants: [
      s.participants[0], { code: "p8", name: "Ana" }, { code: "p9", name: "Joe" }] } : s)) };
    const zero = [...answers].flatMap(([item, m]) => [...m.keys()].map((sid) => ({ item, sid })))
      .find(({ item, sid }) => cellQuotes(answers, item, sid) === 0);
    const L = layout(800);
    try {
      const { container } = render(<DiscussionView data={group} />);
      const it = data.sections.flatMap((s) => s.items).find((i) => i.asks.some((a) => a.session === "s1")
        && cellQuotes(answers, i.id, "s1") > 0)!;
      const n = cellQuotes(answers, it.id, "s1");
      const cell = container.querySelector(`.dl-row[data-id="${it.id}"] .dl-cell`)!;
      expect(cell.getAttribute("aria-label")).toMatch(new RegExp(` · ${n} quotes? from 1 of 3 people$`));
      if (zero) {
        const i = data.sessions.findIndex((s) => s.id === zero.sid);
        const z = container.querySelectorAll(`.dl-row[data-id="${zero.item}"] .dl-cell`)[i];
        expect(z.getAttribute("aria-label")).toMatch(/ · Asked, no quotes$/);
        expect(z).toHaveClass("s0"); // drawn as not asked (decided 18 Oct)
      }
      expect(zero).toBeDefined(); // the fixture carries one asked-with-no-quotes cell
    } finally {
      L.restore();
    }
  });

  it("a session's lead-in in All opens that session at that question", async () => {
    const { container } = render(<DiscussionView data={data} />);
    const multi = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const target = data.sessions.find((s) => s.id !== "s1" && multi.asks.some((a) => a.session === s.id))!;
    const block = within(container.querySelector(`.dl-item[data-item="${multi.id}"]`) as HTMLElement);
    const lead = block.getByRole("button", { name: new RegExp(`^#${target.number}`) });
    expect(lead).toHaveAttribute("title", `Show session ${target.number}`);
    lead.focus();
    fireEvent.click(lead);
    expect(heading()).toBe(`Session ${target.number}`);
    expect(container.querySelector(`.dl-row[data-id="${multi.id}"]`)).toHaveClass("active");
    // the lead-in is gone with the All column: focus goes to the question it opened, not the page
    await act(async () => { await new Promise((r) => requestAnimationFrame(() => r(null))); });
    expect(document.activeElement).toHaveClass("dl-ask-btn");
    expect(document.activeElement!.closest(".dl-ask")).toHaveClass("hot");
  });

  it("each cell is shaded by the quotes it drew, in the study's thirds, and the row says its totals", () => {
    const L = layout(800);
    try {
      const { container } = render(<DiscussionView data={data} />);
      const answers = itemAnswers(data);
      const counts: number[] = [];
      for (const [item, bySession] of answers) for (const sid of bySession.keys()) counts.push(cellQuotes(answers, item, sid));
      const thirds = yieldThirds(counts);
      const steps = new Set<string>();
      for (const r of container.querySelectorAll<HTMLElement>(".dl-nav .dl-row")) {
        const it = data.sections.flatMap((s) => s.items).find((i) => i.id === r.dataset.id)!;
        const cells = [...r.querySelectorAll(".dl-cell")];
        expect(cells).toHaveLength(data.sessions.length);
        data.sessions.forEach((sess, i) => {
          const asked = it.asks.some((a) => a.session === sess.id);
          const want = asked ? `s${shadeStep(cellQuotes(answers, it.id, sess.id), thirds)}` : "s0";
          expect(cells[i]).toHaveClass(want);
          steps.add(want);
        });
        const total = data.sessions.reduce((n, sess) => n + cellQuotes(answers, it.id, sess.id), 0);
        expect(r.querySelector(".tag-count")!.textContent).toBe(String(total));
      }
      // asked cells are shaded, not all drawn as not asked (the fixture's cells all drew one
      // quote, so all take the middle step; the ranking itself is model.test.ts's)
      expect([...steps].some((x) => x !== "s0")).toBe(true);
    } finally {
      L.restore();
    }
  });

  it("the split is a keyboard-operable separator that remembers its width", () => {
    render(<DiscussionView data={data} />);
    const split = screen.getByRole("separator", { name: "Resize the discussion guide" });
    fireEvent.keyDown(split, { key: "Home" });
    expect(split).toHaveAttribute("aria-valuenow", "200");
    fireEvent.keyDown(split, { key: "ArrowRight" });
    // jsdom measures every width as 0, so the step lands relative to the floor
    expect(Number(split.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(200);
  });

  it("names a group session in the list form, capped past two", () => {
    const group: DiscussionData = {
      ...data,
      sessions: data.sessions.map((s, i) => i === 0 ? { ...s, participants: [
        { code: "p1", name: "Bettina" }, { code: "p5", name: "Priya" }, { code: "p6", name: "Christopher" },
      ] } : s),
    };
    render(<DiscussionView data={group} />);
    expect(screen.getByRole("radio", { name: /^#1/ }).textContent).toContain("Bettina and 2 others");
    expect(screen.getByRole("radio", { name: /^#1/ })).toHaveAttribute("title", "Session 1: Bettina, Priya and Christopher");
    // the accessible name carries the visible "#1" and every name in full
    expect(screen.getByRole("radio", { name: "#1 Bettina, Priya and Christopher" })).toBeInTheDocument();
  });
});

describe("quotes work as they do everywhere else (decided 19 Oct 2026)", () => {
  /** A quote under an asked question, its question and its session. */
  function answered() {
    const answers = itemAnswers(data);
    for (const [item, bySession] of answers) {
      for (const [sid, asks] of bySession) {
        for (const a of asks) if (a.answers.length) return { item, sid, turn: a.turn, q: a.answers[0] };
      }
    }
    throw new Error("the fixture has no answered question");
  }
  /** Hide through the store, and wait until it has landed (the card collapses first). */
  async function hide(ids: string[]) {
    act(() => hideQuotes(ids));
    await waitFor(() => expect(ids.every((d) => getQuotesSnapshot().hidden[d])).toBe(true),
      { timeout: HIDE_DURATION * 10 });
  }
  const card = (container: HTMLElement, id: string) => container.querySelector(`.dl-card > blockquote#${CSS.escape(id)}`);
  const total = (container: HTMLElement, item: string) =>
    Number(container.querySelector(`.dl-row[data-id="${item}"] .tag-count`)!.textContent);

  it("every quote is the report's own card: it plays, opens its transcript, stars, hides and tags", () => {
    const { q } = answered();
    const { container } = view(data);
    const el = card(container, q.dom_id!) as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.querySelector("a.timecode")).toHaveAttribute("data-participant", q.participant);
    expect(el.querySelector("a.speaker-link")!.getAttribute("href")).toContain(`/report/sessions/${q.session}#t-${Math.floor(q.sec)}`);
    expect(el.querySelector(".hide-btn")).not.toBeNull();
    expect(el.querySelector(".badge-add")).not.toBeNull();
    fireEvent.click(el.querySelector(".star-btn")!);
    expect(getQuotesSnapshot().starred[q.dom_id!]).toBe(true);
    expect(card(container, q.dom_id!)).toHaveClass("starred");
  });

  it("a quote the report does not hold is not drawn: nothing could star or hide it", () => {
    const { q } = answered();
    const d = { ...data, quotes: data.quotes.map((x) => (x.key === q.key ? { ...x, dom_id: undefined } : x)) };
    const { container } = view(d);
    expect(container.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)")).toHaveLength(data.quotes.length - 1);
  });

  it("a hidden quote leaves the lens and its counts, and is counted beside its question, with a way back", async () => {
    const { item, q } = answered();
    const { container } = view(data);
    const before = total(container, item);
    await hide([q.dom_id!]);
    expect(card(container, q.dom_id!)).toBeNull();
    expect(total(container, item)).toBe(before - 1);
    // All: the question's heading is the Quotes lens's group header, its counter beside it
    const head = container.querySelector(`.dl-item[data-item="${item}"] > .bn-group-header`)!;
    expect(within(head as HTMLElement).getByText(/1 hidden quote/)).toBeInTheDocument();
    fireEvent.click(within(head as HTMLElement).getByRole("button", { name: /1 hidden quote/ }));
    fireEvent.click(within(head as HTMLElement).getByRole("button", { name: /Unhide/ }));
    expect(card(container, q.dom_id!)).not.toBeNull();
    expect(total(container, item)).toBe(before);
  });

  it("in a session, a hidden quote is counted at the foot of its question's block", async () => {
    const { sid, turn, q } = answered();
    const { container } = view(data);
    onSession(Number(sid.slice(1)));
    await hide([q.dom_id!]);
    const block = container.querySelector(`.dl-ask[data-turn="${CSS.escape(turn.id)}"]`)!.closest(".dl-group")!;
    expect(block.querySelector(".dl-hidden-foot")!.textContent).toMatch(/1 hidden quote/);
  });

  it("a question with nothing to show is its grey heading alone, and its guide row is grey", async () => {
    const { item } = answered();
    const { container } = view(data);
    // hide every quote under the question, in every session
    const answers = itemAnswers(data);
    const under = [...(answers.get(item)?.values() ?? [])].flatMap((asks) => asks.flatMap((a) => a.answers.map((x) => x.dom_id!)));
    await hide(under);
    const block = container.querySelector(`.dl-item[data-item="${item}"]`)!;
    expect(block).toHaveClass("empty");
    expect(block.querySelectorAll(".dl-group")).toHaveLength(0);
    expect(block.querySelector(".bn-group-header h3")!.textContent).toBe(
      container.querySelector(`.dl-row[data-id="${item}"] .dl-tx`)!.textContent);
    expect(within(block as HTMLElement).getByText(new RegExp(`${under.length} hidden quote`))).toBeInTheDocument();
    expect(container.querySelector(`.dl-row[data-id="${item}"]`)).toHaveClass("ghost");
  });

  it("a session's row is grey where it asked a question that drew nothing to show", async () => {
    const { item, sid } = answered();
    const answers = itemAnswers(data);
    const under = (answers.get(item)?.get(sid) ?? []).flatMap((a) => a.answers.map((x) => x.dom_id!));
    const { container } = view(data);
    onSession(Number(sid.slice(1)));
    expect(container.querySelector(`.dl-row[data-id="${item}"]`)).not.toHaveClass("ghost");
    await hide(under);
    expect(container.querySelector(`.dl-row[data-id="${item}"]`)).toHaveClass("ghost");
    // the question stays in the session's own column, folded forward, and says nothing about it
    expect(container.querySelector(`.dl-content .dl-ask[data-item="${item}"]`)).not.toBeNull();
    expect(screen.queryByText(/No quotes from this question/)).toBeNull();
  });

  it("a question row's timecode plays its session and its badge opens the transcript there", () => {
    const { turn } = answered();
    const { container } = view(data);
    const ask = container.querySelector(`.dl-ask[data-turn="${CSS.escape(turn.id)}"]`)!;
    // keyed by session: a moderator's code is not unique across sessions
    expect(ask.querySelector("a.timecode")).toHaveAttribute("data-participant", turn.session);
    expect(ask.querySelector("a.speaker-link")!.getAttribute("href")).toContain(`/report/sessions/${turn.session}#t-${Math.floor(turn.sec)}`);
    // a moment in the recording, not a quote
    expect(ask.querySelector(".star-btn, .hide-btn, .badge-add")).toBeNull();
  });

  it("says it is loading until the report's quotes are in, and says so if they cannot be loaded", async () => {
    resetStore();
    let fail: (e: Error) => void = () => {};
    api.apiGet.mockImplementation((path: string) =>
      path === "/quotes" ? new Promise((_, reject) => { fail = reject; }) : route(path));
    render(<DiscussionView data={data} />);
    // never a lens of unanswered questions while the quotes are on their way
    expect(screen.getByText(/Loading/)).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByTestId("discussion-lens")).toBeNull();
    const err = vi.spyOn(console, "error").mockImplementation(() => {});
    await act(async () => fail(new Error("GET /quotes 500")));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    err.mockRestore();
  });

  it("two quotes sharing a report id (one second) draw one card, the store's own, once", () => {
    const { q } = answered();
    // a second quote half a second later: the same id, other words, and the store holds the first
    const twin = { ...q, key: "twin", sec: q.sec + 0.5, text: "Words the store does not hold" };
    const d = { ...data, quotes: [...data.quotes, twin] };
    const { container } = render(<DiscussionView data={d} />);
    expect(container.querySelectorAll(`#${CSS.escape(q.dom_id!)}`)).toHaveLength(1);
    expect(container.querySelector(".dl-content")!.textContent).not.toContain("Words the store does not hold");
  });

  it("a record quote whose id the report does not hold is neither drawn nor counted", () => {
    const { item, q } = answered();
    const d = { ...data, quotes: data.quotes.map((x) => (x.key === q.key ? { ...x, dom_id: "q-nobody-1" } : x)) };
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<DiscussionView data={d} />); // the store holds the fixture's ids
    expect(container.querySelector(".dl-content")!.textContent).not.toContain(q.text);
    const want = [...(itemAnswers(data).get(item)?.values() ?? [])].flat().reduce((n, a) => n + a.answers.length, 0) - 1;
    expect(total(container, item)).toBe(want);
    expect(warn).toHaveBeenCalledWith(expect.stringMatching(/1 quote\(s\) in the record are not in the report/));
    warn.mockRestore();
  });

  it("a hidden quote from before the first question is counted there, in All and in its session", async () => {
    const first = Math.min(...data.turns.filter((x) => x.session === "s2").map((x) => x.sec));
    const early = { ...data.quotes.find((q) => q.session === "s2")!, key: "early", dom_id: "q-early-1",
      sec: Math.max(0, first - 30), text: "Before anything was asked" };
    const d: DiscussionData = { ...data, quotes: [...data.quotes, early] };
    const { container } = view(d);
    await hide(["q-early-1"]);
    const part = [...container.querySelectorAll(".dl-part")].find((h) => h.textContent === "Before the first question")!;
    expect(part.parentElement!.querySelector(".dl-hidden-foot")!.textContent).toMatch(/1 hidden quote/);
    onSession(2);
    const block = container.querySelector(".dl-content .dl-group")!;
    expect(block.querySelector(".dl-hidden-foot")!.textContent).toMatch(/1 hidden quote/);
  });

  it("in All, an ask the model never classified shows only with quotes, and its hidden ones are counted", async () => {
    const t = data.turns.find((x) => x.item && data.quotes.some((q) => q.session === x.session && q.sec >= x.sec))!;
    const d: DiscussionData = {
      ...data, turns: data.turns.map((x) => (x.id === t.id ? { ...x, kind: "unclassified" as const, item: null } : x)),
    };
    const { container } = view(d);
    const mine = quoteTurns(d);
    const under = d.quotes.filter((q) => mine.get(q.dom_id!) === t.id).map((q) => q.dom_id!);
    expect(under.length).toBeGreaterThan(0);
    expect(container.querySelector(`.dl-leftovers .dl-ask[data-turn="${CSS.escape(t.id)}"]`)).not.toBeNull();
    await hide(under);
    expect(container.querySelector(`.dl-leftovers .dl-ask[data-turn="${CSS.escape(t.id)}"]`)).toBeNull();
    expect(container.querySelector(".dl-leftovers .dl-hidden-foot")!.textContent)
      .toMatch(new RegExp(`${under.length} hidden quote`));
  });

  it("an arrival lands once: hiding a quote afterwards does not scroll back to it", async () => {
    const { discussionPath } = await import("./discussionLinks");
    window.history.replaceState(null, "", discussionPath("s5.1", "s2@01:26"));
    const into = vi.fn();
    const real = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = into;
    try {
      const { container } = view(data);
      const landed = into.mock.calls.length;
      expect(landed).toBeGreaterThan(0);
      const some = container.querySelector(".dl-card > blockquote.quote-card")!.id;
      await hide([some]);
      // the hide re-folds the column, so match the asking by its turn, not the element
      expect(into.mock.calls.length).toBe(landed);
      expect(into.mock.contexts.filter((el) => (el as Element).getAttribute("data-turn") === "s2@01:26")).toHaveLength(1);
    } finally {
      Element.prototype.scrollIntoView = real;
      window.history.replaceState(null, "", "/");
    }
  });

  it("registers its cards in reading order for j/k and ⌘A, and Esc clears the card before the question", () => {
    let focus: ReturnType<typeof useFocus> | null = null;
    function Probe() {
      focus = useFocus();
      return null;
    }
    seed(data);
    const { container } = render(<FocusProvider><Probe /><DiscussionView data={data} /></FocusProvider>);
    const drawn = Array.from(container.querySelectorAll(".dl-card > blockquote.quote-card"), (b) => b.id);
    expect(focus!.getVisibleQuoteIds()).toEqual(drawn);
    const row = screen.getAllByRole("button", { pressed: false }).find((b) => b.classList.contains("dl-row-btn"))!;
    fireEvent.click(row);
    expect(row).toHaveAttribute("aria-pressed", "true");
    act(() => focus!.setFocus(drawn[0], { scroll: false }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(row).toHaveAttribute("aria-pressed", "true"); // the card goes first (the report's cascade)
    act(() => focus!.setFocus(null));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(row).toHaveAttribute("aria-pressed", "false");
  });
});

describe("review fixes, 3 Oct 2026", () => {
  it("arrow keys move the session radio group, with one tab stop", () => {
    render(<DiscussionView data={data} />);
    const radios = within(screen.getByRole("radiogroup", { name: "Sessions" })).getAllByRole("radio");
    expect(radios.map((r) => r.getAttribute("aria-label")?.split(" ")[0])).toEqual(["All", "#1", "#2", "#3"]);
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1, -1]);
    fireEvent.keyDown(radios[0], { key: "ArrowRight" });
    expect(heading()).toBe("Session 1");
    fireEvent.keyDown(radios[1], { key: "End" });
    expect(heading()).toBe("Session 3");
    fireEvent.keyDown(radios[3], { key: "ArrowRight" });  // wraps, to All
    expect(heading()).toBe("All sessions");
  });

  it("digit keys do nothing while a dialog owns the keyboard", () => {
    const root = document.createElement("div");
    root.id = "bn-app-root";
    document.body.appendChild(root);
    render(<DiscussionView data={data} />);
    root.setAttribute("inert", "");
    fireEvent.keyDown(document, { key: "2" });
    expect(heading()).toBe("All sessions");
    root.removeAttribute("inert");
    fireEvent.keyDown(document, { key: "2" });
    expect(heading()).toBe("Session 2");
  });

  it("clearing a row's focus never moves the reader to another session", () => {
    const { container } = render(<DiscussionView data={data} />);
    onSession(1);
    const elsewhere = data.sections.flatMap((s) => s.items)
      .find((i) => i.asks.length && !i.asks.some((a) => a.session === "s1"))!;
    const btn = container.querySelector(`.dl-row[data-id="${elsewhere.id}"] .dl-row-btn`)!;
    fireEvent.click(btn);                         // jumps to a session that asked it
    const landed = heading();
    fireEvent.keyDown(document, { key: "1" });    // reader moves on
    fireEvent.click(btn);                         // still focused on the row: this clears
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
    expect(heading()).toBe("Session 1");
    expect(landed).not.toBe("Session 1");
  });

  it("names the views Normalised questions then Your guide, in that order", () => {
    render(<DiscussionView data={data} />);
    const radios = within(screen.getByRole("radiogroup", { name: "Show" })).getAllByRole("radio");
    expect(radios.map((r) => r.textContent)).toEqual(["Normalised questions", "Your guide"]);
    expect(radios.map((r) => r.getAttribute("title"))).toEqual([
      "What was asked in every session, merged with your guide",
      "Your discussion guide, as written",
    ]);
  });

  it("Your guide offers Summary or Original; Original shows the guide's own wording", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.queryByRole("radiogroup", { name: "Show your guide as" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    const views = screen.getByRole("radiogroup", { name: "Show your guide as" });
    expect(within(views).getByRole("radio", { name: "Summary" })).toBeChecked();
    const first = data.spine.find((sec) => sec.items.length && sec.kind !== "instruction")!.items[0];
    const text = () => container.querySelector(`.dl-row[data-id="${first.id}"] .dl-tx`)!.textContent;
    expect(text()).toBe(first.terse);
    fireEvent.click(within(views).getByRole("radio", { name: "Original" }));
    expect(text()).toBe(first.text);
  });

  it("a line never asked in any session does not take focus (no dead click)", () => {
    const { container } = render(<DiscussionView data={data} />);
    const never = data.sections.flatMap((s) => s.items).find((i) => !i.asks.length)!;
    const btn = container.querySelector(`.dl-row[data-id="${never.id}"] .dl-row-btn`)!;
    expect(btn).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(btn);
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
    expect(heading()).toBe("All sessions");
  });

  it("with no guide there is no Planned view to offer", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    expect(screen.queryByRole("radio", { name: "Your guide" })).toBeNull();
  });

  it("a turn the model never classified is shown, marked, and wired to nothing", () => {
    const t = data.turns.find((x) => x.session === "s1" && x.kind === "chat")!;
    const d = { ...data, turns: data.turns.map((x) => (x.id === t.id ? { ...x, kind: "unclassified" as const } : x)) };
    const { container } = render(<DiscussionView data={d} />);
    onSession(1);
    const row = container.querySelector(`.dl-ask[data-turn="${t.id}"]`)!;
    expect(row).not.toBeNull();
    expect(row.textContent).toContain("not classified");
    expect((row as HTMLElement).dataset.item).toBe("");
  });

  it("offers to add or replace the guide with the house small button, and says where the guide goes", () => {
    const { unmount } = render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    expect(screen.queryByRole("button", { name: "Add your guide…" })).toBeNull(); // not on the first tab
    fireEvent.click(screen.getByRole("radio", { name: "Add your guide" }));
    expect(screen.getByRole("heading", { name: "Upload your discussion guide" })).toBeInTheDocument();
    expect(screen.getByText(/See the study as you planned it/)).toBeInTheDocument();
    expect(screen.getByText("Word, Markdown or plain text.")).toBeInTheDocument();
    // the tab is only that: the questions and the key stay on the first tab
    expect(document.querySelectorAll(".dl-nav .dl-row")).toHaveLength(0);
    expect(screen.queryByRole("note", { name: "Key" })).toBeNull();
    const add = screen.getByRole("button", { name: "Add your guide…" });
    expect(add).toHaveClass("bn-btn", "bn-btn-secondary", "bn-btn-sm");
    fireEvent.click(add);
    expect(screen.getByRole("status").textContent).toMatch(/folder named “Discussion guide”/);
    unmount();
    resetLensState(); // the lens remembers its tab between visits
    render(<DiscussionView data={data} />);
    expect(screen.queryByRole("button", { name: /your guide…/ })).toBeNull(); // Normalised, with a guide
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    expect(screen.getByRole("button", { name: "Replace your guide…" })).toBeInTheDocument();
  });

  it("each tab carries a key at the top, of the marks it shows", () => {
    render(<DiscussionView data={data} />);
    // grey explains itself: no key line says what it means, in All or in a session (19 Oct 2026)
    expect(within(screen.getByRole("note", { name: "Key" })).queryByText(/^Grey:/)).toBeNull();
    onSession(1);
    const key = screen.getByRole("note", { name: "Key" });
    expect(key).toHaveClass("bn-pipeline-key");
    expect(within(key).queryByText(/^Grey:/)).toBeNull();
    for (const t of ["Asked as planned", "Planned, never asked", "Not in your guide"]) {
      expect(within(key).getByText(t, { exact: false })).toBeInTheDocument();
    }
    // above the first section, so it scrolls away
    expect(key.nextElementSibling?.getAttribute("role")).toBe("group");
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    const planned = screen.getByRole("note", { name: "Key" });
    expect(within(planned).getByText("Asked as planned", { exact: false })).toBeInTheDocument();
    expect(within(planned).queryByText("Not in your guide", { exact: false })).toBeNull(); // no + rows here
  });

  it("each mark explains itself on hover, the house ? cursor way", () => {
    const { container } = render(<DiscussionView data={data} />);
    const tips = new Set([...container.querySelectorAll(".dl-row .dl-mk")].map((m) => m.getAttribute("title")));
    expect(tips).toEqual(new Set([
      "In your guide, and asked", "In your guide, never asked in any session",
      "Not in your guide — asked as it came up",
    ]));
  });

  it("every navigator row says its provenance in words, not only by its mark", () => {
    const { container } = render(<DiscussionView data={data} />);
    const rows = [...container.querySelectorAll(".dl-row-btn")];
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) expect(r.querySelector(".bn-sr-only")!.textContent).toMatch(/planned|not in the guide/);
  });

  it("section titles in the navigator are headings, labelling their rows", () => {
    render(<DiscussionView data={data} />);
    const first = data.sections.find((s) => s.items.length)!;
    expect(within(nav()).getByRole("group", { name: new RegExp(first.title) })).toBeInTheDocument();
    expect(within(nav()).getAllByRole("heading", { level: 2 }).length).toBe(data.sections.length);
  });

  it("the measure is chosen by measuring the guide and its one-digit head, and holds", () => {
    // 3 sessions; the guide's text keeps 130px, its row chrome and gaps 50px: room = nav − 180.
    // The grid needs 3 × pitch + 72 (+20 to step up into it); the strip 3 × 8 + 28.
    const L = layout(380, 19); // pitch 23: 69 + 72 + 20 = 161 ≤ 200 → grid
    try {
      const { container } = render(<DiscussionView data={data} />);
      const lens = () => container.querySelector(".dl-lens")!;
      expect(lens()).toHaveClass("dl-m-grid");
      expect((lens() as HTMLElement).style.getPropertyValue("--dl-pitch")).toBe("23px");
      // the heads: one-digit compact badges, none lit in All, the selected one lit in a session
      expect(container.querySelectorAll(".dl-grid-head .bn-person-badge-compact")).toHaveLength(data.sessions.length);
      expect(container.querySelector(".dl-grid-head .bn-person-badge-here")).toBeNull();
      onSession(2);
      expect(container.querySelectorAll(".dl-grid-head .bn-person-badge-here")).toHaveLength(1);
      // the probe decides: a wider head (pitch 44: 132 + 72 = 204 > 200) cannot hold the grid
      L.resize({ probe: 40 });
      expect(lens()).toHaveClass("dl-m-strip");
      expect(container.querySelector(".dl-grid-head")).toBeNull();
      expect(container.querySelector(".dl-cells")).not.toBeNull();
      // stepping back up needs 20px to spare, so a scrollbar's width cannot flip it to and fro
      L.resize({ probe: 19, nav: 330 }); // 141 ≤ 150, but 161 > 150: stays strip
      expect(lens()).toHaveClass("dl-m-strip");
      L.resize({ nav: 345 });              // 161 ≤ 165: steps up
      expect(lens()).toHaveClass("dl-m-grid");
      L.resize({ nav: 325 });              // 141 ≤ 145: a grid holds without the spare
      expect(lens()).toHaveClass("dl-m-grid");
      L.resize({ nav: 150 });              // under the strip's 52: the bar, and no cells at all
      expect(lens()).toHaveClass("dl-m-bar");
      expect(container.querySelector(".dl-cells")).toBeNull();
      // a folded guide (or an unlaid probe) measures 0 and keeps the tier, never guesses
      L.resize({ nav: 380 });
      expect(lens()).toHaveClass("dl-m-grid");
      L.resize({ nav: 0 });
      expect(lens()).toHaveClass("dl-m-grid");
      L.resize({ nav: 380, probe: 0 });
      expect(lens()).toHaveClass("dl-m-grid");
    } finally {
      L.restore();
    }
  });


  it("remembers All across a lens switch", () => {
    const first = render(<DiscussionView data={data} />);
    onSession(2);
    fireEvent.click(screen.getByRole("radio", { name: "All sessions" }));
    first.unmount();
    render(<DiscussionView data={data} />);
    expect(heading()).toBe("All sessions");
  });

  it("with one session there is no All: it would be that session twice", () => {
    render(<DiscussionView data={{ ...data, sessions: data.sessions.slice(0, 1) }} />);
    expect(screen.queryByRole("radio", { name: "All sessions" })).toBeNull();
    expect(heading()).toBe("Session 1");
  });

  it("remembers mode, session and focus across a lens switch", () => {
    const first = render(<DiscussionView data={data} />);
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    fireEvent.keyDown(document, { key: "3" });
    first.unmount();
    render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Your guide" })).toHaveAttribute("aria-checked", "true");
    expect(heading()).toBe("Session 3");
  });
});

// The record as the server sends it: codes only. Built from the synthetic
// fixture so the shape matches the lens's own data.
const record = {
  ...data,
  sessions: data.sessions.map((s) => ({ ...s, participants: s.participants.map((p) => p.code) })),
  quotes: data.quotes.map(({ key: _key, name: _name, ...q }) => q),
};
const sessionList = data.sessions.map((s) => ({
  session_id: s.id,
  session_number: s.number,
  session_date: null,
  speakers: s.participants.map((p) => ({ speaker_code: p.code, name: p.name, role: "participant" })),
}));

const api = vi.hoisted(() => ({
  apiGet: vi.fn(), getSessionList: vi.fn(), getCodebook: vi.fn(),
  // the quotes store's writes (QuotesContext): fire-and-forget PUTs
  putHidden: vi.fn(), putStarred: vi.fn(), putEdits: vi.fn(), putTags: vi.fn(), putDeletedBadges: vi.fn(),
  acceptProposal: vi.fn(), denyProposal: vi.fn(),
}));
vi.mock("../../utils/api", () => api);
const bridge = vi.hoisted(() => ({ postProjectAction: vi.fn() }));
vi.mock("../../shims/bridge", async (orig) => ({
  ...(await orig<typeof import("../../shims/bridge")>()),
  postProjectAction: bridge.postProjectAction,
}));
const exportState = vi.hoisted(() => ({ on: false }));
vi.mock("../../utils/exportData", async (orig) => ({
  ...(await orig<typeof import("../../utils/exportData")>()),
  isExportMode: () => exportState.on,
}));

function serve(status: string, rec: unknown) {
  api.apiGet.mockImplementation((path: string) =>
    path === "/discussion" ? Promise.resolve({ status, record: rec }) : route(path));
  api.getSessionList.mockResolvedValue(sessionList);
}

describe("DiscussionLens", () => {
  it("loads the record, joins names from the sessions, and renders the lens", async () => {
    serve("ready", record);
    render(<DiscussionLens />);
    expect(await screen.findByTestId("discussion-lens")).toBeInTheDocument();
    expect(api.apiGet).toHaveBeenCalledWith("/discussion");
  });

  it.each([
    ["not_run", null, /no discussion for this project yet/],
    ["stale", null, /quotes have changed since the discussion was built/],
    ["failed", record, /could not be built for this project/],
  ])("says what a %s record means and what to do", async (status, rec, text) => {
    serve(status, rec);
    render(<DiscussionLens />);
    expect(await screen.findByText(text)).toBeInTheDocument();
    expect(screen.queryByTestId("discussion-lens")).toBeNull();
  });

  it.each([
    ["no_moderator", /Discussion lens is for moderated interviews/],
    ["moderator_unreliable", /could not be told apart reliably in any session/],
    ["failed", /could not be built for this project/],
  ])("a failed record whose sessions are all %s says why — re-analyse only where it helps", async (state, text) => {
    serve("failed", { ...record, sessions: record.sessions.map((s) => ({ ...s, state })) });
    render(<DiscussionLens />);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("a server failure is said, not shown as an empty lens", async () => {
    api.apiGet.mockRejectedValue(new Error("GET /discussion 500"));
    api.getSessionList.mockResolvedValue(sessionList);
    render(<DiscussionLens />);
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
  });
});

describe("platform and export copy", () => {
  afterEach(() => {
    exportState.on = false;
    delete document.documentElement.dataset.platform;
    _resetPlatformCache();
  });

  it("the CLI is told to run bristlenose run again", async () => {
    serve("not_run", null);
    render(<DiscussionLens />);
    expect(await screen.findByText(/Run bristlenose run on the project folder again/)).toBeInTheDocument();
  });

  it("the Mac is never sent to Re-analyse, which starts over and discards edits", async () => {
    document.documentElement.dataset.platform = "desktop";
    _resetPlatformCache();
    // The app registers the desktop namespace at start-up when <html> says
    // desktop; this test flips the platform after start-up, so register it here.
    i18n.addResourceBundle("en", "desktop", enDesktop, true, true);
    for (const [status, says] of [
      ["not_run", /choose Analyse from the project’s menu in the sidebar/],
      ["stale", /next time the project is analysed/],
    ] as const) {
      serve(status, null);
      const { unmount } = render(<DiscussionLens />);
      const text = (await screen.findByText(says)).textContent ?? "";
      expect(text).not.toMatch(/re-analyse|bristlenose run/i);
      unmount();
    }
  });

  it("an exported report's reader gets one plain line, not an instruction", async () => {
    exportState.on = true;
    serve("not_run", null);
    render(<DiscussionLens />);
    expect(await screen.findByText("No discussion was built for this report.")).toBeInTheDocument();
  });
});

describe("the guide button in the Mac app", () => {
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    _resetEmbeddedCache();
    bridge.postProjectAction.mockReset();
  });

  it("asks the app for its native panel instead of describing the folder", () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    fireEvent.click(screen.getByRole("radio", { name: "Add your guide" }));
    fireEvent.click(screen.getByRole("button", { name: "Add your guide…" }));
    expect(bridge.postProjectAction).toHaveBeenCalledWith("choose-discussion-guide");
    expect(screen.queryByText(/folder named “Discussion guide”/)).toBeNull();
  });

  it("in a browser it says where the guide goes, and asks nothing of a host", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    fireEvent.click(screen.getByRole("radio", { name: "Add your guide" }));
    fireEvent.click(screen.getByRole("button", { name: "Add your guide…" }));
    expect(bridge.postProjectAction).not.toHaveBeenCalled();
    expect(screen.getByText(/folder named “Discussion guide”/)).toBeInTheDocument();
  });
});

describe("joinNames", () => {
  it("names a code from its own session: p1 is a different person in each", () => {
    const two = {
      ...record,
      sessions: [
        { ...record.sessions[0], id: "s1", participants: ["p1"] },
        { ...record.sessions[0], id: "s2", participants: ["p1"] },
      ],
      quotes: [],
    };
    const list = [
      { session_id: "s1", session_number: 1, session_date: null, speakers: [{ speaker_code: "p1", name: "Asha", role: "participant" }] },
      { session_id: "s2", session_number: 2, session_date: null, speakers: [{ speaker_code: "p1", name: "Ben", role: "participant" }] },
    ];
    const joined = joinNames(two as never, list);
    expect(joined.sessions.map((s) => s.participants[0].name)).toEqual(["Asha", "Ben"]);
  });

  it("names each participant and quote from its own session, by code", () => {
    const joined = joinNames(record as never, sessionList);
    expect(joined.sessions[0].participants).toEqual(data.sessions[0].participants);
    expect(joined.quotes[0].name).toBe(data.quotes[0].name);
  });

  it("leaves a name the sessions list blanked (an anonymised export) blank", () => {
    const blank = sessionList.map((s) => ({ ...s, speakers: s.speakers.map((sp) => ({ ...sp, name: "" })) }));
    const joined = joinNames(record as never, blank);
    expect(joined.sessions.every((s) => s.participants.every((p) => p.name === ""))).toBe(true);
    expect(joined.quotes.every((q) => q.name === "")).toBe(true);
  });
});

describe("language", () => {
  afterEach(async () => {
    await act(async () => { await i18n.changeLanguage("en"); });
  });

  it("re-renders in the new language without remounting (the getters are read live)", async () => {
    render(<DiscussionView data={data} />);
    onSession(1);
    expect(heading()).toBe("Session 1");
    i18n.addResourceBundle("xx", "common", { discussion: { session: "Sitzung {{n}}" } }, true, true);
    await act(async () => { await i18n.changeLanguage("xx"); });
    expect(heading()).toBe("Sitzung 1");
  });
});

describe("degraded records", () => {
  it("a guide that is there but unread says why", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [], guide_problem: "unsupported_format" }} />);
    expect(screen.getByText(/format Bristlenose can’t read/)).toBeInTheDocument();
  });

  it("a session that could not be read says so, never 'no questions'", () => {
    const sessions = data.sessions.map((s, i) => (i === 0 ? { ...s, state: "failed" as const } : s));
    render(<DiscussionView data={{ ...data, sessions }} />);
    // in All, and in the session itself
    expect(screen.getByText(/questions could not be classified/)).toBeInTheDocument();
    onSession(1);
    expect(screen.getByText(/questions could not be classified/)).toBeInTheDocument();
    expect(screen.queryByText("No questions found in this session")).toBeNull();
  });
});


describe("the guide as a left panel (4 Oct 2026)", () => {
  /** The lens measures itself on the next animation frame. */
  async function settle() {
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
  }
  function lensWidth(px: number) {
    return vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(function (this: HTMLElement) {
      return this.classList.contains("dl-lens") ? px : 0;
    });
  }
  afterEach(() => vi.restoreAllMocks());

  it("starts open, with the tabs in the guide's own head", async () => {
    const { container } = render(<DiscussionView data={data} />);
    await settle();
    expect(container.querySelector(".dl-lens")).not.toHaveClass("guide-hidden");
    expect(container.querySelector(".dl-bar-nav .dimension-toggle")).not.toBeNull();
    expect(discussionGuideState().shown).toBe(true);
  });

  it("hidden by the researcher, it stays hidden and the conversation takes the width", async () => {
    setDiscussionGuideOpen(false);
    const { container } = render(<DiscussionView data={data} />);
    await settle();
    expect(container.querySelector(".dl-lens")).toHaveClass("guide-hidden");
    expect(discussionGuideState().shown).toBe(false);
    expect(localStorage.getItem("bn-discussion-guide-open")).toBe("false");
  });

  it("folds when the conversation would fall under its floor, and says so to the app", async () => {
    lensWidth(500); // under 200 guide + 40 wires + 368 floor
    const { container } = render(<DiscussionView data={data} />);
    await waitFor(() => expect(container.querySelector(".dl-lens")).toHaveClass("guide-hidden"));
    expect(discussionGuideState()).toMatchObject({ wish: true, shown: false });
  });

  it("opened by hand where it does not fit, it stays open: never folded for you", async () => {
    lensWidth(500);
    const { container } = render(<DiscussionView data={data} />);
    await settle();
    act(() => toggleDiscussionGuide()); // what the toolbar button, ⌥⌘L and [ do
    await waitFor(() => expect(discussionGuideState().shown).toBe(true));
    expect(container.querySelector(".dl-lens")).not.toHaveClass("guide-hidden");
  });

  it("asks the app for the width the pair needs, so the projects column folds first", async () => {
    lensWidth(900);
    render(<DiscussionView data={data} />);
    // the opening width (30% of the window, 280–480) + the wires + the conversation's 368 floor.
    // Waited for, not timed: the measure lands on a frame after the cards and the store settle.
    const opening = Math.round(Math.min(480, Math.max(280, 0.3 * window.innerWidth)));
    await waitFor(() => expect(discussionGuideState().wanted).toBe(opening + 40 + 368));
  });
});


describe("the guide tabs (4 Oct 2026)", () => {
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    _resetEmbeddedCache();
    bridge.postProjectAction.mockReset();
  });

  it("are always there: with no guide the second tab is where one is added", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    expect(screen.getByRole("radio", { name: "Normalised questions" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Add your guide" })).toBeInTheDocument();
  });

  it("show the guide by its file name, which chooses a different one", () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    render(<DiscussionView data={{ ...data, guide_file: "Home coffee discussion guide v3 final.docx" }} />);
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    expect(screen.getByRole("radio", { name: "Original Home coffee discussion guide v3 final.docx" })).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Choose a different guide" });
    expect(link.textContent).toMatch(/…/); // shortened, the extension kept
    expect(link.textContent).toMatch(/\.docx$/);
    fireEvent.click(link);
    expect(bridge.postProjectAction).toHaveBeenCalledWith("choose-discussion-guide");
    expect(screen.queryByRole("button", { name: "Replace your guide…" })).toBeNull(); // the link replaces it
  });

  it("say they are reading a guide the Mac has just copied in, in place of the upload block", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    fireEvent.click(screen.getByRole("radio", { name: "Add your guide" }));
    act(() => setPendingGuide("Home coffee guide.docx"));
    expect(screen.getByRole("status").textContent).toMatch(/^Reading your guide… Home coffee guide\.docx$/);
    expect(screen.queryByRole("button", { name: "Add your guide…" })).toBeNull();
  });

  it("with no guide uploaded, the questions carry a faint dot and no claim about the plan", () => {
    const { container } = render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    const rows = container.querySelectorAll(".dl-nav .dl-row");
    expect(rows.length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".dl-nav .dl-row .dl-mid")).toHaveLength(rows.length);
    expect(container.querySelector(".dl-nav .dl-row .dl-dot")).toBeNull();
    expect(container.querySelector(".dl-nav .dl-row")?.textContent).not.toMatch(/\+|not in your guide/i);
    // no guide and no cells: nothing for a key to explain, so no key — in All or in a session
    expect(screen.queryByRole("note", { name: "Key" })).toBeNull();
    onSession(1);
    expect(screen.queryByRole("note", { name: "Key" })).toBeNull();
  });

  it("in an export with no guide there is nothing to add, so no tabs", () => {
    exportState.on = true;
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    expect(screen.queryByRole("radio", { name: "Add your guide" })).toBeNull();
    exportState.on = false;
  });
});

describe("DiscussionView — arriving from the transcript's gutter", () => {
  // docs/design-transcript-gutter.md, stage 3: the address names a guide item and the turn that
  // asked it; the lens opens on that asking, in that turn's session, whatever it last showed.
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("opens on the asking the address names, in its session", async () => {
    const { discussionPath } = await import("./discussionLinks");
    window.history.replaceState(null, "", discussionPath("s5.1", "s2@01:26"));
    const { container } = render(<DiscussionView data={data} />);
    expect(heading()).toBe(`Session ${data.sessions[1].number}`);
    const ask = container.querySelector('.dl-ask[data-turn="s2@01:26"]')!;
    expect(ask.classList.contains("hot")).toBe(true);
    expect(ask.querySelector(".dl-ask-btn")).toHaveAttribute("aria-pressed", "true");
    // And flashes it, so the eye finds it (utils/arrival.ts).
    expect(ask.hasAttribute("data-arrived")).toBe(true);
  });

  it("opens as usual without one, or with a turn it does not have", () => {
    window.history.replaceState(null, "", "/report/discussion/?item=s5.1&turn=s9@00:00");
    render(<DiscussionView data={data} />);
    expect(heading()).toBe("All sessions");
  });
});
