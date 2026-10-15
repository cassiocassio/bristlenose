/**
 * EyeToggle — reusable open/closed eye button for visual declutter.
 *
 * NOT a data filter — purely hides UI sections so the researcher
 * can focus on specific tag groups. See design doc for interaction spec.
 *
 * @module EyeToggle
 */

import { Icon } from "./Icon";

interface EyeToggleProps {
  open: boolean;
  onClick: (e: React.MouseEvent) => void;
  className?: string;
  "aria-label"?: string;
}

/** Open eye — visible when hovering an open group */
function EyeOpenIcon() {
  return (
    <Icon name="show" px={14} decorative />
  );
}

/** Closed eye — visible as affordance to reopen */
function EyeClosedIcon() {
  return (
    <Icon name="hide" px={14} decorative />
  );
}

export function EyeToggle({ open, onClick, className, "aria-label": ariaLabel }: EyeToggleProps) {
  return (
    <button
      type="button"
      className={className ?? "group-eye"}
      onClick={onClick}
      aria-label={ariaLabel ?? (open ? "Hide" : "Show")}
    >
      {open ? <EyeOpenIcon /> : <EyeClosedIcon />}
    </button>
  );
}
