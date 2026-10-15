import { useEffect, useRef } from "react";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { getQuotesSnapshot, hideQuotes, resetStore, unhideQuotes } from "../../contexts/QuotesContext";
import { getUndoState, redo, resetUndoStore, undo } from "../../contexts/UndoStore";
import { resetLiveResize, setLiveResize } from "../../utils/liveResize";
import { resetSidebarStore, toggleTagGroupHidden, useSidebarStore } from "../../contexts/SidebarStore";
import type { QuoteResponse, QuotesListResponse } from "../../utils/types";
import { FocusProvider, useFocus } from "../../contexts/FocusContext";
import { arrangementFor, CARD_W, COLUMN_GUTTER, MOVE_STEP, resetArrangementMemory, type Arrangement } from "./layout";
import { resetScreensNav, screensNavState, toggleScreensNav } from "./navPanel";

vi.mock("../../utils/announce", () => ({ announce: vi.fn(), setAnnounceElement: vi.fn() }));
// jsdom has no canvas and resolves no CSS variable, so the paper sampler and the accent probe are
// stubbed; both answer null by default, which is "no paper yet": today's line, unchanged.
const paperStub = vi.hoisted(() => ({
  sample: null as [number, number, number] | null,
  accents: null as { light: [number, number, number]; dark: [number, number, number] } | null,
}));
vi.mock("./paper", async (orig) => ({
  ...(await orig<typeof import("./paper")>()),
  samplePaper: vi.fn(async () => paperStub.sample),
  readAccents: () => paperStub.accents,
}));

vi.mock("../../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
  putStarred: vi.fn(),
  putHidden: vi.fn(),
  putTags: vi.fn(),
  putEdits: vi.fn(),
  putHiddenTagGroups: vi.fn(),
  putFrameworkStates: vi.fn(),
  getFrameworkStates: vi.fn(),
  sendPut: vi.fn(() => Promise.resolve()),
}));

import { announce } from "../../utils/announce";
import { papers } from "./paper";
import { featureFlags, resetFeatureFlags } from "../../utils/featureFlags";
import { apiGet, getCodebook, sendPut } from "../../utils/api";
import { failedText, NAV_W, quotesOnScreen, ScreensLens, SCREENS_POLL_LIMIT, shouldPoll, unavailableText, type ScreensResponse } from "./ScreensLens";

/** The board's ResizeObserver callbacks, so a test can resize the stage. */
const observers = new Set<() => void>();
const resized = () =>
  act(() => {
    observers.forEach((cb) => cb());
  });

beforeAll(() => {
  // J/K bring a card forward through FocusContext, which scrolls it into view; jsdom has no
  // scrollIntoView, so without this each step throws in a requestAnimationFrame after the test.
  Element.prototype.scrollIntoView ??= () => {};
  // jsdom has no ResizeObserver; the board measures through one.
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = class {
    cb: () => void;
    constructor(cb: () => void) {
      this.cb = cb;
      observers.add(cb);
    }
    observe() {}
    disconnect() {
      observers.delete(this.cb);
    }
  };
});

function quote(start: number, text: string): QuoteResponse {
  return {
    dom_id: `q-p1-${start}`, text, verbatim_excerpt: text, participant_id: "p1", session_id: "s1",
    speaker_name: "p1", start_timecode: start, end_timecode: start + 5, sentiment: null, intensity: 1,
    researcher_context: null, quote_type: "screen_specific", topic_label: "", is_starred: false,
    is_hidden: false, edited_text: null, tags: [], deleted_badges: [], proposed_tags: [], segment_index: 0,
  } as unknown as QuoteResponse;
}

const QUOTES: QuotesListResponse = {
  sections: [], themes: [],
  // q-p1-50 is on no screen: a quote a selection made on the Quotes lens can carry here.
  unjoined: [quote(10, "so I click continue to checkout now"), quote(30, "this is quite expensive"),
             quote(50, "somewhere else entirely")],
  total_quotes: 2, total_hidden: 0, total_starred: 0, has_moderator: false,
} as unknown as QuotesListResponse;

const TAB = {
  session_id: "s1", code: "p1", t: 12, crop: [0, 0.1, 0.9, 1], heading: "Shopping Bag", visits: [[0, 60]],
  pins: [{ dom_id: "q-p1-10", box: [0.5, 0.6, 0.3, 0.04], phrase: "continue to checkout", line: "Continue to checkout" }],
  loose: ["q-p1-30"],
};

function screensResponse(over: Record<string, unknown> = {}) {
  return {
    enabled: true, unavailable: null, pending: false, reading: null, videos: 1, indexed: 1,
    screens: [
      { key: "url:/shoppingcart", name: "/shoppingcart", quotes: 2, tabs: [TAB] },
      { key: "url:/order/delivery", name: "/order/delivery", quotes: 0,
        tabs: [{ ...TAB, heading: "Delivery or collect", pins: [], loose: [], t: 80 }] },
    ],
    ...over,
  };
}

// What the server holds for /screens/arrangements: seeded per test, read when the lens opens.
let serverArrangements: { screen_key: string; session_id: string; cards: Arrangement }[] = [];
const seed = (screenKey: string, sessionId: string, cards: Arrangement) =>
  serverArrangements.push({ screen_key: screenKey, session_id: sessionId, cards });

function mockApi(screens: unknown) {
  vi.mocked(apiGet).mockImplementation(((path: string) => {
    if (path === "/screens") return Promise.resolve(screens);
    if (path === "/quotes") return Promise.resolve(QUOTES);
    if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
    return Promise.reject(new Error(path));
  }) as typeof apiGet);
}

const screensCalls = () => vi.mocked(apiGet).mock.calls.filter(([p]) => p === "/screens").length;

async function opened() {
  render(<ScreensLens />);
  await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
}

beforeEach(() => {
  vi.clearAllMocks();
  resetStore();
  resetSidebarStore();
  resetArrangementMemory();
  resetScreensNav();
  resetLiveResize();
  resetUndoStore();
  vi.mocked(getCodebook).mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
  serverArrangements = [];
  // The fake server keeps what is PUT to it, one version per write, as the route does.
  vi.mocked(sendPut).mockImplementation(((path: string, body: unknown) => {
    if (path === "/screens/arrangement") {
      const b = body as { screen_key: string; session_id: string; cards: Arrangement | null };
      serverArrangements = serverArrangements.filter((v) => !(v.screen_key === b.screen_key && v.session_id === b.session_id));
      if (b.cards) serverArrangements.push({ screen_key: b.screen_key, session_id: b.session_id, cards: b.cards });
    }
    return Promise.resolve();
  }) as typeof sendPut);
  paperStub.sample = null;
  paperStub.accents = null;
  papers.clear();
  try {
    localStorage.clear();
  } catch {
    /* jsdom without storage */
  }
});

afterEach(() => {
  document.getElementById("bn-app-root")?.remove();
  vi.useRealTimers();
});

