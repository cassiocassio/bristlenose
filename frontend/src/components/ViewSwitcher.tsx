/**
 * ViewSwitcher — dropdown for switching between All / Starred quote views.
 *
 * Controlled component: receives viewMode, fires onViewModeChange.
 * Uses useDropdown hook for dismiss behaviour; open/close controlled by parent.
 *
 * Reuses organisms/toolbar.css (.view-switcher, .view-switcher-menu).
 */

import { useTranslation } from "react-i18next";
import { ToolbarButton } from "./ToolbarButton";
import { useDropdown } from "../hooks/useDropdown";

export interface ViewSwitcherProps {
  viewMode: "all" | "starred";
  onViewModeChange: (mode: "all" | "starred") => void;
  /** Controlled open state from parent (for mutual exclusion). */
  isOpen?: boolean;
  onToggle?: (open: boolean) => void;
  /** Label override (e.g. "7 matching quotes" during search). */
  labelOverride?: string;
  "data-testid"?: string;
}

const VIEW_ICONS: Record<"all" | "starred", string> = {
  all: "\u00A0",
  starred: "\u2733",
};

export function ViewSwitcher({
  viewMode,
  onViewModeChange,
  isOpen,
  onToggle,
  labelOverride,
  "data-testid": testId,
}: ViewSwitcherProps) {
  const { t } = useTranslation();
  const { open, toggle, containerRef } = useDropdown({ isOpen, onToggle });

  const viewOptions = [
    { value: "all" as const, label: t("quotes.allQuotes"), icon: VIEW_ICONS.all },
    { value: "starred" as const, label: t("quotes.starredQuotes"), icon: VIEW_ICONS.starred },
  ];

  const currentOption = viewOptions.find((o) => o.value === viewMode) ?? viewOptions[0];
  const displayLabel = labelOverride ?? currentOption.label;

  function handleSelect(value: "all" | "starred") {
    onViewModeChange(value);
    if (onToggle) onToggle(false);
    else toggle();
  }

  return (
    <div
      className="view-switcher"
      ref={containerRef}
      data-testid={testId}
    >
      <ToolbarButton
        label={<span className="view-switcher-label">{displayLabel} </span>}
        arrow
        expanded={open}
        onClick={toggle}
        className="view-switcher-btn"
        data-testid={testId ? `${testId}-btn` : undefined}
      />
      {open && (
        <ul
          className="view-switcher-menu open"
          role="menu"
          data-testid={testId ? `${testId}-menu` : undefined}
        >
          {viewOptions.map((opt) => (
            <li
              key={opt.value}
              role="menuitem"
              data-view={opt.value}
              className={viewMode === opt.value ? "active" : ""}
              onClick={() => handleSelect(opt.value)}
            >
              <span className="menu-icon">{opt.icon}</span> {opt.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
