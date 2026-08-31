/**
 * AppLayout — top-level layout for the report SPA.
 *
 * Renders Header, NavBar, Outlet, and Footer.  Installs backward-compat
 * navigation shims on window for vanilla JS modules.  Provides
 * FocusProvider (keyboard focus/selection) and installs global keyboard
 * shortcuts via useKeyboardShortcuts.
 */

import { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from "react";
import { Outlet, useNavigate, useMatch, useLocation } from "react-router-dom";
import { Header } from "../components/Header";
import { NavBar } from "../components/NavBar";
import { Footer } from "../components/Footer";
import { formatTimecode } from "../utils/format";
import { FeedbackModal } from "../components/FeedbackModal";
import { SettingsModal } from "../components/SettingsModal";
import { SidebarLayout, sidebarAnimations } from "../components/SidebarLayout";
import { SessionsSidebar } from "../components/SessionsSidebar";
// By path, not through the `components` barrel — the barrel rides in the
// always-loaded chunk, and this is only reachable from one route.
import { CodebookV2Sidebar } from "../components/CodebookV2Sidebar";
import { AnalysisSidebar } from "../components/AnalysisSidebar";
import { ExportDialog } from "../components/ExportDialog";
import { MiroExportPanel } from "../components/MiroExportPanel";
import { ActivityChipStack, normaliseAutoCode } from "../components/ActivityChipStack";
import type { ActivityJob } from "../components/ActivityChipStack";
import { AnnounceRegion } from "../components/AnnounceRegion";
import { LensSubtitleSync } from "../components/LensSubtitleSync";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider, useFocus } from "../contexts/FocusContext";
import { useActivityJobs, removeJob } from "../contexts/ActivityStore";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useAnchorReporter } from "../hooks/useAnchorReporter";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";
import { useProjectId } from "../hooks/useProjectId";
import {
  installBridge,
  postRouteChange,
  postReady,
  postProjectAction,
  postFindPasteboardWrite,
  postExportCounts,
  postFocusChange,
  postQuoteActionState,
  postFocusMode,
  postPanelState,
} from "../shims/bridge";
import { toggleFocusMode, useFocusMode } from "../contexts/FocusModeStore";
import { getPlayerOpen, getPlayerPlaying } from "../contexts/PlayerContext";
import { cancelAutoCode, cancelClipExtraction, getAutoCodeStatus, getClipExtractionStatus, revealClips } from "../utils/api";
import {
  copyQuotesToClipboard,
  saveQuotesSpreadsheet,
  extractVideoClips,
} from "../utils/exportActions";
import type { NormalisedJobStatus } from "../components/ActivityChipStack";
import { toggleInspector, useInspectorStore } from "../contexts/InspectorStore";
import { useSidebarStore } from "../contexts/SidebarStore";
import {
  setSearchQuery,
  setViewMode,
  setTagFilter,
  getQuotesSnapshot,
  getVisibleQuotes,
  useQuoteCounts,
  useStarredMap,
  useLastTagName,
  starActionIsUnstar,
} from "../contexts/QuotesContext";
import { EMPTY_TAG_FILTER } from "../utils/filter";
import { toast } from "../utils/toast";
import { announce } from "../utils/announce";
import i18n from "../i18n";
import { resolveBrowserLang } from "../i18n/LocaleStore";
import { isEditing } from "../utils/editing";
import { isEmbedded } from "../utils/embedded";
import { getExportData } from "../utils/exportData";
import { DEFAULT_HEALTH_RESPONSE, type HealthResponse } from "../utils/health";

// ── CSV helpers (shared with Toolbar — duplicated to avoid coupling) ─────

function csvEsc(v: string): string {
  if (v.includes(",") || v.includes('"') || v.includes("\n")) {
    return `"${v.replace(/"/g, '""')}"`;
  }
  return v;
}

