/**
 * HelpModal — sidebar-nav modal with help, shortcuts, and reference sections.
 *
 * Replaces the old keyboard-shortcut-only overlay with a ModalNav-based
 * version that combines help, shortcuts, signals, codebook, and about
 * into a single navigable surface.
 *
 * CSS: organisms/modal-nav.css (layout), molecules/help-overlay.css (sizing + kbd).
 *
 * @module HelpModal
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ModalNav, type NavItem } from "./ModalNav";
import {
  HelpSection,
  ShortcutsSection,
  SignalsSection,
  CodebookSection,
  DeveloperSection,
  DesignSection,
  ContributingSection,
} from "./about";
import type { DevInfoResponse } from "./about";
import type { HealthResponse } from "../utils/health";
import { isExportMode } from "../utils/exportData";

// ── Navigation structure ──────────────────────────────────────────────────

const NAV_ITEMS: NavItem[] = [
  { id: "help", label: "Help" },
  { id: "shortcuts", label: "Shortcuts" },
  { id: "signals", label: "Signals" },
  { id: "codebook", label: "Codebook" },
  {
    id: "about",
    label: "About",
    children: [
      { id: "developer", label: "Developer" },
      { id: "design", label: "Design" },
      { id: "contributing", label: "Contributing" },
    ],
  },
];

// ── Component ─────────────────────────────────────────────────────────────

interface HelpModalProps {
  open: boolean;
  onClose: () => void;
  /** Which section to show when the modal opens. "help" for navbar, "shortcuts" for ? key. */
  initialSection?: string;
  /** Health data from AppLayout — avoids a duplicate fetch. */
  health: HealthResponse;
}

export function HelpModal({
  open,
  onClose,
  initialSection = "help",
  health: _health,
}: HelpModalProps) {
  // _health reserved for version display in HelpSection (next iteration).
  void _health;
  const [activeId, setActiveId] = useState(initialSection);
  const [devInfo, setDevInfo] = useState<DevInfoResponse | null>(null);
  const devInfoFetched = useRef(false);

  // Reset activeId to initialSection on each open (false→true transition).
  const prevOpen = useRef(open);
  useEffect(() => {
    if (open && !prevOpen.current) {
      setActiveId(initialSection);
    }
    prevOpen.current = open;
  }, [open, initialSection]);

  // Lazy-fetch /api/dev/info on first open (dev mode only).
  useEffect(() => {
    if (!open || devInfoFetched.current || isExportMode()) return;
    devInfoFetched.current = true;
    fetch("/api/dev/info")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setDevInfo(data as DevInfoResponse);
      })
      .catch(() => {});
  }, [open]);

  const handleSelect = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  // Render the content for the active section.
  let content: React.ReactNode;
  switch (activeId) {
    case "help":
      content = <HelpSection />;
      break;
    case "shortcuts":
      content = <ShortcutsSection />;
      break;
    case "signals":
      content = <SignalsSection />;
      break;
    case "codebook":
      content = <CodebookSection />;
      break;
    case "developer":
      content = <DeveloperSection info={devInfo} />;
      break;
    case "design":
      content = <DesignSection sections={devInfo?.design_sections} />;
      break;
    case "contributing":
      content = <ContributingSection />;
      break;
    default:
      content = null;
  }

  return (
    <ModalNav
      open={open}
      onClose={onClose}
      title="Help"
      items={NAV_ITEMS}
      activeId={activeId}
      onSelect={handleSelect}
      className="help-modal"
      testId="bn-help-overlay"
      titleId="help-modal-title"
    >
      {content}
    </ModalNav>
  );
}
