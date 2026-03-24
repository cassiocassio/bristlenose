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
import { useTranslation } from "react-i18next";
import { isMac } from "../../utils/platform";

interface KeyCombo {
  modifier?: "shift" | "cmd";
  key: string;
}

interface Shortcut {
  keys: KeyCombo[];
  description: string;
}

function useSections(): { title: string; shortcuts: Shortcut[] }[] {
  const { t } = useTranslation();
  return [
    {
      title: t("help.shortcuts.navigation"),
      shortcuts: [
        { keys: [{ key: "j" }, { key: "\u2193" }], description: t("help.shortcuts.nextQuote") },
        { keys: [{ key: "k" }, { key: "\u2191" }], description: t("help.shortcuts.previousQuote") },
      ],
    },
    {
      title: t("help.shortcuts.selection"),
      shortcuts: [
        { keys: [{ key: "x" }], description: t("help.shortcuts.toggleSelect") },
        {
          keys: [{ modifier: "shift", key: "j" }, { modifier: "shift", key: "k" }],
          description: t("help.shortcuts.extend"),
        },
      ],
    },
    {
      title: t("help.shortcuts.actions"),
      shortcuts: [
        { keys: [{ key: "s" }], description: t("help.shortcuts.starQuotes") },
        { keys: [{ key: "h" }], description: t("help.shortcuts.hideQuotes") },
        { keys: [{ key: "t" }], description: t("help.shortcuts.addTag") },
        { keys: [{ key: "r" }], description: t("help.shortcuts.repeatLastTag") },
        { keys: [{ key: "Enter" }], description: t("help.shortcuts.playInVideo") },
      ],
    },
    {
      title: t("help.shortcuts.global"),
      shortcuts: [
        { keys: [{ key: "/" }], description: t("help.shortcuts.search") },
        { keys: [{ key: "[" }], description: t("help.shortcuts.toggleContents") },
        { keys: [{ key: "]" }], description: t("help.shortcuts.toggleTags") },
        {
          keys: [{ key: "\\" }, { modifier: "cmd", key: "." }],
          description: t("help.shortcuts.toggleBothSidebars"),
        },
        { keys: [{ key: "m" }], description: t("help.shortcuts.toggleHeatmap") },
        { keys: [{ key: "?" }], description: t("help.shortcuts.thisHelp") },
        { keys: [{ key: "Esc" }], description: t("help.shortcuts.closeClear") },
      ],
    },
  ];
}

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
  const sections = useSections();
  return (
    <div className="help-columns">
      {sections.map((section) => (
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
