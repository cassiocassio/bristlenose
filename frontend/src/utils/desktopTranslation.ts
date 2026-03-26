/**
 * Desktop-aware translation helper.
 *
 * Desktop-variant help text lives in the `desktop` i18next namespace
 * (loaded from `bristlenose/locales/{lang}/desktop.json`). This helper
 * checks the desktop namespace first when `isDesktop()` is true, falling
 * back to the base key if no desktop variant exists.
 *
 * @module desktopTranslation
 */

import type { TFunction } from "i18next";
import i18n from "../i18n";
import { isDesktop } from "./platform";

/**
 * Return desktop-specific translation if available, else fall back to base key.
 *
 * Desktop keys use the same key path in the `desktop` namespace.
 * E.g. `dt(t, "help.privacy.redactionIntro")` checks
 * `desktop:help.privacy.redactionIntro` first.
 */
export function dt(t: TFunction, key: string): string {
  if (!isDesktop()) return t(key);
  const desktopKey = `desktop:${key}`;
  return i18n.exists(desktopKey) ? t(desktopKey) : t(key);
}
