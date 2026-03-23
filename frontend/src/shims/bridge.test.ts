import { describe, it, expect, vi, afterEach } from "vitest";
import { _resetEmbeddedCache } from "../utils/embedded";
import {
  installBridge,
  postRouteChange,
  postReady,
  postEditingStarted,
  postEditingEnded,
  postProjectAction,
  postPlayerState,
} from "./bridge";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setEmbedded(v: boolean): void {
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = v;
  _resetEmbeddedCache();
}

function clearEmbedded(): void {
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
}

function installMockWebkit() {
  const postMessage = vi.fn();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).webkit = {
    messageHandlers: { navigation: { postMessage } },
  };
  return postMessage;
}

function clearWebkit(): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (window as any).webkit;
}

function clearBridge(): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (window as any).__bristlenose;
}

const STUB_DEPS = {
  getActiveTab: () => "project" as string,
  getFocusedQuoteId: () => null as string | null,
  getSelectedIds: () => [] as string[],
  getIsEditing: () => false,
  getHasPlayer: () => false,
  getPlayerPlaying: () => false,
};

afterEach(() => {
  clearEmbedded();
  clearWebkit();
  clearBridge();
});

// ---------------------------------------------------------------------------
// postNativeMessage variants
// ---------------------------------------------------------------------------

describe("postRouteChange", () => {
  it("posts route-change message to webkit handler", () => {
    const post = installMockWebkit();
    postRouteChange("/report/quotes/");
    expect(post).toHaveBeenCalledWith({ type: "route-change", url: "/report/quotes/" });
  });

  it("no-ops gracefully when webkit is absent", () => {
    expect(() => postRouteChange("/report/")).not.toThrow();
  });
});

describe("postReady", () => {
  it("posts ready message", () => {
    const post = installMockWebkit();
    postReady();
    expect(post).toHaveBeenCalledWith({ type: "ready" });
  });
});

describe("postEditingStarted / postEditingEnded", () => {
  it("posts editing-started with element name", () => {
    const post = installMockWebkit();
    postEditingStarted("INPUT");
    expect(post).toHaveBeenCalledWith({ type: "editing-started", element: "INPUT" });
  });

  it("posts editing-ended", () => {
    const post = installMockWebkit();
    postEditingEnded();
    expect(post).toHaveBeenCalledWith({ type: "editing-ended" });
  });
});

describe("postProjectAction", () => {
  it("posts project-action with action and optional data", () => {
    const post = installMockWebkit();
    postProjectAction("open-settings", { key: "value" });
    expect(post).toHaveBeenCalledWith({
      type: "project-action",
      action: "open-settings",
      data: { key: "value" },
    });
  });

  it("posts project-action without data", () => {
    const post = installMockWebkit();
    postProjectAction("re-analyse");
    expect(post).toHaveBeenCalledWith({
      type: "project-action",
      action: "re-analyse",
      data: undefined,
    });
  });
});

// ---------------------------------------------------------------------------
// installBridge
// ---------------------------------------------------------------------------

describe("installBridge", () => {
  it("does nothing when not embedded", () => {
    installBridge(STUB_DEPS);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((window as any).__bristlenose).toBeUndefined();
  });

  it("installs namespace when embedded", () => {
    setEmbedded(true);
    installBridge(STUB_DEPS);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ns = (window as any).__bristlenose;
    expect(ns).toBeDefined();
    expect(typeof ns.menuAction).toBe("function");
    expect(typeof ns.getState).toBe("function");
  });

  it("getState returns live values from deps", () => {
    setEmbedded(true);
    let tab = "project";
    installBridge({
      ...STUB_DEPS,
      getActiveTab: () => tab,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ns = (window as any).__bristlenose;
    expect(ns.getState().activeTab).toBe("project");
    tab = "quotes";
    expect(ns.getState().activeTab).toBe("quotes");
  });

  it("getState includes stubbed fields", () => {
    setEmbedded(true);
    installBridge(STUB_DEPS);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const state = (window as any).__bristlenose.getState();
    expect(state.canUndo).toBe(false);
    expect(state.canRedo).toBe(false);
    expect(state.hasPlayer).toBe(false);
    expect(state.playerPlaying).toBe(false);
  });

  it("getState reads live player state from deps", () => {
    setEmbedded(true);
    let hasPlayer = false;
    let playing = false;
    installBridge({
      ...STUB_DEPS,
      getHasPlayer: () => hasPlayer,
      getPlayerPlaying: () => playing,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ns = (window as any).__bristlenose;
    expect(ns.getState().hasPlayer).toBe(false);
    expect(ns.getState().playerPlaying).toBe(false);
    hasPlayer = true;
    playing = true;
    expect(ns.getState().hasPlayer).toBe(true);
    expect(ns.getState().playerPlaying).toBe(true);
  });

  it("menuAction dispatches CustomEvent on window", () => {
    setEmbedded(true);
    installBridge(STUB_DEPS);
    const handler = vi.fn();
    window.addEventListener("bn:menu-action", handler);
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).__bristlenose.menuAction("star", { quoteId: "q-1" });
      expect(handler).toHaveBeenCalledTimes(1);
      const detail = (handler.mock.calls[0][0] as CustomEvent).detail;
      expect(detail.action).toBe("star");
      expect(detail.payload).toEqual({ quoteId: "q-1" });
    } finally {
      window.removeEventListener("bn:menu-action", handler);
    }
  });

  it("menuAction works without payload", () => {
    setEmbedded(true);
    installBridge(STUB_DEPS);
    const handler = vi.fn();
    window.addEventListener("bn:menu-action", handler);
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).__bristlenose.menuAction("toggle-help");
      expect(handler).toHaveBeenCalledTimes(1);
      const detail = (handler.mock.calls[0][0] as CustomEvent).detail;
      expect(detail.action).toBe("toggle-help");
      expect(detail.payload).toBeUndefined();
    } finally {
      window.removeEventListener("bn:menu-action", handler);
    }
  });
});

// ---------------------------------------------------------------------------
// postPlayerState
// ---------------------------------------------------------------------------

describe("postPlayerState", () => {
  it("posts player-state message with hasPlayer and playing", () => {
    const post = installMockWebkit();
    postPlayerState(true, false);
    expect(post).toHaveBeenCalledWith({
      type: "player-state",
      hasPlayer: true,
      playing: false,
    });
  });

  it("posts playing=true when player is playing", () => {
    const post = installMockWebkit();
    postPlayerState(true, true);
    expect(post).toHaveBeenCalledWith({
      type: "player-state",
      hasPlayer: true,
      playing: true,
    });
  });

  it("no-ops gracefully when webkit is absent", () => {
    expect(() => postPlayerState(false, false)).not.toThrow();
  });
});
