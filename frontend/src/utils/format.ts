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

const MONTH_ABBR = [
  "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** Format a date string as Finder-style relative date. */
export function formatFinderDate(isoDate: string | null): string {
  if (!isoDate) return "\u2014";
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return "\u2014";

  const now = new Date();
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const dtDate = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;

  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  const timePart = `${hh}:${mm}`;

  if (dtDate === todayStr) {
    return `Today at ${timePart}`;
  }

  // Check yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;
  if (dtDate === yesterdayStr) {
    return `Yesterday at ${timePart}`;
  }

  const month = MONTH_ABBR[dt.getMonth() + 1];
  return `${dt.getDate()} ${month} ${dt.getFullYear()} at ${timePart}`;
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
