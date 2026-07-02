/**
 * Colour-palette boot logic — the single source of truth for the valid palette
 * set and how a saved preference is read/applied.
 *
 * The pre-React inline script in `frontend/index.html` hand-mirrors the allowed
 * list below (it runs before the bundle and cannot import this module). When
 * you add a palette here, update that inline allowlist too — the tiny manual
 * sync is deliberate; the alternative (a permissive regex) is what let a stale
 * value silently apply. See the review log Finding 2.
 */

/** All valid colour-palette identifiers. Extend as palettes land (edo2…). */
export const PALETTES = ["default", "edo"] as const;

export type Palette = (typeof PALETTES)[number];

export function isPalette(v: unknown): v is Palette {
  return typeof v === "string" && (PALETTES as readonly string[]).includes(v);
}

/**
 * Read a persisted palette preference — JSON-encoded (the vanilla store format)
 * or a bare legacy string — validated against the closed set. Returns `null`
 * when unset or invalid, so callers never clobber a server-injected default
 * with a bogus value.
 */
export function readSavedPalette(storage: Pick<Storage, "getItem">): Palette | null {
  try {
    const raw = storage.getItem("bristlenose-palette");
    if (!raw) return null;
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isPalette(parsed)) return parsed;
    } catch {
      // Not JSON — fall through to the bare-string check.
    }
    return isPalette(raw) ? raw : null;
  } catch {
    return null;
  }
}

/**
 * Apply a saved palette to the document root. No-op when unset or invalid,
 * leaving the server-injected `data-color-theme` in place. This is the tested
 * mirror of the inline no-flash boot script in `index.html`.
 */
export function applyBootPalette(root: Element, storage: Pick<Storage, "getItem">): void {
  const palette = readSavedPalette(storage);
  if (palette) root.setAttribute("data-color-theme", palette);
}