describe("ScreensLens", () => {
  it("lists every screen by its page title", async () => {
    mockApi(screensResponse());
    await opened();
    const nav = screen.getByRole("navigation", { name: "Screens" });
    expect(nav).toHaveTextContent("2 screens · 1 participant");
    // The address, codes and count are kept and not shown for now (NAV_DETAILS).
    expect(nav).not.toHaveTextContent("/shoppingcart");
    expect(nav).toHaveTextContent("Delivery or collect");
  });

  it("keeps the screen's path on the info line and parks the quote count (the owner, 15 Oct 2026)", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-sub")).not.toBeNull());
    const sub = container.querySelector(".screens-sub")!;
    expect(sub.querySelector("code")).toHaveTextContent("/");
    expect(sub).not.toHaveTextContent(/\bquotes?\b/);
  });

  it("still says the count when the flag is on", async () => {
    featureFlags.screensQuoteCount = true;
    onTestFinished(resetFeatureFlags);
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-sub")).not.toBeNull());
    expect(container.querySelector(".screens-sub")).toHaveTextContent(/\d+ quotes?/);
  });

  it("puts its zone title where the shared datum rule reaches it", async () => {
    // `.center > main > section:first-of-type > .section-heading` (report.css): the heading must be
    // a direct child of the lens's outermost section, with no controls bar above it.
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".section-heading")).not.toBeNull());
    const section = container.firstElementChild!;
    expect(section.tagName).toBe("SECTION");
    const heading = section.querySelector(":scope > .section-heading");
    expect(heading).not.toBeNull();
    expect(container.querySelector("main")).toBeNull(); // no <main> inside <main>
    expect(container.querySelector("select")).toBeNull(); // the prototype's pickers are gone
  });

  it("keeps the zone title on the datum while it loads and when it has nothing to show", async () => {
    vi.mocked(apiGet).mockImplementation((() => new Promise(() => {})) as unknown as typeof apiGet);
    const { container, unmount } = render(<ScreensLens />);
    expect(container.querySelector(":scope > section > .section-heading")).not.toBeNull();
    unmount();
    mockApi(screensResponse({ enabled: false, screens: [] }));
    const r = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Screens are off/)).toBeInTheDocument());
    expect(r.container.querySelector(":scope > section > .section-heading")).not.toBeNull();
  });

  it("draws each quote with the Quotes lens's card: the words read aloud marked, the timecode a link", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-col blockquote")).not.toBeNull());
    const pinned = container.querySelector(".screens-col blockquote")!;
    expect(pinned.querySelector("mark")).toHaveTextContent("continue to checkout");
    // TimecodeLink, not a bare span: it plays the clip.
    expect(pinned.querySelector("a.timecode")).not.toBeNull();
    const loose = container.querySelector(".screens-loose blockquote")!;
    expect(loose).toHaveTextContent("this is quite expensive");
    // No heading over the unpinned quotes: they are not lesser, only unmatched.
    expect(container.querySelector(".screens-lens h2, .screens-lens h3")).toBeNull();
  });

  it("stars and hides through the report's own store", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote")).not.toBeNull());
    const loose = container.querySelector<HTMLElement>(".screens-loose blockquote")!;
    fireEvent.click(loose.querySelector(".star-btn")!);
    expect(getQuotesSnapshot().starred["q-p1-30"]).toBe(true);
    act(() => {
      fireEvent.click(loose.querySelector(".hide-btn")!);
    });
    await waitFor(() => expect(getQuotesSnapshot().hidden["q-p1-30"]).toBe(true));
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote")).toBeNull());
    expect(screen.getByText(/1 hidden quote/)).toBeInTheDocument();
  });

  it("un-hides a tag's group when a tag from it is added, as the Quotes lens does", async () => {
    vi.mocked(getCodebook).mockResolvedValue({
      all_tag_names: ["slow"], ungrouped: [],
      groups: [{ id: 1, name: "Friction", colour_set: "ux", framework_id: null, tags: [{ name: "slow", colour_index: 2 }] }],
    } as never);
    mockApi(screensResponse());
    toggleTagGroupHidden("Friction");
    const sidebar = renderHook(() => useSidebarStore());
    expect(sidebar.result.current.hiddenTagGroups.has("Friction")).toBe(true);
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote .badge-add")).not.toBeNull());
    fireEvent.click(container.querySelector(".screens-loose blockquote .badge-add")!);
    const input = container.querySelector<HTMLInputElement>(".screens-loose blockquote input")!;
    fireEvent.change(input, { target: { value: "slow" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(getQuotesSnapshot().tags["q-p1-30"]?.map((t) => [t.name, t.codebook_group])).toEqual([["slow", "Friction"]]);
    expect(sidebar.result.current.hiddenTagGroups.has("Friction")).toBe(false);
  });

  it("moves between screens with the arrow keys", async () => {
    mockApi(screensResponse());
    await opened();
    fireEvent.keyDown(document, { key: "ArrowDown" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
  });

  it("leaves arrow keys alone when they are a chord, already handled, or a dialog is open", async () => {
    mockApi(screensResponse());
    await opened();
    const h1 = () => screen.getByRole("heading", { level: 1 });
    fireEvent.keyDown(document, { key: "ArrowDown", metaKey: true });
    fireEvent.keyDown(document, { key: "ArrowDown", altKey: true });
    fireEvent.keyDown(document, { key: "ArrowDown", ctrlKey: true });
    expect(h1()).toHaveTextContent("Shopping Bag");
    // Someone nearer the target already used it (a separator, a list, a menu).
    const handled = new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true });
    handled.preventDefault();
    act(() => {
      document.dispatchEvent(handled);
    });
    expect(h1()).toHaveTextContent("Shopping Bag");
    // A dialog (Help, Settings) owns the keyboard.
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    const button = document.createElement("button");
    dialog.appendChild(button);
    document.body.appendChild(dialog);
    fireEvent.keyDown(button, { key: "ArrowDown" });
    dialog.remove();
    const root = document.createElement("div");
    root.id = "bn-app-root";
    root.setAttribute("inert", "");
    document.body.appendChild(root);
    fireEvent.keyDown(document, { key: "ArrowDown" });
    expect(h1()).toHaveTextContent("Shopping Bag");
  });

  it("says why there is nothing to show", async () => {
    mockApi(screensResponse({ enabled: false, screens: [] }));
    const { unmount } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Screens are off/)).toBeInTheDocument());
    unmount();
    mockApi(screensResponse({ screens: [], indexed: 1, videos: 1 }));
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/No screens found/)).toBeInTheDocument());
  });

  it("names a recording it could not read, and one with no text, in its own words", async () => {
    mockApi(screensResponse({ screens: [], indexed: 1, videos: 2, failed: { s2: "read_failed" }, blank: ["s1"] }));
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText("Couldn’t read s2: reading its screen failed.")).toBeInTheDocument());
    expect(screen.getByText(/No text found in s1’s recording/)).toBeInTheDocument();
    expect(screen.queryByText(/Reading screens/)).toBeNull();
    expect(screen.queryByText(/No screens found/)).toBeNull(); // the one indexed recording had no text
  });

  it("never shows a reason code or server text, only a sentence", async () => {
    mockApi(screensResponse({ screens: [], indexed: 0, videos: 2,
                              failed: { s1: "cloud_downloading", s2: "ValueError: no video stream" } }));
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Couldn’t read s1: the recording is still downloading/)).toBeInTheDocument());
    expect(screen.getByText("Couldn’t read s2: something went wrong reading it.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/ValueError|cloud_downloading/);
  });

  it("says why screens can't be read here, by code", async () => {
    mockApi(screensResponse({ unavailable: "not_macos", screens: [] }));
    const { container, unmount } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(unavailableText("not_macos"))).toBeInTheDocument());
    expect(container.textContent).not.toContain("not_macos");
    unmount();
    mockApi(screensResponse({ unavailable: "pyobjc exploded: Traceback", screens: [] }));
    const r = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText("Screens can’t be read here.")).toBeInTheDocument());
    expect(r.container.textContent).not.toContain("Traceback");
  });

  it("has a sentence for every reason the server sends", () => {
    for (const code of ["not_macos", "vision_missing", "no_job"]) {
      expect(unavailableText(code)).not.toBe(unavailableText("unknown"));
    }
    for (const code of ["unreadable", "cloud_downloading", "ffprobe_failed", "read_failed", "not_read"]) {
      expect(failedText(code)).not.toBe(failedText("unknown"));
    }
  });

  it("says the quotes failed to load rather than showing every screen empty", async () => {
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      if (path === "/screens") return Promise.resolve(screensResponse());
      if (path === "/quotes") return Promise.reject(new Error("401 Unauthorized"));
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Couldn’t load the quotes/)).toBeInTheDocument());
    expect(container.textContent).not.toContain("401");
  });

  // The page's project id is always "1" today (server/app.py), so this separates by origin only;
  // it pins that the key carries the id, for when multi-project makes it real.
  it("keys a rearranged board by the page's project id", async () => {
    const spot = JSON.stringify({ "s1@12/q-p1-10": { kind: "edge", side: "R", frac: 0.1, z: 31 } });
    const root = document.createElement("div");
    root.id = "bn-app-root";
    root.setAttribute("data-project-id", "2");
    document.body.appendChild(root);
    // Stored under another id: not this page's.
    localStorage.setItem("bristlenose-screens-placements-1", spot);
    mockApi(screensResponse());
    const first = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
    first.unmount();
    resetArrangementMemory();
    localStorage.setItem("bristlenose-screens-placements-2", spot);
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument());
  });

  it("reports its navigator to the shell, and hides it when asked", async () => {
    mockApi(screensResponse());
    await opened();
    expect(screensNavState().shown).toBe(true);
    expect(screen.getByRole("navigation", { name: "Screens" })).toBeInTheDocument();
    const { toggleScreensNav } = await import("./navPanel");
    act(() => toggleScreensNav()); // what the rail button, ⌥⌘L and [ do
    expect(screen.queryByRole("navigation", { name: "Screens" })).toBeNull();
    expect(screensNavState().shown).toBe(false);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
  });

  it("toggles what is showing: with no board, the toggle opens rather than remembering it closed", async () => {
    mockApi(screensResponse({ enabled: false, screens: [] }));
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Screens are off/)).toBeInTheDocument());
    // The View menu and the rail button read `shown`, which is false here.
    expect(screensNavState()).toMatchObject({ wish: true, shown: false });
    act(() => toggleScreensNav());
    expect(screensNavState().wish).toBe(true);
  });

  it("sets the navigator's width from the one source the stylesheet reads", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-lens")).not.toBeNull());
    const lens = container.querySelector<HTMLElement>(".screens-lens")!;
    // screens.css's grid reads var(--screens-nav-w) and names no width of its own (vitest stubs
    // CSS, so the stylesheet half is pinned by its comment, not here).
    expect(lens.style.getPropertyValue("--screens-nav-w")).toBe(`${NAV_W}px`);
  });

  it("keeps showing the board when one look fails, and looks again", async () => {
    vi.useFakeTimers();
    vi.spyOn(console, "error").mockImplementation(() => {});
    let n = 0;
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      if (path === "/screens") {
        n += 1;
        // Still reading, so it polls; the second look fails (the sidecar restarting).
        return n === 2 ? Promise.reject(new Error("401")) : Promise.resolve(screensResponse({ indexed: 0 }));
      }
      if (path === "/quotes") return Promise.resolve(QUOTES);
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    render(<ScreensLens />);
    // Looks at 0 s and 7.5 s (which fails); the retry is due at 18.75 s. In between, the board stays.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(n).toBe(2);
    expect(screen.queryByText("Couldn’t load the screens.")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(n).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("Couldn’t load the screens.")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
  });

  it("clears a failed first load once a later look succeeds", async () => {
    vi.useFakeTimers();
    vi.spyOn(console, "error").mockImplementation(() => {});
    let n = 0;
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      if (path === "/screens") {
        n += 1;
        return n === 1 ? Promise.reject(new Error("401")) : Promise.resolve(screensResponse());
      }
      if (path === "/quotes") return Promise.resolve(QUOTES);
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    render(<ScreensLens />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("Couldn’t load the screens.")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(screen.queryByText("Couldn’t load the screens.")).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
  });

  it("clears a failed quotes load when a refresh loads them", async () => {
    const { bumpRefreshKey } = await import("../../contexts/LastRunStore");
    vi.spyOn(console, "error").mockImplementation(() => {});
    let n = 0;
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      if (path === "/screens") return Promise.resolve(screensResponse());
      if (path === "/quotes") {
        n += 1;
        return n === 1 ? Promise.reject(new Error("401")) : Promise.resolve(QUOTES);
      }
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Couldn’t load the quotes/)).toBeInTheDocument());
    act(() => bumpRefreshKey());
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    expect(screen.queryByText(/Couldn’t load the quotes/)).toBeNull();
  });
});


describe("Tidy", () => {
  const key = "bristlenose-screens-placements-1";
  const placed = JSON.stringify({ "s1@12/q-p1-10": { kind: "edge", side: "R", frac: 0.4, z: 31 } });
  beforeEach(async () => {
    const { resetUndoStore } = await import("../../contexts/UndoStore");
    resetUndoStore();
    localStorage.setItem(key, placed);
  });

  it("says nothing while the layout is automatic", async () => {
    localStorage.removeItem(key);
    mockApi(screensResponse());
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
  });

  it("tells the Mac whether the arrangement is custom, so View ▸ Tidy enables only then", async () => {
    const post = vi.fn();
    (window as unknown as { webkit: unknown }).webkit = { messageHandlers: { navigation: { postMessage: post } } };
    try {
      mockApi(screensResponse());
      const { unmount } = render(<ScreensLens />);
      const control = await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
      const said = () => post.mock.calls.map((c) => c[0]).filter((m) => m.type === "screens-arrangement");
      expect(said().slice(-1)[0]).toEqual({ type: "screens-arrangement", custom: true });
      fireEvent.click(control);
      await waitFor(() => expect(said().slice(-1)[0]).toEqual({ type: "screens-arrangement", custom: false }));
      unmount();
    } finally {
      delete (window as unknown as { webkit?: unknown }).webkit;
    }
  });

  it("moves focus to the lens's title when Tidy removes its own button", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    const control = await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
    control.focus();
    fireEvent.click(control);
    const h1 = screen.getByRole("heading", { level: 1 });
    await waitFor(() => expect(document.activeElement).toBe(h1));
  });

  it("gives focus back to where it was when the menu closes, and its items are not tab stops", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
    const star = container.querySelector<HTMLElement>('.screens-card[data-dom="q-p1-10"] .star-btn')!;
    star.focus();
    fireEvent.contextMenu(star);
    const items = await screen.findAllByRole("menuitem");
    expect(items.every((i) => i.tabIndex === -1)).toBe(true);
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
    expect(document.activeElement).toBe(star);
  });

  it("closes the menu when focus moves out of it", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    const control = await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
    fireEvent.contextMenu(screen.getByRole("heading", { level: 1 }).closest("section")!.querySelector(".screens-stage")!);
    const items = await screen.findAllByRole("menuitem");
    fireEvent.focusOut(items[0], { relatedTarget: control });
    await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());
  });
});

describe("a selection made on another lens", () => {
  /** Selects ids the way the Quotes lens would have left them selected. */
  function Selected({ ids }: { ids: string[] }) {
    const { toggleSelection } = useFocus();
    const done = useRef(false);
    useEffect(() => {
      if (done.current) return;
      done.current = true;
      ids.forEach(toggleSelection);
    }, [ids, toggleSelection]);
    return null;
  }

  async function board(ids: string[]) {
    mockApi(screensResponse());
    const r = render(
      <FocusProvider>
        <Selected ids={ids} />
        <ScreensLens />
      </FocusProvider>,
    );
    await waitFor(() => expect(r.container.querySelector(".screens-loose blockquote")).not.toBeNull());
    return r.container;
  }

  it("stars only the selected quotes on this board", async () => {
    const c = await board(["q-p1-30", "q-p1-50"]);
    fireEvent.click(c.querySelector(".screens-loose blockquote .star-btn")!);
    expect(getQuotesSnapshot().starred["q-p1-30"]).toBe(true);
    expect(getQuotesSnapshot().starred["q-p1-50"]).toBeFalsy();
  });

  it("hides only the selected quotes on this board", async () => {
    const c = await board(["q-p1-30", "q-p1-50"]);
    act(() => {
      fireEvent.click(c.querySelector(".screens-loose blockquote .hide-btn")!);
    });
    await waitFor(() => expect(getQuotesSnapshot().hidden["q-p1-30"]).toBe(true));
    expect(getQuotesSnapshot().hidden["q-p1-50"]).toBeFalsy();
  });

  it("selects a shift-click range in the board's own order", async () => {
    const c = await board([]);
    const pinned = c.querySelector<HTMLElement>(".screens-col blockquote")!;
    const loose = c.querySelector<HTMLElement>(".screens-loose blockquote")!;
    fireEvent.click(pinned, { metaKey: true });
    fireEvent.click(loose, { shiftKey: true });
    expect(pinned.className).toContain("bn-selected");
    expect(loose.className).toContain("bn-selected");
  });
});

