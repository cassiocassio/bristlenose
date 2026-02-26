/**
 * NavBar — tab bar for the report, replacing global_nav.html.
 *
 * Uses React Router `<NavLink>` for navigation. Active tab styling uses
 * the existing `.bn-tab.active` CSS class. SVG icons for Settings and
 * About are inlined from the Jinja2 template.
 */

import { NavLink } from "react-router-dom";

const textTabs = [
  { to: "/report/", label: "Project", end: true },
  { to: "/report/sessions/", label: "Sessions" },
  { to: "/report/quotes/", label: "Quotes" },
  { to: "/report/codebook/", label: "Codebook" },
  { to: "/report/analysis/", label: "Analysis" },
] as const;

function tabClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? "bn-tab active" : "bn-tab";
}

function iconTabClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? "bn-tab bn-tab-icon active" : "bn-tab bn-tab-icon";
}

export function NavBar() {
  return (
    <nav className="bn-global-nav" role="tablist">
      {textTabs.map(({ to, label, ...rest }) => (
        <NavLink
          key={to}
          to={to}
          className={tabClassName}
          role="tab"
          {...rest}
        >
          {label}
        </NavLink>
      ))}
      <div className="bn-tab-spacer" />
      <NavLink
        to="/report/settings/"
        className={iconTabClassName}
        role="tab"
        aria-label="Settings"
        title="Settings"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="8" cy="8" r="2.5"/>
          <path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.4 3.4l.85.85M11.75 11.75l.85.85M3.4 12.6l.85-.85M11.75 4.25l.85-.85"/>
        </svg>
      </NavLink>
      <NavLink
        to="/report/about/"
        className={iconTabClassName}
        role="tab"
        aria-label="About"
        title="About"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="8" cy="8" r="6.5"/>
          <line x1="8" y1="7" x2="8" y2="11.5"/>
          <circle cx="8" cy="4.5" r="0.01" fill="currentColor" strokeWidth="2"/>
        </svg>
      </NavLink>
    </nav>
  );
}