function buildCsvString(
  quoteIds: string[] | null,
  store: ReturnType<typeof getQuotesSnapshot>,
): string {
  const header = [
    i18n.t("toolbar.csvTimecode"),
    i18n.t("toolbar.csvQuote"),
    i18n.t("toolbar.csvParticipant"),
    i18n.t("toolbar.csvTopic"),
    i18n.t("toolbar.csvSentiment"),
    i18n.t("toolbar.csvTags"),
  ];
  const quotes = quoteIds
    ? store.quotes.filter((q) => quoteIds.includes(q.dom_id))
    : store.quotes;
  const rows = quotes.map((q) => {
    const text = store.edits[q.dom_id] ?? q.text;
    const tags = (store.tags[q.dom_id] ?? q.tags).map((t) => t.name).join("; ");
    return [
      csvEsc(formatTimecode(q.start_timecode)),
      csvEsc(text),
      csvEsc(q.speaker_name),
      csvEsc(q.topic_label),
      csvEsc(q.sentiment ?? ""),
      csvEsc(tags),
    ].join(",");
  });
  return [header.join(","), ...rows].join("\n");
}

// ── Zoom helpers ─────────────────────────────────────────────────────────

const ZOOM_STEP = 0.1;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 2.0;
const ZOOM_KEY = "bristlenose-zoom";

function getZoom(): number {
  try {
    const raw = localStorage.getItem(ZOOM_KEY);
    if (raw) return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, parseFloat(raw)));
  } catch { /* */ }
  return 1;
}

function applyZoom(level: number): void {
  const clamped = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.round(level * 100) / 100));
  document.documentElement.style.fontSize = `${clamped * 100}%`;
  try { localStorage.setItem(ZOOM_KEY, String(clamped)); } catch { /* */ }
}

/** Dev-only playground — lazy-loaded so it's tree-shaken in production. */
const ResponsivePlayground = lazy(
  () =>
    import("../components/ResponsivePlayground").then((m) => ({
      default: m.ResponsivePlayground,
    })),
);
const PlaygroundHUD = lazy(
  () =>
    import("../components/PlaygroundHUD").then((m) => ({
      default: m.PlaygroundHUD,
    })),
);

/** Check if we're in dev mode (set by _build_dev_html in app.py). */
const IS_DEV =
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_DEV__ === true ||
  location.port === "5173";

// Help is browser-based docs now — the in-app Help modal is retired. Open in a
// NAMED tab so repeated ? presses reuse one tab instead of spawning a pile.
const DOCS_URL = "https://bristlenose.app/docs/";
const SHORTCUTS_DOCS_URL = "https://bristlenose.app/docs/keyboard-shortcuts.html";
function openDocs(url: string): void {
  window.open(url, "bristlenose-docs");
}

/**
 * Inner component that uses hooks requiring PlayerProvider + FocusProvider.
 */
