/**
 * Landing in the Quotes lens from a link (docs/design-transcript-gutter.md, "Arrival").
 *
 * The address is `/report/quotes/?reveal=<dom_id>#<anchor>` (utils/quotesLink.ts). QuotesTab reads
 * the anchor to show Sections & themes for that visit; this brings the revealed quote into view
 * and scrolls to its group. It renders nothing: it is a component only so that it, and not the
 * whole lens, re-renders while the quotes it waits for arrive.
 *
 * The quotes store outlives navigation, so on arrival it may hold another visit's quotes, or
 * none: this waits until the lens has loaded them again (quotesLoadCount moves) before it reads
 * anything.
 *
 * Bringing a quote into view is the fewest changes that do it (utils/filter.ts relaxFor): a
 * hidden quote is un-hidden (a write, undoable, refused in an export — the researcher chose to
 * follow a link to a quote they had hidden), and the view's filters change as little as they can.
 * What was changed is kept (`lastQuotesArrival`) for when the lens says so.
 */
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  filterStateOf,
  getQuotesSnapshot,
  quotesLoadCount,
  removeSearchToken,
  setSearchQuery,
  setTagFilter,
  setViewMode,
  unhideQuotes,
  useQuotesStore,
} from "../contexts/QuotesContext";
import { exitSoloMode, getSoloTag } from "../contexts/SidebarStore";
import { relaxFor, type Relaxation } from "../utils/filter";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";

/** An anchor the Sections & themes view draws: a group (`section-<id>`, `theme-<id>`) or the
 *  heading of either list (`sections`, `themes`, the Dashboard's). */
export function arrivalAnchor(hash: string): string | null {
  const m = /^#((?:section|theme)-\d+|sections|themes)$/.exec(hash);
  return m ? m[1] : null;
}

export interface QuotesArrival {
  reveal: string;
  anchor: string;
  changed: Relaxation["kind"][];
}

/** What the last arrival changed to bring its quote into view, for the lens to report. */
export let lastQuotesArrival: QuotesArrival | null = null;

/** Scroll to the group after this long even if the quotes have not loaded. The reveal still
 *  waits for them: it needs the quote. */
const WAIT_MS = 5000;
/** For this long after the first load, a load that brings the quote back hidden is un-hidden
 *  again. The lens's islands each fetch /quotes as they mount, and a response answered before the
 *  un-hide reached the server still says hidden (review, 17 Oct 2026). Only the hide is re-applied:
 *  filters are the page's own and no load resets them, so the researcher's change to one in this
 *  window stands. Long enough for the mount's loads; short enough that a quote hidden again on
 *  purpose, later in the visit, stays hidden. */
const REAPPLY_MS = 10000;

/** Take `reveal` off the page's address once it has landed, without telling the router: Back to
 *  this page, or a reload, must not un-hide again a quote the researcher has since hidden. The
 *  router keeps its own location, so nothing re-renders. Both routers: the browser's query, or
 *  the query inside an export's hash. */
export function dropRevealFromAddress(): void {
  const url = new URL(window.location.href);
  if (url.searchParams.has("reveal")) {
    url.searchParams.delete("reveal");
  } else {
    // The export's hash router: "#/report/quotes/?reveal=q-p1-10#theme-1".
    const h = url.hash;
    const q = h.indexOf("?");
    if (q < 0) return;
    const inner = h.indexOf("#", q);
    const params = new URLSearchParams(h.slice(q + 1, inner < 0 ? undefined : inner));
    if (!params.has("reveal")) return;
    params.delete("reveal");
    const rest = params.toString();
    url.hash = h.slice(0, q) + (rest ? `?${rest}` : "") + (inner < 0 ? "" : h.slice(inner));
  }
  window.history.replaceState(window.history.state, "", url.toString());
}

