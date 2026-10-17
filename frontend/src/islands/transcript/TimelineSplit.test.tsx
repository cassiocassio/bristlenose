import { describe, it, expect, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TimelineSplit } from "./TimelineSplit";
import { getTranscriptTimeline, resetTranscriptTimelineStore } from "../../contexts/TranscriptTimelineStore";

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
