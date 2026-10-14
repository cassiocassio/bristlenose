/**
 * The Screens lens (diagnostics): every screen the participants were on, a large screengrab of
 * each, and the quotes said there floating beside it, pinned to the on-screen line they read.
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
 * Diagnostics-only and English-only while it is rough (the Specimen precedent): reached from the
 * Diagnostics menu on the Mac and from a nav link with diagnostics on in the browser.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
import { apiGet, getCodebook } from "../../utils/api";
import { formatTimecode } from "../../utils/format";
import { wholeWordsTerm, type SearchTerm } from "../../utils/searchMatch";
import { deriveTagVisibility, type TagGroupMeta } from "../../utils/tagVisibility";
import type { QuoteResponse, QuotesListResponse } from "../../utils/types";
import { QuoteCard } from "../QuoteCard";
import {
  clearSpots,
  leaderPath,
  placeColumn,
  putSpot,
  sideFor,
  spotsFor,
  stillKey,
  topZ,
  WIDE_STAGE,
  type Side,
  type Spot,
} from "./layout";
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

const TITLE = "Screens";

// One English map per field, and a generic sentence for a code this build does not know: the
// server's own text never reaches the page (a reason code may be added before the lens learns it).
const UNAVAILABLE: Record<UnavailableReason, string> = {
  not_macos: "Screens are read on a Mac only for now, so there are none to show here.",
  vision_missing: "This Mac can’t read text on screen: its text recognition isn’t available.",
  no_job: "Screen reading isn’t running for this project, so no recordings have been read.",
};
const UNAVAILABLE_OTHER = "Screens can’t be read here.";

const FAILED: Record<FailedReason, string> = {
  unreadable: "the recording couldn’t be opened",
  cloud_downloading: "the recording is still downloading from cloud storage",
  ffprobe_failed: "its video couldn’t be inspected",
  read_failed: "reading its screen failed",
  // Only when nothing is about to read it: during an analysis the server answers "waiting" instead.
  not_read: "it hasn’t been read yet; it will be when the report next updates",
};
const FAILED_OTHER = "something went wrong reading it";

const has = (o: object, k: string) => Object.prototype.hasOwnProperty.call(o, k);

export function unavailableText(code: string): string {
  return has(UNAVAILABLE, code) ? UNAVAILABLE[code as UnavailableReason] : UNAVAILABLE_OTHER;
}

export function failedText(code: string): string {
  return has(FAILED, code) ? FAILED[code as FailedReason] : FAILED_OTHER;
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

/** What the lens says about recordings it could not, or has not yet, read. */
function readingNote(r: ScreensResponse): string[] {
  const out: string[] = [];
  if (stillReading(r)) {
    out.push(
      r.pending
        ? `Reading screens… ${r.indexed} of ${r.videos} recordings${r.reading ? ` (now ${r.reading})` : ""}.`
        : `Waiting to read ${r.videos - r.indexed} of ${r.videos} recordings (after the current analysis).`,
    );
  }
  for (const [sid, why] of Object.entries(r.failed ?? {})) out.push(`Couldn’t read ${sid}: ${failedText(why)}.`);
  for (const sid of r.blank ?? []) out.push(`No text found in ${sid}’s recording.`);
  return out;
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
    (t instanceof HTMLElement && t.isContentEditable)));
}

// ── Stills ───────────────────────────────────────────────────────────────

const stills = new Map<string, string>();
const stillFailed = new Set<string>();
const stillWaiters = new Map<string, Promise<string | null>>();

function stillUrl(tab: ScreenTab, w: number): string {
  const crop = tab.crop.map((v) => v.toFixed(4)).join(",");
  return `/screens/still?session_id=${encodeURIComponent(tab.session_id)}&t=${tab.t}&w=${w}&crop=${crop}`;
}

