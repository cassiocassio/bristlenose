/**
 * AnalysisPage — React island for the Analysis tab.
 *
 * Shows signal concentration cards and heatmaps for both:
 * - **Sentiment signals** (baked into HTML as `window.BRISTLENOSE_ANALYSIS`)
 * - **Tag signals** (fetched per-codebook from `/api/projects/{id}/analysis/codebooks`)
 *
 * Both views render simultaneously — sentiment cards first (typically stronger
 * signals), then tag cards, then heatmaps for each.
 *
 * Reuses existing CSS from analysis.css — emits the same class names as
 * the vanilla JS analysis.js so all styling carries over.
 */

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Badge, Metric, PersonBadge } from "../components";
import { useTranscriptCache } from "../hooks/useTranscriptCache";
import { getCodebookAnalysis } from "../utils/api";
import { getGroupBg, getTagBg } from "../utils/colours";
import { formatTimecode } from "../utils/format";
import { detectSequences, type SequenceMeta } from "../utils/sequences";
import type {
  AnalysisMatrix,
  CodebookAnalysisListResponse,
  SentimentAnalysisData,
  SentimentSignal,
  SourceBreakdown,
  TagSignalQuote,
  TranscriptSegmentResponse,
} from "../utils/types";

// ── Vanilla JS interop ─────────────────────────────────────────────────

declare global {
  interface Window {
    BRISTLENOSE_ANALYSIS?: SentimentAnalysisData;
    switchToTab?: (tab: string, pushHash?: boolean) => void;
    scrollToAnchor?: (anchorId: string, opts?: { block?: string; highlight?: boolean }) => void;
  }
}

// ── Constants ─────────────────────────────────────────────────────────

/** Maximum signal cards shown per type (sentiment / tags). */
const MAX_SIGNALS = 6;

// ── Quote context expansion ───────────────────────────────────────────

/** How many segments a user has expanded above/below a quote. */
interface QuoteExpansion {
  above: number;
  below: number;
}

type ExpansionAction =
  | { type: "expand_above"; quoteKey: string }
  | { type: "expand_below"; quoteKey: string };

function expansionReducer(
  state: Map<string, QuoteExpansion>,
  action: ExpansionAction,
): Map<string, QuoteExpansion> {
  const next = new Map(state);
  const prev = next.get(action.quoteKey) ?? { above: 0, below: 0 };
  if (action.type === "expand_above") {
    next.set(action.quoteKey, { ...prev, above: prev.above + 1 });
  } else {
    next.set(action.quoteKey, { ...prev, below: prev.below + 1 });
  }
  return next;
}

/** Stable key for a quote within the expansion state. */
function quoteKey(q: { sessionId: string; pid: string; startSeconds: number }): string {
  return `${q.sessionId}-${q.pid}-${q.startSeconds}`;
}

// ── Types ──────────────────────────────────────────────────────────────

/** Unified signal shape for rendering — adapts both sentiment and tag signals. */
interface UnifiedSignal {
  key: string;
  location: string;
  sourceType: "section" | "theme";
  columnLabel: string; // sentiment name or group name
  colourSet: string; // codebook group colour_set (empty for sentiment)
  codebookName: string; // display name of the codebook
  count: number;
  participants: string[];
  nEff: number;
  meanIntensity: number;
  concentration: number;
  compositeSignal: number;
  confidence: "strong" | "moderate" | "emerging";
  quotes: UnifiedQuote[];
}

interface UnifiedQuote {
  text: string;
  pid: string;
  sessionId: string;
  startSeconds: number;
  intensity: number;
  tagNames: string[];
  colourSet: string;
  tagColourIndices: Record<string, number>;
  segmentIndex: number;
}

function adaptSentimentSignals(data: SentimentAnalysisData): UnifiedSignal[] {
  return data.signals.map((s: SentimentSignal) => ({
    key: `${s.sourceType}|${s.location}|${s.sentiment}`,
    location: s.location,
    sourceType: s.sourceType,
    columnLabel: s.sentiment,
    colourSet: "",
    codebookName: "",
    count: s.count,
    participants: s.participants,
    nEff: s.nEff,
    meanIntensity: s.meanIntensity,
    concentration: s.concentration,
    compositeSignal: s.compositeSignal,
    confidence: s.confidence,
    quotes: s.quotes.map((q) => ({
      text: q.text,
      pid: q.pid,
      sessionId: q.sessionId,
      startSeconds: q.startSeconds,
      intensity: q.intensity,
      tagNames: [],
      colourSet: "",
      tagColourIndices: {},
      segmentIndex: q.segmentIndex ?? -1,
    })),
  }));
}

function adaptCodebookSignals(data: CodebookAnalysisListResponse): UnifiedSignal[] {
  const all: UnifiedSignal[] = [];
  for (const cb of data.codebooks) {
    for (const s of cb.signals) {
      all.push({
        key: `${s.source_type}|${s.location}|${s.group_name}`,
        location: s.location,
        sourceType: s.source_type,
        columnLabel: s.group_name,
        colourSet: s.colour_set || cb.colour_set,
        codebookName: cb.codebook_name,
        count: s.count,
        participants: s.participants,
        nEff: s.n_eff,
        meanIntensity: s.mean_intensity,
        concentration: s.concentration,
        compositeSignal: s.composite_signal,
        confidence: s.confidence,
        quotes: s.quotes.map((q: TagSignalQuote) => ({
          text: q.text,
          pid: q.participant_id,
          sessionId: q.session_id,
          startSeconds: q.start_seconds,
          intensity: q.intensity,
          tagNames: q.tag_names || [],
          colourSet: s.colour_set || cb.colour_set,
          tagColourIndices: cb.tag_colour_indices || {},
          segmentIndex: q.segment_index ?? -1,
        })),
      });
    }
  }
  return all.sort((a, b) => b.compositeSignal - a.compositeSignal);
}

