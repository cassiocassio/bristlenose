/**
 * What other pages need to know about a screen, without loading the Screens lens: its title, an
 * opaque reference to it for an address, and where each session's visits to it begin.
 * (The transcript's gutter: docs/design-transcript-gutter.md, stage 2.)
 *
 * Kept out of ScreensLens.tsx on purpose: importing from the lens would pull its whole lazy chunk
 * into the transcript's.
 */

export interface ScreenTabLike {
  session_id: string;
  code?: string;
  t: number;
  crop: [number, number, number, number];
  heading: string;
  visits: [number, number][];
}

export interface ScreenLike {
  key: string;
  name: string;
  tabs: ScreenTabLike[];
}

/** The title the Screens lens's navigator shows for a screen (or for one of its versions). */
export function screenTitle(screen: ScreenLike, tab?: ScreenTabLike): string {
  if (!screen.name.startsWith("/")) return screen.name.charAt(0).toUpperCase() + screen.name.slice(1);
  if (tab?.heading) return tab.heading;
  const hs = [...new Set(screen.tabs.map((t) => t.heading).filter(Boolean))];
  return hs.join(" · ") || screen.name;
}

/**
 * An opaque, stable reference to a screen, for an address. A screen's key is a path from a
 * participant's screen, deleted when screen text is switched off; put in a URL it would live on in
 * the browser's history, the web view's back list and the route the page reports to the Mac app.
 * So the address carries this instead (FNV-1a of the key, base 36), and the lens finds the screen
 * whose key hashes to it.
 */
export function screenRef(key: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(36);
}

/** The router path into the Screens lens at one screen, on one session's version of it. */
export function screensPath(key: string, sessionId: string): string {
  return `/report/screens/?screen=${screenRef(key)}&session=${encodeURIComponent(sessionId)}`;
}

/** The address a Screens arrival asked for, read from the page's own query. */
export function screensArrival(search: string): { ref: string; session: string } | null {
  const q = new URLSearchParams(search);
  const ref = q.get("screen");
  const session = q.get("session");
  return ref && session ? { ref, session } : null;
}

export interface ScreenStart {
  screen: ScreenLike;
  tab: ScreenTabLike;
  /** When this visit began, in the recording's seconds. */
  at: number;
}

/**
 * For one session, where each visit to a screen begins, by the paragraph it begins in. A visit
 * that follows a visit to the same screen with nothing else between is the same stay, not a new
 * one (switching back from a pop-up, or a gap in what could be read): it draws no new mark. Two
 * screens beginning in one paragraph are both listed, in the order they began.
 *
 * "The same screen" is the same title, not the same key: two pages with different addresses and
 * one heading (a paginated list, a filtered one) are one place to someone reading the transcript,
 * and listing both put one name twice in a paragraph's margin (QA, 17 Oct 2026).
 */
export function screenStarts(
  screens: ScreenLike[],
  sessionId: string,
  paragraphAt: (seconds: number) => number | null,
): Map<number, ScreenStart[]> {
  const visits: ScreenStart[] = [];
  for (const screen of screens) {
    for (const tab of screen.tabs) {
      if (tab.session_id !== sessionId) continue;
      for (const [a] of tab.visits ?? []) visits.push({ screen, tab, at: a });
    }
  }
  visits.sort((x, y) => x.at - y.at);
  const out = new Map<number, ScreenStart[]>();
  let previous: string | null = null;
  for (const v of visits) {
    const title = screenTitle(v.screen, v.tab);
    if (title === previous) continue;
    previous = title;
    const p = paragraphAt(v.at);
    if (p === null) continue;
    const list = out.get(p) ?? [];
    if (!list.some((s) => screenTitle(s.screen, s.tab) === title)) list.push(v);
    out.set(p, list);
  }
  return out;
}

/** The still for a version of a screen at a width (GET /screens/still, behind the bearer). */
export function stillUrl(tab: ScreenTabLike, w: number): string {
  const crop = tab.crop.map((v) => v.toFixed(4)).join(",");
  return `/screens/still?session_id=${encodeURIComponent(tab.session_id)}&t=${tab.t}&w=${w}&crop=${crop}`;
}
