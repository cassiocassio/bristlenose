/**
 * What a right-click lands on, told to the Mac app so its context menu can say
 * exactly what each item does (docs/design-webview-context-menu.md §9).
 *
 * A component that writes a link's click handler also declares the link's
 * place, from the same values the handler uses. The place is never parsed back
 * out of the `href`: two hrefs in the report point at the wrong lens (§4.2),
 * and a href is only what a browser would do, not what the click does.
 *
 * The listener (`installContextTargetListener`) runs in the Mac app only. It
 * posts one `context-target` message per right-click, before WebKit asks the
 * app for its menu (measured 30 of 30, 8–71 ms ahead). It never cancels the
 * event: the menu is WebKit's, and the app edits it.
 */

/** Where a link goes and what clicking it does. */
export interface ContextPlace {
  /** The single click, which is the menu's first item: play the recording, go to `path`, or
   *  open `path` in a new window (threshold review, whose modal a same-window visit would close). */
  click: "play" | "navigate" | "window";
  /** How going there reads: Show in X (a moment or section inside X), Open X, or Go to Section. */
  verb: "show" | "open" | "go";
  /** What `path` shows: a session's transcript, the Quotes lens, or another lens. */
  dest: "transcript" | "quotes" | "lens";
  /** The router path the click (or Show/Open) navigates to, as `navigateTo` takes it. */
  path: string;
  /** The recording at a moment, for Play: `seekTo(key, seconds)`. Null where there is none. */
  media: { key: string; seconds: number } | null;
  /** Go to Section: the heading's id on the page showing, scrolled to as the contents link does. */
  anchor?: string;
}

/** A quote card under the pointer: the card menu's Star, Hide, Add Tag… and Copy Quote. */
export interface ContextCard {
  domId: string;
  starred: boolean;
  /** What its Star will do, by the one rule every surface uses (`starActionIsUnstar`), and how
   *  many quotes the card's commands act on: the selection it sits in, else 0 for itself alone.
   *  Filled in by the listener once it has settled the selection. */
  unstar: boolean;
  count: number;
  /** The card's own transcript place (its speaker link's), for Show in Transcript. */
  place: ContextPlace | null;
}

/** Spread onto the element that carries the click: `<a {...placeProps(p)}>`. */
export function placeProps(place: ContextPlace | null): { "data-bn-place"?: string } {
  return place ? { "data-bn-place": JSON.stringify(place) } : {};
}

/** A moment in a session: a timecode, a speaker badge, a journey label. */
export function momentPlace(
  click: ContextPlace["click"],
  sessionId: string | null | undefined,
  seconds: number,
  mediaKey: string | null,
): ContextPlace | null {
  if (!sessionId && !mediaKey) return null;
  return {
    click,
    verb: "show",
    dest: "transcript",
    path: sessionId ? `/report/sessions/${sessionId}#t-${Math.floor(seconds)}` : "",
    media: mediaKey ? { key: mediaKey, seconds } : null,
  };
}

/** A moment whose click opens its transcript in a new window, so the dialog it sits in stays
 *  open (threshold review). */
export function windowPlace(sessionId: string, seconds: number): ContextPlace | null {
  const place = momentPlace("navigate", sessionId, seconds, sessionId);
  return place && { ...place, click: "window" };
}

/** A whole session: its number or filename on the Sessions grid and the dashboard. */
export function sessionPlace(
  click: ContextPlace["click"],
  sessionId: string,
  hasMedia: boolean,
): ContextPlace {
  return {
    click,
    verb: "open",
    dest: "transcript",
    path: `/report/sessions/${sessionId}`,
    media: hasMedia ? { key: sessionId, seconds: 0 } : null,
  };
}

/** A heading in the Quotes lens, reached from elsewhere: Show in Quotes. */
export function quotesPlace(path: string): ContextPlace {
  return { click: "navigate", verb: "show", dest: "quotes", path, media: null };
}

/** A heading in the contents beside it: Go to Section. `path` is the heading's own address, for a new window. */
export function sectionPlace(anchor: string, path: string): ContextPlace {
  return { click: "navigate", verb: "go", dest: "quotes", path, media: null, anchor };
}

/** A whole lens: a dashboard stat card naming one. */
export function lensPlace(path: string): ContextPlace {
  return { click: "navigate", verb: "open", dest: "lens", path, media: null };
}

function readPlace(el: Element | null): ContextPlace | null {
  const raw = el?.getAttribute("data-bn-place");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ContextPlace;
  } catch {
    return null;
  }
}

/** The message one right-click posts. `here` is true when the place's page is the one showing. */
export interface ContextTarget {
  seq: number;
  place: ContextPlace | null;
  here: boolean;
  card: ContextCard | null;
  /** The link under the pointer, if any: one into this report (its href is a loopback address
   *  that dies with the serve, so the app takes out Copy Link and Share) or one out of it. */
  link: "internal" | "external" | null;
}

/** Whether a non-empty text selection reaches into `el`. */
function selectsTextIn(el: Element): boolean {
  const sel = typeof window.getSelection === "function" ? window.getSelection() : null;
  if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !sel.toString().trim()) return false;
  try {
    return sel.getRangeAt(0).intersectsNode(el);
  } catch {
    return false;
  }
}

function linkKind(target: Element | null): ContextTarget["link"] {
  const a = target?.closest("a[href]");
  const href = a?.getAttribute("href");
  if (href == null) return null;
  if (href.startsWith("#")) return "internal";
  try {
    return new URL(href, window.location.href).origin === window.location.origin
      ? "internal"
      : "external";
  } catch {
    return null;
  }
}

/** Read what a right-click at `target` landed on. Pure over the DOM, so it is tested without a
 *  bridge. `hasRecording` drops Play where the video map has no recording for the key, so the
 *  menu never offers a Play that would do nothing. */
export function readContextTarget(
  target: Element | null,
  seq: number,
  pathname: string,
  hasRecording: (key: string) => boolean,
): ContextTarget {
  const playable = (p: ContextPlace | null): ContextPlace | null => {
    if (!p?.media || hasRecording(p.media.key)) return p;
    // A link whose click plays has nothing to offer without its recording.
    return p.click === "play" && !p.path ? null : { ...p, media: null };
  };
  const placed = target?.closest("[data-bn-place]") ?? null;
  const place = playable(readPlace(placed));
  const here = place?.dest === "transcript" && !!place.path && place.path.split("#")[0] === pathname;
  const cardEl = target?.closest("blockquote.quote-card") ?? null;
  // A right-click on selected text is about the text: WebKit's Look Up, Copy and Share.
  const card: ContextCard | null =
    cardEl && cardEl.id && !selectsTextIn(cardEl)
      ? {
          domId: cardEl.id,
          starred: cardEl.classList.contains("starred"),
          unstar: cardEl.classList.contains("starred"),
          count: 0,
          place: playable(readPlace(cardEl.querySelector(".speaker [data-bn-place]"))),
        }
      : null;
  return { seq, place, here, card, link: linkKind(target) };
}
