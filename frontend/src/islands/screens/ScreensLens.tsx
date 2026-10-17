/**
 * The Screens lens: every screen the participants were on, a large screengrab of each, and every
 * quote said there around it — the ones whose words are on the screengrab in its margins, joined to
 * the line they read by a leader, the rest in a list under it.
 *
 * docs/design-screens.md S5. Data from GET /screens (server/routes/screens.py), stills from
 * GET /screens/still. Quotes are the report's own: the lens joins the screens' DOM ids to the
 * quotes store, and every quote is drawn by the Quotes lens's own card (islands/QuoteCard.tsx).
 * Focus and selection are the Quotes lens's too — FocusContext, the shared .bn-focused and
 * .bn-selected, and the report's own keys (J/K, ⇧J/K, ⇧-click, ⌘A over the order this lens
 * registers) — so what is learnt on one lens works on the other. The board only positions the
 * cards: it wraps each one to place it, raise the focused one, and drag it.
 *
 * Structured like its nearest sibling, the Discussion lens: a navigator column of its own that runs
 * the full height and resizes like the guide (navPanel.ts), the zone title on the shared datum
 * (`.center > main > section:first-of-type > .section-heading`), the same key guards.
 *
 * A screen is one place for everything about it: every participant's version of it can show, one at
 * a time, chosen from one unit on the heading line (carousel.ts), and the quote set is the same
 * whichever version shows. The version decides only which quotes are LINKED — on its screengrab, so
 * in a margin with a leader. Placement and the researcher's arrangement are layout.ts; the order
 * the shared keys walk is narrative.ts.
 *
 * Offered when the project has screens, or recordings still being read (availability.ts, the one
 * rule the nav and the Mac's lens rail follow). Every sentence is a `screens.*` locale key.
 */

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useReducer, useRef, useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import { Counter, type CounterItem } from "../../components/Counter";
import { PersonBadge } from "../../components/PersonBadge";
import { SectionHeading } from "../../components/SectionHeading";
import type { TagVocabularyGroup } from "../../components/TagInput";
import { TimecodeLink } from "../../components/TimecodeLink";
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
import { installLiveResizeWatch, isLiveResizing, subscribeLiveResize } from "../../utils/liveResize";
import { wholeWordsTerm, type SearchTerm } from "../../utils/searchMatch";
import { deriveTagVisibility, type TagGroupMeta } from "../../utils/tagVisibility";
import type { QuoteResponse, QuotesListResponse } from "../../utils/types";
import { QuoteCard } from "../QuoteCard";
import { MIN_WIDTH, RESIZE_STEP } from "../discussion/split";
import {
  arrangementFor,
  arrangementsLoaded,
  arrangementVersion,
  autoIntent,
  boardColumns,
  CARD_W,
  COLUMN_GUTTER,
  COLUMN_W,
  composeBoard,
  customFrame,
  edgeFor,
  intentFromRect,
  leaderPath,
  loadArrangements,
  migrateArrangement,
  reloadArrangements,
  rectFromIntent,
  MOVE_STEP,
  setArrangement,
  stageMode,
  subscribeArrangement,
  topZ,
  versionKey,
  type Arrangement,
  type BoardCard,
  type Composition,
  type Edge,
  type Intent,
  type Mode,
  type Rect,
} from "./layout";
import { Lru, makeSwipe, slideWindow, VERSION_BADGES_MAX } from "./carousel";
import { readingOrder, type Seen } from "./narrative";
import { markScreensFound } from "./availability";
import { postScreensArrangement } from "../../shims/bridge";
import { reportScreensNav, useScreensNav } from "./navPanel";
import { setScreensCount } from "./screensCount";
import { featureFlags } from "../../utils/featureFlags";
import { choosePaper, papers, readAccents, samplePaper, type Rgb } from "./paper";
import "./screens.css";
import { screenRef, screensArrival, screenTitle, stillUrl } from "./screenModel";
import { Icon } from "../../components/Icon";
import { markArrived } from "../../utils/arrival";

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