describe("where the cards go", () => {
  // Rows replace "the pinned cards lead the list" (the owner, 15 Oct 2026): below the side-column
  // threshold the side bands become rows above and below the screengrab; the list stays below.
  it("puts linked cards in rows above and below the screengrab when the stage is too narrow for a column", async () => {
    const spy = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(600);
    try {
      mockApi(screensResponse());
      const { container } = render(<ScreensLens />);
      await waitFor(() => expect(container.querySelector(".screens-band .screens-card")).not.toBeNull());
      expect(container.querySelector(".screens-board")!.className).toContain("cols-none");
      expect(container.querySelector(".screens-col .screens-card")).toBeNull();
      // The linked quote's line is in the lower half: the row below.
      expect(container.querySelector<HTMLElement>(".screens-band-b .screens-card")!.dataset.dom).toBe("q-p1-10");
      // The unlinked one stays in the list, under everything.
      const listed = [...container.querySelectorAll<HTMLElement>(".screens-loose .screens-card")].map((c) => c.dataset.dom);
      expect(listed).toEqual(["q-p1-30"]);
    } finally {
      spy.mockRestore();
    }
  });

  it("gives the pinned card a column beside the screengrab when there is room", async () => {
    const spy = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    try {
      mockApi(screensResponse());
      const { container } = render(<ScreensLens />);
      await waitFor(() => expect(container.querySelector(".screens-col-r .screens-card")).not.toBeNull());
      expect(container.querySelector(".screens-board")!.className).toContain("cols-r");
    } finally {
      spy.mockRestore();
    }
  });
});



describe("for a keyboard and a screen reader", () => {
  it("describes the screengrab", async () => {
    mockApi(screensResponse());
    await opened();
    expect(screen.getByAltText("p1’s screen: Shopping Bag, at 00:12")).toBeInTheDocument();
  });

  it("announces a move to another screen, and to another participant's view of this one", async () => {
    const two = screensResponse();
    (two.screens as { tabs: unknown[] }[])[0].tabs.push({ ...TAB, session_id: "s2", code: "p2", t: 40 });
    mockApi(two);
    await opened();
    vi.mocked(announce).mockClear();
    fireEvent.keyDown(document, { key: "ArrowRight" });
    expect(announce).toHaveBeenLastCalledWith("p2’s screen at 00:40 · 2 of 2");
    fireEvent.keyDown(document, { key: "ArrowDown" });
    expect(announce).toHaveBeenLastCalledWith("Delivery or collect, screen 2 of 2");
  });

  it("leaves ↑/↓ to the page when there is only one screen", async () => {
    const one = screensResponse();
    (one.screens as unknown[]).splice(1);
    mockApi(one);
    await opened();
    const down = new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true });
    act(() => {
      document.dispatchEvent(down);
    });
    expect(down.defaultPrevented).toBe(false);
  });
});

