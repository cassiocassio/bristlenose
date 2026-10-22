/**
 * TranscriptPage — React island for standalone transcript pages.
 *
 * Replaces the static back link, heading, and transcript body with a
 * React-rendered version that pulls data from the transcript API.
 * Coexists with the vanilla JS IIFE (player.js, transcript-names.js,
 * transcript-annotations.js) — those scripts become inert because
 * React replaces the DOM they target.
 *
 * Player integration: emits the same DOM attributes (data-participant,
 * data-start-seconds, data-end-seconds, class="transcript-segment")
 * so player.js glow index works without modification.
 */

import { useEffect, useState, useRef, useLayoutEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import i18n from "../i18n";
import { JourneyChain, PersonBadge, TimecodeLink } from "../components";
import { SpeakerPickerTrigger } from "../components/SpeakerPickerTrigger";
import { useSpeakersChanged } from "../hooks/useSpeakersChanged";
import { useLastRun } from "../contexts/LastRunStore";
import {
  captureReadingAnchor,
  readerIsBusy,
  restoreReadingAnchor,
  type ReadingAnchor,
} from "../utils/readingAnchor";
import { Badge } from "../components/Badge";
import { GutterEntry } from "./transcript/GutterEntry";
import { GutterThumb } from "./transcript/GutterThumb";
import { screenStarts, screensPath, screenTitle, type ScreenLike, type ScreenStart } from "./screens/screenModel";
import { reportHref } from "../utils/reportHref";
import { discussionPath, questionsAsked, type QuestionAsked } from "./discussion/discussionLinks";
import type { DiscussionData } from "./discussion/types";
import { useGutterHover } from "./transcript/useGutterHover";
import { TimelineSplit } from "./transcript/TimelineSplit";
import { TranscriptTimeline } from "./transcript/TranscriptTimeline";
import {
  onTimelineWillChange,
  setTimelineAvailable,
  useTranscriptTimeline,
} from "../contexts/TranscriptTimelineStore";
import "./transcript/transcript-gutter.css";
import { quoteExtents } from "../utils/quoteExtents";
import { followInApp, quotesHref, quotesPath } from "../utils/quotesLink";
import { Selector } from "../components/Selector";
import { isEmbedded } from "../utils/embedded";
import { isExportMode } from "../utils/exportData";
import { redo, undo } from "../contexts/UndoStore";
import { resetParagraphScope } from "../utils/paragraphScope";
import { copyTranscriptSelection } from "../utils/transcriptCopy";
import { drawsCapital } from "../utils/sentenceStart";
import {
  TRANSCRIPT_WRITTEN_EVENT,
  caretAtStart,
  caretWords,
  drawnTokens,
  joinParagraphs,
  splitParagraph,
  verifyOf,
} from "../utils/paragraphEdits";
import {
  apiGet,
  getTranscript,
  getSessionList,
  patchDeletedBadges,
  patchTags,
} from "../utils/api";
import type { ApiError, SessionListItem } from "../utils/api";
import { formatFinderDate, formatTimecode } from "../utils/format";
import { getTagBg } from "../utils/colours";
import { markArrived } from "../utils/arrival";
import { segmentIndexAt } from "../utils/segmentAt";
import { announce } from "../utils/announce";
import { ErrorNotice } from "../components/RouteError";
import type {
  TapestryResponse,
  TapestrySession,
  TranscriptPageResponse,
  TranscriptSegmentResponse,
  TranscriptSpeakerResponse,
  QuoteAnnotationResponse,
} from "../utils/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TranscriptPageProps {
  projectId: string;
  sessionId: string;
}

// ---------------------------------------------------------------------------
// Journey scroll sync hook
// ---------------------------------------------------------------------------

interface JourneyWaypoint {
  anchorId: string;
  label: string;
}

/**
 * Build an ordered list of section waypoints for scroll tracking.
 * Includes revisits — if a user navigates Dashboard → Search → Dashboard,
 * three waypoints are returned, not two.
 */
function buildWaypoints(
  segments: TranscriptSegmentResponse[],
  annotations: Record<string, QuoteAnnotationResponse>,
): JourneyWaypoint[] {
  const waypoints: JourneyWaypoint[] = [];
  let lastLabel = "";

  for (const seg of segments) {
    if (!seg.is_quoted) continue;
    for (const qid of seg.quote_ids) {
      const ann = annotations[qid];
      if (!ann || ann.label_type !== "section" || !ann.label) continue;

      // New section boundary → record waypoint
      if (ann.label !== lastLabel) {
        const anchorId = `t-${Math.floor(seg.start_time)}`;
        waypoints.push({ anchorId, label: ann.label });
        lastLabel = ann.label;
      }
      break; // Only need first annotation per segment for section mapping
    }
  }

  return waypoints;
}

/**
 * Resolve a target time (seconds) to the best transcript segment: the segment
 * that contains it, else the nearest segment starting at/after it, else the
 * last segment. Used by the deep-link hash-scroll so a `#t-<seconds>` anchor
 * that doesn't land exactly on a segment id (e.g. a quote that starts
 * mid-segment) still scrolls to a real segment. Segments are time-ordered.
 */
/**
 * The paragraph a moment falls in, by position: the one containing it, else (a moment in a pause)
 * the next to start; past the end of the transcript, none — a screen visited after the last word
 * is not drawn on the last paragraph.
 */
function paragraphIndexAt(segments: TranscriptSegmentResponse[], sec: number): number | null {
  for (let i = 0; i < segments.length; i++) {
    const s = segments[i];
    if ((s.start_time <= sec && sec < s.end_time) || s.start_time >= sec) return i;
  }
  return null;
}

/**
 * The moderator's paragraph a question was asked in: the one containing its moment, else the
 * moderator paragraph starting nearest it within 3 s. Never a participant's paragraph: a question
 * mark belongs on the question.
 */
function moderatorParagraphAt(segments: TranscriptSegmentResponse[], sec: number): number | null {
  let best: number | null = null;
  let gap = Infinity;
  for (let i = 0; i < segments.length; i++) {
    const s = segments[i];
    if (!s.is_moderator) continue;
    if (s.start_time <= sec && sec < s.end_time) return i;
    const d = Math.abs(s.start_time - sec);
    if (d <= 3 && d < gap) {
      gap = d;
      best = i;
    }
  }
  return best;
}

