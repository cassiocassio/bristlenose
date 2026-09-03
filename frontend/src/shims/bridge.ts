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
  | { type: "anchor-change"; lens: string; anchor: string | null }
  | { type: "ready" }
  | { type: "editing-started"; element: string }
  | { type: "editing-ended" }
  | { type: "project-action"; action: string; data?: object }
  | { type: "find-pasteboard-write"; text: string }
  | { type: "player-state"; hasPlayer: boolean; playing: boolean }
  | { type: "export-counts"; total: number; selected: number; starred: number }
  | { type: "focus-change"; quoteId: string | null }
  | { type: "quote-action-state"; starIsUnstar: boolean; lastTagName: string | null }
  | { type: "lens-subtitle"; tab: string; subtitle: string }
  | { type: "quotes-filter"; searchQuery: string; viewMode: string }
  | { type: "focus-mode"; active: boolean }
  | {
      type: "panel-state";
      leftOpen: boolean;
      rightOpen: boolean;
      inspectorOpen: boolean;
    }
  | { type: "store-miro-token"; token: string }
  | { type: "llm-failure"; kind: string; provider: string };

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

/**
 * Where the reader is within a lens — a heading id, or null for the top of the
 * page. The shell persists it per project so reopening lands there.
 *
 * Carries the lens it belongs to, because this message and `route-change` are
 * independent: without it, "scrolled to the top of Quotes" and "left Quotes"
 * both arrive as a bare null, and the shell would clear a perfectly good
 * remembered position on every lens switch. Same guard as
 * `lens-subtitle`/`lensSubtitleTab`.
 *
 * See `useAnchorReporter`, which decides what counts as a position.
 */
