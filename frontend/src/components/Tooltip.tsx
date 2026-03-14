/**
 * Tooltip — shortcut hint tooltip for toolbar and nav buttons.
 *
 * Pure CSS hover delay (300ms via transition-delay in atoms/tooltip.css).
 * Renders platform-aware <kbd> badges using the same isMac() logic as HelpModal.
 *
 * Positioned above the trigger by default (suitable for toolbar buttons).
 * Uses aria-describedby for accessibility.
 *
 * @module Tooltip
 */

import { useId } from "react";
import { isMac } from "../utils/platform";

export interface KeyDef {
  key: string;
  modifier?: "shift" | "cmd";
}

export interface TooltipProps {
  /** Descriptive label (e.g. "Search quotes"). */
  content: string;
  /** Keyboard shortcut to display as <kbd> badge(s). */
  shortcut?: KeyDef;
  /** The trigger element(s). */
  children: React.ReactNode;
}

function renderShortcutBadge(shortcut: KeyDef): React.ReactNode {
  const mac = isMac();

  if (!shortcut.modifier) {
    return <kbd>{shortcut.key}</kbd>;
  }

  if (mac) {
    const glyph = shortcut.modifier === "shift" ? "\u21E7" : "\u2318";
    const displayKey =
      shortcut.modifier === "shift"
        ? shortcut.key.toUpperCase()
        : shortcut.key;
    return <kbd>{glyph}{displayKey}</kbd>;
  }

  const label = shortcut.modifier === "shift" ? "Shift" : "Ctrl";
  const displayKey =
    shortcut.modifier === "shift"
      ? shortcut.key.toUpperCase()
      : shortcut.key;
  return (
    <>
      <kbd>{label}</kbd>
      <span className="help-key-sep">+</span>
      <kbd>{displayKey}</kbd>
    </>
  );
}

export function Tooltip({ content, shortcut, children }: TooltipProps) {
  const id = useId();
  const tooltipId = `bn-tooltip-${id}`;

  return (
    <span className="bn-tooltip-wrap" aria-describedby={tooltipId}>
      {children}
      <span className="bn-tooltip" id={tooltipId} role="tooltip">
        {content}
        {shortcut && renderShortcutBadge(shortcut)}
      </span>
    </span>
  );
}
