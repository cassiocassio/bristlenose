/**
 * NavBar — tab bar for the report, replacing global_nav.html.
 *
 * Uses React Router `<NavLink>` for navigation. Active tab styling uses
 * the existing `.bn-tab.active` CSS class. SVG icons for Export,
 * Settings, and Help are inlined.
 */

import { useEffect } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useLenses, type LensId } from "../contexts/ConditionStore";
import { ExportDropdown } from "./ExportDropdown";
import { RefreshButton } from "./RefreshButton";
import { useScreensAvailable } from "../islands/screens/availability";

interface NavBarProps {
  onExportReport?: () => void;
  onSendToMiro?: () => void;
  onSettings?: () => void;
  onHelp?: () => void;
}

const TAB_ROUTES: readonly {
  to: string;
  key: string;
  lens: LensId;
  end?: boolean;
}[] = [
  { to: "/report/", key: "nav.project", lens: "project", end: true },
  { to: "/report/sessions/", key: "nav.sessions", lens: "sessions" },
  { to: "/report/quotes/", key: "nav.quotes", lens: "quotes" },
  { to: "/report/codebook/", key: "nav.codebook", lens: "codebook" },
  { to: "/report/signals/", key: "nav.signals", lens: "signals" },
  { to: "/report/discussion/", key: "nav.discussion", lens: "discussion" },
  // Shown only when the project has screens, or recordings still being read
  // (islands/screens/availability.ts).
  { to: "/report/screens/", key: "nav.screens", lens: "screens" },
];

/** The lens a report path belongs to; null for a path no lens owns (the specimen). */
function lensForPath(pathname: string): LensId | null {
  const path = pathname.endsWith("/") ? pathname : `${pathname}/`;
  for (const { to, lens, end } of TAB_ROUTES) {
    if (end ? path === to : path.startsWith(to)) return lens;
  }
  return null;
}

/** Dev mode — same signal AppLayout uses for the responsive playground. */
const IS_DEV =
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_DEV__ === true ||
  location.port === "5173";

function tabClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? "bn-tab active" : "bn-tab";
}


export function NavBar({ onExportReport, onSendToMiro, onSettings, onHelp }: NavBarProps) {
  const { t } = useTranslation();
  const lenses = useLenses();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const screens = useScreensAvailable();
  // The status page hands over to the SPA where the reader was, usually
  // `/report/` — the Project lens, which a first analysis withholds. Don't draw
  // a lens under a nav that says it is not there yet: go to Sessions.
  const here = lensForPath(pathname);
  const withheld = here !== null && !lenses[here] && lenses.sessions;
  useEffect(() => {
    if (withheld) navigate("/report/sessions/", { replace: true });
  }, [withheld, navigate]);
  return (
    <nav className="bn-global-nav">
      {TAB_ROUTES.filter((r) => r.lens !== "screens" || screens).map(({ to, key, lens, end }) =>
        lenses[lens] ? (
          <NavLink key={to} to={to} className={tabClassName} end={end}>
            {t(key)}
          </NavLink>
        ) : (
          // A lens with nothing to show yet, during a run: visible, not a link
          // (docs/design-progressive-lenses.md §2 — disabled, never hidden).
          <span key={to} className="bn-tab" role="link" aria-disabled="true" data-lens={lens}>
            {t(key)}
          </span>
        ),
      )}
      {IS_DEV && (
        // Debug lens — dev only, English only (dev tool; no locale keys, same
        // precedent as the responsive playground).
        <NavLink to="/report/specimen" className={tabClassName}>
          Specimen
        </NavLink>
      )}
      <div className="bn-tab-spacer" />
      <RefreshButton iconOnly data-testid="bn-navbar-refresh" />
      {onExportReport && onSendToMiro && (
        <ExportDropdown onExportReport={onExportReport} onSendToMiro={onSendToMiro} />
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
