/**
 * HelpModal — keyboard shortcuts reference overlay.
 *
 * Replaces getHelpModal() HTML string in focus.js. Uses existing
 * .help-overlay / .help-modal CSS classes.  Two-column layout with
 * Navigation, Selection, Actions, Global sections.
 *
 * @module HelpModal
 */

import { useCallback, useEffect } from "react";
import { createPortal } from "react-dom";

interface HelpModalProps {
  open: boolean;
  onClose: () => void;
}

interface Shortcut {
  keys: string[];
  description: string;
}

const SECTIONS: { title: string; shortcuts: Shortcut[] }[] = [
  {
    title: "Navigation",
    shortcuts: [
      { keys: ["j", "\u2193"], description: "Next quote" },
      { keys: ["k", "\u2191"], description: "Previous quote" },
    ],
  },
  {
    title: "Selection",
    shortcuts: [
      { keys: ["x"], description: "Toggle select" },
      { keys: ["Shift", "+", "j", "/", "k"], description: "Extend" },
    ],
  },
  {
    title: "Actions",
    shortcuts: [
      { keys: ["s"], description: "Star quote(s)" },
      { keys: ["h"], description: "Hide quote(s)" },
      { keys: ["t"], description: "Add tag(s)" },
      { keys: ["Enter"], description: "Play in video" },
    ],
  },
  {
    title: "Global",
    shortcuts: [
      { keys: ["/"], description: "Search" },
      { keys: ["?"], description: "This help" },
      { keys: ["Esc"], description: "Close / clear" },
    ],
  },
];

function renderKeys(keys: string[]): React.ReactNode {
  return keys.map((k, i) => {
    // Separators: +, / are rendered as text, not in kbd
    if (k === "+" || k === "/") {
      return (
        <span key={i} className="help-key-sep">
          {k}
        </span>
      );
    }
    return <kbd key={i}>{k}</kbd>;
  });
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

  if (!open) return null;

  return createPortal(
    <div
      className="help-overlay"
      onClick={handleOverlayClick}
      data-testid="bn-help-overlay"
    >
      <div className="help-modal" data-testid="bn-help-modal">
        <h2>Keyboard Shortcuts</h2>
        <div className="help-columns">
          {SECTIONS.map((section) => (
            <div className="help-section" key={section.title}>
              <h3>{section.title}</h3>
              <dl>
                {section.shortcuts.map((s, i) => (
                  <div key={i}>
                    <dt>{renderKeys(s.keys)}</dt>
                    <dd>{s.description}</dd>
                  </div>
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
