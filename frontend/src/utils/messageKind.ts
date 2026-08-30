/**
 * messageKind — the web mirror of `bristlenose/ui_kinds.py`.
 *
 * Five kinds, five glyphs, and nothing else. The taxonomy is the entire glyph
 * vocabulary any surface may use; `docs/design-pipeline-diagnostic-popover.md`
 * forbids minting new ones — anything that does not fit is either
 * over-engineering or a real gap worth filing.
 *
 * Third mirror of the same table. Python is the source of truth, Swift's
 * `MessageKind.swift` is the desktop mirror, this is the web one. Kept as
 * literal strings rather than imported so a browser bundle carries no
 * dependency on the Python package; pinned by `messageKind.test.ts`, which
 * reads `ui_kinds.py` and fails if the two drift.
 */

export type MessageKind = "success" | "info" | "warning" | "error" | "skipped";

/** Must match `CLI_GLYPH` in `bristlenose/ui_kinds.py`. */
export const KIND_GLYPH: Record<MessageKind, string> = {
  success: "✓",
  info: "ℹ",
  warning: "⚠",
  error: "✗",
  skipped: "—",
};
