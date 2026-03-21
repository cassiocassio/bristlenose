/**
 * Tests for AnalysisSidebar — signal-entry navigation for the Analysis tab.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnalysisSidebar } from "./AnalysisSidebar";
import {
  setAnalysisSignals,
  setFocusedSignalKey,
  resetAnalysisSignalStore,
} from "../contexts/AnalysisSignalStore";
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
    count: 3,
    participants: ["p1", "p2"],
    nEff: 2,
    meanIntensity: 0.7,
    concentration: 0.5,
    compositeSignal: 3.2,
    confidence: "strong",
    quotes: [],
    ...overrides,
  };
}

// ── Setup ────────────────────────────────────────────────────────────

beforeEach(() => {
  resetAnalysisSignalStore();
});

// ── Tests ────────────────────────────────────────────────────────────

describe("AnalysisSidebar", () => {
  it("renders nothing when store has no signals", () => {
    const { container } = render(<AnalysisSidebar />);
    expect(container.innerHTML).toBe("");
  });

  it("renders sentiment section signals", () => {
    setAnalysisSignals(
      [
        makeSignal({ key: "section|Homepage|frustration", location: "Homepage", sourceType: "section", columnLabel: "frustration" }),
        makeSignal({ key: "theme|Navigation|delight", location: "Navigation", sourceType: "theme", columnLabel: "delight" }),
      ],
      [],
    );
    render(<AnalysisSidebar />);

    expect(screen.getByText("Sentiment")).toBeInTheDocument();
    expect(screen.getByText("Section")).toBeInTheDocument();
    expect(screen.getByText("Theme")).toBeInTheDocument();
    expect(screen.getByText("Homepage")).toBeInTheDocument();
    expect(screen.getByText("Navigation")).toBeInTheDocument();
    expect(screen.getByText("frustration")).toBeInTheDocument();
    expect(screen.getByText("delight")).toBeInTheDocument();
  });

  it("renders codebook tag signals", () => {
    setAnalysisSignals(
      [],
      [
        makeSignal({
          key: "section|Onboarding|Trust",
          location: "Onboarding",
          sourceType: "section",
          columnLabel: "Trust",
          colourSet: "emo",
          codebookName: "Emotions",
        }),
      ],
    );
    render(<AnalysisSidebar />);

    expect(screen.getByText("Codebook tags")).toBeInTheDocument();
    expect(screen.getByText("Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Trust")).toBeInTheDocument();
  });

  it("applies active class to focused signal", () => {
    const sig = makeSignal({ key: "section|Homepage|frustration", location: "Homepage" });
    setAnalysisSignals([sig], []);
    setFocusedSignalKey("section|Homepage|frustration");
    render(<AnalysisSidebar />);

    const entry = screen.getByText("Homepage").closest(".signal-entry");
    expect(entry).toHaveClass("active");
  });

  it("does not apply active class to unfocused signal", () => {
    const sig = makeSignal({ key: "section|Homepage|frustration", location: "Homepage" });
    setAnalysisSignals([sig], []);
    // No focused key set
    render(<AnalysisSidebar />);

    const entry = screen.getByText("Homepage").closest(".signal-entry");
    expect(entry).not.toHaveClass("active");
  });

  it("dispatches bn:signal-focus on click", () => {
    const sig = makeSignal({ key: "section|Homepage|frustration", location: "Homepage" });
    setAnalysisSignals([sig], []);
    render(<AnalysisSidebar />);

    const handler = vi.fn();
    window.addEventListener("bn:signal-focus", handler);

    fireEvent.click(screen.getByText("Homepage"));

    expect(handler).toHaveBeenCalledTimes(1);
    const detail = (handler.mock.calls[0][0] as CustomEvent).detail;
    expect(detail.key).toBe("section|Homepage|frustration");

    window.removeEventListener("bn:signal-focus", handler);
  });

  it("shows signalName when available instead of location", () => {
    const sig = makeSignal({
      key: "section|Homepage|frustration",
      location: "Homepage",
      signalName: "Homepage frustration signal",
    });
    setAnalysisSignals([sig], []);
    render(<AnalysisSidebar />);

    expect(screen.getByText("Homepage frustration signal")).toBeInTheDocument();
    expect(screen.queryByText("Homepage")).not.toBeInTheDocument();
  });

  it("hides sub-headings when no signals of that sourceType exist", () => {
    // Only section signals, no theme signals
    setAnalysisSignals(
      [makeSignal({ key: "section|Homepage|frustration", sourceType: "section" })],
      [],
    );
    render(<AnalysisSidebar />);

    expect(screen.getByText("Section")).toBeInTheDocument();
    expect(screen.queryByText("Theme")).not.toBeInTheDocument();
  });

  it("renders both sentiment and tag sections together", () => {
    setAnalysisSignals(
      [makeSignal({ key: "section|A|frustration", location: "A", sourceType: "section" })],
      [makeSignal({ key: "section|B|Trust", location: "B", sourceType: "section", colourSet: "emo", codebookName: "Emo" })],
    );
    render(<AnalysisSidebar />);

    expect(screen.getByText("Sentiment")).toBeInTheDocument();
    expect(screen.getByText("Codebook tags")).toBeInTheDocument();
  });
});
