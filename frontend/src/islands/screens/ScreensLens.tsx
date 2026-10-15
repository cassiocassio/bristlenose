/**
 * The Screens lens: every screen the participants were on, a large screengrab of each, and every
 * quote said there around it — the ones whose words are on the screengrab in its margins, joined to
 * the line they read by a leader, the rest in a list under it.
 *
 * docs/design-screens.md S5. Data from GET /screens (server/routes/screens.py), stills from
 * GET /screens/still. Quotes are the report's own: the lens joins the screens' DOM ids to the
 * quotes store, and every quote is drawn by the Quotes lens's own card (islands/QuoteCard.tsx),
 * so star, hide, tags, editing, the playable timecode and focus are the same gestures there and
 * here. The board only positions the cards: it wraps each one to place, lift and drag it.
 *
 * Structured like its nearest sibling, the Discussion lens: a navigator column of its own (shown
 * and hidden like the guide, navPanel.ts), the zone title on the shared datum
 * (`.center > main > section:first-of-type > .section-heading`), the same key guards.
 *
 * A screen is one place for everything about it: every participant's version of it is a slide in
 * the backdrop carousel (carousel.ts), and the quote set is the same whichever slide shows. The
 * slide decides only which quotes are LINKED — on its screengrab, so in a margin with a leader —
 * and the person chips decide only whose quotes are in front. Placement is layout.ts; per-person
 * sequence and the J/K step are narrative.ts.
 *
 * Offered when the project has screens, or recordings still being read (availability.ts, the one
 * rule the nav and the Mac's lens rail follow). Every sentence is a `screens.*` locale key.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import { Counter, type CounterItem } from "../../components/Counter";
import { PersonBadge } from "../../components/PersonBadge";
import { SectionHeading } from "../../components/SectionHeading";
import type { TagVocabularyGroup } from "../../components/TagInput";
import { useFocus } from "../../contexts/FocusContext";
import { useLastRun } from "../../contexts/LastRunStore";
import {
  acceptProposedTag,
  addTagToQuotes,
  commitEdit,
  deleteBadge,
  denyProposedTag,
  hideQuotes,
  initFromQuotes,
  removeTag,
  restoreBadges,
  setStarred,
  starActionIsUnstar,
  toggleStar,
  unhideQuotes,
  useQuotesStore,
} from "../../contexts/QuotesContext";
import { CONTENT_FLOOR_PX, toggleTagGroupHidden, useSidebarStore } from "../../contexts/SidebarStore";
import { useProjectId } from "../../hooks/useProjectId";
import { announce } from "../../utils/announce";
import { pushUndo } from "../../contexts/UndoStore";
import { apiGet, getCodebook } from "../../utils/api";
import { formatTimecode } from "../../utils/format";
import { wholeWordsTerm, type SearchTerm } from "../../utils/searchMatch";
import { deriveTagVisibility, type TagGroupMeta } from "../../utils/tagVisibility";
import type { QuoteResponse, QuotesListResponse } from "../../utils/types";
import { QuoteCard } from "../QuoteCard";
import {
  arrangementVersion,
  boardColumns,
  CARD_W,
  cardEdge,
  clearPlacement,
  composeBoard,
  leaderPath,
  placementFromDrop,
  placementsFor,
  putPlacement,
  setPlacements,
  stageMode,
  subscribeArrangement,
  stillKey,
  topZ,
  type BoardCard,
  type Composition,
  type Edge,
  type Mode,
  type Placement,
} from "./layout";
import { dotWindow, Lru, makeSwipe, slideWindow } from "./carousel";
import { peopleOf, sequenceByPerson, stepFrom, type Said, type Sequence } from "./narrative";
import { markScreensFound } from "./availability";
import { postScreensArrangement } from "../../shims/bridge";
import { reportScreensNav, useScreensNav } from "./navPanel";
import { setScreensCount } from "./screensCount";
import "./screens.css";

// ── Types ────────────────────────────────────────────────────────────────

interface Pin {
  dom_id: string;
  box: [number, number, number, number];
  phrase: string;
  line: string;
}

interface ScreenTab {
  session_id: string;
  code: string;
  t: number;
  crop: [number, number, number, number];
  heading: string;
  visits: [number, number][];
  pins: Pin[];
  loose: string[];
}

interface Screen {
  key: string;
  name: string;
  quotes: number;
  tabs: ScreenTab[];
  /** The slide to open on: the version that links the most quotes. Older servers omit it. */
  default_tab?: number;
}

/** The slide a screen opens on. */
function defaultTab(sc: Screen): number {
  const d = sc.default_tab ?? 0;
  return Number.isInteger(d) && d >= 0 && d < sc.tabs.length ? d : 0;
}

/** Why the lens cannot read screens at all (server/routes/screens.py). */
export type UnavailableReason = "not_macos" | "vision_missing" | "no_job";
/** Why one recording has no index. */
export type FailedReason = "unreadable" | "cloud_downloading" | "ffprobe_failed" | "read_failed" | "not_read";

export interface ScreensResponse {
  enabled: boolean;
  /** A code, never prose: the lens says it in its own words (UNAVAILABLE). */
  unavailable: UnavailableReason | null;
  pending: boolean;
  reading: string | null;
  videos: number;
  indexed: number;
  /** Why a recording has no index, by session id, as a code (FAILED). Older servers omit it. */
  failed?: Record<string, FailedReason>;
  /** Recordings the engine read and found no text in. */
  blank?: string[];
  screens: Screen[];
}

// ── What the lens says ───────────────────────────────────────────────────

// One locale key per code, and a generic sentence for a code this build does not know: the
// server's own text never reaches the page (a reason code may be added before the lens learns it).
const UNAVAILABLE: Record<UnavailableReason, string> = {
  not_macos: "screens.unavailable.notMacos",
  vision_missing: "screens.unavailable.visionMissing",
  no_job: "screens.unavailable.noJob",
};

// Whole sentences, one per code, so each language words "Couldn't read s2: …" its own way.
const FAILED: Record<FailedReason, string> = {
  unreadable: "screens.couldNotRead.unreadable",
  cloud_downloading: "screens.couldNotRead.cloudDownloading",
  ffprobe_failed: "screens.couldNotRead.ffprobeFailed",
  read_failed: "screens.couldNotRead.readFailed",
  // Only when nothing is about to read it: during an analysis the server answers "waiting" instead.
  not_read: "screens.couldNotRead.notRead",
};

const has = (o: object, k: string) => Object.prototype.hasOwnProperty.call(o, k);

export function unavailableText(code: string): string {
  return i18n.t(has(UNAVAILABLE, code) ? UNAVAILABLE[code as UnavailableReason] : "screens.unavailable.other");
}

/** Why recording `session` has no index, as a sentence that names it. */
export function failedText(code: string, session = ""): string {
  return i18n.t(has(FAILED, code) ? FAILED[code as FailedReason] : "screens.couldNotRead.other", { session });
}

/** Still reading: the job is running, or recordings remain that have neither an index nor a failure. */
function stillReading(r: ScreensResponse): boolean {
  return r.pending || r.indexed + Object.keys(r.failed ?? {}).length < r.videos;
}

/**
 * Whether another look at /screens can show anything new. Not when reading is off or impossible,
 * and not once the job has said it will not read a recording (`not_read`): it has stopped, and
 * asking again every few seconds would only ask the same question.
 */
export function shouldPoll(r: ScreensResponse): boolean {
  if (!r.enabled || r.unavailable) return false;
  if (r.pending) return true;
  const failed = Object.values(r.failed ?? {});
  if (failed.includes("not_read")) return false;
  return r.indexed + failed.length < r.videos;
}

/** How far reading has got — the one sentence the lens's live region carries. Empty when done. */
export function progressText(r: ScreensResponse | null): string {
  if (!r || !r.enabled || r.unavailable || !stillReading(r)) return "";
  if (!r.pending) return i18n.t("screens.waiting", { count: r.videos, waiting: r.videos - r.indexed });
  const line = i18n.t("screens.reading", { count: r.videos, indexed: r.indexed });
  return r.reading ? `${line} ${i18n.t("screens.readingSession", { session: r.reading })}` : line;
}

/** Recordings that could not be read, or were read and held no text: a plain list, never live. */
function problemNotes(r: ScreensResponse): string[] {
  const out: string[] = [];
  for (const [sid, why] of Object.entries(r.failed ?? {})) out.push(failedText(why, sid));
  for (const sid of r.blank ?? []) out.push(i18n.t("screens.blank", { session: sid }));
  return out;
}

function NotesList({ lines, className = "screens-notes" }: { lines: string[]; className?: string }) {
  if (!lines.length) return null;
  return (
    <ul className={className}>
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}

// ── Polling ──────────────────────────────────────────────────────────────

/** 5 s apart, backing off to 30 s, for a few hours — SessionsTable's strip poll. A response that
 *  shows progress starts the back-off again, so a study being read keeps its count current. */
const pollDelay = (attempt: number) => Math.min(30_000, 5_000 * 1.5 ** attempt);
export const SCREENS_POLL_LIMIT = 400;

/** How far a grip must travel before a press becomes a drag (useVerticalDragResize's threshold). */
const DRAG_THRESHOLD = 3;

// ── Keys ─────────────────────────────────────────────────────────────────

/** True when a dialog owns the keyboard: the app root goes inert under a modal (DiscussionLens). */
function modalOpen(target: EventTarget | null): boolean {
  if (document.getElementById("bn-app-root")?.hasAttribute("inert")) return true;
  return target instanceof Element && !!target.closest('[aria-modal="true"], [role="dialog"]');
}

/** The Discussion lens's guard: never claim a key someone else handled, a chord, a key typed into a
 *  field, or one pressed while a dialog owns the keyboard. */
function keyIsOurs(e: KeyboardEvent): boolean {
  if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || modalOpen(e.target)) return false;
  const t = e.target;
  return !(t instanceof Element && (t.closest("input, textarea, select, [contenteditable='true']") ||
    // A dropdown or menu open under focus owns its own arrow keys (the hidden-quotes list's items
    // have none, so ↓ there would change screen and close it mid-use).
    t.closest(".bn-hidden-dropdown, [role='menu'], [role='listbox']") ||
    (t instanceof HTMLElement && t.isContentEditable)));
}

