/**
 * ShortcutsSection — keyboard shortcuts grid.
 *
 * Extracted from the old HelpModal overlay. Platform-aware:
 * Mac gets glyph-concatenated modifiers (⌘., ⇧J),
 * Windows/Linux gets text labels with + separators (Ctrl+., Shift+J).
 *
 * @module ShortcutsSection
 */

import { Fragment } from "react";
import { isMac } from "../../utils/platform";

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
      // TODO: ⌘, is intercepted by the browser (opens Safari/Chrome prefs).
      // Uncomment for desktop app where the shortcut works natively.
      // { keys: [{ modifier: "cmd", key: "," }], description: "Settings" },
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
    const glyph = combo.modifier === "shift" ? "\u21E7" : "\u2318";
    const displayKey = combo.modifier === "shift" ? combo.key.toUpperCase() : combo.key;
    return <kbd key={idx}>{glyph}{displayKey}</kbd>;
  }

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

export function ShortcutsSection() {
  return (
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
  );
}