function AppShell() {
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportAnonymise, setExportAnonymise] = useState(false);
  const [miroOpen, setMiroOpen] = useState(false);
  const projectId = useProjectId();
  const isEmbeddedDesktop = useCallback(
    () => Boolean((window as unknown as { __BRISTLENOSE_EMBEDDED__?: boolean }).__BRISTLENOSE_EMBEDDED__),
    [],
  );
  const triggerReportDownload = useCallback(
    (anonymise: boolean) => {
      // Bake the researcher's current UI language into the export so the
      // offline report reads in the language they wrote it in — not the
      // recipient's browser language (there's no server on file:// to inject it).
      // Normalise via resolveBrowserLang: i18n.language can be a raw region tag
      // (en-US / en-GB) that isSupportedLocale rejects, which would silently drop
      // the bake and fall back to the recipient's browser — the exact bug this fixes.
      const params = new URLSearchParams();
      if (anonymise) params.set("anonymise", "true");
      params.set("locale", resolveBrowserLang(i18n.language) ?? "en");
      const a = document.createElement("a");
      a.href = `/api/projects/${projectId}/export?${params.toString()}`;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    },
    [projectId],
  );
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse>(DEFAULT_HEALTH_RESPONSE);
  const openFeedback = useCallback(() => setFeedbackOpen(true), []);
  const closeFeedback = useCallback(() => setFeedbackOpen(false), []);
  const toggleSettings = useCallback(() => {
    if (isEmbedded()) {
      postProjectAction("open-settings");
      return;
    }
    setSettingsOpen((prev) => !prev);
  }, []);
  const _isQuotes = useMatch("/report/quotes");
  const _isQuotesSlash = useMatch("/report/quotes/");
  const _isSessions = useMatch("/report/sessions");
  const _isSessionsSlash = useMatch("/report/sessions/");
  const isTranscript = useMatch("/report/sessions/:sessionId");
  const _isCodebook = useMatch("/report/codebook");
  const _isCodebookSlash = useMatch("/report/codebook/");
  // `useMatch` is exact, so these do NOT also match `/report/codebook` — the
  // prefix trap that bit `Tab.from(path:)` on the Swift side does not arise.
  const _isAnalysis = useMatch("/report/analysis");
  const _isAnalysisSlash = useMatch("/report/analysis/");
  const isQuotes = _isQuotes || _isQuotesSlash;
  const isSessions = _isSessions || _isSessionsSlash;
  const isCodebook = _isCodebook || _isCodebookSlash;
  const isAnalysis = _isAnalysis || _isAnalysisSlash;
  const isSessionsRoute = !!(isSessions || isTranscript);
  // Embedded (macOS) removes the Sessions lens's left panel — the native
  // session-switcher popover replaces it (design-sessions-popover-navigation.md).
  // ONLY Sessions: the Quotes TOC, codebook and signals panels keep their
  // panels on both platforms. Gate `showSidebar` (→ SidebarLayout `active`),
  // NOT just the leftPanel prop — `{leftPanel ?? <TocSidebar/>}` means a bare
  // undefined would render the *Quotes* contents panel on the Sessions lens.
  const embeddedSessionsPanelRemoved = isEmbedded() && isSessionsRoute;
  const showSidebar = !!(
    (isQuotes || isSessionsRoute || isCodebook || isAnalysis) &&
    !embeddedSessionsPanelRemoved
  );
  const toggleExport = useCallback(() => setExportOpen((prev) => !prev), []);
  const toggleMiro = useCallback(() => setMiroOpen((prev) => !prev), []);
  const navigate = useNavigate();
  const activityJobs = useActivityJobs();

  // ── Embedded mode: hooks must be called before effects that use them ──
  const embedded = isEmbedded();
  const location = useLocation();
  const { focusedId, selectedIds } = useFocus();

  // Refs for bridge getState() — reads must be live, not stale closures.
  const focusedIdBridgeRef = useRef(focusedId);
  focusedIdBridgeRef.current = focusedId;
  const selectedIdsBridgeRef = useRef(selectedIds);
  selectedIdsBridgeRef.current = selectedIds;
  const locationBridgeRef = useRef(location);
  locationBridgeRef.current = location;

  // Live export scope counts → native popover (All / Selected / Starred).
  // useQuoteCounts() returns a stable {total,starred} ref unless those change,
  // so the shell doesn't re-render on unrelated store mutations (tag/edit/search).
  const { total: totalQuoteCount, starred: starredQuoteCount } = useQuoteCounts();
  const selectedQuoteCount = selectedIds.size;
  useEffect(() => {
    if (!embedded) return;
    postExportCounts(totalQuoteCount, selectedQuoteCount, starredQuoteCount);
  }, [embedded, totalQuoteCount, selectedQuoteCount, starredQuoteCount]);

  // Push the focused quote to native so the Quotes menu's focus-gated items
  // (Add Tag, Reveal in Transcript) enable exactly when a quote is focused —
  // the native `focusedQuoteId` has no other writer, so without this it stays
  // nil and those items are permanently dimmed. Fires only when focus changes.
  useEffect(() => {
    if (!embedded) return;
    postFocusChange(focusedId);
  }, [embedded, focusedId]);

  // Mirror Focus Mode to the native View menu's checkmark. Keyed on the state,
  // so it also fires on mount — which is the re-sync after a project switch or
  // the post-run reload, both of which reset Focus to off without telling the
  // menu. See postFocusMode's doc comment.
  const focusModeActive = useFocusMode();
  useEffect(() => {
    if (!embedded) return;
    postFocusMode(focusModeActive);
  }, [embedded, focusModeActive]);

  // Derived state for the native Quotes menu's adaptive labels. The Star
  // command targets the selection (or the focused quote); it *unstars* when
  // that target set is already all-starred — the same intent the click/`s`-key
  // path uses. Swift can't derive this (it has no per-quote starred map), so
  // the SPA computes it and pushes it. Keyed on the derived value, not counts:
  // swapping a starred selection for an unstarred one keeps the count but flips
  // the intent, which the export-counts channel would miss.
  const starredMap = useStarredMap();
  const lastTagName = useLastTagName();
  const starIsUnstar = useMemo(
    () => starActionIsUnstar(selectedIds, focusedId, starredMap),
    [selectedIds, focusedId, starredMap],
  );
  useEffect(() => {
    if (!embedded) return;
    postQuoteActionState(starIsUnstar, lastTagName);
  }, [embedded, starIsUnstar, lastTagName]);

  // Mirror the report's own panels to native so the View menu's three panel
  // rows can swap Hide↔Show. Swift owns no part of this state and can't derive
  // it, so without the mirror those rows read one-directional ("Show Tags"
  // while the tag sidebar is open). Keyed on the three booleans, not the store
  // objects: a width drag, a tag-eye toggle, or a solo-tag entry mutates
  // SidebarStore without changing what the menu says.
  const { tocMode, tagsOpen } = useSidebarStore();
  const { open: inspectorOpen } = useInspectorStore();
  // "overlay" is the transient hover-peek, and it can't occur embedded (the
  // rails that trigger it are hidden) — but it is open when it does, so treat
  // any non-closed mode as open rather than testing for "push".
  // On the embedded Sessions lens there IS no left panel (native popover
  // instead), so the store flag must not reach `panel-state` — otherwise the
  // View menu confidently offers "Hide Sessions" for a panel not on screen.
  const leftPanelOpen = tocMode !== "closed" && !embeddedSessionsPanelRemoved;
  useEffect(() => {
    if (!embedded) return;
    postPanelState(leftPanelOpen, tagsOpen, inspectorOpen);
  }, [embedded, leftPanelOpen, tagsOpen, inspectorOpen]);

  useEffect(() => {
    const exportData = getExportData();
    if (exportData) {
      setHealth(exportData.health);
      if (embedded) postReady();
      return;
    }
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data?.version) return;
        setHealth(data as HealthResponse);
        if (embedded) postReady();
      })
      .catch(() => {});
  }, [embedded]);

  // ? opens the keyboard-shortcuts docs page (in the shared named tab).
  const openShortcutsDocs = useCallback(() => openDocs(SHORTCUTS_DOCS_URL), []);

  useKeyboardShortcuts({
    helpModalOpen: false,
    onToggleHelp: openShortcutsDocs,
    settingsModalOpen: settingsOpen,
    onToggleSettings: toggleSettings,
  });

  // Install bridge namespace (once).
  useEffect(() => {
    if (!embedded) return;
    installBridge({
      getActiveTab: () => {
        const path = locationBridgeRef.current.pathname;
        if (path.startsWith("/report/quotes")) return "quotes";
        if (path.startsWith("/report/sessions")) return "sessions";
        if (path.startsWith("/report/codebook")) return "codebook";
        if (path.startsWith("/report/analysis")) return "analysis";
        return "project";
      },
      getFocusedQuoteId: () => focusedIdBridgeRef.current,
      getSelectedIds: () => Array.from(selectedIdsBridgeRef.current),
      getIsEditing: () => isEditing(),
      getHasPlayer: getPlayerOpen,
      getPlayerPlaying: getPlayerPlaying,
    });
  }, [embedded]);

  // Post route changes to native for tab highlight sync.
  useEffect(() => {
    if (!embedded) return;
    postRouteChange(location.pathname);
  }, [embedded, location.pathname]);

  // Report where the reader is within the lens, so reopening the project lands
  // there rather than at the top. Lives here, not in the TOC sidebar, because
  // the TOC is only mounted when its panel is open — and a position is worth
  // remembering whether or not the reader has that panel showing.
  useAnchorReporter(location.pathname, embedded);

  // Announce tab navigation to screen readers.
  const isFirstRender = useRef(true);
  useEffect(() => {
    // Skip the initial mount — only announce user-initiated navigations.
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const path = location.pathname;
    let key = "nav.project";
    if (path.startsWith("/report/quotes")) key = "nav.quotes";
    else if (path.startsWith("/report/sessions/s")) key = "announce.transcript";
    else if (path.startsWith("/report/sessions")) key = "nav.sessions";
    // v2 deliberately shares `nav.codebook`: it IS the codebook lens, so the
    // announcement is accurate, and a dedicated key would oblige a translation
    // in all 21 locales for a screen-reader string on an experimental surface.
    // Revisit if v2 replaces v1 under its own name.
    else if (path.startsWith("/report/codebook")) key = "nav.codebook";
    else if (path.startsWith("/report/analysis")) key = "nav.analysis";
    announce(i18n.t("announce.navigatedTo", { label: i18n.t(key) }));
  }, [location.pathname]);

  // Handle menu actions from native toolbar/menu (embedded mode).
  useEffect(() => {
    if (!embedded) return;
    const focusSearchInput = () => {
      const input = document.querySelector<HTMLInputElement>(".search-input");
      if (input) {
        const container = input.closest(".search-container");
        if (container && !container.classList.contains("expanded")) {
          container.classList.add("expanded");
        }
        input.focus();
        input.select();
      }
    };

    const handler = (e: Event) => {
      const { action, payload } = (e as CustomEvent).detail;
      switch (action) {
        case "toggleLeftPanel":
          sidebarAnimations.toggleToc();
          break;
        case "toggleRightPanel":
          sidebarAnimations.toggleTags();
          break;
        // Explicit, not a toggle: native decides the direction because it also
        // owns the projects column. A toggle here would disagree with it
        // whenever the column and the web panels were in different states.
        case "hideAllSidebars":
          sidebarAnimations.hideAll();
          break;
        case "showAllSidebars":
          sidebarAnimations.showAll();
          break;
        case "toggleInspectorPanel":
          toggleInspector();
          break;
        case "find":
          focusSearchInput();
          break;
        case "setSearchQuery": {
          // Native macOS search field → store (live as the user types). In
          // embedded mode the native field is the sole search input; the web
          // SearchBox isn't rendered, so this drives filtering directly.
          const text = (payload as { text?: string } | undefined)?.text ?? "";
          setSearchQuery(text);
          break;
        }
        case "useSelectionForFind": {
          const sel = window.getSelection()?.toString().trim() ?? "";
          if (sel) {
            setSearchQuery(sel);
            postFindPasteboardWrite(sel);
          }
          focusSearchInput();
          break;
        }
        case "findNext":
        case "findPrevious": {
          const text = (payload as { text?: string } | undefined)?.text ?? "";
          if (text) setSearchQuery(text);
          focusSearchInput();
          break;
        }
        case "jumpToSelection":
          // Native WKWebView handles scroll-to-selection; no-op on web side.
          break;

        // ── Tier 2: export, filter, help, zoom, dark mode ──────────────
        case "exportReport": {
          // Global Anonymise toggle (macOS menu) rides the payload; the web
          // dropdown sends no payload and surfaces anonymise via the modal.
          const anon = (payload as { anonymise?: boolean } | undefined)?.anonymise ?? false;
          if (isEmbeddedDesktop()) {
            triggerReportDownload(anon);
          } else {
            setExportAnonymise(anon);
            setExportOpen(true);
          }
          break;
        }
        case "sendToMiro":
          // Modal action, like exportReport — opens the Miro export panel.
          // Dispatched by the macOS native menu for parity with the web dropdown.
          setMiroOpen(true);
          break;
        case "copyAsCSV": {
          const snap2 = getQuotesSnapshot();
          const focused = focusedIdBridgeRef.current;
          const selected = selectedIdsBridgeRef.current;
          const ids = selected.size > 0 ? Array.from(selected) : focused ? [focused] : null;
          if (!ids || ids.length === 0) {
            toast(i18n.t("toolbar.noQuotesSelected"));
            break;
          }
          const csv2 = buildCsvString(ids, snap2);
          navigator.clipboard
            .writeText(csv2)
            .then(() => toast(i18n.t("toolbar.csvCopied", { count: ids.length })))
            .catch(() => toast(i18n.t("toolbar.csvFailed")));
          break;
        }
        // ── Canonical quote-export actions (shared with the SPA dropdown via
        //    utils/exportActions, so the macOS native menu and web behave
        //    identically). Selection → focused → all quotes. ──────────────
        case "copyQuotes": {
          const snap = getQuotesSnapshot();
          const p = payload as
            | { anonymise?: boolean; scope?: "all" | "selected" | "starred" }
            | undefined;
          const anon = p?.anonymise ?? false;
          // Scopes operate within the *visible* set ("all" = quotes on screen,
          // excluding hidden/filtered). "selected" uses the live selection;
          // "starred" = visible & starred. Default (no scope) = all visible.
          const visible = getVisibleQuotes(snap);
          let ids: string[];
          if (p?.scope === "selected") ids = Array.from(selectedIdsBridgeRef.current);
          else if (p?.scope === "starred")
            ids = visible.filter((q) => snap.starred[q.dom_id]).map((q) => q.dom_id);
          else ids = visible.map((q) => q.dom_id);
          void copyQuotesToClipboard(snap, ids, i18n.t, anon);
          break;
        }
        case "saveSpreadsheet": {
          // Spreadsheet exports everything on screen (all visible quotes), not
          // the current selection — the rich sheet is the full-dataset export.
          const snap = getQuotesSnapshot();
          const p = payload as { anonymise?: boolean; format?: "csv" | "xlsx" } | undefined;
          const anon = p?.anonymise ?? false;
          const format = p?.format === "csv" ? "csv" : "xlsx";
          const ids = getVisibleQuotes(snap).map((q) => q.dom_id);
          saveQuotesSpreadsheet(projectId, ids, i18n.t, anon, format);
          break;
        }
        case "extractClips": {
          // Native menu has no clip scope submenu yet — pass null for the
          // legacy union. When the native submenu lands it will carry a scope
          // like copyQuotes above and hand over an explicit id set here.
          const anon = (payload as { anonymise?: boolean } | undefined)?.anonymise ?? false;
          void extractVideoClips(null, i18n.t, anon);
          break;
        }
        case "allQuotes":
          // Explicit "All Quotes" command — full reset (search + tags + mode).
          setSearchQuery("");
          setTagFilter(EMPTY_TAG_FILTER);
          setViewMode("all");
          break;
        case "showAllQuotes":
          // Star toggle off — view mode only, preserves a typed search query
          // (star and search are orthogonal filters that compose).
          setViewMode("all");
          break;
        case "starredQuotesOnly":
          setViewMode("starred");
          break;
        // showHelp / showKeyboardShortcuts / showAcknowledgements / showReleaseNotes
        // are handled natively now (the Help menu opens external docs directly) —
        // no SPA case needed. The browser SPA reaches docs via the ? key / footer Help.
        case "sendFeedback":
          setFeedbackOpen(true);
          break;
        case "openBlog":
          window.open("https://blog.bristlenose.app", "_blank");
          break;
        case "focusMode":
          // Report-wide view state — no FocusContext/QuotesContext closure
          // needed, so AppLayout is the right listener per the menu-action
          // cookbook in desktop/CLAUDE.md. Native mirrors the result back via
          // the `focus-mode` bridge post below.
          toggleFocusMode();
          break;
        case "zoomIn":
          applyZoom(getZoom() + ZOOM_STEP);
          break;
        case "zoomOut":
          applyZoom(getZoom() - ZOOM_STEP);
          break;
        case "actualSize":
          applyZoom(1);
          break;

        // ── Codebook operations ─────────────────────────────────────────
        case "browseCodebooks":
          window.dispatchEvent(new CustomEvent("bn:codebook-browse"));
          break;
        case "importFramework": {
          const templateId = (payload as { templateId?: string } | undefined)?.templateId;
          window.dispatchEvent(
            new CustomEvent("bn:codebook-browse", templateId ? { detail: { templateId } } : undefined),
          );
          break;
        }
        case "removeFramework": {
          const frameworkId = (payload as { frameworkId?: string } | undefined)?.frameworkId;
          if (frameworkId) {
            window.dispatchEvent(
              new CustomEvent("bn:codebook-remove", { detail: { frameworkId } }),
            );
          }
          break;
        }
        case "createCodeGroup":
          window.dispatchEvent(new CustomEvent("bn:codebook-create-group"));
          break;
        case "createCode":
          window.dispatchEvent(new CustomEvent("bn:codebook-create-code"));
          break;
        case "toggleCodeGroup":
        case "renameCodeGroup":
        case "deleteCodeGroup":
        case "renameCode":
        case "deleteCode":
          // Needs focused group/code context from native sidebar (not yet built).
          console.warn(`[bn:menu-action] "${action}" requires native focus context — not yet wired`);
          break;
        case "openSpecimen":
          // Debug lens (Diagnostics menu, DEBUG harness) — the specimen page
          // has no native sidebar row, so the menu navigates the SPA directly.
          navigate("/report/specimen");
          break;
      }
    };
    window.addEventListener("bn:menu-action", handler);
    return () => window.removeEventListener("bn:menu-action", handler);
  }, [embedded, navigate]);

  const chipJobs: ActivityJob[] = useMemo(
    () =>
      Array.from(activityJobs.entries()).map(([id, j]) => {
        if (j.type === "clips") {
          return {
            id,
            label: i18n.t("export.clips.progress", { progress: 0, total: j.total ?? 0 }),
            completedLabel: i18n.t("export.clips.done", { count: j.total ?? 0 }),
            frameworkId: "",
            onComplete: () => {
              // no-op — reveal is the action
            },
            onAction: () => {
              revealClips().catch((err) =>
                console.error("Reveal clips failed:", err),
              );
            },
            actionLabel: i18n.t("export.clips.reveal"),
            onCancel: () => {
              cancelClipExtraction().catch((err) =>
                console.error("Cancel clip extraction failed:", err),
              );
            },
            pollFn: async (): Promise<NormalisedJobStatus> => {
              const s = await getClipExtractionStatus();
              const status = s.status === "idle" ? "running" : s.status;
              return {
                status: status as "running" | "completed" | "failed" | "cancelled",
                progressLabel: status === "running" ? `${s.progress}/${s.total}` : null,
                durationLabel: null,
                errorMessage: status === "failed" ? i18n.t("export.clips.failed") : null,
                // Clip extraction has no partial outcome — a clip is produced
                // or it is not.
                partialMessage: null,
              };
            },
          };
        }
        if (j.type === "catchup") {
          // On-enable catch-up delta. Numberless by design: the AutoCodeJob's
          // counts are cumulative, not the delta being coded, so showing them would
          // mislead (§4a). Spinner → ✓, then refresh so the new tags appear.
          return {
            id,
            label: i18n.t("autocode.chip.recoding", {
              title: j.frameworkTitle,
              defaultValue: "Re-coding new sessions for {{title}}…",
            }),
            completedLabel: i18n.t("autocode.chip.recoded", {
              title: j.frameworkTitle,
              defaultValue: "Re-coded new sessions for {{title}}",
            }),
            frameworkId: j.frameworkId,
            onComplete: () => {
              window.dispatchEvent(new Event("codebook-changed"));
              document.dispatchEvent(new CustomEvent("bn:tags-changed"));
            },
            pollFn: async (): Promise<NormalisedJobStatus> => {
              // The shared normaliser, not a third local copy: this one still
              // interpolated raw `error_message` (the leak e2cb193d fixed in the
              // other two call sites) and would have needed its own partial
              // branch to avoid reintroducing the shortfall bug one file over.
              return normaliseAutoCode(await getAutoCodeStatus(j.frameworkId));
            },
          };
        }
        // Default: autocode job
        return {
          id,
          label: i18n.t("autocode.chip.coding", { title: j.frameworkTitle }),
          completedLabel: i18n.t("autocode.chip.coded", { title: j.frameworkTitle }),
          frameworkId: j.frameworkId,
          onComplete: () => {
            window.dispatchEvent(new Event("codebook-changed"));
          },
          onAction: () => {
            const detail = { frameworkId: j.frameworkId, frameworkTitle: j.frameworkTitle };
            // Two codebook lenses run side by side (D29). Dispatch in place if
            // we are already on EITHER — both listen for `bn:autocode-report`.
            // Otherwise return to the lens this job was started from, not to
            // whichever one is hardcoded: a researcher who installed from v2
            // and clicked View Report used to land in v1, a different lens from
            // the one they were working in, with nothing saying so.
            if (isCodebook) {
              window.dispatchEvent(new CustomEvent("bn:autocode-report", { detail }));
            } else {
              navigate(j.originRoute ?? "/report/codebook");
              setTimeout(() => {
                window.dispatchEvent(new CustomEvent("bn:autocode-report", { detail }));
              }, 100);
            }
          },
          actionLabel: i18n.t("codebook.viewReport"),
          actionHref: j.originRoute ?? "/report/codebook",
          onCancel: () => {
            cancelAutoCode(j.frameworkId).catch((err) =>
              console.error("Cancel AutoCode failed:", err),
            );
          },
        };
      }),
    [activityJobs, isCodebook, navigate],
  );

  return (
    <SidebarLayout
      active={showSidebar}
      leftPanel={
        // The embedded gate repeats here (belt to showSidebar's braces) so
        // SessionsSidebar never MOUNTS on the embedded Sessions lens — its
        // useEffect fetch would otherwise still fire behind an inactive layout.
        isSessionsRoute && !embeddedSessionsPanelRemoved ? <SessionsSidebar /> : isCodebook ? <CodebookV2Sidebar /> : isAnalysis ? <AnalysisSidebar /> : undefined
      }
      leftPanelTitle={
        // Codebooks dropped its title 14 Aug 2026, alongside Quotes' "Contents"
        // (SidebarLayout renders the header only when a title is passed). To
        // restore, put the branch back: isCodebook ? i18n.t("codebook.heading") :
        isSessionsRoute && !embeddedSessionsPanelRemoved ? i18n.t("nav.sessions") : isAnalysis ? i18n.t("analysis.signals") : undefined
      }
      showRightSidebar={!!isQuotes}
    >
      {!embedded && <Header />}
      {!embedded && <NavBar onExportReport={toggleExport} onSendToMiro={toggleMiro} onSettings={toggleSettings} onHelp={() => openDocs(DOCS_URL)} />}
      <main className="bn-main">
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      </main>
      {!embedded && (
        <Footer
          health={health}
          onOpenFeedback={openFeedback}
          onToggleHelp={() => openDocs(DOCS_URL)}
        />
      )}
      <FeedbackModal open={feedbackOpen} onClose={closeFeedback} health={health} />
      <ExportDialog open={exportOpen} onClose={toggleExport} initialAnonymise={exportAnonymise} />
      <MiroExportPanel open={miroOpen} onClose={toggleMiro} />
      <SettingsModal open={settingsOpen} onClose={toggleSettings} />
      <ActivityChipStack jobs={chipJobs} onDismiss={removeJob} />
      <AnnounceRegion />
      <LensSubtitleSync />
      {IS_DEV && (
        <Suspense fallback={null}>
          <PlaygroundHUD />
          <ResponsivePlayground />
        </Suspense>
      )}
    </SidebarLayout>
  );
}

export function AppLayout() {
  const navigate = useNavigate();
  const scrollToAnchor = useScrollToAnchor();

  useEffect(() => {
    installNavigationShims(navigate, scrollToAnchor);
  }, [navigate, scrollToAnchor]);

  // Dim selection when window is inactive (macOS convention).
  useEffect(() => {
    const cl = document.documentElement.classList;
    const onBlur = () => cl.add("bn-window-inactive");
    const onFocus = () => cl.remove("bn-window-inactive");
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    return () => {
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      cl.remove("bn-window-inactive");
    };
  }, []);

  return (
    <PlayerProvider>
      <FocusProvider>
        <AppShell />
      </FocusProvider>
    </PlayerProvider>
  );
}
