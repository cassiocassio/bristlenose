/**
 * QuotesTab — cross-island contract test.
 *
 * The pre-existing per-island tests cover refetch behaviour in
 * isolation. This file exercises the wiring between the page wrapper,
 * LastRunStore, and the two consuming islands (QuoteSections and
 * QuoteThemes) — catching the regression where a refactor accidentally
 * drops `refreshKey` from one island's prop list.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QuotesTab } from "./QuotesTab";
import { FocusProvider } from "../contexts/FocusContext";
import {
  resetLastRunStore,
  stopLastRunPolling,
  triggerManualRefresh,
} from "../contexts/LastRunStore";
import { resetStore } from "../contexts/QuotesContext";

// ── Mocks ────────────────────────────────────────────────────────────────

vi.mock("../utils/api", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../utils/api");
  return {
    ...actual,
    authHeaders: () => ({}),
    apiGet: vi.fn(),
    getCodebook: vi.fn(),
    getPeople: vi.fn(),
  };
});

vi.mock("../utils/announce", () => ({
  announce: vi.fn(),
}));

vi.mock("../i18n", () => ({
  default: { t: (k: string) => k },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, opts?: Record<string, unknown>) =>
      opts ? `${k}:${JSON.stringify(opts)}` : k,
    i18n: { language: "en" },
  }),
}));

import { apiGet, getCodebook } from "../utils/api";

// Empty quotes payload — resolves the round-trip cleanly without
// needing to mock the codebook / sessions data.
const EMPTY_QUOTES = {
  sections: [],
  themes: [],
  has_moderator: false,
};

const EMPTY_CODEBOOK = {
  groups: [],
  all_tag_names: [],
};

const SEED_RUN = {
  run_id: "01J100",
  outcome: "completed",
  completed_at: "2026-05-09T12:00:00Z",
};

const NEW_RUN = {
  run_id: "01J200",
  outcome: "completed",
  completed_at: "2026-05-09T12:05:00Z",
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetLastRunStore();
  resetStore();
  vi.mocked(apiGet).mockResolvedValue(EMPTY_QUOTES);
  vi.mocked(getCodebook).mockResolvedValue(EMPTY_CODEBOOK as never);

  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => "visible",
  });

  // The page wrapper reads project ID from a #bn-app-root data attribute.
  const root = document.createElement("div");
  root.id = "bn-app-root";
  root.setAttribute("data-project-id", "1");
  document.body.appendChild(root);
});

afterEach(() => {
  stopLastRunPolling();
  vi.useRealTimers();
  document.getElementById("bn-app-root")?.remove();
});

function renderQuotesTab() {
  return render(
    <MemoryRouter initialEntries={["/report/quotes"]}>
      <FocusProvider>
        <QuotesTab />
      </FocusProvider>
    </MemoryRouter>,
  );
}

// Replace the two real islands with stubs that record every
// `refreshKey` they observe. The contract under test is
// "both islands receive every refreshKey bump from QuotesTab" —
// dropping the prop from one island leaves its observed-key list
// stale across the manual refresh.
const sectionsKeys: number[] = [];
const themesKeys: number[] = [];

vi.mock("../islands/QuoteSections", () => ({
  QuoteSections: ({ refreshKey = 0 }: { refreshKey?: number }) => {
    sectionsKeys.push(refreshKey);
    return null;
  },
}));

vi.mock("../islands/QuoteThemes", () => ({
  QuoteThemes: ({ refreshKey = 0 }: { refreshKey?: number }) => {
    themesKeys.push(refreshKey);
    return null;
  },
}));

// Toolbar pulls in heavy dependencies (codebook, QuotesContext) we
// don't need for this contract test.
vi.mock("../islands/Toolbar", () => ({
  Toolbar: () => null,
}));

describe("QuotesTab — cross-island refetch contract", () => {
  beforeEach(() => {
    sectionsKeys.length = 0;
    themesKeys.length = 0;
  });

  it("propagates every refreshKey bump to BOTH islands", async () => {
    fetchMock.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => SEED_RUN,
    });

    renderQuotesTab();

    // Both islands rendered with the initial refreshKey of 0.
    await waitFor(() => {
      expect(sectionsKeys).toContain(0);
      expect(themesKeys).toContain(0);
    });

    // Let the seed poll bump refreshKey from 0 → 1.
    await waitFor(() => {
      expect(sectionsKeys).toContain(1);
      expect(themesKeys).toContain(1);
    });

    const sectionsMaxBefore = Math.max(...sectionsKeys);
    const themesMaxBefore = Math.max(...themesKeys);

    fetchMock.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => NEW_RUN,
    });

    await act(async () => {
      await triggerManualRefresh();
      await Promise.resolve();
      await Promise.resolve();
    });

    // EACH island must have observed a strictly newer refreshKey. A
    // refactor that drops `refreshKey` from one island freezes that
    // island's observed-key list and fails the assertion.
    expect(Math.max(...sectionsKeys)).toBeGreaterThan(sectionsMaxBefore);
    expect(Math.max(...themesKeys)).toBeGreaterThan(themesMaxBefore);
  });
});
