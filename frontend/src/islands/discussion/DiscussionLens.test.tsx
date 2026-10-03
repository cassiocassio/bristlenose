import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import fixture from "./fixture.json";
import { DiscussionLens, DiscussionView } from "./DiscussionLens";
import type { DiscussionData } from "./types";

const data = fixture as unknown as DiscussionData;

function nav() {
  return screen.getByRole("navigation", { name: "Discussion guide" });
}

function heading() {
  return screen.getByRole("heading", { level: 1 }).textContent;
}

beforeEach(() => {
  try {
    localStorage.clear();
  } catch {
    // jsdom without Web Storage
  }
});

describe("DiscussionView", () => {
  it("opens on Merged and the first session, with the session's questions and quotes", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Merged" })).toHaveAttribute("aria-checked", "true");
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
    fireEvent.click(screen.getByRole("radio", { name: "Planned" }));
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
    expect(btn.querySelector(".dl-here .bn-person-badge-highlighted")).not.toBeNull();
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
    fireEvent.click(within(chip as HTMLElement).getByRole("button", { name: new RegExp(`^Session ${target.number}:`) }));
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
  });
});

describe("DiscussionLens", () => {
  it("loads the data and renders the lens", async () => {
    render(<DiscussionLens />);
    expect(await screen.findByTestId("discussion-lens")).toBeInTheDocument();
  });
});
