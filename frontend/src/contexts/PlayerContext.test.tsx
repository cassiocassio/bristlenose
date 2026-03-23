import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import {
  PlayerProvider,
  usePlayer,
  getPlayerOpen,
  getPlayerPlaying,
} from "./PlayerContext";

vi.mock("../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../shims/bridge", () => ({ postPlayerState: vi.fn() }));

import { announce } from "../utils/announce";
import { postPlayerState } from "../shims/bridge";

// ── Helpers ──────────────────────────────────────────────────────────────

/** Render PlayerProvider inside a memory router (useLocation dependency). */
function renderProvider(children?: React.ReactNode) {
  const routes = [
    {
      path: "/",
      element: <PlayerProvider>{children ?? <div />}</PlayerProvider>,
    },
  ];
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  return render(<RouterProvider router={router} />);
}

/** Build a mock transcript segment DOM element. */
function addSegment(
  pid: string,
  start: number,
  end: number,
  container: HTMLElement = document.body,
): HTMLElement {
  const el = document.createElement("div");
  el.className = "transcript-segment";
  el.setAttribute("data-participant", pid);
  el.setAttribute("data-start-seconds", String(start));
  el.setAttribute("data-end-seconds", String(end));
  el.scrollIntoView = vi.fn();
  container.appendChild(el);
  return el;
}

/** Build a mock quote blockquote DOM element. */
function addBlockquote(
  pid: string,
  start: number,
  end: number,
  container: HTMLElement = document.body,
): HTMLElement {
  const bq = document.createElement("blockquote");
  bq.setAttribute("data-participant", pid);
  const link = document.createElement("a");
  link.className = "timecode";
  link.setAttribute("data-seconds", String(start));
  link.setAttribute("data-end-seconds", String(end));
  bq.appendChild(link);
  bq.scrollIntoView = vi.fn();
  container.appendChild(bq);
  return bq;
}

/** Dispatch a postMessage event to the window (with matching origin). */
function postPlayerMessage(data: unknown) {
  const event = new MessageEvent("message", {
    data,
    origin: window.location.origin,
  });
  window.dispatchEvent(event);
}

// ── Setup / teardown ─────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let openSpy: ReturnType<typeof vi.spyOn<any, any>>;

