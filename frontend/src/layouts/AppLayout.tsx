/**
 * AppLayout — top-level layout for the report SPA.
 *
 * Renders the NavBar and an Outlet for the active route. Installs
 * backward-compat navigation shims on window for vanilla JS modules.
 * Provides FocusProvider (keyboard focus/selection) and installs
 * global keyboard shortcuts via useKeyboardShortcuts.
 */

import { useCallback, useEffect, useState } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { HelpModal } from "../components/HelpModal";
import { PlayerProvider } from "../contexts/PlayerContext";
import { FocusProvider } from "../contexts/FocusContext";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";

/**
 * Inner component that uses hooks requiring PlayerProvider + FocusProvider.
 */
function KeyboardShortcutsManager({ children }: { children: React.ReactNode }) {
  const [helpOpen, setHelpOpen] = useState(false);
  const toggleHelp = useCallback(() => setHelpOpen((prev) => !prev), []);

  useKeyboardShortcuts({
    helpModalOpen: helpOpen,
    onToggleHelp: toggleHelp,
  });

  return (
    <>
      {children}
      <HelpModal open={helpOpen} onClose={toggleHelp} />
    </>
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
        <KeyboardShortcutsManager>
          <NavBar />
          <Outlet />
        </KeyboardShortcutsManager>
      </FocusProvider>
    </PlayerProvider>
  );
}