/** Fetch a still once, however many ask for it; null when there is none. */
function fetchStill(url: string): Promise<string | null> {
  let p = stillWaiters.get(url);
  if (!p) {
    p = apiGet<{ src: string }>(url)
      .then(async (r) => {
        // A board still's paper is sampled now, off the DOM, and cached before the still itself, so
        // the still and its paper arrive together and a turn never shows one without the other.
        if (cacheFor(url) === boardStills) {
          const paper = await samplePaper(r.src).catch(() => null);
          if (paper) papers.set(url, paper);
        }
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

/** The navigator's starting width, and the one set on the lens as `--screens-nav-w` for
 *  screens.css's grid until the researcher drags the split. */
export const NAV_W = 280;
/** Its widest: past this the board is what the researcher came for. */
const NAV_MAX = 480;
/** The navigator's width, remembered per viewer (Discussion's guide keeps its own the same way). */
const NAV_WIDTH_KEY = "bn-screens-nav-width";

function readNavWidth(): number | null {
  try {
    const v = Number(localStorage.getItem(NAV_WIDTH_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null; // private window or blocked storage: the width just isn't remembered
  }
}

function writeNavWidth(w: number): void {
  try {
    localStorage.setItem(NAV_WIDTH_KEY, String(Math.round(w)));
  } catch {
    // as above
  }
}

interface TagInfo extends TagGroupMeta {
  colour_set: string;
  colour_index: number;
}

/** Draws one quote with the Quotes lens's card, wired to the report's store. */
type RenderQuote = (q: QuoteResponse, phrase: string) => React.ReactNode;

const NO_FLASH = new Set<string>();
const noop = () => {};

/** Which version shows for `sid` on this screen: that session's, else the screen's default. */
function tabIndexOf(sc: Screen, sid: string | null): number {
  const i = sc.tabs.findIndex((tb) => tb.session_id === sid);
  return i >= 0 ? i : defaultTab(sc);
}

/** "p2's screen at 00:40 · 2 of 3", as plain text: what a change of version announces. */
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
type Refocus = "nav" | "versions" | "lost";

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
  const { selectedIds, clearSelection, focusedId, setFocus } = useFocus();
  const { hiddenTagGroups, disabledFrameworks } = useSidebarStore();

  // The board holds still during a live window resize and settles once when it ends (E).
  useEffect(() => installLiveResizeWatch(), []);

  // The researcher's arrangements, from the project's database, read before any board shows: a
  // custom board drawn automatic first would jump, and one drawn automatic over an arrangement the
  // server holds would be overwritten by its first drag. So a failed read keeps the board waiting
  // and asks again, on the screens poll's back-off. Read only once /screens says the lens is on:
  // the read also sends up this browser's old copy, which an explicit off must not bring back.
  const [arrangementsReady, setArrangementsReady] = useState(() => arrangementsLoaded(projectId));
  const [arrangementsError, setArrangementsError] = useState(false);
  const lensOn = !!data?.enabled && !data.unavailable;
  useEffect(() => {
    if (!lensOn || arrangementsLoaded(projectId)) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const read = (attempt: number) => {
      void loadArrangements(projectId).then((ok) => {
        if (!live) return;
        setArrangementsReady(ok);
        setArrangementsError(!ok);
        if (!ok && attempt + 1 < SCREENS_POLL_LIMIT) timer = setTimeout(() => read(attempt + 1), pollDelay(attempt + 1));
      });
    };
    read(0);
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [projectId, lensOn]);
  // A finished run re-reads them, as it re-reads the screens: another window's changes show.
  const arrangementsRefresh = useRef(refreshKey);
  useEffect(() => {
    if (arrangementsRefresh.current === refreshKey) return;
    arrangementsRefresh.current = refreshKey;
    if (lensOn && arrangementsLoaded(projectId)) void reloadArrangements(projectId);
  }, [refreshKey, lensOn, projectId]);

  // Arriving from a link (the transcript's gutter: docs/design-transcript-gutter.md): the address
  // names a screen by an opaque reference to its key, never the key, and a session. The first load
  // that holds that screen opens it on that session's version. Read from the page's own query: the
  // lens exists only in serve mode, under the browser router, never in an export.
  const arrival = useRef(screensArrival(window.location.search));
  // The screen an arrival opened, until its title on the board has flashed (utils/arrival.ts).
  const arrivedKey = useRef<string | null>(null);

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
          const want = arrival.current;
          const asked = want ? r.screens.find((sc) => screenRef(sc.key) === want.ref) : undefined;
          if (want && asked) {
            arrival.current = null;
            setCurKey(asked.key);
            arrivedKey.current = asked.key;
            const hasSession = asked.tabs.some((tb) => tb.session_id === want.session);
            if (!hasSession) console.warn("Screens: the screen asked for has no version from", want.session);
            setTabSid(hasSession ? want.session : null);
          } else if (want && !r.pending) {
            // Read everything and still not there: its key changed (screen text was rebuilt) or the
            // address is old. Stop waiting, so a later poll cannot jump the reader to it mid-read.
            arrival.current = null;
            console.warn("Screens: the screen asked for is not in the lens", want.ref);
          }
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
  // set whichever version shows (a screen is one place for everything about it). Hidden quotes are
  // not on the board. It is also the only set a gesture on a selection may reach: a selection made
  // on the Quotes lens survives the route change, and starring one card must not star twenty
  // quotes nobody can see here.
  const said = useMemo(() => {
    if (!screen) return [];
    const seen = new Set<string>();
    for (const tb of screen.tabs) {
      for (const d of [...tb.pins.map((p) => p.dom_id), ...tb.loose]) if (byId.has(d) && !store.hidden[d]) seen.add(d);
    }
    return [...seen].sort((a, b) => byId.get(a)!.start_timecode - byId.get(b)!.start_timecode);
  }, [screen, byId, store.hidden]);

  // The window subtitle's count, and what the Mac reads for its View menu and column fit.
  useEffect(() => {
    setScreensCount(screens.length);
    return () => setScreensCount(0);
  }, [screens.length]);

  // The navigator: shown and hidden like Discussion's guide, and resized the same way — the
  // shipped .drag-handle on its edge, a keyboard-operable separator (←/→ by RESIZE_STEP, Home,
  // End), its width remembered on release (discussion/split.ts's floor and step).
  const [navW, setNavW] = useState<number>(() => readNavWidth() ?? NAV_W);
  const [splitting, setSplitting] = useState(false);
  const [splitHover, setSplitHover] = useState(false);
  const clampNav = (w: number) => Math.round(Math.min(NAV_MAX, Math.max(MIN_WIDTH, w)));
  const navWidth = clampNav(navW);
  const boardShown = !quotesError && !!data?.enabled && !data.unavailable && screens.length > 0;
  const navShown = navPanel.wish && boardShown;
  useEffect(() => {
    reportScreensNav(navShown, (navPanel.wish ? navWidth : 0) + CONTENT_FLOOR_PX);
  }, [navShown, navPanel.wish, navWidth]);
  const navRef = useRef<HTMLDivElement>(null);
  // `[` hides the navigator; if the split had keyboard focus, focus goes to the board's title
  // rather than to the page.
  const splitFocused = useRef(false);
  useLayoutEffect(() => {
    if (navShown || !splitFocused.current) return;
    splitFocused.current = false;
    focusLensHeading(lensRef.current);
  }, [navShown]);
  const onSplitDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const startX = e.clientX;
    const startW = navRef.current?.getBoundingClientRect().width || navWidth;
    let last = navWidth;
    setSplitting(true);
    document.body.classList.add("dragging");
    const move = (ev: PointerEvent) => {
      last = clampNav(startW + ev.clientX - startX);
      setNavW(last);
    };
    const end = () => {
      setSplitting(false);
      document.body.classList.remove("dragging");
      writeNavWidth(last); // once, on release
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
  };
  const onSplitKey = (e: React.KeyboardEvent) => {
    const step: Record<string, number> = { ArrowLeft: -RESIZE_STEP, ArrowRight: RESIZE_STEP };
    let next: number;
    if (e.key in step) next = clampNav(navWidth + step[e.key]);
    else if (e.key === "Home") next = MIN_WIDTH;
    else if (e.key === "End") next = NAV_MAX;
    else return;
    e.preventDefault();
    e.stopPropagation(); // the lens's own ←/→ change version; on the split they resize
    setNavW(next);
    writeNavWidth(next);
  };

  // Changing screen remounts the board, and focus inside it would fall to the page; changing
  // version keeps the board but can move a card from a margin to the list (a remount of that card).
  // Where focus was decides where it goes: on a navigator link, to the link that is now current; in
  // the versions unit, to its checked badge; anywhere else on the board, nowhere if it survived,
  // else the board's title. Focus outside the lens is left alone. "On p2's screen" is the board's to
  // settle (`focusRequest`): the card it moves is hidden until placement gives it a spot.
  const lensRef = useRef<HTMLElement>(null);
  // An arrival flashes the title of the screen it opened, once the board shows it (the loading
  // shell's "Screens" heading is not it). Checked after every render: the board waits on data,
  // arrangements and stills, and the check is one comparison until then.
  useEffect(() => {
    if (arrivedKey.current === null || screen?.key !== arrivedKey.current) return;
    const lens = lensRef.current;
    const title = lens?.classList.contains("screens-lens") ? lens.querySelector<HTMLElement>(".section-heading h1") : null;
    if (!title) return;
    arrivedKey.current = null;
    markArrived(title);
  });
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
    if (r.want === "versions" && at(lens.querySelector<HTMLElement>('.screens-versions [role="radio"][aria-checked="true"]'))) return;
    const now = document.activeElement;
    if (now && now !== document.body && lens.contains(now)) return; // it survived
    const h1 = lens.querySelector<HTMLElement>(":scope > .section-heading h1");
    if (h1) {
      h1.tabIndex = -1; // a focus target, not a tab stop
      h1.focus();
    }
  }, [boardKey]);

  // Moving to another screen, or another version, is announced: the board changes under a screen
  // reader with nothing else to say so — unless focus lands somewhere that says it.
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
      // On a version badge, focus follows the checked one (a radio group). On ‹ › or the collapsed
      // button, focus stays where it is, so they work again and again from the keyboard.
      const onRadio = active instanceof Element && !!active.closest('.screens-versions [role="radio"]');
      const onStepper = active instanceof Element && !!active.closest(".screens-step, .screens-version-menu");
      let want: Refocus | null = null;
      if (focusCard) setFocusRequest((r) => ({ dom: focusCard, seq: (r?.seq ?? 0) + 1 }));
      else if (moving && active instanceof Element && lens?.contains(active) && !(same && onStepper)) {
        want = active.closest(".screens-nav") ? "nav" : onRadio ? "versions" : "lost";
      }
      refocus.current = want ? { want, from: active } : null;
      setCurKey(next.key);
      setTabSid(nextTab?.session_id ?? null);
      if (!moving || !nextTab) return;
      if (same) {
        // A change of version. On a badge, focus moves to the newly checked one, which says it; on
        // ‹ › or the collapsed button focus stays, so the new version's name is announced; from
        // anywhere else, where and when as well.
        if (onStepper) announce(i18n.t("screens.announceParticipant", { code: nextTab.code }));
        else if (!onRadio) announce(slideCaptionText(nextTab, jj, next.tabs.length));
        // The card that asked for this version is now linked: focus it, as a click would.
        if (focusCard) setFocus(focusCard, { scroll: false });
        return;
      }
      // Where focus moves, the newly focused title, link or badge says where we are; announcing
      // as well would say it twice.
      if (refocus.current) return;
      announce(i18n.t("screens.announceScreen", { title: screenTitle(next, nextTab), n: at + 1, total: n }));
    },
    [screens, screen, tabIdx, boardKey, setFocus],
  );
  // An undo or redo of a move or a Tidy on a screen or version not showing shows it first, so the
  // change is seen (the closure outlives the board that pushed it).
  const reveal = useCallback((key: string, sid: string) => {
    setCurKey(key);
    setTabSid(sid);
  }, []);
  const flip = useCallback(
    (dir: 1 | -1) => {
      if (!screen || screen.tabs.length < 2) return;
      go(cur, (tabIdx + dir + screen.tabs.length) % screen.tabs.length);
    },
    [go, cur, tabIdx, screen],
  );

  // The lens's own keys: ↑/↓ change screen, ←/→ change version. Everything else that moves
  // through or acts on the quotes — J/K, ⇧J/K, ⌘A, s/h/t/r/x/Enter — is the report's shared
  // handler (hooks/useKeyboardShortcuts.ts), as on the Quotes lens, over the order the board
  // registers. That handler returns early on Screens for the arrow keys only, so these four are
  // ours; each is under keyIsOurs (defaultPrevented first) and preventDefault()ed when taken.
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
      else return;
      e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [go, flip, cur, screen, screens.length]);

  // The Mac's View menu (and anything else on the bridge) drives the same steps by name
  // (shims/bridge.ts dispatches `bn:menu-action`). Tidy is the board's own (ScreenBoard); Next and
  // Previous Quote are the shared handler's.
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
        default:
          break;
      }
    };
    window.addEventListener("bn:menu-action", onMenu);
    return () => window.removeEventListener("bn:menu-action", onMenu);
  }, [go, flip, cur, screen, screens.length]);

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
        // The owner, 15 Oct 2026: the "[When asked…]" line is "interesting but new… hide here for
        // the moment". Only here; the Quotes lens keeps it, and so does the code.
        showResearcherContext={false}
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
  // Only a board needs the arrangements; the states above never wait for them.
  if (!arrangementsReady) {
    return shell(arrangementsError
      ? <p className="bn-empty-state" role="alert">{t("screens.loadFailed")}</p>
      : <p className="bn-empty-state" aria-busy="true">{t("screens.loading")}</p>);
  }
  return (
    <section
      ref={lensRef}
      className={`screens-lens${navShown ? "" : " nav-hidden"}`}
      style={{ "--screens-nav-w": `${navWidth}px`, "--screens-card-w": `${CARD_W}px`, "--screens-col-w": `${COLUMN_W}px` } as React.CSSProperties}
      data-testid="screens-lens"
    >
      {navShown && (
        <div className="screens-nav-pane" ref={navRef}>
          <ScreenNav screens={screens} cur={cur} onPick={(i) => go(i)} byId={byId} hidden={store.hidden} />
          {/* The shipped .drag-handle on the navigator's edge, as Discussion's guide has. A
              focusable separator is an interactive widget (ARIA window splitter). */}
          {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
          <div
            className={`drag-handle screens-split${splitting ? " active" : ""}${splitHover ? " hover-intent" : ""}`}
            role="separator" aria-orientation="vertical" aria-label={t("screens.resizeNavigator")} aria-controls="screens-nav"
            tabIndex={0} aria-valuemin={MIN_WIDTH} aria-valuemax={NAV_MAX} aria-valuenow={navWidth}
            aria-valuetext={t("screens.navWidthPixels", { count: navWidth })}
            onFocus={() => (splitFocused.current = true)} onBlur={() => (splitFocused.current = false)}
            onPointerDown={onSplitDown} onKeyDown={onSplitKey}
            onPointerEnter={() => setSplitHover(true)} onPointerLeave={() => setSplitHover(false)}
          />
        </div>
      )}
      {screen && (
        // Keyed by the screen alone: changing version keeps the board (its cross-fade, its swipe
        // lock); another screen is another board.
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
          focusedId={focusedId}
          focusRequest={focusRequest}
          reveal={reveal}
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

/**
 * The navigator's per-screen detail — the address, the participants' codes and the quote count —
 * is built and kept, and not shown for now. The owner, 15 Oct 2026: these may belong on the board,
 * as context for the screen it shows, rather than in the list of screens. Turn on to show them.
 */
export const NAV_DETAILS = false;

/** How many quotes a screen's board shows: each once, hidden ones not counted. */
export function quotesOnScreen(s: Screen, byId: Map<string, QuoteResponse>, hidden: Record<string, boolean>): number {
  const seen = new Set<string>();
  for (const tb of s.tabs) for (const d of [...tb.pins.map((p) => p.dom_id), ...tb.loose]) if (byId.has(d) && !hidden[d]) seen.add(d);
  return seen.size;
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
    <nav className="screens-nav" id="screens-nav" aria-label={t("screens.title")}>
      <div className="screens-nav-head">
        {t("screens.navSummary", {
          screens: t("screens.screenCount", { count: screens.length }),
          participants: t("screens.participantCount", { count: participants }),
        })}
      </div>
      <ol ref={listRef}>
        {screens.map((s, i) => {
          const codes = [...new Set(s.tabs.map((tb) => tb.code))];
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
                {/* Dropped below the navigator's narrow width (screens.css container query). */}
                <span className={`screens-thumb${s.tabs.length > 1 ? " stacked" : ""}`}>
                  {s.tabs.slice(0, 3).map((tb) => (
                    <NavThumb key={`${tb.session_id}@${tb.t}`} tab={tb} />
                  ))}
                </span>
                <span>
                  <span className="screens-nav-title">{screenTitle(s)}</span>
                  {NAV_DETAILS && s.name.startsWith("/") && <span className="screens-nav-path">{s.name}</span>}
                  {NAV_DETAILS && (
                    <span className="screens-nav-meta">
                      <span className="screens-count">{quotesOnScreen(s, byId, hidden)}</span>
                      <span className="screens-codes">
                        {codes.slice(0, 12).map((c) => (
                          <span key={c} className="bn-speaker-badge-code">
                            {c}
                          </span>
                        ))}
                        {codes.length > 12 && <span className="screens-more">+{codes.length - 12}</span>}
                      </span>
                    </span>
                  )}
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
  /** Show version `j`. */
  onFlip: (j: number) => void;
  /** Show version `j`, where card `dom` is linked, and bring it forward. */
  onShowOn: (dom: string, j: number) => void;
  byId: Map<string, QuoteResponse>;
  store: ReturnType<typeof useQuotesStore>;
  /** Every quote on this screen, once each, in time order (hidden ones not). */
  said: string[];
  focusedId: string | null;
  /** Move keyboard focus into this card once it has a place (after "On p2's screen"). */
  focusRequest: FocusRequest | null;
  /** Show this screen and version (an undo reaching back to one not showing). */
  reveal: (screenKey: string, sessionId: string) => void;
  /** Recordings that could not be read or held no text: a plain list, never live. */
  problems: string[];
  renderQuote: RenderQuote;
}

interface Geometry {
  stageW: number;
  /** The showing screengrab as the board lays it out: where its box sits in the board and its
   *  size, border included — the one measure placement, a freeze, a drop and Tidy all use, so they
   *  agree to the pixel with each other and with the grid. */
  W: number;
  H: number;
  sx: number;
  sy: number;
  /** The picture inside that border, where a line's box is: its inset and size. */
  ix: number;
  iy: number;
  iw: number;
  ih: number;
  /** Two columns, one, or rows: changes only at a threshold, with hysteresis (layout.ts). */
  mode: Mode;
}

const sameGeometry = (a: Geometry, b: Geometry) =>
  a.stageW === b.stageW && a.W === b.W && a.H === b.H && a.sx === b.sx && a.sy === b.sy && a.mode === b.mode &&
  a.ix === b.ix && a.iy === b.iy && a.iw === b.iw && a.ih === b.ih;

interface Drag {
  dom: string;
  left: number;
  top: number;
  width: number;
  z: number;
}

/** Where everything on the board is, once measured. */
interface Laid {
  /** Automatic: the composition of the linked cards. Custom: null. */
  comp: Composition | null;
  /** Custom: each placed card's top-left in the board. */
  pos: Record<string, { left: number; top: number }>;
  /** What the bands above and below the screengrab hold open. */
  band: { T: number; B: number };
  /** The side columns' height: the screengrab's, or more where a column runs past it. */
  colH: number;
  /** The board's least height, so a card placed low is not cut off. */
  boardMin: number;
}

/** How long a card glides from its old place to its new one (ms). */
const GLIDE_MS = 260;

const boxOf = (p: Pin) => ({ x: p.box[0], y: p.box[1], w: p.box[2], h: p.box[3] });

/**
 * Which version shows: ONE unit, ranged right on the heading line (the owner, 15 Oct 2026). The
 * moment's timecode (the house link: it plays), ‹ ›, and the participants' badges as a radio group
 * — one tab stop, ←/→ within it, the checked badge in the shared "you are here" style. Past
 * VERSION_BADGES_MAX the badges collapse to `‹ p3 · 2 of 8 ›`, the badge opening a menu of
 * versions. Each radio is named for its version ("p3's screen, 2 of 3"); the timecode is its own
 * link. Nothing for choosing a version sits on the screengrab.
 */
function Versions({ screen, tabIdx, onFlip }: { screen: Screen; tabIdx: number; onFlip: (j: number) => void }) {
  const { t } = useTranslation();
  const total = screen.tabs.length;
  const tab = screen.tabs[tabIdx];
  const [menu, setMenu] = useState(false);
  const closeMenu = useCallback(() => setMenu(false), []);
  const step = (d: 1 | -1) => onFlip((tabIdx + d + total) % total);
  // A radio says its own position ("2 of 3"), so its name is whose screen only; the collapsed
  // button, which is no radio, says both.
  const name = (j: number) => t("screens.announceParticipant", { code: screen.tabs[j].code });
  // ←/→ move the checked badge, as in any radio group; ↑/↓ are left to the lens (screens).
  const onRadioKey = (e: React.KeyboardEvent) => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      onFlip(e.key === "Home" ? 0 : total - 1);
      return;
    }
    if (!d) return;
    e.preventDefault();
    step(d);
  };
  const arrow = (d: 1 | -1) => (
    <button type="button" className="screens-step" onClick={() => step(d)}
      aria-label={t(d < 0 ? "screens.previousVersion" : "screens.nextVersion")}>
      <Icon name={d < 0 ? "previous" : "next"} decorative />
    </button>
  );
  return (
    <span className="screens-versions">
      <TimecodeLink seconds={tab.t} participantId={tab.code} data-testid="screens-version-time" />
      {total > 1 && arrow(-1)}
      {total > VERSION_BADGES_MAX ? (
        <span className="screens-version-pick">
          <button type="button" className="screens-version-menu bn-person-badge-here" aria-haspopup="menu"
            aria-expanded={menu} aria-label={t("screens.versionOption", { code: tab.code, n: tabIdx + 1, total })}
            onClick={() => setMenu((m) => !m)}>
            <PersonBadge code={tab.code} role="participant" />
            <span className="screens-version-count" aria-hidden="true">{t("screens.versionCount", { n: tabIdx + 1, total })}</span>
          </button>
          {menu && (
            <BoardMenu x={0} y={30} onClose={closeMenu}
              items={screen.tabs.map((_, j) => ({ label: name(j), run: () => onFlip(j), checked: j === tabIdx }))} />
          )}
        </span>
      ) : total > 1 ? (
        <span role="radiogroup" aria-label={t("screens.versionsLabel")} className="screens-version-radios">
          {screen.tabs.map((tb, j) => (
            <button key={`${tb.session_id}@${tb.t}`} type="button" role="radio" aria-checked={j === tabIdx}
              tabIndex={j === tabIdx ? 0 : -1} aria-label={name(j)}
              className={j === tabIdx ? "bn-person-badge-here" : undefined} onClick={() => onFlip(j)} onKeyDown={onRadioKey}>
              <PersonBadge code={tb.code} role="participant" />
            </button>
          ))}
        </span>
      ) : (
        <span className="bn-person-badge-here">
          <PersonBadge code={tab.code} role="participant" />
        </span>
      )}
      {total > 1 && arrow(1)}
    </span>
  );
}

/** Both halves of the palette's accent, re-read when the palette or the theme attribute changes. */
function usePaletteAccents(): { light: Rgb; dark: Rgb } | null {
  const [accents, setAccents] = useState(readAccents);
  useEffect(() => {
    if (typeof MutationObserver === "undefined") return;
    const mo = new MutationObserver(() => setAccents(readAccents()));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-color-theme", "data-theme", "style", "class"] });
    return () => mo.disconnect();
  }, []);
  return accents;
}

/** A Retina screen: the halo's blur is drawn only there. At 1× WebKit and Chromium both render a
 *  σ 0.7 blur as a 3px smear whose brightest row is 81% paper, under the 3:1 floor beside the line
 *  (measured 15 Oct 2026), so a 1× screen gets the hard casing instead. */
const HIDPI = "(min-resolution: 2dppx)";
function useHiDpi(): boolean {
  const [hi, setHi] = useState(() => typeof matchMedia === "function" && matchMedia(HIDPI).matches);
  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const mq = matchMedia(HIDPI);
    const on = () => setHi(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return hi;
}

function ScreenBoard(props: BoardProps) {
  const { t } = useTranslation();
  const { projectId, screen, tabIdx, byId, store, said } = props;
  const { setFocus, registerVisibleQuoteIds, clearSelection, toggleSelection, setAnchor } = useFocus();
  const tab = screen.tabs[tabIdx];
  const multi = screen.tabs.length > 1;
  const slides = useStills(screen.tabs, tabIdx, 1600);
  const { src, failed: stillFailed } = slides[tabIdx];
  // Over the screengrab the leaders follow its paper, not the board (paper.ts): the accent half that
  // reads against it, and a halo in its own colour. No paper yet, no halo: today's line stands.
  const accents = usePaletteAccents();
  const blurred = useHiDpi();
  const paperRgb = src ? papers.get(stillUrl(tab, 1600)) : undefined;
  const paperKey = paperRgb?.join(",");
  const choice = useMemo(
    () => (paperRgb && accents ? choosePaper(paperRgb, accents, blurred) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- paperKey is paperRgb's value
    [paperKey, accents, blurred],
  );
  const paperStyle = useMemo(
    () => (choice ? ({ colorScheme: choice.scheme, "--screens-paper": choice.casing } as React.CSSProperties) : undefined),
    [choice],
  );
  const leadId = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const stageRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const shotRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const cardEls = useRef(new Map<string, HTMLElement>());
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [laid, setLaid] = useState<Laid | null>(null);
  const settled = useRef(false);
  const [leaders, setLeaders] = useState<{ id: string; d: string; end: [number, number] }[]>([]);
  // Bumped to re-render: when a glide ends (re-measure the leaders), and after a live resize.
  const [, bump] = useReducer((n: number) => n + 1, 0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [menu, setMenu] = useState<{ x: number; y: number; items: { label: string; run: () => void }[] } | null>(null);
  // Stable, so the menu's effect (which focuses its first item, and returns focus on close) runs
  // once per opening rather than on every render of the board.
  const closeMenu = useCallback(() => setMenu(null), []);
  const [hiddenOpen, setHiddenOpen] = useState(false);

  // ── The researcher's arrangement of this version: null while automatic (layout.ts) ──
  const arrangeVersion = useSyncExternalStore(subscribeArrangement, arrangementVersion, arrangementVersion);
  // A version migrated from the 14 Oct store has spots for the cards placed then, and none for the
  // rest: on its first view the rest are frozen where automatic layout puts them, as a first drag
  // does, or its linked cards would drop into the list ("my cards disappeared").
  const fillPending = useRef(false);
  useLayoutEffect(() => {
    if (migrateArrangement(projectId, screen.key, tab.session_id, tab.t)) fillPending.current = true;
  }, [projectId, screen.key, tab.session_id, tab.t]);
  const arrangement = useMemo(
    () => arrangementFor(projectId, screen.key, tab.session_id),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectId, screen.key, tab.session_id, arrangeVersion],
  );
  const custom = arrangement !== null;
  const write = (cards: Arrangement | null) => setArrangement(projectId, screen.key, tab.session_id, cards);
  const vkey = versionKey(screen.key, tab.session_id);
  // One undoable change to this version's arrangement. Undone or redone while another screen or
  // version is showing, it shows this one first, so the change is seen.
  const undoable = (action: "moveQuote" | "tidy", before: Arrangement | null, after: Arrangement | null) => {
    const key = screen.key, sid = tab.session_id, reveal = props.reveal;
    const put = (a: Arrangement | null) => {
      reveal(key, sid);
      setArrangement(projectId, key, sid, a);
    };
    pushUndo({ action, undo: () => put(before), redo: () => put(after) });
  };

  // ── A live window resize: hold still, scale as one, settle once (utils/liveResize.ts) ──
  const liveRef = useRef(isLiveResizing());
  const [live, setLive] = useState(isLiveResizing);
  const [liveW, setLiveW] = useState(0);
  // The stage's width when the resize began: the board is held at it and scaled.
  const [liveBase, setLiveBase] = useState(0);
  const geoRef = useRef(geo);
  useLayoutEffect(() => {
    geoRef.current = geo;
  });
  // The glide's starting places, and whether the next settled layout glides to its new places
  // (a mode change, Tidy, an undo, the end of a live resize) or simply arrives (a drop, a freeze).
  const flipFrom = useRef<{ mode: Mode; at: Map<string, [number, number]> } | null>(null);
  const glideNext = useRef(false);
  const remeasure = useRef(false);
  const where = () => {
    const board = boardRef.current;
    const at = new Map<string, [number, number]>();
    if (!board) return at;
    const bb = board.getBoundingClientRect();
    for (const [id, el] of cardEls.current) {
      // A card not yet placed sits hidden at the origin: never glide from there.
      if (el.style.visibility === "hidden") continue;
      const r = el.getBoundingClientRect();
      at.set(id, [r.left - bb.left, r.top - bb.top]);
    }
    return at;
  };
  useEffect(
    () =>
      subscribeLiveResize(() => {
        const now = isLiveResizing();
        if (now === liveRef.current) return;
        if (now) {
          const base = geoRef.current?.stageW ?? stageRef.current?.clientWidth ?? 0;
          setLiveBase(base);
          setLiveW(base);
        } else {
          // Where the cards are now, scaled: the glide home starts here.
          flipFrom.current = { mode: geoRef.current?.mode ?? "r", at: where() };
          glideNext.current = true;
          remeasure.current = true;
        }
        liveRef.current = now;
        setLive(now);
      }),
    [],
  );

  const onScreen = useMemo(() => new Set(said), [said]);
  // LINKED: the quotes whose words are on the screengrab showing — this version's pins, and only
  // these, in time order (time breaks ties along an edge). A quote linked on another version is
  // listed, offering that version ("On p2's screen"). No screengrab to pin to: nothing is linked.
  const pins = useMemo(() => {
    if (stillFailed) return [];
    const seen = new Set<string>();
    return tab.pins
      .filter((p) => {
        if (seen.has(p.dom_id) || !byId.has(p.dom_id) || store.hidden[p.dom_id]) return false;
        seen.add(p.dom_id);
        return true;
      })
      .sort((a, b) => byId.get(a.dom_id)!.start_timecode - byId.get(b.dom_id)!.start_timecode);
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
  const hiddenHere = useMemo(() => {
    const seen = new Set<string>();
    for (const tb of screen.tabs) {
      for (const d of [...tb.pins.map((p) => p.dom_id), ...tb.loose]) if (byId.has(d) && store.hidden[d]) seen.add(d);
    }
    return [...seen];
  }, [screen, byId, store.hidden]);
  // The focused card comes forward and its line lights, as a click does (FocusContext).
  const lit = props.focusedId && onScreen.has(props.focusedId) ? props.focusedId : null;
  // The card in front: the last one touched, by a press anywhere on it (its star, eye, tag or
  // timecode included) or by focus moving to it. Stacking order only; focus and selection stay the
  // Quotes lens's own (the owner, 15 Oct 2026: "any press anywhere — yes").
  const [touched, setTouched] = useState<string | null>(null);
  const [seenFocus, setSeenFocus] = useState(props.focusedId);
  if (props.focusedId !== seenFocus) {
    // Adjusted during render, not in an effect: the new focus is in front on the same paint.
    setSeenFocus(props.focusedId);
    if (props.focusedId) setTouched(props.focusedId);
  }

  // A card is placed against the screengrab: without one to measure (it failed to load, or has no
  // size yet) every card is listed, a custom board's included, not held hidden for a spot.
  const placeable = !!geo && geo.H > 0;
  const mode: Mode = geo?.mode ?? "r";
  const dragging = drag?.dom ?? null;
  // Below the side-column threshold a custom board is SHOWN as the automatic rows — its side
  // columns would push the page sideways at 320px (1.4.10) — and its arrangement is kept, to apply
  // again once the stage is wide enough. Nothing is moved there by hand: the grips and ⌥-arrows
  // rest until the arrangement shows.
  const shown = arrangement !== null && mode !== "rows" ? arrangement : null;
  const showCustom = shown !== null;
  const handsOff = custom && !showCustom;
  // Automatic: the linked cards on the edges, by their lines. Custom: every card with a spot, where
  // the researcher's arrangement has it (layout.ts rectFromIntent); a card without one (it arrived
  // after the board went custom) waits in the list until Tidy.
  const placed = shown && placeable ? said.filter((d) => d in shown && d !== dragging) : [];
  const edgeCards: BoardCard[] = showCustom ? [] : pins.map((p) => ({ id: p.dom_id, height: 0, anchor: boxOf(p) }));
  const edgeOf = new Map<string, Edge>(edgeCards.map((c) => [c.id, edgeFor(c.anchor, mode)]));
  const onEdge = (e: Edge) => edgeCards.filter((c) => edgeOf.get(c.id) === e).map((c) => c.id);
  const frameSides = shown ? customFrame(placed.map((d) => ({ intent: shown[d], height: 0 }))) : null;
  const columns = frameSides
    ? boardColumns("lr", frameSides)
    : boardColumns(mode, { L: onEdge("L").length > 0, R: onEdge("R").length > 0 });
  const inMargin = new Set(showCustom ? placed : edgeCards.map((c) => c.id));
  // Everything else said here: under the screengrab, in time order.
  const listed = said.filter((d) => !inMargin.has(d) && d !== dragging);

  // Measure the stage and the showing screengrab, and pick the mode (with hysteresis: the previous
  // mode is part of the answer). During a live resize only the stage, for the scale.
  const measure = useCallback(() => {
    const stage = stageRef.current, shot = shotRef.current;
    if (!stage || !shot) return;
    // During a live resize only the stage, for the scale — once the board has been laid out at all.
    // A board that mounts mid-resize lays itself out first, and that is the size it scales from.
    if (liveRef.current && (geoRef.current?.H ?? 0) > 0) {
      setLiveW(stage.clientWidth);
      return;
    }
    const img = shot.querySelector<HTMLImageElement>("img.is-current");
    const stageW = stage.clientWidth;
    if (liveRef.current) {
      setLiveBase((b) => b || stageW);
      setLiveW((w) => w || stageW);
    }
    // (jsdom measures no box: there the client size stands in.)
    const W = img ? img.offsetWidth || img.clientWidth : shot.clientWidth;
    const H = img ? img.offsetHeight || img.clientHeight : 0;
    const inner = { ix: img?.clientLeft ?? 0, iy: img?.clientTop ?? 0, iw: img?.clientWidth ?? W, ih: img?.clientHeight ?? H };
    setGeo((old) => {
      const g = { stageW, W, H, sx: shot.offsetLeft, sy: shot.offsetTop, ...inner, mode: stageMode(stageW, old?.mode) };
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

  // An arrangement change the researcher did not make by dropping a card here (Tidy, an undo, a
  // redo, Return to automatic) glides every card to its new place; a drop or a freeze just lands.
  // A change of version is not such a change: the screengrab cross-fades and the cards simply take
  // their places on the new version.
  const quiet = useRef(false);
  const lastArrangement = useRef({ key: vkey, arr: arrangement });
  useLayoutEffect(() => {
    const last = lastArrangement.current;
    if (last.key === vkey && last.arr === arrangement) return;
    lastArrangement.current = { key: vkey, arr: arrangement };
    if (last.key !== vkey) {
      quiet.current = false;
      return;
    }
    if (quiet.current) quiet.current = false;
    else glideNext.current = true;
  });

  // Place the cards once they have heights. Deliberately runs after every render (a card's height
  // changes with tags, edits and width; a band's height moves the screengrab down) and sets state
  // only when the placement changes. `settled` says this commit's placement held, which is when the
  // glide below may measure where everything went. Never during a live resize: everything holds.
  const height = (d: string) => cardEls.current.get(d)?.offsetHeight ?? 120;
  // Where Tidy would put each linked card, as intent: the automatic composition, frozen. The band
  // below starts under the taller of the screengrab and its side columns, as in the grid.
  const autoSpots = () => {
    const g = geo!;
    const comp = composeBoard(pins.map((p) => ({ id: p.dom_id, height: height(p.dom_id), anchor: boxOf(p) })), g.mode, { W: g.W, H: g.H });
    const below = Math.max(0, comp.colBottom - g.H);
    return (d: string, z: number): Intent => autoIntent(comp.at[d], height(d), { W: g.W, H: g.H }, comp.band.T, z, below);
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    if (liveRef.current && laid) return;
    if (remeasure.current) {
      // The resize has ended: measure afresh before anything settles, so the glide starts from
      // where the cards were drawn, scaled, and ends where they now belong.
      remeasure.current = false;
      settled.current = false;
      measure();
      bump();
      return;
    }
    measure();
    if (!geo || !geo.H) {
      settled.current = false;
      return;
    }
    if (fillPending.current && arrangement) {
      fillPending.current = false;
      const missing = pins.filter((p) => !(p.dom_id in arrangement));
      if (missing.length) {
        const auto = autoSpots();
        const after: Arrangement = { ...arrangement };
        for (const p of missing) after[p.dom_id] = auto(p.dom_id, 31);
        quiet.current = true;
        write(after);
        return;
      }
    }
    let next: Laid;
    if (!shown) {
      const comp = composeBoard(pins.map((p) => ({ id: p.dom_id, height: height(p.dom_id), anchor: boxOf(p) })), geo.mode, { W: geo.W, H: geo.H });
      next = { comp, pos: {}, band: comp.band, colH: Math.max(geo.H, comp.colBottom), boardMin: 0 };
    } else {
      const cards = placed.map((d) => ({ id: d, intent: shown[d], height: height(d) }));
      const f = customFrame(cards);
      const s: Rect = { left: geo.sx, top: geo.sy, width: geo.W, height: geo.H };
      const pos: Laid["pos"] = {};
      let boardMin = 0;
      for (const c of cards) {
        const r = rectFromIntent(c.intent, s, c.height);
        pos[c.id] = { left: Math.max(0, r.left), top: Math.max(0, r.top) };
        boardMin = Math.max(boardMin, pos[c.id].top + c.height);
      }
      next = { comp: null, pos, band: { T: f.T, B: f.B }, colH: geo.H, boardMin };
    }
    const same = laid !== null && JSON.stringify(laid) === JSON.stringify(next);
    settled.current = same;
    // A measured layout: placement needs the cards' heights, which exist only after they render, so
    // it is set from this effect, and only when it changed — which is what makes it settle.
    setLaid((old) => (old && JSON.stringify(old) === JSON.stringify(next) ? old : next));
  });

  // Where a card sits in the board, for the reading order.
  const seenAt = (id: string): Seen | null => {
    if (!laid || !geo) return null;
    if (!laid.comp) return laid.pos[id] ? { id, ...laid.pos[id] } : null;
    const sp = laid.comp.at[id];
    if (!sp) return null;
    if (sp.edge === "L") return { id, top: geo.sy + sp.top, left: sp.left };
    if (sp.edge === "R") return { id, top: geo.sy + sp.top, left: geo.sx + geo.W + COLUMN_GUTTER + sp.left };
    if (sp.edge === "T") return { id, top: sp.top, left: geo.sx + sp.left };
    return { id, top: geo.sy + laid.colH + COLUMN_GUTTER + sp.top, left: geo.sx + sp.left };
  };
  // The board's reading order, for the report's shared keys (J/K, ⇧J/K, ⇧-click, ⌘A, and the
  // per-quote keys' scope): the margins as they sit, then the list in time order (narrative.ts).
  const margins = [...inMargin].map((d, i) => seenAt(d) ?? { id: d, top: i, left: 0 });
  const order = readingOrder(margins, listed);
  const orderKey = order.join("\n");
  useEffect(() => {
    registerVisibleQuoteIds("screens", orderKey ? orderKey.split("\n") : []);
  }, [registerVisibleQuoteIds, orderKey]);
  // Registers empty rather than deleting, as QuoteSections does, so the slot outlives a remount.
  useEffect(() => () => registerVisibleQuoteIds("screens", []), [registerVisibleQuoteIds]);

  // Leaders, once everything has settled; after every render for the same reason, set on change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    if (liveRef.current && leaders.length) return; // the board scales as one: its leaders with it
    const board = boardRef.current;
    if (!geo || !geo.H || !board || !laid) return;
    const bb = board.getBoundingClientRect();
    const next: { id: string; d: string; end: [number, number] }[] = [];
    for (const p of pins) {
      const d = p.dom_id;
      let edge: Edge | undefined;
      if (dragging === d) edge = undefined;
      else if (laid.comp) {
        edge = laid.comp.at[d]?.edge;
        if (!edge) continue;
      } else {
        const it: Intent | undefined = shown?.[d];
        if (!it || !(d in laid.pos)) continue;
        edge = it.kind === "edge" ? it.edge : undefined;
      }
      const el = cardEls.current.get(d);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const card = { left: r.left - bb.left, top: r.top - bb.top, width: r.width, height: r.height };
      const elem = {
        left: geo.sx + geo.ix + p.box[0] * geo.iw, top: geo.sy + geo.iy + p.box[1] * geo.ih,
        width: p.box[2] * geo.iw, height: p.box[3] * geo.ih,
      };
      next.push({ id: d, ...leaderPath(card, elem, edge) });
    }
    setLeaders((old) => (JSON.stringify(old) === JSON.stringify(next) ? old : next));
  });

  // Each card glides from where it was to where it now is (FLIP), measured once placement has
  // settled, against the last settled places: at a mode change, at Tidy, an undo or a redo, and at
  // the end of a live resize (from where the scaled board drew it). Instant under reduced motion.
  // The leaders are measured from the cards' rectangles, which include the glide's transform, so
  // they are measured again when the glide ends.
  useLayoutEffect(() => {
    if (liveRef.current || !geo || !boardRef.current || !settled.current) return;
    const now = where();
    const from = flipFrom.current;
    flipFrom.current = { mode: geo.mode, at: now };
    const glide = glideNext.current || (from !== null && from.mode !== geo.mode);
    glideNext.current = false;
    if (!from || !glide || reducedMotion()) return;
    const ends: Promise<unknown>[] = [];
    for (const [id, el] of cardEls.current) {
      const a = from.at.get(id), b = now.get(id);
      if (!a || !b || (a[0] === b[0] && a[1] === b[1]) || typeof el.animate !== "function") continue;
      const g = el.animate(
        [{ transform: `translate(${a[0] - b[0]}px, ${a[1] - b[1]}px)` }, { transform: "translate(0, 0)" }],
        { duration: GLIDE_MS, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      ) as Animation | undefined;
      if (g?.finished) ends.push(g.finished);
    }
    // A cancelled glide rejects its `finished`: the cards have still come to rest.
    if (ends.length) {
      Promise.allSettled(ends).then(() => {
        if (alive.current) bump();
      });
    }
  });

  // "On p2's screen": once the version has changed, keyboard focus goes into that card. The card
  // has just moved from the list to a margin, where it is hidden (visibility) until placement gives
  // it a spot, and a hidden element cannot take focus — focus() fails without a word and focus
  // falls to the page. So wait for the spot; and check focus really landed, else the board's title.
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

  // One version per horizontal swipe over the screengrab (the Mac's gesture; nothing is drawn for
  // it). Not passive: a horizontal swipe here is ours, and must not also scroll the page sideways or
  // send the browser Back. A vertical one is left alone. The lock lives as long as the board.
  const flipBy = useRef<(dir: 1 | -1) => void>(() => {});
  useEffect(() => {
    flipBy.current = (dir) => props.onFlip((tabIdx + dir + screen.tabs.length) % screen.tabs.length);
  });
  useEffect(() => {
    const el = frameRef.current;
    if (!el || !multi) return;
    const swipe = makeSwipe((dir) => flipBy.current(dir));
    const onWheel = (e: WheelEvent) => {
      if (swipe(e.deltaX, e.deltaY)) e.preventDefault();
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [multi]);

  // The screengrab's rectangle in the board, measured ONE way everywhere — the same geometry the
  // placement and the leaders use (its offset in the board, its inner size) — so a freeze, a drop
  // and a placement agree to the pixel. (The image's outer box, border included, did not: the first
  // drag moved right- and bottom-edge cards by the border's width.)
  const shotBox = (): Rect => ({ left: geo?.sx ?? 0, top: geo?.sy ?? 0, width: geo?.W || 1, height: geo?.H || 1 });
  // Every card on the board as intent, where it is drawn now: the freeze of the first drag.
  const freeze = (bb: DOMRect): Arrangement => {
    const s = shotBox();
    const out: Arrangement = {};
    for (const d of said) {
      const el = cardEls.current.get(d);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const z = 30 + (laid?.comp?.at[d]?.z ?? 1);
      out[d] = intentFromRect({ left: r.left - bb.left, top: r.top - bb.top, width: r.width, height: r.height }, s, z);
    }
    return out;
  };

  // ⌥ + an arrow moves the focused card one MOVE_STEP (2.1.1: a keyboard route to every drag). Along
  // its edge — ↑/↓ beside the screengrab, ←/→ above or below it — or, beside it, ←/→ to the other
  // side; a card over the screengrab moves either way. The same model as a drag: the first move
  // freezes the board into custom; each is undoable as Move Quote, and announced.
  const moveCard = (dom: string, dx: number, dy: number): boolean => {
    if (!placeable || handsOff || !boardRef.current || !geo) return false;
    const bb = boardRef.current.getBoundingClientRect();
    const before = arrangement;
    const base = before ?? freeze(bb);
    let p: Intent | undefined = base[dom];
    if (!p) {
      const el = cardEls.current.get(dom);
      if (!el) return false;
      const r = el.getBoundingClientRect();
      p = intentFromRect({ left: r.left - bb.left, top: r.top - bb.top, width: r.width, height: r.height }, shotBox(), topZ(projectId) + 1);
    }
    let q: Intent = p;
    const alongY = (MOVE_STEP * dy) / geo.H, alongX = (MOVE_STEP * dx) / geo.W;
    if (p.kind === "over") q = { ...p, x: p.x + alongX, y: p.y + alongY };
    else if (p.edge === "L" || p.edge === "R") {
      if (dy) q = { ...p, along: p.along + alongY };
      else if (p.edge === "L" && dx > 0) q = { ...p, edge: "R", out: COLUMN_GUTTER };
      else if (p.edge === "R" && dx < 0) q = { ...p, edge: "L", out: COLUMN_GUTTER };
    } else if (dx) q = { ...p, along: p.along + alongX };
    if (q === p) return false;
    const after: Arrangement = { ...base, [dom]: q };
    quiet.current = true;
    write(after);
    undoable("moveQuote", before, after);
    announce(i18n.t("screens.quoteMoved"));
    return true;
  };
  const moveNow = useRef(moveCard);
  useEffect(() => {
    moveNow.current = moveCard;
  });
  useEffect(() => {
    const steps: Record<string, [number, number]> = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
    const onKey = (e: KeyboardEvent) => {
      const d = steps[e.key];
      if (!d || !e.altKey || e.metaKey || e.ctrlKey || e.defaultPrevented || modalOpen(e.target)) return;
      const tg = e.target;
      if (tg instanceof Element && tg.closest("input, textarea, select, [contenteditable='true'], [role='menu'], [role='radiogroup'], [role='separator']")) return;
      const id = props.focusedId;
      if (!id || !onScreen.has(id)) return;
      if (moveNow.current(id, d[0], d[1])) e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [props.focusedId, onScreen]);

  // A card that held keyboard focus and was re-parented — a mode change, Tidy from the Mac's menu,
  // ⌘Z of a move — remounts, and focus falls to the page. Once it has its new place, focus goes back
  // into it.
  const FOCUSABLE = "a[href], button, input, textarea, [tabindex]:not([tabindex='-1'])";
  const focusInCard = useRef<{ dom: string; el: HTMLElement; i: number } | null>(null);
  // Which card holds keyboard focus, and which of its controls: noted as focus arrives (the card is
  // gone from the page by the time a re-parenting render's effects run).
  const noteFocus = (a: Element | null) => {
    const card = a instanceof Element ? a.closest<HTMLElement>(".screens-card[data-dom]") : null;
    if (!card || !(a instanceof HTMLElement) || !stageRef.current?.contains(card)) return false;
    focusInCard.current = { dom: card.dataset.dom ?? "", el: card, i: [...card.querySelectorAll(FOCUSABLE)].indexOf(a) };
    return true;
  };
  useEffect(() => {
    const onIn = (e: FocusEvent) => {
      noteFocus(e.target as Element | null);
    };
    document.addEventListener("focusin", onIn);
    return () => document.removeEventListener("focusin", onIn);
  });
  useLayoutEffect(() => {
    const a = document.activeElement;
    if (noteFocus(a)) return;
    const lost = focusInCard.current;
    if (!lost) return;
    if (a !== null && a !== document.body) {
      focusInCard.current = null; // focus went somewhere else on purpose
      return;
    }
    const el = cardEls.current.get(lost.dom);
    // Not re-parented (the same element still holds the card): someone else moved focus, and owns
    // where it goes next (a closing menu gives it back to its opener).
    if (el === lost.el) return;
    if (!el) {
      if (!onScreen.has(lost.dom)) focusInCard.current = null;
      return;
    }
    if (el.style.visibility === "hidden") return; // wait for its place
    const controls = [...el.querySelectorAll<HTMLElement>(FOCUSABLE)];
    (controls[lost.i] ?? controls[0])?.focus({ preventScroll: true });
  });

  // Drag to rearrange: the card's top edge and the margin under its timecode are the grips. Nothing
  // moves, and nothing is saved, until the pointer has travelled DRAG_THRESHOLD: a press on a grip
  // that goes nowhere focuses the card, as a click on it does. THE FIRST DRAG SWITCHES THE WHOLE
  // BOARD TO CUSTOM: at that moment every card is frozen where it is, so only the dragged one moves.
  // In custom, a drag moves only its card. Each drag is one undo (Edit ▸ Undo Move Quote); undoing
  // the drag that switched the board returns it to automatic. The window listeners belong to this
  // version: if the board remounts or the version changes mid-drag, the drag is abandoned and an
  // arrangement it froze is put back.
  const endDrag = useRef<(() => void) | null>(null);
  useEffect(() => {
    // A drag abandoned by the change of version wrote its version back quietly: that quiet is not
    // this version's, and must not swallow the next Tidy or undo glide here.
    quiet.current = false;
    return () => {
      endDrag.current?.();
      setDrag(null);
    };
  }, [tab.session_id]);
  const startDrag = (dom: string) => (e: React.PointerEvent) => {
    if (e.button !== 0 || !placeable || handsOff || !boardRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    const el = cardEls.current.get(dom);
    if (!el) return;
    endDrag.current?.();
    const bb = boardRef.current.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const z = topZ(projectId) + 1;
    const start = { x: e.clientX, y: e.clientY };
    // Where on the card the pointer took hold. The card is placed from the board's rectangle as it
    // is NOW, at every move, so a page that scrolls mid-drag keeps the card under the pointer.
    const grab = { x: e.clientX - r.left, y: e.clientY - r.top };
    const before = arrangement;
    let frozen: Arrangement | null = null;
    let moved = false;
    let frame = 0;
    let latest: PointerEvent | null = null;
    const at = (ev: PointerEvent) => {
      const b = boardRef.current?.getBoundingClientRect() ?? bb;
      return { left: ev.clientX - grab.x - b.left, top: Math.max(0, ev.clientY - grab.y - b.top) };
    };
    // Listen on the window, not the grip: the drag moves the card into the free layer, which
    // remounts it. The card follows the pointer at most once a frame (each setDrag re-renders).
    const move = (ev: PointerEvent) => {
      if (!moved && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < DRAG_THRESHOLD) return;
      if (!moved) {
        moved = true;
        if (!before) {
          frozen = freeze(bb);
          quiet.current = true;
          write(frozen);
        }
      }
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
      window.removeEventListener("pointercancel", cancel);
      endDrag.current = null;
    };
    const abandon = () => {
      detach();
      if (moved && frozen) {
        quiet.current = true;
        write(before);
      }
      setDrag(null);
    };
    function cancel() {
      abandon();
    }
    function up(ev: PointerEvent) {
      detach();
      if (!moved) {
        // A press on the grip that never became a drag is a click on the card: focus and select it,
        // exactly as a click on its body does (QuoteCard's handleCardClick).
        clearSelection();
        toggleSelection(dom);
        setFocus(dom, { scroll: false });
        setAnchor(dom);
        return;
      }
      const { left, top } = at(ev);
      const after: Arrangement = {
        ...(frozen ?? before ?? {}),
        [dom]: intentFromRect({ left, top, width: r.width, height: r.height }, shotBox(), z),
      };
      quiet.current = true;
      write(after);
      undoable("moveQuote", before, after);
      setDrag(null);
      // The card just put down is the one in front, and focused.
      setTouched(dom);
      setFocus(dom, { scroll: false });
    }
    endDrag.current = abandon;
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", cancel);
  };

  // The board's wrapper places and drags a card; the card itself is the Quotes lens's, and so are
  // its focus and selection (the shared .bn-focused and .bn-selected). The board adds only the
  // stacking order: the focused card is in front (screens.css).
  const cardFor = (dom: string, style: React.CSSProperties) => {
    const q = byId.get(dom);
    if (!q) return null;
    const pin = pinByDom.get(dom);
    // Unlinked here, linked on another participant's version: offer that version.
    const elsewhere = pin ? -1 : linkedOn.get(dom) ?? -1;
    return (
      <div
        key={dom}
        ref={(el) => {
          if (el) cardEls.current.set(dom, el);
          else cardEls.current.delete(dom);
        }}
        className={`screens-card${dragging === dom ? " is-dragging" : ""}${touched === dom ? " is-front" : ""}`}
        style={style}
        data-dom={dom}
        onPointerDownCapture={() => setTouched(dom)}
        data-pin={pin ? dom : undefined}
      >
        <span className="screens-grip screens-grip-top" aria-hidden="true" onPointerDown={startDrag(dom)} />
        <span className="screens-grip screens-grip-side" aria-hidden="true" onPointerDown={startDrag(dom)} />
        {props.renderQuote(q, pin?.phrase ?? "")}
        {elsewhere >= 0 && (
          <button type="button" className="screens-elsewhere" onClick={() => props.onShowOn(dom, elsewhere)}>
            {t("screens.onScreen", { code: screen.tabs[elsewhere].code })}
          </button>
        )}
      </div>
    );
  };

  const hidden: React.CSSProperties = { left: 0, top: 0, width: CARD_W, visibility: "hidden" };
  const inColumn = (dom: string): React.CSSProperties => {
    const s = laid?.comp?.at[dom];
    return s ? ({ top: s.top, left: s.left, width: CARD_W, "--stack": s.z } as React.CSSProperties) : hidden;
  };
  const inBand = (dom: string): React.CSSProperties => {
    const s = laid?.comp?.at[dom];
    return s ? { left: s.left, top: s.top, width: CARD_W } : hidden;
  };
  const freeStyle = (dom: string): React.CSSProperties => {
    if (drag?.dom === dom) return { left: drag.left, top: drag.top, width: drag.width, zIndex: drag.z };
    const p = laid?.pos[dom];
    return p ? { left: p.left, top: p.top, width: CARD_W, zIndex: shown?.[dom]?.z } : hidden;
  };

  // Tidy: the whole board back to automatic, every card gliding to its place. The one way back,
  // undoable with ⌘Z (Edit ▸ Undo Tidy) through the report's one undo stack, so it needs no confirm.
  const tidy = () => {
    if (!custom) return;
    const before = arrangement;
    // Tidy removes its own button (and the menu that offered it closes), so focus goes to the
    // lens's title rather than to the page.
    const active = document.activeElement;
    const lens = stageRef.current?.closest(".screens-lens");
    const keepFocus = active instanceof Element && !!active.closest(".screens-arrangement, .screens-menu");
    write(null);
    if (keepFocus) requestAnimationFrame(() => focusLensHeading(lens));
    undoable("tidy", before, null);
    announce(i18n.t("screens.arrangementAutomatic"));
  };
  // Return to automatic, on one card of a custom board: back to where Tidy would put it — a linked
  // card to its automatic spot on its edge (frozen there, so nothing else moves), any other card to
  // the list. An undoable move like any other.
  const returnToAutomatic = (dom: string) => {
    if (!arrangement || !(dom in arrangement) || !geo || !geo.H) return;
    const before = arrangement;
    const after: Arrangement = { ...before };
    if (pinByDom.has(dom)) after[dom] = autoSpots()(dom, before[dom].z);
    else delete after[dom];
    write(after);
    undoable("moveQuote", before, after);
  };
  // View ▸ Tidy on the Mac enables only while this version is custom: say so on mount and on every
  // change, and say "not custom" when the board goes (the Mac's mirror would otherwise keep the last
  // board's answer).
  useEffect(() => {
    postScreensArrangement(custom);
  }, [custom]);
  useEffect(() => () => postScreensArrangement(false), []);
  // View ▸ Tidy on the Mac (bn:menu-action), for whichever version is showing.
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

  // Right-click, on a custom board: "Return to automatic" on a card with a spot, and "Tidy". The
  // keyboard's context-menu key raises the same event. On an automatic board, and elsewhere, the
  // browser's own menu shows.
  useEffect(() => {
    const onMenu = (e: MouseEvent) => {
      const stage = stageRef.current;
      if (!custom || !stage || !(e.target instanceof Element) || !stage.contains(e.target)) return;
      const card = e.target.closest<HTMLElement>(".screens-card[data-dom]")?.dataset.dom;
      const items: { label: string; run: () => void }[] = [];
      if (card && arrangement && card in arrangement && placeable) {
        items.push({ label: i18n.t("screens.returnToAutomatic"), run: () => returnToAutomatic(card) });
      }
      items.push({ label: i18n.t("screens.tidy"), run: tidy });
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

  // One highlight per line on the screengrab, however many quotes are about it: they share it, and
  // its anchor, and their leaders fan into one point.
  const lines = new Map<string, { box: Pin["box"]; ids: string[] }>();
  for (const p of pins) {
    const k = p.box.join(",");
    const line = lines.get(k) ?? { box: p.box, ids: [] };
    line.ids.push(p.dom_id);
    lines.set(k, line);
  }
  const ends = new Map<string, { end: [number, number]; on: boolean }>();
  for (const l of leaders) {
    const k = l.end.join(",");
    ends.set(k, { end: l.end, on: (ends.get(k)?.on ?? false) || lit === l.id });
  }

  const people = new Set(said.map((d) => byId.get(d)?.participant_id)).size;
  const quoteCount = said.length;
  const bandT = showCustom ? (laid?.band.T ?? 0) : onEdge("T").length ? (laid?.comp?.band.T ?? 0) : 0;
  const bandB = showCustom ? (laid?.band.B ?? 0) : onEdge("B").length ? (laid?.comp?.band.B ?? 0) : 0;
  const hasT = showCustom ? bandT > 0 : onEdge("T").length > 0;
  const hasB = showCustom ? bandB > 0 : onEdge("B").length > 0;
  const scale = live && liveBase > 0 ? liveW / liveBase : 1;
  const free = [...placed, ...(dragging ? [dragging] : [])];
  // The picture in board space, padded 3px so an end dot on its edge is not halved.
  const pic = choice && geo && src ? { x: geo.sx + geo.ix - 3, y: geo.sy + geo.iy - 3, w: geo.iw + 6, h: geo.ih + 6 } : null;
  return (
    <>
      <SectionHeading action={<Versions screen={screen} tabIdx={tabIdx} onFlip={props.onFlip} />}>
        {screenTitle(screen, tab)}
      </SectionHeading>
      <p className="screens-sub">
        {screen.name.startsWith("/") && <code>{screen.name}</code>}
        {featureFlags.screensQuoteCount && (
          <span>
            {people > 1 ? t("screens.quoteCountFrom", { count: quoteCount, people }) : t("screens.quoteCount", { count: quoteCount })}
          </span>
        )}
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
      <div className={`screens-stage${drag ? " dragging" : ""}`} ref={stageRef}>
        {/* During a live resize the board and its list scale as one, from their last settled size,
            and settle once when it ends (utils/liveResize.ts). */}
        <div
          className="screens-scale"
          style={scale !== 1 || live ? { width: liveBase || undefined, transform: `scale(${scale})`, transformOrigin: "0 0" } : undefined}
        >
          <div
            className={`screens-board cols-${columns} mode-${mode}${showCustom ? " is-custom" : ""}`}
            ref={boardRef}
            style={{ minHeight: laid?.boardMin || undefined }}
          >
            <div className={`screens-band screens-band-t${hasT ? " has-cards" : ""}`} style={{ height: bandT }}>
              {!showCustom && onEdge("T").map((d) => cardFor(d, inBand(d)))}
            </div>
            <div className={`screens-col screens-col-l${laid?.comp?.stacked.L ? " stacked" : ""}`} style={{ height: laid?.colH || undefined }}>
              {!showCustom && onEdge("L").map((d) => cardFor(d, inColumn(d)))}
            </div>
            <div className="screens-shot" ref={shotRef}>
              <div className="screens-slides" ref={frameRef}>
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
                      className={`screens-hl${lit && l.ids.includes(lit) ? " on" : ""}`}
                      style={{
                        left: geo.ix + l.box[0] * geo.iw - 3, top: geo.iy + l.box[1] * geo.ih - 3,
                        width: l.box[2] * geo.iw + 6, height: l.box[3] * geo.ih + 6,
                        ...paperStyle,
                      }}
                    />
                  ))}
              </div>
            </div>
            <div className={`screens-col screens-col-r${laid?.comp?.stacked.R ? " stacked" : ""}`} style={{ height: laid?.colH || undefined }}>
              {!showCustom && onEdge("R").map((d) => cardFor(d, inColumn(d)))}
            </div>
            <div className={`screens-band screens-band-b${hasB ? " has-cards" : ""}`} style={{ height: bandB }}>
              {!showCustom && onEdge("B").map((d) => cardFor(d, inBand(d)))}
            </div>
            <svg className="screens-leaders" aria-hidden="true">
              {leaders.map((l) => (
                <path key={l.id} d={l.d} className={lit === l.id ? "on" : undefined} />
              ))}
              {pic ? (
                // Over the screengrab: the same lines again, clipped to the picture, with a halo in
                // its paper underneath and the accent half that reads on it. The filter's region is
                // the picture, not the board, so a drag or a glide never rasterises the whole board.
                <>
                  <defs>
                    <clipPath id={`${leadId}-clip`}>
                      <rect x={pic.x} y={pic.y} width={pic.w} height={pic.h} />
                    </clipPath>
                    {blurred && (
                      <filter id={`${leadId}-soft`} filterUnits="userSpaceOnUse" x={pic.x - 3} y={pic.y - 3} width={pic.w + 6} height={pic.h + 6}>
                        <feGaussianBlur stdDeviation={0.7} />
                      </filter>
                    )}
                  </defs>
                  <g className="lead-shot" clipPath={`url(#${leadId}-clip)`} style={paperStyle}>
                    <g className="lead-casing" filter={blurred ? `url(#${leadId}-soft)` : undefined}>
                      {leaders.map((l) => (
                        <path key={l.id} d={l.d} className={lit === l.id ? "on" : undefined} />
                      ))}
                    </g>
                    {leaders.map((l) => (
                      <path key={l.id} d={l.d} className={lit === l.id ? "on" : undefined} />
                    ))}
                    {[...ends.entries()].map(([k, e]) => (
                      <circle key={k} cx={e.end[0]} cy={e.end[1]} r={2.5} className={e.on ? "on" : undefined} />
                    ))}
                  </g>
                </>
              ) : (
                [...ends.entries()].map(([k, e]) => (
                  <circle key={k} cx={e.end[0]} cy={e.end[1]} r={2.5} className={e.on ? "on" : undefined} />
                ))
              )}
            </svg>
            <div className="screens-free">
              {free.map((d) => cardFor(d, freeStyle(d)))}
            </div>
          </div>
          <div className="screens-loose">
            {listed.map((d) => cardFor(d, {}))}
          </div>
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
interface MenuItem {
  label: string;
  run: () => void;
  /** A choice of one (menuitemradio): whether it is the current one. */
  checked?: boolean;
}

function BoardMenu(props: { x: number; y: number; items: MenuItem[]; onClose: () => void }) {
  const { x, y, items, onClose } = props;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const lens = el?.closest(".screens-lens");
    // Open on the checked choice, where there is one; else the first item.
    (el?.querySelector<HTMLButtonElement>('button[aria-checked="true"]') ?? el?.querySelector<HTMLButtonElement>("button"))?.focus();
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
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    e.stopPropagation();
    const buttons = [...(ref.current?.querySelectorAll<HTMLButtonElement>("button") ?? [])];
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next =
      e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1
        : (at + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next]?.focus();
  };
  return (
    <div ref={ref} className="screens-menu" role="menu" tabIndex={-1} style={{ left: x, top: y }} onKeyDown={onKeyDown}>
      {items.map((it, i) => (
        <button
          key={i}
          role={it.checked === undefined ? "menuitem" : "menuitemradio"}
          aria-checked={it.checked}
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
