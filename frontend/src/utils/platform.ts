/**
 * Platform detection — Mac vs non-Mac, desktop vs web.
 *
 * Memoised: platform doesn't change mid-session.
 * `_resetPlatformCache()` is test-only (underscore convention).
 *
 * Desktop mode is set via `data-platform="desktop"` on `<html>`,
 * injected by the server when launched from the macOS desktop app.
 *
 * @module platform
 */

let _isMac: boolean | null = null;
let _isDesktop: boolean | null = null;

export function isMac(): boolean {
  if (_isMac === null) {
    const uad = (navigator as any).userAgentData;
    if (uad?.platform) {
      _isMac = /mac/i.test(uad.platform);
    } else {
      _isMac = /Mac/.test(navigator.platform);
    }
  }
  return _isMac;
}

/**
 * True when running inside the macOS desktop app shell.
 * Reads `data-platform="desktop"` from `<html>`, set by the server.
 */
export function isDesktop(): boolean {
  if (_isDesktop === null) {
    _isDesktop = document.documentElement.dataset.platform === "desktop";
  }
  return _isDesktop;
}

/**
 * Current color theme name, or "default" if none set.
 * Reads `data-color-theme` from `<html>`, set by the server.
 */
export function getColorTheme(): string {
  return document.documentElement.dataset.colorTheme || "default";
}

export function _resetPlatformCache(): void {
  _isMac = null;
  _isDesktop = null;
}
