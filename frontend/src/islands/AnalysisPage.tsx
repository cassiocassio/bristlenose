/**
 * AnalysisPage — React island for the Analysis tab.
 *
 * Shows signal concentration cards and heatmaps for both:
 * - **Sentiment signals** (baked into HTML as `BRISTLENOSE_ANALYSIS` global)
 * - **Tag signals** (fetched per-codebook from `/api/projects/{id}/analysis/codebooks`)
 *
 * Reuses existing CSS from analysis.css — emits the same class names as
 * the vanilla JS analysis.js so all styling carries over.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Metric, PersonBadge } from "../components";
import { getCodebookAnalysis } from "../utils/api";
import { getGroupBg, getTagBg } from "../utils/colours";
import { formatTimecode } from "../utils/format";
import type {
  AnalysisMatrix,
  CodebookAnalysis,
  CodebookAnalysisListResponse,
  SentimentAnalysisData,
  SentimentSignal,
  SourceBreakdown,
  TagSignal,
  TagSignalQuote,
} from "../utils/types";

// ── Vanilla JS interop ─────────────────────────────────────────────────

declare global {
  interface Window {
    BRISTLENOSE_ANALYSIS?: SentimentAnalysisData;
    switchToTab?: (tab: string, pushHash?: boolean) => void;
    scrollToAnchor?: (anchorId: string, opts?: { block?: string; highlight?: boolean }) => void;
  }
}

// ── Types ──────────────────────────────────────────────────────────────

type ViewMode = "sentiment" | "tags";

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
  const heat = Math.min(1, absR / maxR);
  if (heat < 0.05) return {};

  const hue = r > 0 ? 150 : 20;
  const chroma = 0.12 * heat;
  const lMin = isDark ? 0.25 : 0.55;
  const lMax = isDark ? 0.55 : 0.95;
  const lightness = lMax - (lMax - lMin) * heat;

  return { background: `oklch(${lightness} ${chroma} ${hue})` };
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
}: {
  signal: UnifiedSignal;
  allPids: string[];
  isSentiment: boolean;
  cardRef?: (el: HTMLDivElement | null) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const expansionRef = useRef<HTMLDivElement>(null);

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
  }, [expanded]);

  const toggleExpand = useCallback(() => setExpanded((prev) => !prev), []);

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
        {visibleQuotes.map((q, i) => (
          <QuoteBlock key={i} quote={q} isSentiment={isSentiment} />
        ))}
        <div
          className="signal-card-expansion"
          ref={expansionRef}
          style={{ maxHeight: expanded ? undefined : 0 }}
        >
          {hiddenQuotes.map((q, i) => (
            <QuoteBlock key={i + 1} quote={q} isSentiment={isSentiment} />
          ))}
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

function QuoteBlock({
  quote,
  isSentiment,
}: {
  quote: UnifiedQuote;
  isSentiment: boolean;
}) {
  const tc = formatTimecode(quote.startSeconds);
  const tcHref = `sessions/transcript_${quote.sessionId}.html#t-${Math.floor(quote.startSeconds)}`;

  return (
    <blockquote>
      <div className="quote-row">
        <a className="timecode" href={tcHref}>
          <span className="timecode-bracket">[</span>
          {tc}
          <span className="timecode-bracket">]</span>
        </a>
        <span className="quote-body">
          <span className="speaker">
            <PersonBadge code={quote.pid} role="participant" />
          </span>{" "}
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
  onCellClick,
  isDark,
}: {
  matrix: AnalysisMatrix | SentimentMatrixAdapter;
  columnLabels: string[];
  rowHeader: string;
  isSentiment: boolean;
  signalKeys: Set<string>;
  onCellClick: (key: string) => void;
  isDark: boolean;
}) {
  const grandTotal = matrix.grand_total;
  if (grandTotal === 0 || matrix.row_labels.length === 0) return null;

  return (
    <table className="analysis-heatmap" data-testid="bn-heatmap">
      <thead>
        <tr>
          <th>{rowHeader}</th>
          {columnLabels.map((col) => (
            <th key={col} className={isSentiment ? undefined : "heatmap-col-header"}>
              {isSentiment ? (
                <Badge text={col} variant="ai" sentiment={col} />
              ) : (
                <span className="heatmap-col-label">{col}</span>
              )}
            </th>
          ))}
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
        {matrix.row_labels.map((row) => {
          const rowTotal = matrix.row_totals[row] || 0;
          return (
            <tr key={row}>
              <td>{row}</td>
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

// ── View Toggle ────────────────────────────────────────────────────────

function ViewToggle({
  mode,
  onToggle,
  hasSentiment,
  hasTags,
}: {
  mode: ViewMode;
  onToggle: (m: ViewMode) => void;
  hasSentiment: boolean;
  hasTags: boolean;
}) {
  if (!hasSentiment || !hasTags) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: "var(--bn-space-sm)",
        marginBottom: "var(--bn-space-lg)",
      }}
      data-testid="bn-analysis-toggle"
    >
      <button
        className={`bn-radio-label${mode === "sentiment" ? " active" : ""}`}
        onClick={() => onToggle("sentiment")}
        style={{
          background: mode === "sentiment" ? "var(--bn-colour-accent)" : "var(--bn-colour-bg)",
          color: mode === "sentiment" ? "#fff" : "var(--bn-colour-text)",
          border: "1px solid var(--bn-colour-border)",
          borderRadius: "var(--bn-radius-sm)",
          padding: "0.35rem 0.8rem",
          fontSize: "0.82rem",
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        Sentiment signals
      </button>
      <button
        className={`bn-radio-label${mode === "tags" ? " active" : ""}`}
        onClick={() => onToggle("tags")}
        style={{
          background: mode === "tags" ? "var(--bn-colour-accent)" : "var(--bn-colour-bg)",
          color: mode === "tags" ? "#fff" : "var(--bn-colour-text)",
          border: "1px solid var(--bn-colour-border)",
          borderRadius: "var(--bn-radius-sm)",
          padding: "0.35rem 0.8rem",
          fontSize: "0.82rem",
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        Tag signals
      </button>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

interface AnalysisPageProps {
  projectId: string;
}

export function AnalysisPage({ projectId }: AnalysisPageProps) {
  const [cbData, setCbData] = useState<CodebookAnalysisListResponse | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);
  const [tagLoaded, setTagLoaded] = useState(false);
  const [mode, setMode] = useState<ViewMode>("tags");

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

  // Default to whichever view has data
  useEffect(() => {
    if (hasTags && !hasSentiment) setMode("tags");
    else if (hasSentiment && !hasTags) setMode("sentiment");
    else if (hasTags) setMode("tags"); // prefer tags when both exist
  }, [hasSentiment, hasTags]);

  // Build unified signal cards for current mode
  const signals = useMemo<UnifiedSignal[]>(() => {
    if (mode === "sentiment" && sentimentData) return adaptSentimentSignals(sentimentData);
    if (mode === "tags" && cbData) return adaptCodebookSignals(cbData);
    return [];
  }, [mode, sentimentData, cbData]);

  // Sentiment-mode data (flat, single matrix)
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

  // Tag-mode: collect all participant IDs across codebooks for signal cards
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

  const allPids = mode === "sentiment" ? sentimentPids : tagAllPids;

  // Aggregate source breakdown across codebooks
  const sourceBreakdown = useMemo<SourceBreakdown | null>(() => {
    if (mode !== "tags" || !cbData) return null;
    const total = { accepted: 0, pending: 0, total: 0 };
    for (const cb of cbData.codebooks) {
      total.accepted += cb.source_breakdown.accepted;
      total.pending += cb.source_breakdown.pending;
      total.total += cb.source_breakdown.total;
    }
    return total.total > 0 ? total : null;
  }, [mode, cbData]);

  const signalKeys = useMemo(
    () => new Set(signals.map((s) => s.key)),
    [signals],
  );

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

  const isSentiment = mode === "sentiment";
  const totalParticipants = isSentiment
    ? (sentimentData?.totalParticipants ?? 0)
    : (cbData?.total_participants ?? 0);

  return (
    <div data-testid="bn-analysis-page">
      <ViewToggle
        mode={mode}
        onToggle={setMode}
        hasSentiment={hasSentiment}
        hasTags={hasTags}
      />

      {sourceBreakdown && <SourceBanner breakdown={sourceBreakdown} />}

      <h2 className="section-heading">Key findings</h2>
      <p className="section-desc">
        Patterns ranked by signal strength — where {isSentiment ? "sentiments" : "codebook tags"} concentrate
        more than expected given the study average.
      </p>

      {signals.length === 0 ? (
        <p className="description" style={{ opacity: 0.6 }}>
          No notable patterns detected.
        </p>
      ) : (
        <div className="signal-cards" id="signal-cards">
          {signals.map((s) => (
            <SignalCard
              key={s.key}
              signal={s}
              allPids={allPids}
              isSentiment={isSentiment}
              cardRef={(el: HTMLDivElement | null) => {
                if (el) cardRefs.current.set(s.key, el);
                else cardRefs.current.delete(s.key);
              }}
            />
          ))}
        </div>
      )}

      {/* Sentiment mode: single section/theme heatmap */}
      {isSentiment && sentimentSectionMatrix && (
        <>
          <h2 className="section-heading" id="section-x-sentiment">
            Section × Sentiment
          </h2>
          <p className="section-desc">
            Quote counts per report section and sentiment.
            {totalParticipants > 0 && ` ${totalParticipants} participants total.`}
          </p>
          <Heatmap
            matrix={sentimentSectionMatrix}
            columnLabels={sentimentColumns}
            rowHeader="Section"
            isSentiment={true}
            signalKeys={signalKeys}
            onCellClick={handleCellClick}
            isDark={isDark}
          />
        </>
      )}
      {isSentiment && sentimentThemeMatrix && (
        <>
          <h2 className="section-heading">Theme × Sentiment</h2>
          <p className="section-desc">The same view grouped by cross-cutting themes.</p>
          <Heatmap
            matrix={sentimentThemeMatrix}
            columnLabels={sentimentColumns}
            rowHeader="Theme"
            isSentiment={true}
            signalKeys={signalKeys}
            onCellClick={handleCellClick}
            isDark={isDark}
          />
        </>
      )}

      {/* Tag mode: separate heatmaps per codebook */}
      {!isSentiment && cbData && cbData.codebooks.map((cb) => (
        <div key={cb.codebook_id} className="analysis-codebook-section">
          <h3 className="analysis-codebook-heading">{cb.codebook_name}</h3>
          {cb.section_matrix.grand_total > 0 && (
            <>
              <p className="analysis-heatmap-label">
                Section × {cb.codebook_name}
                {totalParticipants > 0 && ` · ${totalParticipants} participants`}
              </p>
              <Heatmap
                matrix={cb.section_matrix}
                columnLabels={cb.columns}
                rowHeader="Section"
                isSentiment={false}
                signalKeys={signalKeys}
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
