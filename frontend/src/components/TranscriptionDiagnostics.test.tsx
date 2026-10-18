import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TranscriptionDiagnostics, { headline, type TranscriptionQuality } from "./TranscriptionDiagnostics";

function record(over: Partial<TranscriptionQuality> = {}): TranscriptionQuality {
  return {
    version: 1,
    session_id: "s1",
    duration_s: 120,
    audio: { floor_dbfs: -50, peak_dbfs: -10, active_share: 0.8, clipped_share: 0 },
    recognition: {
      backend: "mlx", model: "large-v3-turbo", transcribed: true, language: "es",
      language_set: false, prompt: true, decode_windows: 20, fallback_windows: 5,
      mean_confidence: 0.86, low_confidence_share: 0.1,
    },
    repair: {
      silent_dropped: 0, echoes_dropped: 1, loop_segments_removed: 39,
      skipped_found: 2, skipped_seconds: 40, skipped_recovered: 1, recovered_words: 80,
      found: [[10, 30], [60, 80]], still_empty: [[60, 80]],
      inaudible_gaps: 1, inaudible_seconds: 3,
    },
    text: { words: 300, wpm: 150, sentence_ends_per_100: 9.5, longest_unpunctuated: 24 },
    series: {
      bin_s: 10,
      level_p90: Array(12).fill(-20),
      wpm: Array(12).fill(150),
      low_conf: Array(12).fill(0.1),
    },
    ...over,
  };
}

describe("headline", () => {
  it("says how much was retried and how long had sound but no words", () => {
    expect(headline(record())).toBe(
      "25% of windows retried · 00:20 with sound but no words · 1 inaudible (00:03)",
    );
  });

  it("says nothing was missing when the net left nothing empty", () => {
    const r = record({ repair: { ...record().repair, still_empty: [], inaudible_gaps: 0 } });
    expect(headline(r)).toBe("25% of windows retried · no stretch with sound and no words found");
  });

  it("says nothing about retries mlx did not report", () => {
    const r = record({ recognition: { ...record().recognition, fallback_windows: null } });
    expect(headline(r)).not.toMatch(/retried/);
  });

  it("names a recording that was never transcribed", () => {
    const r = record({ recognition: { ...record().recognition, transcribed: false } });
    expect(headline(r)).toBe("Not transcribed: no sound above the floor");
  });

  it("leaves out what a backend did not measure", () => {
    // faster-whisper: no decode windows, no net, no audio levels.
    const r = record({
      audio: null,
      recognition: { backend: "faster-whisper", mean_confidence: 0.9, low_confidence_share: 0.05 },
      repair: { inaudible_gaps: 0, inaudible_seconds: 0 },
    });
    expect(headline(r)).toBe("");
  });
});

describe("TranscriptionDiagnostics", () => {
  it("is closed by default and opens to the lanes and panels", () => {
    render(<TranscriptionDiagnostics record={record()} durationSeconds={120} sPerPx={1} onJump={() => {}} />);
    const toggle = screen.getByRole("button", { name: /Diagnostics/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Recognition")).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    for (const title of ["Audio", "Recognition", "Repair", "Text"]) {
      expect(screen.getByRole("region", { name: title })).toBeInTheDocument();
    }
  });

  it("jumps to a stretch that still has sound and no words", () => {
    const onJump = vi.fn();
    render(<TranscriptionDiagnostics record={record()} durationSeconds={120} sPerPx={1} onJump={onJump} />);
    fireEvent.click(screen.getByRole("button", { name: /Diagnostics/ }));
    fireEvent.click(screen.getByRole("button", { name: "01:00" }));
    expect(onJump).toHaveBeenCalledWith(60);
  });

  it("leaves out a lane nothing was measured for", () => {
    const r = record({
      audio: null,
      series: { ...record().series, level_p90: [] },
      repair: { inaudible_gaps: 0, inaudible_seconds: 0 },
    });
    render(<TranscriptionDiagnostics record={r} durationSeconds={120} sPerPx={1} onJump={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Diagnostics/ }));
    const labels = Array.from(document.querySelectorAll(".bn-dx-lanes .bn-tp-lane")).map((n) => n.textContent);
    expect(labels).toEqual(["Pace", "Doubt"]);
  });

  it("draws the lanes on the timeline's own scale", () => {
    const { container } = render(
      <TranscriptionDiagnostics record={record()} durationSeconds={120} sPerPx={2} onJump={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Diagnostics/ }));
    const empty = container.querySelector(".bn-dx-gap-empty")!;
    // The timeline's gutter is 82 px; 60 s at 2 s a pixel is 30 px in.
    expect(empty.getAttribute("x")).toBe("112");
    expect(empty.getAttribute("width")).toBe("10");
  });
});

describe("Apple's speech model", () => {
  const apple = (gate: { passed: boolean; reason: string }) =>
    record({
      recognition: {
        backend: "apple-speech", transcribed: true, locale: "en-GB", locale_source: "assumed",
        mean_confidence: 0.92, low_confidence_share: 0.02,
        gate: { ...gate, mean_confidence: 0.92, words_per_signal_minute: 140, signal_minutes: 2 },
      },
    });

  it("says a session was left for Whisper, and why", () => {
    expect(headline(apple({ passed: false, reason: "low confidence" })))
      .toBe("Left for Whisper: low confidence under en-GB");
  });

  it("shows the locale as assumed, never detected, and drops Whisper's rows", () => {
    render(<TranscriptionDiagnostics record={apple({ passed: true, reason: "ok" })}
      durationSeconds={120} sPerPx={1} onJump={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Diagnostics/ }));
    expect(screen.getByText("Apple speech model")).toBeTruthy();
    expect(screen.getByText("en-GB")).toBeTruthy();
    expect(screen.getByText(/assumed/)).toBeTruthy();
    expect(screen.queryByText(/detected/)).toBeNull();
    expect(screen.queryByText("Style prompt")).toBeNull();
    expect(screen.getByText("passed")).toBeTruthy();
  });
});