// ── Heatmap maths ──────────────────────────────────────────────────────

function adjustedResidual(
  observed: number,
  rowTotal: number,
  colTotal: number,
  grandTotal: number,
): number {
  if (grandTotal === 0 || rowTotal === 0 || colTotal === 0) return 0;
  const expected = (rowTotal * colTotal) / grandTotal;
  if (expected === 0) return 0;
  const denom = Math.sqrt(
    expected * (1 - rowTotal / grandTotal) * (1 - colTotal / grandTotal),
  );
  return denom === 0 ? 0 : (observed - expected) / denom;
}

function heatCellStyle(
  count: number,
  rowTotal: number,
  colTotal: number,
  grandTotal: number,
  isDark: boolean,
): React.CSSProperties {
  if (count === 0) return {};
  const r = adjustedResidual(count, rowTotal, colTotal, grandTotal);
  const absR = Math.abs(r);
  const maxR = 4;
  let heat = Math.min(1, absR / maxR);
  if (heat < 0.05) return {};

  // Fade single-occurrence cells to ~30% heat — background noise, not clickable
  if (count === 1) heat *= 0.3;

  const hue = r > 0 ? 150 : 20;
  const chroma = 0.12 * heat;
  const lMin = isDark ? 0.25 : 0.55;
  const lMax = isDark ? 0.55 : 0.95;
  const lightness = lMax - (lMax - lMin) * heat;

  return { background: `oklch(${lightness} ${chroma} ${hue})` };
}

// ── Cell tooltip (context-only micro variant 5b) ──────────────────────

/** Tooltip position relative to the hovered cell. */
interface TooltipPos {
  top: number;
  left: number;
}

