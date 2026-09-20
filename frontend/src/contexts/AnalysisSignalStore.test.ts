/**
 * Tests for AnalysisSignalStore — module-level store for analysis sidebar.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import {
  setAnalysisSignals,
  setFocusedSignalKey,
  resetAnalysisSignalStore,
  useAnalysisSignalStore,
} from "./AnalysisSignalStore";
import type { UnifiedSignal } from "../utils/types";

// ── Helpers ──────────────────────────────────────────────────────────

/** Minimal signal factory for testing. */
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

// The store holds ONE de-duplicated list now — it held two, split by kind,
// because the lens drew two grids split by kind. Rendering is tested in
// AnalysisSidebar.test.tsx; these assert the store's own contract.

describe("AnalysisSignalStore", () => {
  beforeEach(() => {
    resetAnalysisSignalStore();
  });

  function read() {
    const { result } = renderHook(() => useAnalysisSignalStore());
    return result.current;
  }

  it("holds the list it is given, and the focused key", () => {
    const a = makeSignal({ key: "a" });
    const b = makeSignal({ key: "b" });
    setAnalysisSignals([a, b]);
    setFocusedSignalKey("a");
    expect(read().signals.map((s) => s.key)).toEqual(["a", "b"]);
    expect(read().focusedKey).toBe("a");
  });

  it("resetAnalysisSignalStore clears both the list and the focus", () => {
    setAnalysisSignals([makeSignal({ key: "a" })]);
    setFocusedSignalKey("a");
    resetAnalysisSignalStore();
    expect(read().signals).toEqual([]);
    expect(read().focusedKey).toBeNull();
  });

  // useSyncExternalStore compares snapshots by reference and will loop
  // forever on a store that returns a fresh object for an unchanged write —
  // so "the same reference in, the same state object out" is the contract,
  // not a nicety.
  it("re-setting the same list reference leaves the state object untouched", () => {
    const list = [makeSignal({ key: "x" })];
    setAnalysisSignals(list);
    const before = read();
    setAnalysisSignals(list);
    expect(read()).toBe(before);
  });

  it("setting an equal-but-different list DOES replace the state", () => {
    setAnalysisSignals([makeSignal({ key: "x" })]);
    const before = read();
    setAnalysisSignals([makeSignal({ key: "x" })]);
    expect(read()).not.toBe(before);
  });

  it("re-setting the same focused key leaves the state object untouched", () => {
    setFocusedSignalKey("a");
    const before = read();
    setFocusedSignalKey("a");
    expect(read()).toBe(before);
  });
});
