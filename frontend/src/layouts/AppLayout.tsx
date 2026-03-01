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
import { SidebarLayout } from "../components/SidebarLayout";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider } from "../contexts/FocusContext";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";

/**
 * Inner component that uses hooks requiring PlayerProvider + FocusProvider.
 */
function AppShell() {
  const [helpOpen, setHelpOpen] = useState(false);
  const toggleHelp = useCallback(() => setHelpOpen((prev) => !prev), []);
  const isQuotes = useMatch("/report/quotes");

  useKeyboardShortcuts({
    helpModalOpen: helpOpen,
    onToggleHelp: toggleHelp,
  });

  return (
    <SidebarLayout active={!!isQuotes}>
      <Header />
      <NavBar />
      <Outlet />
      <Footer onToggleHelp={toggleHelp} />
      <HelpModal open={helpOpen} onClose={toggleHelp} />
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
