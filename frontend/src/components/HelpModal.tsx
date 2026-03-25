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

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ModalNav, type NavItem } from "./ModalNav";
import {
  HelpSection,
  ShortcutsSection,
  SignalsSection,
  CodebookSection,
  PrivacySection,
  DeveloperSection,
  DesignSection,
  ContributingSection,
  AcknowledgementsSection,
} from "./about";
import type { DevInfoResponse } from "./about";
import type { HealthResponse } from "../utils/health";
import { isExportMode } from "../utils/exportData";

// ── Navigation structure (built inside component for i18n) ───────────────

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
  const { t, i18n } = useTranslation();
  // _health reserved for version display in HelpSection (next iteration).
  void _health;
  const [activeId, setActiveId] = useState(initialSection);

  const navItems = useMemo<NavItem[]>(() => [
    { id: "help", label: t("help.navHelp") },
    { id: "shortcuts", label: t("help.navShortcuts") },
    { id: "signals", label: t("help.navSignals") },
    { id: "codebook", label: t("help.navCodebook") },
    { id: "privacy", label: t("help.navPrivacy") },
    {
      id: "about",
      label: t("help.navAbout"),
      children: [
        { id: "developer", label: t("help.navDeveloper") },
        { id: "design", label: t("help.navDesign") },
        { id: "contributing", label: t("help.navContributing") },
        { id: "acknowledgements", label: t("help.navAcknowledgements") },
      ],
    },
  ], [t, i18n.language]);
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
    case "privacy":
      content = <PrivacySection />;
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
    case "acknowledgements":
      content = <AcknowledgementsSection />;
      break;
    default:
      content = null;
  }

  return (
    <ModalNav
      open={open}
      onClose={onClose}
      title={t("help.title")}
      items={navItems}
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
