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
import { PersonBadge, TimecodeLink } from "../components";
import { Annotation } from "../components/Annotation";
import type { AnnotationTag } from "../components/Annotation";
import { getTranscript, putDeletedBadges, putTags } from "../utils/api";
import { formatTimecode } from "../utils/format";
import type {
  TranscriptPageResponse,
  TranscriptSegmentResponse,
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
// Component
// ---------------------------------------------------------------------------

export function TranscriptPage({ projectId: _projectId, sessionId }: TranscriptPageProps) {
  void _projectId; // API base URL from window global already includes project ID
  const [data, setData] = useState<TranscriptPageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const bodyRef = useRef<HTMLElement | null>(null);

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

  // Track which quote IDs have been rendered (first segment per quote only)
  const seenQuoteIds = new Set<string>();
  // Track last-shown label+sentiment to suppress repetition — show only on change
  let lastShownLabel = "";
  let lastShownSentiment = "";

  return (
    <>
      {/* Back link */}
      <nav className="transcript-back" data-testid="transcript-back">
        <a href="/report/">
          &larr; {data.project_name} Research Report
        </a>
      </nav>

      {/* Heading with speaker badges */}
      <h1 data-testid="transcript-heading">
        Session {sessionNum}:{" "}
        {speakers.map((sp, i) => {
          const badgeRole = sp.code.startsWith("m")
            ? "moderator" as const
            : sp.code.startsWith("o")
              ? "observer" as const
              : "participant" as const;
          return (
            <span key={sp.code}>
              {i > 0 && ", "}
              <span className="heading-speaker" data-participant={sp.code}>
                <PersonBadge
                  code={sp.code}
                  role={badgeRole}
                  name={sp.name !== sp.code ? sp.name : undefined}
                />
              </span>
            </span>
          );
        })}
      </h1>

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
              <span
                className="segment-speaker bn-person-badge"
                data-participant={seg.speaker_code}
              >
                <span className="badge">{seg.speaker_code}</span>
              </span>
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
