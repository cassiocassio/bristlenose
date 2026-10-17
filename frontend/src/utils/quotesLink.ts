/**
 * One address into the Quotes lens at a section or theme, for every surface that links to one:
 * `/report/quotes/?reveal=<dom_id>#<anchor>` (docs/design-transcript-gutter.md, "Arrival").
 *
 * The lens reads it on arrival (QuotesTab): a `section-`/`theme-` fragment shows Sections &
 * themes for that visit, and `reveal` names a quote to bring into view first. Because the whole
 * request is in the address, a plain click and a modifier-click into a new tab land alike.
 */
import type { MouseEvent } from "react";
import { navigateTo } from "../shims/navigation";
import { reportHref } from "./reportHref";

/** The router path (for `navigate`). */
export function quotesPath(anchor: string, reveal?: string): string {
  const query = reveal ? `?reveal=${encodeURIComponent(reveal)}` : "";
  return `/report/quotes/${query}${anchor ? `#${anchor}` : ""}`;
}

/** The `<a href>` (works under the export's hash router too). */
export function quotesHref(anchor: string, reveal?: string): string {
  return reportHref(quotesPath(anchor, reveal));
}

/** A link's plain click navigates in the app; a modifier click falls through to the href. When
 *  `from` is given (a router path with a `#t-…` fragment), the page being left is first replaced
 *  by it, so Back returns to the paragraph the jump was made from. */
export function followInApp(e: MouseEvent, path: string, from?: string): void {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  if (from) navigateTo(from, { replace: true });
  navigateTo(path);
}
