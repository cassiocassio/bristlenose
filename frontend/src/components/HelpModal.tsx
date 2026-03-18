/**
 * HelpModal — keyboard shortcuts reference overlay.
 *
 * Platform-aware: Mac gets glyph-concatenated modifiers (⌘., ⇧J),
 * Windows/Linux gets text labels with + separators (Ctrl+., Shift+J).
 *
 * Uses existing .help-overlay / .help-modal CSS classes. Three-column layout
 * with Navigation, Selection, Actions, Global sections.
 *
 * @module HelpModal
 */

import { Fragment, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { isMac } from "../utils/platform";

interface HelpModalProps {
  open: boolean;
  onClose: () => void;
}

interface KeyCombo {
  modifier?: "shift" | "cmd";
  key: string;
}

interface Shortcut {
  keys: KeyCombo[];
  description: string;
}

const SECTIONS: { title: string; shortcuts: Shortcut[] }[] = [
  {
    title: "Navigation",
    shortcuts: [
      { keys: [{ key: "j" }, { key: "\u2193" }], description: "Next quote" },
      { keys: [{ key: "k" }, { key: "\u2191" }], description: "Previous quote" },
    ],
  },
  {
    title: "Selection",
    shortcuts: [
      { keys: [{ key: "x" }], description: "Toggle select" },
      {
        keys: [{ modifier: "shift", key: "j" }, { modifier: "shift", key: "k" }],
        description: "Extend",
      },
    ],
  },
  {
    title: "Actions",
    shortcuts: [
      { keys: [{ key: "s" }], description: "Star quote(s)" },
      { keys: [{ key: "h" }], description: "Hide quote(s)" },
      { keys: [{ key: "t" }], description: "Add tag" },
      { keys: [{ key: "r" }], description: "Repeat last tag" },
      { keys: [{ key: "Enter" }], description: "Play in video" },
    ],
  },
  {
    title: "Global",
    shortcuts: [
      { keys: [{ key: "/" }], description: "Search" },
      { keys: [{ key: "[" }], description: "Toggle contents" },
      { keys: [{ key: "]" }], description: "Toggle tags" },
      {
        keys: [{ key: "\\" }, { modifier: "cmd", key: "." }],
        description: "Toggle both sidebars",
      },
      { keys: [{ modifier: "cmd", key: "," }], description: "Settings" },
      { keys: [{ key: "?" }], description: "This help" },
      { keys: [{ key: "Esc" }], description: "Close / clear" },
    ],
  },
];

function renderKeyCombo(combo: KeyCombo, idx: number): React.ReactNode {
  const mac = isMac();

  if (!combo.modifier) {
    return <kbd key={idx}>{combo.key}</kbd>;
  }

  if (mac) {
    // Mac: single <kbd> with glyph prefix, no separator
    const glyph = combo.modifier === "shift" ? "\u21E7" : "\u2318";
    const displayKey = combo.modifier === "shift" ? combo.key.toUpperCase() : combo.key;
    return <kbd key={idx}>{glyph}{displayKey}</kbd>;
  }

  // Non-Mac: separate <kbd> elements with + separator
  const label = combo.modifier === "shift" ? "Shift" : "Ctrl";
  const displayKey = combo.modifier === "shift" ? combo.key.toUpperCase() : combo.key;
  return (
    <span key={idx} className="help-key-group">
      <kbd>{label}</kbd>
      <span className="help-key-sep">+</span>
      <kbd>{displayKey}</kbd>
    </span>
  );
}

function renderKeys(keys: KeyCombo[]): React.ReactNode {
  return keys.map((combo, i) => (
    <Fragment key={i}>
      {i > 0 && <span className="help-key-sep">/</span>}
      {renderKeyCombo(combo, i)}
    </Fragment>
  ));
}

export function HelpModal({ open, onClose }: HelpModalProps) {
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  // Close on Escape (belt-and-suspenders — the global handler also does this)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [open, onClose]);

  return createPortal(
    <div
      className={`bn-overlay help-overlay${open ? " visible" : ""}`}
      onClick={handleOverlayClick}
      aria-hidden={!open}
      data-testid="bn-help-overlay"
    >
      <div className="bn-modal help-modal" data-testid="bn-help-modal">
        <button className="bn-modal-close" onClick={onClose} aria-label="Close">
          &times;
        </button>
        <h2>Keyboard Shortcuts</h2>
        <div className="help-columns">
          {SECTIONS.map((section) => (
            <div className="help-section" key={section.title}>
              <h3>{section.title}</h3>
              <dl>
                {section.shortcuts.map((s, i) => (
                  <Fragment key={i}>
                    <dt>{renderKeys(s.keys)}</dt>
                    <dd>{s.description}</dd>
                  </Fragment>
                ))}
              </dl>
            </div>
          ))}
        </div>
        <p className="bn-modal-footer">
          Press <kbd>?</kbd> to open this help, <kbd>Esc</kbd> or click outside
          to close
        </p>
      </div>
    </div>,
    document.body,
  );
}
