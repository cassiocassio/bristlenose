/**
 * AppLayout — top-level layout for the report SPA.
 *
 * Renders Header, NavBar, Outlet, and Footer.  Installs backward-compat
 * navigation shims on window for vanilla JS modules.  Provides
 * FocusProvider (keyboard focus/selection) and installs global keyboard
 * shortcuts via useKeyboardShortcuts.
 */

import { useCallback, useEffect, useState, lazy, Suspense } from "react";
import { Outlet, useNavigate, useMatch } from "react-router-dom";
import { Header } from "../components/Header";
import { NavBar } from "../components/NavBar";
import { Footer } from "../components/Footer";
import { HelpModal } from "../components/HelpModal";
import { FeedbackModal } from "../components/FeedbackModal";
import { SidebarLayout } from "../components/SidebarLayout";
import { SessionsSidebar } from "../components/SessionsSidebar";
import { ExportDialog } from "../components/ExportDialog";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider } from "../contexts/FocusContext";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";
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
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse>(DEFAULT_HEALTH_RESPONSE);
  const toggleHelp = useCallback(() => setHelpOpen((prev) => !prev), []);
  const openFeedback = useCallback(() => setFeedbackOpen(true), []);
  const closeFeedback = useCallback(() => setFeedbackOpen(false), []);
  const isQuotes = useMatch("/report/quotes");
  const isSessions = useMatch("/report/sessions");
  const isTranscript = useMatch("/report/sessions/:sessionId");
  const showSidebar = !!(isQuotes || isSessions || isTranscript);
  const isSessionsRoute = !!(isSessions || isTranscript);
  const toggleExport = useCallback(() => setExportOpen((prev) => !prev), []);

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

  useKeyboardShortcuts({
    helpModalOpen: helpOpen,
    onToggleHelp: toggleHelp,
  });

  return (
    <SidebarLayout
      active={showSidebar}
      leftPanel={isSessionsRoute ? <SessionsSidebar /> : undefined}
      leftPanelTitle={isSessionsRoute ? "Sessions" : undefined}
      showRightSidebar={!!isQuotes}
    >
      <Header />
      <NavBar onExport={toggleExport} />
      <Outlet />
      <Footer
        health={health}
        onOpenFeedback={openFeedback}
        onToggleHelp={toggleHelp}
      />
      <FeedbackModal open={feedbackOpen} onClose={closeFeedback} health={health} />
      <HelpModal open={helpOpen} onClose={toggleHelp} />
      <ExportDialog open={exportOpen} onClose={toggleExport} />
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
