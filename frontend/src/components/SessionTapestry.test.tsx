import { describe, it, expect, vi, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import SessionTapestry from "./SessionTapestry";
import { fitScale, zoomScale } from "../utils/tapestryScale";
import { DEFAULTS, resetTapestryTuning, setTapestryTuning } from "../utils/tapestryTuning";
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
    // The sentiment line sits under the flags and both speaker tracks (108 at the shipped tuning).
    const mid = Number(document.querySelector(".bn-tp-axis")!.getAttribute("y1"));
    expect(mid).toBe(108);
    expect(Number(pos.getAttribute("y")) + Number(pos.getAttribute("height"))).toBe(mid);
    expect(Number(neg.getAttribute("y"))).toBe(mid);
    expect(pos.getAttribute("width")).toBe("6");
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

describe("SessionTapestry — hover", () => {
  it("lights the tick nearest the playhead while the speaker lane is hovered", async () => {
    setup(); // 1 s/px: ticks every 2 min
    const lane = document.querySelector(".bn-tp-hit")!;
    fireEvent.mouseMove(lane, { clientX: 82 + 250 }); // 4:10
    await waitFor(() =>
      expect(Array.from(document.querySelectorAll(".bn-tp-tick.near")).map((n) => n.textContent)).toEqual(["04:00"]),
    );
    fireEvent.mouseLeave(lane);
    expect(document.querySelectorAll(".bn-tp-tick.near")).toHaveLength(0);
  });
});

describe("SessionTapestry — hovering a section flag", () => {
  it("selects it: blue, full label, the cursor at its time", () => {
    setup();
    const flag = document.querySelectorAll(".bn-tp-flag")[1];
    fireEvent.mouseEnter(flag);
    const hot = document.querySelector(".bn-tp-flag.hot")!;
    expect(hot.textContent).toContain("Checkout and payment"); // full label, never truncated
    expect(document.querySelector(".bn-tp-playhead")).not.toBeNull();
    expect(Array.from(document.querySelectorAll(".bn-tp-tick.near")).map((n) => n.textContent)).toEqual(["06:00"]);
    fireEvent.mouseLeave(document.querySelector(".bn-tp-flag.hot")!);
    expect(document.querySelector(".bn-tp-flag.hot")).toBeNull();
    expect(document.querySelector(".bn-tp-playhead")).toBeNull();
  });
});

describe("SessionTapestry — which track a speaker is on", () => {
  it("follows the server's team flag over the transcript tag (a recoded speaker)", () => {
    const recoded = { ...session, turns: [{ t0: 0, t1: 600, speaker: "p1", colour: null, team: true }] };
    render(<SessionTapestry session={recoded} sPerPx={1} nameOf={(c) => c} onJump={() => {}} />);
    expect(document.querySelectorAll(".bn-tp-clip-team")).toHaveLength(1);
    expect(document.querySelectorAll(".bn-tp-clip-ppt")).toHaveLength(0);
  });

  it("falls back to the displayed code, not the raw tag, when the server sends no flag", () => {
    const old = { ...session, turns: [{ t0: 0, t1: 600, speaker: "p1", colour: null }] };
    render(<SessionTapestry session={old} sPerPx={1} nameOf={(c) => c} codeOf={() => "m2"} onJump={() => {}} />);
    expect(document.querySelectorAll(".bn-tp-clip-team")).toHaveLength(1);
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

describe("SessionTapestry — the quote popover", () => {
  it("claims Esc before the app's global shortcuts", () => {
    const global = vi.fn();
    document.addEventListener("keydown", global); // the app's cascade listens in the bubble phase
    const { bars } = setup();
    fireEvent.click(bars()[0]);
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByText("That was easy to find")).not.toBeInTheDocument();
    expect(global).not.toHaveBeenCalled();
    fireEvent.keyDown(document.body, { key: "Escape" }); // nothing open: Esc goes on to the app
    expect(global).toHaveBeenCalledTimes(1);
    document.removeEventListener("keydown", global);
  });

  it("stands aside while a modal holds the page", () => {
    const root = document.createElement("div");
    root.id = "bn-app-root";
    document.body.appendChild(root);
    const { bars } = setup();
    fireEvent.click(bars()[0]);
    root.setAttribute("inert", ""); // what useInert does
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.getByText("That was easy to find")).toBeInTheDocument();
    root.remove();
  });

  it("closes from its X", () => {
    const { bars } = setup();
    fireEvent.click(bars()[0]);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByText("That was easy to find")).not.toBeInTheDocument();
  });

  it("hands focus back to its bar when closed from the X", async () => {
    const { bars } = setup();
    fireEvent.click(bars()[1]);
    const close = screen.getByRole("button", { name: "Close" });
    close.focus();
    fireEvent.click(close);
    await waitFor(() => expect(document.activeElement).toBe(bars()[1]));
    expect(bars()[1].getAttribute("tabindex")).toBe("0"); // the Tab stop stays on the quote just read
  });

  it("closes on a click anywhere that is not a bar or the popover", () => {
    const { bars } = setup();
    fireEvent.click(bars()[0]);
    fireEvent.pointerDown(screen.getByText("That was easy to find"));
    expect(screen.getByText("That was easy to find")).toBeInTheDocument(); // inside: stays
    fireEvent.pointerDown(bars()[1]);
    expect(screen.getByText("That was easy to find")).toBeInTheDocument(); // another bar: the click selects
    fireEvent.pointerDown(document.body);
    expect(screen.queryByText("That was easy to find")).not.toBeInTheDocument();
  });

  it("floats rather than taking space, with its arrow on the bar", () => {
    const { bars } = setup();
    fireEvent.click(bars()[1]);
    const pop = document.querySelector<HTMLElement>(".bn-tp-popover")!;
    expect(pop.parentElement).toHaveClass("bn-tp-wrap");
    expect(pop.style.getPropertyValue("--bn-tp-arrow-x")).toMatch(/px$/);
  });
});

describe("SessionTapestry — tuning", () => {
  afterEach(() => resetTapestryTuning());

  it("draws the shipped geometry at the defaults", () => {
    setup();
    const chip = document.querySelector(".bn-tp-tag")!;
    expect(chip.getAttribute("height")).toBe("18");
    const wrap = document.querySelector<HTMLElement>(".bn-tp-wrap")!;
    expect(wrap.style.getPropertyValue("--bn-tp-text-theme")).toBe("var(--bn-text-label)");
  });

  it("follows a tuned step and padding live", () => {
    setup();
    act(() => setTapestryTuning({ ...DEFAULTS, type: { ...DEFAULTS.type, theme: "caption" }, pad: { ...DEFAULTS.pad, themeH: 20 } }));
    expect(document.querySelector(".bn-tp-tag")!.getAttribute("height")).toBe("20");
    expect(document.querySelector<HTMLElement>(".bn-tp-wrap")!.style.getPropertyValue("--bn-tp-text-theme")).toBe("var(--bn-text-caption)");
  });
});

describe("SessionTapestry — sentiment click targets", () => {
  afterEach(() => resetTapestryTuning());

  it("are wider than the bar and select its quote", () => {
    setup();
    const [hit] = Array.from(document.querySelectorAll(".bn-tp-bar-hit"));
    expect(Number(hit.getAttribute("width"))).toBe(6.4 + 2); // max(bar 6, dot 6.4) + 2
    fireEvent.click(hit);
    expect(screen.getByText("That was easy to find")).toBeInTheDocument();
  });

  it("give way when marks are close at this zoom: never past halfway to a neighbour", () => {
    const close = { ...session, quotes: [
      { ...session.quotes[0], t0: 100 },
      { ...session.quotes[1], t0: 103 },
    ] };
    // 1 s/px: the marks are 3px apart, so each side stops at 1.5px — and never below the bar (3px).
    render(<SessionTapestry session={close} sPerPx={1} nameOf={(c) => c} onJump={() => {}} />);
    const hits = Array.from(document.querySelectorAll(".bn-tp-bar-hit")).map((h) => [Number(h.getAttribute("x")), Number(h.getAttribute("width"))]);
    const [a, b] = hits;
    expect(a[0] + a[1]).toBeLessThanOrEqual(b[0] + 3); // no wider than the bar where they meet
    expect(a[1]).toBeGreaterThanOrEqual(6); // never narrower than the mark
  });
});

describe("SessionTapestry — theme tags", () => {
  it("show the whole name when there is room, on a chip that fades out to the right", () => {
    // Early in the session, so the full name fits before the slice's right edge.
    const early = { ...session, quotes: [{ ...session.quotes[2], t0: 50 }] };
    render(<SessionTapestry session={early} sPerPx={1} nameOf={(c) => c} onJump={() => {}} />);
    expect(document.querySelector(".bn-tp-tag-text")!.textContent).toBe("Shopping as a household chore");
    // Before, a name was cut to its span or 120px even with room to spare.
    expect(document.querySelector<SVGRectElement>(".bn-tp-tag")!.style.fill).toMatch(/url\(.*bn-tp-fade-s1/);
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