function CellTooltip({
  signal,
  allPids,
  pos,
}: {
  signal: UnifiedSignal;
  allPids: string[];
  pos: TooltipPos;
}) {
  const accentVar = signal.colourSet
    ? getGroupBg(signal.colourSet)
    : `var(--bn-sentiment-${signal.columnLabel})`;
  const presentSet = new Set(signal.participants);
  const quotes = signal.quotes.slice(0, 2);
  const remaining = signal.quotes.length - quotes.length;

  return (
    <div
      className="cell-tooltip"
      style={{
        "--tip-accent": accentVar,
        top: pos.top,
        left: pos.left,
      } as React.CSSProperties}
      data-testid="bn-cell-tooltip"
    >
      <div className="cell-tooltip-body">
        <div className="cell-tooltip-metrics">
          <span>
            <span className="cell-tooltip-val">{signal.concentration.toFixed(1)}&times;</span> conc
          </span>
          <span>
            <span className="cell-tooltip-val">{signal.participants.length}</span>
            {signal.participants.length === 1 ? " voice" : " voices"}
          </span>
          <span className="cell-tooltip-pips">
            {allPids.map((pid) => (
              <span
                key={pid}
                className={`cell-tooltip-pip${presentSet.has(pid) ? "" : " absent"}`}
              />
            ))}
          </span>
        </div>
        <div className="cell-tooltip-quotes">
          {quotes.map((q, i) => (
            <div key={i} className="cell-tooltip-quote">
              <span className="cell-tooltip-quote-text">{q.text}</span>
              <span className="cell-tooltip-speaker">{q.pid}</span>
            </div>
          ))}
        </div>
        {remaining > 0 && (
          <div className="cell-tooltip-footer">+{remaining} more</div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function SourceBanner({ breakdown }: { breakdown: SourceBreakdown }) {
  if (breakdown.total === 0) return null;
  const parts: string[] = [];
  if (breakdown.accepted > 0) parts.push(`${breakdown.accepted} accepted`);
  if (breakdown.pending > 0) parts.push(`${breakdown.pending} pending`);
  return (
    <p
      className="description"
      style={{ fontSize: "0.82rem", marginBottom: "var(--bn-space-md)" }}
      data-testid="bn-source-banner"
    >
      Based on {parts.join(" + ")} tag{breakdown.total === 1 ? "" : "s"}
      {breakdown.pending > 0 && " (pending tags weighted by AI confidence)"}
    </p>
  );
}

function ParticipantGrid({
  allPids,
  presentPids,
  accentVar,
}: {
  allPids: string[];
  presentPids: string[];
  accentVar?: string;
}) {
  const presentSet = useMemo(() => new Set(presentPids), [presentPids]);
  return (
    <span className="participant-grid">
      <span className="participant-count">
        {presentPids.length}/{allPids.length}
      </span>
      {allPids.map((pid) => (
        <span
          key={pid}
          className={`p-box${presentSet.has(pid) ? " p-present" : ""}`}
          style={accentVar ? ({ "--card-accent": accentVar } as React.CSSProperties) : undefined}
        >
          {pid}
        </span>
      ))}
    </span>
  );
}

function SignalCard({
  signal,
  allPids,
  isSentiment,
  cardRef,
  transcriptCache,
}: {
  signal: UnifiedSignal;
  allPids: string[];
  isSentiment: boolean;
  cardRef?: (el: HTMLDivElement | null) => void;
  transcriptCache: ReturnType<typeof useTranscriptCache>;
}) {
  const [expanded, setExpanded] = useState(false);
  const expansionRef = useRef<HTMLDivElement>(null);

  // Context expansion state
  const [expansionState, dispatchExpansion] = useReducer(
    expansionReducer,
    new Map<string, QuoteExpansion>(),
  );
  // Resolved context segments (keyed by quoteKey, then "above"/"below")
  const [contextSegments, setContextSegments] = useState<
    Map<string, { above: TranscriptSegmentResponse[]; below: TranscriptSegmentResponse[] }>
  >(new Map());

  const accentVar = isSentiment
    ? `var(--bn-sentiment-${signal.columnLabel})`
    : signal.colourSet
      ? getGroupBg(signal.colourSet)
      : "var(--bn-colour-accent)";

  const anchorPrefix = signal.sourceType === "section" ? "section-" : "theme-";
  const slug = signal.location.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
  const locationHref = `#${anchorPrefix}${slug}`;

  const handleLocationClick = (e: React.MouseEvent) => {
    e.preventDefault();
    window.switchToTab?.("quotes");
    window.scrollToAnchor?.(`${anchorPrefix}${slug}`);
  };

  const concPct = Math.min(100, Math.max(0, (signal.concentration / 5) * 100));
  const agreePct = signal.nEff > 0 && allPids.length > 0
    ? Math.min(100, (signal.nEff / allPids.length) * 100)
    : 0;

  const sequenceMetas = useMemo(
    () => detectSequences(signal.quotes),
    [signal.quotes],
  );

  // Determine which quotes get expand arrows (only sequence edges + solo quotes)
  const quoteExpandability = useMemo(() => {
    return signal.quotes.map((q, i) => {
      const meta = sequenceMetas[i];
      const pos = meta?.position ?? "solo";
      // Can expand above: only if first-in-sequence or solo, and has timecodes
      const canAbove = (pos === "solo" || pos === "first") && q.startSeconds > 0;
      // Can expand below: only if last-in-sequence or solo, and has timecodes
      const canBelow = (pos === "solo" || pos === "last") && q.startSeconds > 0;
      return { canAbove, canBelow };
    });
  }, [signal.quotes, sequenceMetas]);

  // Fetch context segments when expansion state changes
  useEffect(() => {
    let cancelled = false;
    const promises: Promise<void>[] = [];

    for (const [qk, exp] of expansionState) {
      const q = signal.quotes.find((qq) => quoteKey(qq) === qk);
      if (!q) continue;

      if (q.segmentIndex >= 0) {
        // Segment-index path: precise lookup by ordinal
        const qIdx = signal.quotes.indexOf(q);
        const meta = sequenceMetas[qIdx];
        const pos = meta?.position ?? "solo";

        let earliestIdx = q.segmentIndex;
        let latestIdx = q.segmentIndex;
        if (pos === "first" || pos === "middle") {
          for (let i = qIdx + 1; i < signal.quotes.length; i++) {
            const m = sequenceMetas[i];
            if (m?.position === "middle" || m?.position === "last") {
              latestIdx = Math.max(latestIdx, signal.quotes[i].segmentIndex);
              if (m.position === "last") break;
            } else break;
          }
        }
        if (pos === "last" || pos === "middle") {
          for (let i = qIdx - 1; i >= 0; i--) {
            const m = sequenceMetas[i];
            if (m?.position === "middle" || m?.position === "first") {
              earliestIdx = Math.min(earliestIdx, signal.quotes[i].segmentIndex);
              if (m.position === "first") break;
            } else break;
          }
        }

        if (exp.above > 0) {
          promises.push(
            transcriptCache.getSegmentRange(q.sessionId, earliestIdx - exp.above, earliestIdx - 1).then((segs) => {
              if (cancelled) return;
              setContextSegments((prev) => {
                const next = new Map(prev);
                const existing = next.get(qk) ?? { above: [], below: [] };
                next.set(qk, { ...existing, above: segs });
                return next;
              });
            }),
          );
        }
        if (exp.below > 0) {
          promises.push(
            transcriptCache.getSegmentRange(q.sessionId, latestIdx + 1, latestIdx + exp.below).then((segs) => {
              if (cancelled) return;
              setContextSegments((prev) => {
                const next = new Map(prev);
                const existing = next.get(qk) ?? { above: [], below: [] };
                next.set(qk, { ...existing, below: segs });
                return next;
              });
            }),
          );
        }
      } else {
        // Timecode fallback: find segment by startSeconds, return neighbours
        promises.push(
          transcriptCache.getContextByTimecode(q.sessionId, q.startSeconds, exp.above, exp.below).then((ctx) => {
            if (cancelled) return;
            setContextSegments((prev) => {
              const next = new Map(prev);
              next.set(qk, ctx);
              return next;
            });
          }),
        );
      }
    }

    return () => { cancelled = true; };
  }, [expansionState, signal.quotes, sequenceMetas, transcriptCache]);

  const visibleQuotes = signal.quotes.slice(0, 1);
  const hiddenQuotes = signal.quotes.slice(1);

  // Fix: useEffect ensures expanded class is applied before maxHeight is set,
  // so both opacity and maxHeight transitions work together.
  useEffect(() => {
    if (!expansionRef.current) return;
    if (expanded) {
      expansionRef.current.style.maxHeight = `${expansionRef.current.scrollHeight}px`;
    } else {
      expansionRef.current.style.maxHeight = "0";
    }
  }, [expanded, contextSegments]);

  const toggleExpand = useCallback(() => setExpanded((prev) => !prev), []);

  const renderQuoteBlock = (q: UnifiedQuote, i: number) => {
    const qk = quoteKey(q);
    const exp = quoteExpandability[i];
    const ctx = contextSegments.get(qk);
    const expState = expansionState.get(qk);
    // Disable arrow if no more segments returned than requested
    const aboveExhausted = expState && ctx ? ctx.above.length < expState.above : false;
    const belowExhausted = expState && ctx ? ctx.below.length < expState.below : false;
    return (
      <QuoteBlock
        key={i}
        quote={q}
        isSentiment={isSentiment}
        sequenceMeta={sequenceMetas[i]}
        contextAbove={ctx?.above}
        contextBelow={ctx?.below}
        canExpandAbove={exp.canAbove && !aboveExhausted}
        canExpandBelow={exp.canBelow && !belowExhausted}
        onExpandAbove={() => dispatchExpansion({ type: "expand_above", quoteKey: qk })}
        onExpandBelow={() => dispatchExpansion({ type: "expand_below", quoteKey: qk })}
      />
    );
  };

  return (
    <div
      className={`signal-card${expanded ? " expanded" : ""}`}
      style={{ "--card-accent": accentVar } as React.CSSProperties}
      data-testid="bn-signal-card"
      ref={cardRef ?? undefined}
    >
      <div className="signal-card-top">
        <div className="signal-card-identity">
          <span className="signal-card-source">
            {signal.sourceType === "section" ? "Section" : "Theme"}
          </span>
          <div className="signal-card-location">
            <a
              href={locationHref}
              className="signal-card-location-link"
              onClick={handleLocationClick}
            >
              {signal.location}
            </a>
          </div>
          {isSentiment ? (
            <Badge text={signal.columnLabel} variant="ai" sentiment={signal.columnLabel} />
          ) : (
            <Badge
              text={signal.columnLabel}
              variant="readonly"
              colour={signal.colourSet ? getGroupBg(signal.colourSet) : undefined}
              className="signal-group-badge"
            />
          )}
        </div>
        <div className="signal-card-metrics">
          <Metric
            label="Signal"
            title="Composite signal strength"
            displayValue={signal.compositeSignal.toFixed(4)}
            viz={{ type: "none" }}
          />
          <Metric
            label="Conc."
            title="Concentration ratio — how overrepresented vs study average"
            displayValue={`${signal.concentration.toFixed(1)}×`}
            viz={{ type: "bar", percentage: concPct }}
          />
          <Metric
            label="Agree."
            title="Agreement — effective number of voices (Simpson's diversity)"
            displayValue={signal.nEff.toFixed(1)}
            viz={{ type: "bar", percentage: agreePct }}
          />
          <Metric
            label="Intensity"
            title="Mean emotional intensity (0–3)"
            displayValue={signal.meanIntensity.toFixed(1)}
            viz={{ type: "dots", value: signal.meanIntensity }}
          />
        </div>
      </div>

      <div className="signal-card-quotes">
        {visibleQuotes.map((q, i) => renderQuoteBlock(q, i))}
        <div
          className="signal-card-expansion"
          ref={expansionRef}
          style={{ maxHeight: expanded ? undefined : 0 }}
        >
          {hiddenQuotes.map((q, i) => renderQuoteBlock(q, i + visibleQuotes.length))}
        </div>
      </div>

      <div className="signal-card-footer">
        {hiddenQuotes.length > 0 ? (
          <a
            className="signal-card-link signal-card-toggle"
            onClick={toggleExpand}
            data-testid="bn-signal-toggle"
          >
            {expanded ? "Hide" : `Show all ${signal.quotes.length} quotes \u2192`}
          </a>
        ) : (
          <span className="signal-card-link" style={{ visibility: "hidden" }}>
            1 quote
          </span>
        )}
        <ParticipantGrid
          allPids={allPids}
          presentPids={signal.participants}
          accentVar={accentVar}
        />
      </div>
    </div>
  );
}

function ContextSegment({ segment }: { segment: TranscriptSegmentResponse }) {
  const tc = formatTimecode(segment.start_time);
  const role = segment.is_moderator ? "moderator" as const : "participant" as const;
  return (
    <div className="context-segment">
      <div className="quote-row">
        <span className="timecode" style={{ opacity: 0.5 }}>
          <span className="timecode-bracket">[</span>
          {tc}
          <span className="timecode-bracket">]</span>
        </span>
        <span className="quote-body">
          <span className="speaker">
            <PersonBadge code={segment.speaker_code} role={role} />
          </span>{" "}
          <span className="context-text">{segment.text}</span>
        </span>
      </div>
    </div>
  );
}

function QuoteBlock({
  quote,
  isSentiment,
  sequenceMeta,
  contextAbove,
  contextBelow,
  canExpandAbove,
  canExpandBelow,
  onExpandAbove,
  onExpandBelow,
}: {
  quote: UnifiedQuote;
  isSentiment: boolean;
  sequenceMeta?: SequenceMeta;
  contextAbove?: TranscriptSegmentResponse[];
  contextBelow?: TranscriptSegmentResponse[];
  canExpandAbove?: boolean;
  canExpandBelow?: boolean;
  onExpandAbove?: () => void;
  onExpandBelow?: () => void;
}) {
  const tc = formatTimecode(quote.startSeconds);
  const tcHref = `sessions/transcript_${quote.sessionId}.html#t-${Math.floor(quote.startSeconds)}`;

  const seqPos = sequenceMeta?.position ?? "solo";
  const isContinuation = seqPos === "middle" || seqPos === "last";
  const seqClass = seqPos !== "solo" ? ` seq-${seqPos}` : "";

  const showAboveArrow = canExpandAbove && onExpandAbove;
  const showBelowArrow = canExpandBelow && onExpandBelow;
  const hasArrows = showAboveArrow || showBelowArrow;

  const timecodeEl = hasArrows ? (
    <span className="timecode-expandable">
      {showAboveArrow && (
        <button
          className="expand-arrow expand-arrow--above"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onExpandAbove(); }}
          title="Show earlier context"
          aria-label="Show earlier transcript segment"
        >
          &#x25B4;
        </button>
      )}
      <a className="timecode" href={tcHref}>
        <span className="timecode-bracket">[</span>
        {tc}
        <span className="timecode-bracket">]</span>
      </a>
      {showBelowArrow && (
        <button
          className="expand-arrow expand-arrow--below"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onExpandBelow(); }}
          title="Show later context"
          aria-label="Show later transcript segment"
        >
          &#x25BE;
        </button>
      )}
    </span>
  ) : (
    <a className="timecode" href={tcHref}>
      <span className="timecode-bracket">[</span>
      {tc}
      <span className="timecode-bracket">]</span>
    </a>
  );

  return (
    <div>
      {contextAbove?.map((seg, i) => (
        <ContextSegment key={`above-${i}`} segment={seg} />
      ))}

      <blockquote className={seqClass ? seqClass.trimStart() : undefined}>
        <div className="quote-row">
          {timecodeEl}
          <span className="quote-body">
            {!isContinuation && (
              <><span className="speaker">
                <PersonBadge code={quote.pid} role="participant" />
              </span>{" "}</>
            )}
            <span className="quote-text">{quote.text}</span>
            {!isSentiment && quote.tagNames.length > 0 && quote.tagNames.map((tag) => (
              <Badge
                key={tag}
                text={tag}
                variant="readonly"
                colour={
                  quote.colourSet
                    ? getTagBg(quote.colourSet, quote.tagColourIndices[tag] ?? 0)
                    : undefined
                }
                className="signal-quote-tag"
              />
            ))}
          </span>
          <span className="intensity-dots" title={`Intensity ${quote.intensity}/3`}>
            <IntensityDotsSvg value={quote.intensity} />
          </span>
        </div>
      </blockquote>

      {contextBelow?.map((seg, i) => (
        <ContextSegment key={`below-${i}`} segment={seg} />
      ))}
    </div>
  );
}

