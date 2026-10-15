import { useEffect, useRef } from "react";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { getQuotesSnapshot, resetStore } from "../../contexts/QuotesContext";
import { resetSidebarStore, toggleTagGroupHidden, useSidebarStore } from "../../contexts/SidebarStore";
import type { QuoteResponse, QuotesListResponse } from "../../utils/types";
import { FocusProvider, useFocus } from "../../contexts/FocusContext";
import { resetArrangementMemory } from "./layout";
import { resetScreensNav, screensNavState, toggleScreensNav } from "./navPanel";

vi.mock("../../utils/announce", () => ({ announce: vi.fn(), setAnnounceElement: vi.fn() }));

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
}));

import { announce } from "../../utils/announce";
import { apiGet, getCodebook } from "../../utils/api";
import { failedText, NAV_W, ScreensLens, SCREENS_POLL_LIMIT, shouldPoll, unavailableText, type ScreensResponse } from "./ScreensLens";

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

function mockApi(screens: unknown) {
  vi.mocked(apiGet).mockImplementation(((path: string) => {
    if (path === "/screens") return Promise.resolve(screens);
    if (path === "/quotes") return Promise.resolve(QUOTES);
    if (path.startsWith("/screens/still")) return Promise.resolve({ src: "data:image/jpeg;base64,AA==" });
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
  vi.mocked(getCodebook).mockResolvedValue({ all_tag_names: [], groups: [], ungrouped: [] } as never);
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
  it("lists every screen by its page title and address, most said-about first", async () => {
    mockApi(screensResponse());
    await opened();
    const nav = screen.getByRole("navigation", { name: "Screens" });
    expect(nav).toHaveTextContent("2 screens · 1 participant");
    expect(nav).toHaveTextContent("/shoppingcart");
    expect(nav).toHaveTextContent("Delivery or collect");
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

  it("counts in the navigator only what the board shows: hidden quotes are not counted", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-loose blockquote")).not.toBeNull());
    const count = () => container.querySelector(".screens-nav .screens-count")!.textContent;
    expect(count()).toBe("2");
    act(() => {
      fireEvent.click(container.querySelector(".screens-loose blockquote .hide-btn")!);
    });
    await waitFor(() => expect(getQuotesSnapshot().hidden["q-p1-30"]).toBe(true));
    await waitFor(() => expect(count()).toBe("1"));
  });

  it("keeps showing the board when one look fails, and looks again", async () => {
    vi.useFakeTimers();
    vi.spyOn(console, "error").mockImplementation(() => {});
    let n = 0;
    vi.mocked(apiGet).mockImplementation(((path: string) => {
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

describe("rearranging the board", () => {
  const key = "bristlenose-screens-placements-1";
  const pointer = (type: string, x: number, y: number) =>
    act(() => {
      window.dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y }));
    });

  async function grip() {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-col .screens-grip-top")).not.toBeNull());
    return container.querySelector<HTMLElement>(".screens-col .screens-grip-top")!;
  }

  it("does not move a card on a click: a grip pressed and released in place saves nothing", async () => {
    const g = await grip();
    fireEvent.pointerDown(g, { button: 0, clientX: 100, clientY: 100 });
    pointer("pointermove", 101, 101);
    pointer("pointerup", 101, 101);
    expect(localStorage.getItem(key)).toBeNull();
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
  });

  it("moves a card once the pointer has travelled, and remembers where", async () => {
    const g = await grip();
    fireEvent.pointerDown(g, { button: 0, clientX: 100, clientY: 100 });
    pointer("pointermove", 140, 160);
    pointer("pointerup", 140, 160);
    expect(localStorage.getItem(key)).toContain("s1@12/q-p1-10");
    expect(screen.getByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
  });

  it("drops a drag in progress when the board changes, rather than saving it to the screen left", async () => {
    const g = await grip();
    fireEvent.pointerDown(g, { button: 0, clientX: 100, clientY: 100 });
    pointer("pointermove", 140, 160);
    fireEvent.keyDown(document, { key: "ArrowDown" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
    pointer("pointerup", 140, 160);
    expect(localStorage.getItem(key) ?? "").not.toContain("s1@12/");
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

  it("marks a placed card, returns every card to automatic, and is undone by the report's undo", async () => {
    const { undo, getUndoState } = await import("../../contexts/UndoStore");
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    const control = await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
    expect(container.querySelector('.screens-card[data-dom="q-p1-10"]')!.className).toContain("is-placed");
    fireEvent.click(control);
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
    expect(container.querySelector('.screens-card[data-dom="q-p1-10"]')!.className).not.toContain("is-placed");
    expect(localStorage.getItem(key)).not.toContain("q-p1-10");
    expect(getUndoState().undoAction).toBe("tidy");
    await act(async () => {
      await undo();
    });
    expect(await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeInTheDocument();
    expect(localStorage.getItem(key)).toContain("q-p1-10");
  });

  it("offers Return to automatic for a placed card, and Tidy, on right-click", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await screen.findByRole("button", { name: "Arrangement: Custom. Tidy" });
    const card = container.querySelector<HTMLElement>('.screens-card[data-dom="q-p1-10"]')!;
    fireEvent.contextMenu(card.querySelector(".quote-body") ?? card);
    const items = await screen.findAllByRole("menuitem");
    expect(items.map((i) => i.textContent)).toEqual(["Return to automatic", "Tidy"]);
    fireEvent.click(items[0]);
    expect(screen.queryByRole("menu")).toBeNull();
    expect(container.querySelector('.screens-card[data-dom="q-p1-10"]')!.className).not.toContain("is-placed");
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
  });

  // Tidy removes its own button; focus used to fall to the page (accessibility review, 14 Oct 2026).
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

describe("bringing a card forward", () => {
  // Click, never hover (the owner, 14 Oct 2026): a lifted card unclamps and grows, the column
  // re-stacks, and under hover a different card was then under the pointer — flicker.
  it("brings a card forward on click, not on hover, and puts it back on a press elsewhere", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-col .screens-card")).not.toBeNull());
    const card = container.querySelector<HTMLElement>(".screens-col .screens-card")!;
    fireEvent.mouseEnter(card);
    fireEvent.mouseOver(card);
    expect(card.className).not.toContain("is-lifted");
    fireEvent.pointerDown(card.querySelector(".quote-body") ?? card);
    expect(card.className).toContain("is-lifted");
    fireEvent.mouseLeave(card);
    expect(card.className).toContain("is-lifted");
    fireEvent.pointerDown(card); // a press on the card itself keeps it forward
    expect(card.className).toContain("is-lifted");
    fireEvent.pointerDown(document.body);
    expect(card.className).not.toContain("is-lifted");
  });

  it("brings a card forward from a press on its grip that is not a drag", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-col .screens-card")).not.toBeNull());
    const card = container.querySelector<HTMLElement>(".screens-col .screens-card")!;
    const grip = card.querySelector<HTMLElement>(".screens-grip-side")!;
    fireEvent.pointerDown(grip, { button: 0, clientX: 10, clientY: 10 });
    window.dispatchEvent(new PointerEvent("pointerup", { clientX: 10, clientY: 10 }));
    await waitFor(() => expect(card.className).toContain("is-lifted"));
  });
});

describe("deselecting", () => {
  // The shared quote card keeps its own focus (.bn-focused), and a focused card is raised. Escape
  // once cleared only the board's selection, so the "deselected" card stayed on top of its stack.
  it("clears the card's own focus as well as the board's selection on Escape", async () => {
    mockApi(screensResponse());
    const { container } = render(
      <FocusProvider>
        <ScreensLens />
      </FocusProvider>,
    );
    await waitFor(() => expect(container.querySelector(".screens-col .screens-card")).not.toBeNull());
    const card = container.querySelector<HTMLElement>(".screens-col .screens-card")!;
    const body = card.querySelector<HTMLElement>(".quote-body") ?? card;
    fireEvent.pointerDown(body);
    fireEvent.click(body);
    await waitFor(() => expect(card.querySelector(".quote-card.bn-focused")).not.toBeNull());
    expect(card.className).toContain("is-lifted");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(card.querySelector(".quote-card.bn-focused")).toBeNull());
    expect(card.className).not.toContain("is-lifted");
  });
});

describe("for a keyboard and a screen reader", () => {
  it("brings a card forward when focus enters it, and keeps it forward while focus stays inside", async () => {
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(container.querySelector(".screens-col .screens-card")).not.toBeNull());
    const card = container.querySelector<HTMLElement>(".screens-col .screens-card")!;
    const star = card.querySelector<HTMLElement>(".star-btn")!;
    const hide = card.querySelector<HTMLElement>(".hide-btn")!;
    fireEvent.focus(star);
    expect(card.className).toContain("is-lifted");
    fireEvent.blur(star, { relatedTarget: hide }); // Tab within the card
    expect(card.className).toContain("is-lifted");
    fireEvent.blur(hide, { relatedTarget: document.body }); // Tab out of it
    expect(card.className).not.toContain("is-lifted");
  });

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

  it("keeps focus on the carousel as it turns, and says which slide once", async () => {
    const two = screensResponse();
    (two.screens as { tabs: unknown[] }[])[0].tabs.push({ ...TAB, session_id: "s2", code: "p2", t: 40 });
    mockApi(two);
    await opened();
    const carousel = screen.getByRole("group", { name: "Versions of this screen" });
    expect(carousel.tabIndex).toBe(0); // the keyboard's stop
    expect(carousel).toHaveAttribute("aria-roledescription", "carousel");
    expect(carousel).toHaveAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight");
    expect(carousel).toHaveAttribute("title", "← and → turn between versions");
    carousel.focus();
    vi.mocked(announce).mockClear();
    fireEvent.keyDown(carousel, { key: "ArrowRight" });
    expect(document.activeElement).toBe(carousel);
    // The name stays put, so only the announcement says the slide: once, not twice.
    expect(carousel).toHaveAccessibleName("Versions of this screen");
    expect(announce).toHaveBeenCalledTimes(1);
    expect(announce).toHaveBeenLastCalledWith("p2’s screen at 00:40 · 2 of 2");
    // ↓ to another screen: a new board; focus goes to its title, which says where we are.
    fireEvent.keyDown(carousel, { key: "ArrowDown" });
    expect(document.activeElement).toBe(screen.getByRole("heading", { level: 1 }));
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
  it("opens on the version that links the most quotes, and names whose screenshot it is", async () => {
    mockVersions();
    const c = await openVersions();
    expect(screen.getByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument();
    expect(c.querySelector(".screens-caption")).toHaveTextContent("p2’s screen at 00:40 · 2 of 2");
    // A carousel, not a row of participant buttons.
    expect(screen.getByRole("group", { name: "Versions of this screen" })).toBeInTheDocument();
  });

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
    const carousel = c.querySelector<HTMLElement>(".screens-carousel")!;
    fireEvent.wheel(carousel, { deltaX: -40, deltaY: 0 });
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    // The same swipe's momentum does not turn it again (with two slides it would come back).
    fireEvent.wheel(carousel, { deltaX: -30, deltaY: 0 });
    fireEvent.wheel(carousel, { deltaX: -20, deltaY: 0 });
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
  });

  it("turns from its chevrons and dots, which are the pointer's and not tab stops", async () => {
    mockVersions();
    await openVersions();
    const next = screen.getByRole("button", { name: "Next screengrab" });
    expect(next.tabIndex).toBe(-1);
    fireEvent.click(next);
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    const dot = screen.getByRole("button", { name: "p2’s screen" });
    expect(dot.tabIndex).toBe(-1);
    fireEvent.click(dot);
    expect(screen.getByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument();
  });

  it("cross-fades in one frame: the neighbouring versions are in it, one showing", async () => {
    mockVersions();
    const c = await openVersions();
    await waitFor(() => expect(c.querySelectorAll(".screens-slide")).toHaveLength(2));
    expect(c.querySelectorAll(".screens-slide.is-current")).toHaveLength(1);
    expect(c.querySelector(".screens-slide:not(.is-current)")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("whose quotes", () => {
  it("dims the others' cards with toggle chips, and never turns the carousel", async () => {
    mockVersions();
    const c = await openVersions();
    const chips = screen.getByRole("group", { name: "Whose quotes" });
    const p1 = [...chips.querySelectorAll("button")].find((b) => b.textContent === "p1")!;
    expect(p1).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(p1);
    expect(p1).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument(); // still p2's
    const muted = [...c.querySelectorAll<HTMLElement>(".screens-card.is-muted")].map((el) => el.dataset.dom).sort();
    expect(muted).toEqual(["q-p2-20", "q-p2-60"]);
    fireEvent.click(p1);
    expect(c.querySelector(".screens-card.is-muted")).toBeNull();
  });
});

describe("the narrative", () => {
  it("numbers each person's quotes among their own, in time order, and says so", async () => {
    mockVersions();
    const c = await openVersions();
    const mark = (dom: string) => {
      const card = [...c.querySelectorAll<HTMLElement>(".screens-card")].find((el) => el.dataset.dom === dom)!;
      return [card.querySelector(".screens-seq")!.textContent, card.querySelector(".bn-sr-only")!.textContent];
    };
    expect(mark("q-p1-10")).toEqual(["p11", "p1, quote 1 of 2"]);
    expect(mark("q-p1-30")).toEqual(["p12", "p1, quote 2 of 2"]);
    expect(mark("q-p2-20")).toEqual(["p21", "p2, quote 1 of 2"]);
    expect(mark("q-p2-60")).toEqual(["p22", "p2, quote 2 of 2"]);
  });

  async function focused() {
    mockVersions();
    const c = await openVersions(
      <FocusProvider>
        <ScreensLens />
      </FocusProvider>,
    );
    const now = () => c.querySelector<HTMLElement>(".quote-card.bn-focused")?.id ?? null;
    return { c, now };
  }

  it("steps through the screen's quotes in time order with J and K, bringing each forward", async () => {
    const { c, now } = await focused();
    const press = (key: string) => fireEvent.keyDown(document, { key });
    press("j");
    await waitFor(() => expect(now()).toBe("q-p1-10"));
    press("j");
    await waitFor(() => expect(now()).toBe("q-p2-20"));
    // Brought forward, and its line lit.
    const card = [...c.querySelectorAll<HTMLElement>(".screens-card")].find((el) => el.dataset.dom === "q-p2-20")!;
    expect(card.className).toContain("is-lifted");
    expect(c.querySelector(".screens-hl.on")).not.toBeNull();
    press("j");
    await waitFor(() => expect(now()).toBe("q-p1-30"));
    press("k");
    await waitFor(() => expect(now()).toBe("q-p2-20"));
  });

  it("steps through only the chosen people's quotes when a chip is on", async () => {
    const { now } = await focused();
    const chips = screen.getByRole("group", { name: "Whose quotes" });
    fireEvent.click([...chips.querySelectorAll("button")].find((b) => b.textContent === "p2")!);
    fireEvent.keyDown(document, { key: "j" });
    await waitFor(() => expect(now()).toBe("q-p2-20"));
    fireEvent.keyDown(document, { key: "j" });
    await waitFor(() => expect(now()).toBe("q-p2-60"));
    fireEvent.keyDown(document, { key: "j" });
    await waitFor(() => expect(now()).toBe("q-p2-60")); // clamped, as moveFocus is
  });

  it("leaves J and K to a field, a chord, or a key someone else took", async () => {
    const { now } = await focused();
    fireEvent.keyDown(document, { key: "j", metaKey: true });
    fireEvent.keyDown(document, { key: "j", shiftKey: true });
    const handled = new KeyboardEvent("keydown", { key: "j", bubbles: true, cancelable: true });
    handled.preventDefault();
    act(() => {
      document.dispatchEvent(handled);
    });
    expect(now()).toBeNull();
    const taken = new KeyboardEvent("keydown", { key: "j", bubbles: true, cancelable: true });
    act(() => {
      document.dispatchEvent(taken);
    });
    expect(taken.defaultPrevented).toBe(true); // the lens claimed it
  });
});

describe("the Mac's View menu", () => {
  const menu = (action: string) =>
    act(() => {
      window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action } }));
    });

  it("turns the carousel, changes screen and steps the quotes by name", async () => {
    mockVersions();
    const c = await openVersions(
      <FocusProvider>
        <ScreensLens />
      </FocusProvider>,
    );
    menu("nextScreenshot");
    expect(screen.getByAltText("p1’s screen: Basket, at 00:12")).toBeInTheDocument();
    menu("previousScreenshot");
    expect(screen.getByAltText("p2’s screen: Basket, at 00:40")).toBeInTheDocument();
    menu("nextQuote");
    await waitFor(() => expect(c.querySelector(".quote-card.bn-focused")?.id).toBe("q-p1-10"));
    menu("previousQuote");
    menu("nextScreen");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Delivery or collect");
    menu("previousScreen");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Basket");
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
  ];
  return { width: spies[0], restore: () => spies.forEach((s) => s.mockRestore()) };
}

describe("the report's per-quote keys on Screens", () => {
  // The report's s/h/t/r/x/Enter act only on the quotes this lens registers. A chip dims cards, it
  // does not remove them: a dimmed card takes a click, so it must take a key — and ⌘A selects it.
  it("are scoped to every card the board shows, a chip-dimmed one included", async () => {
    const ctx: { current: ReturnType<typeof useFocus> | null } = { current: null };
    function Probe() {
      const f = useFocus();
      useEffect(() => {
        ctx.current = f;
      });
      return null;
    }
    mockVersions();
    await openVersions(
      <FocusProvider>
        <Probe />
        <ScreensLens />
      </FocusProvider>,
    );
    const chips = screen.getByRole("group", { name: "Whose quotes" });
    fireEvent.click([...chips.querySelectorAll("button")].find((b) => b.textContent === "p2")!);
    expect(new Set(ctx.current!.getVisibleQuoteIds())).toEqual(new Set(["q-p1-10", "q-p2-20", "q-p1-30", "q-p2-60"]));
    act(() => ctx.current!.selectAll());
    expect(ctx.current!.selectedIds.has("q-p1-10")).toBe(true);
  });
});

describe("bringing forward with J/K after a press", () => {
  it("raises the card J lands on, not the one pressed before", async () => {
    mockVersions();
    const c = await openVersions(
      <FocusProvider>
        <ScreensLens />
      </FocusProvider>,
    );
    fireEvent.pointerDown(cardOf(c, "q-p1-30").querySelector(".quote-body")!);
    expect(cardOf(c, "q-p1-30").className).toContain("is-lifted");
    fireEvent.keyDown(document, { key: "j" });
    await waitFor(() => expect(c.querySelector(".quote-card.bn-focused")?.id).toBe("q-p1-10"));
    expect(cardOf(c, "q-p1-10").className).toContain("is-lifted");
    expect(cardOf(c, "q-p1-30").className).not.toContain("is-lifted");
  });
});

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
      return Promise.reject(new Error(path));
    }) as typeof apiGet);
    const c = await openVersions();
    await waitFor(() => expect(screen.getByText("Screengrab unavailable.")).toBeInTheDocument());
    const card = cardOf(c, "q-p1-10");
    expect(card.closest(".screens-loose")).not.toBeNull();
    expect(card.style.visibility).not.toBe("hidden");
    expect(card.className).toContain("is-placed"); // still the researcher's
  });
});

describe("Tidy, counted once", () => {
  // A spot kept for a quote that is not on the board (hidden, or gone) is not an arrangement anyone
  // can see: the arrangement control, the right-click menu and View ▸ Tidy all leave it alone.
  it("offers nothing for a spot kept for a quote not on the board", async () => {
    localStorage.setItem("bristlenose-screens-placements-1",
      JSON.stringify({ "s1@12/q-gone": { kind: "edge", side: "R", frac: 0.4, z: 31 } }));
    mockApi(screensResponse());
    const { container } = render(<ScreensLens />);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Shopping Bag"));
    expect(screen.queryByRole("button", { name: "Arrangement: Custom. Tidy" })).toBeNull();
    fireEvent.contextMenu(container.querySelector(".screens-stage")!);
    expect(screen.queryByRole("menu")).toBeNull();
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