beforeEach(() => {
  // Provide video map and player URL globals
  const win = window as unknown as Record<string, unknown>;
  win.BRISTLENOSE_VIDEO_MAP = { p1: "/media/session1.mp4", s1: "/media/session1.mp4" };
  win.BRISTLENOSE_PLAYER_URL = "/assets/bristlenose-player.html";

  // Mock window.open
  openSpy = vi.spyOn(window, "open").mockReturnValue({
    closed: false,
    postMessage: vi.fn(),
    focus: vi.fn(),
  } as unknown as Window);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  const win = window as unknown as Record<string, unknown>;
  delete win.BRISTLENOSE_VIDEO_MAP;
  delete win.BRISTLENOSE_PLAYER_URL;
  delete win.seekTo;

  // Remove test DOM elements
  document
    .querySelectorAll(".transcript-segment, blockquote[data-participant]")
    .forEach((el) => el.remove());
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("PlayerContext", () => {
  // --- seekTo ---

  it("opens popout window on first seekTo call", () => {
    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => playerSeekTo("p1", 42));

    expect(openSpy).toHaveBeenCalledOnce();
    const url = openSpy.mock.calls[0][0] as string;
    expect(url).toContain("/assets/bristlenose-player.html#");
    expect(url).toContain("t=42");
    expect(url).toContain("pid=p1");
  });

  it("reuses existing window on subsequent seekTo calls", () => {
    const mockWin = {
      closed: false,
      postMessage: vi.fn(),
      focus: vi.fn(),
    };
    openSpy.mockReturnValue(mockWin as unknown as Window);

    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => playerSeekTo("p1", 10));
    act(() => playerSeekTo("p1", 20));

    expect(openSpy).toHaveBeenCalledOnce();
    expect(mockWin.postMessage).toHaveBeenCalledOnce();
    expect(mockWin.postMessage).toHaveBeenCalledWith(
      expect.objectContaining({ type: "bristlenose-seek", pid: "p1", t: 20 }),
      window.location.origin,
    );
    expect(mockWin.focus).toHaveBeenCalled();
  });

  it("no-ops when pid is not in video map", () => {
    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => playerSeekTo("p999", 10));

    expect(openSpy).not.toHaveBeenCalled();
  });

  it("handles popup blocked (window.open returns null)", () => {
    openSpy.mockReturnValue(null);

    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    // Should not throw
    expect(() => act(() => playerSeekTo("p1", 10))).not.toThrow();
  });

  // --- Glow: timeupdate ---

  it("adds glow classes on timeupdate message", () => {
    const seg = addSegment("p1", 10, 20);
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });

    expect(seg.classList.contains("bn-timecode-glow")).toBe(true);
    expect(seg.classList.contains("bn-timecode-playing")).toBe(true);
  });

  it("toggles playing class on playstate message", () => {
    const seg = addSegment("p1", 10, 20);
    renderProvider();

    // First: playing
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });
    expect(seg.classList.contains("bn-timecode-playing")).toBe(true);

    // Then: paused
    act(() => {
      postPlayerMessage({
        type: "bristlenose-playstate",
        pid: "p1",
        playing: false,
      });
    });
    expect(seg.classList.contains("bn-timecode-glow")).toBe(true);
    expect(seg.classList.contains("bn-timecode-playing")).toBe(false);
  });

  // --- Glow: player close ---

  it("clears glow when player window closes", () => {
    vi.useFakeTimers();
    const mockWin = { closed: false, postMessage: vi.fn(), focus: vi.fn() };
    openSpy.mockReturnValue(mockWin as unknown as Window);

    const seg = addSegment("p1", 10, 20);

    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    // Open player + glow
    act(() => playerSeekTo("p1", 15));
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });
    expect(seg.classList.contains("bn-timecode-glow")).toBe(true);

    // Simulate player window closing
    mockWin.closed = true;
    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(seg.classList.contains("bn-timecode-glow")).toBe(false);
    expect(seg.classList.contains("bn-timecode-playing")).toBe(false);
  });

  // --- Glow index ---

  it("indexes transcript segments correctly", () => {
    const seg1 = addSegment("p1", 0, 10);
    const seg2 = addSegment("p1", 10, 20);
    addSegment("p2", 0, 30); // Different participant

    renderProvider();

    // Timeupdate at t=5 should glow seg1 only
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 5,
        playing: false,
      });
    });

    expect(seg1.classList.contains("bn-timecode-glow")).toBe(true);
    expect(seg2.classList.contains("bn-timecode-glow")).toBe(false);
  });

  it("indexes quote blockquotes correctly", () => {
    const bq = addBlockquote("p1", 30, 45);
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 35,
        playing: false,
      });
    });

    expect(bq.classList.contains("bn-timecode-glow")).toBe(true);
  });

  it("fixes zero-length segments using next segment start", () => {
    // Segment with end == start (from .txt files)
    const seg1 = addSegment("p1", 10, 10);
    addSegment("p1", 20, 30);

    renderProvider();

    // t=15 is between seg1.start (10) and seg2.start (20) → seg1 should glow
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: false,
      });
    });

    expect(seg1.classList.contains("bn-timecode-glow")).toBe(true);
  });

  // --- Auto-scroll ---

  it("auto-scrolls transcript segments but not blockquotes", () => {
    const seg = addSegment("p1", 10, 20);
    const bq = addBlockquote("p1", 10, 20);
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: false,
      });
    });

    expect(seg.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
    });
    expect(bq.scrollIntoView).not.toHaveBeenCalled();
  });

  // --- Progress fill ---

  it("sets --bn-segment-progress on transcript segments during glow", () => {
    const seg = addSegment("p1", 10, 20);
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });

    // 15 is 50% through [10, 20]
    expect(seg.style.getPropertyValue("--bn-segment-progress")).toBe("0.5");
  });

  it("clamps progress between 0 and 1", () => {
    const seg = addSegment("p1", 10, 20);
    renderProvider();

    // At the start
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 10,
        playing: true,
      });
    });
    expect(seg.style.getPropertyValue("--bn-segment-progress")).toBe("0");

    // Just before end
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 19.9,
        playing: true,
      });
    });
    const progress = parseFloat(
      seg.style.getPropertyValue("--bn-segment-progress"),
    );
    expect(progress).toBeGreaterThan(0.9);
    expect(progress).toBeLessThanOrEqual(1);
  });

  it("clears --bn-segment-progress when segment loses glow", () => {
    const seg1 = addSegment("p1", 10, 20);
    addSegment("p1", 20, 30);
    renderProvider();

    // Glow seg1
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });
    expect(seg1.style.getPropertyValue("--bn-segment-progress")).toBe("0.5");

    // Move to seg2 — seg1 loses glow
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 25,
        playing: true,
      });
    });
    expect(seg1.style.getPropertyValue("--bn-segment-progress")).toBe("");
  });

  it("does not set progress on blockquote elements", () => {
    const bq = addBlockquote("p1", 30, 45);
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 35,
        playing: true,
      });
    });

    expect(bq.classList.contains("bn-timecode-glow")).toBe(true);
    expect(bq.style.getPropertyValue("--bn-segment-progress")).toBe("");
  });

  it("handles zero-duration segments using corrected end from glow index", () => {
    const seg = addSegment("p1", 10, 10);
    addSegment("p1", 20, 30); // next segment fixes zero-length via index
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });

    // Zero-length segment gets fixed end=20 from next segment.
    // (15 - 10) / (20 - 10) = 0.5
    expect(seg.style.getPropertyValue("--bn-segment-progress")).toBe("0.5");
  });

  it("shows zero progress for last zero-length segment (Infinity end)", () => {
    // Last segment with end == start gets end = Infinity — progress should be 0
    const seg = addSegment("p1", 50, 50);
    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 55,
        playing: true,
      });
    });

    expect(seg.classList.contains("bn-timecode-glow")).toBe(true);
    expect(seg.style.getPropertyValue("--bn-segment-progress")).toBe("0");
  });

  // --- Backward-compat shim ---

  it("installs window.seekTo shim", () => {
    renderProvider();
    expect(typeof (window as unknown as Record<string, unknown>).seekTo).toBe(
      "function",
    );
  });

  // --- Cleanup ---

  it("cleans up on unmount", () => {
    const seg = addSegment("p1", 10, 20);
    const { unmount } = renderProvider();

    // Glow an element
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });
    expect(seg.classList.contains("bn-timecode-glow")).toBe(true);

    // Unmount should clear glow
    unmount();
    expect(seg.classList.contains("bn-timecode-glow")).toBe(false);
    expect(seg.classList.contains("bn-timecode-playing")).toBe(false);
  });

  // --- Word-level highlighting ---

  it("adds bn-word-active to the current word during playback", () => {
    const seg = addSegment("p1", 10, 20);
    const w1 = document.createElement("span");
    w1.className = "transcript-word";
    w1.setAttribute("data-start", "10");
    w1.setAttribute("data-end", "13");
    const w2 = document.createElement("span");
    w2.className = "transcript-word";
    w2.setAttribute("data-start", "13");
    w2.setAttribute("data-end", "16");
    const w3 = document.createElement("span");
    w3.className = "transcript-word";
    w3.setAttribute("data-start", "16");
    w3.setAttribute("data-end", "20");
    seg.appendChild(w1);
    seg.appendChild(w2);
    seg.appendChild(w3);

    renderProvider();

    // At t=11 → word 1 is active
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 11,
        playing: true,
      });
    });
    expect(w1.classList.contains("bn-word-active")).toBe(true);
    expect(w2.classList.contains("bn-word-active")).toBe(false);
    expect(w3.classList.contains("bn-word-active")).toBe(false);

    // At t=14 → word 2 is active, word 1 cleared
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 14,
        playing: true,
      });
    });
    expect(w1.classList.contains("bn-word-active")).toBe(false);
    expect(w2.classList.contains("bn-word-active")).toBe(true);
    expect(w3.classList.contains("bn-word-active")).toBe(false);
  });

  it("clears bn-word-active when segment loses glow", () => {
    const seg1 = addSegment("p1", 10, 20);
    const w1 = document.createElement("span");
    w1.className = "transcript-word";
    w1.setAttribute("data-start", "10");
    w1.setAttribute("data-end", "20");
    seg1.appendChild(w1);
    addSegment("p1", 20, 30);

    renderProvider();

    // Glow seg1 with word active
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });
    expect(w1.classList.contains("bn-word-active")).toBe(true);

    // Move to seg2 — seg1 loses glow, word should clear
    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 25,
        playing: true,
      });
    });
    expect(seg1.classList.contains("bn-timecode-glow")).toBe(false);
    expect(w1.classList.contains("bn-word-active")).toBe(false);
  });

  it("clears bn-word-active on clearAllGlow (unmount)", () => {
    const seg = addSegment("p1", 10, 20);
    const w1 = document.createElement("span");
    w1.className = "transcript-word";
    w1.setAttribute("data-start", "10");
    w1.setAttribute("data-end", "20");
    seg.appendChild(w1);

    const { unmount } = renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 15,
        playing: true,
      });
    });
    expect(w1.classList.contains("bn-word-active")).toBe(true);

    unmount();
    expect(w1.classList.contains("bn-word-active")).toBe(false);
  });

  it("does not add bn-word-active to blockquote children", () => {
    const bq = addBlockquote("p1", 30, 45);
    const w1 = document.createElement("span");
    w1.className = "transcript-word";
    w1.setAttribute("data-start", "30");
    w1.setAttribute("data-end", "45");
    bq.appendChild(w1);

    renderProvider();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-timeupdate",
        pid: "p1",
        seconds: 35,
        playing: true,
      });
    });
    // Blockquotes get glow but not word-level highlighting
    expect(bq.classList.contains("bn-timecode-glow")).toBe(true);
    expect(w1.classList.contains("bn-word-active")).toBe(false);
  });

  // --- sendCommand ---

  it("sendCommand posts bristlenose-command to popout window", () => {
    const mockWin = {
      closed: false,
      postMessage: vi.fn(),
      focus: vi.fn(),
    };
    openSpy.mockReturnValue(mockWin as unknown as Window);

    let cmd: (command: string, data?: Record<string, unknown>) => void = () => {};
    let seek: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const ctx = usePlayer();
      cmd = ctx.sendCommand;
      seek = ctx.seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    // Open the player first
    act(() => seek("p1", 0));

    act(() => cmd("playPause"));
    expect(mockWin.postMessage).toHaveBeenCalledWith(
      { type: "bristlenose-command", command: "playPause", payload: undefined },
      window.location.origin,
    );
  });

  it("sendCommand includes extra data fields", () => {
    const mockWin = {
      closed: false,
      postMessage: vi.fn(),
      focus: vi.fn(),
    };
    openSpy.mockReturnValue(mockWin as unknown as Window);

    let cmd: (command: string, data?: Record<string, unknown>) => void = () => {};
    let seek: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const ctx = usePlayer();
      cmd = ctx.sendCommand;
      seek = ctx.seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => seek("p1", 0));
    act(() => cmd("skipRelative", { seconds: 5 }));
    expect(mockWin.postMessage).toHaveBeenCalledWith(
      { type: "bristlenose-command", command: "skipRelative", payload: { seconds: 5 } },
      window.location.origin,
    );
  });

  it("sendCommand is a no-op when no player window is open", () => {
    openSpy.mockReturnValue(null);

    let cmd: (command: string, data?: Record<string, unknown>) => void = () => {};
    function Consumer() {
      const ctx = usePlayer();
      cmd = ctx.sendCommand;
      return null;
    }
    renderProvider(<Consumer />);

    // No seekTo call — no player window exists
    expect(() => act(() => cmd("playPause"))).not.toThrow();
  });

  // --- Module-level player state getters ---

  it("getPlayerOpen returns true after seekTo opens a window", () => {
    const mockWin = {
      closed: false,
      postMessage: vi.fn(),
      focus: vi.fn(),
    };
    openSpy.mockReturnValue(mockWin as unknown as Window);

    let seek: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const ctx = usePlayer();
      seek = ctx.seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    expect(getPlayerOpen()).toBe(false);
    act(() => seek("p1", 0));
    expect(getPlayerOpen()).toBe(true);
  });

  it("getPlayerPlaying updates from playstate messages", () => {
    renderProvider();

    expect(getPlayerPlaying()).toBe(false);
    act(() => {
      postPlayerMessage({
        type: "bristlenose-playstate",
        pid: "p1",
        playing: true,
      });
    });
    expect(getPlayerPlaying()).toBe(true);

    act(() => {
      postPlayerMessage({
        type: "bristlenose-playstate",
        pid: "p1",
        playing: false,
      });
    });
    expect(getPlayerPlaying()).toBe(false);
  });

  it("getPlayerOpen resets to false when player window closes", () => {
    vi.useFakeTimers();
    const mockWin = {
      closed: false,
      postMessage: vi.fn(),
      focus: vi.fn(),
    };
    openSpy.mockReturnValue(mockWin as unknown as Window);

    let seek: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const ctx = usePlayer();
      seek = ctx.seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => seek("p1", 0));
    expect(getPlayerOpen()).toBe(true);

    // Simulate window close
    mockWin.closed = true;
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(getPlayerOpen()).toBe(false);
    expect(getPlayerPlaying()).toBe(false);
  });

  // --- Origin validation (#1) ---

  it("ignores messages from a different origin", () => {
    const seg = addSegment("p1", 10, 20);
    renderProvider();

    act(() => {
      const event = new MessageEvent("message", {
        data: {
          type: "bristlenose-timeupdate",
          pid: "p1",
          seconds: 15,
          playing: true,
        },
        origin: "https://evil.example.com",
      });
      window.dispatchEvent(event);
    });

    expect(seg.classList.contains("bn-timecode-glow")).toBe(false);
  });

  // --- a11y announce on seekTo (#5) ---

  it("announces participant when seekTo opens a player", () => {
    const mockAnnounce = vi.mocked(announce);
    mockAnnounce.mockClear();

    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => playerSeekTo("p1", 42));
    expect(mockAnnounce).toHaveBeenCalledWith("Playing p1");
  });

  // --- Bridge player-state notifications (#6) ---

  it("posts player-state to bridge on seekTo", () => {
    const mockPost = vi.mocked(postPlayerState);
    mockPost.mockClear();

    let playerSeekTo: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const { seekTo } = usePlayer();
      playerSeekTo = seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => playerSeekTo("p1", 0));
    expect(mockPost).toHaveBeenCalledWith(true, false);
  });

  it("posts player-state to bridge on playstate message", () => {
    const mockPost = vi.mocked(postPlayerState);
    renderProvider();
    mockPost.mockClear();

    act(() => {
      postPlayerMessage({
        type: "bristlenose-playstate",
        pid: "p1",
        playing: true,
      });
    });
    expect(mockPost).toHaveBeenCalledWith(true, true);
  });

  it("posts player-state(false, false) to bridge when player closes", () => {
    vi.useFakeTimers();
    const mockWin = { closed: false, postMessage: vi.fn(), focus: vi.fn() };
    openSpy.mockReturnValue(mockWin as unknown as Window);
    const mockPost = vi.mocked(postPlayerState);

    let seek: (pid: string, seconds: number) => void = () => {};
    function Consumer() {
      const ctx = usePlayer();
      seek = ctx.seekTo;
      return null;
    }
    renderProvider(<Consumer />);

    act(() => seek("p1", 0));
    mockPost.mockClear();

    mockWin.closed = true;
    act(() => {
      vi.advanceTimersByTime(1100);
    });
    expect(mockPost).toHaveBeenCalledWith(false, false);
  });
});