describe("focus when the board changes under it", () => {
  // The board remounts on every move; focus inside it used to fall to the page (accessibility
  // review, 14 Oct 2026).
  it("moves focus from a card to the new board's title when ↓ changes screen", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-loose .star-btn")).not.toBeNull());
    const star = container.querySelector<HTMLElement>(".screens-loose .star-btn")!;
    star.focus();
    expect(document.activeElement).toBe(star);
    vi.mocked(announce).mockClear();
    fireEvent.keyDown(star, { key: "ArrowDown" });
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveTextContent("Delivery or collect");
    expect(document.activeElement).toBe(h1);
    expect(h1.tabIndex).toBe(-1); // a target, not a tab stop
    // The focused title says where we are; an announcement as well would say it twice.
    expect(announce).not.toHaveBeenCalled();
  });

  it("leaves the arrow keys to a dropdown open under focus", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    const dropdown = document.createElement("div");
    dropdown.className = "bn-hidden-dropdown";
    const item = document.createElement("span");
    item.setAttribute("role", "button");
    item.tabIndex = 0;
    dropdown.appendChild(item);
    container.querySelector("section")!.appendChild(dropdown);
    item.focus();
    fireEvent.keyDown(item, { key: "ArrowDown" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
  });

  it("keeps focus in the navigator, on the link that is now current", async () => {
    mockApi(screensResponse());
    await opened();
    const links = screen.getByRole("navigation", { name: "Screens" }).querySelectorAll<HTMLElement>("a");
    links[0].focus();
    fireEvent.keyDown(links[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(links[1]);
    expect(links[1]).toHaveAttribute("aria-current", "true");
  });

  it("leaves focus alone when it was not in the lens", async () => {
    mockApi(screensResponse());
    await opened();
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    try {
      outside.focus();
      fireEvent.keyDown(document, { key: "ArrowDown" });
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
      expect(document.activeElement).toBe(outside);
    } finally {
      outside.remove();
    }
  });
});

describe("a keyboard route to every card", () => {
  /** Focusable, and not hidden from the keyboard by an ancestor. */
  function tabbable(el: HTMLElement): boolean {
    if (el.tabIndex < 0 || (el as HTMLButtonElement).disabled) return false;
    for (let n: HTMLElement | null = el; n; n = n.parentElement) {
      if (n.hasAttribute("inert") || n.getAttribute("aria-hidden") === "true") return false;
      if (n.style.visibility === "hidden" || n.style.display === "none") return false;
    }
    return true;
  }

  it("reaches a control in every card, a stacked column's included", async () => {
    // A stage wide enough for one column, a screengrab, and cards tall enough that three pinned
    // close together must stack.
    const w = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    const h = vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(300);
    const oh = vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(200);
    try {
      const stack = {
        ...TAB, loose: [],
        pins: [
          { dom_id: "q-p1-10", box: [0.6, 0.2, 0.3, 0.04], phrase: "continue", line: "Continue" },
          { dom_id: "q-p1-30", box: [0.6, 0.25, 0.3, 0.04], phrase: "expensive", line: "Expensive" },
          { dom_id: "q-p1-50", box: [0.6, 0.3, 0.3, 0.04], phrase: "somewhere", line: "Somewhere" },
        ],
      };
      mockApi(screensResponse({ screens: [{ key: "url:/x", name: "/x", quotes: 3, tabs: [stack] }] }));
      const { container } = render(<ScreensLens />);
      await waitFor(() => expect(container.querySelectorAll(".screens-card")).toHaveLength(3));
      await waitFor(() => expect(container.querySelector(".screens-col-r.stacked")).not.toBeNull());
      const cards = [...container.querySelectorAll<HTMLElement>(".screens-card")];
      for (const card of cards) {
        const reach = [...card.querySelectorAll<HTMLElement>("button, a[href]")].filter(tabbable);
        expect(reach.length, card.dataset.dom).toBeGreaterThan(0);
      }
    } finally {
      w.mockRestore();
      h.mockRestore();
      oh.mockRestore();
    }
  });

  it("reaches the arrangement control, which is Tidy's keyboard route", async () => {
    localStorage.setItem("bristlenose-screens-placements-1",
      JSON.stringify({ "s1@12/q-p1-10": { kind: "edge", side: "R", frac: 0.5, z: 31 } }));
    mockApi(screensResponse());
    render(<ScreensLens />);
    const tidy = await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
    expect(tabbable(tidy)).toBe(true);
  });
});

describe("one live region", () => {
  const reading = (over: Record<string, unknown> = {}) =>
    screensResponse({ pending: true, videos: 3, indexed: 1, reading: "s2", failed: { s3: "read_failed" }, ...over });

  it("carries only how far reading has got, never what could not be read", async () => {
    mockApi(reading());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    const live = container.querySelectorAll('[role="status"], [aria-live]');
    expect(live).toHaveLength(1);
    expect(live[0]).toHaveTextContent("Reading screens… 1 of 3 recordings. Now reading s2.");
    // The failure is said, in a plain list, outside any live region.
    const failure = screen.getByText("Couldn’t read s3: reading its screen failed.");
    expect(failure.closest('[role="status"], [aria-live], [role="alert"]')).toBeNull();
    expect(failure.closest("ul")).not.toBeNull();
  });

  it("is the same element from the first render, across a change of screen", async () => {
    vi.useFakeTimers();
    let resolve: (v: unknown) => void = () => {};
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      if (path === "/screens") return new Promise<unknown>((r) => (resolve = r));
      if (path === "/quotes") return Promise.resolve(QUOTES);
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    const { container } = render(<ScreensLens />);
    const region = container.querySelector('[role="status"]');
    expect(region).not.toBeNull();
    await act(async () => {
      resolve(reading());
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
    expect(container.querySelector('[role="status"]')).toBe(region);
    fireEvent.keyDown(document, { key: "ArrowDown" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
    expect(container.querySelector('[role="status"]')).toBe(region);
    expect(region).toHaveTextContent(/Reading screens… 1 of 3 recordings/);
  });

  it("says nothing once reading is done", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    expect(container.querySelector('[role="status"]')!.textContent).toBe("");
  });
});

describe("polling /screens", () => {
  const base: ScreensResponse = {
    enabled: true, unavailable: null, pending: false, reading: null, videos: 2, indexed: 1, screens: [],
  };

  it("polls while reading or waiting to read, and not when it cannot help", () => {
    expect(shouldPoll({ ...base, pending: true })).toBe(true);
    expect(shouldPoll(base)).toBe(true); // one recording neither read nor failed
    expect(shouldPoll({ ...base, indexed: 2 })).toBe(false);
    expect(shouldPoll({ ...base, enabled: false })).toBe(false);
    expect(shouldPoll({ ...base, unavailable: "no_job" })).toBe(false);
    // The job has said it will not read it: asking again cannot change that until a run ends.
    expect(shouldPoll({ ...base, videos: 3, failed: { s2: "not_read" } })).toBe(false);
  });

  it("stops asking once the job says a recording was not read", async () => {
    vi.useFakeTimers();
    mockApi({ ...base, videos: 3, failed: { s2: "not_read" } });
    render(<ScreensLens />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(screensCalls()).toBe(1);
  });

  it("gives up after a bounded number of looks when nothing ever changes", async () => {
    vi.useFakeTimers();
    mockApi(base);
    render(<ScreensLens />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(24 * 3600_000);
    });
    expect(screensCalls()).toBe(SCREENS_POLL_LIMIT);
  });

  it("looks again when a run ends, and resumes polling if there is still reading to do", async () => {
    const { bumpRefreshKey } = await import("../../contexts/LastRunStore");
    vi.useFakeTimers();
    // Nothing is going to read it (not_read): the lens stops asking.
    mockApi({ ...base, videos: 3, failed: { s2: "not_read" } });
    render(<ScreensLens />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(screensCalls()).toBe(1);
    // A run finishes (or the project changes); the next pass starts.
    mockApi({ ...base, pending: true });
    await act(async () => {
      bumpRefreshKey();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screensCalls()).toBe(2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000);
    });
    expect(screensCalls()).toBeGreaterThan(2);
  });
});

// ── Composition (docs/design-screens.md S5, 15 Oct 2026) ─────────────────

/** A second participant's quote. */
function quoteBy(person: string, start: number, text: string): QuoteResponse {
  return { ...quote(start, text), dom_id: `q-${person}-${start}`, participant_id: person, speaker_name: person,
           session_id: person === "p1" ? "s1" : "s2" } as QuoteResponse;
}

const TWO_QUOTES: QuotesListResponse = {
  ...QUOTES,
  unjoined: [...(QUOTES.unjoined ?? []), quoteBy("p2", 20, "the basket total looks wrong"),
             quoteBy("p2", 60, "where is the basket total")],
} as QuotesListResponse;

const SEARCH: [number, number, number, number] = [0.4, 0.03, 0.2, 0.04]; // top middle: the band above
const SIDE: [number, number, number, number] = [0.7, 0.5, 0.2, 0.04];

/** One screen, two versions. p2's version (the default) links three quotes, two of them on one
 *  line; p1's links one, which p2's does not. */
function versions(over: Record<string, unknown> = {}) {
  return screensResponse({
    videos: 2, indexed: 2,
    screens: [{
      key: "url:/basket", name: "/basket", quotes: 4, default_tab: 1,
      tabs: [
        { ...TAB, heading: "Basket" },
        { ...TAB, session_id: "s2", code: "p2", t: 40, heading: "Basket", loose: [],
          pins: [
            { dom_id: "q-p2-20", box: SEARCH, phrase: "basket total", line: "Basket total" },
            { dom_id: "q-p2-60", box: SEARCH, phrase: "basket total", line: "Basket total" },
            { dom_id: "q-p1-30", box: SIDE, phrase: "expensive", line: "Expensive" },
          ] },
      ],
    }, { key: "url:/order/delivery", name: "/order/delivery", quotes: 0,
         tabs: [{ ...TAB, heading: "Delivery or collect", pins: [], loose: [], t: 80 }] }],
    ...over,
  });
}

function mockVersions(screens: unknown = versions()) {
  vi.mocked(apiGet).mockImplementation(((path: string) => {
    if (path === "/screens") return Promise.resolve(screens);
    if (path === "/quotes") return Promise.resolve(TWO_QUOTES);
    if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
    return Promise.reject(new Error(path));
  }) as typeof apiGet);
}

const where = (c: HTMLElement, dom: string) => {
  const card = [...c.querySelectorAll<HTMLElement>(".screens-card")].find((el) => el.dataset.dom === dom);
  if (!card) return "absent";
  if (card.closest(".screens-loose")) return "list";
  if (card.closest(".screens-free")) return "free";
  if (card.closest(".screens-shot")) return "shot";
  return "margin";
};

async function openVersions(ui: React.ReactElement = <ScreensLens />) {
  const r = render(ui);
  await waitFor(() => expect(r.container.querySelectorAll(".screens-card")).toHaveLength(4));
  return r.container;
}

describe("a screen is one place for everything about it", () => {
  it("links only the quotes whose words are on the showing screengrab; the set never changes", async () => {
    mockVersions();
    const c = await openVersions();
    // p2's version: its three, whoever said them, in the margins; p1's line is not on it.
    expect(["q-p2-20", "q-p2-60", "q-p1-30"].map((d) => where(c, d))).toEqual(["margin", "margin", "margin"]);
    expect(where(c, "q-p1-10")).toBe("list");
    fireEvent.keyDown(document, { key: "ArrowLeft" });
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    expect(where(c, "q-p1-10")).toBe("margin");
    expect(["q-p2-20", "q-p2-60", "q-p1-30"].map((d) => where(c, d))).toEqual(["list", "list", "list"]);
    expect(c.querySelectorAll(".screens-card")).toHaveLength(4);
  });

  it("lists the rest in time order", async () => {
    mockVersions();
    const c = await openVersions();
    fireEvent.keyDown(document, { key: "ArrowLeft" });
    const listed = [...c.querySelectorAll<HTMLElement>(".screens-loose .screens-card")].map((el) => el.dataset.dom);
    expect(listed).toEqual(["q-p2-20", "q-p1-30", "q-p2-60"]);
  });

  it("offers the version an unlinked card is on, and turns to it", async () => {
    mockVersions();
    const c = await openVersions();
    const offer = screen.getByRole("button", { name: "On p1’s screen" });
    expect(offer.closest<HTMLElement>(".screens-card")!.dataset.dom).toBe("q-p1-10");
    fireEvent.click(offer);
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    expect(where(c, "q-p1-10")).toBe("margin");
    expect(announce).toHaveBeenLastCalledWith("p1’s screen at 00:12 · 1 of 2");
  });

  it("gives quotes about one line one highlight", async () => {
    mockVersions();
    const c = await openVersions();
    expect(c.querySelectorAll(".screens-hl")).toHaveLength(2); // three linked quotes, two lines
  });

  it("puts a header line's cards in the band above the screengrab, and a side line's in a column", async () => {
    const spy = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1200);
    try {
      mockVersions();
      const c = await openVersions();
      const band = [...c.querySelectorAll<HTMLElement>(".screens-band-t .screens-card")].map((el) => el.dataset.dom);
      expect(band).toEqual(["q-p2-20", "q-p2-60"]);
      expect(c.querySelector<HTMLElement>(".screens-col-r .screens-card")!.dataset.dom).toBe("q-p1-30");
    } finally {
      spy.mockRestore();
    }
  });

  // What this gates, and no more: with a measured screengrab, every linked card is placed (has a
  // spot) in a column or band track — never in the screengrab's own track or the free layer. jsdom
  // lays nothing out, so whether the tracks overlap is not seen here: that is the model in
  // layout.test.ts and the measurement on real data (docs/design-screens.md S5).
  it("places every linked card in a column or band, never the screengrab's track, at any width", async () => {
    for (const w of [1440, 1100, 900, 600]) {
      const width = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(w);
      const height = vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(300);
      const oh = vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(100);
      try {
        mockVersions();
        const { container, unmount } = render(<ScreensLens />);
        await waitFor(() => expect(container.querySelectorAll(".screens-card")).toHaveLength(4));
        const linked = () => [...container.querySelectorAll<HTMLElement>(".screens-card[data-pin]")];
        await waitFor(() => expect(linked().every((c) => c.style.visibility !== "hidden")).toBe(true));
        expect(linked()).toHaveLength(3);
        for (const card of linked()) {
          expect(card.closest(".screens-col, .screens-band"), `${w}px ${card.dataset.dom}`).not.toBeNull();
          expect(card.closest(".screens-shot, .screens-free")).toBeNull();
        }
        unmount();
      } finally {
        width.mockRestore();
        height.mockRestore();
        oh.mockRestore();
      }
    }
  });
});

describe("the carousel", () => {
  it("turns one slide per horizontal swipe", async () => {
    mockVersions();
    const c = await openVersions();
    const carousel = c.querySelector<HTMLElement>(".screens-slides")!;
    fireEvent.wheel(carousel, { deltaX: -40, deltaY: 0 });
    expect(await screen.findByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    // The same swipe's momentum does not turn it again (with two slides it would come back).
    fireEvent.wheel(carousel, { deltaX: -30, deltaY: 0 });
    fireEvent.wheel(carousel, { deltaX: -20, deltaY: 0 });
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
  });

  it("cross-fades in one frame: the neighbouring versions are in it, one showing", async () => {
    mockVersions();
    const c = await openVersions();
    await waitFor(() => expect(c.querySelectorAll(".screens-slide")).toHaveLength(2));
    expect(c.querySelectorAll(".screens-slide.is-current")).toHaveLength(1);
    expect(c.querySelector(".screens-slide:not(.is-current)")).toHaveAttribute("aria-hidden", "true");
  });
});



describe("the Mac's View menu", () => {
  const menu = (action: string) =>
    act(() => {
      window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action } }));
    });

  it("tidies the showing screengrab", async () => {
    localStorage.setItem("bristlenose-screens-placements-1",
      JSON.stringify({ "s2@40/q-p2-20": { kind: "edge", side: "R", frac: 0.5, z: 31 } }));
    mockVersions();
    await openVersions();
    expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
    menu("tidy");
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
  });
});

describe("a change of layout", () => {
  // Each card glides from its old place to its new one when the layout changes mode (FLIP), and
  // switches at once under reduced motion.
  async function resize(reduce: boolean) {
    const width = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(900);
    const height = vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(300);
    const oh = vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(100);
    const rect = vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const x = this.closest(".screens-col") ? 900 : 0;
      return { left: x, top: 0, right: x + 270, bottom: 100, width: 270, height: 100, x, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = animate;
    const mm = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: reduce && q.includes("reduce") })) as unknown as typeof window.matchMedia;
    try {
      mockApi(screensResponse());
      const { container } = render(<ScreensLens />);
      await waitFor(() => expect(container.querySelector(".screens-col-r .screens-card")).not.toBeNull());
      resized();
      expect(animate).not.toHaveBeenCalled(); // a resize within a mode: the cards follow it
      width.mockReturnValue(600);
      resized();
      await waitFor(() => expect(container.querySelector(".screens-band .screens-card")).not.toBeNull());
      return animate;
    } finally {
      width.mockRestore();
      height.mockRestore();
      oh.mockRestore();
      rect.mockRestore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
      window.matchMedia = mm;
    }
  }

  it("glides each card from where it was", async () => {
    const animate = await resize(false);
    expect(animate).toHaveBeenCalled();
    const [frames] = animate.mock.calls[0] as [Keyframe[]];
    expect(frames[0].transform).toBe("translate(900px, 0px)");
  });

  it("moves at once under reduced motion", async () => {
    const animate = await resize(true);
    expect(animate).not.toHaveBeenCalled();
  });
});

// ── Review fixes (15 Oct 2026) ───────────────────────────────────────────

const cardOf = (c: HTMLElement, dom: string) =>
  [...c.querySelectorAll<HTMLElement>(".screens-card")].find((el) => el.dataset.dom === dom)!;

/** A measured board: jsdom lays nothing out, so give every element a width and the screengrab a
 *  height, which is what lets placement give each card a spot. */
function measured(w = 900) {
  const spies = [
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(w),
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(300),
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(100),
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(function (this: HTMLElement) {
      return this.clientWidth;
    }),
  ];
  return { width: spies[0], restore: () => spies.forEach((s) => s.mockRestore()) };
}



describe("a placed card with no screengrab to place it against", () => {
  it("is listed with the rest rather than held hidden", async () => {
    // Stills are cached for the page's life: a time no other test asks for, so this one fails.
    const failing = versions();
    (failing.screens as { tabs: { t: number }[] }[])[0].tabs[1].t = 41;
    localStorage.setItem("bristlenose-screens-placements-1",
      JSON.stringify({ "s2@41/q-p1-10": { kind: "edge", side: "L", frac: 0.2, z: 31 } }));
    vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens") return Promise.resolve(failing);
      if (path === "/quotes") return Promise.resolve(TWO_QUOTES);
      if (path.includes("session_id=s2&t=41&w=1600")) return Promise.reject(new Error("404"));
      if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      return Promise.reject(new Error(path));
    }) as typeof apiGet);
    const c = await openVersions();
    await waitFor(() => expect(screen.getByText("Screengrab unavailable.")).toBeInTheDocument());
    const card = cardOf(c, "q-p1-10");
    expect(card.closest(".screens-loose")).not.toBeNull();
    expect(card.style.visibility).not.toBe("hidden");
  });
});


describe("focus after On p1's screen", () => {
  it("lands in the card once it has a place in the margin", async () => {
    const m = measured(900);
    // As a browser does: an element under visibility:hidden takes no focus, silently.
    const real = HTMLElement.prototype.focus;
    const focus = vi.spyOn(HTMLElement.prototype, "focus").mockImplementation(function (this: HTMLElement, o?: FocusOptions) {
      if (this.closest('[style*="visibility: hidden"]')) return;
      real.call(this, o);
    });
    try {
      mockVersions();
      const c = await openVersions();
      fireEvent.click(screen.getByRole("button", { name: "On p1’s screen" }));
      await waitFor(() => expect(cardOf(c, "q-p1-10").contains(document.activeElement)).toBe(true));
      expect(cardOf(c, "q-p1-10").closest(".screens-col")).not.toBeNull();
    } finally {
      focus.mockRestore();
      m.restore();
    }
  });
});