/** Focus the lens's title — a focus target, not a tab stop — where the control that held focus is
 *  going away (Tidy removes its own button; a closed menu may leave nothing to return to). */
function focusLensHeading(lens: Element | null | undefined): void {
  const h1 = lens?.querySelector<HTMLElement>(":scope > .section-heading h1");
  if (!h1) return;
  h1.tabIndex = -1;
  h1.focus({ preventScroll: true });
}

// ── Stills ───────────────────────────────────────────────────────────────

// Data URIs, under an LRU: a board's screengrabs (1600px, the showing slide and its neighbours)
// and the navigator's thumbnails (240px, three per row) in caches of their own, so scrolling the
// navigator never evicts the board's stills.
const boardStills = new Lru<string>(24);
const thumbStills = new Lru<string>(96);
const cacheFor = (url: string) => (url.includes("&w=240&") ? thumbStills : boardStills);
const stills = {
  get: (url: string) => cacheFor(url).get(url),
  has: (url: string) => cacheFor(url).has(url),
  set: (url: string, src: string) => cacheFor(url).set(url, src),
};
const stillFailed = new Set<string>();
const stillWaiters = new Map<string, Promise<string | null>>();

function stillUrl(tab: ScreenTab, w: number): string {
  const crop = tab.crop.map((v) => v.toFixed(4)).join(",");
  return `/screens/still?session_id=${encodeURIComponent(tab.session_id)}&t=${tab.t}&w=${w}&crop=${crop}`;
}

/** Fetch a still once, however many ask for it; null when there is none. */
function fetchStill(url: string): Promise<string | null> {
  let p = stillWaiters.get(url);
  if (!p) {
    p = apiGet<{ src: string }>(url)
      .then((r) => {
        stills.set(url, r.src);
        return r.src;
      })
      .catch((e: Error) => {
        // Shown in place of the screengrab: a missing still must not look like one still loading.
        stillFailed.add(url);
        console.warn("Screens: no still for", url, e);
        return null;
      })
      .finally(() => stillWaiters.delete(url));
    stillWaiters.set(url, p);
  }
  return p;
}

/** The still's data URI, or whether there is none (src null while it loads). */
function useStill(tab: ScreenTab | undefined, w: number): { src: string | null; failed: boolean } {
  const url = tab ? stillUrl(tab, w) : "";
  const [fetched, setFetched] = useState<{ url: string; src: string | null } | null>(null);
  useEffect(() => {
    if (!url || stills.has(url)) return;
    let live = true;
    fetchStill(url).then((s) => {
      if (live) setFetched({ url, src: s });
    });
    return () => {
      live = false;
    };
  }, [url]);
  if (!url) return { src: null, failed: false };
  const src = stills.get(url) ?? (fetched?.url === url ? fetched.src : null);
  return { src, failed: !src && stillFailed.has(url) };
}

/** The showing slide and its neighbours (carousel.ts slideWindow), the showing one asked for
 *  first; the others are neither fetched nor mounted. A turn shows a screengrab already loaded. */
function useStills(tabs: ScreenTab[], cur: number, w: number): { src: string | null; failed: boolean; near: boolean }[] {
  const near = new Set(slideWindow(tabs.length, cur));
  const urls = tabs.map((tb) => stillUrl(tb, w));
  const want = [cur, ...[...near].filter((j) => j !== cur)].map((j) => urls[j]).join("\n");
  const [, loaded] = useReducer((n: number) => n + 1, 0);
  useEffect(() => {
    let live = true;
    for (const url of want.split("\n")) {
      if (!url || stills.has(url) || stillFailed.has(url)) continue;
      fetchStill(url).then(() => {
        if (live) loaded();
      });
    }
    return () => {
      live = false;
    };
  }, [want]);
  return urls.map((u, j) => {
    if (!near.has(j)) return { src: null, failed: false, near: false };
    const src = stills.get(u) ?? null;
    return { src, failed: !src && stillFailed.has(u), near: true };
  });
}

// ── The lens ─────────────────────────────────────────────────────────────

/** The navigator's width: the one source, set on the lens as `--screens-nav-w` for screens.css's
 *  grid, and reported to the Mac as part of the width the lens wants. */
export const NAV_W = 280;

interface TagInfo extends TagGroupMeta {
  colour_set: string;
  colour_index: number;
}

/** Draws one quote with the Quotes lens's card, wired to the report's store. */
type RenderQuote = (q: QuoteResponse, phrase: string) => React.ReactNode;

const NO_FLASH = new Set<string>();
const noop = () => {};

/** Which slide shows for `sid` on this screen: that session's version, else the screen's default. */
function tabIndexOf(sc: Screen, sid: string | null): number {
  const i = sc.tabs.findIndex((tb) => tb.session_id === sid);
  return i >= 0 ? i : defaultTab(sc);
}

/** "p2's screen at 00:40 · 2 of 3", as plain text: what a turn of the carousel announces. */
function slideCaptionText(tab: ScreenTab, j: number, total: number): string {
  return i18n.t("screens.slideCaption", { code: tab.code, time: formatTimecode(tab.t), n: j + 1, total });
}

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** A card to focus once it can take focus; `seq` makes a second request for one card new. */
interface FocusRequest {
  dom: string;
  seq: number;
}

/** Where focus goes when the board changes under it (see ScreensLens's layout effect). */
type Refocus = "nav" | "carousel" | "lost";

