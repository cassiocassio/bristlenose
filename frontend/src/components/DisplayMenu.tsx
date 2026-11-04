/**
 * DisplayMenu — the toolbar's Display button and its menu: how the quote
 * content looks (docs/design-display-preferences.md).
 *
 * Layout (Columns · Single column), Density (Compact · Normal · Spacious),
 * Break long paragraphs, and Focus Mode. Built in the Export menu's family:
 * `useDropdown` + `useMenuKeyboard`, the `export-dropdown-*` classes, a muted
 * group label over indented rows with a tick.
 *
 * Two things differ from the Export menu, both decided by the owner:
 * the choices persist (`DisplayPrefsStore` → `storePref`), and the menu
 * **stays open on a choice** so the reader can try settings. Escape and a click
 * outside close it. So no handler here calls `setOpen(false)`.
 *
 * Focus Mode's row calls the same `toggleFocusMode()` as the toolbar button
 * beside it, so the two stay in step.
 */

import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { useDropdown } from "../hooks/useDropdown";
import { useMenuKeyboard } from "../hooks/useMenuKeyboard";
import {
  DENSITY_STOPS,
  setDisplayPref,
  useDisplayPrefs,
  type Layout,
} from "../contexts/DisplayPrefsStore";
import { toggleFocusMode, useFocusMode } from "../contexts/FocusModeStore";
import { Icon, type IconName } from "./Icon";
import { ToolbarButton } from "./ToolbarButton";

export function DisplayMenu() {
  const { t } = useTranslation();
  const prefs = useDisplayPrefs();
  const focusMode = useFocusMode();
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const { open, setOpen, toggle, containerRef } = useDropdown();
  const { menuRef } = useMenuKeyboard({
    open,
    onClose: () => setOpen(false),
    triggerRef,
  });

  // useMenuKeyboard turns Enter/Space on the focused row into a click, so the
  // row's own key handler only stops the page scrolling.
  const suppressKeyScroll = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") e.preventDefault();
  };

  const check = (on: boolean) => (
    <span className="export-dropdown-check" aria-hidden="true">
      {on && <Icon name="check" size="menu" decorative />}
    </span>
  );

  const radio = (
    testId: string,
    icon: IconName,
    label: string,
    checked: boolean,
    onChoose: () => void,
  ) => (
    <li
      role="menuitemradio"
      aria-checked={checked}
      tabIndex={-1}
      className="export-dropdown-item export-dropdown-scope"
      data-testid={testId}
      onClick={onChoose}
      onKeyDown={suppressKeyScroll}
    >
      {check(checked)}
      <Icon name={icon} size="menu" decorative />
      {label}
    </li>
  );

  const layoutRow = (value: Layout, icon: IconName, label: string) =>
    radio(`bn-display-layout-${value}`, icon, label, prefs.layout === value, () =>
      setDisplayPref("layout", value),
    );
  // Density is a continuous value (the Mac popover has a slider); the web menu
  // offers its three named stops. The tick shows only on exactly a stop, so a
  // value set between them on the Mac ticks none of these rows.
  const densityRow = (
    stop: keyof typeof DENSITY_STOPS,
    icon: IconName,
    label: string,
  ) =>
    radio(`bn-display-density-${stop}`, icon, label, prefs.density === DENSITY_STOPS[stop], () =>
      setDisplayPref("density", DENSITY_STOPS[stop]),
    );

  const breaksOn = prefs.breaks === "on";

  return (
    <div ref={containerRef} className="export-dropdown-wrapper">
      <ToolbarButton
        ref={triggerRef}
        label={t("toolbar.display")}
        icon={<Icon name="display" px={14} decorative />}
        arrow
        expanded={open}
        onClick={toggle}
        data-testid="bn-toolbar-display"
      />

      {open && (
        <ul
          ref={menuRef}
          role="menu"
          aria-label={t("toolbar.display")}
          className="export-dropdown-menu display-menu"
          data-testid="bn-display-menu"
        >
          <li role="none">
            <ul role="group" aria-labelledby="bn-display-layout-label" className="display-group">
              <li
                id="bn-display-layout-label"
                role="presentation"
                className="export-dropdown-group-label"
              >
                {t("toolbar.displayLayout")}
              </li>
              {layoutRow("columns", "layoutColumns", t("toolbar.displayColumns"))}
              {layoutRow("single", "layoutSingle", t("toolbar.displaySingleColumn"))}
            </ul>
          </li>
          <li role="separator" className="export-dropdown-separator" />

          <li role="none">
            <ul role="group" aria-labelledby="bn-display-density-label" className="display-group">
              <li
                id="bn-display-density-label"
                role="presentation"
                className="export-dropdown-group-label"
              >
                {t("toolbar.displayDensity")}
              </li>
              {densityRow("compact", "densityCompact", t("toolbar.displayCompact"))}
              {densityRow("normal", "densityNormal", t("toolbar.displayNormal"))}
              {densityRow("spacious", "densitySpacious", t("toolbar.displaySpacious"))}
            </ul>
          </li>
          <li role="separator" className="export-dropdown-separator" />

          <li
            role="menuitemcheckbox"
            aria-checked={breaksOn}
            tabIndex={-1}
            className="export-dropdown-item export-dropdown-scope"
            data-testid="bn-display-breaks"
            onClick={() => setDisplayPref("breaks", breaksOn ? "off" : "on")}
            onKeyDown={suppressKeyScroll}
          >
            {check(breaksOn)}
            {t("toolbar.displayBreakParagraphs")}
          </li>
          <li
            role="menuitemcheckbox"
            aria-checked={focusMode}
            tabIndex={-1}
            className="export-dropdown-item export-dropdown-scope"
            data-testid="bn-display-focus-mode"
            onClick={toggleFocusMode}
            onKeyDown={suppressKeyScroll}
          >
            {check(focusMode)}
            {t("toolbar.focusMode")}
          </li>
        </ul>
      )}
    </div>
  );
}
