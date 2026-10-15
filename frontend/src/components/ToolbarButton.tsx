/**
 * ToolbarButton — styled button atom for toolbar controls.
 *
 * Renders a `.toolbar-btn` with optional icon, label, and dropdown arrow.
 * Controlled component — does not own open/active state.
 * Reuses atoms/button.css (.toolbar-btn, .toolbar-icon-svg, .toolbar-arrow).
 */

import type { ReactNode, ButtonHTMLAttributes } from "react";
import { Icon } from "./Icon";

export interface ToolbarButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Button label text. */
  label: ReactNode;
  /** Optional SVG icon rendered before the label. */
  icon?: ReactNode;
  /** Show dropdown arrow (chevron) after the label. */
  arrow?: boolean;
  /** Whether the dropdown is open (sets aria-expanded). */
  expanded?: boolean;
  "data-testid"?: string;
}

export function ToolbarButton({
  label,
  icon,
  arrow,
  expanded,
  className,
  "data-testid": testId,
  ...rest
}: ToolbarButtonProps) {
  const classes = ["toolbar-btn", className].filter(Boolean).join(" ");

  return (
    <button
      type="button"
      className={classes}
      aria-expanded={expanded}
      aria-haspopup={arrow ? "true" : undefined}
      data-testid={testId}
      {...rest}
    >
      {icon && <span className="toolbar-icon-svg">{icon}</span>}
      {label}
      {arrow && (
        <Icon name="caret" px={10} decorative className="toolbar-arrow" />
      )}
    </button>
  );
}
