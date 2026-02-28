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

import { useEffect, useState, useRef, useLayoutEffect, useCallback } from "react";
import { JourneyChain, PersonBadge, TimecodeLink } from "../components";
import { Annotation } from "../components/Annotation";
import type { AnnotationTag } from "../components/Annotation";
import { Selector } from "../components/Selector";
import {
  getTranscript,
  getSessionList,
  putDeletedBadges,
  putTags,
} from "../utils/api";
import type { SessionListItem } from "../utils/api";
import { formatFinderDate, formatTimecode } from "../utils/format";
import type {
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
// Span bar layout
// ---------------------------------------------------------------------------

/** Compute absolute-positioned span bars for quoted segment ranges. */
function useSpanBars(
  containerRef: React.RefObject<HTMLElement | null>,
  segments: TranscriptSegmentResponse[],
  annotations: Record<string, QuoteAnnotationResponse>,
) {
  const [bars, setBars] = useState<
    { top: number; height: number; left: number; quoteId: string; label: string }[]
  >([]);

  useLayoutEffect(() => {
    if (!containerRef.current || segments.length === 0) return;

    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();

    // Read layout tokens from CSS custom properties
    const rootStyle = getComputedStyle(document.documentElement);
    const barGap = parseFloat(rootStyle.getPropertyValue("--bn-span-bar-gap")) || 6;
    const barInset =
      parseFloat(rootStyle.getPropertyValue("--bn-span-bar-offset")) || 8;

    // Find margin column left edge for bar placement
    const firstMargin = container.querySelector<HTMLElement>(".segment-margin");
    let marginLeft: number;
    if (firstMargin) {
      marginLeft = firstMargin.getBoundingClientRect().left - containerRect.left;
    } else {
      marginLeft =
        containerRect.width -
        parseFloat(getComputedStyle(container).paddingRight);
    }

    // Group segments by quote ID to find contiguous ranges
    const quoteSegments = new Map<string, HTMLElement[]>();
    for (const seg of segments) {
      if (!seg.is_quoted) continue;
      for (const qid of seg.quote_ids) {
        const anchor = `t-${Math.floor(seg.start_time)}`;
        const el = container.querySelector<HTMLElement>(`#${anchor}`);
        if (el) {
          if (!quoteSegments.has(qid)) quoteSegments.set(qid, []);
          quoteSegments.get(qid)!.push(el);
        }
      }
    }

    // Build spans with vertical extents
    const spans: { qid: string; top: number; bottom: number; slot: number }[] = [];
    for (const [qid, els] of quoteSegments) {
      if (els.length === 0) continue;
      const firstRect = els[0].getBoundingClientRect();
      const lastRect = els[els.length - 1].getBoundingClientRect();
      const top = firstRect.top - containerRect.top;
      const bottom = lastRect.bottom - containerRect.top;
      spans.push({ qid, top, bottom, slot: 0 });
    }

    // Sort by top position for consistent slot assignment
    spans.sort((a, b) => a.top - b.top);

    // Greedy slot layout — each bar gets the leftmost slot that doesn't
    // overlap vertically with another bar already in that slot.
    const slots: { top: number; bottom: number }[][] = [];
    for (const span of spans) {
      let assigned = false;
      for (let s = 0; s < slots.length; s++) {
        const overlaps = slots[s].some(
          (r) => span.top < r.bottom && span.bottom > r.top,
        );
        if (!overlaps) {
          slots[s].push({ top: span.top, bottom: span.bottom });
          span.slot = s;
          assigned = true;
          break;
        }
      }
      if (!assigned) {
        span.slot = slots.length;
        slots.push([{ top: span.top, bottom: span.bottom }]);
      }
    }

    // Build final bars with horizontal position
    const newBars: typeof bars = [];
    for (const span of spans) {
      const height = Math.max(span.bottom - span.top, 8);
      const left = marginLeft - barInset - span.slot * barGap;
      const ann = annotations[span.qid];
      const label = ann?.label ?? "";
      newBars.push({ top: span.top, height, left, quoteId: span.qid, label });
    }

    setBars(newBars);
  }, [containerRef, segments, annotations]);

  return bars;
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

function useJourneyScrollSync(
  segments: TranscriptSegmentResponse[],
  annotations: Record<string, QuoteAnnotationResponse>,
  headerRef: React.RefObject<HTMLElement | null>,
) {
  // Build waypoints once from data (full sequence including revisits)
  const waypointsRef = useRef<JourneyWaypoint[] | null>(null);
  if (!waypointsRef.current && segments.length > 0) {
    waypointsRef.current = buildWaypoints(segments, annotations);
  }
  const waypoints = waypointsRef.current ?? [];

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

    function onScroll() {
      if (!isUserScrolling.current) return;
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
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
      });
    }

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

  return { activeIndex, handleIndexClick, journeyLabels };
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
        <span className="bn-selector__detail">{formatFinderDate(s.session_date)}</span>
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
function oxfordJoin(people: TranscriptSpeakerResponse[]): React.ReactNode[] {
  return people.map((sp, i) => {
    const badgeRole = sp.code.startsWith("m")
      ? "moderator" as const
      : "observer" as const;
    const person = (
      <span key={sp.code} className="bn-transcript-roles__person">
        <PersonBadge
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
): React.ReactNode | null {
  const moderators = speakers.filter((s) => s.role === "researcher");
  const observers = speakers.filter((s) => s.role === "observer");
  if (moderators.length === 0 && observers.length === 0) return null;

  return (
    <div className="bn-transcript-roles" data-testid="transcript-roles">
      {moderators.length > 0 && (
        <span>
          {moderators.length === 1 ? "Moderator " : "Moderators "}
          {oxfordJoin(moderators)}
        </span>
      )}
      {moderators.length > 0 && observers.length > 0 && ", "}
      {observers.length > 0 && (
        <span>
          {moderators.length > 0
            ? (observers.length === 1 ? "observer " : "observers ")
            : (observers.length === 1 ? "Observer " : "Observers ")}
          {oxfordJoin(observers)}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TranscriptPage({ projectId: _projectId, sessionId }: TranscriptPageProps) {
  void _projectId; // API base URL from window global already includes project ID
  const [data, setData] = useState<TranscriptPageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionList, setSessionList] = useState<SessionListItem[]>([]);
  const bodyRef = useRef<HTMLElement | null>(null);
  const headerRef = useRef<HTMLDivElement | null>(null);

  // Fetch transcript data
  useEffect(() => {
    setLoading(true);
    getTranscript(sessionId)
      .then((resp) => {
        setData(resp);
        setError(null);
      })
      .catch((err) => {
        setError(err.message || "Failed to load transcript");
      })
      .finally(() => setLoading(false));
  }, [sessionId]);

  // Fetch session list for dropdown
  useEffect(() => {
    getSessionList()
      .then(setSessionList)
      .catch(() => {}); // Non-critical — dropdown just won't show
  }, []);

  // Anchor highlight after render
  useEffect(() => {
    if (!data || loading) return;
    const hash = window.location.hash;
    if (!hash) return;
    const targetId = hash.slice(1); // strip #
    // Defer to next frame so DOM is ready
    requestAnimationFrame(() => {
      const el = document.getElementById(targetId);
      if (el) {
        el.classList.add("anchor-highlight");
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }, [data, loading]);

  // Span bars
  const bars = useSpanBars(bodyRef, data?.segments ?? [], data?.annotations ?? {});

  // Journey scroll sync (derives full label sequence from waypoints)
  const { activeIndex, handleIndexClick, journeyLabels } = useJourneyScrollSync(
    data?.segments ?? [],
    data?.annotations ?? {},
    headerRef,
  );

  // Measure sticky header height for scroll-margin-top
  useLayoutEffect(() => {
    if (headerRef.current) {
      const height = headerRef.current.offsetHeight;
      document.documentElement.style.setProperty(
        "--bn-journey-header-height",
        `${height}px`,
      );
    }
  }, [journeyLabels]);

  // Deleted badge / tag callbacks
  const handleDeleteBadge = useCallback(
    (quoteId: string, sentiment: string) => {
      if (!data) return;
      const ann = data.annotations[quoteId];
      if (!ann) return;
      const updated = [...ann.deleted_badges, sentiment];
      setData({
        ...data,
        annotations: {
          ...data.annotations,
          [quoteId]: { ...ann, deleted_badges: updated },
        },
      });
      putDeletedBadges({ [quoteId]: updated });
    },
    [data],
  );

  const handleDeleteTag = useCallback(
    (quoteId: string, tagName: string) => {
      if (!data) return;
      const ann = data.annotations[quoteId];
      if (!ann) return;
      const updated = ann.tags.filter((t) => t.name !== tagName);
      setData({
        ...data,
        annotations: {
          ...data.annotations,
          [quoteId]: { ...ann, tags: updated },
        },
      });
      putTags({ [quoteId]: updated.map((t) => t.name) });
    },
    [data],
  );

  // Loading state
  if (loading) {
    return (
      <div className="bn-loading" data-testid="transcript-loading">
        Loading transcript&hellip;
      </div>
    );
  }

  // Error state
  if (error || !data) {
    return (
      <div className="bn-error" data-testid="transcript-error">
        {error || "No transcript data available."}
      </div>
    );
  }

  const { segments, speakers, annotations } = data;
  const sessionNum = sessionId.length > 1 && "sp".includes(sessionId[0]) && /^\d+$/.test(sessionId.slice(1))
    ? sessionId.slice(1)
    : sessionId;

  const hasJourney = journeyLabels.length > 0;
  const speakerMap = new Map(speakers.map((sp) => [sp.code, sp]));

  // Track which quote IDs have been rendered (first segment per quote only)
  const seenQuoteIds = new Set<string>();
  // Track which speakers have been introduced (first occurrence gets full name badge)
  const introducedSpeakers = new Set<string>();
  // Track last-shown label+sentiment to suppress repetition — show only on change
  let lastShownLabel = "";
  let lastShownSentiment = "";

  return (
    <>
      {/* Sticky header — session selector + journey chain (when available) */}
      <div
        className="bn-transcript-journey-header"
        ref={headerRef}
        data-testid="transcript-journey-header"
      >
        {sessionList.length > 1 ? (
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
        {hasJourney && (
          <JourneyChain
            labels={journeyLabels}
            activeIndex={activeIndex}
            onIndexClick={handleIndexClick}
            stickyOverflow
            data-testid="transcript-journey-chain"
          />
        )}
      </div>

      {/* Session roles — moderator/observer line (scrolls away naturally) */}
      {renderSessionRoles(speakers)}

      {/* Transcript body */}
      <section
        className="transcript-body"
        ref={bodyRef}
        data-testid="transcript-body"
      >
        {segments.map((seg) => {
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
          }[] = [];
          if (seg.is_quoted) {
            for (const qid of seg.quote_ids) {
              if (!seenQuoteIds.has(qid)) {
                seenQuoteIds.add(qid);
                const ann = annotations[qid];
                if (ann) {
                  const labelKey = `${ann.label_type}:${ann.label}`;
                  const showLabel = labelKey !== lastShownLabel;
                  const showSentiment =
                    showLabel || ann.sentiment !== lastShownSentiment;
                  if (ann.label) lastShownLabel = labelKey;
                  if (ann.sentiment) lastShownSentiment = ann.sentiment;
                  segAnnotations.push({
                    quoteId: qid,
                    ann,
                    showLabel,
                    showSentiment,
                  });
                }
              }
            }
          }

          return (
            <div
              key={anchor}
              className={classes}
              id={anchor}
              data-participant={seg.speaker_code}
              data-start-seconds={seg.start_time}
              data-end-seconds={seg.end_time}
              {...(seg.is_quoted && seg.quote_ids.length > 0
                ? { "data-quote-ids": seg.quote_ids.join(" ") }
                : {})}
              data-testid={`segment-${anchor}`}
            >
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
              {(() => {
                const isFirst = !introducedSpeakers.has(seg.speaker_code);
                if (isFirst) introducedSpeakers.add(seg.speaker_code);
                const sp = speakerMap.get(seg.speaker_code);
                const showName = isFirst && sp != null && sp.name !== sp.code;
                return (
                  <span className="segment-speaker" data-participant={seg.speaker_code}>
                    <PersonBadge
                      code={seg.speaker_code}
                      role={seg.is_moderator ? "moderator" : "participant"}
                      name={showName ? sp!.name : undefined}
                    />
                  </span>
                );
              })()}
              <div className="segment-body">
                {seg.html_text ? (
                  <span dangerouslySetInnerHTML={{ __html: seg.html_text }} />
                ) : (
                  <>{seg.text}</>
                )}
              </div>

              {/* Margin annotations */}
              {segAnnotations.length > 0 && (
                <div className="segment-margin">
                  {segAnnotations.map(({ quoteId, ann, showLabel, showSentiment }) => {
                    const sentimentBadge =
                      showSentiment &&
                      ann.sentiment &&
                      !ann.deleted_badges.includes(ann.sentiment)
                        ? {
                            text: ann.sentiment,
                            sentiment: ann.sentiment,
                            onDelete: () =>
                              handleDeleteBadge(quoteId, ann.sentiment),
                          }
                        : undefined;

                    const tags: AnnotationTag[] = ann.tags.map((t) => ({
                      name: t.name,
                    }));

                    return (
                      <Annotation
                        key={quoteId}
                        quoteId={quoteId}
                        label={showLabel ? (ann.label || undefined) : undefined}
                        sentiment={sentimentBadge}
                        tags={tags.length > 0 ? tags : undefined}
                        onTagDelete={(name) => handleDeleteTag(quoteId, name)}
                        data-testid={`annotation-${quoteId}`}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {/* Span bars */}
        {bars.map((bar) => (
          <div
            key={bar.quoteId}
            className="span-bar"
            style={{
              position: "absolute",
              top: `${bar.top}px`,
              height: `${bar.height}px`,
              left: `${bar.left}px`,
            }}
            data-testid={`span-bar-${bar.quoteId}`}
          />
        ))}
      </section>
    </>
  );
}
