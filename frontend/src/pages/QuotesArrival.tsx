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

/** Give up waiting for the quotes after this long: scroll to the group anyway. */
const WAIT_MS = 5000;

function bringIntoView(reveal: string, anchor: string): void {
  let snapshot = getQuotesSnapshot();
  const quote = snapshot.quotes.find((q) => q.dom_id === reveal);
  if (!quote) return;
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
  lastQuotesArrival = { reveal, anchor, changed: changes.map((c) => c.kind) };
}

export function QuotesArrival() {
  const location = useLocation();
  const anchor = arrivalAnchor(location.hash);
  const reveal = new URLSearchParams(location.search).get("reveal");
  useQuotesStore(); // re-render as the quotes load
  const scrollToAnchor = useScrollToAnchor();
  const handled = useRef<string | null>(null);
  // This visit, and how many loads the store had seen when it arrived.
  const [arrival, setArrival] = useState<{ key: string; loads: number } | null>(null);
  if (anchor && arrival?.key !== location.key) setArrival({ key: location.key, loads: quotesLoadCount() });

  const current = arrival !== null && arrival.key === location.key ? arrival : null;
  const loaded = current !== null && quotesLoadCount() > current.loads;

  useEffect(() => {
    if (!anchor || !current || handled.current === current.key) return;
    const land = () => {
      handled.current = current.key;
      if (reveal) bringIntoView(reveal, anchor);
      scrollToAnchor(anchor, { block: "start" });
    };
    if (loaded) {
      land();
      return;
    }
    const timer = setTimeout(land, WAIT_MS);
    return () => clearTimeout(timer);
  }, [anchor, reveal, loaded, current, scrollToAnchor]);

  return null;
}
