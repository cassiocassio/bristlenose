/**
 * Tests for SignalsSidebar — signal-entry navigation for the Analysis tab.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SignalsSidebar } from "./SignalsSidebar";
import {
  setSignals,
  setFocusedSignalKey,
  resetSignalStore,
} from "../contexts/SignalStore";
import type { UnifiedSignal } from "../utils/types";

// ── Helpers ──────────────────────────────────────────────────────────

function makeSignal(overrides: Partial<UnifiedSignal> = {}): UnifiedSignal {
  return {
    key: "section|Homepage|frustration",
    location: "Homepage",
    sourceType: "section",
    columnLabel: "frustration",
    colourSet: "",
    codebookName: "",
    participants: ["p1", "p2"],
    nEff: 2,
    meanIntensity: 0.7,
    concentration: 0.5,
    compositeSignal: 3.2,
    quotes: [],
    ...overrides,
  };
}

// ── Setup ────────────────────────────────────────────────────────────

beforeEach(() => {
  resetSignalStore();
});

// ── Tests ────────────────────────────────────────────────────────────

describe("SignalsSidebar", () => {
  it("renders nothing when the store has no signals", () => {
    const { container } = render(<SignalsSidebar />);
    expect(container.firstChild).toBeNull();
  });

  it("groups rows under their location, not under Section / Theme", () => {
    setSignals([
      makeSignal({ key: "section|Bag|Scope", location: "Bag", columnLabel: "Scope",
                   colourSet: "emo", codebookName: "Garrett", compositeSignal: 1.0,
                   signalName: "Scope Feature Mix" }),
      makeSignal({ key: "theme|Wrap-up|Sentiment", location: "Wrap-up", sourceType: "theme",
                   columnLabel: "Sentiment", compositeSignal: 0.3,
                   signalName: "Wrap-up Expectation Mismatch" }),
    ]);
    render(<SignalsSidebar />);

    expect(screen.getByText("Bag")).toBeInTheDocument();
    expect(screen.getByText("Wrap-up")).toBeInTheDocument();
    // The four sub-headings the old sidebar carried are gone. Sections and
    // themes interleave unlabelled — the words carry it, and the Quotes lens
    // still owns the demarcation.
    expect(screen.queryByText("Section")).not.toBeInTheDocument();
    expect(screen.queryByText("Theme")).not.toBeInTheDocument();
    expect(screen.queryByText("Sentiment signals")).not.toBeInTheDocument();
  });

  it("orders locations by their strongest signal, and cards within", () => {
    setSignals([
      makeSignal({ key: "section|Weak|A", location: "Weak", columnLabel: "A",
                   compositeSignal: 0.1, signalName: "Weak one" }),
      makeSignal({ key: "section|Strong|B", location: "Strong", columnLabel: "B",
                   compositeSignal: 0.9, signalName: "Strong one" }),
      makeSignal({ key: "section|Strong|C", location: "Strong", columnLabel: "C",
                   compositeSignal: 0.4, signalName: "Strong two" }),
    ]);
    render(<SignalsSidebar />);

    const text = [...document.querySelectorAll(".toc-sub-heading, .signal-entry-name")]
      .map((n) => n.textContent);
    expect(text).toEqual(["Strong", "Strong one", "Strong two", "Weak", "Weak one"]);
  });

  it("shows the elaborated name, and its group as a trailing chip", () => {
    setSignals([
      makeSignal({ key: "section|Homepage|Structure", location: "Homepage",
                   columnLabel: "Structure", colourSet: "task", codebookName: "Garrett",
                   signalName: "Navigation Structure Tension" }),
    ]);
    render(<SignalsSidebar />);

    expect(screen.getByText("Navigation Structure Tension")).toBeInTheDocument();
    expect(screen.getByText("Structure")).toBeInTheDocument();
  });

  it("a row with no elaborated name is its group chip alone", () => {
    // It used to fall back to the location, which the heading above already
    // says. Measured after de-duplication: 22% of locations carry exactly one
    // bare-chip row, and it reads as what it is.
    setSignals([
      makeSignal({ key: "section|Homepage|Feedback", location: "Homepage",
                   columnLabel: "Feedback", colourSet: "emo", codebookName: "Norman",
                   signalName: null }),
    ]);
    render(<SignalsSidebar />);

    expect(document.querySelector(".signal-entry-name")).toBeNull();
    expect(screen.getByText("Feedback")).toBeInTheDocument();
    // The location appears once — as the heading, not repeated in the row.
    expect(screen.getAllByText("Homepage")).toHaveLength(1);
  });

  it("applies the active class to the focused signal only", () => {
    setSignals([
      makeSignal({ key: "a", columnLabel: "A", signalName: "One" }),
      makeSignal({ key: "b", columnLabel: "B", signalName: "Two" }),
    ]);
    setFocusedSignalKey("a");
    render(<SignalsSidebar />);

    const rows = [...document.querySelectorAll(".signal-entry")];
    expect(rows[0].classList.contains("active")).toBe(true);
    expect(rows[1].classList.contains("active")).toBe(false);
  });

  // The wire contract: the card column listens for this and scrolls. Nothing
  // else connects the two halves of the lens.
  it("dispatches bn:signal-focus carrying the clicked key", () => {
    const handler = vi.fn();
    window.addEventListener("bn:signal-focus", handler);
    setSignals([
      makeSignal({ key: "section|Homepage|Structure", columnLabel: "Structure",
                   signalName: "Navigation Structure Tension" }),
    ]);
    render(<SignalsSidebar />);

    fireEvent.click(screen.getByText("Navigation Structure Tension"));
    expect(handler).toHaveBeenCalledTimes(1);
    expect((handler.mock.calls[0][0] as CustomEvent).detail).toEqual({
      key: "section|Homepage|Structure",
    });
    window.removeEventListener("bn:signal-focus", handler);
  });
});