export function ScreensLens() {
  const { t } = useTranslation();
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();
  const navPanel = useScreensNav();
  const [data, setData] = useState<ScreensResponse | null>(null);
  // Each load's own failure, cleared by its next success: a 401 while the sidecar restarts must not
  // leave the lens saying "couldn't load" after a refresh has loaded it.
  const [screensError, setScreensError] = useState(false);
  const [quotesError, setQuotesError] = useState(false);
  // Held by key and session, not by position: the list re-sorts as recordings are read.
  const [curKey, setCurKey] = useState<string | null>(null);
  const [tabSid, setTabSid] = useState<string | null>(null);
  const [vocabulary, setVocabulary] = useState<string[]>([]);
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);
  const [tagInfo, setTagInfo] = useState<Record<string, TagInfo>>({});
  const [hasModerator, setHasModerator] = useState(false);
  const store = useQuotesStore();
  const { selectedIds, clearSelection, registerVisibleQuoteIds, focusedId, setFocus } = useFocus();
  const { hiddenTagGroups, disabledFrameworks } = useSidebarStore();

  // Screens: polled while the job is still reading, capped, and re-read when the data moves.
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let lastIndexed = -1;
    const load = (attempt: number) => {
      apiGet<ScreensResponse>("/screens")
        .then((r) => {
          if (!live) return;
          setData(r);
          setScreensError(false);
          // The nav follows what the lens can show, not only the last status read.
          if (r.enabled && !r.unavailable && r.screens.length > 0) markScreensFound();
          const next = r.indexed !== lastIndexed && lastIndexed >= 0 ? 0 : attempt + 1;
          lastIndexed = r.indexed;
          if (shouldPoll(r) && next < SCREENS_POLL_LIMIT) timer = setTimeout(() => load(next), pollDelay(next));
        })
        .catch((e: unknown) => {
          // The cause reaches the console; the page says what happened, not the server's words.
          console.error("Screens: /screens failed", e);
          if (!live) return;
          setScreensError(true);
          // A failure is usually transient (the sidecar restarting): look again, on the same
          // back-off and within the same cap as the poll, rather than stop for good.
          const next = attempt + 1;
          if (next < SCREENS_POLL_LIMIT) timer = setTimeout(() => load(next), pollDelay(next));
        });
    };
    load(0);
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [refreshKey]);

  // Quotes: the report's own store, hydrated as the Quotes lens hydrates it, again on a refresh.
  const loadedOnce = useRef(false);
  useEffect(() => {
    const replace = loadedOnce.current;
    loadedOnce.current = true;
    apiGet<QuotesListResponse>("/quotes")
      .then((json) => {
        const all = [
          ...json.sections.flatMap((s) => s.quotes),
          ...json.themes.flatMap((th) => th.quotes),
          ...(json.unjoined ?? []),
        ];
        initFromQuotes(all, replace, json.uncategorised);
        setHasModerator(!!json.has_moderator);
        setQuotesError(false);
      })
      // Without the quotes every screen would read "0 quotes": say so instead.
      .catch((e: unknown) => {
        console.error("Screens: /quotes failed", e);
        setQuotesError(true);
      });
    getCodebook()
      .then((cb) => {
        setVocabulary(cb.all_tag_names);
        const info: Record<string, TagInfo> = {};
        const groups: TagVocabularyGroup[] = [];
        for (const g of cb.groups) {
          const tags: { name: string; colourIndex: number }[] = [];
          for (const tg of g.tags) {
            info[tg.name.toLowerCase()] = {
              group: g.name, frameworkId: g.framework_id, colour_set: g.colour_set, colour_index: tg.colour_index,
            };
            tags.push({ name: tg.name, colourIndex: tg.colour_index });
          }
          groups.push({ groupName: g.name, colourSet: g.colour_set, tags });
        }
        setTagInfo(info);
        setGroupedVocabulary(groups);
      })
      .catch((e: unknown) => console.warn("Screens: no codebook, so no tag vocabulary", e));
  }, [refreshKey]);

  const byId = useMemo(() => {
    const m = new Map<string, QuoteResponse>();
    for (const q of [...store.quotes, ...(store.uncategorised ?? [])]) m.set(q.dom_id, q);
    return m;
  }, [store.quotes, store.uncategorised]);

  const screens = useMemo(() => data?.screens ?? [], [data]);
  const cur = Math.max(0, screens.findIndex((sc) => sc.key === curKey));
  const screen = screens[cur];
  const tabIdx = screen ? tabIndexOf(screen, tabSid) : 0;
  const tab = screen?.tabs[tabIdx];

  // Everything said on this screen, by every participant on it, once each, in time order: the same
  // set whichever slide is showing (a screen is one place for everything about it). Hidden quotes
  // are not on the board. It is also the only set a gesture on a selection may reach: a selection
  // made on the Quotes lens survives the route change, and starring one card must not star twenty
  // quotes nobody can see here.
  const said = useMemo(() => {
    if (!screen) return [];
    return screen.tabs
      .flatMap((tb) => [...tb.pins.map((p) => p.dom_id), ...tb.loose])
      .filter((d, i, a) => a.indexOf(d) === i && byId.has(d) && !store.hidden[d])
      .sort((a, b) => byId.get(a)!.start_timecode - byId.get(b)!.start_timecode);
  }, [screen, byId, store.hidden]);
  const saidBy = useMemo<Said[]>(
    () => said.map((d) => ({ id: d, person: byId.get(d)!.participant_id, t: byId.get(d)!.start_timecode })),
    [said, byId],
  );
  const people = useMemo(() => peopleOf(saidBy), [saidBy]);
  const sequence = useMemo(() => sequenceByPerson(saidBy), [saidBy]);

  // The person chips: whose quotes are in front. They never turn the carousel — the carousel says
  // whose screenshot, the chips whose quotes. Kept per screen; a screen opens with everyone's.
  const [chips, setChips] = useState<{ key: string; on: string[] }>({ key: "", on: [] });
  const chosen = useMemo(
    () => new Set(chips.key === screen?.key ? chips.on.filter((p) => people.includes(p)) : []),
    [chips, screen, people],
  );
  const toggleChip = useCallback(
    (person: string) => {
      if (!screen) return;
      setChips((c) => {
        const on = c.key === screen.key ? c.on : [];
        return { key: screen.key, on: on.includes(person) ? on.filter((p) => p !== person) : [...on, person] };
      });
    },
    [screen],
  );

  // The narrative: this screen's quotes in time order, only the chosen people's while a chip is on.
  // It is J/K's list and nothing else's.
  const stepOrder = useMemo(
    () => (chosen.size ? said.filter((d) => chosen.has(byId.get(d)!.participant_id)) : said),
    [said, chosen, byId],
  );
  // The visible quotes, for the report's per-quote keys (s/h/t/r/x/Enter scope to them on this lens),
  // a shift-click range and ⌘A: every card the board shows, dimmed ones included. A chip says whose
  // quotes are in front, not which exist — a dimmed card still takes a click, so it takes a key, and
  // ⌘A selects it.
  useEffect(() => {
    registerVisibleQuoteIds("screens", said);
    // Registers empty rather than deleting, as QuoteSections does, so the slot outlives a remount.
    return () => registerVisibleQuoteIds("screens", []);
  }, [registerVisibleQuoteIds, said]);

  // The window subtitle's count, and what the Mac reads for its View menu and column fit.
  useEffect(() => {
    setScreensCount(screens.length);
    return () => setScreensCount(0);
  }, [screens.length]);
  const boardShown = !quotesError && !!data?.enabled && !data.unavailable && screens.length > 0;
  const navShown = navPanel.wish && boardShown;
  useEffect(() => {
    reportScreensNav(navShown, (navPanel.wish ? NAV_W : 0) + CONTENT_FLOOR_PX);
  }, [navShown, navPanel.wish]);

  // Changing screen remounts the board, and focus inside it would fall to the page; turning the
  // carousel keeps the board but can move a card from a margin to the list (a remount of that card).
  // Where focus was decides where it goes: on a navigator link, to the link that is now current; in
  // the carousel, to the carousel; anywhere else on the board, nowhere if it survived, else the
  // board's title. Focus outside the lens is left alone. "On p2's screen" is the board's to settle
  // (`focusRequest`): the card it moves is hidden until placement gives it a spot.
  const lensRef = useRef<HTMLElement>(null);
  const refocus = useRef<{ want: Refocus; from: Element | null } | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const boardKey = screen && tab ? `${screen.key}|${tab.session_id}|${tab.t}` : "";
  useLayoutEffect(() => {
    const r = refocus.current;
    refocus.current = null;
    const lens = lensRef.current;
    if (!r || !lens) return;
    const at = (el: HTMLElement | null | undefined) => {
      if (!el) return false;
      el.focus({ preventScroll: true });
      return true;
    };
    if (r.want === "nav" && at(lens.querySelector<HTMLElement>('.screens-nav a[aria-current="true"]'))) return;
    if (r.want === "carousel" && at(lens.querySelector<HTMLElement>('.screens-carousel[tabindex="0"]'))) return;
    const now = document.activeElement;
    if (now && now !== document.body && lens.contains(now)) return; // it survived
    const h1 = lens.querySelector<HTMLElement>(":scope > .section-heading h1");
    if (h1) {
      h1.tabIndex = -1; // a focus target, not a tab stop
      h1.focus();
    }
  }, [boardKey]);

  // Moving to another screen, or turning the carousel, is announced: the board changes under a
  // screen reader with nothing else to say so.
  const go = useCallback(
    (i: number, j?: number, focusCard?: string) => {
      if (!screens.length) return;
      const n = screens.length;
      const at = ((i % n) + n) % n;
      const next = screens[at];
      const same = next.key === screen?.key;
      const jj = Math.min(Math.max(0, j ?? (same ? tabIdx : defaultTab(next))), next.tabs.length - 1);
      const nextTab = next.tabs[jj];
      const active = document.activeElement;
      const lens = lensRef.current;
      const moving = `${next.key}|${nextTab?.session_id}|${nextTab?.t}` !== boardKey;
      let want: Refocus | null = null;
      if (focusCard) setFocusRequest((r) => ({ dom: focusCard, seq: (r?.seq ?? 0) + 1 }));
      else if (moving && active instanceof Element && lens?.contains(active)) {
        want = active.closest(".screens-nav") ? "nav" : active.closest(".screens-carousel") ? "carousel" : "lost";
      }
      refocus.current = want ? { want, from: active } : null;
      setCurKey(next.key);
      setTabSid(nextTab?.session_id ?? null);
      if (!moving || !nextTab) return;
      if (same) {
        // A turn of the carousel: say which slide ("2 of 3"), wherever focus is — it mostly stays.
        announce(slideCaptionText(nextTab, jj, next.tabs.length));
        // The card that asked for this slide is now linked: bring it forward and light its line.
        if (focusCard) setFocus(focusCard, { scroll: false });
        return;
      }
      // Where focus moves, the newly focused title, link or carousel says where we are; announcing
      // as well would say it twice.
      if (refocus.current) return;
      announce(i18n.t("screens.announceScreen", { title: screenTitle(next, nextTab), n: at + 1, total: n }));
    },
    [screens, screen, tabIdx, boardKey, setFocus],
  );
  const flip = useCallback(
    (dir: 1 | -1) => {
      if (!screen || screen.tabs.length < 2) return;
      go(cur, (tabIdx + dir + screen.tabs.length) % screen.tabs.length);
    },
    [go, cur, tabIdx, screen],
  );
  // J/K: the next quote in the narrative, brought forward (FocusContext's focus: the card rises and
  // its line lights) and scrolled into view. It moves as moveFocus does (narrative.ts stepFrom), but
  // over `stepOrder`, not the registered visible quotes.
  const step = useCallback(
    (dir: 1 | -1) => {
      const next = stepFrom(stepOrder, focusedId, dir);
      if (next && next !== focusedId) setFocus(next);
    },
    [stepOrder, focusedId, setFocus],
  );

  // Keys: ↑/↓ change screen, ←/→ turn the carousel, J/K step through the quotes.
  //
  // How these meet the report's global handler (hooks/useKeyboardShortcuts.ts): on Screens it
  // returns early for the arrows and j/k, so this lens owns them, and it ignores Next/Previous
  // Quote from the menu here (the lens answers those below). What the global handler does handle
  // on Screens is the per-quote keys — s/h/t/r/x/Enter — scoped to the cards this lens registers
  // (`said`). Every key here is still under keyIsOurs, whose first test is `defaultPrevented`, and
  // every key taken is preventDefault()ed.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!screen || !keyIsOurs(e)) return;
      const k = e.key;
      // With one screen there is nowhere to go: leave ↑/↓ to scroll the page. Likewise ←/→ with one
      // version of the screen.
      if (k === "ArrowDown" && screens.length > 1) go(cur + 1);
      else if (k === "ArrowUp" && screens.length > 1) go(cur - 1);
      else if (k === "ArrowRight" && screen.tabs.length > 1) flip(1);
      else if (k === "ArrowLeft" && screen.tabs.length > 1) flip(-1);
      else if ((k === "j" || k === "k") && !e.shiftKey && stepOrder.length) step(k === "j" ? 1 : -1);
      else return;
      e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [go, flip, step, cur, screen, screens.length, stepOrder.length]);

  // The Mac's View menu (and anything else on the bridge) drives the same steps by name
  // (shims/bridge.ts dispatches `bn:menu-action`). Tidy is the board's own (ScreenBoard).
  useEffect(() => {
    const onMenu = (e: Event) => {
      if (!screen) return;
      switch ((e as CustomEvent<{ action?: string }>).detail?.action) {
        case "nextScreen":
          if (screens.length > 1) go(cur + 1);
          break;
        case "previousScreen":
          if (screens.length > 1) go(cur - 1);
          break;
        case "nextScreenshot":
          flip(1);
          break;
        case "previousScreenshot":
          flip(-1);
          break;
        case "nextQuote":
          step(1);
          break;
        case "previousQuote":
          step(-1);
          break;
        default:
          break;
      }
    };
    window.addEventListener("bn:menu-action", onMenu);
    return () => window.removeEventListener("bn:menu-action", onMenu);
  }, [go, flip, step, cur, screen, screens.length]);

  // ── The card's gestures: QuoteGroup's, so a selection acts as one ──
  const vis = useMemo(
    () => deriveTagVisibility(tagInfo, hiddenTagGroups, disabledFrameworks),
    [tagInfo, hiddenTagGroups, disabledFrameworks],
  );
  /** The selection the clicked card belongs to, narrowed to this board; else the card alone. */
  const targets = useCallback(
    (domId: string) => (selectedIds.has(domId) ? said.filter((d) => selectedIds.has(d)) : [domId]),
    [selectedIds, said],
  );
  const onToggleStar = useCallback(
    (domId: string, on: boolean) => {
      const ids = targets(domId);
      if (ids.length > 1) setStarred(ids, !starActionIsUnstar(new Set(ids), null, store.starred));
      else toggleStar(domId, on);
    },
    [targets, store.starred],
  );
  const onToggleHide = useCallback(
    (domId: string) => {
      hideQuotes(targets(domId));
      if (selectedIds.has(domId)) clearSelection();
    },
    [targets, selectedIds, clearSelection],
  );
  const onTagAdd = useCallback(
    (domId: string, name: string) => {
      const info = tagInfo[name.toLowerCase()];
      const group = info?.group ?? "Uncategorised";
      addTagToQuotes(targets(domId), {
        name,
        codebook_group: group,
        colour_set: info?.colour_set ?? "",
        colour_index: info?.colour_index ?? 0,
        source: "human",
      });
      // As on the Quotes lens: a tag picked from an eye-hidden group un-hides the group, or the
      // badge would vanish the moment it was added (QuoteGroup.handleTagAdd).
      if (hiddenTagGroups.has(group)) toggleTagGroupHidden(group);
    },
    [tagInfo, targets, hiddenTagGroups],
  );
  const onProposedAccept = useCallback(
    (domId: string, proposalId: number, name: string) => {
      const pt = (store.proposedTags[domId] || []).find((p) => p.id === proposalId);
      acceptProposedTag(domId, proposalId, {
        name,
        codebook_group: pt?.group_name ?? "Uncategorised",
        colour_set: pt?.colour_set ?? "",
        colour_index: pt?.colour_index ?? 0,
        source: "autocode",
      });
    },
    [store.proposedTags],
  );

  const renderQuote: RenderQuote = (q, phrase) => {
    const id = q.dom_id;
    const allTags = store.tags[id] ?? [];
    const edited = store.edits[id] ?? null;
    const proposed = store.proposedTags[id] ?? [];
    const term: SearchTerm | null = phrase ? wholeWordsTerm(phrase) : null;
    return (
      <QuoteCard
        quote={q}
        displayText={edited ?? q.text}
        isStarred={!!store.starred[id]}
        isHidden={false}
        userTags={allTags.filter((tb) => !vis.hiddenGroups.has(tb.codebook_group))}
        allTagNames={allTags.map((tb) => tb.name)}
        hiddenTagNames={vis.decoratedTagNames}
        disabledTagNames={vis.suppressedTagNames}
        deletedBadges={store.deletedBadges[id] ?? []}
        isEdited={edited != null && edited !== q.text}
        tagVocabulary={vocabulary}
        groupedVocabulary={groupedVocabulary}
        sessionId={q.session_id}
        hasMedia
        hasModerator={hasModerator}
        proposedTags={proposed.filter((p) => !vis.hiddenGroups.has(p.group_name))}
        flashingTags={NO_FLASH}
        moderatorQuestion={null}
        isQuestionOpen={false}
        isPillVisible={false}
        onToggleStar={onToggleStar}
        onToggleHide={onToggleHide}
        onEditCommit={commitEdit}
        onTagAdd={onTagAdd}
        onTagRemove={removeTag}
        onBadgeDelete={deleteBadge}
        onBadgeRestore={restoreBadges}
        onProposedAccept={(pid, name) => onProposedAccept(id, pid, name)}
        onProposedDeny={(pid) => denyProposedTag(id, pid)}
        onToggleQuestion={noop}
        onQuoteHoverEnter={noop}
        onQuoteHoverLeave={noop}
        onPillHoverEnter={noop}
        onPillHoverLeave={noop}
        highlight={term ? [term] : undefined}
      />
    );
  };

  // Every state carries the zone title, as Discussion's do, so the lens opens at the same height
  // loading, failed or empty as it does with data (lens template). Every state also carries the one
  // live region, last and keyed, so it is the same element from the first render to the board and
  // across every board change: it says only how far reading has got. What could not be read is a
  // plain list (problemNotes), never live — a remounting region re-announced it on every move.
  const progress = (
    <p key="screens-progress" className={`screens-progress${boardShown ? "" : " bn-empty-state"}`} role="status">
      {progressText(data)}
    </p>
  );
  const shell = (body: React.ReactNode) => (
    <section ref={lensRef}>
      <SectionHeading key="screens-heading">{t("screens.title")}</SectionHeading>
      {body}
      {progress}
    </section>
  );
  // A failed look with screens already on the page keeps them, and looks again (the poll's retry).
  if (screensError && !data) return shell(<p className="bn-empty-state" role="alert">{t("screens.loadFailed")}</p>);
  if (quotesError) return shell(<p className="bn-empty-state" role="alert">{t("screens.quotesFailed")}</p>);
  if (!data) return shell(<p className="bn-empty-state" aria-busy="true">{t("screens.loading")}</p>);
  if (!data.enabled) return shell(<p className="bn-empty-state">{t("screens.off")}</p>);
  if (data.unavailable) return shell(<p className="bn-empty-state">{unavailableText(data.unavailable)}</p>);
  if (!data.videos) return shell(<p className="bn-empty-state">{t("screens.noVideo")}</p>);
  if (!screens.length) {
    const lines = problemNotes(data);
    if (!stillReading(data) && data.indexed > (data.blank ?? []).length) lines.push(t("screens.noneFound"));
    return shell(<NotesList lines={lines} className="bn-empty-state screens-notes" />);
  }
  return (
    <section
      ref={lensRef}
      className={`screens-lens${navShown ? "" : " nav-hidden"}`}
      style={{ "--screens-nav-w": `${NAV_W}px` } as React.CSSProperties}
      data-testid="screens-lens"
    >
      {navShown && <ScreenNav screens={screens} cur={cur} onPick={(i) => go(i)} byId={byId} hidden={store.hidden} />}
      {screen && (
        // Keyed by the screen alone: turning the carousel keeps the board (and its cross-fade, its
        // swipe lock, a selected card); another screen is another board.
        <ScreenBoard
          key={screen.key}
          projectId={projectId}
          screen={screen}
          tabIdx={tabIdx}
          onFlip={(j) => go(cur, j)}
          onShowOn={(dom, j) => go(cur, j, dom)}
          byId={byId}
          store={store}
          said={said}
          sequence={sequence}
          people={people}
          chosen={chosen}
          onChip={toggleChip}
          focusedId={focusedId}
          focusRequest={focusRequest}
          problems={problemNotes(data)}
          renderQuote={renderQuote}
        />
      )}
      {progress}
    </section>
  );
}

