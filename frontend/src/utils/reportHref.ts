/**
 * Build an intra-app link href that works under BOTH routers:
 *  - browser router (serve mode): pathname URLs like "/report/sessions/s1"
 *  - hash router (export mode, opened from file://): must be "#/report/..."
 *
 * A plain "/report/..." href in an exported report navigates the browser off
 * the file:// document to a non-existent path — the link silently fails (no
 * console error). Every intra-app `<a href>` must go through this helper.
 *
 * Pass a router path, optionally with a "#t-123" / "#themes" fragment; in
 * export mode the whole thing is `#`-prefixed (the fragment rides as a nested
 * hash the destination page resolves — see TranscriptPage's tail-parse).
 */
import { isExportMode } from "./exportData";

export function reportHref(path: string): string {
  return isExportMode() ? `#${path}` : path;
}
