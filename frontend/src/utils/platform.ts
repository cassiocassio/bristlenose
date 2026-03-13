/**
 * Platform detection — Mac vs non-Mac (Windows + Linux).
 *
 * Memoised: platform doesn't change mid-session.
 * `_resetPlatformCache()` is test-only (underscore convention).
 *
 * @module platform
 */

let _isMac: boolean | null = null;

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

export function _resetPlatformCache(): void {
  _isMac = null;
}