// ── Navigation ───────────────────────────────────────────────────────────

/** True once the element has scrolled into view (at once where there is no IntersectionObserver). */
function useSeen<T extends Element>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === "undefined");
  useEffect(() => {
    if (seen || !ref.current) return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) setSeen(true);
    }, { rootMargin: "200px" });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [seen]);
  return [ref, seen];
}

function NavThumb({ tab }: { tab: ScreenTab }) {
  // A study has dozens of screens: fetch a thumbnail only when its row is near the view, so the
  // board's own screengrab is not queued behind every one of them.
  const [ref, seen] = useSeen<HTMLSpanElement>();
  const { src } = useStill(seen ? tab : undefined, 240);
  return (
    <span ref={ref} className="screens-thumb-slot">
      {src ? <img alt="" src={src} /> : <span className="screens-thumb-empty" />}
    </span>
  );
}

function screenTitle(screen: Screen, tab?: ScreenTab): string {
  if (!screen.name.startsWith("/")) return screen.name.charAt(0).toUpperCase() + screen.name.slice(1);
  if (tab?.heading) return tab.heading;
  const hs = [...new Set(screen.tabs.map((t) => t.heading).filter(Boolean))];
  return hs.join(" · ") || screen.name;
}

/** "p1's screen at 00:12" with the time set as a timecode: the sentence is the locale's, split on its
 *  own {{time}} slot, so the word order is each language's (MiroExportPanel's approach, no <Trans>). */
function screenAt(template: string, time: string): React.ReactNode {
  const slot = template.indexOf("{{time}}");
  if (slot < 0) return template;
  return (
    <>
      {template.slice(0, slot)}
      <span className="timecode">{time}</span>
      {template.slice(slot + "{{time}}".length)}
    </>
  );
}

