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

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Metric, PersonBadge, SectionHeading } from "../components";
import { InspectorPanel, DimensionToggle, type InspectorSource } from "../components/InspectorPanel";
import {
  useInspectorStore,
  setInspectorSourceAndDimension,
  type InspectorDimension,
} from "../contexts/InspectorStore";
import {
  useAnalysisSignalStore,
  setAnalysisSignals,
  setFocusedSignalKey,
} from "../contexts/AnalysisSignalStore";
import { useIsDarkAppearance } from "../hooks/useIsDarkAppearance";
import { apiGet, getCodebookAnalysis } from "../utils/api";
import {
  dedupeSignals,
  groupSignalsByLocation,
  isFromSentimentLens,
} from "../utils/signalDedup";
import { reportHref } from "../utils/reportHref";
import { getBarColour, getGroupBg, getTagBg } from "../utils/colours";
import { formatTimecode } from "../utils/format";
import { detectSequences, type SequenceMeta } from "../utils/sequences";
import { selectQuotes } from "../utils/quoteSelection";
import { renderLead } from "../utils/leadSentence";
import type {
  AnalysisMatrix,
  CodebookAnalysisListResponse,
  SentimentAnalysisData,
  SentimentSignal,
  SourceBreakdown,
  TagSignalQuote,
  UnifiedSignal,
  UnifiedQuote,
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
/**
 * A safety valve, not a display rule.
 *
 * This used to be 6, sliced off each of two lists — twelve cards a project, and
 * the sidebar and the cards drew from that same slice, which was the only
 * reason they could not disagree. De-duplication does the capping now: the
 * busiest project in the trial corpus lands at 20 cards over 19 locations
 * against the 12 this allowed, and cards scale with LOCATIONS rather than study
 * length, because quotes per session is near-constant. The number below exists
 * so a pathological project cannot render thousands of cards; nothing real
 * reaches it. Applied before grouping, so it can never leave a location heading
 * with half its cards.
 */
const SAFETY_CAP = 60;

/** Quotes a card shows at rest. The rest are one click away and never dropped. */
const VISIBLE_QUOTES = 4;

// ── Types ──────────────────────────────────────────────────────────────
// UnifiedSignal and UnifiedQuote are imported from utils/types.ts

/**
 * The card's hero: the group or sentiment, the score, and the control that
 * opens the working.
 *
 * One chip, because most readers need one number. Measured across a trial
 * project's 24 signals, Agreement takes 3 distinct values and Intensity 4, both
 * clustered at the bottom of their scales, while Signal is close to collinear
 * with Concentration — two of the four metrics are captions, not columns. The
 * rest is for whoever wants to audit it, so it is behind this.
 *
 * A real <button>: keyboard reachable, `aria-expanded` carrying the disclosure
 * semantics, and a focus ring matching the nav rows and the location link. The
 * caret is always drawn, just quiet — a control has to read as a control BEFORE
 * the pointer arrives, and the chip is otherwise indistinguishable from the
 * tinted chips on the same card that are not clickable.
 *
 * No new i18n key: the button's own text ("Feedback 0.60") is its accessible
 * name and `aria-expanded` says what pressing it does, which is the standard
 * disclosure pattern. i18n is parked, and a tooltip is not worth 21 locales.
 */
function SignalHero({
  signal,
  isSentiment,
  expanded,
  onToggle,
}: {
  signal: UnifiedSignal;
  isSentiment: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { t } = useTranslation("enums");
  const { t: tc } = useTranslation();

  // The label is resolved server-side and arrives on the wire — a feeling, a
  // direction, or "Mixed sentiments". `columnLabel` is the fallback for a
  // response that predates it, and for the sentiment lens's own value cards.
  const raw = signal.label || signal.columnLabel;

  // A sentiment VALUE is translated and title-cased by `enums`. The two
  // summary labels and the hedge are NOT members of that map — they are this
  // design's own strings and carry their own keys in `common`.
  //
  // The old gate was `isSentiment`, which is true only on the fallback lens.
  // The rendered card never took that path, so it never reached the
  // translation at all and showed the raw group name, "Sentiment".
  const isValue = signal.labelKind === "value" || isSentiment;
  const SUMMARY: Record<string, string> = {
    Positive: "analysis.labelPositive",
    Negative: "analysis.labelNegative",
    "Mixed sentiments": "analysis.labelMixed",
  };
  const label = isValue
    ? t(`sentiment.${raw}`, { defaultValue: raw })
    : SUMMARY[raw]
      ? tc(SUMMARY[raw], { defaultValue: raw })
      : raw;

  const classes = [
    "badge",
    "signal-card-hero",
    isValue ? `badge-${raw}` : null,
  ]
    .filter(Boolean)
    .join(" ");
  const style =
    !isSentiment && signal.colourSet
      ? { backgroundColor: getGroupBg(signal.colourSet) }
      : undefined;

  return (
    <button
      type="button"
      className={classes}
      style={style}
      aria-expanded={expanded}
      data-testid="bn-signal-hero"
      onClick={(e) => {
        // The whole card is role="button" and focuses on click. Without this
        // the chip fires both — you open the working AND re-point the
        // inspector, which is not what pressing a disclosure should do.
        e.stopPropagation();
        onToggle();
      }}
    >
      {/* One chip, one background. A second chip was rejected: "too complex
          visually, adds confusion — the eye will jump to a single patch of
          colour". A null flag renders nothing at all, no gap, no placeholder. */}
      {signal.flag && (
        <span className="signal-card-hero-flag">{signal.flag}:</span>
      )}
      <span className="signal-card-hero-label">{label}</span>
      <span className="signal-card-hero-score">
        {signal.compositeSignal.toFixed(2)}
      </span>
      <span className="signal-card-hero-caret" aria-hidden="true">
        {"\u25be"}
      </span>
    </button>
  );
}

function adaptSentimentSignals(data: SentimentAnalysisData): UnifiedSignal[] {
  return data.signals.map((s: SentimentSignal) => ({
    key: `${s.sourceType}|${s.location}|${s.sentiment}`,
    location: s.location,
    sourceType: s.sourceType,
    columnLabel: s.sentiment,
    colourSet: "",
    codebookName: "",
    participants: s.participants,
    nEff: s.nEff,
    meanIntensity: s.meanIntensity,
    concentration: s.concentration,
    compositeSignal: s.compositeSignal,
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
        label: s.label,
        labelKind: s.label_kind,
        flag: s.flag,
        colourSet: s.colour_set || cb.colour_set,
        codebookName: cb.codebook_name,
        participants: s.participants,
        nEff: s.n_eff,
        meanIntensity: s.mean_intensity,
        concentration: s.concentration,
        compositeSignal: s.composite_signal,
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
        signalName: s.signal_name ?? null,
        pattern: s.pattern ?? null,
        elaboration: s.elaboration ?? null,
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
  const { t } = useTranslation();
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
            <span className="cell-tooltip-val">{signal.concentration.toFixed(1)}&times;</span> {t("analysis.conc")}
          </span>
          <span>
            <span className="cell-tooltip-val">{signal.participants.length}</span>
            {" "}{t("analysis.voice", { count: signal.participants.length })}
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
          <div className="cell-tooltip-footer">{t("analysis.more", { count: remaining })}</div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function SourceBanner({ breakdown }: { breakdown: SourceBreakdown }) {
  const { t } = useTranslation();
  if (breakdown.total === 0) return null;
  const parts: string[] = [];
  if (breakdown.accepted > 0) parts.push(t("analysis.accepted", { count: breakdown.accepted }));
  if (breakdown.pending > 0) parts.push(t("analysis.pending", { count: breakdown.pending }));
  return (
    <p
      className="description"
      style={{ fontSize: "var(--bn-text-label)", marginBottom: "var(--bn-space-md)" }}
      data-testid="bn-source-banner"
    >
      {t("analysis.basedOnTags", { parts: parts.join(" + "), count: breakdown.total })}
      {breakdown.pending > 0 && ` ${t("analysis.pendingWeighted")}`}
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

/** Mini bar chart showing this card's signal strength relative to siblings. */
function SparkBars({
  values,
  currentIndex,
  accentVar,
}: {
  values: number[];
  currentIndex: number;
  accentVar: string;
}) {
  const maxVal = Math.max(...values);
  if (maxVal === 0) return null;
  const n = values.length;
  const maxH = 28; // matches CSS .signal-sparkbars height
  const barW = Math.floor((96 - (n - 1) * 2) / n);
  return (
    <div className="signal-sparkbars">
      {values.map((v, i) => {
        const h = Math.max(2, (v / maxVal) * maxH);
        const opacity = i === currentIndex ? 1 : Math.max(0.09, (v / maxVal) * 0.45);
        return (
          <div
            key={i}
            className="signal-sparkbar"
            style={{
              height: `${h}px`,
              width: `${barW}px`,
              background: i === currentIndex ? accentVar : "var(--bn-colour-text)",
              opacity,
            }}
          />
        );
      })}
    </div>
  );
}

function SignalCard({
  signal,
  allPids,
  isSentiment,
  isFocused,
  cardRef,
  siblingSignals,
  signalIndex,
  elaborationsIn,
  onFocus,
}: {
  signal: UnifiedSignal;
  allPids: string[];
  isSentiment: boolean;
  /** Has the elaborated fetch come back? Distinguishes "no finding yet" from
   *  "no finding at all", which want different treatments. */
  elaborationsIn?: boolean;
  isFocused?: boolean;
  cardRef?: (el: HTMLDivElement | null) => void;
  siblingSignals?: number[];
  signalIndex?: number;
  onFocus?: (signal: UnifiedSignal) => void;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const expansionRef = useRef<HTMLDivElement>(null);

  const accentVar = isSentiment
    ? `var(--bn-sentiment-${signal.columnLabel})`
    : signal.colourSet
      ? getGroupBg(signal.colourSet)
      : "var(--bn-colour-accent)";

  const concPct = Math.min(100, Math.max(0, (signal.concentration / 5) * 100));
  const agreePct = signal.nEff > 0 && allPids.length > 0
    ? Math.min(100, (signal.nEff / allPids.length) * 100)
    : 0;



  // Four open, not one. Measured over the corpus: the median card carries 4
  // quotes and the longest 56, so the cap is the tail's problem and the
  // "show all" control is the exception — 24% of merged cards exceed it.
  //
  // WHICH four is editorial, not chronological: the strongest that carry the
  // finding, plus one slot held for the voice that argues with it. Selection
  // and ordering are separable — the chosen quotes come back in
  // `(participant, time)` order, so the sequence treatment is untouched.
  const { shown: visibleQuotes, dissenting } = useMemo(
    () => selectQuotes(signal, VISIBLE_QUOTES),
    [signal],
  );
  const shownIds = new Set(visibleQuotes);
  const hiddenQuotes = signal.quotes.filter((q) => !shownIds.has(q));

  // Sequences are a property of what is DRAWN, not of the whole set: two
  // quotes 10s apart are only a run if both are on screen. Computed over the
  // visible list and the hidden list separately for that reason.
  const sequenceMetas = useMemo(() => detectSequences(visibleQuotes), [visibleQuotes]);
  const hiddenMetas = useMemo(() => detectSequences(hiddenQuotes), [hiddenQuotes]);

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
  /** The metrics block, minimised by default. Independent of `expanded`,
   *  which owns the hidden QUOTES — two disclosures, two states. */
  const [workingOpen, setWorkingOpen] = useState(false);
  const toggleWorking = useCallback(() => setWorkingOpen((prev) => !prev), []);

  return (
    <div
      className={`signal-card${expanded ? " expanded" : ""}${isFocused ? " bn-selected" : ""}`}
      style={{ "--card-accent": accentVar } as React.CSSProperties}
      data-testid="bn-signal-card"
      ref={cardRef ?? undefined}
      role="button"
      tabIndex={0}
      // The pending headline block is decorative and correctly aria-hidden,
      // which left a screen-reader user with NO signal that a finding was
      // still coming — a sighted reader at least had a grey bar. Marked on the
      // card rather than announced per bar: role="status" on forty skeletons
      // would read forty announcements, which is not an improvement.
      aria-busy={!signal.signalName && !elaborationsIn ? true : undefined}
      onClick={() => onFocus?.(signal)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onFocus?.(signal);
        }
      }}
    >
      {/* The hero is emitted FIRST so the float catches the headline and the
          elaboration both — a float only affects content that follows it. The
          visual order is unchanged (it sits top-right); only the source order
          moved.

          The cost is real and not fixed: a screen reader now announces the
          chip before the finding's name. `order` would NOT fix it — it moves
          the visual rendering only, which is the classic accessibility trap.
          See design-signal-card.md §7. */}
      <div className="signal-card-top">
        <div className="signal-card-right">
          <SignalHero
            signal={signal}
            isSentiment={isSentiment}
            expanded={workingOpen}
            onToggle={toggleWorking}
          />
          {workingOpen && (
            <div className="signal-card-metrics" data-testid="bn-signal-working">
              <span className="metric-label" title={t("analysis.signalTitle")}>{t("analysis.signalLabel")}</span>
              <span className="metric-value">{signal.compositeSignal.toFixed(2)}</span>
              <span className="metric-viz">
                {siblingSignals && siblingSignals.length > 1 && signalIndex != null ? (
                  <SparkBars
                    values={siblingSignals}
                    currentIndex={signalIndex}
                    accentVar={signal.colourSet ? getBarColour(signal.colourSet) : accentVar}
                  />
                ) : null}
              </span>
              <Metric
                label={t("analysis.concLabel")}
                title={t("analysis.concTitle")}
                displayValue={`${signal.concentration.toFixed(1)}×`}
                viz={{ type: "bar", percentage: concPct }}
              />
              <Metric
                label={t("analysis.agreeLabel")}
                title={t("analysis.agreeTitle")}
                displayValue={signal.nEff.toFixed(1)}
                viz={{ type: "bar", percentage: agreePct }}
              />
              <Metric
                label={t("analysis.intensityLabel")}
                title={t("analysis.intensityTitle")}
                displayValue={signal.meanIntensity.toFixed(1)}
                viz={{ type: "dots", value: signal.meanIntensity }}
              />
            </div>
          )}
        </div>
        {/* No eyebrow on either branch. The location is the heading above this
            run of cards and is stated once there — printing it again on every
            card said the same thing three times in one viewport. The bare
            branch used to print the literal word "Section", which reads as a
            type label but only ever meant "no name was generated". */}
        <div className="signal-card-identity">
          {/* THE HEADLINE IS A FINDING, OR IT IS NOT THERE.
              It fell back to the location, which is the one string that is
              definitionally not a finding — and the location is the heading
              directly above, so every card repeated it. Worse, the lens
              fetches twice (once without elaboration, then with), so on first
              paint NO card had a name and every one of them said its location
              for three to five seconds.

              Pending: a skeleton, which says nothing false and does not make
              the card grow a headline under the reader a moment later.
              Returned and still absent: nothing. A card that cannot carry a
              finding should not pretend to. */}
          {signal.signalName ? (
            <div className="signal-card-location">{signal.signalName}</div>
          ) : !elaborationsIn ? (
            <div className="signal-card-location signal-card-location-pending" aria-hidden="true" />
          ) : null}
          {signal.elaboration && (
            <div
              className="signal-elaboration bn-lead-para"
              data-testid="signal-elaboration"
            >
              {renderLead(signal.elaboration)}
            </div>
          )}
          {/* Readings folded into this card. They cite essentially the same
              quotes, usually the same finding in another codebook's language —
              so spending a whole card's chrome on each spends the reader's
              attention twice for one answer. They are NOT deleted: the
              vocabulary survives here, and a researcher can see this place was
              also read that way. */}
          {signal.alternates?.length ? (
            <div className="signal-card-alternates" data-testid="bn-signal-alternates">
              {t("analysis.alsoReadAs")}{" "}
              {signal.alternates.map((alt, i) => (
                <Fragment key={alt.label}>
                  {i > 0 ? ", " : ""}
                  {/* The folded reading's own claim sits in the title. It is
                      the thing that made that card worth keeping, and storing
                      it while never showing it would make it exactly the kind
                      of carried-but-unread field this change removed three of.
                      A title rather than prose: the card's own finding is what
                      is being read, and this is available, not shouting. */}
                  <span
                    className="signal-card-alternate"
                    title={alt.elaboration?.replace("||", "\u2014").trim() || undefined}
                  >
                    {alt.signalName || alt.label}
                  </span>
                </Fragment>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="signal-card-quotes">
        {visibleQuotes.map((q, i) => (
          <QuoteBlock
            key={i}
            quote={q}
            isSentiment={isSentiment}
            sequenceMeta={sequenceMetas[i]}
            isDissenting={q === dissenting}
          />
        ))}
        <div
          className="signal-card-expansion"
          ref={expansionRef}
          style={{ maxHeight: expanded ? undefined : 0 }}
        >
          {hiddenQuotes.map((q, i) => (
            <QuoteBlock
              key={i + 1}
              quote={q}
              isSentiment={isSentiment}
              sequenceMeta={hiddenMetas[i]}
            />
          ))}
        </div>
      </div>

      <div className="signal-card-footer">
        {hiddenQuotes.length > 0 ? (
          <button
            type="button"
            className="signal-card-link signal-card-toggle"
            onClick={toggleExpand}
            data-testid="bn-signal-toggle"
          >
            {expanded ? t("analysis.hide") : t("analysis.showAllQuotes", { count: signal.quotes.length })}
          </button>
        ) : (
          <span className="signal-card-link" style={{ visibility: "hidden" }}>
            {t("analysis.oneQuote")}
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
  sequenceMeta,
  isDissenting,
}: {
  quote: UnifiedQuote;
  isSentiment: boolean;
  sequenceMeta?: SequenceMeta;
  /** Took the slot reserved for a voice that argues with the finding. Marked
   *  so a reader can see the card is not only agreeing with itself. */
  isDissenting?: boolean;
}) {
  const { t } = useTranslation();
  const tc = formatTimecode(quote.startSeconds);
  const tcHref = reportHref(`/report/sessions/${quote.sessionId}#t-${Math.floor(quote.startSeconds)}`);

  const seqPos = sequenceMeta?.position ?? "solo";
  const isContinuation = seqPos === "middle" || seqPos === "last";
  const seqClass = seqPos !== "solo" ? ` seq-${seqPos}` : "";
  const cls = [seqClass.trim(), isDissenting ? "bn-dissenting" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <blockquote className={cls || undefined} data-dissenting={isDissenting || undefined}>
      <div className="quote-row">
        <a className="timecode" href={tcHref}>
          <span className="timecode-bracket">[</span>
          {tc}
          <span className="timecode-bracket">]</span>
        </a>
        <span className="quote-body">
          <span className="quote-text">{quote.text}</span>
          {!isContinuation && (
            <>{" "}<span className="speaker">
              <PersonBadge code={quote.pid} role="participant" />
            </span></>
          )}
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
        <span className="intensity-dots" title={t("analysis.intensityTooltip", { value: quote.intensity })}>
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
  dimension,
  isSentiment,
  signalKeys,
  signalMap,
  allPids,
  onCellClick,
  isDark,
  topLeftContent,
}: {
  matrix: AnalysisMatrix | SentimentMatrixAdapter;
  columnLabels: string[];
  rowHeader: string;
  /** Logical dimension — "section" or "theme" — used for signal key lookup (not displayed). */
  dimension: "section" | "theme";
  isSentiment: boolean;
  signalKeys: Set<string>;
  signalMap: Map<string, UnifiedSignal>;
  allPids: string[];
  onCellClick: (key: string) => void;
  isDark: boolean;
  topLeftContent?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const grandTotal = matrix.grand_total;

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
        const tipHeight = 120; // approximate tooltip height
        const spaceBelow = window.innerHeight - cellRect.bottom;
        const placeAbove = spaceBelow < tipHeight + 12;
        const top = placeAbove
          ? cellRect.top - wrapperRect.top - tipHeight - 6
          : cellRect.bottom - wrapperRect.top + 6;
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

  if (grandTotal === 0 || matrix.row_labels.length === 0) return null;

  return (
    <div ref={wrapperRef} style={{ position: "relative" }}>
    <table className="analysis-heatmap" data-testid="bn-heatmap">
      <thead>
        <tr>
          <th>{topLeftContent ?? rowHeader}</th>
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
            {isSentiment ? t("analysis.total") : <span className="heatmap-col-label">{t("analysis.total")}</span>}
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
                const sourceType = dimension;
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
          <td className="heatmap-total">{t("analysis.total")}</td>
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

/**
 * A location's heading, and the lens's only link to the Quotes lens.
 *
 * The link used to sit on every card under this heading, which meant the same
 * destination repeated once per card and the location printed three times in a
 * viewport. One heading, one link.
 *
 * The anchor is namespaced because a section and a theme can share a name:
 * `section-<slug>` and `theme-<slug>` are different places. Slug format must
 * match QuoteSections / QuoteThemes exactly — lowercase, spaces to hyphens,
 * nothing else.
 */
function LocationHeading({
  location,
  sourceType,
}: {
  location: string;
  sourceType: "section" | "theme";
}) {
  const prefix = sourceType === "section" ? "section-" : "theme-";
  const anchor = `${prefix}${location.toLowerCase().replace(/ /g, "-")}`;
  return (
    <div className="analysis-codebook-heading">
      <a
        href={`#${anchor}`}
        className="signal-card-location-link"
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey) return;
          e.preventDefault();
          window.switchToTab?.("quotes");
          window.scrollToAnchor?.(anchor);
        }}
      >
        {location}
      </a>
    </div>
  );
}

interface AnalysisPageProps {
  projectId: string;
}

export function AnalysisPage({ projectId }: AnalysisPageProps) {
  const { t } = useTranslation();
  const [cbData, setCbData] = useState<CodebookAnalysisListResponse | null>(null);
  const [tagError, setTagError] = useState<string | null>(null);
  const [tagLoaded, setTagLoaded] = useState(false);

  // Theme detection for heatmap colouring. Reads the forced `data-theme` when
  // the web picker set one, else `prefers-color-scheme` — the desktop app
  // never writes the attribute (appearance is native).
  const isDark = useIsDarkAppearance();

  // Fetch sentiment data from API (or fall back to window global for legacy mode)
  const [sentimentData, setSentimentData] = useState<SentimentAnalysisData | null>(
    () => window.BRISTLENOSE_ANALYSIS ?? null,
  );
  useEffect(() => {
    // Already have baked data from window global — skip API fetch
    if (window.BRISTLENOSE_ANALYSIS) return;
    apiGet<SentimentAnalysisData>("/analysis/sentiment")
      .then((data) => {
        if (data.signals.length > 0) setSentimentData(data);
      })
      .catch(() => {});
  }, [projectId]);

  // Fetch per-codebook tag analysis from API
  useEffect(() => {
    getCodebookAnalysis()
      .then((data) => { setCbData(data); setTagLoaded(true); })
      .catch((err: Error) => { setTagError(err.message); setTagLoaded(true); });
  }, [projectId]);

  // Progressive enhancement: fetch with elaboration (may take 3-5s first time)
  const [elaborationsIn, setElaborationsIn] = useState(false);
  useEffect(() => {
    if (!tagLoaded) return;
    getCodebookAnalysis(true)
      .then((data) => { setCbData(data); })
      .catch(() => {})          // elaboration failure is non-fatal
      .finally(() => setElaborationsIn(true));
  }, [projectId, tagLoaded]);

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

  /**
   * One list, de-duplicated, ranked.
   *
   * A card is a (location × tag group), and sentiment is a group like any
   * other — so the Sentiment card comes from the CODEBOOK path, which carries
   * the sentiment framework as a one-group codebook. The /analysis/sentiment
   * lens draws one card per (location × sentiment VALUE) instead, which is the
   * shape that decision retired: confusion and frustration are tags inside the
   * Sentiment card, not cards of their own.
   *
   * Measured across the trial corpus: every project yields Sentiment-group
   * cards from the codebook path, so the sentiment lens's own signals are kept
   * only as a fallback for a project whose codebook path has none. Its
   * MATRICES are untouched either way — they feed the heatmaps.
   */
  const signals = useMemo(() => {
    const hasSentimentGroup = allTagSignals.some((s) => s.columnLabel === "Sentiment");
    const merged = hasSentimentGroup
      ? allTagSignals
      : [...allTagSignals, ...allSentimentSignals];
    return dedupeSignals(
      [...merged].sort((a, b) => b.compositeSignal - a.compositeSignal),
    ).slice(0, SAFETY_CAP);
  }, [allTagSignals, allSentimentSignals]);

  /** Every card's score, for the SparkBars comparison inside a card. It
   *  compares against the whole project rather than against the location,
   *  which is the more informative reading and is what shipped. */
  const siblingComposites = useMemo(
    () => signals.map((s) => s.compositeSignal),
    [signals],
  );

  /** Each card's position in that comparison, without an indexOf per card. */
  const siblingIndex = useMemo(
    () => new Map(signals.map((s, i) => [s.key, i])),
    [signals],
  );

  /**
   * Locations, ordered by their strongest signal; cards ordered within.
   *
   * Grouped through the SAME helper the sidebar uses, deliberately — that is
   * what makes the navigation one-to-one with the main content by
   * construction. Re-implementing the grouping here would make the two agree
   * only for as long as nobody edited one of them.
   */
  const places = useMemo(() => groupSignalsByLocation(signals), [signals]);

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

  /**
   * Which heatmap cells are hot.
   *
   * Built from the RENDERED list, not from every signal the analysis computed.
   * A cell whose card is not on the page has nothing to scroll to:
   * `scrollToCard` looks up a ref that is not in `cardRefs` and silently does
   * nothing. That was already true for every cell outside the old six-card cap;
   * de-duplication would have added a second class of it.
   */
  const signalKeys = useMemo(() => new Set(signals.map((s) => s.key)), [signals]);

  // Signal lookup map for tooltip (key → signal)
  const signalMap = useMemo(() => {
    const m = new Map<string, UnifiedSignal>();
    for (const s of allSentimentSignals) m.set(s.key, s);
    for (const s of allTagSignals) m.set(s.key, s);
    return m;
  }, [allSentimentSignals, allTagSignals]);

  // Card refs for scroll-to from heatmap cells
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  // ── Inspector store (for card focus → panel sync) ────────────────────
  // Must be called before early returns to satisfy Rules of Hooks.
  const { activeDimension } = useInspectorStore();

  // Shimmer trigger — increments when a card is focused while panel is collapsed
  const [shimmerTrigger, setShimmerTrigger] = useState(0);

  // Focused signal key — shared via AnalysisSignalStore (sidebar reads it)
  const { focusedKey: focusedSignalKey } = useAnalysisSignalStore();

  // Populate the store so the sidebar can render signal entries — the same
  // de-duplicated list the cards below are drawn from, which is what makes the
  // navigation one-to-one with the main content.
  useEffect(() => {
    setAnalysisSignals(signals);
  }, [signals]);

  const scrollToCard = useCallback((key: string) => {
    const el = cardRefs.current.get(key);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  const handleCellClick = useCallback((key: string) => {
    setFocusedSignalKey(key);
    scrollToCard(key);
  }, [scrollToCard]);

  const handleCardFocus = useCallback(
    (signal: UnifiedSignal) => {
      setFocusedSignalKey(signal.key);
      // Determine which source key this signal belongs to
      let sourceKey: string;
      if (signal.codebookName === "" || signal.codebookName === "Sentiment") {
        sourceKey = "sentiment";
      } else {
        // Find the codebook ID for this signal
        const cb = cbData?.codebooks.find((c) => c.codebook_name === signal.codebookName);
        sourceKey = cb ? `cb-${cb.codebook_id}` : "sentiment";
      }
      const dim: InspectorDimension = signal.sourceType === "theme" ? "theme" : "section";
      setInspectorSourceAndDimension(sourceKey, dim);
      setShimmerTrigger((n) => n + 1);
    },
    [cbData],
  );

  // Listen for sidebar signal-focus events
  useEffect(() => {
    const handler = (e: Event) => {
      const key = (e as CustomEvent<{ key: string }>).detail.key;
      scrollToCard(key);
      // Also sync inspector via handleCardFocus logic
      const signal = signals.find((s) => s.key === key);
      if (signal) {
        let sourceKey: string;
        if (signal.codebookName === "" || signal.codebookName === "Sentiment") {
          sourceKey = "sentiment";
        } else {
          const cb = cbData?.codebooks.find((c) => c.codebook_name === signal.codebookName);
          sourceKey = cb ? `cb-${cb.codebook_id}` : "sentiment";
        }
        const dim: InspectorDimension = signal.sourceType === "theme" ? "theme" : "section";
        setInspectorSourceAndDimension(sourceKey, dim);
        setShimmerTrigger((n) => n + 1);
      }
    };
    window.addEventListener("bn:signal-focus", handler);
    return () => window.removeEventListener("bn:signal-focus", handler);
  }, [scrollToCard, signals, cbData]);

  void activeDimension; // used indirectly by DimensionToggle components in sources

  // ── Build heatmap sources for InspectorPanel ─────────────────────────

  const heatmapSources = useMemo<InspectorSource[]>(() => {
    const sources: InspectorSource[] = [];

    // Sentiment source
    if (hasSentiment && sentimentSectionMatrix) {
      const sentHasBoth = !!sentimentThemeMatrix;
      sources.push({
        key: "sentiment",
        label: "Sentiment",
        sectionContent: (
          <Heatmap
            matrix={sentimentSectionMatrix}
            columnLabels={sentimentColumns}
            rowHeader={t("analysis.section")}
            dimension="section"
            isSentiment={true}
            signalKeys={signalKeys}
            signalMap={signalMap}
            allPids={sentimentPids}
            onCellClick={handleCellClick}
            isDark={isDark}
            topLeftContent={<DimensionToggle hasBoth={sentHasBoth} />}
          />
        ),
        themeContent: sentimentThemeMatrix ? (
          <Heatmap
            matrix={sentimentThemeMatrix}
            columnLabels={sentimentColumns}
            rowHeader={t("analysis.theme")}
            dimension="theme"
            isSentiment={true}
            signalKeys={signalKeys}
            signalMap={signalMap}
            allPids={sentimentPids}
            onCellClick={handleCellClick}
            isDark={isDark}
            topLeftContent={<DimensionToggle hasBoth={sentHasBoth} />}
          />
        ) : undefined,
      });
    }

    // Per-codebook sources
    if (hasTags && cbData) {
      for (const cb of cbData.codebooks) {
        const hasSection = cb.section_matrix.grand_total > 0;
        const hasTheme = cb.theme_matrix.grand_total > 0;
        if (!hasSection && !hasTheme) continue;

        const cbHasBoth = hasSection && hasTheme;
        sources.push({
          key: `cb-${cb.codebook_id}`,
          label: cb.codebook_name,
          sectionContent: hasSection ? (
            <Heatmap
              matrix={cb.section_matrix}
              columnLabels={cb.columns}
              rowHeader={t("analysis.section")}
            dimension="section"
              isSentiment={false}
              signalKeys={signalKeys}
              signalMap={signalMap}
              allPids={tagAllPids}
              onCellClick={handleCellClick}
              isDark={isDark}
              topLeftContent={<DimensionToggle hasBoth={cbHasBoth} />}
            />
          ) : undefined,
          themeContent: hasTheme ? (
            <Heatmap
              matrix={cb.theme_matrix}
              columnLabels={cb.columns}
              rowHeader={t("analysis.theme")}
            dimension="theme"
              isSentiment={false}
              signalKeys={signalKeys}
              signalMap={signalMap}
              allPids={tagAllPids}
              onCellClick={handleCellClick}
              isDark={isDark}
              topLeftContent={<DimensionToggle hasBoth={cbHasBoth} />}
            />
          ) : undefined,
        });
      }
    }

    return sources;
  }, [
    hasSentiment, sentimentSectionMatrix, sentimentThemeMatrix, sentimentColumns,
    sentimentPids, hasTags, cbData, tagAllPids, signalKeys, signalMap,
    handleCellClick, isDark, t,
  ]);

  // Still loading
  if (!hasSentiment && !hasTags && !tagLoaded) {
    return (
      <div>
        <SectionHeading>{t("analysis.heading")}</SectionHeading>
        <p className="description" style={{ opacity: 0.5 }}>
          {t("analysis.loadingData")}
        </p>
      </div>
    );
  }

  if (!hasSentiment && !hasTags) {
    return (
      <div>
        <SectionHeading>{t("analysis.heading")}</SectionHeading>
        <p className="description">
          {t("analysis.noData")}
        </p>
        {tagError && (
          <p style={{ color: "var(--bn-colour-danger, #c00)", fontSize: "var(--bn-text-label)" }}>
            {t("analysis.tagError", { error: tagError })}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="analysis-layout" data-testid="bn-analysis-page">
      {/* ── Center pane: signal cards ───────────────────────── */}
      <div className="analysis-center">
        {/* ── Signal cards, in the navigation's order ────────────
             One run of locations, ranked by their strongest signal, cards
             ranked within. It used to be two flat grids split by KIND, so a
             place appeared in both halves and nowhere as itself, and every
             card repeated its location because nothing above it said where it
             was. The heading is `.analysis-codebook-heading` — the class the
             lens already had for exactly this weight of statement; no new
             heading style was invented for this. The heatmaps do not live in
             this column at all: they are InspectorPanel's, rendered below. */}
        {/* The lens's zone title, and its FLUSH-TO-DATUM enrolment.
            `.analysis-center > .section-heading:first-of-type { margin-top: 0 }`
            in templates/report.css is how every lens starts at the same height;
            a lens that renders no .section-heading as the first child of its
            pane falls silently out of the system and opens 40px low. The old
            first heading was "Sentiment signals" — a SECTION title standing in
            for a LENS title, which is why removing it took the datum with it.
            e2e/tests/lens-datum.spec.ts is the gate, and no unit test can see a
            CSS selector failing to match. */}
        <SectionHeading>{t("analysis.heading")}</SectionHeading>
        {sourceBreakdown && <SourceBanner breakdown={sourceBreakdown} />}
        {places.map(({ location, cards }) => (
          <Fragment key={location}>
            <LocationHeading location={location} sourceType={cards[0].sourceType} />
            <div className="signal-cards">
              {cards.map((s) => (
                <SignalCard
                  key={s.key}
                  signal={s}
                  allPids={isFromSentimentLens(s) ? sentimentPids : tagAllPids}
                  isSentiment={isFromSentimentLens(s)}
                  isFocused={focusedSignalKey === s.key}
                  elaborationsIn={elaborationsIn}
                  siblingSignals={siblingComposites}
                  signalIndex={siblingIndex.get(s.key)}
                  cardRef={(el: HTMLDivElement | null) => {
                    if (el) cardRefs.current.set(s.key, el);
                    else cardRefs.current.delete(s.key);
                  }}
                  onFocus={handleCardFocus}
                />
              ))}
            </div>
          </Fragment>
        ))}
      </div>

      {/* ── Inspector panel: heatmaps ──────────────────────── */}
      <InspectorPanel sources={heatmapSources} shimmerTrigger={shimmerTrigger} />
    </div>
  );
}
