/**
 * Native bridge — communication between React SPA and macOS WKWebView shell.
 *
 * Installs `window.__bristlenose` namespace (called by native via
 * `callAsyncJavaScript`).  Posts messages to native via
 * `window.webkit.messageHandlers.navigation.postMessage()`.
 *
 * No-ops gracefully when not in WKWebView — all postMessage calls
 * silently bail if `window.webkit` doesn't exist.
 */

import { isEmbedded } from "../utils/embedded";
import { setLocale as setStoreLocale } from "../i18n/LocaleStore";
import { isSupportedLocale } from "../i18n/index";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** State snapshot returned by getState() — queried by native before showing menus. */
export interface BridgeState {
  activeTab: string;
  focusedQuoteId: string | null;
  selectedIds: string[];
  isEditing: boolean;
  canUndo: boolean;
  canRedo: boolean;
  hasPlayer: boolean;
  playerPlaying: boolean;
}

/** Messages posted to the native side via WKScriptMessageHandler. */
export type BridgeMessage =
  | { type: "route-change"; url: string }
  | { type: "ready" }
  | { type: "editing-started"; element: string }
  | { type: "editing-ended" }
  | { type: "project-action"; action: string; data?: object }
  | { type: "find-pasteboard-write"; text: string }
  | { type: "player-state"; hasPlayer: boolean; playing: boolean };

// ---------------------------------------------------------------------------
// Native message posting
// ---------------------------------------------------------------------------

/** Post a message to the native shell. No-ops when not in WKWebView. */
function postNativeMessage(msg: BridgeMessage): void {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).webkit?.messageHandlers?.navigation?.postMessage(msg);
  } catch {
    // Not in WKWebView, or handler deregistered during a race.
  }
}

export function postRouteChange(url: string): void {
  postNativeMessage({ type: "route-change", url });
}

export function postReady(): void {
  postNativeMessage({ type: "ready" });
}

export function postEditingStarted(element: string): void {
  postNativeMessage({ type: "editing-started", element });
}

export function postEditingEnded(): void {
  postNativeMessage({ type: "editing-ended" });
}

export function postProjectAction(action: string, data?: object): void {
  postNativeMessage({ type: "project-action", action, data });
}

/** Write text to the macOS shared find pasteboard (Cmd+E cross-app support). */
export function postFindPasteboardWrite(text: string): void {
  postNativeMessage({ type: "find-pasteboard-write", text });
}

/** Notify native shell of player open/close and play/pause state changes. */
export function postPlayerState(hasPlayer: boolean, playing: boolean): void {
  postNativeMessage({ type: "player-state", hasPlayer, playing });
}

// ---------------------------------------------------------------------------
// Bridge namespace installation
// ---------------------------------------------------------------------------

/** Dependencies injected by AppShell so getState() reads live React state. */
export interface BridgeDeps {
  getActiveTab: () => string;
  getFocusedQuoteId: () => string | null;
  getSelectedIds: () => string[];
  getIsEditing: () => boolean;
  getHasPlayer: () => boolean;
  getPlayerPlaying: () => boolean;
}

/**
 * Install `window.__bristlenose` namespace for native → web calls.
 *
 * Called once from AppShell. Only installs when `isEmbedded()` is true.
 * The namespace provides:
 * - `menuAction(action, payload?)` — dispatches a CustomEvent for React hooks
 * - `getState()` — returns a live BridgeState snapshot
 */
export function installBridge(deps: BridgeDeps): void {
  if (!isEmbedded()) return;

  const ns = {
    menuAction(action: string, payload?: object): void {
      window.dispatchEvent(
        new CustomEvent("bn:menu-action", { detail: { action, payload } }),
      );
    },

    getState(): BridgeState {
      return {
        activeTab: deps.getActiveTab(),
        focusedQuoteId: deps.getFocusedQuoteId(),
        selectedIds: deps.getSelectedIds(),
        isEditing: deps.getIsEditing(),
        // Stubs — wired when undo store ships.
        canUndo: false,
        canRedo: false,
        hasPlayer: deps.getHasPlayer(),
        playerPlaying: deps.getPlayerPlaying(),
      };
    },

    /** Called by native shell to push locale changes. */
    setLocale(locale: string): void {
      if (isSupportedLocale(locale)) {
        void setStoreLocale(locale);
      }
    },
  };

  (window as unknown as Record<string, unknown>).__bristlenose = ns;
}