function ScreenNav({
  screens,
  cur,
  onPick,
  byId,
  hidden,
}: {
  screens: Screen[];
  cur: number;
  onPick: (i: number) => void;
  byId: Map<string, QuoteResponse>;
  hidden: Record<string, boolean>;
}) {
  const listRef = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]');
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  }, [cur]);
  const { t } = useTranslation();
  const participants = new Set(screens.flatMap((s) => s.tabs.map((tb) => tb.code))).size;
  return (
    <nav className="screens-nav" aria-label={t("screens.title")}>
      <div className="screens-nav-head">
        {t("screens.navSummary", {
          screens: t("screens.screenCount", { count: screens.length }),
          participants: t("screens.participantCount", { count: participants }),
        })}
      </div>
      <ol ref={listRef}>
        {screens.map((s, i) => {
          const codes = [...new Set(s.tabs.map((tb) => tb.code))];
          // What the board would show: each quote once, hidden ones not counted (its "N quotes").
          const said = new Set(
            s.tabs.flatMap((tb) => [...tb.pins.map((p) => p.dom_id), ...tb.loose]).filter((d) => byId.has(d) && !hidden[d]),
          ).size;
          return (
            <li key={s.key}>
              <a
                href={`#${s.key}`}
                aria-current={i === cur ? "true" : "false"}
                onClick={(e) => {
                  e.preventDefault();
                  onPick(i);
                }}
              >
                <span className={`screens-thumb${s.tabs.length > 1 ? " stacked" : ""}`}>
                  {s.tabs.slice(0, 3).map((tb) => (
                    <NavThumb key={`${tb.session_id}@${tb.t}`} tab={tb} />
                  ))}
                </span>
                <span>
                  <span className="screens-nav-title">{screenTitle(s)}</span>
                  {s.name.startsWith("/") && <span className="screens-nav-path">{s.name}</span>}
                  <span className="screens-nav-meta">
                    <span className="screens-count">{said}</span>
                    <span className="screens-codes">
                      {codes.slice(0, 12).map((c) => (
                        <span key={c} className="bn-speaker-badge-code">
                          {c}
                        </span>
                      ))}
                      {codes.length > 12 && <span className="screens-more">+{codes.length - 12}</span>}
                    </span>
                  </span>
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ── The board ────────────────────────────────────────────────────────────

interface BoardProps {
  projectId: string;
  screen: Screen;
  tabIdx: number;
  /** Turn the carousel to slide `j`. */
  onFlip: (j: number) => void;
  /** Turn to slide `j`, where card `dom` is linked, and bring it forward. */
  onShowOn: (dom: string, j: number) => void;
  byId: Map<string, QuoteResponse>;
  store: ReturnType<typeof useQuotesStore>;
  /** Every quote on this screen, once each, in time order (hidden ones not). */
  said: string[];
  sequence: Record<string, Sequence>;
  people: string[];
  /** The people whose quotes are in front; empty is everyone's. */
  chosen: Set<string>;
  onChip: (person: string) => void;
  focusedId: string | null;
  /** Move keyboard focus into this card once it has a place (after "On p2's screen"). */
  focusRequest: FocusRequest | null;
  /** Recordings that could not be read or held no text: a plain list, never live. */
  problems: string[];
  renderQuote: RenderQuote;
}

interface Geometry {
  stageW: number;
  /** The showing screengrab's size, and where it sits in the board. */
  W: number;
  H: number;
  sx: number;
  sy: number;
  /** Two columns, one, or rows: changes only at a threshold, with hysteresis (layout.ts). */
  mode: Mode;
}

const sameGeometry = (a: Geometry, b: Geometry) =>
  a.stageW === b.stageW && a.W === b.W && a.H === b.H && a.sx === b.sx && a.sy === b.sy && a.mode === b.mode;

interface Drag {
  dom: string;
  left: number;
  top: number;
  width: number;
  z: number;
}

interface Laid {
  comp: Composition;
  /** The side columns' height: the screengrab's, or more where a column runs past it. */
  colH: number;
  /** The board's least height, so a card dropped low over the screengrab is not cut off. */
  boardMin: number;
}

/** How long a card glides from its old place to its new one when the layout changes mode (ms). */
const GLIDE_MS = 260;

const boxOf = (p: Pin) => ({ x: p.box[0], y: p.box[1], w: p.box[2], h: p.box[3] });

/** A card's person and place among that person's quotes here: seen as a badge, heard as a sentence. */
function SequenceMark({ seq }: { seq: Sequence }) {
  const { t } = useTranslation();
  return (
    <>
      <span className="screens-seq" aria-hidden="true">
        <span className="screens-seq-code">{seq.person}</span>
        <span className="screens-seq-n">{seq.n}</span>
      </span>
      <span className="bn-sr-only">{t("screens.sequence", { code: seq.person, n: seq.n, total: seq.total })}</span>
    </>
  );
}

function ScreenBoard(props: BoardProps) {
  const { t } = useTranslation();
  const { projectId, screen, tabIdx, byId, store, said, sequence, people, chosen } = props;
  const { setFocus } = useFocus();
  const tab = screen.tabs[tabIdx];
  const total = screen.tabs.length;
  const multi = total > 1;
  const still = stillKey(tab.session_id, tab.t);
  const slides = useStills(screen.tabs, tabIdx, 1600);
  const { src, failed: stillFailed } = slides[tabIdx];
  const stageRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const shotRef = useRef<HTMLDivElement>(null);
  const carouselRef = useRef<HTMLDivElement>(null);
  const cardEls = useRef(new Map<string, HTMLElement>());
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [laid, setLaid] = useState<Laid | null>(null);
  const settled = useRef(false);
  const [leaders, setLeaders] = useState<{ id: string; d: string; end: [number, number]; muted: boolean }[]>([]);
  // Bumped when a glide ends, so the leaders are measured again where the cards came to rest.
  const [, setGlides] = useState(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  // The selected card: a press or keyboard focus selects it, never hover (the owner, 14 Oct 2026,
  // docs/design-screens.md §6.8). Selecting raises it and nothing else: a card keeps one size. A
  // press is remembered with the report's focus at that moment: once focus moves (J/K, Next Quote,
  // Escape through the report's own cascade, which takes Escape before the board can), the press
  // is stale and the focused card is the one in front.
  const [pressed, setPressed] = useState<{ id: string; focus: string | null } | null>(null);
  const focusNow = useRef(props.focusedId);
  useLayoutEffect(() => {
    focusNow.current = props.focusedId;
  });
  const lift = useCallback((id: string | null) => setPressed(id ? { id, focus: focusNow.current } : null), []);
  const unlift = useCallback((id: string) => setPressed((p) => (p?.id === id ? null : p)), []);
  const lifted = pressed && pressed.focus === props.focusedId ? pressed.id : null;
  const [drag, setDrag] = useState<Drag | null>(null);
  // The researcher's arrangement of this screengrab, as intent (layout.ts): re-read on every write,
  // including an undo of Tidy made after the board has moved on.
  const arrangeVersion = useSyncExternalStore(subscribeArrangement, arrangementVersion, arrangementVersion);
  const placements = useMemo(
    () => placementsFor(projectId, still),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectId, still, arrangeVersion],
  );
  const [menu, setMenu] = useState<{ x: number; y: number; items: { label: string; run: () => void }[] } | null>(null);
  // Stable, so the menu's effect (which focuses its first item, and returns focus on close) runs
  // once per opening rather than on every render of the board.
  const closeMenu = useCallback(() => setMenu(null), []);
  const [hiddenOpen, setHiddenOpen] = useState(false);

  const visible = (dom: string) => byId.has(dom) && !store.hidden[dom];
  const onScreen = useMemo(() => new Set(said), [said]);
  // LINKED: the quotes whose words are on the screengrab showing — this slide's pins, and only
  // these. A quote linked on another participant's version is listed under it, offering that
  // version ("On p2's screen"). No screengrab to pin to: nothing is linked.
  const pins = useMemo(() => {
    if (stillFailed) return [];
    const seen = new Set<string>();
    return tab.pins.filter((p) => {
      if (seen.has(p.dom_id) || !byId.has(p.dom_id) || store.hidden[p.dom_id]) return false;
      seen.add(p.dom_id);
      return true;
    });
  }, [tab, stillFailed, byId, store.hidden]);
  const pinByDom = useMemo(() => new Map(pins.map((p) => [p.dom_id, p])), [pins]);
  // For an unlinked card: the first other version whose screengrab links it.
  const linkedOn = useMemo(() => {
    const m = new Map<string, number>();
    screen.tabs.forEach((tb, j) => {
      if (j !== tabIdx) for (const p of tb.pins) if (!m.has(p.dom_id)) m.set(p.dom_id, j);
    });
    return m;
  }, [screen, tabIdx]);
  const personOf = (d: string) => byId.get(d)?.participant_id ?? "";
  // A person chip on: the other people's cards step back (by colour, as a selection's do).
  const muted = (d: string) => chosen.size > 0 && !chosen.has(personOf(d));
  // The researcher's arrangement of the cards on the board: what the arrangement control, the
  // right-click menu and the Mac's View ▸ Tidy all count, so the three agree.
  const arranged = Object.fromEntries(Object.entries(placements).filter(([d]) => visible(d))) as Record<string, Placement>;
  const custom = Object.keys(arranged).length > 0;
  // A placed card is placed against the screengrab. Without one to measure (it failed to load, or
  // has no size yet) a placed card is listed with the rest, not held hidden for a spot that never
  // comes.
  const placeable = !!geo && geo.H > 0;
  const mine: Record<string, Placement> = placeable ? arranged : {};
  // Over the screengrab: where the researcher dropped it. Beside it: a placed card's intent.
  const over = new Set(Object.keys(mine).filter((d) => mine[d].kind === "over"));
  // A card being dragged leaves its edge (or the list) for the free layer until it is dropped.
  const dragOut = drag && !over.has(drag.dom) ? drag.dom : null;
  const hiddenHere = useMemo(() => {
    const seen = new Set<string>();
    for (const tb of screen.tabs) {
      for (const d of [...tb.pins.map((p) => p.dom_id), ...tb.loose]) if (byId.has(d) && store.hidden[d]) seen.add(d);
    }
    return [...seen];
  }, [screen, byId, store.hidden]);
  // The selected card: pressed or focused here, else the report's focused quote if it is on this
  // board (J/K, Next Quote) — it comes forward and its line lights.
  const lit = lifted ?? (props.focusedId && onScreen.has(props.focusedId) ? props.focusedId : null);

  const mode: Mode = geo?.mode ?? "r";
  // The cards on the edges: every card the researcher placed beside the screengrab, and every linked
  // card they did not place. Placed cards win their spot; the rest are automatic (layout.ts).
  const edgeCards: BoardCard[] = [
    ...Object.keys(mine).flatMap((d): BoardCard[] => {
      const p = mine[d];
      return p.kind === "edge" && d !== dragOut ? [{ id: d, height: 0, placed: { side: p.side, frac: p.frac, z: p.z } }] : [];
    }),
    ...pins.filter((p) => !(p.dom_id in mine) && p.dom_id !== dragOut).map((p) => ({ id: p.dom_id, height: 0, anchor: boxOf(p) })),
  ];
  const edgeOf = new Map(edgeCards.map((c) => [c.id, cardEdge(c, mode)]));
  const onEdge = (e: Edge) => edgeCards.filter((c) => edgeOf.get(c.id) === e).map((c) => c.id);
  const columns = boardColumns(mode, { L: onEdge("L").length > 0, R: onEdge("R").length > 0 });
  // Everything else said here: under the screengrab, in time order.
  const listed = said.filter((d) => !pinByDom.has(d) && !(d in mine) && d !== dragOut);

  // Measure the stage and the showing screengrab, and pick the mode (with hysteresis: the previous
  // mode is part of the answer).
  const measure = useCallback(() => {
    const stage = stageRef.current, shot = shotRef.current;
    if (!stage || !shot) return;
    const img = shot.querySelector<HTMLImageElement>("img.is-current");
    const stageW = stage.clientWidth;
    const W = img?.clientWidth ?? shot.clientWidth;
    const H = img?.clientHeight ?? 0;
    setGeo((old) => {
      const g = { stageW, W, H, sx: shot.offsetLeft, sy: shot.offsetTop, mode: stageMode(stageW, old?.mode) };
      return old && sameGeometry(old, g) ? old : g;
    });
  }, []);
  useLayoutEffect(() => {
    measure();
    const ro = new ResizeObserver(measure);
    if (stageRef.current) ro.observe(stageRef.current);
    if (shotRef.current) ro.observe(shotRef.current);
    return () => ro.disconnect();
  }, [measure, src]);

  // Place the edges once the cards have heights. Deliberately runs after every render (a card's
  // height changes with tags, edits and width; a band's height moves the screengrab down) and sets
  // state only when the placement changes. `settled` says this commit's placement held, which is
  // when the glide below may measure where everything went.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    measure();
    if (!geo || !geo.H) {
      settled.current = false;
      return;
    }
    const cards = edgeCards.map((c) => ({ ...c, height: cardEls.current.get(c.id)?.offsetHeight ?? 120 }));
    const comp = composeBoard(cards, geo.mode, { W: geo.W, H: geo.H });
    let boardMin = 0;
    for (const d of over) {
      const s = mine[d];
      if (s.kind !== "over") continue;
      const h = cardEls.current.get(d)?.offsetHeight ?? 120;
      boardMin = Math.max(boardMin, geo.sy + s.y * geo.H + h);
    }
    const next: Laid = { comp, colH: Math.max(geo.H, comp.colBottom), boardMin };
    const same = laid !== null && JSON.stringify(laid) === JSON.stringify(next);
    settled.current = same;
    if (!same) setLaid(next);
  });

  // Leaders, once everything has settled; after every render for the same reason, set on change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    const board = boardRef.current;
    if (!geo || !geo.H || !board || !laid) return;
    const bb = board.getBoundingClientRect();
    const next: { id: string; d: string; end: [number, number]; muted: boolean }[] = [];
    for (const p of pins) {
      const free = over.has(p.dom_id) || drag?.dom === p.dom_id;
      const edge = free ? undefined : laid.comp.at[p.dom_id]?.edge;
      if (!free && !edge) continue;
      const el = cardEls.current.get(p.dom_id);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const card = { left: r.left - bb.left, top: r.top - bb.top, width: r.width, height: r.height };
      const elem = {
        left: geo.sx + p.box[0] * geo.W, top: geo.sy + p.box[1] * geo.H,
        width: p.box[2] * geo.W, height: p.box[3] * geo.H,
      };
      next.push({ id: p.dom_id, ...leaderPath(card, elem, edge), muted: muted(p.dom_id) });
    }
    setLeaders((old) => (JSON.stringify(old) === JSON.stringify(next) ? old : next));
  });

  // When the layout changes mode (two columns, one, rows), each card glides from where it was to
  // where it now is (FLIP): measured once placement has settled, against the last settled places.
  // Instant under reduced motion. Only at a mode change: within a mode the cards follow the resize.
  // The leaders are measured from the cards' rectangles, which include the glide's transform, so
  // they are measured again when the glide ends — or they would stay where the cards set off.
  const flipFrom = useRef<{ mode: Mode; at: Map<string, [number, number]> } | null>(null);
  useLayoutEffect(() => {
    const board = boardRef.current;
    if (!geo || !board || !settled.current) return;
    const bb = board.getBoundingClientRect();
    const now = new Map<string, [number, number]>();
    for (const [id, el] of cardEls.current) {
      const r = el.getBoundingClientRect();
      now.set(id, [r.left - bb.left, r.top - bb.top]);
    }
    const from = flipFrom.current;
    flipFrom.current = { mode: geo.mode, at: now };
    if (!from || from.mode === geo.mode || reducedMotion()) return;
    const ends: Promise<unknown>[] = [];
    for (const [id, el] of cardEls.current) {
      const a = from.at.get(id), b = now.get(id);
      if (!a || !b || (a[0] === b[0] && a[1] === b[1]) || typeof el.animate !== "function") continue;
      const glide = el.animate(
        [{ transform: `translate(${a[0] - b[0]}px, ${a[1] - b[1]}px)` }, { transform: "translate(0, 0)" }],
        { duration: GLIDE_MS, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      ) as Animation | undefined;
      if (glide?.finished) ends.push(glide.finished);
    }
    // A cancelled glide rejects its `finished`: the cards have still come to rest.
    if (ends.length) {
      Promise.allSettled(ends).then(() => {
        if (alive.current) setGlides((g) => g + 1);
      });
    }
  });

  // "On p2's screen": once the carousel has turned, keyboard focus goes into that card. The card has
  // just moved from the list to a margin, where it is hidden (visibility) until placement gives it a
  // spot, and a hidden element cannot take focus — focus() fails without a word and focus falls to
  // the page. So wait for the spot; and check focus really landed, else the board's title.
  // A request made before this board existed (on another screen) is not this board's.
  const focusDone = useRef(props.focusRequest?.seq ?? 0);
  useLayoutEffect(() => {
    const req = props.focusRequest;
    if (!req || req.seq <= focusDone.current) return;
    const el = cardEls.current.get(req.dom);
    const waiting = el?.style.visibility === "hidden" && !stillFailed && (!src || (!!geo && geo.H > 0));
    if (waiting) return;
    focusDone.current = req.seq;
    const target = el?.querySelector<HTMLElement>("a[href], button:not(.screens-elsewhere)") ?? null;
    target?.focus({ preventScroll: true });
    if (!target || document.activeElement !== target) focusLensHeading(stageRef.current?.closest(".screens-lens"));
  });

  // A press on a card brings it forward; Escape, or a press anywhere that is not a card, puts it back.
  // One listener for the board rather than a click handler per card: the keyboard's way in is focus
  // (below), so the cards stay plain wrappers. A press on a drag grip never arrives here (the grip
  // stops it) and lifts its card on release instead, when it was not a drag. Escape is under the
  // same guards as the arrow keys.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !keyIsOurs(e)) return;
      // Deselect in both places. The shared quote card keeps its own focus (.bn-focused), and a
      // focused card is raised: clearing only ours left the "deselected" card on top of its
      // neighbour in a stack (measured, 14 Oct 2026).
      lift(null);
      setFocus(null, { scroll: false });
    };
    const onDown = (e: PointerEvent) => {
      const card = e.target instanceof Element ? e.target.closest<HTMLElement>(".screens-card[data-dom]") : null;
      lift(card ? card.dataset.dom ?? null : null);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [setFocus, lift]);

  // One slide per horizontal swipe, over the carousel. Not passive: a horizontal swipe here is the
  // carousel's, and must not also scroll the page sideways or send the browser Back. A vertical one
  // is left alone. The lock lives as long as the board, so a turn does not reset it mid-swipe.
  const flipBy = useRef<(dir: 1 | -1) => void>(() => {});
  useEffect(() => {
    flipBy.current = (dir) => props.onFlip((tabIdx + dir + total) % total);
  });
  useEffect(() => {
    const el = carouselRef.current;
    if (!el || !multi) return;
    const swipe = makeSwipe((dir) => flipBy.current(dir));
    const onWheel = (e: WheelEvent) => {
      if (swipe(e.deltaX, e.deltaY)) e.preventDefault();
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [multi]);

  // Drag to rearrange: the card's top edge and the margin under its timecode are the grips. Nothing
  // moves, and nothing is saved, until the pointer has travelled DRAG_THRESHOLD: a click on a grip
  // is not a drag (useVerticalDragResize's 3px). The window listeners belong to this screengrab: if
  // the board remounts or the carousel turns mid-drag they are removed, so a release cannot write a
  // spot against the previous screengrab.
  const endDrag = useRef<(() => void) | null>(null);
  useEffect(
    () => () => {
      endDrag.current?.();
      setDrag(null);
    },
    [still],
  );
  const startDrag = (dom: string) => (e: React.PointerEvent) => {
    if (e.button !== 0 || !geo || !boardRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    const el = cardEls.current.get(dom);
    if (!el) return;
    endDrag.current?.();
    const bb = boardRef.current.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const z = topZ(projectId) + 1;
    const start = { x: e.clientX, y: e.clientY, left: r.left - bb.left, top: r.top - bb.top };
    let moved = false;
    const at = (ev: PointerEvent) => ({
      left: start.left + ev.clientX - start.x,
      top: Math.max(0, start.top + ev.clientY - start.y),
    });
    // Listen on the window, not the grip: starting the drag moves the card into the free layer,
    // which remounts it, and a detached grip receives no more pointer events. The card follows the
    // pointer at most once a frame: a pointermove can fire several times a frame, and each
    // setDrag re-renders the whole board.
    let frame = 0;
    let latest: PointerEvent | null = null;
    const move = (ev: PointerEvent) => {
      if (!moved && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < DRAG_THRESHOLD) return;
      if (!moved) lift(null);
      moved = true;
      latest = ev;
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (latest) setDrag({ dom, ...at(latest), width: r.width, z });
      });
    };
    const detach = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      endDrag.current = null;
    };
    function up(ev: PointerEvent) {
      detach();
      if (!moved) {
        lift(dom); // a press on the grip that never became a drag is a press on the card
        return;
      }
      const { left, top } = at(ev);
      // Stored as intent: beside the screengrab on the side its centre fell, and how far down that
      // edge; or over it, where the researcher put it.
      putPlacement(projectId, still, dom, placementFromDrop(
        { left, top, width: r.width },
        { left: geo!.sx, top: geo!.sy, width: geo!.W, height: geo!.H }, z));
      setDrag(null);
    }
    endDrag.current = detach;
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  };

  // The board's wrapper places, lifts and drags a card; the card itself is the Quotes lens's.
  const cardFor = (dom: string, style: React.CSSProperties) => {
    const q = byId.get(dom);
    if (!q) return null;
    const pin = pinByDom.get(dom);
    const seq = sequence[dom];
    // Unlinked here, linked on another participant's version: offer that version.
    const elsewhere = pin ? -1 : linkedOn.get(dom) ?? -1;
    const cls = [
      "screens-card", lit === dom && "is-lifted", drag?.dom === dom && "is-dragging", dom in arranged && "is-placed",
      muted(dom) && "is-muted",
    ]
      .filter(Boolean)
      .join(" ");
    return (
      // A card comes forward on a press (the board's listener above), and when keyboard focus
      // enters it so Tab never lands on a control hidden under the next card in a stack. Never on
      // hover. Rearranging is pointer-only for now.
      <div
        key={dom}
        ref={(el) => {
          if (el) cardEls.current.set(dom, el);
          else cardEls.current.delete(dom);
        }}
        className={cls}
        style={style}
        data-dom={dom}
        data-pin={pin ? dom : undefined}
        onFocus={() => !drag && lift(dom)}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) unlift(dom);
        }}
      >
        <span className="screens-grip screens-grip-top" aria-hidden="true" onPointerDown={startDrag(dom)} />
        <span className="screens-grip screens-grip-side" aria-hidden="true" onPointerDown={startDrag(dom)} />
        {seq && <SequenceMark seq={seq} />}
        {props.renderQuote(q, pin?.phrase ?? "")}
        {elsewhere >= 0 && (
          <button type="button" className="screens-elsewhere" onClick={() => props.onShowOn(dom, elsewhere)}>
            {t("screens.onScreen", { code: screen.tabs[elsewhere].code })}
          </button>
        )}
      </div>
    );
  };

  const spot = (dom: string) => laid?.comp.at[dom];
  const inColumn = (dom: string): React.CSSProperties => {
    const s = spot(dom);
    return s ? ({ top: s.top, "--stack": s.z } as React.CSSProperties) : { top: 0, visibility: "hidden" };
  };
  const inBand = (dom: string): React.CSSProperties => {
    const s = spot(dom);
    return s ? { left: s.left, top: s.top, width: CARD_W } : { left: 0, top: 0, width: CARD_W, visibility: "hidden" };
  };
  const freeStyle = (dom: string): React.CSSProperties => {
    if (drag?.dom === dom) return { left: drag.left, top: drag.top, width: drag.width, zIndex: drag.z };
    const s = mine[dom];
    if (!geo || !s || s.kind !== "over") return { visibility: "hidden" };
    return { left: geo.sx + s.x * geo.W, top: geo.sy + s.y * geo.H, width: CARD_W, zIndex: s.z };
  };

  // Tidy: every card on this screengrab back to automatic. Undoable with ⌘Z through the report's
  // one undo stack, so it needs no confirm.
  const tidy = () => {
    // Offered while the arrangement is custom (`custom`, the one count); it clears everything kept
    // for this screengrab, a hidden quote's spot included, and undo puts all of it back.
    if (!custom) return;
    const before = placementsFor(projectId, still);
    // Tidy removes its own button (and the menu that offered it closes), so focus goes to the
    // lens's title rather than to the page.
    const active = document.activeElement;
    const lens = stageRef.current?.closest(".screens-lens");
    const keepFocus = active instanceof Element && !!active.closest(".screens-arrangement, .screens-menu");
    setPlacements(projectId, still, {});
    if (keepFocus) requestAnimationFrame(() => focusLensHeading(lens));
    pushUndo({
      action: "tidy",
      undo: () => setPlacements(projectId, still, before),
      redo: () => setPlacements(projectId, still, {}),
    });
    announce(i18n.t("screens.arrangementAutomatic"));
  };
  // View ▸ Tidy on the Mac enables only while this board's arrangement is custom: say so on mount
  // and on every change, and say "not custom" when the board goes (the Mac's mirror would
  // otherwise keep the last board's answer).
  useEffect(() => {
    postScreensArrangement(custom);
  }, [custom]);
  useEffect(() => () => postScreensArrangement(false), []);
  // View ▸ Tidy on the Mac (bn:menu-action), for whichever screengrab is showing.
  const tidyNow = useRef(tidy);
  useEffect(() => {
    tidyNow.current = tidy;
  });
  useEffect(() => {
    const onMenu = (e: Event) => {
      if ((e as CustomEvent<{ action?: string }>).detail?.action === "tidy") tidyNow.current();
    };
    window.addEventListener("bn:menu-action", onMenu);
    return () => window.removeEventListener("bn:menu-action", onMenu);
  }, []);

  // Right-click: "Return to automatic" on a card the researcher placed, "Tidy" anywhere on the board
  // once something is placed. The keyboard's context-menu key raises the same event. Elsewhere, and
  // with nothing to offer, the browser's own menu shows.
  useEffect(() => {
    const onMenu = (e: MouseEvent) => {
      const stage = stageRef.current;
      if (!stage || !(e.target instanceof Element) || !stage.contains(e.target)) return;
      const card = e.target.closest<HTMLElement>(".screens-card[data-dom]")?.dataset.dom;
      const items: { label: string; run: () => void }[] = [];
      // The same count as the arrangement control and View ▸ Tidy: the cards on the board.
      if (card && card in arranged) {
        items.push({ label: i18n.t("screens.returnToAutomatic"), run: () => clearPlacement(projectId, still, card) });
      }
      if (custom) items.push({ label: i18n.t("screens.tidy"), run: tidy });
      if (items.length === 0) return;
      e.preventDefault();
      const r = stage.getBoundingClientRect();
      setMenu({ x: e.clientX - r.left, y: e.clientY - r.top, items });
    };
    document.addEventListener("contextmenu", onMenu);
    return () => document.removeEventListener("contextmenu", onMenu);
  });

  const counterItems: CounterItem[] = hiddenHere.map((d) => {
    const q = byId.get(d)!;
    return {
      domId: d, timecode: formatTimecode(q.start_timecode), seconds: q.start_timecode,
      participantId: q.participant_id, previewText: store.edits[d] ?? q.text, hasMedia: false,
    };
  });

  // The person chips: toggle buttons, whose quotes are in front. They never turn the carousel.
  const who =
    people.length > 1 ? (
      <span className="screens-who" role="group" aria-label={t("screens.whoseQuotes")}>
        {people.map((p) => (
          <button key={p} type="button" aria-pressed={chosen.has(p)} onClick={() => props.onChip(p)}>
            <PersonBadge code={p} role="participant" />
          </button>
        ))}
      </span>
    ) : people.length === 1 ? (
      <span className="screens-who">
        <PersonBadge code={people[0]} role="participant" />
      </span>
    ) : null;

  // One highlight per line on the screengrab, however many quotes are about it: they share it, and
  // its anchor, and their leaders fan into one point.
  const lines = new Map<string, { box: Pin["box"]; ids: string[] }>();
  for (const p of pins) {
    const k = p.box.join(",");
    const line = lines.get(k) ?? { box: p.box, ids: [] };
    line.ids.push(p.dom_id);
    lines.set(k, line);
  }
  const ends = new Map<string, { end: [number, number]; on: boolean; muted: boolean }>();
  for (const l of leaders) {
    const k = l.end.join(",");
    const e = ends.get(k);
    ends.set(k, { end: l.end, on: (e?.on ?? false) || lit === l.id, muted: (e?.muted ?? true) && l.muted });
  }

  const captionTemplate = t("screens.slideCaption", { code: tab.code, n: tabIdx + 1, total });
  const [dot0, dot1] = dotWindow(total, tabIdx);
  const flipTo = (dir: 1 | -1) => props.onFlip((tabIdx + dir + total) % total);
  const bandT = onEdge("T"), bandB = onEdge("B");
  const quoteCount = said.length;
  return (
    <>
      <SectionHeading action={who}>{screenTitle(screen, tab)}</SectionHeading>
      <p className="screens-sub">
        {screen.name.startsWith("/") && <code>{screen.name}</code>}
        {/* With several versions the carousel's caption says whose screen, and when. */}
        {!multi && <span>{screenAt(t("screens.screenAt", { code: tab.code }), formatTimecode(tab.t))}</span>}
        <span>
          {people.length > 1
            ? t("screens.quoteCountFrom", { count: quoteCount, people: people.length })
            : t("screens.quoteCount", { count: quoteCount })}
        </span>
        <span className="screens-hidden-slot">
          <Counter
            count={hiddenHere.length}
            items={counterItems}
            isOpen={hiddenOpen}
            onToggle={() => setHiddenOpen((o) => !o)}
            onUnhide={(d) => unhideQuotes([d])}
            onUnhideAll={() => {
              unhideQuotes(hiddenHere);
              setHiddenOpen(false);
            }}
          />
        </span>
        {custom && (
          // At rest it says what the arrangement is; on hover and on keyboard focus, what pressing it
          // does. Both words share one fixed cell, so nothing moves when they swap, and the
          // accessible name says both, once.
          <button className="screens-arrangement" aria-label={t("screens.arrangementCustomTidy")} onClick={tidy}>
            <span className="screens-arrangement-state" aria-hidden="true">{t("screens.arrangementCustom")}</span>
            <span className="screens-arrangement-act" aria-hidden="true">{t("screens.tidy")}</span>
          </button>
        )}
      </p>
      <NotesList lines={props.problems} />
      <div className={`screens-stage${lit ? " focus" : ""}${drag ? " dragging" : ""}${chosen.size ? " chosen" : ""}`} ref={stageRef}>
        <div
          className={`screens-board cols-${columns} mode-${mode}`}
          ref={boardRef}
          style={{ minHeight: laid?.boardMin || undefined }}
        >
          <div className={`screens-band screens-band-t${bandT.length ? " has-cards" : ""}`} style={{ height: bandT.length ? laid?.comp.band.T ?? 0 : 0 }}>
            {bandT.map((d) => cardFor(d, inBand(d)))}
          </div>
          <div className={`screens-col screens-col-l${laid?.comp.stacked.L ? " stacked" : ""}`} style={{ height: laid?.colH || undefined }}>
            {onEdge("L").map((d) => cardFor(d, inColumn(d)))}
          </div>
          <div className="screens-shot" ref={shotRef}>
            {/* The carousel: one participant's version at a time, in a frame that cross-fades.
                Keyboard: Tab reaches it, ←/→ turn it (the lens's keys), and each turn is announced
                ("2 of 3"). The chevrons and dots are the pointer's: revealed on hover, never by
                focus, and not tab stops. */}
            <div
              ref={carouselRef}
              className={`screens-carousel${multi ? " is-multi" : ""}`}
              role={multi ? "group" : undefined}
              // A fixed name: the slide is said by announce() as the carousel turns, so a name that
              // changed with it would be read a second time.
              aria-label={multi ? t("screens.versionsLabel") : undefined}
              aria-roledescription={multi ? t("screens.carouselRole") : undefined}
              aria-keyshortcuts={multi ? "ArrowLeft ArrowRight" : undefined}
              title={multi ? t("screens.versionsKeys") : undefined}
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a carousel's keyboard stop (APG): ←/→ turn it
              tabIndex={multi ? 0 : undefined}
            >
              <div className="screens-slides">
                {slides.map((sl, j) =>
                  sl.src ? (
                    <img
                      key={`${screen.tabs[j].session_id}@${screen.tabs[j].t}`}
                      className={`screens-slide${j === tabIdx ? " is-current" : ""}`}
                      alt={j === tabIdx ? t("screens.stillAlt", { code: tab.code, title: screenTitle(screen, tab), time: formatTimecode(tab.t) }) : ""}
                      aria-hidden={j === tabIdx ? undefined : true}
                      src={sl.src}
                    />
                  ) : null,
                )}
                {!src && (
                  <div className="screens-shot-wait">
                    {stillFailed && <span className="screens-shot-error">{t("screens.stillUnavailable")}</span>}
                  </div>
                )}
                {geo &&
                  [...lines.entries()].map(([k, l]) => (
                    <div
                      key={k}
                      className={`screens-hl${lit && l.ids.includes(lit) ? " on" : ""}${l.ids.every(muted) ? " is-muted" : ""}`}
                      style={{
                        left: l.box[0] * geo.W - 3, top: l.box[1] * geo.H - 3,
                        width: l.box[2] * geo.W + 6, height: l.box[3] * geo.H + 6,
                      }}
                    />
                  ))}
              </div>
              {multi && (
                <>
                  <button type="button" tabIndex={-1} className="screens-chev screens-chev-prev"
                    aria-label={t("screens.previousScreengrab")} onClick={() => flipTo(-1)}>
                    <span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5" /></svg></span>
                  </button>
                  <button type="button" tabIndex={-1} className="screens-chev screens-chev-next"
                    aria-label={t("screens.nextScreengrab")} onClick={() => flipTo(1)}>
                    <span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" /></svg></span>
                  </button>
                </>
              )}
            </div>
            {multi && (
              <div className="screens-carousel-line">
                <span className="screens-dots">
                  {Array.from({ length: dot1 - dot0 }, (_, k) => dot0 + k).map((j) => (
                    <button
                      key={j}
                      type="button"
                      tabIndex={-1}
                      aria-label={t("screens.announceParticipant", { code: screen.tabs[j].code })}
                      aria-current={j === tabIdx ? "true" : undefined}
                      className={`screens-dot${j === tabIdx ? " is-current" : ""}${(j === dot0 && dot0 > 0) || (j === dot1 - 1 && dot1 < total) ? " is-edge" : ""}`}
                      onClick={() => props.onFlip(j)}
                    />
                  ))}
                </span>
                <span className="screens-caption">{screenAt(captionTemplate, formatTimecode(tab.t))}</span>
                {/* For a sighted keyboard user: shown while the carousel has keyboard focus. */}
                <span className="screens-keys" aria-hidden="true">← →</span>
              </div>
            )}
          </div>
          <div className={`screens-col screens-col-r${laid?.comp.stacked.R ? " stacked" : ""}`} style={{ height: laid?.colH || undefined }}>
            {onEdge("R").map((d) => cardFor(d, inColumn(d)))}
          </div>
          <div className={`screens-band screens-band-b${bandB.length ? " has-cards" : ""}`} style={{ height: bandB.length ? laid?.comp.band.B ?? 0 : 0 }}>
            {bandB.map((d) => cardFor(d, inBand(d)))}
          </div>
          <svg className="screens-leaders" aria-hidden="true">
            {leaders.map((l) => (
              <path key={l.id} d={l.d} className={[lit === l.id && "on", l.muted && "is-muted"].filter(Boolean).join(" ") || undefined} />
            ))}
            {[...ends.entries()].map(([k, e]) => (
              <circle key={k} cx={e.end[0]} cy={e.end[1]} r={2.5}
                className={[e.on && "on", e.muted && "is-muted"].filter(Boolean).join(" ") || undefined} />
            ))}
          </svg>
          <div className="screens-free">
            {[...over, ...(dragOut ? [dragOut] : [])]
              .filter((d, i, a) => a.indexOf(d) === i)
              .map((d) => cardFor(d, freeStyle(d)))}
          </div>
        </div>
        <div className="screens-loose">
          {listed.map((d) => cardFor(d, {}))}
        </div>
        {menu && <BoardMenu {...menu} onClose={closeMenu} />}
      </div>
    </>
  );
}

