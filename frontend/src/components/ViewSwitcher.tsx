/**
 * ViewSwitcher — dropdown for switching between All / Starred quote views.
 *
 * Controlled component: receives viewMode, fires onViewModeChange.
 * Uses useDropdown hook for dismiss behaviour; open/close controlled by parent.
 *
 * Reuses organisms/toolbar.css (.view-switcher, .view-switcher-menu).
 */

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

const VIEW_OPTIONS: { value: "all" | "starred"; label: string; icon: string }[] = [
  { value: "all", label: "All quotes", icon: "\u00A0" },
  { value: "starred", label: "Starred quotes", icon: "\u2733" },
];

export function ViewSwitcher({
  viewMode,
  onViewModeChange,
  isOpen,
  onToggle,
  labelOverride,
  "data-testid": testId,
}: ViewSwitcherProps) {
  const { open, toggle, containerRef } = useDropdown({ isOpen, onToggle });

  const currentOption = VIEW_OPTIONS.find((o) => o.value === viewMode) ?? VIEW_OPTIONS[0];
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
          {VIEW_OPTIONS.map((opt) => (
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
