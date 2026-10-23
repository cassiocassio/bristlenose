import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";
import { closeToc, openTocPush, resetSidebarStore } from "./contexts/SidebarStore";
import { resetQuoteGroupingSlot } from "./contexts/QuoteGroupingSlot";
import { activityStorageKey, addJob, resetActivityStore } from "./contexts/ActivityStore";
import { act } from "@testing-library/react";
import i18n, { ensureLocaleLoaded } from "./i18n";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";

  // Mock the app root element for useProjectId
  const root = document.createElement("div");
  root.id = "bn-app-root";
  root.setAttribute("data-project-id", "1");
  document.body.appendChild(root);

  // Mock matchMedia — jsdom ships none, and `useIsDarkAppearance` calls it
  // whenever no `data-theme` override is set (see its own header comment).
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  // Suppress fetch calls from islands — return empty JSON for all endpoints
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ quotes: [], sessions: [], tags: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
});

function renderRoute(initialEntry: string) {
  const router = createMemoryRouter(routes, {
    initialEntries: [initialEntry],
  });
  return render(<RouterProvider router={router} />);
}

// ---------------------------------------------------------------------------
// Tests — route → NavBar active state
// ---------------------------------------------------------------------------

describe("Router", () => {
  it("renders NavBar on /report/", () => {
    renderRoute("/report/");
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("/report/ activates Project tab", () => {
    renderRoute("/report/");
    const tab = screen.getByRole("link", { name: "Project" });
    expect(tab.className).toContain("active");
  });

  it("/report/sessions/ activates Sessions tab", () => {
    renderRoute("/report/sessions/");
    const tab = screen.getByRole("link", { name: "Sessions" });
    expect(tab.className).toContain("active");
  });

  it("/report/quotes/ activates Quotes tab", () => {
    renderRoute("/report/quotes/");
    const tab = screen.getByRole("link", { name: "Quotes" });
    expect(tab.className).toContain("active");
  });

  it("/report/codebook/ activates Codebooks tab", () => {
    renderRoute("/report/codebook/");
    const tab = screen.getByRole("link", { name: "Codebooks" });
    expect(tab.className).toContain("active");
  });

  it("/report/signals/ activates Signals lens", () => {
    renderRoute("/report/signals/");
    const tab = screen.getByRole("link", { name: "Signals" });
    expect(tab.className).toContain("active");
  });

  it("/report/settings/ redirects to project tab (settings is now a modal)", async () => {
    renderRoute("/report/settings/");
    // The catch-all route redirects unknown paths to /report/. The redirect is a
    // router transition; the lazy ProjectTab island holds it pending until the
    // chunk resolves, so await the active state rather than asserting synchronously.
    await waitFor(() => {
      const tab = screen.getByRole("link", { name: "Project" });
      expect(tab.className).toContain("active");
    });
  });

  it("/report/about/ redirects to project tab", async () => {
    renderRoute("/report/about/");
    await waitFor(() => {
      const tab = screen.getByRole("link", { name: "Project" });
      expect(tab.className).toContain("active");
    });
  });

  it("/report/sessions/s1 activates Sessions tab (prefix match)", () => {
    renderRoute("/report/sessions/s1");
    const tab = screen.getByRole("link", { name: "Sessions" });
    expect(tab.className).toContain("active");
  });

  it("unknown sub-path redirects to project tab", async () => {
    renderRoute("/report/nonexistent");
    await waitFor(() => {
      const tab = screen.getByRole("link", { name: "Project" });
      expect(tab.className).toContain("active");
    });
  });
});

// ---------------------------------------------------------------------------
// Embedded mode — chrome suppression
// ---------------------------------------------------------------------------

describe("Embedded mode", () => {
  it("suppresses NavBar, Header, and Footer when embedded", () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    renderRoute("/report/");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });

  it("renders NavBar when not embedded", () => {
    renderRoute("/report/");
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// The Quotes lens's grouping control: at the top of the content sidebar while
// it shows, never there otherwise (QuotesTab takes it into the heading then).
// ---------------------------------------------------------------------------

describe("Quotes grouping control placement", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetQuoteGroupingSlot();
    // Real-shaped answers: the catch-all stub above has no `sections`, and the
    // sidebar reads them once its fetch lands.
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/quotes")
        ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
        : url.includes("/sessions")
          ? { sessions: [] }
          : url.includes("/codebook")
            ? { groups: [], ungrouped: [], all_tag_names: [] }
            : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  it("sits at the top of the content sidebar while it is open, and leaves with it", async () => {
    openTocPush();
    const { container } = renderRoute("/report/quotes/");
    await waitFor(() =>
      expect(
        container.querySelector(".toc-sidebar-header [data-testid='bn-quote-grouping-sections']"),
      ).not.toBeNull(),
    );
    act(() => closeToc());
    expect(container.querySelector(".toc-sidebar-header .bn-quote-grouping")).toBeNull();
  });

  it("is not offered in the sidebar of another lens", async () => {
    openTocPush();
    const { container } = renderRoute("/report/signals/");
    await waitFor(() => expect(container.querySelector(".toc-sidebar")).not.toBeNull());
    expect(container.querySelector(".bn-quote-grouping")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// An AutoCode run that finishes tells the lenses that draw quotes, not only the
// codebook: the proposals live on the quotes, which reload on `bn:tags-changed`.
// ---------------------------------------------------------------------------

describe("AutoCode chip completion", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/autocode/norman/status")
        ? {
            status: "completed",
            processed_quotes: 4,
            total_quotes: 4,
            started_at: "2026-10-20T10:00:00Z",
            completed_at: "2026-10-20T10:01:00Z",
          }
        : url.includes("/quotes")
          ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
          : url.includes("/sessions")
            ? { sessions: [] }
            : url.includes("/codebook")
              ? { groups: [], ungrouped: [], all_tag_names: [] }
              : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("announces bn:tags-changed when the run completes", async () => {
    const heard = vi.fn();
    document.addEventListener("bn:tags-changed", heard);
    try {
      renderRoute("/report/sessions/");
      act(() => {
        addJob("autocode-norman", { type: "autocode", frameworkId: "norman", frameworkTitle: "Norman" });
      });
      await waitFor(() => expect(heard).toHaveBeenCalled());
    } finally {
      document.removeEventListener("bn:tags-changed", heard);
    }
  });
});

// ---------------------------------------------------------------------------
// R12: switching a codebook back on re-codes its new sessions, and the chip for
// it is numberless by design — the job's counts are the codebook's cumulative
// totals, not the sessions being coded — so it must not draw them while it runs.
// ---------------------------------------------------------------------------

describe("Catch-up chip", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/autocode/norman/status")
        ? { status: "running", processed_quotes: 40, total_quotes: 40, proposed_count: 12 }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("says what it is doing and draws no counts while it runs", async () => {
    renderRoute("/report/sessions/");
    act(() => {
      addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveTextContent("Coding the remaining sessions…"));
    // The chip draws the ellipsis itself; a value that carried one doubled it.
    expect(chip).not.toHaveTextContent("……");
    expect(chip).toHaveAttribute("data-status", "running");
    expect(chip).not.toHaveTextContent("40/40");
  });

  // #53: the keys were in no locale, so the chip said its English default in
  // every language. Spanish stands for the 21: it reads its own value, not ours.
  it("speaks the interface language", async () => {
    await ensureLocaleLoaded("es");
    await act(async () => { await i18n.changeLanguage("es"); });
    try {
      renderRoute("/report/sessions/");
      act(() => {
        addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
      });
      const chip = await screen.findByTestId("bn-activity-chip");
      const spanish = i18n.t("autocode.chip.recoding");
      expect(spanish).not.toBe("autocode.chip.recoding");
      expect(spanish).not.toBe(i18n.t("autocode.chip.recoding", { lng: "en" }));
      await waitFor(() => expect(chip).toHaveTextContent(spanish));
      expect(chip).not.toHaveTextContent("Coding the remaining sessions");
    } finally {
      await act(async () => { await i18n.changeLanguage("en"); });
    }
  });
});

// R12 wave 6: the chip read the job's cumulative counts, which keep an earlier
// apply's shortfall for good, so every later catch-up that worked said "some
// batches failed". A catch-up's own counts decide its chip.
describe("Catch-up chip outcome", () => {
  function serve(status: Record<string, unknown>) {
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/autocode/norman/status")
        ? status
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  }

  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("says done when the catch-up coded everything, whatever an earlier apply missed", async () => {
    serve({
      status: "completed", processed_quotes: 38, total_quotes: 43,
      catch_up_processed: 3, catch_up_total: 3, proposed_count: 12, failure_kind: "",
    });
    renderRoute("/report/sessions/");
    act(() => {
      addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveAttribute("data-status", "completed"));
    expect(chip).not.toHaveTextContent("some batches failed");
  });

  it("names its own shortfall when the catch-up came up short", async () => {
    serve({
      status: "completed", processed_quotes: 40, total_quotes: 44,
      catch_up_processed: 2, catch_up_total: 4, proposed_count: 12, failure_kind: "",
    });
    renderRoute("/report/sessions/");
    act(() => {
      addJob("catchup:norman:1", { type: "catchup", frameworkId: "norman", frameworkTitle: "Norman" });
    });
    const chip = await screen.findByTestId("bn-activity-chip");
    await waitFor(() => expect(chip).toHaveTextContent("Tagged 2 of 4 quotes"));
  });
});

// ---------------------------------------------------------------------------
// R13: a clip export the server no longer holds (it restarted; its jobs live in
// memory) answers "idle", which the chip read as still running, for ever.
// ---------------------------------------------------------------------------

describe("Clip export chip after a server restart", () => {
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/clips/status")
        ? { status: "idle", progress: 0, total: 0, completed_count: 0, skipped_count: 0, current_clip: "", output_dir: null }
        : url.includes("/quotes")
          ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
          : url.includes("/sessions")
            ? { sessions: [] }
            : url.includes("/codebook")
              ? { groups: [], ungrouped: [], all_tag_names: [] }
              : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("ends as failed rather than spinning", async () => {
    renderRoute("/report/sessions/");
    act(() => {
      addJob("clips", { type: "clips", frameworkId: "", frameworkTitle: "", total: 3 });
    });
    await waitFor(() =>
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed"),
    );
  });

  it("a screens export the server no longer holds ends the same way", async () => {
    // Restarted between the export's start and its first read: "idle" from the first answer.
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/screens/status")
        ? { status: "idle", progress: 0, total: 0, completed_count: 0, skipped_count: 0, current: "", output_dir: null, files: [] }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    renderRoute("/report/sessions/");
    act(() => {
      addJob("screens:r13", { type: "screens", frameworkId: "", frameworkTitle: "", total: 3 });
    });
    await waitFor(() =>
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "failed"),
    );
  });
});

// ---------------------------------------------------------------------------
// R14: a reload during a job lost its chip, and the job's end was never shown. The report asks the
// server on load what is still running and puts the chip back.
// ---------------------------------------------------------------------------

describe("Activity chips after a reload", () => {
  let clipsStatus = "running";
  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    clipsStatus = "running";
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/clips/status")
        ? { status: clipsStatus, progress: 2, total: 5, completed_count: 2, skipped_count: 0, current_clip: "", output_dir: null }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
  });

  it("a clip export still running comes back as its chip, and its end is shown", async () => {
    renderRoute("/report/sessions/");
    await waitFor(() =>
      expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "running"),
    );
    clipsStatus = "completed";
    await waitFor(
      () => expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed"),
      // The next poll is up to 2 s away; a wide budget, since CI runners are slow on real timers.
      { timeout: 10_000 },
    );
  }, 15_000);
});

// ---------------------------------------------------------------------------
// RE#38 (#35, #36): the window keeps its chips across a reload. A Copy Screens still running when
// the report reloaded came back as a plain export and never reached the clipboard.
// ---------------------------------------------------------------------------

describe("A Copy Screens across a reload", () => {
  let postMessage: ReturnType<typeof vi.fn>;
  let serverJob = "s1";
  // A real serve's token: with none, nothing is kept across a reload.
  const key = () => activityStorageKey("1")!;
  const carry = (entry: Record<string, unknown>) =>
    sessionStorage.setItem(key(), JSON.stringify([["screens:1", entry]]));
  const copyEntry = {
    type: "screens", frameworkId: "", frameworkTitle: "", total: 2, copyWhenDone: true, jobId: "s1",
  };
  const copies = () =>
    postMessage.mock.calls.map((c) => c[0]).filter((m) => m?.type === "screens-pasteboard-write");

  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    serverJob = "s1";
    postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = {
      messageHandlers: { navigation: { postMessage } },
    };
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_AUTH_TOKEN__ = "serve-token";
    _resetEmbeddedCache();
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/screens/status")
        ? { status: "completed", progress: 2, total: 2, completed_count: 2, skipped_count: 0, current: "",
            output_dir: "/Users/r/Study A/bristlenose-output/screens", files: ["p1-01.jpg", "p1-02.jpg"],
            job_id: serverJob }
        : url.includes("/export/clips/status")
          ? { status: "idle", progress: 0, total: 0, completed_count: 0, skipped_count: 0, current_clip: "",
              output_dir: null, job_id: null }
          : url.includes("/sessions")
            ? { sessions: [] }
            : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
    delete (window as unknown as Record<string, unknown>).webkit;
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_AUTH_TOKEN__;
  });

  it("finishing during the reload, still copies, once, in the window that asked", async () => {
    carry(copyEntry);
    renderRoute("/report/sessions/");
    await waitFor(() => expect(copies()).toHaveLength(1), { timeout: 5000 });
    expect(copies()[0]).toEqual({
      type: "screens-pasteboard-write",
      dir: "/Users/r/Study A/bristlenose-output/screens",
      files: ["p1-01.jpg", "p1-02.jpg"],
    });
    expect(screen.getByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed");
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2500));
    });
    expect(copies()).toHaveLength(1);
    // Carried as finished, so the next reload shows it without copying again.
    const kept = JSON.parse(sessionStorage.getItem(key()) ?? "[]");
    expect(kept[0][1].outcome.status).toBe("completed");
  }, 10_000);

  it("is not copied again by a reload after it was copied", async () => {
    carry({
      ...copyEntry,
      outcome: { status: "completed", progressLabel: null, durationLabel: null, errorMessage: null, partialMessage: null },
    });
    renderRoute("/report/sessions/");
    expect(await screen.findByTestId("bn-activity-chip")).toHaveAttribute("data-status", "completed");
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2500));
    });
    expect(copies()).toHaveLength(0);
  }, 10_000);

  it("never copies a newer export another window started", async () => {
    serverJob = "s2";
    carry(copyEntry);
    renderRoute("/report/sessions/");
    // The carried chip was read back and its export asked after, before it went.
    const screensReads = () =>
      vi.mocked(globalThis.fetch).mock.calls.filter((c) => String(c[0]).includes("/export/screens/status"));
    await waitFor(() => expect(screensReads().length).toBeGreaterThan(0), { timeout: 5000 });
    expect(JSON.parse(sessionStorage.getItem(key()) ?? "[]")).toEqual([]);
    await waitFor(() => expect(screen.queryByTestId("bn-activity-chip")).not.toBeInTheDocument(), { timeout: 5000 });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2500));
    });
    expect(copies()).toHaveLength(0);
  }, 10_000);
});

