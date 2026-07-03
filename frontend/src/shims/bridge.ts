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
import { isPalette } from "../utils/bootPalette";
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
  | { type: "player-state"; hasPlayer: boolean; playing: boolean }
  | { type: "export-counts"; total: number; selected: number; starred: number }
  | { type: "lens-subtitle"; tab: string; subtitle: string }
  | { type: "quotes-filter"; searchQuery: string; viewMode: string }
  | { type: "store-miro-token"; token: string };

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

/**
  * Push live export scope counts to the native shell so the macOS export
 * popover can label its "Copy Quotes" scope choices (All / Selected / Starred)
 * with current totals. No-ops outside WKWebView.
 */
export function postExportCounts(total: number, selected: number, starred: number): void {
  postNativeMessage({ type: "export-counts", total, selected, starred });
}

/**
 * Push the active lens's subtitle to the native window subtitle — e.g.
 * "163 Quotes", "3 Codebooks · 47 Tags". The SPA owns the count + formatting
 * (live as quotes hide and tags/signals change); native chrome just renders
 * the string. `tab` lets the receiver ignore a subtitle for a lens it has
 * already navigated away from.
 */
export function postLensSubtitle(tab: string, subtitle: string): void {
  postNativeMessage({ type: "lens-subtitle", tab, subtitle });
}

/**
 * Push the Quotes-lens filter state to the native shell so the macOS toolbar's
 * native search field + starred toggle (and the View-menu checkmarks) reflect
 * the live store. The native field is the sole text input in embedded mode, so
 * this is a one-way mirror for the few store changes the native side didn't
 * originate (Cmd+E selection, All Quotes reset). Native echo-guards on value
 * equality. No-ops outside WKWebView.
 */
export function postQuotesFilter(searchQuery: string, viewMode: string): void {
  postNativeMessage({ type: "quotes-filter", searchQuery, viewMode });
}

/**
 * Hand a validated Miro access token to the native host so it persists in the
 * macOS Keychain — the sandboxed Python sidecar can't write the Keychain itself,
 * so without this the token is lost on app restart. The host injects it to the
 * next sidecar launch as `BRISTLENOSE_MIRO_ACCESS_TOKEN`. No-ops outside the
 * desktop WKWebView (browser/serve mode persists via the Python keychain path).
 */
export function postStoreMiroToken(token: string): void {
  postNativeMessage({ type: "store-miro-token", token });
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

    /**
     * Called by native shell to push colour-palette changes — live, no reload.
     * The report is a runtime `data-color-theme` CSS swap, so (unlike typography)
     * the native picker applies it here instead of restarting the serve sidecar.
     * Persisted so it agrees with the web store and survives a later reload.
     */
    setColorPalette(palette: string): void {
      if (!isPalette(palette)) return;
      document.documentElement.setAttribute("data-color-theme", palette);
      try {
        localStorage.setItem("bristlenose-palette", JSON.stringify(palette));
      } catch {
        // Applied for the session; persistence is best-effort (private mode/quota).
      }
    },
  };

  (window as unknown as Record<string, unknown>).__bristlenose = ns;
}
