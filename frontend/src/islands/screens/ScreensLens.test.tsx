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

beforeAll(() => {
  // jsdom has no ResizeObserver; the board measures through one.
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = class {
    observe() {}
    disconnect() {}
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
  it("puts the pinned cards first in the list under the screengrab when the stage is too narrow for a column", async () => {
    const spy = vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(600);
    try {
      mockApi(screensResponse());
      const { container } = render(<ScreensLens />);
      await waitFor(() => expect(container.querySelector(".screens-loose .screens-card")).not.toBeNull());
      expect(container.querySelector(".screens-board")!.className).toContain("cols-none");
      expect(container.querySelector(".screens-col .screens-card")).toBeNull();
      const first = container.querySelector<HTMLElement>(".screens-loose .screens-card")!;
      expect(first.dataset.dom).toBe("q-p1-10"); // the pinned quote leads the list
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
    expect(announce).toHaveBeenLastCalledWith("p2’s screen");
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