function IntensityDotsSvg({ value }: { value: number }) {
  const r = 5;
  const cx0 = 7;
  const gap = 16;
  const w = cx0 + gap * 2 + r + 2;
  const h = r * 2 + 2;
  const colour = "var(--dot-colour, var(--bn-colour-muted))";

  const dots: React.ReactNode[] = [];
  for (let i = 0; i < 3; i++) {
    const threshold = i + 1;
    const x = cx0 + i * gap;
    const y = r + 1;
    if (value >= threshold) {
      dots.push(<circle key={i} cx={x} cy={y} r={r} fill={colour} opacity={0.7} />);
    } else {
      dots.push(
        <circle key={i} cx={x} cy={y} r={r} fill="none" stroke={colour} strokeWidth={1.2} opacity={0.35} />,
      );
    }
  }
  return (
    <svg className="intensity-dots-svg" width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      {dots}
    </svg>
  );
}

function Heatmap({
  matrix,
  columnLabels,
  rowHeader,
  isSentiment,
  signalKeys,
  signalMap,
  allPids,
  onCellClick,
  isDark,
}: {
  matrix: AnalysisMatrix | SentimentMatrixAdapter;
  columnLabels: string[];
  rowHeader: string;
  isSentiment: boolean;
  signalKeys: Set<string>;
  signalMap: Map<string, UnifiedSignal>;
  allPids: string[];
  onCellClick: (key: string) => void;
  isDark: boolean;
}) {
  const grandTotal = matrix.grand_total;
  if (grandTotal === 0 || matrix.row_labels.length === 0) return null;

  // Tooltip hover state
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState<TooltipPos>({ top: 0, left: 0 });
  const enterTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const leaveTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Track which row/col is highlighted for header tinting
  const [highlightRow, setHighlightRow] = useState<string | null>(null);
  const [highlightCol, setHighlightCol] = useState<string | null>(null);

  const handleCellEnter = useCallback(
    (e: React.MouseEvent<HTMLTableCellElement>, signalKey: string, row: string, col: string) => {
      if (leaveTimer.current) clearTimeout(leaveTimer.current);
      // Capture rects before the timeout — React nulls e.currentTarget after the handler returns
      const cellRect = e.currentTarget.getBoundingClientRect();
      enterTimer.current = setTimeout(() => {
        if (!wrapperRef.current) return;
        const wrapperRect = wrapperRef.current.getBoundingClientRect();
        // Position below the cell, centred horizontally
        const top = cellRect.bottom - wrapperRect.top + 6;
        let left = cellRect.left - wrapperRect.left + cellRect.width / 2;
        // Clamp so tooltip doesn't overflow wrapper right edge
        const wrapperWidth = wrapperRect.width;
        const tipWidth = 270; // approximate max-width of micro tooltip
        if (left + tipWidth / 2 > wrapperWidth) left = wrapperWidth - tipWidth / 2 - 8;
        if (left - tipWidth / 2 < 0) left = tipWidth / 2 + 8;
        setTooltipPos({ top, left });
        setHoveredKey(signalKey);
        setHighlightRow(row);
        setHighlightCol(col);
      }, 300);
    },
    [],
  );

  const handleCellLeave = useCallback(() => {
    if (enterTimer.current) clearTimeout(enterTimer.current);
    leaveTimer.current = setTimeout(() => {
      setHoveredKey(null);
      setHighlightRow(null);
      setHighlightCol(null);
    }, 100);
  }, []);

  const hoveredSignal = hoveredKey ? signalMap.get(hoveredKey) ?? null : null;

  return (
    <div ref={wrapperRef} style={{ position: "relative" }}>
    <table className="analysis-heatmap" data-testid="bn-heatmap">
      <thead>
        <tr>
          <th>{rowHeader}</th>
          {columnLabels.map((col) => {
            const isHl = col === highlightCol;
            const baseClass = isSentiment ? undefined : "heatmap-col-header";
            const hlClass = isHl ? (baseClass ? `${baseClass} heatmap-header-hl` : "heatmap-header-hl") : baseClass;
            return (
              <th key={col} className={hlClass || undefined}>
                {isSentiment ? (
                  <Badge text={col} variant="ai" sentiment={col} />
                ) : (
                  <span className="heatmap-col-label">{col}</span>
                )}
              </th>
            );
          })}
          <th className={isSentiment ? undefined : "heatmap-col-header"}>
            {isSentiment ? "Total" : <span className="heatmap-col-label">Total</span>}
          </th>
        </tr>
      </thead>
      <tbody>
        {matrix.row_labels.map((row) => {
          const rowTotal = matrix.row_totals[row] || 0;
          const isRowHl = row === highlightRow;
          return (
            <tr key={row}>
              <td className={isRowHl ? "heatmap-row-hl" : undefined}>{row}</td>
              {columnLabels.map((col) => {
                const cellKey = `${row}|${col}`;
                const cell = matrix.cells[cellKey];
                const count = cell?.count ?? 0;
                const colTotal = matrix.col_totals[col] || 0;
                const sourceType = rowHeader.toLowerCase().includes("section") ? "section" : "theme";
                const signalKey = `${sourceType}|${row}|${col}`;
                const hasCard = signalKeys.has(signalKey);
                const style = heatCellStyle(count, rowTotal, colTotal, grandTotal, isDark);
                const classes = [
                  "heatmap-cell",
                  hasCard ? "has-card" : "",
                ].filter(Boolean).join(" ");

                const ar = adjustedResidual(count, rowTotal, colTotal, grandTotal);
                const heatClasses = [
                  classes,
                  ar > 0 ? "heat-positive" : ar < 0 ? "heat-negative" : "",
                  ar > 0 && Math.abs(ar) / 4 > 0.7 ? "heat-strong" : "",
                ].filter(Boolean).join(" ");

                return (
                  <td
                    key={col}
                    className={heatClasses}
                    data-count={count}
                    data-row={row}
                    data-sentiment={col}
                    style={style}
                    onClick={hasCard ? () => onCellClick(signalKey) : undefined}
                    onMouseEnter={hasCard ? (e) => handleCellEnter(e, signalKey, row, col) : undefined}
                    onMouseLeave={hasCard ? handleCellLeave : undefined}
                  >
                    {count}
                  </td>
                );
              })}
              <td className="heatmap-total">{rowTotal}</td>
            </tr>
          );
        })}
        <tr>
          <td className="heatmap-total">Total</td>
          {columnLabels.map((col) => (
            <td key={col} className="heatmap-total">
              {matrix.col_totals[col] || 0}
            </td>
          ))}
          <td className="heatmap-total">{grandTotal}</td>
        </tr>
      </tbody>
    </table>
    {hoveredSignal && (
      <CellTooltip signal={hoveredSignal} allPids={allPids} pos={tooltipPos} />
    )}
    </div>
  );
}