/** The still's data URI, or whether there is none (src null while it loads). */
function useStill(tab: ScreenTab | undefined, w: number): { src: string | null; failed: boolean } {
  const url = tab ? stillUrl(tab, w) : "";
  const [fetched, setFetched] = useState<{ url: string; src: string | null } | null>(null);
  useEffect(() => {
    if (!url || stills.has(url)) return;
    let live = true;
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
    p.then((s) => {
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

export function ScreensLens() {
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
  const { selectedIds, clearSelection, registerVisibleQuoteIds } = useFocus();
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
  const tabIdx = screen ? Math.max(0, screen.tabs.findIndex((t) => t.session_id === tabSid)) : 0;

  // The quotes on this board, in its reading order: the pinned ones down the screengrab, then the
  // rest by time (as ScreenBoard lays them out). It is what a shift-click range runs over, and the
  // only quotes a gesture on a selection may reach: a selection made on the Quotes lens survives
  // the route change, and starring one card must not star twenty quotes nobody can see here.
  const boardOrder = useMemo(() => {
    if (!screen) return [];
    const tab = screen.tabs[tabIdx];
    const shown = (d: string) => byId.has(d) && !store.hidden[d];
    const pinned = tab.pins.filter((p) => shown(p.dom_id)).sort((a, b) => a.box[1] - b.box[1]).map((p) => p.dom_id);
    const seen = new Set(pinned);
    const rest = screen.tabs
      .flatMap((t) => [...t.pins.map((p) => p.dom_id), ...t.loose])
      .filter((d, i, a) => a.indexOf(d) === i && !seen.has(d) && shown(d))
      .sort((a, b) => byId.get(a)!.start_timecode - byId.get(b)!.start_timecode);
    return [...pinned, ...rest];
  }, [screen, tabIdx, byId, store.hidden]);
  useEffect(() => {
    registerVisibleQuoteIds("screens", boardOrder);
    // Registers empty rather than deleting, as QuoteSections does, so the slot outlives a remount.
    return () => registerVisibleQuoteIds("screens", []);
  }, [registerVisibleQuoteIds, boardOrder]);

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

  // Moving to another screen, or to another participant's view of this one, is announced: the
  // board changes under a screen reader with nothing else to say so.
  const go = useCallback(
    (i: number, j = 0) => {
      if (!screens.length) return;
      const n = screens.length;
      const at = ((i % n) + n) % n;
      const next = screens[at];
      const tab = next.tabs[Math.min(j, next.tabs.length - 1)];
      setCurKey(next.key);
      setTabSid(tab?.session_id ?? null);
      if (next.key === screen?.key) {
        if (tab) announce(`${tab.code}’s screen`);
      } else {
        announce(`${screenTitle(next, tab)}, screen ${at + 1} of ${n}`);
      }
    },
    [screens, screen],
  );

  // ↑/↓ change screen, ←/→ change whose screen it is.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!screen || !keyIsOurs(e)) return;
      // With one screen there is nowhere to go: leave ↑/↓ to scroll the page.
      if (e.key === "ArrowDown" && screens.length > 1) go(cur + 1);
      else if (e.key === "ArrowUp" && screens.length > 1) go(cur - 1);
      else if (e.key === "ArrowRight" && screen.tabs.length > 1) go(cur, (tabIdx + 1) % screen.tabs.length);
      else if (e.key === "ArrowLeft" && screen.tabs.length > 1)
        go(cur, (tabIdx - 1 + screen.tabs.length) % screen.tabs.length);
      else return;
      e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [go, cur, tabIdx, screen, screens.length]);

  // ── The card's gestures: QuoteGroup's, so a selection acts as one ──
  const vis = useMemo(
    () => deriveTagVisibility(tagInfo, hiddenTagGroups, disabledFrameworks),
    [tagInfo, hiddenTagGroups, disabledFrameworks],
  );
  /** The selection the clicked card belongs to, narrowed to this board; else the card alone. */
  const targets = useCallback(
    (domId: string) => (selectedIds.has(domId) ? boardOrder.filter((d) => selectedIds.has(d)) : [domId]),
    [selectedIds, boardOrder],
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
        userTags={allTags.filter((t) => !vis.hiddenGroups.has(t.codebook_group))}
        allTagNames={allTags.map((t) => t.name)}
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
  // loading, failed or empty as it does with data (lens template).
  const shell = (body: React.ReactNode) => (
    <section>
      <SectionHeading>{TITLE}</SectionHeading>
      {body}
    </section>
  );
  // A failed look with screens already on the page keeps them, and looks again (the poll's retry).
  if (screensError && !data) return shell(<p className="bn-empty-state" role="alert">Couldn’t load the screens.</p>);
  if (quotesError) {
    return shell(<p className="bn-empty-state" role="alert">Couldn’t load the quotes, so the screens can’t show what was said.</p>);
  }
  if (!data) return shell(<p className="bn-empty-state" aria-busy="true">Reading screens…</p>);
  if (!data.enabled) {
    return shell(<p className="bn-empty-state">Screens are off. Turn on Diagnostics to read shared screens.</p>);
  }
  if (data.unavailable) return shell(<p className="bn-empty-state">{unavailableText(data.unavailable)}</p>);
  if (!data.videos) return shell(<p className="bn-empty-state">No recordings with video in this project.</p>);
  if (!screens.length) {
    return shell(
      <div className="bn-empty-state screens-notes" role="status">
        {readingNote(data).map((line) => (
          <p key={line}>{line}</p>
        ))}
        {!stillReading(data) && data.indexed > (data.blank ?? []).length && (
          <p>No screens found: these recordings show no web page with an address or tab title.</p>
        )}
      </div>,
    );
  }
  return (
    <section
      className={`screens-lens${navShown ? "" : " nav-hidden"}`}
      style={{ "--screens-nav-w": `${NAV_W}px` } as React.CSSProperties}
      data-testid="screens-lens"
    >
      {navShown && <ScreenNav screens={screens} cur={cur} onPick={(i) => go(i)} byId={byId} hidden={store.hidden} />}
      {screen && (
        <ScreenBoard
          key={`${screen.key}|${screen.tabs[tabIdx]?.session_id}|${screen.tabs[tabIdx]?.t}`}
          projectId={projectId}
          screen={screen}
          tabIdx={tabIdx}
          onTab={(j) => go(cur, j)}
          byId={byId}
          store={store}
          notes={readingNote(data)}
          renderQuote={renderQuote}
        />
      )}
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
  const participants = new Set(screens.flatMap((s) => s.tabs.map((t) => t.code))).size;
  return (
    <nav className="screens-nav" aria-label="Screens">
      <div className="screens-nav-head">
        {screens.length} {screens.length === 1 ? "screen" : "screens"} · {participants}{" "}
        {participants === 1 ? "participant" : "participants"}
      </div>
      <ol ref={listRef}>
        {screens.map((s, i) => {
          const codes = [...new Set(s.tabs.map((t) => t.code))];
          // What the board would show: each quote once, hidden ones not counted (its "N quotes").
          const said = new Set(
            s.tabs.flatMap((t) => [...t.pins.map((p) => p.dom_id), ...t.loose]).filter((d) => byId.has(d) && !hidden[d]),
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
                  {s.tabs.slice(0, 3).map((t) => (
                    <NavThumb key={`${t.session_id}@${t.t}`} tab={t} />
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
  onTab: (j: number) => void;
  byId: Map<string, QuoteResponse>;
  store: ReturnType<typeof useQuotesStore>;
  notes: string[];
  renderQuote: RenderQuote;
}

interface Geometry {
  stageW: number;
  W: number;
  H: number;
  sx: number;
  sy: number;
  colW: number;
}

interface Drag {
  dom: string;
  left: number;
  top: number;
  width: number;
  z: number;
}

function ScreenBoard(props: BoardProps) {
  const { projectId, screen, tabIdx, byId, store } = props;
  const tab = screen.tabs[tabIdx];
  const still = stillKey(tab.session_id, tab.t);
  const { src, failed: stillFailed } = useStill(tab, 1600);
  const stageRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const shotRef = useRef<HTMLDivElement>(null);
  const cardEls = useRef(new Map<string, HTMLElement>());
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [tops, setTops] = useState<Record<string, { top: number; z: number }>>({});
  const [stacked, setStacked] = useState<Record<Side, boolean>>({ L: false, R: false });
  const [colH, setColH] = useState(0);
  const [leaders, setLeaders] = useState<{ id: string; d: string; end: [number, number] }[]>([]);
  // The card brought forward: on click, never on hover (the owner, 14 Oct 2026, docs/design-screens.md
  // §6.8). Hover flickered: bringing a card forward unclamps its text, the card grows, the column
  // re-stacks around it, a different card is then under the pointer, and hover moves again.
  const [lifted, setLifted] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [spots, setSpots] = useState<Record<string, Spot>>(() => spotsFor(projectId, still));
  const [hiddenOpen, setHiddenOpen] = useState(false);

  const visible = (dom: string) => byId.has(dom) && !store.hidden[dom];
  // No screengrab to pin to: the pinned quotes join the others rather than waiting, hidden, for it.
  const pins = stillFailed ? [] : tab.pins.filter((p) => visible(p.dom_id));
  const pinByDom = new Map(pins.map((p) => [p.dom_id, p]));
  // Everything else said on this screen, by every participant on it.
  const shownPins = new Set(pins.map((p) => p.dom_id));
  const rest = screen.tabs
    .flatMap((t) => [...t.pins.map((p) => p.dom_id), ...t.loose])
    .filter((d, i, a) => a.indexOf(d) === i && !shownPins.has(d) && visible(d))
    .sort((a, b) => (byId.get(a)!.start_timecode - byId.get(b)!.start_timecode));
  const free = new Set(Object.keys(spots).filter((d) => visible(d)));
  const hiddenHere = screen.tabs
    .flatMap((t) => [...t.pins.map((p) => p.dom_id), ...t.loose])
    .filter((d, i, a) => a.indexOf(d) === i && byId.has(d) && store.hidden[d]);

  // Measure the stage and the screengrab.
  useLayoutEffect(() => {
    const measure = () => {
      const stage = stageRef.current, shot = shotRef.current, board = boardRef.current;
      if (!stage || !shot || !board) return;
      const img = shot.querySelector("img");
      const W = img?.clientWidth ?? shot.clientWidth;
      const H = img?.clientHeight ?? 0;
      const col = board.querySelector<HTMLElement>(".screens-col-r");
      const g = { stageW: stage.clientWidth, W, H, sx: shot.offsetLeft, sy: shot.offsetTop, colW: col?.clientWidth ?? 270 };
      setGeo((old) => (old && JSON.stringify(old) === JSON.stringify(g) ? old : g));
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (stageRef.current) ro.observe(stageRef.current);
    if (shotRef.current) ro.observe(shotRef.current);
    return () => ro.disconnect();
  }, [src]);

  const wide = (geo?.stageW ?? 0) >= WIDE_STAGE;
  const sideOf = (p: Pin): Side => sideFor({ x: p.box[0], y: p.box[1], w: p.box[2], h: p.box[3] }, wide);
  const columnPins = pins.filter((p) => !free.has(p.dom_id)).sort((a, b) => a.box[1] - b.box[1]);

  // Place the columns once the cards have heights. Deliberately runs after every render (a card's
  // height changes with tags, edits and width) and sets state only when the placement changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    if (!geo || !geo.H) return;
    const next: Record<string, { top: number; z: number }> = {};
    const nextStacked: Record<Side, boolean> = { L: false, R: false };
    let bottom = geo.H;
    for (const side of ["L", "R"] as Side[]) {
      const col = columnPins.filter((p) => sideOf(p) === side);
      const cards = col.map((p) => ({
        want: Math.max(0, (p.box[1] + p.box[3] / 2) * geo.H - 20),
        height: cardEls.current.get(p.dom_id)?.offsetHeight ?? 120,
      }));
      const { placed, stacked: st, bottom: b } = placeColumn(cards, geo.H);
      col.forEach((p, i) => (next[p.dom_id] = { top: placed[i].top, z: 2 + i }));
      nextStacked[side] = st;
      bottom = Math.max(bottom, b);
    }
    for (const d of free) {
      const s = spots[d];
      const h = cardEls.current.get(d)?.offsetHeight ?? 120;
      bottom = Math.max(bottom, geo.sy + s.y * geo.H + h);
    }
    setTops((old) => (JSON.stringify(old) === JSON.stringify(next) ? old : next));
    setStacked((old) => (old.L === nextStacked.L && old.R === nextStacked.R ? old : nextStacked));
    setColH((old) => (old === bottom ? old : bottom));
  });

  // Leaders, once everything has settled; after every render for the same reason, set on change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    const board = boardRef.current;
    if (!geo || !geo.H || !board) return;
    const bb = board.getBoundingClientRect();
    const next: { id: string; d: string; end: [number, number] }[] = [];
    for (const p of pins) {
      const el = cardEls.current.get(p.dom_id);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const card = { left: r.left - bb.left, top: r.top - bb.top, width: r.width, height: r.height };
      const elem = {
        left: geo.sx + p.box[0] * geo.W, top: geo.sy + p.box[1] * geo.H,
        width: p.box[2] * geo.W, height: p.box[3] * geo.H,
      };
      const { d, end } = leaderPath(card, elem);
      next.push({ id: p.dom_id, d, end });
    }
    setLeaders((old) => (JSON.stringify(old) === JSON.stringify(next) ? old : next));
  });

  // A press on a card brings it forward; Escape, or a press anywhere that is not a card, puts it back.
  // One listener for the board rather than a click handler per card: the keyboard's way in is focus
  // (below), so the cards stay plain wrappers. A press on a drag grip never arrives here (the grip
  // stops it) and lifts its card on release instead, when it was not a drag. Escape is under the
  // same guards as the arrow keys.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && keyIsOurs(e)) setLifted(null);
    };
    const onDown = (e: PointerEvent) => {
      const card = e.target instanceof Element ? e.target.closest<HTMLElement>(".screens-card[data-dom]") : null;
      setLifted(card ? card.dataset.dom ?? null : null);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, []);

  // Drag to rearrange: the card's top edge and the margin under its timecode are the grips. Nothing
  // moves, and nothing is saved, until the pointer has travelled DRAG_THRESHOLD: a click on a grip
  // is not a drag (useVerticalDragResize's 3px). The window listeners belong to this board: if it
  // remounts or changes screengrab mid-drag they are removed, so a release cannot write a spot
  // against the previous screengrab.
  const endDrag = useRef<(() => void) | null>(null);
  useEffect(() => () => endDrag.current?.(), []);
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
    // which remounts it, and a detached grip receives no more pointer events.
    const move = (ev: PointerEvent) => {
      if (!moved && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < DRAG_THRESHOLD) return;
      if (!moved) setLifted(null);
      moved = true;
      setDrag({ dom, ...at(ev), width: r.width, z });
    };
    const detach = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      endDrag.current = null;
    };
    function up(ev: PointerEvent) {
      detach();
      if (!moved) {
        setLifted(dom); // a press on the grip that never became a drag is a press on the card
        return;
      }
      const { left, top } = at(ev);
      putSpot(projectId, still, dom, { x: (left - geo!.sx) / geo!.W, y: (top - geo!.sy) / geo!.H, z });
      setSpots(spotsFor(projectId, still));
      setDrag(null);
    }
    endDrag.current = detach;
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  };

  // The board's wrapper places, lifts and drags a card; the card itself is the Quotes lens's.
  const cardFor = (dom: string, style: React.CSSProperties, pin?: Pin) => {
    const q = byId.get(dom);
    if (!q) return null;
    const cls = ["screens-card", lifted === dom && "is-lifted", drag?.dom === dom && "is-dragging"]
      .filter(Boolean)
      .join(" ");
    return (
      // A card comes forward on a press (the board's listener above), and when keyboard focus
      // enters it so Tab never lands on a
      // control hidden under the next card in a stack. Never on hover. Rearranging is pointer-only
      // for now.
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
        onFocus={() => !drag && setLifted(dom)}
        onBlur={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setLifted((l) => (l === dom ? null : l));
        }}
      >
        <span className="screens-grip screens-grip-top" aria-hidden="true" onPointerDown={startDrag(dom)} />
        <span className="screens-grip screens-grip-side" aria-hidden="true" onPointerDown={startDrag(dom)} />
        {props.renderQuote(q, pin?.phrase ?? "")}
      </div>
    );
  };

  const placed = (dom: string): React.CSSProperties => {
    const p = tops[dom];
    return p ? ({ top: p.top, "--stack": p.z } as React.CSSProperties) : { top: 0, visibility: "hidden" };
  };
  const freeStyle = (dom: string): React.CSSProperties => {
    if (drag?.dom === dom) return { left: drag.left, top: drag.top, width: drag.width, zIndex: drag.z };
    const s = spots[dom];
    if (!geo || !s) return { visibility: "hidden" };
    return { left: geo.sx + s.x * geo.W, top: geo.sy + s.y * geo.H, width: geo.colW, zIndex: s.z };
  };
  const dragOutOfColumn = drag && !free.has(drag.dom) ? drag.dom : null;

  const counterItems: CounterItem[] = hiddenHere.map((d) => {
    const q = byId.get(d)!;
    return {
      domId: d, timecode: formatTimecode(q.start_timecode), seconds: q.start_timecode,
      participantId: q.participant_id, previewText: store.edits[d] ?? q.text, hasMedia: false,
    };
  });

  const said = pins.length + rest.length;
  const people = screen.tabs.length;
  const who =
    screen.tabs.length > 1 ? (
      <span className="screens-who">
        {screen.tabs.map((t, j) => (
          <button key={`${t.session_id}@${t.t}`} aria-pressed={j === tabIdx} title={t.heading} onClick={() => props.onTab(j)}>
            <PersonBadge code={t.code} role="participant" />
          </button>
        ))}
      </span>
    ) : (
      <span className="screens-who">
        <PersonBadge code={tab.code} role="participant" />
      </span>
    );
  return (
    <>
      <SectionHeading action={who}>{screenTitle(screen, tab)}</SectionHeading>
      <p className="screens-sub">
        {screen.name.startsWith("/") && <code>{screen.name}</code>}
        <span>
          {tab.code}’s screen at <span className="timecode">{formatTimecode(tab.t)}</span>
        </span>
        <span>
          {said} {said === 1 ? "quote" : "quotes"}
          {people > 1 ? ` from ${people} participants` : ""}
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
        {Object.keys(spots).length > 0 && (
          <button
            className="screens-putback"
            onClick={() => {
              clearSpots(projectId, still);
              setSpots({});
            }}
          >
            Put the quotes back
          </button>
        )}
      </p>
      {props.notes.length > 0 && (
        <div className="screens-notes" role="status">
          {props.notes.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}
      <div className={`screens-stage${lifted ? " focus" : ""}${drag ? " dragging" : ""}`} ref={stageRef}>
        <div className="screens-board" ref={boardRef} style={{ minHeight: colH || undefined }}>
          <div className={`screens-col screens-col-l${stacked.L ? " stacked" : ""}`} style={{ height: colH || undefined }}>
            {columnPins.filter((p) => sideOf(p) === "L" && p.dom_id !== dragOutOfColumn).map((p) => cardFor(p.dom_id, placed(p.dom_id), p))}
          </div>
          <div className="screens-shot" ref={shotRef}>
            {src ? (
              <img alt={`${tab.code}’s screen: ${screenTitle(screen, tab)}, at ${formatTimecode(tab.t)}`} src={src} />
            ) : (
              <div className="screens-shot-wait">
                {stillFailed && <span className="screens-shot-error">Screengrab unavailable.</span>}
              </div>
            )}
            {geo &&
              pins.map((p) => (
                <div
                  key={p.dom_id}
                  className={`screens-hl${lifted === p.dom_id ? " on" : ""}`}
                  style={{
                    left: p.box[0] * geo.W - 3, top: p.box[1] * geo.H - 3,
                    width: p.box[2] * geo.W + 6, height: p.box[3] * geo.H + 6,
                  }}
                />
              ))}
          </div>
          <div className={`screens-col screens-col-r${stacked.R ? " stacked" : ""}`} style={{ height: colH || undefined }}>
            {columnPins.filter((p) => sideOf(p) === "R" && p.dom_id !== dragOutOfColumn).map((p) => cardFor(p.dom_id, placed(p.dom_id), p))}
          </div>
          <svg className="screens-leaders" aria-hidden="true">
            {leaders.map((l) => (
              <g key={l.id} className={lifted === l.id ? "on" : undefined}>
                <path d={l.d} />
                <circle cx={l.end[0]} cy={l.end[1]} r={2.5} />
              </g>
            ))}
          </svg>
          <div className="screens-free">
            {[...free, ...(dragOutOfColumn ? [dragOutOfColumn] : [])]
              .filter((d, i, a) => a.indexOf(d) === i)
              .map((d) => cardFor(d, freeStyle(d), pinByDom.get(d)))}
          </div>
        </div>
        <div className="screens-loose">
          {rest.filter((d) => !free.has(d) && d !== dragOutOfColumn).map((d) => cardFor(d, {}))}
        </div>
      </div>
    </>
  );
}
