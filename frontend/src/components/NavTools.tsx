/**
 * The tab bar's icon tabs — refresh, export, settings, help — as one group.
 *
 * Rendered by NavBar at the end of the tab row, or by Header under the
 * document title when the fit has moved them up to give the tabs the whole
 * row (SidebarStore "Fit to width", `barMode === "iconsUp"`). Moving remounts
 * it, so an open export menu closes as the window crosses that width.
 */

import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { setNavTools } from "../contexts/SidebarStore";
import { ExportDropdown } from "./ExportDropdown";
import { RefreshButton } from "./RefreshButton";
import { useBarMeasure } from "./navBarMeasure";

export interface NavToolsProps {
  onExportReport?: () => void;
  onSendToMiro?: () => void;
  onSettings?: () => void;
  onHelp?: () => void;
}

export function NavTools({ onExportReport, onSendToMiro, onSettings, onHelp }: NavToolsProps) {
  const { t } = useTranslation();
  const root = useRef<HTMLDivElement>(null);
  const probeFull = useRef<HTMLSpanElement>(null);
  const probeCondensed = useRef<HTMLSpanElement>(null);
  const hasExport = !!(onExportReport && onSendToMiro);
  useBarMeasure(root, ":scope > .bn-tab-icon, :scope > .export-dropdown-wrapper > .bn-tab-icon", probeFull, probeCondensed, setNavTools, String(hasExport), false);
  return (
    <div className="bn-tab-tools" ref={root}>
      <span className="bn-nav-probe" aria-hidden="true">
        <span className="bn-tab bn-tab-icon" ref={probeFull} />
        <span className="bn-global-nav--condensed">
          <span className="bn-tab bn-tab-icon" ref={probeCondensed} />
        </span>
      </span>
      <RefreshButton iconOnly data-testid="bn-navbar-refresh" />
      {hasExport && <ExportDropdown onExportReport={onExportReport!} onSendToMiro={onSendToMiro!} />}
      <button
        className="bn-tab bn-tab-icon"
        aria-label={t("nav.settings")}
        aria-haspopup="dialog"
        title={t("nav.settings")}
        onClick={onSettings}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="8" cy="8" r="2.5"/>
          <path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.4 3.4l.85.85M11.75 11.75l.85.85M3.4 12.6l.85-.85M11.75 4.25l.85-.85"/>
        </svg>
      </button>
      <button
        className="bn-tab bn-tab-icon"
        aria-label={t("nav.help")}
        aria-haspopup="dialog"
        title={t("nav.help")}
        onClick={onHelp}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="8" cy="8" r="6.5"/>
          <line x1="8" y1="7" x2="8" y2="11.5"/>
          <circle cx="8" cy="4.5" r="0.01" fill="currentColor" strokeWidth="2"/>
        </svg>
      </button>
    </div>
  );
}