describe("leaders after a glide", () => {
  it("are measured again where the cards came to rest", async () => {
    const m = measured(900);
    let gliding = false;
    const rect = vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const x = this.closest(".screens-col") ? 900 : this.closest(".screens-band") && gliding ? 500 : 0;
      return { left: x, top: 0, right: x + 270, bottom: 100, width: 270, height: 100, x, y: 0, toJSON: () => ({}) } as DOMRect;
    });
    let land: () => void = () => {};
    const finished = new Promise<void>((r) => (land = r));
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = vi.fn(() => ({ finished }));
    try {
      mockApi(screensResponse());
      const { container } = render(<ScreensLens />);
      await waitFor(() => expect(container.querySelector(".screens-col-r .screens-card")).not.toBeNull());
      gliding = true;
      m.width.mockReturnValue(600);
      resized();
      const leader = () => container.querySelector("svg.screens-leaders path")?.getAttribute("d") ?? "";
      await waitFor(() => expect(leader().startsWith("M512,")).toBe(true)); // measured mid-glide
      gliding = false;
      await act(async () => {
        land();
        await finished;
      });
      await waitFor(() => expect(leader().startsWith("M258,")).toBe(true));
    } finally {
      rect.mockRestore();
      m.restore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
    }
  });
});

describe("stills", () => {
  it("fetches and mounts only the showing slide and its neighbours", async () => {
    const five = screensResponse({
      screens: [{ key: "url:/x", name: "/x", quotes: 2, default_tab: 0,
        tabs: [1, 2, 3, 4, 5].map((k) => ({ ...TAB, session_id: `s${k}`, code: `p${k}`, t: 10 * k })) }],
    });
    mockApi(five);
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelectorAll(".screens-slide")).toHaveLength(3));
    const asked = () => new Set(vi.mocked(apiGet).mock.calls.map(([p]) => String(p))
      .filter((p) => p.includes("&w=1600&")).map((p) => /session_id=(s\d)/.exec(p)![1]));
    expect(asked()).toEqual(new Set(["s1", "s2", "s5"]));
    fireEvent.keyDown(document, { key: "ArrowRight" });
    await waitFor(() => expect(asked()).toEqual(new Set(["s1", "s2", "s3", "s5"])));
    expect(container.querySelectorAll(".screens-slide")).toHaveLength(3);
  });
});

// ── The owner's feedback round, 15 Oct 2026 (docs/design-screens.md S5) ────

// What the board keeps for a version (`screen key|session`): the store the server is fed from.
const stored = (version: string) => {
  const cut = version.lastIndexOf("|");
  // Undefined while the version is automatic; typed as present, as the tests read it once it is.
  return (arrangementFor("1", version.slice(0, cut), version.slice(cut + 1)) ?? undefined) as Arrangement;
};

const px = (v: string) => Number.parseFloat(v || "0") || 0;
/** The fixture's screengrab: where `.screens-shot` sits in the board, and the image's 1px border
 *  (its outer box is 2px wider and taller than its inner, client box) — so a test can see a
 *  measurement taken the wrong way. */
const GEO = { SX: 16, SY: 40, BORDER: 2 };
/**
 * A model of the board's layout for jsdom, which lays nothing out: the screengrab at (SX, SY),
 * W × H inside a 1px border; a right column a gutter beyond its outer edge; the band below a gutter
 * under it; the free layer absolute; the list below everything; the board itself at (0, -scroll)
 * in the viewport. Every card CARD_W × 100. Mirrors screens.css closely enough that a card's
 * rectangle follows its inline style, which is what the board writes.
 */
function geometry(start: { width?: number; height?: number } = {}) {
  let W = start.width ?? 1200;
  let H = start.height ?? 300;
  let scroll = 0;
  const rect = (left: number, top: number, width: number, height: number) =>
    ({ left, top: top - scroll, width, height, right: left + width, bottom: top - scroll + height, x: left, y: top - scroll, toJSON: () => ({}) }) as DOMRect;
  const offset = (el: HTMLElement, v: number) => (el.classList.contains("screens-shot") ? v : 0);
  const spies = [
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(() => W),
    vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(() => H),
    // The image's outer box is its inner box and a 1px border each side; every card is 100px tall.
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(function (this: HTMLElement) {
      return this.matches("img.is-current") ? H + GEO.BORDER : 100;
    }),
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(function (this: HTMLElement) {
      return this.matches("img.is-current") ? W + GEO.BORDER : 0;
    }),
    vi.spyOn(HTMLElement.prototype, "offsetLeft", "get").mockImplementation(function (this: HTMLElement) { return offset(this, GEO.SX); }),
    vi.spyOn(HTMLElement.prototype, "offsetTop", "get").mockImplementation(function (this: HTMLElement) { return offset(this, GEO.SY); }),
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      const el = this as HTMLElement;
      if (el.classList.contains("screens-board")) return rect(0, 0, 2000, 2000);
      if (el.matches("img.is-current")) return rect(GEO.SX, GEO.SY, W + GEO.BORDER, H + GEO.BORDER);
      if (!el.classList.contains("screens-card")) return rect(0, 0, 0, 0);
      const l = px(el.style.left), t = px(el.style.top);
      const right = GEO.SX + W + GEO.BORDER + 32, below = GEO.SY + H + GEO.BORDER + 32;
      if (el.closest(".screens-col-r")) return rect(right + l, GEO.SY + t, CARD_W, 100);
      if (el.closest(".screens-band-b")) return rect(GEO.SX + l, below + t, CARD_W, 100);
      if (el.closest(".screens-band-t")) return rect(GEO.SX + l, t, CARD_W, 100);
      if (el.closest(".screens-free")) return rect(l, t, CARD_W, 100);
      const list = [...(el.parentElement?.children ?? [])].indexOf(el);
      return rect(list * (CARD_W + 12), below + 200, CARD_W, 100);
    }),
  ];
  return {
    set(w: number, h = H) {
      W = w;
      H = h;
    },
    scrollTo(y: number) {
      scroll = y;
    },
    restore: () => spies.forEach((s) => s.mockRestore()),
  };
}

/** Drag a card by its top grip, past the threshold. */
function drag(card: HTMLElement, dx: number, dy: number) {
  const grip = card.querySelector<HTMLElement>(".screens-grip-top")!;
  fireEvent.pointerDown(grip, { button: 0, clientX: 100, clientY: 100 });
  act(() => {
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 100 + dx, clientY: 100 + dy }));
  });
  act(() => {
    window.dispatchEvent(new MouseEvent("pointerup", { clientX: 100 + dx, clientY: 100 + dy }));
  });
}

const box = (el: HTMLElement) => {
  const r = el.getBoundingClientRect();
  return { left: r.left, top: r.top };
};

/** Open the one-screen board, measured, with every card placed. */
async function measuredBoard() {
  mockApi(screensResponse());
  const r = render(<ScreensLens />);
  await waitFor(() => expect(cardOf(r.container, "q-p1-10").style.visibility).not.toBe("hidden"));
  return r.container;
}

describe("the arrangement: automatic, or the researcher's", () => {
  // The owner: "when I drag a card I'm saying leave all the other cards where they are and move
  // this one."
  it("the first drag switches the whole board to custom, freezing every other card where it was", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
      const linked = box(cardOf(c, "q-p1-10"));
      drag(cardOf(c, "q-p1-30"), 60, -150);
      expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
      // Every card the board showed has a spot; the one not dragged has not moved.
      expect(Object.keys(stored("url:/shoppingcart|s1")).sort()).toEqual(["q-p1-10", "q-p1-30"]);
      await waitFor(() => expect(box(cardOf(c, "q-p1-10"))).toEqual(linked));
      expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull();
    } finally {
      g.restore();
    }
  });

  it("in custom, nothing re-flows: a narrower window keeps each card on its edge, and a drag moves only its card", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      const listedSpot = stored("url:/shoppingcart|s1")["q-p1-30"];
      g.set(900); // narrower, still above the rows threshold: the card holds its intent, not a column
      resized();
      await waitFor(() => expect(box(cardOf(c, "q-p1-10")).left).toBe(GEO.SX + 900 + GEO.BORDER + 32));
      expect(cardOf(c, "q-p1-10").closest(".screens-col")).toBeNull();
      expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull();
      drag(cardOf(c, "q-p1-10"), -40, 20);
      expect(stored("url:/shoppingcart|s1")["q-p1-30"]).toEqual(listedSpot);
    } finally {
      g.restore();
    }
  });

  it("in custom, a resize scales the arrangement with the screengrab", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      const at = box(cardOf(c, "q-p1-10"));
      // Along the edge as a fraction of the screengrab's height (its laid-out box, border included).
      const along = (at.top - GEO.SY) / (300 + GEO.BORDER);
      g.set(900, 150);
      resized();
      await waitFor(() => expect(box(cardOf(c, "q-p1-10")).left).toBe(GEO.SX + 900 + GEO.BORDER + 32));
      expect(box(cardOf(c, "q-p1-10")).top).toBeCloseTo(GEO.SY + along * (150 + GEO.BORDER), 6);
    } finally {
      g.restore();
    }
  });

  it("Tidy is the way back: every card returns to automatic, with one glide, and it undoes", async () => {
    const g = geometry();
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = animate;
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-10"), -300, 0);
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull());
      animate.mockClear();
      fireEvent.click(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" }));
      expect(stored("url:/shoppingcart|s1")).toBeUndefined();
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-col-r")).not.toBeNull());
      expect(cardOf(c, "q-p1-30").closest(".screens-loose")).not.toBeNull();
      await waitFor(() => expect(animate).toHaveBeenCalled());
      expect(getUndoState().undoAction).toBe("tidy");
      await act(async () => {
        await undo();
      });
      expect(Object.keys(stored("url:/shoppingcart|s1"))).toContain("q-p1-10");
    } finally {
      g.restore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
    }
  });

  it("each drag is one undo, and undoing the drag that went custom returns the board to automatic", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      expect(getUndoState().undoAction).toBe("moveQuote");
      drag(cardOf(c, "q-p1-30"), 10, 10);
      await act(async () => {
        await undo(); // the second move
      });
      expect(stored("url:/shoppingcart|s1")).toBeDefined();
      await act(async () => {
        await undo(); // the move that switched the board
      });
      expect(stored("url:/shoppingcart|s1")).toBeUndefined();
      expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-col-r")).not.toBeNull());
      await act(async () => {
        await redo();
      });
      expect(stored("url:/shoppingcart|s1")).toBeDefined();
    } finally {
      g.restore();
    }
  });

  it("Return to automatic puts one card where Tidy would, and nothing else moves", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      const home = box(cardOf(c, "q-p1-10"));
      drag(cardOf(c, "q-p1-10"), -400, 40);
      const list = box(cardOf(c, "q-p1-30"));
      fireEvent.contextMenu(cardOf(c, "q-p1-10").querySelector(".quote-body")!);
      const items = await screen.findAllByRole("menuitem");
      expect(items.map((i) => i.textContent)).toEqual(["Return to automatic", "Tidy"]);
      fireEvent.click(items[0]);
      await waitFor(() => expect(box(cardOf(c, "q-p1-10"))).toEqual(home));
      expect(box(cardOf(c, "q-p1-30"))).toEqual(list);
      expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument(); // still custom
      expect(getUndoState().undoAction).toBe("moveQuote");
    } finally {
      g.restore();
    }
  });

  it("is never lost by a re-read that picks another still moment", async () => {
    const g = geometry();
    const { bumpRefreshKey } = await import("../../contexts/LastRunStore");
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      const moved = screensResponse({
        screens: [{ key: "url:/shoppingcart", name: "/shoppingcart", quotes: 2, tabs: [{ ...TAB, t: 13 }] }],
      });
      mockApi(moved);
      act(() => bumpRefreshKey());
      expect(await screen.findByAltText("p1’s screen: Shopping Bag, at 00:13")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
      expect(cardOf(c, "q-p1-30").closest(".screens-free")).not.toBeNull();
    } finally {
      g.restore();
    }
  });

  it("keeps each version's arrangement, through a change of version and back", async () => {
    seed("url:/basket", "s2", { "q-p2-20": { kind: "edge", edge: "R", along: 0.2, out: 32, z: 31 } });
    mockVersions();
    await openVersions();
    expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "ArrowLeft" });
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull(); // p1's is automatic
    fireEvent.keyDown(document, { key: "ArrowRight" });
    expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
  });

  it("returns a hidden card to its spot when it is shown again", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-10"), -300, 40);
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull());
      const spot = box(cardOf(c, "q-p1-10"));
      act(() => hideQuotes(["q-p1-10"]));
      await waitFor(() => expect(getQuotesSnapshot().hidden["q-p1-10"]).toBe(true));
      await waitFor(() => expect(c.querySelector('[data-dom="q-p1-10"]')).toBeNull());
      act(() => unhideQuotes(["q-p1-10"]));
      await waitFor(() => expect(cardOf(c, "q-p1-10")?.closest(".screens-free")).toBeTruthy());
      await waitFor(() => expect(box(cardOf(c, "q-p1-10"))).toEqual(spot));
    } finally {
      g.restore();
    }
  });

  it("abandons a drag when the board changes, putting back the arrangement it froze", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      const grip = cardOf(c, "q-p1-30").querySelector<HTMLElement>(".screens-grip-top")!;
      fireEvent.pointerDown(grip, { button: 0, clientX: 100, clientY: 100 });
      act(() => {
        window.dispatchEvent(new MouseEvent("pointermove", { clientX: 160, clientY: 40 }));
      });
      expect(stored("url:/shoppingcart|s1")).toBeDefined(); // frozen at the drag's start
      fireEvent.keyDown(document, { key: "ArrowDown" });
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
      expect(stored("url:/shoppingcart|s1")).toBeUndefined();
      act(() => {
        window.dispatchEvent(new MouseEvent("pointerup", { clientX: 160, clientY: 40 }));
      });
      expect(stored("url:/shoppingcart|s1")).toBeUndefined();
    } finally {
      g.restore();
    }
  });

  it("does not switch on a click: a grip pressed and released in place focuses the card and saves nothing", async () => {
    const g = geometry();
    try {
      mockApi(screensResponse());
      const { container } = render(
        <FocusProvider>
          <ScreensLens />
        </FocusProvider>,
      );
      await waitFor(() => expect(cardOf(container, "q-p1-10").style.visibility).not.toBe("hidden"));
      const grip = cardOf(container, "q-p1-10").querySelector<HTMLElement>(".screens-grip-top")!;
      fireEvent.pointerDown(grip, { button: 0, clientX: 100, clientY: 100 });
      act(() => {
        window.dispatchEvent(new MouseEvent("pointermove", { clientX: 101, clientY: 101 }));
        window.dispatchEvent(new MouseEvent("pointerup", { clientX: 101, clientY: 101 }));
      });
      expect(stored("url:/shoppingcart|s1")).toBeUndefined();
      await waitFor(() => expect(cardOf(container, "q-p1-10").querySelector(".quote-card.bn-focused")).not.toBeNull());
    } finally {
      g.restore();
    }
  });
});

