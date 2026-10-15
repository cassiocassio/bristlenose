/**
 * NavBar — tab bar for the report, replacing global_nav.html.
 *
 * Uses React Router `<NavLink>` for navigation. Active tab styling uses
 * the existing `.bn-tab.active` CSS class. SVG icons for Export,
 * Settings, and Help are inlined.
 */

import { useEffect, useRef } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useLenses, type LensId } from "../contexts/ConditionStore";
import { NavTools } from "./NavTools";
import { useBarMeasure } from "./navBarMeasure";
import { setNavTabs } from "../contexts/SidebarStore";
import { useNavBarMode } from "../contexts/TocShowing";
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

  // The bar measures its tabs for the fit cascade, and follows the mode the
  // fit gives back: condensed spacing, then the icon tabs moved into the
  // header (SidebarStore "Fit to width"; Header renders them there).
  const mode = useNavBarMode();
  const navRef = useRef<HTMLElement>(null);
  const probeFull = useRef<HTMLSpanElement>(null);
  const probeCondensed = useRef<HTMLSpanElement>(null);
  const tabs = TAB_ROUTES.filter((r) => r.lens !== "screens" || screens);
  const labelKey = tabs.map((r) => t(r.key)).join("\u0000") + (IS_DEV ? "\u0000Specimen" : "");
  useBarMeasure(navRef, ":scope > .bn-tab", probeFull, probeCondensed, setNavTabs, labelKey);

  return (
    <nav ref={navRef} className={`bn-global-nav${mode === "full" ? "" : " bn-global-nav--condensed"}`}>
      <span className="bn-nav-probe" aria-hidden="true">
        <span className="bn-tab" ref={probeFull} />
        <span className="bn-global-nav--condensed">
          <span className="bn-tab" ref={probeCondensed} />
        </span>
      </span>
      {tabs.map(({ to, key, lens, end }) =>
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
      {mode !== "iconsUp" && (
        <NavTools onExportReport={onExportReport} onSendToMiro={onSendToMiro} onSettings={onSettings} onHelp={onHelp} />
      )}
    </nav>
  );
}
