/**
 * AppLayout — top-level layout for the report SPA.
 *
 * Renders Header, NavBar, Outlet, and Footer.  Installs backward-compat
 * navigation shims on window for vanilla JS modules.  Provides
 * FocusProvider (keyboard focus/selection) and installs global keyboard
 * shortcuts via useKeyboardShortcuts.
 */

import { useCallback, useEffect, useMemo, useState, lazy, Suspense } from "react";
import { Outlet, useNavigate, useMatch } from "react-router-dom";
import { Header } from "../components/Header";
import { NavBar } from "../components/NavBar";
import { Footer } from "../components/Footer";
import { HelpModal } from "../components/HelpModal";
import { FeedbackModal } from "../components/FeedbackModal";
import { SettingsModal } from "../components/SettingsModal";
import { SidebarLayout } from "../components/SidebarLayout";
import { SessionsSidebar } from "../components/SessionsSidebar";
import { CodebookSidebar } from "../components/CodebookSidebar";
import { ExportDialog } from "../components/ExportDialog";
import { ActivityChipStack } from "../components/ActivityChipStack";
import type { ActivityJob } from "../components/ActivityChipStack";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider } from "../contexts/FocusContext";
import { useActivityJobs, removeJob } from "../contexts/ActivityStore";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";
import { cancelAutoCode } from "../utils/api";
import { getExportData } from "../utils/exportData";
import { DEFAULT_HEALTH_RESPONSE, type HealthResponse } from "../utils/health";

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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse>(DEFAULT_HEALTH_RESPONSE);
  const toggleHelp = useCallback(() => setHelpOpen((prev) => !prev), []);
  const openHelp = useCallback(() => {
    setHelpSection("help");
    setHelpOpen(true);
  }, []);
  const openFeedback = useCallback(() => setFeedbackOpen(true), []);
  const closeFeedback = useCallback(() => setFeedbackOpen(false), []);
  const toggleSettings = useCallback(() => setSettingsOpen((prev) => !prev), []);
  const _isQuotes = useMatch("/report/quotes");
  const _isQuotesSlash = useMatch("/report/quotes/");
  const _isSessions = useMatch("/report/sessions");
  const _isSessionsSlash = useMatch("/report/sessions/");
  const isTranscript = useMatch("/report/sessions/:sessionId");
  const _isCodebook = useMatch("/report/codebook");
  const _isCodebookSlash = useMatch("/report/codebook/");
  const isQuotes = _isQuotes || _isQuotesSlash;
  const isSessions = _isSessions || _isSessionsSlash;
  const isCodebook = _isCodebook || _isCodebookSlash;
  const showSidebar = !!(isQuotes || isSessions || isTranscript || isCodebook);
  const isSessionsRoute = !!(isSessions || isTranscript);
  const toggleExport = useCallback(() => setExportOpen((prev) => !prev), []);
  const navigate = useNavigate();
  const activityJobs = useActivityJobs();

  useEffect(() => {
    const exportData = getExportData();
    if (exportData) {
      setHealth(exportData.health);
      return;
    }
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data?.version) return;
        setHealth(data as HealthResponse);
      })
      .catch(() => {});
  }, []);

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

  const chipJobs: ActivityJob[] = useMemo(
    () =>
      Array.from(activityJobs.entries()).map(([id, j]) => ({
        id,
        label: `\u2726 AutoCoding ${j.frameworkTitle}`,
        completedLabel: `\u2726 AutoCoded ${j.frameworkTitle}`,
        frameworkId: j.frameworkId,
        onComplete: () => {
          window.dispatchEvent(new Event("codebook-changed"));
        },
        onAction: () => {
          const detail = { frameworkId: j.frameworkId, frameworkTitle: j.frameworkTitle };
          if (isCodebook) {
            // Already on codebook tab — open modal directly.
            window.dispatchEvent(new CustomEvent("bn:autocode-report", { detail }));
          } else {
            navigate("/report/codebook");
            // Defer so CodebookPanel has time to mount after navigation.
            setTimeout(() => {
              window.dispatchEvent(new CustomEvent("bn:autocode-report", { detail }));
            }, 100);
          }
        },
        actionLabel: "View Report",
        actionHref: "/report/codebook",
        onCancel: () => {
          cancelAutoCode(j.frameworkId).catch((err) =>
            console.error("Cancel AutoCode failed:", err),
          );
        },
      })),
    [activityJobs, isCodebook, navigate],
  );

  return (
    <SidebarLayout
      active={showSidebar}
      leftPanel={isSessionsRoute ? <SessionsSidebar /> : isCodebook ? <CodebookSidebar /> : undefined}
      leftPanelTitle={isSessionsRoute ? "Sessions" : isCodebook ? "Codebooks" : undefined}
      showRightSidebar={!!isQuotes}
    >
      <Header />
      <NavBar onExport={toggleExport} onSettings={toggleSettings} onHelp={openHelp} />
      <Outlet />
      <Footer
        health={health}
        onOpenFeedback={openFeedback}
        onToggleHelp={openHelp}
      />
      <FeedbackModal open={feedbackOpen} onClose={closeFeedback} health={health} />
      <HelpModal open={helpOpen} onClose={toggleHelp} initialSection={helpSection} health={health} />
      <ExportDialog open={exportOpen} onClose={toggleExport} />
      <SettingsModal open={settingsOpen} onClose={toggleSettings} />
      <ActivityChipStack jobs={chipJobs} onDismiss={removeJob} />
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

  return (
    <PlayerProvider>
      <FocusProvider>
        <AppShell />
      </FocusProvider>
    </PlayerProvider>
  );
}
