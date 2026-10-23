/**
 * A cold open of the report (RE#33 review): the landing lens reads /dashboard once, and the
 * hand-over dim never plays. The first /last-run poll used to bump `refreshKey` for the run it
 * found, so the lens read the same data twice and dimmed over it on every page load.
 */

import { Suspense } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { ProjectTab } from "./ProjectTab";
import { resetLastRunStore, stopLastRunPolling } from "../contexts/LastRunStore";
import type { DashboardResponse } from "../utils/types";

const dashboard: DashboardResponse = {
  stats: {
    session_count: 1,
    total_duration_seconds: 1800,
    total_duration_human: "30m",
    total_words: 2000,
    quotes_count: 4,
    sections_count: 1,
    themes_count: 0,
    ai_tags_count: 0,
    user_tags_count: 0,
  },
  sessions: [],
  featured_quotes: [],
  sections: [{ label: "Onboarding", anchor: "section-onboarding" }],
  themes: [],
  moderator_header: "",
  observer_header: "",
  coverage: null,
};

const run = { run_id: "01J123", outcome: "completed", completed_at: "2026-10-23T20:00:00Z" };

function answer(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body });
}

describe("ProjectTab — a cold open", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    resetLastRunStore();
    fetchMock = vi.fn((url: string) => answer(url.endsWith("/last-run") ? run : dashboard));
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
  });

  afterEach(() => {
    stopLastRunPolling();
    vi.unstubAllGlobals();
  });

  it("reads /dashboard once, and the hand-over never plays", async () => {
    // The dim lasts HANDOVER_MS and then its class goes, so watch for it rather than look after.
    let dimmed = false;
    const watch = new MutationObserver(() => {
      if (document.querySelector(".bn-handover")) dimmed = true;
    });
    watch.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"] });
    try {
      render(
        <Suspense fallback={null}>
          <ProjectTab />
        </Suspense>,
      );
      expect(await screen.findByText("Onboarding")).toBeTruthy();
      // Let the first poll and anything it set off settle.
      await act(async () => {
        await new Promise((r) => setTimeout(r, 50));
      });
      const urls = fetchMock.mock.calls.map((c) => String(c[0]));
      expect(urls.filter((u) => u.endsWith("/last-run"))).toHaveLength(1);
      expect(urls.filter((u) => u.endsWith("/dashboard"))).toHaveLength(1);
      expect(dimmed).toBe(false);
    } finally {
      watch.disconnect();
    }
  });
});
