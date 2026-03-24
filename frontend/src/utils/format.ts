/** Format seconds as MM:SS or HH:MM:SS. */
export function formatDuration(seconds: number): string {
  if (seconds <= 0) return "\u2014"; // em dash
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) {
    return `${h}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}

/**
 * Format a date string as Finder-style relative date, locale-aware.
 * Uses Intl.DateTimeFormat for month/day names and Intl.RelativeTimeFormat
 * for "today"/"yesterday".
 */
export function formatFinderDate(isoDate: string | null, locale?: string): string {
  if (!isoDate) return "\u2014";
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return "\u2014";

  // Default to en-GB for day-month order (12 Feb), not en-US (Feb 12)
  const lng = locale ?? "en-GB";
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

/** Format seconds as a timecode string (MM:SS or HH:MM:SS). Unlike formatDuration, always returns a timecode — never an em-dash. */
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

/** Compact duration: "47m" / "1h 03" / "2h 23". Returns em-dash for 0/negative. */
export function formatCompactDuration(seconds: number): string {
  if (seconds <= 0) return "\u2014";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h === 0) return `${m}m`;
  return `${h}h ${String(m).padStart(2, "0")}`;
}

/** Compact date: "12 Feb" or "Wed 12 Feb" (includeDay=true). Locale-aware. Returns em-dash for null/invalid. */
export function formatCompactDate(isoDate: string | null, includeDay?: boolean, locale?: string): string {
  if (!isoDate) return "\u2014";
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return "\u2014";
  // Default to en-GB for day-month order (12 Feb), not en-US (Feb 12)
  const lng = locale ?? "en-GB";
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