describe("a live window resize", () => {
  async function resizeLive(reduce: boolean) {
    const g = geometry({ width: 1200 });
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = animate;
    const mm = window.matchMedia;
    window.matchMedia = ((q: string) => ({ matches: reduce && q.includes("reduce") })) as unknown as typeof window.matchMedia;
    try {
      const c = await measuredBoard();
      const board = () => c.querySelector<HTMLElement>(".screens-board")!;
      act(() => setLiveResize(true));
      g.set(800);
      resized();
      // Held: not recomposed (still one column, the card still in it), the whole board scaled.
      expect(board().className).toContain("mode-r");
      expect(cardOf(c, "q-p1-10").closest(".screens-col-r")).not.toBeNull();
      expect(c.querySelector<HTMLElement>(".screens-scale")!.style.transform).toBe(`scale(${800 / 1200})`);
      animate.mockClear();
      act(() => setLiveResize(false));
      await waitFor(() => expect(board().className).toContain("mode-rows"));
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-band-b")).not.toBeNull());
      expect(c.querySelector<HTMLElement>(".screens-scale")!.style.transform).toBe("");
      return animate;
    } finally {
      g.restore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
      window.matchMedia = mm;
    }
  }

  it("holds the board still, scaled as one, and settles once with a glide when it ends", async () => {
    const animate = await resizeLive(false);
    await waitFor(() => expect(animate).toHaveBeenCalled());
  });

  it("settles at once under reduced motion", async () => {
    const animate = await resizeLive(true);
    expect(animate).not.toHaveBeenCalled();
  });
});

describe("which version: one unit on the heading line", () => {
  it("opens on the version that links the most quotes, with its moment's timecode and its badge checked", async () => {
    mockVersions();
    const c = await openVersions();
    expect(await screen.findByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument();
    const unit = c.querySelector<HTMLElement>(".section-heading .screens-versions")!;
    expect(unit.querySelector("a.timecode")).toHaveTextContent("00:40");
    const group = screen.getByRole("radiogroup", { name: "Versions of this screen" });
    const radios = [...group.querySelectorAll<HTMLElement>('[role="radio"]')];
    // A radio says its own position; its name is whose screen.
    expect(radios.map((r) => r.getAttribute("aria-label"))).toEqual(["p1’s screen", "p2’s screen"]);
    expect(radios.map((r) => r.getAttribute("aria-checked"))).toEqual(["false", "true"]);
    expect(radios.map((r) => r.tabIndex)).toEqual([-1, 0]); // one tab stop
    expect(radios[1].className).toContain("bn-person-badge-here");
    // Nothing for choosing a version sits on the screengrab.
    expect(c.querySelector(".screens-shot button, .screens-dot, .screens-chev, .screens-caption")).toBeNull();
  });

  it("moves the checked badge with ←/→ inside the group, focus going with it", async () => {
    mockVersions();
    await openVersions();
    const checked = () => screen.getByRole("radio", { checked: true });
    checked().focus();
    vi.mocked(announce).mockClear();
    fireEvent.keyDown(checked(), { key: "ArrowLeft" });
    expect(await screen.findByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    expect(checked()).toHaveAccessibleName("p1’s screen");
    expect(document.activeElement).toBe(checked());
    expect(announce).not.toHaveBeenCalled(); // the focused badge says it
  });

  it("steps with ‹ › and the arrow keys anywhere, and says which version", async () => {
    mockVersions();
    await openVersions();
    fireEvent.click(screen.getByRole("button", { name: "Next version" }));
    expect(await screen.findByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    vi.mocked(announce).mockClear();
    fireEvent.keyDown(document, { key: "ArrowRight" });
    expect(await screen.findByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument();
    expect(announce).toHaveBeenLastCalledWith("p2’s screen at 00:40 · 2 of 2");
  });

  it("collapses past five versions to one badge that opens a menu of them", async () => {
    const many = screensResponse({
      screens: [{ key: "url:/x", name: "/x", quotes: 2, default_tab: 2,
        tabs: [1, 2, 3, 4, 5, 6, 7].map((k) => ({ ...TAB, session_id: `s${k}`, code: `p${k}`, t: 10 * k })) }],
    });
    mockApi(many);
    await opened();
    expect(screen.queryByRole("radiogroup")).toBeNull();
    const pick = screen.getByRole("button", { name: "p3’s screen, 3 of 7" });
    expect(pick).toHaveTextContent("3 of 7");
    fireEvent.click(pick);
    const items = await screen.findAllByRole("menuitemradio");
    expect(items).toHaveLength(7);
    // It opens on the checked version, and Home/End reach the ends.
    expect(items[2]).toHaveAttribute("aria-checked", "true");
    expect(document.activeElement).toBe(items[2]);
    fireEvent.keyDown(items[2], { key: "End" });
    expect(document.activeElement).toBe(items[6]);
    fireEvent.keyDown(items[6], { key: "Home" });
    expect(document.activeElement).toBe(items[0]);
    fireEvent.click(items[5]);
    expect(await screen.findByAltText("p6’s screen: Shopping Bag, at 01:00")).toBeInTheDocument();
  });

  it("shows the moment and the one badge when there is one version, with nothing to step", async () => {
    mockApi(screensResponse());
    const c = await (async () => {
      const r = render(<ScreensLens />);
      await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
      return r.container;
    })();
    expect(c.querySelector(".screens-versions a.timecode")).toHaveTextContent("00:12");
    expect(c.querySelector(".screens-versions .bn-person-badge-here")).toHaveTextContent("p1");
    expect(screen.queryByRole("button", { name: "Next version" })).toBeNull();
  });
});

describe("cards", () => {
  it("carry no per-person sequence badge: the timecode already says the order", async () => {
    mockVersions();
    const c = await openVersions();
    expect(c.querySelector(".screens-seq")).toBeNull();
  });

  it("are one width everywhere, the margins and the list alike", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      expect(cardOf(c, "q-p1-10").style.width).toBe(`${CARD_W}px`);
      expect(c.querySelector<HTMLElement>(".screens-lens")!.style.getPropertyValue("--screens-card-w")).toBe(`${CARD_W}px`);
    } finally {
      g.restore();
    }
  });

  // The owner, 15 Oct 2026: "interesting but new… hide here for the moment". Only here.
  it("leave out the [When asked…] line on this lens", async () => {
    const asked = { ...QUOTES, unjoined: QUOTES.unjoined!.map((q) => ({ ...q, researcher_context: "When asked about price" })) };
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens/arrangements") return Promise.resolve({ versions: serverArrangements });
      if (path === "/screens") return Promise.resolve(screensResponse());
      if (path === "/quotes") return Promise.resolve(asked);
      return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
    }) as typeof apiGet);
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote")).not.toBeNull());
    expect(container.textContent).not.toContain("When asked about price");
  });
});

describe("the shared keys", () => {
  function Probe({ out }: { out: { current: ReturnType<typeof useFocus> | null } }) {
    const f = useFocus();
    useEffect(() => {
      out.current = f;
    });
    return null;
  }

  // J/K, ⇧J/K, ⇧-click and ⌘A are the report's handler, as on Quotes, over this order.
  it("registers the board's reading order: the margins as they sit, then the list in time order", async () => {
    const ctx: { current: ReturnType<typeof useFocus> | null } = { current: null };
    mockVersions();
    await openVersions(
      <FocusProvider>
        <Probe out={ctx} />
        <ScreensLens />
      </FocusProvider>,
    );
    // Unmeasured, the margins go in their lines' time order; the unlinked card comes last.
    expect(ctx.current!.getVisibleQuoteIds()).toEqual(["q-p2-20", "q-p1-30", "q-p2-60", "q-p1-10"]);
  });

  it("orders the margins by where they sit once measured", async () => {
    const g = geometry();
    const ctx: { current: ReturnType<typeof useFocus> | null } = { current: null };
    try {
      mockApi(screensResponse());
      const { container } = render(
        <FocusProvider>
          <Probe out={ctx} />
          <ScreensLens />
        </FocusProvider>,
      );
      await waitFor(() => expect(cardOf(container, "q-p1-10").style.visibility).not.toBe("hidden"));
      expect(ctx.current!.getVisibleQuoteIds()).toEqual(["q-p1-10", "q-p1-30"]);
    } finally {
      g.restore();
    }
  });

  it("leaves J and K to the shared handler, and a focused card's line lights", async () => {
    const ctx: { current: ReturnType<typeof useFocus> | null } = { current: null };
    mockVersions();
    const c = await openVersions(
      <FocusProvider>
        <Probe out={ctx} />
        <ScreensLens />
      </FocusProvider>,
    );
    const j = new KeyboardEvent("keydown", { key: "j", bubbles: true, cancelable: true });
    act(() => {
      document.dispatchEvent(j);
    });
    expect(j.defaultPrevented).toBe(false);
    act(() => ctx.current!.setFocus("q-p1-30", { scroll: false }));
    await waitFor(() => expect(cardOf(c, "q-p1-30").querySelector(".quote-card.bn-focused")).not.toBeNull());
    expect(c.querySelector(".screens-hl.on")).not.toBeNull();
  });
});