describe("Cancel on a chip carried across a reload", () => {
  let cancelStatus = 200;
  const w = window as unknown as Record<string, unknown>;
  const cancels = () =>
    vi.mocked(globalThis.fetch).mock.calls.filter((c) => String(c[0]).includes("/export/clips/cancel"));

  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    cancelStatus = 200;
    w.__BRISTLENOSE_AUTH_TOKEN__ = "serve-token";
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/export/clips/cancel")) {
        return new Response(JSON.stringify({ detail: "replaced" }), {
          status: cancelStatus, headers: { "Content-Type": "application/json" },
        });
      }
      const body = url.includes("/export/clips/status")
        ? { status: "running", progress: 1, total: 4, completed_count: 1, skipped_count: 0, current_clip: "",
            output_dir: null, job_id: "c1" }
        : url.includes("/sessions")
          ? { sessions: [] }
          : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    sessionStorage.setItem(activityStorageKey("1")!, JSON.stringify([
      ["clips:1", { type: "clips", frameworkId: "", frameworkTitle: "", total: 4, jobId: "c1" }],
    ]));
  });

  afterEach(() => {
    resetActivityStore();
    delete w.__BRISTLENOSE_AUTH_TOKEN__;
  });

  it("names its own export, so a newer one another window started is never stopped", async () => {
    renderRoute("/report/sessions/");
    const cancel = await screen.findByTestId("bn-activity-chip-cancel", {}, { timeout: 5000 });
    act(() => cancel.click());
    await waitFor(() => expect(cancels()).toHaveLength(1));
    expect(JSON.parse(String(cancels()[0][1]?.body))).toEqual({ job_id: "c1" });
  });

  it("goes when the server says its export was replaced", async () => {
    cancelStatus = 409;
    renderRoute("/report/sessions/");
    const cancel = await screen.findByTestId("bn-activity-chip-cancel", {}, { timeout: 5000 });
    act(() => cancel.click());
    await waitFor(() => expect(screen.queryByTestId("bn-activity-chip")).not.toBeInTheDocument());
    expect(cancels()).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// R72: in the Mac app the chip's Reveal asked the sandboxed sidecar to run `open -R`, which does
// nothing there (and the clips route said it had). The app reveals through its own bridge.
// ---------------------------------------------------------------------------

describe("Reveal in Finder on a finished export", () => {
  let postMessage: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    resetSidebarStore();
    resetActivityStore();
    postMessage = vi.fn();
    (window as unknown as Record<string, unknown>).webkit = {
      messageHandlers: { navigation: { postMessage } },
    };
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/export/clips/status")
        ? { status: "completed", progress: 3, total: 3, completed_count: 3, skipped_count: 0, current_clip: "", output_dir: "/Users/r/Study A/bristlenose-output/clips" }
        : url.includes("/export/screens/status")
          ? { status: "completed", progress: 2, total: 2, completed_count: 2, skipped_count: 0, current: "", output_dir: "/Users/r/Study A/bristlenose-output/screens", files: ["p1-01.jpg", "p1-02.jpg"] }
          : url.includes("/sessions")
            ? { sessions: [] }
            : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  afterEach(() => {
    resetActivityStore();
    delete (window as unknown as Record<string, unknown>).webkit;
  });

  const reveals = () =>
    postMessage.mock.calls.map((c) => c[0]).filter((m) => m?.action === "reveal-in-finder");
  const serverReveals = () =>
    vi.mocked(globalThis.fetch).mock.calls.filter((c) => String(c[0]).includes("/reveal"));

  async function revealFinished(id: string, type: "clips" | "screens") {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    renderRoute("/report/sessions/");
    act(() => {
      addJob(id, { type, frameworkId: "", frameworkTitle: "", total: 2 });
    });
    const action = await screen.findByTestId("bn-activity-chip-action", {}, { timeout: 5000 });
    act(() => action.click());
  }

  it("a clips export is shown in Finder by the app, not the sidecar", async () => {
    await revealFinished("clips", "clips");
    await waitFor(() => expect(reveals()).toHaveLength(1));
    expect(reveals()[0].data).toEqual({ uri: "file:///Users/r/Study%20A/bristlenose-output/clips" });
    expect(serverReveals()).toHaveLength(0);
  });

  it("a screens export is shown with its first still selected", async () => {
    await revealFinished("screens:r72", "screens");
    await waitFor(() => expect(reveals()).toHaveLength(1));
    expect(reveals()[0].data).toEqual({
      uri: "file:///Users/r/Study%20A/bristlenose-output/screens/p1-01.jpg",
    });
    expect(serverReveals()).toHaveLength(0);
  });

  it("a reveal the server could not do says so, not only the console (#44)", async () => {
    const fetchAnswers = vi.mocked(globalThis.fetch).getMockImplementation()!;
    vi.mocked(globalThis.fetch).mockImplementation(async (input, init) =>
      String(input).includes("/reveal")
        ? new Response(JSON.stringify({ revealed: false, path: "/x/clips" }), {
            status: 200, headers: { "Content-Type": "application/json" },
          })
        : fetchAnswers(input, init),
    );
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      renderRoute("/report/sessions/"); // a browser: the server's reveal route
      act(() => {
        addJob("clips", { type: "clips", frameworkId: "", frameworkTitle: "", total: 2 });
      });
      const action = await screen.findByTestId("bn-activity-chip-action", {}, { timeout: 5000 });
      act(() => action.click());
      expect(await screen.findByText("Couldn’t show the folder.")).toBeInTheDocument();
    } finally {
      logged.mockRestore();
    }
  });
});
