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
import { Icon } from "./Icon";

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
        <Icon name="settings" px={16} decorative />
      </button>
      <button
        className="bn-tab bn-tab-icon"
        aria-label={t("nav.help")}
        aria-haspopup="dialog"
        title={t("nav.help")}
        onClick={onHelp}
      >
        <Icon name="help" px={16} decorative />
      </button>
    </div>
  );
}
