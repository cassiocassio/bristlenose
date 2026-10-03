import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import fixture from "./fixture.json";
import { DiscussionLens, DiscussionView } from "./DiscussionLens";
import { resetLensState } from "./lensState";
import type { DiscussionData } from "./types";

const data = fixture as unknown as DiscussionData;

function nav() {
  return screen.getByRole("navigation", { name: "Discussion guide" });
}

function heading() {
  return screen.getByRole("heading", { level: 1 }).textContent;
}

beforeEach(() => {
  resetLensState();
  document.getElementById("bn-app-root")?.remove();
});

describe("DiscussionView", () => {
  it("opens on Merged and the first session, with the session's questions and quotes", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Normalised questions" })).toHaveAttribute("aria-checked", "true");
    expect(heading()).toBe("Session 1");
    const asked = data.turns.filter((t) => t.session === "s1" && t.item).length;
    expect(container.querySelectorAll(".dl-content .dl-ask")).toHaveLength(asked);
    const quotes = data.quotes.filter((q) => q.session === "s1").length;
    expect(container.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)")).toHaveLength(quotes);
  });

  it("Merged shows the promoted new section, badged as new", () => {
    render(<DiscussionView data={data} />);
    const emergent = data.sections.find((s) => s.origin === "emergent")!;
    const head = within(nav()).getByText(emergent.title, { exact: false });
    expect(head.closest(".toc-heading")!.querySelector(".badge")!.textContent).toBe("new");
  });

  it("Planned shows the guide as written, every line with the solid dot", () => {
    const { container } = render(<DiscussionView data={data} />);
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    const rows = container.querySelectorAll(".dl-nav .dl-row");
    expect(rows).toHaveLength(data.spine.reduce((n, s) => n + s.items.length, 0));
    expect(container.querySelectorAll(".dl-nav .dl-dot.hollow")).toHaveLength(0);
    expect(container.querySelectorAll(".dl-nav .dl-mk .dl-dot")).toHaveLength(rows.length);
  });

  it("a header session switches the column and marks itself as here", () => {
    render(<DiscussionView data={data} />);
    const s2 = data.sessions[1];
    const btn = screen.getByRole("radio", { name: new RegExp(`^#${s2.number}`) });
    fireEvent.click(btn);
    expect(heading()).toBe(`Session ${s2.number}`);
    expect(btn).toHaveAttribute("aria-checked", "true");
    // option C: the navigator's selection vocabulary, no ring
    expect(btn.querySelector(".dl-here .bn-person-badge")).not.toBeNull();
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

  it("focusing a row the current session never asked jumps to a session that did", () => {
    const { container } = render(<DiscussionView data={data} />);
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

  it("a session badge in a row selects that session and focuses the row", () => {
    const { container } = render(<DiscussionView data={data} />);
    const multi = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const target = data.sessions.find((s) => s.id !== "s1" && multi.asks.some((a) => a.session === s.id))!;
    const chip = container.querySelector(`.dl-row[data-id="${multi.id}"] .dl-chips`)!;
    fireEvent.click(within(chip as HTMLElement).getByRole("button", { name: new RegExp(`^#${target.number} `) }));
    expect(heading()).toBe(`Session ${target.number}`);
    expect(container.querySelector(`.dl-row[data-id="${multi.id}"]`)).toHaveClass("active");
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
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    fireEvent.keyDown(radios[0], { key: "ArrowRight" });
    expect(heading()).toBe("Session 2");
    fireEvent.keyDown(radios[1], { key: "End" });
    expect(heading()).toBe("Session 3");
    fireEvent.keyDown(radios[2], { key: "ArrowRight" });  // wraps
    expect(heading()).toBe("Session 1");
  });

  it("digit keys do nothing while a dialog owns the keyboard", () => {
    const root = document.createElement("div");
    root.id = "bn-app-root";
    document.body.appendChild(root);
    render(<DiscussionView data={data} />);
    root.setAttribute("inert", "");
    fireEvent.keyDown(document, { key: "2" });
    expect(heading()).toBe("Session 1");
    root.removeAttribute("inert");
    fireEvent.keyDown(document, { key: "2" });
    expect(heading()).toBe("Session 2");
  });

  it("clearing a row's focus never moves the reader to another session", () => {
    const { container } = render(<DiscussionView data={data} />);
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
    expect(heading()).toBe("Session 1");
  });

  it("with no guide there is no Planned view to offer", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    expect(screen.queryByRole("radio", { name: "Your guide" })).toBeNull();
  });

  it("a turn the model never classified is shown, marked, and wired to nothing", () => {
    const t = data.turns.find((x) => x.session === "s1" && x.kind === "chat")!;
    const d = { ...data, turns: data.turns.map((x) => (x.id === t.id ? { ...x, kind: "unclassified" as const } : x)) };
    const { container } = render(<DiscussionView data={d} />);
    const row = container.querySelector(`.dl-ask[data-turn="${t.id}"]`)!;
    expect(row).not.toBeNull();
    expect(row.textContent).toContain("not classified");
    expect((row as HTMLElement).dataset.item).toBe("");
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

  it("collapsed badge rows stay collapsed frame after frame (no measure-of-hidden flicker)", async () => {
    // jsdom measures nothing: give the badges a width only while they are shown,
    // which is exactly the browser behaviour that made a collapsed row reopen.
    const desc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollWidth");
    const navDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", {
      configurable: true,
      get(this: HTMLElement) {
        if (!this.classList.contains("dl-chips")) return 0;
        return this.closest(".dl-row")?.classList.contains("compact") ? 0 : 50 * this.children.length;
      },
    });
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList.contains("dl-nav") ? 300 : 0;
      },
    });
    try {
      const { container } = render(<DiscussionView data={data} />);
      const frames = async () => act(async () => {
        await new Promise((r) => setTimeout(r, 40));
      });
      await frames();
      const after1 = [...container.querySelectorAll(".dl-row.compact")].map((r) => (r as HTMLElement).dataset.id);
      expect(after1.length).toBeGreaterThan(0); // 3 badges × 50 > 30% of 300
      // every frame, not two frames apart: a flicker alternates, so comparing
      // frames an even distance apart would pass it (it did, on the first draft)
      for (let i = 0; i < 3; i++) {
        fireEvent.scroll(window);
        await frames();
        const now = [...container.querySelectorAll(".dl-row.compact")].map((r) => (r as HTMLElement).dataset.id);
        expect(now).toEqual(after1);
      }
    } finally {
      if (desc) Object.defineProperty(HTMLElement.prototype, "scrollWidth", desc);
      if (navDesc) Object.defineProperty(HTMLElement.prototype, "clientWidth", navDesc);
    }
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

describe("DiscussionLens", () => {
  it("loads the data and renders the lens", async () => {
    render(<DiscussionLens />);
    expect(await screen.findByTestId("discussion-lens")).toBeInTheDocument();
  });
});