describe("the navigator", () => {
  it("is a keyboard-operable separator that remembers its width, as Discussion's guide is", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    const split = await screen.findByRole("separator", { name: "Resize the list of screens" });
    const lens = container.querySelector<HTMLElement>(".screens-lens")!;
    fireEvent.keyDown(split, { key: "Home" });
    expect(split).toHaveAttribute("aria-valuenow", "200");
    fireEvent.keyDown(split, { key: "ArrowRight" });
    expect(split).toHaveAttribute("aria-valuenow", "210");
    expect(lens.style.getPropertyValue("--screens-nav-w")).toBe("210px");
    expect(localStorage.getItem("bn-screens-nav-width")).toBe("210");
    fireEvent.keyDown(split, { key: "End" });
    expect(split).toHaveAttribute("aria-valuenow", "480");
  });

  it("counts a screen's quotes as its board does, though the count is not shown for now", () => {
    const byId = new Map([["a", {} as QuoteResponse], ["b", {} as QuoteResponse]]);
    const s = { key: "k", name: "/k", quotes: 0, tabs: [{ ...TAB, pins: [{ ...TAB.pins[0], dom_id: "a" }], loose: ["a", "b", "gone"] }] };
    expect(quotesOnScreen(s as never, byId, {})).toBe(2);
    expect(quotesOnScreen(s as never, byId, { b: true })).toBe(1);
  });
});

describe("the Mac's View menu, by name", () => {
  const menu = (action: string) =>
    act(() => {
      window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action } }));
    });

  it("changes version and screen", async () => {
    mockVersions();
    await openVersions();
    menu("nextScreenshot");
    expect(await screen.findByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    menu("previousScreenshot");
    expect(await screen.findByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument();
    menu("nextScreen");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
    menu("previousScreen");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Basket");
  });
});

// ── Review fixes, 15 Oct 2026 (night) ────────────────────────────────────

const intents = (version: string) => stored(version) as Record<string, { kind: string; edge?: string; along?: number; out?: number }>;

/** measuredBoard, under the FocusProvider, for tests that read focus and selection. */
async function focusedBoard() {
  mockApi(screensResponse());
  const r = render(
    <FocusProvider>
      <ScreensLens />
    </FocusProvider>,
  );
  await waitFor(() => expect(cardOf(r.container, "q-p1-10").style.visibility).not.toBe("hidden"));
  return r.container;
}

describe("which card is in front (the owner, 15 Oct 2026)", () => {
  it("a press anywhere on a card brings it to the front, its star included", async () => {
    const g = geometry();
    onTestFinished(() => g.restore());
    const c = await measuredBoard();
    const a = cardOf(c, "q-p1-10");
    const b = cardOf(c, "q-p1-30");
    fireEvent.pointerDown(a.querySelector(".quote-body") ?? a, { button: 0 });
    expect(a.className).toContain("is-front");
    fireEvent.pointerDown(b.querySelector(".star-btn")!, { button: 0 });
    expect(b.className).toContain("is-front");
    expect(a.className).not.toContain("is-front");
  });

  it("a click on the drag edge that never becomes a drag focuses and selects the card, as a click on its body does", async () => {
    const g = geometry();
    onTestFinished(() => g.restore());
    const c = await focusedBoard();
    const card = cardOf(c, "q-p1-30");
    const grip = card.querySelector<HTMLElement>(".screens-grip-top")!;
    fireEvent.pointerDown(grip, { button: 0, clientX: 100, clientY: 100 });
    act(() => {
      window.dispatchEvent(new MouseEvent("pointerup", { clientX: 100, clientY: 100 }));
    });
    await waitFor(() => expect(card.querySelector(".quote-card")!.className).toContain("bn-selected"));
    expect(card.querySelector(".quote-card")!.className).toContain("bn-focused");
  });

  it("a card just put down is in front and focused", async () => {
    const g = geometry();
    try {
      const c = await focusedBoard();
      fireEvent.pointerDown(cardOf(c, "q-p1-10").querySelector(".quote-body") ?? cardOf(c, "q-p1-10"), { button: 0 });
      drag(cardOf(c, "q-p1-30"), 40, 40);
      await waitFor(() => expect(cardOf(c, "q-p1-30").className).toContain("is-front"));
      expect(cardOf(c, "q-p1-30").querySelector(".quote-card")!.className).toContain("bn-focused");
    } finally {
      g.restore();
    }
  });
});

describe("the arrangement, measured one way", () => {
  // Item 1: the freeze and the placement must measure the screengrab the same way, or the first
  // drag nudges every right- and bottom-edge card by the image's border.
  it("leaves a right-edge card exactly where it was through the first drag, with a bordered, offset screengrab", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      const before = box(cardOf(c, "q-p1-10"));
      expect(before.left).toBe(GEO.SX + 1200 + GEO.BORDER + COLUMN_GUTTER);
      drag(cardOf(c, "q-p1-30"), 60, -150);
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull());
      expect(box(cardOf(c, "q-p1-10"))).toEqual(before);
    } finally {
      g.restore();
    }
  });

  // Item 3: a page that scrolls mid-drag keeps the card under the pointer.
  it("keeps a dragged card under the pointer when the page scrolls during the drag", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      const card = cardOf(c, "q-p1-10");
      const start = box(card);
      fireEvent.pointerDown(card.querySelector(".screens-grip-top")!, { button: 0, clientX: start.left + 10, clientY: start.top + 4 });
      act(() => {
        window.dispatchEvent(new MouseEvent("pointermove", { clientX: start.left + 10, clientY: start.top + 14 }));
      });
      g.scrollTo(50); // the page scrolls 50px; the pointer stays where it is on the screen
      act(() => {
        window.dispatchEvent(new MouseEvent("pointerup", { clientX: start.left + 10, clientY: start.top + 14 }));
      });
      const spot = intents("url:/shoppingcart|s1")["q-p1-10"];
      // 10px down the screen plus the 50px the board moved up: 60px down the board, still beside it.
      expect(spot.edge).toBe("R");
      expect(spot.along! * (300 + GEO.BORDER)).toBeCloseTo(start.top + 60 - GEO.SY, 6);
    } finally {
      g.restore();
    }
  });
});

describe("a board that mounts during a live resize", () => {
  // Item 4.
  it("lays itself out, and does not glide its cards in from the origin when the resize ends", async () => {
    const g = geometry();
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = animate;
    try {
      setLiveResize(true);
      const c = await measuredBoard(); // placed though the resize is live
      act(() => setLiveResize(false));
      await waitFor(() => expect(cardOf(c, "q-p1-10").style.visibility).not.toBe("hidden"));
      expect(animate).not.toHaveBeenCalled();
    } finally {
      g.restore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
    }
  });
});

describe("a change of version", () => {
  // Item 6: a change of version cross-fades; the cards do not glide from one version's spots to
  // the other's.
  it("does not glide the cards", async () => {
    const g = geometry();
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = animate;
    try {
      seed("url:/basket", "s2", { "q-p1-30": { kind: "edge", edge: "R", along: 0.5, out: 32, z: 31 } });
      mockVersions();
      const c = await openVersions();
      await waitFor(() => expect(cardOf(c, "q-p1-30").closest(".screens-free")).not.toBeNull());
      animate.mockClear();
      fireEvent.keyDown(document, { key: "ArrowLeft" }); // p1's version: automatic
      expect(await screen.findByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-col-r")).not.toBeNull());
      expect(animate).not.toHaveBeenCalled();
    } finally {
      g.restore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
    }
  });

  // Item 5: a drag abandoned by the change of version must not leave a stale "quiet" that swallows
  // the next Tidy glide on the version now showing.
  it("leaves the next Tidy's glide alone after a drag it abandoned", async () => {
    const g = geometry();
    const animate = vi.fn();
    (HTMLElement.prototype as unknown as Record<string, unknown>).animate = animate;
    try {
      seed("url:/basket", "s1", { "q-p1-10": { kind: "edge", edge: "R", along: 0.9, out: 32, z: 31 } });
      mockVersions();
      const c = await openVersions(); // p2's version, automatic
      const grip = cardOf(c, "q-p1-30").querySelector<HTMLElement>(".screens-grip-top")!;
      fireEvent.pointerDown(grip, { button: 0, clientX: 100, clientY: 100 });
      act(() => {
        window.dispatchEvent(new MouseEvent("pointermove", { clientX: 160, clientY: 40 }));
      });
      fireEvent.keyDown(document, { key: "ArrowLeft" }); // to p1's version, which is custom
      expect(await screen.findByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull());
      animate.mockClear();
      fireEvent.click(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" }));
      await waitFor(() => expect(animate).toHaveBeenCalled());
    } finally {
      g.restore();
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).animate;
    }
  });
});

describe("a version migrated from the 14 Oct store", () => {
  // Item 7: its first view freezes the rest of the board where automatic puts it, so its linked
  // cards do not drop into the list.
  it("freezes its linked cards where automatic puts them, not into the list", async () => {
    localStorage.setItem("bristlenose-screens-placements-1",
      JSON.stringify({ "s1@12/q-p1-30": { kind: "edge", side: "R", frac: 0.9, z: 31 } }));
    const g = geometry();
    try {
      const c = await measuredBoard();
      await waitFor(() => expect(Object.keys(intents("url:/shoppingcart|s1") ?? {}).sort()).toEqual(["q-p1-10", "q-p1-30"]));
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull());
      expect(cardOf(c, "q-p1-10").closest(".screens-loose")).toBeNull();
      expect(box(cardOf(c, "q-p1-10")).left).toBe(GEO.SX + 1200 + GEO.BORDER + COLUMN_GUTTER); // its automatic spot
    } finally {
      g.restore();
    }
  });
});

describe("an undo out of sight", () => {
  // Item 8: undoing a move on a screen not showing shows it first.
  it("shows the screen and version the undone move belongs to", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      fireEvent.keyDown(document, { key: "ArrowDown" });
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
      await act(async () => {
        await undo();
      });
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag");
      expect(stored("url:/shoppingcart|s1")).toBeUndefined();
    } finally {
      g.restore();
    }
  });
});

describe("the version steppers by keyboard", () => {
  // Item 10: focus stays on ‹ › so they work again and again.
  it("keep focus on the step button: Space works twice", async () => {
    const many = screensResponse({
      screens: [{ key: "url:/x", name: "/x", quotes: 2, default_tab: 0,
        tabs: [1, 2, 3].map((k) => ({ ...TAB, session_id: `s${k}`, code: `p${k}`, t: 10 * k })) }],
    });
    mockApi(many);
    await opened();
    const user = userEvent.setup();
    const next = screen.getByRole("button", { name: "Next version" });
    next.focus();
    await user.keyboard(" ");
    expect(screen.getByRole("radio", { checked: true })).toHaveAccessibleName("p2’s screen");
    expect(document.activeElement).toBe(next);
    await user.keyboard(" ");
    expect(screen.getByRole("radio", { checked: true })).toHaveAccessibleName("p3’s screen");
    expect(document.activeElement).toBe(next);
  });

  // Item 11: where focus does not move to a new element, the change is announced.
  it("announce the version they show, since focus stays put", async () => {
    mockVersions();
    await openVersions();
    const prev = screen.getByRole("button", { name: "Previous version" });
    prev.focus();
    vi.mocked(announce).mockClear();
    fireEvent.click(prev);
    expect(announce).toHaveBeenLastCalledWith("p1’s screen");
  });
});

