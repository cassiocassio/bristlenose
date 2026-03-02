/**
 * AppLayout — top-level layout for the report SPA.
 *
 * Renders Header, NavBar, Outlet, and Footer.  Installs backward-compat
 * navigation shims on window for vanilla JS modules.  Provides
 * FocusProvider (keyboard focus/selection) and installs global keyboard
 * shortcuts via useKeyboardShortcuts.
 */

import { useCallback, useEffect, useState } from "react";
import { Outlet, useNavigate, useMatch } from "react-router-dom";
import { Header } from "../components/Header";
import { NavBar } from "../components/NavBar";
import { Footer } from "../components/Footer";
import { HelpModal } from "../components/HelpModal";
import { FeedbackModal } from "../components/FeedbackModal";
import { SidebarLayout } from "../components/SidebarLayout";
import { ExportDialog } from "../components/ExportDialog";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider } from "../contexts/FocusContext";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";
import { getExportData } from "../utils/exportData";
import { DEFAULT_HEALTH_RESPONSE, type HealthResponse } from "../utils/health";

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
    <SidebarLayout active={!!isQuotes}>
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