/** Two names compared as words: case and punctuation aside ("Shopping bag" is "Shopping Bag"). */
function norm(s: string): string {
  return s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

function resolveSegmentForSeconds(
  segments: TranscriptSegmentResponse[],
  target: number,
): TranscriptSegmentResponse | null {
  return segments[segmentIndexAt(segments, target)] ?? null;
}

function useJourneyScrollSync(
  segments: TranscriptSegmentResponse[],
  annotations: Record<string, QuoteAnnotationResponse>,
  headerRef: React.RefObject<HTMLElement | null>,
) {
  // The full sequence including revisits, rebuilt when the transcript is
  // re-read: during a first analysis a session's quotes, and so its sections,
  // arrive after its transcript (docs/design-progressive-lenses.md).
  const waypoints = useMemo(
    () => (segments.length > 0 ? buildWaypoints(segments, annotations) : []),
    [segments, annotations],
  );

  const [activeIndex, setActiveIndex] = useState<number | null>(
    waypoints.length > 0 ? 0 : null,
  );
  const isUserScrolling = useRef(true);
  const scrollLockTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Labels derived from waypoints — the full sequence with revisits
  const journeyLabels = waypoints.map((wp) => wp.label);

  // Scroll event handler — find which waypoint index is at the top of viewport
  useEffect(() => {
    if (waypoints.length === 0) return;

    let rafId = 0;

    function locate() {
      const header = headerRef.current;
      const threshold = header
        ? header.getBoundingClientRect().bottom + 8
        : 60;

      let currentIndex = 0;
      for (let i = 0; i < waypoints.length; i++) {
        const el = document.getElementById(waypoints[i].anchorId);
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        if (rect.top <= threshold) {
          currentIndex = i;
        } else {
          break;
        }
      }

      setActiveIndex(currentIndex);
    }

    function onScroll() {
      if (!isUserScrolling.current) return;
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(locate);
    }

    // Waypoints rebuilt by a re-read (sections arriving): place the
    // highlight now, not at the next scroll.
    locate();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(rafId);
    };
  }, [waypoints, headerRef]);

  const handleIndexClick = useCallback(
    (index: number) => {
      if (index < 0 || index >= waypoints.length) return;
      const anchorId = waypoints[index].anchorId;

      // Suppress scroll observer during programmatic scroll
      isUserScrolling.current = false;
      setActiveIndex(index);

      const el = document.getElementById(anchorId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      // Re-enable scroll tracking after animation
      if (scrollLockTimer.current) clearTimeout(scrollLockTimer.current);
      scrollLockTimer.current = setTimeout(() => {
        isUserScrolling.current = true;
      }, 600);
    },
    [waypoints],
  );

  // No sections, no highlight (a re-read can take them away).
  return { activeIndex: waypoints.length > 0 ? activeIndex : null, handleIndexClick, journeyLabels };
}

// ---------------------------------------------------------------------------
// Session selector helpers
// ---------------------------------------------------------------------------

function renderSessionItem(s: SessionListItem): React.ReactNode {
  const participants = s.speakers.filter((sp) => sp.role === "participant");
  return (
    <>
      <strong>Session {s.session_number}</strong>
      {s.session_date && (
        <span className="bn-selector__detail">{formatFinderDate(s.session_date, i18n.language)}</span>
      )}
      {participants.map((sp) => (
        <PersonBadge
          key={sp.speaker_code}
          code={sp.speaker_code}
          role="participant"
          name={sp.name && sp.name !== sp.speaker_code ? sp.name : undefined}
        />
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Session roles helpers (moderator/observer line below sticky header)
// ---------------------------------------------------------------------------

/** Render a list of speakers as badge + name fragments with Oxford-comma joining. */
function oxfordJoin(people: TranscriptSpeakerResponse[], sessionId: string): React.ReactNode[] {
  return people.map((sp, i) => {
    const badgeRole = sp.code.startsWith("m")
      ? "moderator" as const
      : "observer" as const;
    const person = (
      <span key={sp.code} className="bn-transcript-roles__person">
        <SpeakerPickerTrigger
          sessionId={sessionId}
          code={sp.code}
          role={badgeRole}
          name={sp.name !== sp.code ? sp.name : undefined}
        />
      </span>
    );
    if (i === 0) return person;
    if (i === people.length - 1) {
      const sep = people.length > 2 ? ", and " : " and ";
      return <span key={sp.code}>{sep}{person}</span>;
    }
    return <span key={sp.code}>, {person}</span>;
  });
}

/** Render the session roles line (moderators + observers). Returns null if none. */
function renderSessionRoles(
  speakers: TranscriptSpeakerResponse[],
  t: TFunction,
  sessionId: string,
): React.ReactNode | null {
  const moderators = speakers.filter((s) => s.role === "researcher");
  const observers = speakers.filter((s) => s.role === "observer");
  if (moderators.length === 0 && observers.length === 0) return null;

  return (
    <div className="bn-transcript-roles" data-testid="transcript-roles">
      {moderators.length > 0 && (
        <span>
          {moderators.length === 1
            ? `${t("transcript.moderator")} `
            : `${t("transcript.moderators")} `}
          {oxfordJoin(moderators, sessionId)}
        </span>
      )}
      {moderators.length > 0 && observers.length > 0 && ", "}
      {observers.length > 0 && (
        <span>
          {moderators.length > 0
            ? (observers.length === 1
                ? `${t("transcript.observer").toLowerCase()} `
                : `${t("transcript.observers").toLowerCase()} `)
            : (observers.length === 1
                ? `${t("transcript.observer")} `
                : `${t("transcript.observers")} `)}
          {oxfordJoin(observers, sessionId)}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Inside a non-editable island of the transcript (timecode, speaker, margin). */
function inIsland(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest('[contenteditable="false"]') !== null;
}

/** Where a page for a session the report no longer has points back to. */
const SESSIONS_PATH = "/report/sessions";

export function TranscriptPage({ projectId: _projectId, sessionId }: TranscriptPageProps) {
  void _projectId; // API base URL from window global already includes project ID
  const { t } = useTranslation();
  const [data, setData] = useState<TranscriptPageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The server's answer was "no such session" (a re-run removed it): Retry
  // would reload into the same 404 (RE#20, decision #55).
  const [sessionGone, setSessionGone] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sessionList, setSessionList] = useState<SessionListItem[]>([]);
  const bodyRef = useRef<HTMLElement | null>(null);
  const headerRef = useRef<HTMLDivElement | null>(null);

  // Every read of the transcript takes a ticket; only the newest is applied.
  // The page stays mounted across sessions, and during a run re-reads come
  // every few seconds, so an older response (another session's, or one sent
  // before a split's own re-read) must never land over a newer one.
  const readTicket = useRef(0);
  //: Local writes this page made (a deleted badge or tag): a re-read sent
  //: before one may return the state before it.
  const localWrites = useRef(0);

  // Fetch transcript data
  useEffect(() => {
    const ticket = ++readTicket.current;
    setLoading(true);
    getTranscript(sessionId)
      .then((resp) => {
        if (ticket !== readTicket.current) return;
        setData(resp);
        setError(null);
        setSessionGone(false);
      })
      .catch((err) => {
        if (ticket !== readTicket.current) return;
        // The wire string is for the console; the lens says it in its own words (R86).
        console.error("Transcript read failed:", err);
        // Never empty: an empty string reads as "no error" and the page would
        // say there is no transcript.
        setError(String(err?.message || "read failed"));
        // The session's own 404 names itself; a missing project does not.
        setSessionGone((err as ApiError | null)?.reason === "session_not_found");
      })
      .finally(() => {
        if (ticket === readTicket.current) setLoading(false);
      });
  }, [sessionId]);

  // Every re-read keeps the reader's place: the first paragraph under the
  // sticky header stays where it is however much moves above it.
  const pendingAnchor = useRef<ReadingAnchor | null>(null);
  const applyReread = useCallback((resp: TranscriptPageResponse) => {
    const body = bodyRef.current;
    const threshold = headerRef.current?.getBoundingClientRect().bottom ?? 0;
    pendingAnchor.current = body ? captureReadingAnchor(body, threshold) : null;
    setData(resp);
    setError(null);
  }, []);
  useLayoutEffect(() => {
    const anchor = pendingAnchor.current;
    pendingAnchor.current = null;
    if (anchor && bodyRef.current) restoreReadingAnchor(bodyRef.current, anchor);
  }, [data]);

  // Re-read after a speaker is named, picked or cleared — here or by undo.
  const reloadTranscript = useCallback(() => {
    const ticket = ++readTicket.current;
    getTranscript(sessionId)
      .then((resp) => {
        if (ticket === readTicket.current) applyReread(resp);
      })
      .catch(() => undefined);
  }, [sessionId, applyReread]);
  useSpeakersChanged(reloadTranscript);
  // …and after a paragraph split or join, or its undo.
  useEffect(() => {
    window.addEventListener(TRANSCRIPT_WRITTEN_EVENT, reloadTranscript);
    return () => window.removeEventListener(TRANSCRIPT_WRITTEN_EVENT, reloadTranscript);
  }, [reloadTranscript]);

  // Splitting and joining paragraphs: not in an exported report, which has no
  // server to keep them.
  const paragraphEditing = !isExportMode();
  // The picker's Paragraph scope sticks for a run of paragraphs and goes back
  // to Session on leaving this transcript (design-people.md §K).
  useEffect(() => () => resetParagraphScope(), [sessionId]);
  // The browser's own input events — typing, dictation, autocorrect, a context
  // menu's delete — never edit a paragraph. Native, not React's onBeforeInput,
  // which is a keypress polyfill and misses most of them.
  useEffect(() => {
    const body = bodyRef.current;
    if (!body || !paragraphEditing) return;
    // Only the paragraphs' text: the islands hold real inputs (the speaker
    // picker's name field) that must still take typing.
    const refuse = (e: Event) => {
      if (!inIsland(e.target)) e.preventDefault();
    };
    body.addEventListener("beforeinput", refuse);
    return () => body.removeEventListener("beforeinput", refuse);
  }, [paragraphEditing, data]);
  const onTranscriptKey = useCallback(
    (e: React.KeyboardEvent<HTMLElement>) => {
      const mod = e.metaKey || e.ctrlKey;
      // The page's own ⌘Z stands down inside editable text, so the report's
      // undo is reached from here.
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        void (e.shiftKey ? redo() : undo());
        return;
      }
      if (mod || e.altKey) return;
      if (e.key !== "Enter" && e.key !== "Backspace") return;
      // A key in an island is the island's (a timecode link's Enter, the
      // picker's Backspace); an IME's Enter confirms its composition.
      if (inIsland(e.target) || e.nativeEvent.isComposing) return;
      // The whole transcript is one editable region, so a selection can run
      // across paragraphs; the paragraph is the one holding the caret.
      e.preventDefault();
      const anchor = window.getSelection()?.anchorNode ?? null;
      const el = anchor instanceof Element ? anchor : anchor?.parentElement ?? null;
      const paragraph = el?.closest<HTMLElement>(".segment-body[data-position]");
      if (!paragraph) return;
      const position = Number(paragraph.dataset.position);
      const segs = data?.segments ?? [];
      const seg = segs[position];
      if (!seg) return;
      const tokens = drawnTokens(seg.text, seg.words);
      if (e.key === "Enter") {
        const token = caretWords(paragraph);
        if (token === null || token <= 0 || token >= tokens.length) return;
        void splitParagraph(sessionId, position, token, verifyOf(tokens, token)).catch(() => undefined);
      } else if (caretAtStart(paragraph)) {
        const above = segs[position - 1];
        if (!above || above.speaker_code !== segs[position]?.speaker_code) return;
        void joinParagraphs(sessionId, position, verifyOf(tokens, 0)).catch(() => undefined);
      }
    },
    [sessionId, data],
  );

  // Fetch session list for dropdown
  useEffect(() => {
    getSessionList()
      .then(setSessionList)
      .catch(() => {}); // Non-critical — dropdown just won't show
  }, []);

  // New data while the transcript is open: during a first analysis this
  // session's quotes arrive after its transcript, other sessions become
  // readable, and the whole report lands at the end
  // (docs/design-progressive-lenses.md). The report's refresh key moves for
  // each; the transcript re-reads without its loading screen. Not while the
  // reader is selecting text or typing in a field: the re-read waits until
  // they stop.
  const { refreshKey } = useLastRun();
  const seenRefreshKey = useRef(refreshKey);
  const rereadOwed = useRef(false);
  const loaded = !loading && !!data;
  // The latest rereadNow, for the retry its own closure schedules.
  const rereadRef = useRef<() => void>(() => {});
  const rereadNow = useCallback(() => {
    rereadOwed.current = false;
    const ticket = ++readTicket.current;
    const writesBefore = localWrites.current;
    getTranscript(sessionId)
      .then((resp) => {
        if (ticket !== readTicket.current) return;
        if (localWrites.current !== writesBefore) {
          // A badge or tag was deleted while this was in flight, and the
          // response may predate it: read again once the write has gone.
          setTimeout(() => rereadRef.current(), 500);
          return;
        }
        if (bodyRef.current && readerIsBusy(bodyRef.current)) {
          rereadOwed.current = true; // they started meanwhile: later
          return;
        }
        applyReread(resp);
      })
      .catch(() => undefined);
    getSessionList().then(setSessionList).catch(() => {});
  }, [sessionId, applyReread]);
  useEffect(() => {
    rereadRef.current = rereadNow;
  }, [rereadNow]);
  useEffect(() => {
    if (refreshKey === seenRefreshKey.current) return;
    seenRefreshKey.current = refreshKey;
    // The first read was sent before this bump and may predate what it
    // announces: owe a re-read for when it lands.
    if (loading) {
      rereadOwed.current = true;
      return;
    }
    if (bodyRef.current && readerIsBusy(bodyRef.current)) {
      rereadOwed.current = true;
      return;
    }
    rereadNow(); // also recovers a page that failed to load
  }, [refreshKey, loading, rereadNow]);
  useEffect(() => {
    if (loaded && rereadOwed.current && !(bodyRef.current && readerIsBusy(bodyRef.current))) {
      rereadNow();
    }
  }, [loaded, rereadNow]);
  useEffect(() => {
    const settle = () => {
      if (!rereadOwed.current) return;
      // After the event: focus has not moved yet during `focusout`.
      setTimeout(() => {
        if (rereadOwed.current && bodyRef.current && !readerIsBusy(bodyRef.current)) {
          rereadNow();
        }
      }, 0);
    };
    document.addEventListener("selectionchange", settle);
    document.addEventListener("focusout", settle);
    return () => {
      document.removeEventListener("selectionchange", settle);
      document.removeEventListener("focusout", settle);
    };
  }, [rereadNow]);

  // Anchor highlight after render — once per session and link: a re-read
  // must not pull the reader back to the anchor they arrived at.
  const anchoredFor = useRef<string | null>(null);
  useEffect(() => {
    if (!data || loading) return;
    const hash = window.location.hash;
    if (!hash) {
      anchoredFor.current = null; // a later visit by the same link scrolls again
      return;
    }
    if (anchoredFor.current === `${sessionId}${hash}`) return;
    anchoredFor.current = `${sessionId}${hash}`;
    const targetId = hash.slice(1); // strip #
    // Defer to next frame so DOM is ready
    requestAnimationFrame(() => {
      let el = document.getElementById(targetId);
      // Tolerant fallback for #t-<seconds> deep-links (e.g. from the Sessions
      // lens journey): the target may not land exactly on a segment id, so
      // resolve to the containing/nearest segment. Match the timecode at the
      // END of the hash so it works under hash routing too, where the full
      // hash is "#/report/sessions/s1#t-589" (export mode), not just "#t-589".
      if (!el) {
        const m = /t-(\d+)$/.exec(hash);
        if (m) {
          const seg = resolveSegmentForSeconds(data.segments, Number(m[1]));
          if (seg) el = document.getElementById(`t-${Math.floor(seg.start_time)}`);
        }
      }
      if (el) {
        markArrived(el);
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }, [data, loading, sessionId]);

  // Journey scroll sync (derives full label sequence from waypoints)
  const { activeIndex, handleIndexClick, journeyLabels } = useJourneyScrollSync(
    data?.segments ?? [],
    data?.annotations ?? {},
    headerRef,
  );

  // Measure sticky header height for scroll-margin-top. Depends on the speaker
  // list too — the header carries participant badges, so two journey-less
  // sessions with different participant counts have different header heights.
  // The timeline changes it too, after a lazy load: the observer below keeps it.
  useLayoutEffect(() => {
    if (headerRef.current) {
      const height = headerRef.current.offsetHeight;
      document.documentElement.style.setProperty(
        "--bn-journey-header-height",
        `${height}px`,
      );
    }
  }, [journeyLabels, data?.speakers]);

  // ── The sticky slot: the journey chain, or the session timeline
  // (docs/mockups/transcript-timeline-toggle.html). The timeline is the Sessions grid's, for this
  // session; the split control appears only when there is one to show.
  const timeline = useTranscriptTimeline();
  const [tapestry, setTapestry] = useState<TapestrySession | null>(null);
  // A failed read keeps what was known and looks again on the next re-read: one failure used to
  // take the Timeline control away, or a showing timeline, for the rest of the view (R92).
  const [tapestryFailed, setTapestryFailed] = useState(false);
  // Once per session to learn whether there is a timeline; while it shows, or after a failed
  // read, again on every re-read (during a first analysis its sections and quotes arrive with the
  // transcript's).
  const tapestryKey = timeline.on || tapestryFailed ? data?.segments : null;
  useEffect(() => {
    let live = true;
    apiGet<TapestryResponse>("/tapestry")
      .then((r) => {
        if (!live) return;
        setTapestry((r.sessions ?? []).find((x) => x.session_id === sessionId) ?? null);
        setTapestryFailed(false);
      })
      .catch(() => {
        if (live) setTapestryFailed(true);
      });
    return () => {
      live = false;
    };
  }, [sessionId, tapestryKey]);
  const hasTimeline = !!tapestry && tapestry.session_id === sessionId && tapestry.turns.length > 0;
  useEffect(() => {
    setTimelineAvailable(hasTimeline);
    return () => setTimelineAvailable(false);
  }, [hasTimeline]);
  const showTimeline = hasTimeline && timeline.on;

  // Switching keeps the reader's place: the paragraph under the header stays the same distance
  // below it, however the header grows or shrinks — the switch itself, then the timeline's lazy
  // chunk landing a moment later. Captured before the change (whoever made it: the split control
  // or the Mac's View menu), applied as the header resizes; the reader's own scroll cancels it.
  const placeRef = useRef<{ el: HTMLElement; offset: number; until: number } | null>(null);
  useEffect(() => onTimelineWillChange(() => {
    const body = bodyRef.current;
    const header = headerRef.current;
    if (!body || !header) return;
    const hb = header.getBoundingClientRect().bottom;
    const el = Array.from(body.querySelectorAll<HTMLElement>(".transcript-segment"))
      .find((p) => p.getBoundingClientRect().bottom > hb);
    placeRef.current = el ? { el, offset: el.getBoundingClientRect().top - hb, until: performance.now() + 1500 } : null;
  }), []);
  const headerShown = !loading && !!data;
  useEffect(() => {
    const header = headerRef.current;
    if (!header || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      document.documentElement.style.setProperty("--bn-journey-header-height", `${header.offsetHeight}px`);
      const place = placeRef.current;
      if (!place || performance.now() > place.until || !place.el.isConnected) return;
      const drift = place.el.getBoundingClientRect().top - header.getBoundingClientRect().bottom - place.offset;
      if (Math.abs(drift) >= 1) window.scrollBy(0, drift);
    });
    ro.observe(header);
    // The reader's own scroll cancels a pending correction. A key inside the header is not that:
    // choosing from the pulldown by keyboard is the change being corrected for.
    const cancel = (e: Event) => {
      if (e.target instanceof Node && header.contains(e.target)) return;
      placeRef.current = null;
    };
    window.addEventListener("wheel", cancel, { passive: true });
    window.addEventListener("touchstart", cancel, { passive: true });
    window.addEventListener("keydown", cancel);
    return () => {
      ro.disconnect();
      window.removeEventListener("wheel", cancel);
      window.removeEventListener("touchstart", cancel);
      window.removeEventListener("keydown", cancel);
    };
  }, [headerShown]);

  // A click on the timeline scrolls this page to the paragraph holding that moment — the
  // resolver a #t- deep link uses — flashes it, and writes #t-<s> in place (shareable; Back still
  // leaves the page). It never navigates: the Sessions grid's timeline does that.
  const paragraphAt = useCallback((sec: number): HTMLElement | null => {
    const i = segmentIndexAt(data?.segments ?? [], sec);
    return i < 0 ? null : bodyRef.current?.querySelectorAll<HTMLElement>(".transcript-segment")[i] ?? null;
  }, [data]);
  const timelineJump = useCallback((sec: number) => {
    const el = paragraphAt(sec);
    if (!el) return;
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    el.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    markArrived(el);
    // Heard as well as seen: the paragraph's time and first words, as the timeline announces a quote.
    const seg = data?.segments[segmentIndexAt(data.segments, sec)];
    if (seg) announce([formatTimecode(seg.start_time), seg.text.slice(0, 80)].join(", "));
    const tag = `#t-${Math.floor(Number(el.dataset.startSeconds) || 0)}`;
    const { pathname, search, hash } = window.location;
    // Hash routing (an export) keeps its route: "#/report/sessions/s1#t-589".
    const next = hash.startsWith("#/") ? hash.replace(/#t-\d+$/, "") + tag : tag;
    try {
      window.history.replaceState(window.history.state, "", `${pathname}${search}${next}`);
    } catch {
      // A sandboxed frame may refuse; the scroll has happened all the same.
    }
    // Already there: a later re-read must not scroll back to it.
    anchoredFor.current = `${sessionId}${window.location.hash}`;
  }, [paragraphAt, sessionId, data]);
  // Dragging the reading window: straight there, no flash, no hash — the reader is still moving.
  const timelineScrub = useCallback((sec: number) => {
    paragraphAt(sec)?.scrollIntoView({ block: "start" });
  }, [paragraphAt]);
  const speakerNameOf = useCallback((slot: string) => {
    const sp = data?.speakers.find((x) => x.code === slot);
    return sp?.name || slot;
  }, [data?.speakers]);

  // Deleted badge / tag callbacks
  const handleDeleteBadge = useCallback(
    (quoteId: string, sentiment: string) => {
      if (!data || isExportMode()) return;
      const ann = data.annotations[quoteId];
      if (!ann) return;
      const updated = [...ann.deleted_badges, sentiment];
      localWrites.current += 1;
      setData({
        ...data,
        annotations: {
          ...data.annotations,
          [quoteId]: { ...ann, deleted_badges: updated },
        },
      });
      // Only this quote's change. A one-quote map sent as the whole map wiped
      // every other quote's deleted badges (and, below, tags) in the project.
      // A write that fails has already said why; reading the transcript again
      // draws what the server kept.
      patchDeletedBadges({ [quoteId]: { add: [sentiment] } }).catch(() => rereadRef.current());
    },
    [data],
  );

  const handleDeleteTag = useCallback(
    (quoteId: string, tagName: string) => {
      if (!data || isExportMode()) return;
      const ann = data.annotations[quoteId];
      if (!ann) return;
      const updated = ann.tags.filter((t) => t.name !== tagName);
      localWrites.current += 1;
      setData({
        ...data,
        annotations: {
          ...data.annotations,
          [quoteId]: { ...ann, tags: updated },
        },
      });
      patchTags({ [quoteId]: { remove: [tagName] } }).catch(() => rereadRef.current());
    },
    [data],
  );

  // Which drawn words belong to which quote (docs/design-transcript-gutter.md, "The data"),
  // and the sheet the hover keyline is drawn over.
  const extents = useMemo(
    () => (data
      ? quoteExtents(data.segments, Object.fromEntries(Object.entries(data.annotations).map(([id, a]) => [
          id, { excerpt: a.verbatim_excerpt, start: a.start_timecode, end: a.end_timecode, participant: a.participant_id },
        ])))
      : null),
    [data],
  );
  // A quote's details show once, at the first paragraph that draws its words (or, if none does,
  // the first the server matched it to by time). Per load, not per render: the journey's scroll
  // sync re-renders the page as the reader scrolls.
  const firstParagraphOf = useMemo(() => {
    const first = new Map<string, number>();
    if (!data) return first;
    data.segments.forEach((_seg, position) => {
      for (const q of extents?.owners[position] ?? []) if (q && !first.has(q)) first.set(q, position);
    });
    data.segments.forEach((seg, position) => {
      for (const q of seg.quote_ids) if (!first.has(q)) first.set(q, position);
    });
    return first;
  }, [data, extents]);
  const sheetRef = useRef<HTMLDivElement | null>(null);
  useGutterHover(sheetRef, loading ? null : data);

  // The screens this session was on (stage 2): the Screens lens's own read, in serve only — an
  // export carries no screens. Off or unavailable: no screen marks. Re-read when the report moves
  // on, and every 20 s while screen text is still being read (up to 15 times), so a transcript
  // opened mid-read gains its marks. A failed read draws no marks and says so in the console.
  const [screens, setScreens] = useState<ScreenLike[]>([]);
  useEffect(() => {
    if (isExportMode()) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = (attempt: number) => {
      apiGet<{ enabled: boolean; unavailable: string | null; pending?: boolean; screens: ScreenLike[] }>("/screens")
        .then((r) => {
          if (!live) return;
          setScreens(r.enabled && !r.unavailable ? r.screens : []);
          if (r.pending && attempt < 15) timer = setTimeout(() => load(attempt + 1), 20000);
        })
        .catch((e: unknown) => {
          console.warn("Transcript: /screens failed; no screen marks", e);
          if (live) setScreens([]);
        });
    };
    load(0);
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [sessionId, refreshKey]);
  // The questions this session's moderator asked of the guide (stage 3): the Discussion lens's
  // record, ready or partial — the states the lens shows. Embedded in an export, so it works
  // offline. Not run, stale or failed: no question marks. Re-read when the report moves on.
  const [discussion, setDiscussion] = useState<DiscussionData | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<{ status: string; record?: DiscussionData | null }>("/discussion")
      .then((r) => {
        const usable = (r.status === "ready" || r.status === "partial") && r.record?.version === 1;
        if (r.record && r.record.version !== 1) console.warn("Transcript: a discussion record this build cannot read", r.record.version);
        if (live) setDiscussion(usable ? r.record! : null);
      })
      .catch((e: unknown) => {
        console.warn("Transcript: /discussion failed; no question marks", e);
        if (live) setDiscussion(null);
      });
    return () => {
      live = false;
    };
  }, [sessionId, refreshKey]);
  const askedByParagraph = useMemo(() => {
    if (!data || !discussion) return new Map<number, QuestionAsked[]>();
    return questionsAsked(discussion, sessionId, (sec) => moderatorParagraphAt(data.segments, sec));
  }, [discussion, sessionId, data]);
  const startsByParagraph = useMemo(() => {
    if (!data || screens.length === 0) return new Map<number, ScreenStart[]>();
    return screenStarts(screens, sessionId, (sec) => paragraphIndexAt(data.segments, sec));
  }, [screens, sessionId, data]);

  // Loading state
  if (loading) {
    return (
      <div className="bn-loading" data-testid="transcript-loading">
        {t("transcript.loading")}
      </div>
    );
  }

  // Error state
  if (error || !data) {
    return (
      <div className="bn-error" data-testid="transcript-error">
        {error && sessionGone ? (
          <div className="bn-empty-state" role="status">
            <p>{t("transcript.sessionGone")}</p>
            <a
              href={reportHref(SESSIONS_PATH)}
              onClick={(e) => followInApp(e, SESSIONS_PATH)}
            >
              {t("transcript.allSessions")}
            </a>
          </div>
        ) : error ? (
          <ErrorNotice scope="lens" />
        ) : (
          t("transcript.noData")
        )}
      </div>
    );
  }

  const { segments, speakers, annotations } = data;
  const sessionNum = sessionId.length > 1 && "sp".includes(sessionId[0]) && /^\d+$/.test(sessionId.slice(1))
    ? sessionId.slice(1)
    : sessionId;

  const hasJourney = journeyLabels.length > 0;
  // Participants are named in the sticky header, so "who is p2" stays on screen.
  // Segment badges below are code-only — see the header block in the return.
  const participants = speakers.filter((sp) => sp.role === "participant");

  const isHidden = (q: string) => !!annotations[q]?.is_hidden;
  const backTo = (seg: TranscriptSegmentResponse) => `/report/sessions/${sessionId}#t-${Math.floor(seg.start_time)}`;
  // First-occurrence-per-run suppression: show a label / sentiment / tag once,
  // stay quiet until it changes, then show again when it returns.
  let lastShownLabel = "";
  let lastSentiment = "";
  // Tag names present on the previous annotated quote. A tag carried over from
  // it is suppressed (the run continues); a newly-appearing tag shows.
  let prevTagNames = new Set<string>();

  return (
    <>
      {/* Sticky header — session selector + journey chain (when available) */}
      <div
        className={`bn-transcript-journey-header${showTimeline ? " bn-transcript-journey-header--timeline" : ""}`}
        ref={headerRef}
        data-testid="transcript-journey-header"
      >
        {sessionList.length > 1 && !isEmbedded() ? (
          // Embedded keeps the LABEL but drops the disclosure — the native
          // session-switcher popover in the titlebar owns switching there
          // (design-sessions-popover-navigation.md §What ships). The label
          // stays because it is the only thing naming the session on the page.
          <Selector<SessionListItem>
            label={`Session ${sessionNum}`}
            items={sessionList}
            itemKey={(s) => s.session_id}
            renderItem={renderSessionItem}
            activeKey={sessionId}
            itemHref={(s) => `/report/sessions/${s.session_id}`}
            className="bn-session-selector"
            data-testid="session-selector"
          />
        ) : (
          <span className="bn-session-selector__label" data-testid="session-label">
            Session {sessionNum}
          </span>
        )}
        {participants.length > 0 && (
          <span
            className="bn-transcript-journey-header__people"
            data-testid="transcript-header-people"
          >
            {participants.map((sp) => (
              <SpeakerPickerTrigger
                key={sp.code}
                sessionId={sessionId}
                code={sp.code}
                role="participant"
                name={sp.name !== sp.code ? sp.name : undefined}
              />
            ))}
          </span>
        )}
        {hasJourney && (
          <JourneyChain
            labels={journeyLabels}
            activeIndex={activeIndex}
            onIndexClick={handleIndexClick}
            stickyOverflow
            data-testid="transcript-journey-chain"
          />
        )}
        {hasTimeline && <TimelineSplit />}
        {showTimeline && tapestry && (
          <TranscriptTimeline
            session={tapestry}
            lanes={timeline.lanes}
            bodyRef={bodyRef}
            headerRef={headerRef}
            nameOf={speakerNameOf}
            onJump={timelineJump}
            onScrub={timelineScrub}
          />
        )}
      </div>

      {/* Session roles — moderator/observer line (scrolls away naturally) */}
      {renderSessionRoles(speakers, t, sessionId)}

      {/* Transcript body, on its sheet: useGutterHover draws the hover keyline over it */}
      <div className="bn-transcript-sheet" ref={sheetRef}>
      <section
        className="transcript-body"
        ref={bodyRef}
        data-testid="transcript-body"
        // A drag across paragraphs copies the house transcript format —
        // Markdown, and rich text for Word — not the page's markup.
        onCopy={(e) => bodyRef.current && copyTranscriptSelection(e, bodyRef.current)}
        // One editable region, not one per paragraph: a selection can't leave
        // the editable element it starts in, so per-paragraph regions made a
        // drag across paragraphs impossible (owner, 7 Oct 2026). It takes a
        // caret so Return splits and Backspace at a paragraph's start joins
        // (design-transcript-editing.md §"Split and join, stage 1"); nothing
        // else edits — typing, cutting, pasting and dropping are refused, as
        // the words are the recording's. Timecodes, badges and the margin are
        // non-editable islands inside it.
        {...(paragraphEditing
          ? {
              contentEditable: true,
              suppressContentEditableWarning: true,
              spellCheck: false,
              onPaste: (e: React.ClipboardEvent) => e.preventDefault(),
              onDrop: (e: React.DragEvent) => e.preventDefault(),
              onCut: (e: React.ClipboardEvent) => e.preventDefault(),
              onKeyDown: onTranscriptKey,
            }
          : {})}
      >
        {segments.map((seg, position) => {
          const anchor = `t-${Math.floor(seg.start_time)}`;
          const classes = [
            "transcript-segment",
            seg.is_moderator ? "segment-moderator" : null,
            seg.is_quoted ? "segment-quoted" : null,
          ]
            .filter(Boolean)
            .join(" ");

          // Annotations: render only on first segment per quote, and
          // suppress repeated label+sentiment (show only when topic changes).
          const segAnnotations: {
            quoteId: string;
            ann: QuoteAnnotationResponse;
            showLabel: boolean;
            showSentiment: boolean;
            shownTags: QuoteAnnotationResponse["tags"];
          }[] = [];
          // The quotes this paragraph draws words of, in the order their words come; a quote
          // the server matched here by time but whose words are drawn elsewhere has no mark here.
          const quotesHere: string[] = [];
          for (const q of extents?.owners[position] ?? []) if (q && !quotesHere.includes(q)) quotesHere.push(q);
          for (const q of seg.quote_ids) if (!quotesHere.includes(q) && firstParagraphOf.get(q) === position) quotesHere.push(q);
          if (quotesHere.length > 0) {
            for (const qid of quotesHere) {
              if (firstParagraphOf.get(qid) === position) {
                const ann = annotations[qid];
                if (ann) {
                  const labelKey = `${ann.label_type}:${ann.label}`;
                  const showLabel = !!ann.label && labelKey !== lastShownLabel;
                  if (ann.label) lastShownLabel = labelKey;

                  // Sentiment badge: run-based (decoupled from label changes),
                  // and — matching QuoteCard — suppressed when a Sentiment-group
                  // tag already carries the same sentiment on this quote.
                  const hasSentimentTag = ann.tags.some(
                    (t) =>
                      t.codebook_group === "Sentiment" &&
                      t.name === ann.sentiment,
                  );
                  const showSentiment =
                    !!ann.sentiment &&
                    ann.sentiment !== lastSentiment &&
                    !hasSentimentTag &&
                    !ann.deleted_badges.includes(ann.sentiment);
                  if (ann.sentiment) lastSentiment = ann.sentiment;

                  // Tags: drop any carried over from the previous annotated
                  // quote; show only tags newly appearing in the run.
                  const shownTags = ann.tags.filter(
                    (t) => !prevTagNames.has(t.name.toLowerCase()),
                  );
                  prevTagNames = new Set(
                    ann.tags.map((t) => t.name.toLowerCase()),
                  );

                  segAnnotations.push({
                    quoteId: qid,
                    ann,
                    showLabel,
                    showSentiment,
                    shownTags,
                  });
                }
              }
            }
          }

          return (
            <div
              // Two halves of a split can share a whole second (or 0:00, untimed).
              key={`${anchor}-${position}`}
              className={classes}
              id={anchor}
              data-participant={seg.speaker_code}
              data-start-seconds={seg.start_time}
              data-end-seconds={seg.end_time}
              data-has-quote={extents?.owners[position]?.some(Boolean) ? "" : undefined}
              {...(seg.is_quoted && seg.quote_ids.length > 0
                ? { "data-quote-ids": seg.quote_ids.join(" ") }
                : {})}
              data-testid={`segment-${anchor}`}
            >
              <span className="segment-timecode-cell" contentEditable={false}>
              {data.has_media ? (
                <TimecodeLink
                  seconds={seg.start_time}
                  endSeconds={seg.end_time}
                  participantId={data.session_id}
                />
              ) : (
                <span className="timecode">
                  <span className="timecode-bracket">[</span>
                  {formatTimecode(seg.start_time)}
                  <span className="timecode-bracket">]</span>
                </span>
              )}
              </span>
              <span className="segment-speaker" data-participant={seg.speaker_code} contentEditable={false}>
                {/* The same picker as the header's (owner, 6 Oct 2026): naming
                    from a paragraph names the speaker everywhere. With the
                    Session | Paragraph switch (§K), it can also credit this
                    one paragraph to another speaker of the session. A click
                    target, not a Tab stop per paragraph. */}
                <SpeakerPickerTrigger
                  sessionId={sessionId}
                  code={seg.speaker_code}
                  role={seg.speaker_code.startsWith("o") ? "observer" : seg.is_moderator ? "moderator" : "participant"}
                  tabbable={false}
                  paragraph={isExportMode() ? undefined : {
                    position,
                    verify: verifyOf(drawnTokens(seg.text, seg.words), 0),
                  }}
                />
              </span>
              <div
                // Option C (owner, 6 Oct 2026): the first letter is drawn as a
                // capital where a sentence begins (CSS ::first-letter, which
                // follows `lang`, so Turkish gets İ). Display only; a word
                // spelled lower-case on purpose (iPhone) keeps its spelling.
                className={`segment-body${drawsCapital(segments, position, drawnTokens(seg.text, seg.words)[0] ?? "") ? " bn-sentence-start" : ""}`}
                // Unknown language: "" (no language), not the page's UI
                // language — a Turkish interface must not draw İ in an English
                // transcript.
                lang={data?.language ?? ""}
                // Where Return and Backspace find their paragraph.
                data-position={position}
              >
                {seg.inaudible ? (
                  // A gap, not words: drawn as an annotation outside the
                  // editable text, so it never reads as something said. No
                  // end time: the transcript file carries starts only, so an
                  // end here would be the next paragraph's start, an estimate.
                  // Copy writes it as "[inaudible]" (utils/transcriptCopy.ts).
                  <span className="segment-inaudible" contentEditable={false}>
                    {t("transcript.inaudible")}
                  </span>
                ) : seg.words && seg.words.length > 0 ? (
                  // Word-level spans, for the karaoke highlight during playback and, where a
                  // word belongs to a quote, for the gutter's lift and keyline (quoteExtents).
                  // The server's html_text is not drawn on either path.
                  seg.words.map((w, i) => {
                    // Which quote the word belongs to rides on data attributes, never the
                    // className: PlayerContext adds bn-word-active to it imperatively.
                    const q = extents?.owners[position]?.[i] ?? null;
                    return (
                      <span
                        key={i}
                        className="transcript-word"
                        data-start={w.start}
                        data-end={w.end}
                        data-q={q ?? undefined}
                        data-q-hidden={q && isHidden(q) ? "" : undefined}
                        data-q-approx={q && extents?.approximate.has(q) ? "" : undefined}
                      >
                        {w.text}{i < seg.words!.length - 1 ? " " : ""}
                      </span>
                    );
                  })
                ) : extents?.owners[position]?.some(Boolean) ? (
                  // Without word timings, a quoted paragraph's words are spans too, cut as
                  // drawnTokens cuts them, so its text is unchanged. A space between two words
                  // of one quote goes inside the quote's span, as on the timed path, so the
                  // pointer resting on it is still on the quote (no keyline flicker).
                  (() => {
                    const owners = extents.owners[position];
                    const parts = seg.text.split(/(\s+)/);
                    const out: React.ReactNode[] = [];
                    let k = -1;
                    for (let j = 0; j < parts.length; j++) {
                      const part = parts[j];
                      if (part === "" || /^\s+$/.test(part)) {
                        out.push(part);
                        continue;
                      }
                      k += 1;
                      const q = owners[k] ?? null;
                      const space = parts[j + 1];
                      const joins = q !== null && space !== undefined && /^\s+$/.test(space) && owners[k + 1] === q;
                      if (!q) {
                        out.push(part);
                        continue;
                      }
                      out.push(
                        <span
                          key={j}
                          data-q={q}
                          data-q-hidden={isHidden(q) ? "" : undefined}
                          data-q-approx={extents.approximate.has(q) ? "" : undefined}
                        >
                          {joins ? part + space : part}
                        </span>,
                      );
                      if (joins) j += 1;
                    }
                    return out;
                  })()
                ) : (
                  <>{seg.text}</>
                )}
              </div>

              {/* The gutter and the margin (docs/design-transcript-gutter.md): one entry per
                  quote this paragraph draws, its mark a link into the Quotes lens. Drawn twice —
                  beside the text, and under it for a narrow window — and only one is displayed. */}
              {(quotesHere.length > 0 || startsByParagraph.has(position) || askedByParagraph.has(position)) && (() => {
                const quoteEntries = quotesHere.map((qid) => {
                  const ann = annotations[qid];
                  const shown = segAnnotations.find((a) => a.quoteId === qid);
                  const anchor = ann?.anchor ?? "";
                  // An export cannot un-hide: a hidden quote's link leads to its group only.
                  const reveal = isExportMode() && isHidden(qid) ? undefined : qid;
                  const href = anchor ? quotesHref(anchor, reveal) : undefined;
                  const follow = (e: React.MouseEvent) => followInApp(e, quotesPath(anchor, reveal), backTo(seg));
                  const content = (withIds: boolean) => {
                    if (!shown) return null;
                    const tags = shown.shownTags;
                    return (
                      <>
                        {shown.showLabel && ann.label ? (
                          href ? (
                            <a className="bn-gutter-title" href={href} onClick={follow}>{ann.label}</a>
                          ) : (
                            <span className="bn-gutter-title">{ann.label}</span>
                          )
                        ) : null}
                        {shown.showSentiment || tags.length > 0 ? (
                          <div className="margin-tags">
                            {shown.showSentiment && (
                              <Badge
                                variant="ai"
                                text={ann.sentiment}
                                sentiment={ann.sentiment}
                                // An exported report has no server to save to.
                                onDelete={isExportMode() ? undefined : () => handleDeleteBadge(qid, ann.sentiment)}
                                data-testid={withIds ? `annotation-${qid}-sentiment` : undefined}
                              />
                            )}
                            {tags.map((tag) => (
                              <Badge
                                key={tag.name}
                                variant="user"
                                text={tag.name}
                                colour={tag.colour_set ? getTagBg(tag.colour_set, tag.colour_index) : undefined}
                                onDelete={isExportMode() ? undefined : () => handleDeleteTag(qid, tag.name)}
                                data-testid={withIds ? `annotation-${qid}-tag-${tag.name}` : undefined}
                              />
                            ))}
                          </div>
                        ) : null}
                      </>
                    );
                  };
                  return {
                    key: qid, icon: "quotes" as const, href, follow, content, hidden: isHidden(qid),
                    same: false, target: `q:${qid}`, testId: `annotation-${qid}`,
                    name: ann?.label ? `${t("nav.quotes")}: ${ann.label}` : t("nav.quotes"),
                  };
                });
                // The screens that began during this paragraph, after its quotes, so a thumbnail
                // hangs into the space below. A screen named as a section shown here says it once.
                const shownLabels = new Set(
                  segAnnotations.filter((a) => a.showLabel && a.ann.label).map((a) => norm(a.ann.label)),
                );
                const screenEntries = (startsByParagraph.get(position) ?? []).map(({ screen, tab }) => {
                  const title = screenTitle(screen, tab);
                  const path = screensPath(screen.key, sessionId);
                  const href = reportHref(path);
                  const follow = (e: React.MouseEvent) => followInApp(e, path, backTo(seg));
                  const same = shownLabels.has(norm(title));
                  return {
                    key: `s:${screen.key}`, icon: "screens" as const, href, follow, hidden: false, same,
                    target: `p:${position}:s`, testId: `screen-entry-${position}`,
                    name: `${t("nav.screens")}: ${title}`,
                    content: (_withIds: boolean) => (
                      <>
                        {same ? (
                          <span aria-hidden="true">{"\u00a0"}</span>
                        ) : (
                          <a className="bn-gutter-title is-screen" href={href} onClick={follow}>{title}</a>
                        )}
                        <GutterThumb tab={tab} href={href} onFollow={follow} />
                      </>
                    ),
                  };
                });
                // The questions the moderator asked in this paragraph, first: they are what the
                // paragraph is.
                const questionEntries = (askedByParagraph.get(position) ?? []).map((q) => {
                  const path = discussionPath(q.item, q.turn);
                  const href = reportHref(path);
                  const follow = (e: React.MouseEvent) => followInApp(e, path, backTo(seg));
                  return {
                    key: `d:${q.item}`, icon: "discussion" as const, href, follow, hidden: false, same: false,
                    target: `p:${position}:d`, testId: `question-entry-${position}`,
                    name: `${t("nav.discussion")}: ${q.topic}`,
                    // Grey, a link all the same (hover underline): more blue in the margin would be
                    // too much (owner, 17 Oct 2026).
                    content: (_withIds: boolean) => (
                      <a className="bn-gutter-topic" href={href} onClick={follow}>{q.topic}</a>
                    ),
                  };
                });
                const entries = [...questionEntries, ...quoteEntries, ...screenEntries];
                return (
                  <>
                    <div className="segment-side" contentEditable={false}>
                      {entries.map((e) => (
                        <GutterEntry
                          key={e.key}
                          icon={e.icon}
                          name={e.name}
                          href={e.href}
                          onFollow={e.follow}
                          hidden={e.hidden}
                          same={e.same}
                          target={e.target}
                          data-testid={e.testId}
                        >
                          {e.content(true)}
                        </GutterEntry>
                      ))}
                    </div>
                    <div className="segment-under" contentEditable={false}>
                      {entries.map((e) => (
                        <div key={e.key} className="bn-gutter-entry" data-hidden={e.hidden ? "" : undefined}>
                          {e.content(false)}
                        </div>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>
          );
        })}
      </section>
      </div>
    </>
  );
}
