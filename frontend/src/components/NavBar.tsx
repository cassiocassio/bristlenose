/**
 * NavBar — tab bar for the report, replacing global_nav.html.
 *
 * Uses React Router `<NavLink>` for navigation. Active tab styling uses
 * the existing `.bn-tab.active` CSS class. SVG icons for Export,
 * Settings, and Help are inlined.
 */

import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ExportDropdown } from "./ExportDropdown";

interface NavBarProps {
  onExportReport?: () => void;
  onSettings?: () => void;
  onHelp?: () => void;
}

const TAB_ROUTES = [
  { to: "/report/", key: "nav.project", end: true },
  { to: "/report/sessions/", key: "nav.sessions" },
  { to: "/report/quotes/", key: "nav.quotes" },
  { to: "/report/codebook/", key: "nav.codebook" },
  { to: "/report/analysis/", key: "nav.analysis" },
] as const;

function tabClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? "bn-tab active" : "bn-tab";
}


export function NavBar({ onExportReport, onSettings, onHelp }: NavBarProps) {
  const { t } = useTranslation();
  return (
    <nav className="bn-global-nav">
      {TAB_ROUTES.map(({ to, key, ...rest }) => (
        <NavLink
          key={to}
          to={to}
          className={tabClassName}
          {...rest}
        >
          {t(key)}
        </NavLink>
      ))}
      <div className="bn-tab-spacer" />
      {onExportReport && (
        <ExportDropdown onExportReport={onExportReport} />
      )}
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
    </nav>
  );
}
