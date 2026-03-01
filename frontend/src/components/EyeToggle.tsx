/**
 * EyeToggle — reusable open/closed eye button for visual declutter.
 *
 * NOT a data filter — purely hides UI sections so the researcher
 * can focus on specific tag groups. See design doc for interaction spec.
 *
 * @module EyeToggle
 */

interface EyeToggleProps {
  open: boolean;
  onClick: (e: React.MouseEvent) => void;
  className?: string;
  "aria-label"?: string;
}

/** Open eye — visible when hovering an open group */
function EyeOpenIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  );
}

/** Closed eye — visible as affordance to reopen */
function EyeClosedIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z" />
      <line x1="2" y1="2" x2="14" y2="14" />
    </svg>
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