/** Adapter to normalise sentiment matrix (camelCase) to snake_case shape. */
interface SentimentMatrixAdapter {
  cells: Record<string, { count: number }>;
  row_totals: Record<string, number>;
  col_totals: Record<string, number>;
  grand_total: number;
  row_labels: string[];
}

function adaptSentimentMatrix(m: {
  cells: Record<string, { count: number }>;
  rowTotals: Record<string, number>;
  colTotals: Record<string, number>;
  grandTotal: number;
  rowLabels: string[];
}): SentimentMatrixAdapter {
  return {
    cells: m.cells,
    row_totals: m.rowTotals,
    col_totals: m.colTotals,
    grand_total: m.grandTotal,
    row_labels: m.rowLabels,
  };
}

// ── Main Component ─────────────────────────────────────────────────────

interface AnalysisPageProps {
  projectId: string;
}

export function AnalysisPage({ projectId }: AnalysisPageProps) {
  const [cbData, setCbData] = useState<CodebookAnalysisListResponse | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);
  const [tagLoaded, setTagLoaded] = useState(false);

  // Transcript cache for quote context expansion (shared across all signal cards)
  const transcriptCache = useTranscriptCache();

  // Theme detection for heatmap colouring
  const [isDark, setIsDark] = useState(
    document.documentElement.getAttribute("data-theme") === "dark",
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.getAttribute("data-theme") === "dark");
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
  }, []);

  // Read baked sentiment data
  const sentimentData = useMemo(() => window.BRISTLENOSE_ANALYSIS ?? null, []);

  // Fetch per-codebook tag analysis from API
  useEffect(() => {
    getCodebookAnalysis()
      .then((data) => { setCbData(data); setTagLoaded(true); })
      .catch((err: Error) => { setTagError(err.message); setTagLoaded(true); });
  }, [projectId]);

  const hasSentiment = sentimentData !== null && sentimentData.signals.length > 0;
  const hasTags = cbData !== null && cbData.codebooks.some((cb) => cb.signals.length > 0);

  // Build full signal arrays (uncapped — used by tooltip lookups)
  const allSentimentSignals = useMemo<UnifiedSignal[]>(() => {
    if (!sentimentData) return [];
    return adaptSentimentSignals(sentimentData);
  }, [sentimentData]);

  const allTagSignals = useMemo<UnifiedSignal[]>(() => {
    if (!cbData) return [];
    return adaptCodebookSignals(cbData);
  }, [cbData]);

  // Capped to strongest N for card display
  const sentimentSignals = useMemo(() => allSentimentSignals.slice(0, MAX_SIGNALS), [allSentimentSignals]);
  const tagSignals = useMemo(() => allTagSignals.slice(0, MAX_SIGNALS), [allTagSignals]);

  // Sentiment data (flat, single matrix)
  const sentimentColumns = useMemo<string[]>(
    () => (sentimentData ? sentimentData.sentiments : []),
    [sentimentData],
  );
  const sentimentPids = useMemo<string[]>(
    () => (sentimentData ? sentimentData.participantIds : []),
    [sentimentData],
  );
  const sentimentSectionMatrix = useMemo(
    () => (sentimentData ? adaptSentimentMatrix(sentimentData.sectionMatrix) : null),
    [sentimentData],
  );
  const sentimentThemeMatrix = useMemo(
    () => (sentimentData ? adaptSentimentMatrix(sentimentData.themeMatrix) : null),
    [sentimentData],
  );

  // Tag data: collect all participant IDs across codebooks
  const tagAllPids = useMemo<string[]>(() => {
    if (!cbData) return [];
    const pids = new Set<string>();
    for (const cb of cbData.codebooks) {
      for (const pid of cb.participant_ids) pids.add(pid);
    }
    return Array.from(pids).sort(
      (a, b) => {
        const na = parseInt(a.slice(1), 10) || 0;
        const nb = parseInt(b.slice(1), 10) || 0;
        return na - nb;
      },
    );
  }, [cbData]);

  // Aggregate source breakdown across codebooks
  const sourceBreakdown = useMemo<SourceBreakdown | null>(() => {
    if (!cbData) return null;
    const total = { accepted: 0, pending: 0, total: 0 };
    for (const cb of cbData.codebooks) {
      total.accepted += cb.source_breakdown.accepted;
      total.pending += cb.source_breakdown.pending;
      total.total += cb.source_breakdown.total;
    }
    return total.total > 0 ? total : null;
  }, [cbData]);

  // Combined signal keys from both types (all signals, not just displayed cards)
  const signalKeys = useMemo(
    () => new Set([...allSentimentSignals, ...allTagSignals].map((s) => s.key)),
    [allSentimentSignals, allTagSignals],
  );

  // Signal lookup map for tooltip (key → signal)
  const signalMap = useMemo(() => {
    const m = new Map<string, UnifiedSignal>();
    for (const s of allSentimentSignals) m.set(s.key, s);
    for (const s of allTagSignals) m.set(s.key, s);
    return m;
  }, [allSentimentSignals, allTagSignals]);

  // Card refs for scroll-to from heatmap cells
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const handleCellClick = useCallback((key: string) => {
    const el = cardRefs.current.get(key);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.style.boxShadow = "0 0 0 3px var(--bn-colour-accent)";
      setTimeout(() => {
        el.style.boxShadow = "";
      }, 1500);
    }
  }, []);

  // Still loading
  if (!hasSentiment && !hasTags && !tagLoaded) {
    return (
      <div>
        <h2 className="section-heading">Analysis</h2>
        <p className="description" style={{ opacity: 0.5 }}>
          Loading analysis data&hellip;
        </p>
      </div>
    );
  }

  if (!hasSentiment && !hasTags) {
    return (
      <div>
        <h2 className="section-heading">Analysis</h2>
        <p className="description">
          No analysis data available. Run the pipeline or apply codebook tags to generate analysis.
        </p>
        {tagError && (
          <p style={{ color: "var(--bn-colour-danger, #c00)", fontSize: "0.82rem" }}>
            Tag analysis error: {tagError}
          </p>
        )}
      </div>
    );
  }

  const sentimentTotalP = sentimentData?.totalParticipants ?? 0;
  const tagTotalP = cbData?.total_participants ?? 0;

  return (
    <div data-testid="bn-analysis-page">
      {/* ── Sentiment signal cards ─────────────────────────────── */}
      {hasSentiment && sentimentSignals.length > 0 && (
        <>
          <h2 className="section-heading">Sentiment signals</h2>
          <p className="section-desc">
            Patterns ranked by signal strength — where sentiments concentrate
            more than expected given the study average.
          </p>
          <div className="signal-cards" id="signal-cards-sentiment">
            {sentimentSignals.map((s) => (
              <SignalCard
                key={s.key}
                signal={s}
                allPids={sentimentPids}
                isSentiment={true}
                transcriptCache={transcriptCache}
                cardRef={(el: HTMLDivElement | null) => {
                  if (el) cardRefs.current.set(s.key, el);
                  else cardRefs.current.delete(s.key);
                }}
              />
            ))}
          </div>
        </>
      )}

      {/* ── Tag signal cards ───────────────────────────────────── */}
      {hasTags && tagSignals.length > 0 && (
        <>
          {sourceBreakdown && <SourceBanner breakdown={sourceBreakdown} />}
          <h2 className="section-heading">Tag signals</h2>
          <p className="section-desc">
            Patterns ranked by signal strength — where codebook tags concentrate
            more than expected given the study average.
          </p>
          <div className="signal-cards" id="signal-cards-tags">
            {tagSignals.map((s) => (
              <SignalCard
                key={s.key}
                signal={s}
                allPids={tagAllPids}
                isSentiment={false}
                transcriptCache={transcriptCache}
                cardRef={(el: HTMLDivElement | null) => {
                  if (el) cardRefs.current.set(s.key, el);
                  else cardRefs.current.delete(s.key);
                }}
              />
            ))}
          </div>
        </>
      )}

      {/* ── Sentiment heatmaps ─────────────────────────────────── */}
      {hasSentiment && sentimentSectionMatrix && (
        <>
          <h2 className="section-heading" id="section-x-sentiment">
            Section × Sentiment
          </h2>
          <p className="section-desc">
            Quote counts per report section and sentiment.
            {sentimentTotalP > 0 && ` ${sentimentTotalP} participants total.`}
          </p>
          <Heatmap
            matrix={sentimentSectionMatrix}
            columnLabels={sentimentColumns}
            rowHeader="Section"
            isSentiment={true}
            signalKeys={signalKeys}
            signalMap={signalMap}
            allPids={sentimentPids}
            onCellClick={handleCellClick}
            isDark={isDark}
          />
        </>
      )}
      {hasSentiment && sentimentThemeMatrix && (
        <>
          <h2 className="section-heading">Theme × Sentiment</h2>
          <p className="section-desc">The same view grouped by cross-cutting themes.</p>
          <Heatmap
            matrix={sentimentThemeMatrix}
            columnLabels={sentimentColumns}
            rowHeader="Theme"
            isSentiment={true}
            signalKeys={signalKeys}
            signalMap={signalMap}
            allPids={sentimentPids}
            onCellClick={handleCellClick}
            isDark={isDark}
          />
        </>
      )}

      {/* ── Per-codebook tag heatmaps ──────────────────────────── */}
      {hasTags && cbData && cbData.codebooks.map((cb) => (
        <div key={cb.codebook_id} className="analysis-codebook-section">
          <h3 className="analysis-codebook-heading">{cb.codebook_name}</h3>
          {cb.section_matrix.grand_total > 0 && (
            <>
              <p className="analysis-heatmap-label">
                Section × {cb.codebook_name}
                {tagTotalP > 0 && ` · ${tagTotalP} participants`}
              </p>
              <Heatmap
                matrix={cb.section_matrix}
                columnLabels={cb.columns}
                rowHeader="Section"
                isSentiment={false}
                signalKeys={signalKeys}
                signalMap={signalMap}
                allPids={tagAllPids}
                onCellClick={handleCellClick}
                isDark={isDark}
              />
            </>
          )}
          {cb.theme_matrix.grand_total > 0 && (
            <>
              <p className="analysis-heatmap-label">
                Theme × {cb.codebook_name}
              </p>
              <Heatmap
                matrix={cb.theme_matrix}
                columnLabels={cb.columns}
                rowHeader="Theme"
                isSentiment={false}
                signalKeys={signalKeys}
                signalMap={signalMap}
                allPids={tagAllPids}
                onCellClick={handleCellClick}
                isDark={isDark}
              />
            </>
          )}
        </div>
      ))}
    </div>
  );
}
