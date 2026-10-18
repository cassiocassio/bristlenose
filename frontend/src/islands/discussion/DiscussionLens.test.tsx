import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixture.json";
import { DiscussionLens, DiscussionView } from "./DiscussionLens";
import { joinNames } from "./loadDiscussion";
import i18n from "../../i18n";
import enDesktop from "@locales/en/desktop.json";
import { _resetPlatformCache } from "../../utils/platform";
import { _resetEmbeddedCache } from "../../utils/embedded";
import { resetLensState } from "./lensState";
import { discussionGuideState, resetDiscussionGuide, setDiscussionGuideOpen, setPendingGuide, toggleDiscussionGuide } from "./guidePanel";
import type { DiscussionData } from "./types";

const data = fixture as unknown as DiscussionData;

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

beforeEach(() => {
  resetLensState();
  resetDiscussionGuide();
  document.getElementById("bn-app-root")?.remove();
});

describe("DiscussionView", () => {
  it("opens on Merged and All: each question once, every session's answers under it", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Normalised questions" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "All sessions" })).toHaveAttribute("aria-checked", "true");
    expect(heading()).toBe("All sessions");
    const asked = data.sections.flatMap((s) => s.items).filter((i) => i.asks.length);
    expect(container.querySelectorAll(".dl-content .dl-item")).toHaveLength(asked.length);
    for (const it of asked) {
      const block = container.querySelector(`.dl-item[data-item="${it.id}"]`)!;
      const sessions = new Set(it.asks.map((a) => a.session));
      // one block per session that asked it, each led by that session's badge
      expect(block.querySelectorAll(".dl-group")).toHaveLength(sessions.size);
      const missing = data.sessions.length - sessions.size;
      expect(block.querySelectorAll(".dl-notasked .bn-person-badge-absent")).toHaveLength(missing);
    }
    // no wires: the column is in the guide's own order
    expect(container.querySelectorAll(".dl-wire")).toHaveLength(0);
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
    const answered = container.querySelector(".dl-group .dl-ask + blockquote.quote-card:not(.dl-ask)")!
      .previousElementSibling as HTMLElement;
    fireEvent.click(within(answered).getByRole("button", { pressed: false }));
    expect(container.querySelectorAll(".dl-ask.hot")).toHaveLength(1);
    const lit = container.querySelectorAll(`blockquote.quote-card.hot[data-for="${answered.dataset.turn}"]`);
    expect(lit.length).toBeGreaterThan(0);
  });

  it("a session's cell in a row opens that session at that question; a not-asked cell does nothing", () => {
    const { container } = render(<DiscussionView data={data} />);
    const multi = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const target = data.sessions.find((s) => s.id !== "s1" && multi.asks.some((a) => a.session === s.id))!;
    const cells = within(container.querySelector(`.dl-row[data-id="${multi.id}"] .dl-cells`) as HTMLElement);
    const cell = cells.getByRole("button", { name: new RegExp(`^#${target.number} `) });
    expect(cell.tabIndex).toBe(-1); // reached from the session bar, not one tab stop per session
    fireEvent.click(cell);
    expect(heading()).toBe(`Session ${target.number}`);
    expect(container.querySelector(`.dl-row[data-id="${multi.id}"]`)).toHaveClass("active");
    expect(cell).toHaveClass("here");
    const elsewhere = data.sections.flatMap((s) => s.items).find((i) => i.asks.length && !i.asks.some((a) => a.session === "s1"))!;
    const notAsked = container.querySelector(`.dl-row[data-id="${elsewhere.id}"] .dl-cell[aria-disabled="true"]`)!;
    expect(notAsked.getAttribute("aria-label")).toMatch(/Not asked$/);
    fireEvent.click(notAsked);
    expect(heading()).toBe(`Session ${target.number}`);
  });

  it("a session's lead-in in All opens that session at that question", () => {
    const { container } = render(<DiscussionView data={data} />);
    const multi = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const target = data.sessions.find((s) => s.id !== "s1" && multi.asks.some((a) => a.session === s.id))!;
    const block = within(container.querySelector(`.dl-item[data-item="${multi.id}"]`) as HTMLElement);
    const lead = block.getByRole("button", { name: new RegExp(`^#${target.number}`) });
    expect(lead).toHaveAttribute("title", `Show session ${target.number}`);
    fireEvent.click(lead);
    expect(heading()).toBe(`Session ${target.number}`);
    expect(container.querySelector(`.dl-row[data-id="${multi.id}"]`)).toHaveClass("active");
  });

  it("each cell is shaded by the quotes it drew, and the row says its totals in words", () => {
    const { container } = render(<DiscussionView data={data} />);
    const rows = [...container.querySelectorAll<HTMLElement>(".dl-nav .dl-row")];
    for (const r of rows) {
      const it = data.sections.flatMap((s) => s.items).find((i) => i.id === r.dataset.id)!;
      const cells = [...r.querySelectorAll(".dl-cell")];
      expect(cells).toHaveLength(data.sessions.length);
      // a session that never asked it is never shaded
      data.sessions.forEach((sess, i) => {
        if (!it.asks.some((a) => a.session === sess.id)) expect(cells[i]).toHaveClass("s0");
      });
      const asked = new Set(it.asks.map((a) => a.session)).size;
      expect(r.querySelector(".dl-measure .bn-sr-only")!.textContent)
        .toMatch(new RegExp(`Asked in ${asked} of ${data.sessions.length} sessions, \\d+ quotes?$`));
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
    // in All nothing is greyed for "not asked in this session"
    expect(within(screen.getByRole("note", { name: "Key" })).queryByText(/^Grey:/)).toBeNull();
    onSession(1);
    const key = screen.getByRole("note", { name: "Key" });
    expect(key).toHaveClass("bn-pipeline-key");
    for (const t of ["Asked as planned", "Planned, never asked", "Not in your guide", "Grey: not asked in this session"]) {
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

  it("the measure is chosen by measuring the guide, and holds frame after frame", async () => {
    // jsdom lays nothing out: give the guide a width and the one-digit probe head a size.
    const navDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    let navW = 600;
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get(this: HTMLElement) { return this.classList.contains("dl-nav") ? navW : 0; },
    });
    const rect = vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const w = this.closest(".dl-head-probe") ? 19 : 0;
      return { width: w, height: 0, top: 0, left: 0, right: w, bottom: 0, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    const frames = async () => act(async () => { await new Promise((r) => setTimeout(r, 40)); });
    try {
      const { container } = render(<DiscussionView data={data} />);
      const lens = () => container.querySelector(".dl-lens")!;
      await frames();
      expect(lens()).toHaveClass("dl-m-grid");
      // the grid's heads, one-digit compact badges, none lit in All
      const heads = container.querySelectorAll(".dl-grid-head .bn-person-badge-compact");
      expect(heads).toHaveLength(data.sessions.length);
      expect(container.querySelector(".dl-grid-head .bn-person-badge-here")).toBeNull();
      for (let i = 0; i < 3; i++) {
        fireEvent.scroll(window);
        await frames();
        expect(lens()).toHaveClass("dl-m-grid");
      }
      // a selected session's head is "here"
      onSession(2);
      await frames();
      expect(container.querySelectorAll(".dl-grid-head .bn-person-badge-here")).toHaveLength(1);
      navW = 230; // narrower: the strip, then the bar
      fireEvent.scroll(window);
      await frames();
      expect(lens()).toHaveClass("dl-m-strip");
      expect(container.querySelector(".dl-grid-head")).toBeNull();
      navW = 150;
      fireEvent.scroll(window);
      await frames();
      expect(lens()).toHaveClass("dl-m-bar");
    } finally {
      rect.mockRestore();
      if (navDesc) Object.defineProperty(HTMLElement.prototype, "clientWidth", navDesc);
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

const api = vi.hoisted(() => ({ apiGet: vi.fn(), getSessionList: vi.fn() }));
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
  api.apiGet.mockResolvedValue({ status, record: rec });
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
    await settle();
    expect(container.querySelector(".dl-lens")).toHaveClass("guide-hidden");
    expect(discussionGuideState()).toMatchObject({ wish: true, shown: false });
  });

  it("opened by hand where it does not fit, it stays open: never folded for you", async () => {
    lensWidth(500);
    const { container } = render(<DiscussionView data={data} />);
    await settle();
    act(() => toggleDiscussionGuide()); // what the toolbar button, ⌥⌘L and [ do
    await settle();
    expect(container.querySelector(".dl-lens")).not.toHaveClass("guide-hidden");
    expect(discussionGuideState().shown).toBe(true);
  });

  it("asks the app for the width the pair needs, so the projects column folds first", async () => {
    lensWidth(900);
    render(<DiscussionView data={data} />);
    await settle();
    // the opening width (30% of the window, 280–480) + the wires + the conversation's 368 floor
    const opening = Math.round(Math.min(480, Math.max(280, 0.3 * window.innerWidth)));
    expect(discussionGuideState().wanted).toBe(opening + 40 + 368);
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
    // in All, no guide and no cells: nothing for a key to explain, so no key
    expect(screen.queryByRole("note", { name: "Key" })).toBeNull();
    onSession(1);
    const key = screen.getByRole("note", { name: "Key" });
    expect(key.textContent).toBe("Grey: not asked in this session");
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
