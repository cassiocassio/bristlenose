/**
 * Platform-aware translation helpers.
 *
 * Three-tier translation model:
 *
 * | Helper | Behaviour                                      | Use case                          |
 * |--------|-------------------------------------------------|-----------------------------------|
 * | `t()`  | Always returns translation                      | Shared content (both platforms)   |
 * | `dt()` | Desktop override if exists, else base key       | Content that differs by platform  |
 * | `ct()` | Returns translation on CLI, `null` on desktop   | CLI-only content (hidden on desktop) |
 *
 * Desktop-variant keys live in the `desktop` i18next namespace
 * (`bristlenose/locales/{lang}/desktop.json`). CLI-only content uses
 * standard keys in `common.json` / `settings.json` — `ct()` simply
 * suppresses them when `isDesktop()` is true.
 *
 * No `desktop-only` helper is needed — content in `desktop.json` that
 * isn't a `dt()` override (menus, toolbar, native chrome) is rendered
 * by desktop-specific components that are never mounted in CLI serve mode.
 *
 * @module platformTranslation
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

/**
 * Return translation only when NOT on desktop. Returns `null` on desktop.
 *
 * Use for CLI-only content that should be hidden in the macOS app.
 * Components conditionally render based on the return value:
 *
 * ```tsx
 * const cliTip = ct(t, "help.privacy.cliTip");
 * {cliTip && <p>{cliTip}</p>}
 * ```
 */
export function ct(t: TFunction, key: string): string | null {
  return isDesktop() ? null : t(key);
}