export function postAnchorChange(lens: string, anchor: string | null): void {
  postNativeMessage({ type: "anchor-change", lens, anchor });
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

/**
 * Tell the shell an LLM call died, and how.
 *
 * The app already has an out-of-credit pill and an app-global model behind it
 * (`OutOfCreditModel`), but it was fed from one place only —
 * `PipelineRunner.deriveFailureState`, the *pipeline* path. An AutoCode job
 * runs inside the sidecar and terminates in the SPA, so a researcher whose
 * account emptied mid-autotagging saw a chip say so and the app itself show
 * nothing: the pill stayed dark, and Settings went on reporting the provider
 * green until it next revalidated.
 *
 * `kind` is an `LLMFailureKind` value straight off the wire — the shell
 * decides which kinds it cares about, so a new one needs no change here.
 * `provider` is the *job's* provider rather than the current one, for the
 * reason `recordActiveProviderOutOfCredit` documents: the researcher may have
 * switched providers while the job ran, and the verdict belongs to the account
 * that actually refused.
 */
export function postLLMFailure(kind: string, provider: string): void {
  postNativeMessage({ type: "llm-failure", kind, provider });
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
 * Push the focused-quote id to the native shell so the Quotes menu can enable
 * its focus-gated items (Add Tag, Reveal in Transcript) exactly when a quote is
 * focused in the report — matching the `t` / reveal keyboard bindings. Without
 * this the native `focusedQuoteId` stays nil and those items are always dimmed.
 * Selection *count* rides `export-counts`; this carries focus only, so the two
 * signals can't drift. No-ops outside WKWebView.
 */
export function postFocusChange(quoteId: string | null): void {
  postNativeMessage({ type: "focus-change", quoteId });
}

/**
 * Push the derived state the native Quotes menu needs to label its
 * quote-action items honestly: whether the Star command would *unstar* (the
 * target set is all-starred, mirroring the click/`s`-key intent) and the name
 * of the last-applied tag (for "Apply <name>" + its disabled state). The SPA
 * owns this logic; native chrome only renders the resulting label. No-ops
 * outside WKWebView.
 */
export function postQuoteActionState(
  starIsUnstar: boolean,
  lastTagName: string | null,
): void {
  postNativeMessage({ type: "quote-action-state", starIsUnstar, lastTagName });
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
 * Mirror the report's Focus Mode state to the native View menu's checkmark.
 *
 * The SPA is the source of truth — the menu item dispatches `focusMode` and
 * reads the result back here, rather than tracking its own flag. That matters
 * because two paths reload the web view without the menu knowing: a project
 * switch (the WebView re-mounts on `.id("<project>-<port>")`) and the
 * post-run `reloadWebView()`. Both reset Focus to off, and a native-side
 * `@State` would keep claiming it was on. The posting effect in AppLayout is
 * keyed on the state and so also fires on mount, which is what re-syncs the
 * checkmark after either reload. No-ops outside the desktop WKWebView.
 */
export function postFocusMode(active: boolean): void {
  postNativeMessage({ type: "focus-mode", active });
}

/**
 * Push which of the report's own panels are open, so the native View menu can
 * pick each row's verb honestly — "Hide Tags" while the tag sidebar is showing,
 * "Show Tags" while it isn't. Without this mirror the panel rows read
 * one-directional and are wrong exactly half the time.
 *
 * `leftOpen` covers whichever list the active lens puts in the left slot
 * (Contents / Sessions / Codes / Signals) — they share one `tocMode`.
 * `inspectorOpen` is the analysis heatmap, which lives in `InspectorStore`
 * rather than `SidebarStore` but is the same kind of fact to the menu.
 * Native equality-guards the assigns.
 *
 * The same mirror feeds **Hide All Sidebars**, which needs to know whether
 * anything is showing before it picks its verb. Native owns the projects
 * column and reads it directly; it cannot see inside the WKWebView, so
 * without this it would have to guess. That item stays one-way — the SPA owns
 * the state, native renders the label and sends explicit `hideAllSidebars` /
 * `showAllSidebars` rather than a toggle, so there is no direction for the two
 * sides to disagree about. Posted from an effect keyed on the state, so it
 * also fires on mount — re-syncing the menu after a project switch or the
 * post-run reload remounts the web view. No-ops outside the desktop WKWebView.
 */
export function postPanelState(
  leftOpen: boolean,
  rightOpen: boolean,
  inspectorOpen: boolean,
): void {
  postNativeMessage({ type: "panel-state", leftOpen, rightOpen, inspectorOpen });
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
     * Called by native shell to push the unified titlebar+toolbar height (CSS
     * px) so the SPA can top-pad content out from under the translucent frost.
     * The WKWebView paints transparent and extends behind the toolbar
     * (ContentView: .ignoresSafeArea(.container, edges: .top)), so without a
     * pad the first row of content is clipped by the frost band. Rendered as
     * `--bn-toolbar-inset` on <html>; report.css consumes it in the embedded
     * body's padding-top calc. Fired once on `ready`; static-at-ready is fine
     * for alpha per the spike brief.
     */
    setToolbarInset(px: unknown): void {
      const n = typeof px === "number" && Number.isFinite(px) && px >= 0 ? px : 0;
      document.documentElement.style.setProperty("--bn-toolbar-inset", `${n}px`);
    },

    /**
     * Called by native shell to push colour-palette changes — live, no reload.
     * The report is a runtime `data-color-theme` CSS swap, so (unlike typography)
     * the native picker applies it here instead of restarting the serve sidecar.
     * Persisted so it agrees with the web store and survives a later reload.
     */
    /**
     * Called by native shell to push the "Show animation while analysing"
     * toggle (Appearance settings). The web "thinking shimmer" (activity chip
     * label — atoms/shimmer.css) gates on `data-analysis-animation`: absent or
     * anything but "off" animates; "off" freezes to static text. This is the
     * native twin of the CSS `prefers-reduced-motion` gate — both must pass.
     * Fired on `ready` (and on the toggle changing). No persistence: the native
     * AppStorage value is the source of truth, re-pushed every load.
     */
    setAnalysisAnimation(on: unknown): void {
      const root = document.documentElement;
      if (on === false) {
        root.setAttribute("data-analysis-animation", "off");
      } else {
        root.removeAttribute("data-analysis-animation");
      }
    },

    setColorPalette(palette: string): void {
      if (!isPalette(palette)) return;
      const root = document.documentElement;
      root.setAttribute("data-color-theme", palette);
      // WKWebView doesn't reliably repaint a style change pushed from Swift's
      // callAsyncJavaScript (no user gesture / render tick): the tokens update
      // correctly but the pixels stay stale. Diagnosed 3 Jul 2026 — the computed
      // accent was already the new palette's value, only paint lagged; a WebKit
      // repro with the real 281 KB CSS confirmed the cascade itself is fine. An
      // imperceptible opacity nudge across one frame forces a compositor repaint
      // without touching layout or scroll position. Browser Settings goes through
      // handlePalette (real user gesture) and never hits this; harmless there.
      root.style.opacity = "0.999";
      requestAnimationFrame(() => {
        root.style.opacity = "";
      });
      try {
        localStorage.setItem("bristlenose-palette", JSON.stringify(palette));
      } catch {
        // Applied for the session; persistence is best-effort (private mode/quota).
      }
    },
  };

  (window as unknown as Record<string, unknown>).__bristlenose = ns;
}