/**
 * The board's right-click menu: "Return to automatic" on a placed card, "Tidy" once anything is
 * placed. A small menu of the lens's own (no shared context menu exists in the SPA): focus goes to
 * its first item, ↑/↓ move, Enter or a click runs, Escape or a press outside closes.
 */
function BoardMenu(props: {
  x: number;
  y: number;
  items: { label: string; run: () => void }[];
  onClose: () => void;
}) {
  const { x, y, items, onClose } = props;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const lens = el?.closest(".screens-lens");
    el?.querySelector<HTMLButtonElement>("button")?.focus();
    // Focus moving to something outside the menu (Tab) closes it. A focusout with no new target is
    // left to the pointerdown check below: WebKit does not focus a clicked button, so a click on an
    // item would otherwise close the menu before the click lands.
    const onFocusOut = (e: FocusEvent) => {
      if (e.relatedTarget instanceof Node && !el?.contains(e.relatedTarget)) onClose();
    };
    el?.addEventListener("focusout", onFocusOut);
    const onDown = (e: PointerEvent) => {
      if (!(e.target instanceof Node && ref.current?.contains(e.target))) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("pointerdown", onDown, true);
    document.addEventListener("keydown", onKey, true);
    return () => {
      el?.removeEventListener("focusout", onFocusOut);
      document.removeEventListener("pointerdown", onDown, true);
      document.removeEventListener("keydown", onKey, true);
      // Closed with focus still in it (or dropped to the page): give it back to where it was, or
      // to the lens's title if that has gone.
      const now = document.activeElement;
      if (now === null || now === document.body || (el && el.contains(now))) {
        if (opener && opener !== document.body && opener.isConnected) opener.focus({ preventScroll: true });
        else focusLensHeading(lens);
      }
    };
  }, [onClose]);
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    e.stopPropagation();
    const buttons = [...(ref.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = (at + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next]?.focus();
  };
  return (
    <div ref={ref} className="screens-menu" role="menu" tabIndex={-1} style={{ left: x, top: y }} onKeyDown={onKeyDown}>
      {items.map((it) => (
        <button
          key={it.label}
          role="menuitem"
          tabIndex={-1}
          className="screens-menu-item"
          onClick={() => {
            onClose();
            it.run();
          }}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}
