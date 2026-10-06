import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import SessionTapestry from "./SessionTapestry";
import { fitScale, zoomScale } from "../utils/tapestryScale";
import type { TapestrySession } from "../utils/types";

const session: TapestrySession = {
  session_id: "s1",
  duration_seconds: 600,
  turns: [
    { t0: 0, t1: 30, speaker: "m1", colour: null },
    { t0: 30, t1: 400, speaker: "p1", colour: "#9fceef" },
    { t0: 400, t1: 600, speaker: "m1", colour: null },
  ],
  sections: [
    { t0: 40, label: "Searching for a product" },
    { t0: 300, label: "Checkout and payment" },
  ],
  quotes: [
    { t0: 40, t1: 50, text: "That was easy to find", sentiment: "satisfaction", intensity: 2, section: "Searching for a product", theme: null },
    { t0: 310, t1: 330, text: "Why does it ask me again?", sentiment: "frustration", intensity: 3, section: "Checkout and payment", theme: null },
    { t0: 500, t1: 510, text: "We usually shop on Sundays", sentiment: null, intensity: 1, section: null, theme: "Shopping as a household chore" },
  ],
};

function setup() {
  const onJump = vi.fn();
  render(<SessionTapestry session={session} sPerPx={1} nameOf={(c) => ({ m1: "Rachel", p1: "Alex" })[c] ?? c} onJump={onJump} />);
  return { onJump, bars: () => Array.from(document.querySelectorAll<SVGElement>(".bn-tp-bar")) };
}

describe("SessionTapestry", () => {
  it("draws every lane: sections, both speaker tracks, sentiment, themes", () => {
    setup();
    expect(document.querySelectorAll(".bn-tp-flag")).toHaveLength(2);
    expect(document.querySelectorAll(".bn-tp-clip-team")).toHaveLength(2);
    expect(document.querySelectorAll(".bn-tp-clip-ppt")).toHaveLength(1);
    expect(document.querySelectorAll(".bn-tp-bar")).toHaveLength(3);
    expect(document.querySelectorAll(".bn-tp-theme")).toHaveLength(1);
  });

  it("paints a clip with its scene colour, and only when there is one", () => {
    setup();
    const ppt = document.querySelector<SVGRectElement>(".bn-tp-clip-ppt")!;
    expect(ppt.style.fill).toMatch(/^(#9fceef|rgb\(159, 206, 239\))$/);
    const team = document.querySelector<SVGRectElement>(".bn-tp-clip-team")!;
    expect(team.style.fill).toBe("");
  });

  it("puts positive sentiment above the line and negative below", () => {
    const { bars } = setup();
    const [pos, neg] = bars();
    expect(Number(pos.getAttribute("y")) + Number(pos.getAttribute("height"))).toBe(104);
    expect(Number(neg.getAttribute("y"))).toBe(104);
  });

  it("opens the quote panel on a bar, and the arrows step quotes whatever has focus", () => {
    const { bars } = setup();
    fireEvent.click(bars()[0]);
    expect(screen.getByText("That was easy to find")).toBeInTheDocument();
    // Focus left on the body, not the bar — the WebKit case that scrolled the slice instead.
    (document.activeElement as HTMLElement | null)?.blur();
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    expect(screen.getByText("Why does it ask me again?")).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    expect(screen.getByText("That was easy to find")).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByText("That was easy to find")).not.toBeInTheDocument();
  });

  it("jumps to the quote when the panel is clicked, and the nav buttons do not", () => {
    const { bars, onJump } = setup();
    fireEvent.click(bars()[1]);
    fireEvent.click(screen.getByRole("button", { name: "Previous Quote" }));
    expect(onJump).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("That was easy to find"));
    expect(onJump).toHaveBeenCalledWith(40);
  });

  it("jumps to a section's start from its flag", () => {
    const { onJump } = setup();
    fireEvent.click(document.querySelectorAll(".bn-tp-flag")[1]);
    expect(onJump).toHaveBeenCalledWith(300);
  });
});

describe("SessionTapestry — keyboard, focus and contrast", () => {
  it("keeps one Tab stop per slice: the first bar, then the selected one", () => {
    const { bars } = setup();
    expect(bars().map((b) => b.getAttribute("tabindex"))).toEqual(["0", "-1", "-1"]);
    fireEvent.click(bars()[1]);
    expect(bars().map((b) => b.getAttribute("tabindex"))).toEqual(["-1", "0", "-1"]);
    expect(bars()[1]).toHaveAttribute("aria-expanded", "true");
  });

  it("lets only one slice hold an open quote, so one arrow press steps one panel", () => {
    const other = { ...session, session_id: "s2", quotes: session.quotes.map((q) => ({ ...q, text: `${q.text} (s2)` })) };
    render(
      <>
        <SessionTapestry session={session} sPerPx={1} nameOf={(c) => c} onJump={() => {}} />
        <SessionTapestry session={other} sPerPx={1} nameOf={(c) => c} onJump={() => {}} />
      </>,
    );
    const all = Array.from(document.querySelectorAll<SVGElement>(".bn-tp-bar"));
    fireEvent.click(all[0]); // s1, first quote
    fireEvent.click(all[3]); // s2, first quote — s1's panel closes
    expect(screen.queryByText("That was easy to find")).not.toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    expect(screen.getByText("Why does it ask me again? (s2)")).toBeInTheDocument();
    expect(screen.queryByText("Why does it ask me again?")).not.toBeInTheDocument();
  });

  it("opens the transcript from the timecode, which is a real button", () => {
    const { bars, onJump } = setup();
    fireEvent.click(bars()[1]);
    fireEvent.click(screen.getByRole("button", { name: "05:10–05:30" }));
    expect(onJump).toHaveBeenCalledTimes(1);
    expect(onJump).toHaveBeenCalledWith(310);
  });

  it("inks a light scene colour dark and a dark one white", () => {
    const light = { ...session, turns: [{ t0: 0, t1: 600, speaker: "p1", colour: "#e8e0d0" }] };
    const { unmount } = render(<SessionTapestry session={light} sPerPx={0.25} nameOf={() => "Alex"} onJump={() => {}} />);
    expect(document.querySelector<SVGTextElement>(".bn-tp-clip-label")!.style.fill).toMatch(/#1a1a1a|rgb\(26, 26, 26\)/);
    unmount();
    const dark = { ...session, turns: [{ t0: 0, t1: 600, speaker: "p1", colour: "#4a3a30" }] };
    render(<SessionTapestry session={dark} sPerPx={0.25} nameOf={() => "Alex"} onJump={() => {}} />);
    expect(document.querySelector<SVGTextElement>(".bn-tp-clip-label")!.style.fill).toMatch(/#fff|rgb\(255, 255, 255\)/);
  });
});

describe("tapestry scale", () => {
  it("fits the longest session, held between 1 and 4 s/px", () => {
    expect(fitScale(300, 1000)).toBe(1);        // short project: never blown up
    expect(fitScale(6000, 1000)).toBe(4);       // 100 min: clamped, so it scrolls
    expect(fitScale(1800, 1000)).toBeCloseTo(1800 / (1000 - 82 - 14));
  });
  it("zooms from fit down to 0.25 s/px", () => {
    expect(zoomScale(4, 0)).toBeCloseTo(4);
    expect(zoomScale(4, 100)).toBeCloseTo(0.25);
  });
});