describe("focus through a re-parenting", () => {
  // Item 12: a card holding keyboard focus that moves to another parent gets focus back.
  it("puts focus back into a card that moved from a column to a row", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      const star = cardOf(c, "q-p1-10").querySelector<HTMLElement>(".star-btn")!;
      star.focus();
      expect(cardOf(c, "q-p1-10").closest(".screens-col-r")).not.toBeNull();
      g.set(600); // rows: the card moves to the band below
      resized();
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-band-b")).not.toBeNull());
      await waitFor(() => expect(document.activeElement).toBe(cardOf(c, "q-p1-10").querySelector(".star-btn")));
    } finally {
      g.restore();
    }
  });
});

describe("a custom board at a narrow width", () => {
  // Item 14 (1.4.10): below the rows threshold the board shows as the automatic rows, and the
  // researcher's arrangement comes back once it is wide enough.
  it("shows as rows below the threshold, keeping the arrangement for when it is wide again", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      const kept = stored("url:/shoppingcart|s1");
      g.set(600);
      resized();
      await waitFor(() => expect(c.querySelector(".screens-board")!.className).toContain("cols-none"));
      expect(cardOf(c, "q-p1-10").closest(".screens-band")).not.toBeNull();
      expect(c.querySelector(".screens-free .screens-card")).toBeNull();
      expect(stored("url:/shoppingcart|s1")).toEqual(kept);
      expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
      g.set(1200);
      resized();
      await waitFor(() => expect(cardOf(c, "q-p1-10").closest(".screens-free")).not.toBeNull());
    } finally {
      g.restore();
    }
  });
});

describe("moving a card from the keyboard", () => {
  // Item 15 (2.1.1): ⌥ + an arrow moves the focused card, as a drag does.
  function Probe({ out }: { out: { current: ReturnType<typeof useFocus> | null } }) {
    const f = useFocus();
    useEffect(() => {
      out.current = f;
    });
    return null;
  }
  it("moves the focused card one step along its edge, then to the other side, each an undoable Move Quote", async () => {
    const g = geometry();
    const ctx: { current: ReturnType<typeof useFocus> | null } = { current: null };
    try {
      mockApi(screensResponse());
      const { container } = render(
        <FocusProvider>
          <Probe out={ctx} />
          <ScreensLens />
        </FocusProvider>,
      );
      await waitFor(() => expect(cardOf(container, "q-p1-10").style.visibility).not.toBe("hidden"));
      act(() => ctx.current!.setFocus("q-p1-10", { scroll: false }));
      const before = box(cardOf(container, "q-p1-10"));
      vi.mocked(announce).mockClear();
      const press = (key: string) => {
        const e = new KeyboardEvent("keydown", { key, altKey: true, bubbles: true, cancelable: true });
        act(() => {
          document.dispatchEvent(e);
        });
        return e;
      };
      expect(press("ArrowDown").defaultPrevented).toBe(true);
      // The board went custom; the card moved one step down its edge, and nothing else.
      await waitFor(() => expect(box(cardOf(container, "q-p1-10")).top).toBeCloseTo(before.top + MOVE_STEP, 6));
      expect(box(cardOf(container, "q-p1-10")).left).toBe(before.left);
      expect(announce).toHaveBeenLastCalledWith("Quote moved");
      expect(getUndoState().undoAction).toBe("moveQuote");
      press("ArrowLeft");
      expect(intents("url:/shoppingcart|s1")["q-p1-10"].edge).toBe("L");
      await act(async () => {
        await undo();
      });
      expect(intents("url:/shoppingcart|s1")["q-p1-10"].edge).toBe("R");
      await act(async () => {
        await undo();
      });
      expect(stored("url:/shoppingcart|s1")).toBeUndefined(); // the first move's undo: automatic again
    } finally {
      g.restore();
    }
  });
});

describe("the navigator's separator", () => {
  it("says its width in pixels", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    const split = await screen.findByRole("separator", { name: "Resize the list of screens" });
    fireEvent.keyDown(split, { key: "Home" });
    expect(split).toHaveAttribute("aria-valuetext", "200 pixels");
  });

  it("gives focus to the board's title when [ hides the navigator under it", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    const split = await screen.findByRole("separator", { name: "Resize the list of screens" });
    split.focus();
    act(() => toggleScreensNav());
    expect(screen.queryByRole("separator")).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1 }));
  });
});

describe("leaders over the screengrab follow its paper (R3, 15 Oct 2026)", () => {
  const DEFAULT = { light: [0, 122, 255] as [number, number, number], dark: [10, 132, 255] as [number, number, number] };
  const boardStill = (t: number) => `/screens/still?session_id=s1&t=${t}&w=1600&crop=0.0000,0.1000,0.9000,1.0000`;

  it("a dark-mode site: the line over it takes the dark accent and a halo in the site's own paper", async () => {
    paperStub.accents = DEFAULT;
    papers.set(boardStill(12), [18, 18, 18]);
    const g = geometry();
    try {
      const c = await measuredBoard();
      const shot = await waitFor(() => {
        const el = c.querySelector<SVGGElement>("svg.screens-leaders g.lead-shot");
        expect(el).not.toBeNull();
        return el!;
      });
      expect(shot.style.colorScheme).toBe("dark");
      expect(shot.style.getPropertyValue("--screens-paper")).toBe("rgb(18, 18, 18)");
      // Clipped to a clip path that exists, and the halo is drawn under the line, never faded.
      const clip = shot.getAttribute("clip-path")!.match(/url\(#(.+)\)/)![1];
      expect(c.querySelector(`clipPath[id="${clip}"]`)).not.toBeNull();
      const casing = shot.querySelector("g.lead-casing")!;
      expect(casing.getAttribute("opacity")).toBeNull();
      expect(casing.querySelectorAll("path").length).toBe(c.querySelectorAll("svg.screens-leaders > path").length);
      expect(shot.querySelectorAll(":scope > circle").length).toBeGreaterThan(0);
      // The target box takes the same scheme and paper; the slides around it do not.
      const hl = c.querySelector<HTMLElement>(".screens-hl")!;
      expect(hl.style.colorScheme).toBe("dark");
      expect(c.querySelector<HTMLElement>(".screens-slides")!.style.colorScheme).toBe("");
    } finally {
      g.restore();
    }
  });

  it("no paper yet: no halo group, and the line and its end dot are today's", async () => {
    paperStub.accents = DEFAULT;
    const g = geometry();
    try {
      const c = await measuredBoard();
      await waitFor(() => expect(c.querySelector("svg.screens-leaders > circle")).not.toBeNull());
      expect(c.querySelector("g.lead-shot")).toBeNull();
    } finally {
      g.restore();
    }
  });

  it("samples a still's paper when it arrives, and caches it with the still", async () => {
    paperStub.sample = [255, 255, 255];
    mockApi(screensResponse({ screens: [{ key: "url:/fresh", name: "/fresh", quotes: 1, tabs: [{ ...TAB, t: 77 }] }] }));
    render(<ScreensLens />);
    await waitFor(() => expect(document.querySelector("img.screens-slide.is-current")).not.toBeNull());
    expect(papers.get(boardStill(77))).toEqual([255, 255, 255]);
  });
});

describe("arrangements come from the project's database (15 Oct 2026)", () => {
  it("reads nothing and sends nothing up while the lens is off, so an explicit off holds", async () => {
    localStorage.setItem("bristlenose-screens-arrangements-1", JSON.stringify({
      "url:/shoppingcart|s1": { "q-p1-10": { kind: "edge", edge: "L", along: 0.3, out: 32, z: 31 } },
    }));
    mockApi(screensResponse({ enabled: false, screens: [] }));
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByText(/Screens are off/)).toBeInTheDocument());
    await act(async () => {});
    expect(apiGet).not.toHaveBeenCalledWith("/screens/arrangements");
    expect(vi.mocked(sendPut)).not.toHaveBeenCalled();
  });

  it("keeps the board waiting when the read fails, writes nothing, and shows it once a look succeeds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.spyOn(console, "error").mockImplementation(() => {});
    // A 14 Oct placement the board would migrate (and write) the moment it drew.
    localStorage.setItem("bristlenose-screens-placements-1", JSON.stringify({
      "s1@12/q-p1-10": { kind: "edge", side: "R", frac: 0.4, z: 31 },
    }));
    seed("url:/shoppingcart", "s1", { "q-p1-30": { kind: "edge", edge: "L", along: 0.3, out: 32, z: 31 } });
    let fail = true;
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens") return Promise.resolve(screensResponse());
      if (path === "/quotes") return Promise.resolve(QUOTES);
      if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
      if (path === "/screens/arrangements") {
        return fail ? Promise.reject(new Error("401")) : Promise.resolve({ versions: serverArrangements });
      }
      return Promise.reject(new Error(path));
    }) as typeof apiGet);
    const { container } = render(<ScreensLens />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(container.querySelector(".screens-stage")).toBeNull();
    expect(vi.mocked(sendPut)).not.toHaveBeenCalled();
    fail = false;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
    // The server's arrangement stands: the 14 Oct entry did not replace it.
    expect(vi.mocked(sendPut)).not.toHaveBeenCalled();
    expect(stored("url:/shoppingcart|s1")).toEqual({ "q-p1-30": { kind: "edge", edge: "L", along: 0.3, out: 32, z: 31 } });
  });

  it("draws no board until they are read, so a custom board never shows automatic first", async () => {
    seed("url:/shoppingcart", "s1", { "q-p1-10": { kind: "edge", edge: "L", along: 0.3, out: 32, z: 31 } });
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    vi.mocked(apiGet).mockImplementation(((path: string) => {
      if (path === "/screens") return Promise.resolve(screensResponse());
      if (path === "/quotes") return Promise.resolve(QUOTES);
      if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
      if (path === "/screens/arrangements") return gate.then(() => ({ versions: serverArrangements }));
      return Promise.reject(new Error(path));
    }) as typeof apiGet);
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(apiGet).toHaveBeenCalledWith("/screens/arrangements"));
    await act(async () => {});
    expect(container.querySelector(".screens-stage")).toBeNull();
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
    await act(async () => release());
    expect(await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
  });

  it("reads them again when a run finishes, so another window's change shows", async () => {
    mockApi(screensResponse());
    render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
    seed("url:/shoppingcart", "s1", { "q-p1-10": { kind: "edge", edge: "L", along: 0.3, out: 32, z: 31 } });
    const { bumpRefreshKey } = await import("../../contexts/LastRunStore");
    await act(async () => bumpRefreshKey());
    expect(await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
  });

  it("sends a drag to the server, for that version alone", async () => {
    const g = geometry();
    try {
      const c = await measuredBoard();
      drag(cardOf(c, "q-p1-30"), 60, -150);
      await waitFor(() => expect(vi.mocked(sendPut)).toHaveBeenCalled());
      const calls = vi.mocked(sendPut).mock.calls;
      const [path, body] = calls[calls.length - 1];
      expect(path).toBe("/screens/arrangement");
      expect(body).toMatchObject({ screen_key: "url:/shoppingcart", session_id: "s1" });
      expect(Object.keys((body as { cards: object }).cards).sort()).toEqual(["q-p1-10", "q-p1-30"]);
    } finally {
      g.restore();
    }
  });
});

