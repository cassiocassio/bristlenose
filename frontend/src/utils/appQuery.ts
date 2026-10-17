/**
 * The app's own query string, whichever router is serving the page: the browser router's
 * `location.search` in serve mode, or — in an exported report, whose hash router keeps the whole
 * address after `#` (`#/report/discussion/?item=s3.2#…`) — the part of the hash after `?`.
 *
 * For a lens that reads an arrival address from outside the router (its tests mount it without
 * one), as the Screens and Discussion lenses do (docs/design-transcript-gutter.md).
 */
import { isExportMode } from "./exportData";

export function appQuery(): URLSearchParams {
  if (!isExportMode()) return new URLSearchParams(window.location.search);
  const hash = window.location.hash;
  const q = hash.indexOf("?");
  if (q < 0) return new URLSearchParams();
  const rest = hash.slice(q + 1);
  const end = rest.indexOf("#");
  return new URLSearchParams(end < 0 ? rest : rest.slice(0, end));
}
