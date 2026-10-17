import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { TimelineSplit } from "./TimelineSplit";
import { getTranscriptTimeline, resetTranscriptTimelineStore } from "../../contexts/TranscriptTimelineStore";
import { _resetEmbeddedCache } from "../../utils/embedded";

beforeEach(() => resetTranscriptTimelineStore());

describe("TimelineSplit", () => {
  it("toggles the slot from the button half, which keeps its name when the label is hidden", () => {
    render(<TimelineSplit />);
    const main = screen.getByTestId("timeline-toggle");
    expect(main).toHaveAttribute("aria-pressed", "false");
    expect(main).toHaveAccessibleName("Session timeline");
    expect(main).toHaveTextContent("Timeline");
    fireEvent.click(main);
    expect(getTranscriptTimeline().on).toBe(true);
    expect(main).toHaveAttribute("aria-pressed", "true");
    expect(main).toHaveClass("active");
  });

  it("offers the same toggle in words, then the detail, each ticked as it stands", () => {
    render(<TimelineSplit />);
    const more = screen.getByTestId("timeline-more");
    expect(more).toHaveAttribute("aria-haspopup", "menu");
    fireEvent.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    const items = screen.getAllByRole("menuitemradio");
    expect(items.map((i) => i.textContent)).toEqual([
      "User journey",
      "Session timeline",
      "CompactSections · Moderator · Participant",
      "Standard+ Sentiment",
      "Full+ Themes",
    ]);
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["true", "false", "false", "true", "false"]);
  });

  it("picks a detail, which also turns the timeline on, and closes", () => {
    render(<TimelineSplit />);
    fireEvent.click(screen.getByTestId("timeline-more"));
    fireEvent.click(screen.getByTestId("timeline-menu-lanes-5"));
    expect(getTranscriptTimeline()).toMatchObject({ on: true, lanes: 5 });
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("goes back to the chain from the menu", () => {
    render(<TimelineSplit />);
    fireEvent.click(screen.getByTestId("timeline-toggle"));
    fireEvent.click(screen.getByTestId("timeline-more"));
    fireEvent.click(screen.getByTestId("timeline-menu-chain"));
    expect(getTranscriptTimeline().on).toBe(false);
  });

  it("closes on Escape", () => {
    render(<TimelineSplit />);
    fireEvent.click(screen.getByTestId("timeline-more"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
  });
});

describe("TimelineSplit in the Mac app", () => {
  const w = window as unknown as Record<string, unknown>;
  let postMessage: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    w.__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    postMessage = vi.fn();
    w.webkit = { messageHandlers: { navigation: { postMessage } } };
  });

  afterEach(() => {
    delete w.__BRISTLENOSE_EMBEDDED__;
    delete w.webkit;
    _resetEmbeddedCache();
  });

  it("asks native for the menu, with the words and the state, instead of opening its own", () => {
    render(<TimelineSplit />);
    const more = screen.getByTestId("timeline-more");
    fireEvent.click(more);
    expect(screen.queryByRole("menu")).toBeNull();
    expect(more).toHaveAttribute("aria-expanded", "true");
    expect(postMessage).toHaveBeenCalledTimes(1);
    expect(postMessage.mock.calls[0][0]).toEqual({
      type: "timeline-menu",
      on: false,
      lanes: 3,
      anchor: { x: 0, y: 0, width: 0, height: 0 },
      labels: {
        journey: "User journey",
        timeline: "Session timeline",
        detail: "Timeline detail",
        lanes: [
          { lanes: 2, title: "Compact", hint: "Sections · Moderator · Participant" },
          { lanes: 3, title: "Standard", hint: "+ Sentiment" },
          { lanes: 5, title: "Full", hint: "+ Themes" },
        ],
      },
    });
  });

  it("takes focus back on the caret when native says the menu closed", () => {
    render(<TimelineSplit />);
    const more = screen.getByTestId("timeline-more");
    fireEvent.click(more);
    act(() => {
      window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action: "timelineMenuClosed" } }));
    });
    expect(more).toHaveAttribute("aria-expanded", "false");
    expect(more).toHaveFocus();
  });
});
