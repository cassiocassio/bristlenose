/**
 * Format a date string as Finder-style relative date, locale-aware.
 * Uses Intl.DateTimeFormat for month/day names and Intl.RelativeTimeFormat
 * for "today"/"yesterday".
 */
export function formatFinderDate(isoDate: string | null, locale?: string): string {
  if (!isoDate) return "\u2014";
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return "\u2014";

  // Default to en-GB for day-month order (12 Feb), not en-US (Feb 12).
  // Map bare "en" and "en-US" to "en-GB" — Bristlenose uses day-month order.
  const lng = !locale || locale.startsWith("en") ? "en-GB" : locale;
  const now = new Date();
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const dtDate = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;

  const timeFmt = new Intl.DateTimeFormat(lng, { hour: "2-digit", minute: "2-digit", hour12: false });
  const timePart = timeFmt.format(dt);

  if (dtDate === todayStr) {
    const rtf = new Intl.RelativeTimeFormat(lng, { numeric: "auto" });
    const today = rtf.format(0, "day"); // "today" / "aujourd'hui" / "heute" etc.
    return `${today[0].toUpperCase()}${today.slice(1)}, ${timePart}`;
  }

  // Check yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;
  if (dtDate === yesterdayStr) {
    const rtf = new Intl.RelativeTimeFormat(lng, { numeric: "auto" });
    const yesterdayWord = rtf.format(-1, "day"); // "yesterday" / "hier" etc.
    return `${yesterdayWord[0].toUpperCase()}${yesterdayWord.slice(1)}, ${timePart}`;
  }

  const dateFmt = new Intl.DateTimeFormat(lng, { day: "numeric", month: "short", year: "numeric" });
  return `${dateFmt.format(dt)}, ${timePart}`;
}

/**
 * Format seconds as a timecode string (MM:SS or HH:MM:SS).
 *
 * This is a POSITION in a recording — where a quote sits — not an elapsed
 * span. `MM:SS` is right for a position and wrong for a duration; for a
 * duration use `formatDurationHuman` below. The Sessions grid used to render
 * durations in this shape and read as a time of day.
 *
 * Always returns a timecode — never an em-dash.
 */
export function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Strip leading/trailing smart quotes and straight quotes from text. */
export function stripSmartQuotes(text: string): string {
  return text.replace(/^[\u201c\u201d"]+|[\u201c\u201d"]+$/g, "").trim();
}

/**
 * Human-readable duration: `"26m"` / `"1h 3m"` / `"1h"` / `"<1m"`.
 *
 * The house format for an elapsed span, and a mirror of two existing
 * implementations that already agree: Python's `_format_duration_human`
 * (`bristlenose/server/routes/dashboard.py`, which feeds the `duration_human`
 * and `total_duration_human` API fields) and Swift's `DurationFormat.human`
 * (`desktop/…/DurationFormat.swift`, the window subtitle and the native
 * sessions popover). Keep all three in step — `DurationFormatTests.swift`
 * pins the Swift side to the same table this file's tests use.
 *
 * Replaces the former `MM:SS` / `HH:MM:SS` rendering on the Sessions grid,
 * which read as a *time of day* when sat in a column beside dates and start
 * times (`26:31` is ambiguous at a glance; `1:03:00` more so).
 *
 * ── The one deliberate divergence from Python/Swift ────────────────────
 * A non-positive duration returns an em-dash, NOT `"0m"`. This is not drift.
 * Python and Swift format *aggregate totals* ("16 Sessions · 18h 23m"), where
 * a real zero is a real answer. This function formats a *per-row cell*, where
 * a zero means the duration is unknown — 19 of 236 sessions in the local
 * trial-run corpus (8%) have `duration_seconds == 0`, and rendering those as
 * `"0m"` would assert a measured zero that nobody measured. The em-dash is
 * this file's established convention for an absent cell value, shared with
 * `formatFinderDate` and `formatCompactDate` directly above.
 *
 * The `h` / `m` abbreviations are knowingly unlocalised, matching the Python
 * source and the note in `DurationFormat.swift`. Changing that is a separate
 * decision with a 22-locale cost — don't do it here.
 */
export function formatDurationHuman(seconds: number): string {
  if (seconds <= 0) return "\u2014"; // em dash — unknown, not measured-zero
  // Truncate to whole seconds first, then integer-divide, matching Python's
  // `int(seconds // 3600)` / `int((seconds % 3600) // 60)`.
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  return m > 0 ? `${m}m` : "<1m";
}

/** Compact date: "12 Feb" or "Wed 12 Feb" (includeDay=true). Locale-aware. Returns em-dash for null/invalid. */
export function formatCompactDate(isoDate: string | null, includeDay?: boolean, locale?: string): string {
  if (!isoDate) return "\u2014";
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return "\u2014";
  // Default to en-GB for day-month order (12 Feb), not en-US (Feb 12).
  // Map bare "en" and "en-US" to "en-GB" — Bristlenose uses day-month order.
  const lng = !locale || locale.startsWith("en") ? "en-GB" : locale;
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  if (includeDay) opts.weekday = "short";
  return new Intl.DateTimeFormat(lng, opts).format(dt);
}

/** Truncate a filename Finder-style with middle ellipsis. */
export function formatFinderFilename(name: string, maxLen: number = 24): string {
  if (name.length <= maxLen) return name;
  const dot = name.lastIndexOf(".");
  if (dot === -1) {
    return name.slice(0, maxLen - 1) + "\u2026";
  }
  const ext = name.slice(dot); // includes dot
  const stem = name.slice(0, dot);
  const budget = maxLen - ext.length - 1; // 1 for ellipsis
  if (budget <= 0) {
    return name.slice(0, maxLen - 1) + "\u2026";
  }
  const front = Math.ceil((budget * 2) / 3);
  const back = budget - front;
  if (back > 0) {
    return stem.slice(0, front) + "\u2026" + stem.slice(-back) + ext;
  }
  return stem.slice(0, front) + "\u2026" + ext;
}
