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
import { HelpModal } from "../components/HelpModal";
import { FeedbackModal } from "../components/FeedbackModal";
import { SettingsModal } from "../components/SettingsModal";
import { SidebarLayout, sidebarAnimations } from "../components/SidebarLayout";
import { SessionsSidebar } from "../components/SessionsSidebar";
import { CodebookSidebar } from "../components/CodebookSidebar";
import { AnalysisSidebar } from "../components/AnalysisSidebar";
import { ExportDialog } from "../components/ExportDialog";
import { ActivityChipStack } from "../components/ActivityChipStack";
import type { ActivityJob } from "../components/ActivityChipStack";
import { AnnounceRegion } from "../components/AnnounceRegion";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider, useFocus } from "../contexts/FocusContext";
import { useActivityJobs, removeJob } from "../contexts/ActivityStore";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";
import {
  installBridge,
  postRouteChange,
  postReady,
  postProjectAction,
  postFindPasteboardWrite,
} from "../shims/bridge";
import { getPlayerOpen, getPlayerPlaying } from "../contexts/PlayerContext";
import { cancelAutoCode, getClipExtractionStatus, revealClips } from "../utils/api";
import type { NormalisedJobStatus } from "../components/ActivityChipStack";
import { toggleInspector } from "../contexts/InspectorStore";
import { setSearchQuery, setViewMode, setTagFilter, getQuotesSnapshot } from "../contexts/QuotesContext";
import { EMPTY_TAG_FILTER } from "../utils/filter";
import { toast } from "../utils/toast";
import { announce } from "../utils/announce";
import i18n from "../i18n";
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

function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
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

// ── Dark mode toggle (mirrors SettingsModal logic) ───────────────────────

const APPEARANCE_KEY = "bristlenose-appearance";

function toggleDarkMode(): void {
  const root = document.documentElement;
  const current = root.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  root.setAttribute("data-theme", next);
  root.style.colorScheme = next;
  try { localStorage.setItem(APPEARANCE_KEY, JSON.stringify(next)); } catch { /* */ }
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

/**
 * Inner component that uses hooks requiring PlayerProvider + FocusProvider.
 */
function AppShell() {
  const [helpOpen, setHelpOpen] = useState(false);
  const [helpSection, setHelpSection] = useState<string>("help");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportAnonymise, setExportAnonymise] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse>(DEFAULT_HEALTH_RESPONSE);
  const toggleHelp = useCallback(() => setHelpOpen((prev) => !prev), []);
  const openHelp = useCallback(() => {
    setHelpSection("help");
    setHelpOpen(true);
  }, []);
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
  const _isAnalysis = useMatch("/report/analysis");
  const _isAnalysisSlash = useMatch("/report/analysis/");
  const isQuotes = _isQuotes || _isQuotesSlash;
  const isSessions = _isSessions || _isSessionsSlash;
  const isCodebook = _isCodebook || _isCodebookSlash;
  const isAnalysis = _isAnalysis || _isAnalysisSlash;
  const showSidebar = !!(isQuotes || isSessions || isTranscript || isCodebook || isAnalysis);
  const isSessionsRoute = !!(isSessions || isTranscript);
  const toggleExport = useCallback(() => setExportOpen((prev) => !prev), []);
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

  const toggleHelpShortcuts = useCallback(() => {
    setHelpSection("shortcuts");
    setHelpOpen((prev) => !prev);
  }, []);

  useKeyboardShortcuts({
    helpModalOpen: helpOpen,
    onToggleHelp: toggleHelpShortcuts,
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
        case "toggleInspectorPanel":
          toggleInspector();
          break;
        case "find":
          focusSearchInput();
          break;
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
        case "exportReport":
          setExportAnonymise(false);
          setExportOpen(true);
          break;
        case "exportAnonymised":
          setExportAnonymise(true);
          setExportOpen(true);
          break;
        case "exportQuotesCSV": {
          const snap = getQuotesSnapshot();
          const csv = buildCsvString(null, snap);
          const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "bristlenose-quotes.csv";
          a.click();
          URL.revokeObjectURL(url);
          toast(i18n.t("toolbar.quotesExported", { count: snap.quotes.length }));
          break;
        }
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
        case "allQuotes":
          setSearchQuery("");
          setTagFilter(EMPTY_TAG_FILTER);
          setViewMode("all");
          break;
        case "starredQuotesOnly":
          setViewMode("starred");
          break;
        case "filterByTag": {
          const btn = document.querySelector<HTMLButtonElement>(
            '[data-testid="bn-toolbar-tag-filter"] button',
          );
          if (btn) btn.click();
          break;
        }
        case "showHelp":
          setHelpSection("help");
          setHelpOpen(true);
          break;
        case "showKeyboardShortcuts":
          setHelpSection("shortcuts");
          setHelpOpen(true);
          break;
        case "showReleaseNotes":
          window.open(
            "https://github.com/cassiocassio/bristlenose/blob/main/CHANGELOG.md",
            "_blank",
          );
          break;
        case "sendFeedback":
          setFeedbackOpen(true);
          break;
        case "openBlog":
          window.open("https://bristlenose.substack.com", "_blank");
          break;
        case "showAcknowledgements":
          setHelpSection("acknowledgements");
          setHelpOpen(true);
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
        case "toggleDarkMode":
          toggleDarkMode();
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
      }
    };
    window.addEventListener("bn:menu-action", handler);
    return () => window.removeEventListener("bn:menu-action", handler);
  }, [embedded]);

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
            pollFn: async (): Promise<NormalisedJobStatus> => {
              const s = await getClipExtractionStatus();
              const status = s.status === "idle" ? "running" : s.status;
              return {
                status: status as "running" | "completed" | "failed",
                progressLabel: status === "running" ? `${s.progress}/${s.total}` : null,
                durationLabel: null,
                errorMessage: status === "failed" ? i18n.t("export.clips.failed") : null,
              };
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
            if (isCodebook) {
              window.dispatchEvent(new CustomEvent("bn:autocode-report", { detail }));
            } else {
              navigate("/report/codebook");
              setTimeout(() => {
                window.dispatchEvent(new CustomEvent("bn:autocode-report", { detail }));
              }, 100);
            }
          },
          actionLabel: i18n.t("codebook.viewReport"),
          actionHref: "/report/codebook",
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
      leftPanel={isSessionsRoute ? <SessionsSidebar /> : isCodebook ? <CodebookSidebar /> : isAnalysis ? <AnalysisSidebar /> : undefined}
      leftPanelTitle={isSessionsRoute ? i18n.t("nav.sessions") : isCodebook ? i18n.t("codebook.heading") : isAnalysis ? i18n.t("analysis.signals") : undefined}
      showRightSidebar={!!isQuotes}
    >
      {!embedded && <Header />}
      {!embedded && <NavBar onExportReport={toggleExport} onSettings={toggleSettings} onHelp={openHelp} />}
      <Outlet />
      {!embedded && (
        <Footer
          health={health}
          onOpenFeedback={openFeedback}
          onToggleHelp={openHelp}
        />
      )}
      <FeedbackModal open={feedbackOpen} onClose={closeFeedback} health={health} />
      <HelpModal open={helpOpen} onClose={toggleHelp} initialSection={helpSection} health={health} />
      <ExportDialog open={exportOpen} onClose={toggleExport} initialAnonymise={exportAnonymise} />
      <SettingsModal open={settingsOpen} onClose={toggleSettings} />
      <ActivityChipStack jobs={chipJobs} onDismiss={removeJob} />
      <AnnounceRegion />
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