/** Bring the quote into view; true if it was among the loaded quotes. */
function bringIntoView(reveal: string, anchor: string): boolean {
  let snapshot = getQuotesSnapshot();
  const quote = snapshot.quotes.find((q) => q.dom_id === reveal);
  if (!quote) return false;
  const tagNames = () => {
    const names = new Set<string>();
    for (const q of snapshot.quotes) for (const t of q.tags) names.add(t.name);
    for (const list of Object.values(snapshot.tags)) for (const t of list) names.add(t.name);
    return [...names];
  };
  let changes = relaxFor(quote, filterStateOf(snapshot), tagNames());
  // A soloed tag holds its own copy of the filter and would put it back on exit: leave solo first.
  if (changes.some((c) => c.kind === "tagFilter") && getSoloTag() !== null) {
    exitSoloMode(setTagFilter);
    snapshot = getQuotesSnapshot();
    changes = relaxFor(quote, filterStateOf(snapshot), tagNames());
  }
  for (const c of changes) {
    if (c.kind === "hidden") unhideQuotes([reveal]);
    else if (c.kind === "starredOnly") setViewMode("all");
    else if (c.kind === "tagFilter") setTagFilter(c.next);
    else if (c.kind === "searchText") setSearchQuery("");
    else removeSearchToken(c.token);
  }
  // The first application says what changed; a later one finding nothing to do keeps that record.
  if (changes.length > 0 || lastQuotesArrival?.reveal !== reveal) {
    lastQuotesArrival = { reveal, anchor, changed: changes.map((c) => c.kind) };
  }
  return true;
}

/** For tests: forget the last arrival. */
export function resetQuotesArrival(): void {
  lastQuotesArrival = null;
}

export function QuotesArrival() {
  const location = useLocation();
  const anchor = arrivalAnchor(location.hash);
  const reveal = new URLSearchParams(location.search).get("reveal");
  useQuotesStore(); // re-render as the quotes load
  const scrollToAnchor = useScrollToAnchor();
  // This visit, and how many loads the store had seen when it arrived.
  const [arrival, setArrival] = useState<{ key: string; loads: number } | null>(null);
  if (anchor && arrival?.key !== location.key) setArrival({ key: location.key, loads: quotesLoadCount() });
  const current = arrival !== null && arrival.key === location.key ? arrival : null;
  const loads = current ? quotesLoadCount() - current.loads : 0;
  // Per visit: whether it has scrolled, and when this visit's first load landed.
  const scrolled = useRef<string | null>(null);
  const firstLoad = useRef<{ key: string; at: number } | null>(null);

  // This visit's first load brings the quote into view; a load in the next REAPPLY_MS that brings
  // it back hidden un-hides it again (no second undo step); scroll once.
  const revealed = useRef<string | null>(null);
  useEffect(() => {
    if (!anchor || !current || loads === 0) return;
    if (firstLoad.current?.key !== current.key) firstLoad.current = { key: current.key, at: Date.now() };
    if (reveal && revealed.current !== current.key) {
      const found = bringIntoView(reveal, anchor);
      if (found) {
        revealed.current = current.key;
        dropRevealFromAddress();
      } else if (loads === 1) {
        // Loaded and not there: deleted, or another quote holds its id. Say so where it can be seen.
        console.warn("QuotesArrival: the quote to reveal is not in this report", reveal);
      }
    } else if (reveal && Date.now() - firstLoad.current.at <= REAPPLY_MS && getQuotesSnapshot().hidden[reveal]) {
      unhideQuotes([reveal], false);
    }
    if (scrolled.current !== current.key) {
      scrolled.current = current.key;
      // Land on the quote the link named and flash it (docs/design-arrival-flash.md); without one,
      // or when it is not in the report, on the group's heading.
      if (reveal && revealed.current === current.key) scrollToAnchor(reveal, { block: "center", highlight: true });
      else scrollToAnchor(anchor, { block: "start", highlight: true });
    }
  }, [anchor, reveal, loads, current, scrollToAnchor]);

  // The quotes are slow to come: scroll to the group anyway; the reveal still waits for them.
  useEffect(() => {
    if (!anchor || !current || scrolled.current === current.key) return;
    const key = current.key;
    const timer = setTimeout(() => {
      if (scrolled.current === key) return;
      scrolled.current = key;
      scrollToAnchor(anchor, { block: "start", highlight: true });
    }, WAIT_MS);
    return () => clearTimeout(timer);
  }, [anchor, current, scrollToAnchor]);

  return null;
}
