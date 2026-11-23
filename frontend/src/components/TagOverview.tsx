/**
 * TagOverview — the summary line at the top of the tag sidebar, and the AutoCode overview it
 * opens (docs/design-autocode-landing-plan.md Phase 6; the approved mockup is
 * docs/mockups/tag-sidebar-autocode-histogram.html).
 *
 * - **Before any run, and in an export** (D22): the line counts every tag in the sidebar but
 *   Sentiment's, as plain text. An export never reads the overview: proposals are server-only.
 * - **One reviewable codebook** (D17): "34 tags | Review". The line, chevron and words, is the
 *   disclosure; the chart below has the codebook's lines as ticks; Review opens the dialog.
 * - **Several**: "96 tags from **3 codebooks**", the count a link that splits the one merged
 *   chart (no ticks, no Review: their lines differ) into one chart per codebook, each with its
 *   own ticks and its own Review. Clicked while closed, it opens the overview split.
 * - A reviewable codebook is one with a run, never Sentiment, never the researcher's own tags,
 *   and only while its eye is open and it is enabled. The line counts their tags only.
 * - **During a run** Review is drawn but inactive, so nothing moves when it ends (D17; the
 *   server refuses it, D49). The chart grows from the playback (D19): the scale only grows, in
 *   rounded steps; split charts that are not landing hold theirs; all rescale once at the end.
 * - **Under search or Used** the line says what it always said there, the live match count.
 * - **Remembered per study, on the server** (D12): open/closed and merged/split; it opens by
 *   itself once, after a first run.
 *
 * @module TagOverview
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { getTagOverview, patchTagOverview } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import { chooseSquares } from "../utils/livePacing";
import { storedLinesOf } from "../utils/recut";
import type { Lines } from "../utils/recut";
import {
  DEFAULT_LINES,
  liveZoneBins,
  markupRuns,
  nextScales,
  sameScales,
  splitAround,
  sumBins,
  tallyOf,
  zoneBins,
} from "../utils/tagOverview";
import type { OverviewBook } from "../utils/tagOverview";
import type { TagOverviewResponse, ZoneBin } from "../utils/types";
import {
  loadedEngine,
  snapshotHasRun,
  stampedRead,
  usePlayback,
} from "../contexts/AutoCodePlaybackView";
import { ZoneHistogram } from "./ConfidenceHistogram";
import { Icon } from "./Icon";

/** The chart's height in px (molecules/tag-overview.css) over a bin about 11 px wide in the
 *  sidebar's usual width: two squares to a column. */
const MAX_STACK = 2;
const MERGED = "__merged";

type Served = TagOverviewResponse["codebooks"][number];

function isOverview(value: unknown): value is TagOverviewResponse {
  const v = value as TagOverviewResponse | null;
  return !!v && typeof v === "object" && Array.isArray(v.codebooks) && typeof v.open === "boolean";
}

interface TagOverviewProps {
  /** Codebooks the line may count: enabled, eye open, not Sentiment, not the floor. */
  candidates: OverviewBook[];
  /** D22's counts: every tag in the sidebar but Sentiment's, and their codebooks. */
  plain: { tags: number; codebooks: number };
  /** Today's words under search or Used (the live match count), or null with no filter. */
  filterText: string | null;
  /** Quotes in the study: squares or bars are chosen once, from it. */
  quoteCount: number;
  onReview: (book: OverviewBook) => void;
}

export function TagOverview({ candidates, plain, filterText, quoteCount, onReview }: TagOverviewProps) {
  const { t } = useTranslation();
  const exportMode = isExportMode();
  const bodyId = useId();

  // ── The server's read, again after a run ends or a codebook changes ──
  const [read, setRead] = useState<TagOverviewResponse | null>(null);
  useEffect(() => {
    if (exportMode) return;
    let alive = true;
    const load = () => {
      // Stamped, so a read from before a run's end is told from one after it.
      stampedRead(getTagOverview)
        .then((r) => {
          if (alive && isOverview(r)) setRead(r);
        })
        .catch(() => {
          // The overview is an extra: the line stays as it was.
        });
    };
    load();
    document.addEventListener("bn:tags-changed", load);
    window.addEventListener("codebook-changed", load);
    return () => {
      alive = false;
      document.removeEventListener("bn:tags-changed", load);
      window.removeEventListener("codebook-changed", load);
    };
  }, [exportMode]);

  const snap = usePlayback();

  // ── Which codebooks are reviewable, and how each one draws ──
  const books = useMemo(() => {
    const served = new Map<string, Served>((read?.codebooks ?? []).map((c) => [c.framework_id, c]));
    const engine = loadedEngine();
    return candidates.flatMap((book) => {
      const c = served.get(book.id);
      const fw = snap.frameworks.get(book.id);
      // A run is landing here while the read cannot have it yet.
      const live = !!fw && !snapshotHasRun(read, fw);
      if (!c && !live) return [];
      const stored = c ? storedLinesOf({ applied_lower_threshold: c.lower, applied_upper_threshold: c.upper }, DEFAULT_LINES) : null;
      const lines: Lines = stored ?? DEFAULT_LINES;
      const bins: ZoneBin[] = live
        ? liveZoneBins(c ? zoneBins(c.bins) : null, engine?.liveProposals(book.id) ?? [], lines.lower)
        : zoneBins(c?.bins);
      // Review is inactive while a first apply codes (D17, D49); a catch-up keeps it live (D20).
      const coding = !!c?.coding || (!!fw && fw.kind === "first" && fw.handoverAt === null);
      return [{ ...book, bins, lines, live, coding, finished: !!c && !c.coding && !live }];
    });
  }, [candidates, read, snap]);

  // ── What is remembered: the first read's, then the researcher's ──
  const [view, setView] = useState<{ open: boolean; split: boolean } | null>(null);
  if (read && view === null) setView({ open: read.open, split: read.split });
  const open = view?.open ?? false;
  const split = view?.split ?? false;

  // Opens by itself once, after a first run (D12): a reviewable codebook whose run has ended
  // with something to show, on a study the overview never opened itself on.
  const [autoOpened, setAutoOpened] = useState(false);
  const shouldAutoOpen =
    !!read && view !== null && !read.auto_opened && !autoOpened &&
    books.some((b) => b.finished && tallyTotal(b.bins) > 0);
  if (shouldAutoOpen) {
    setAutoOpened(true);
    if (!view.open) setView({ ...view, open: true });
  }
  const told = useRef(false);
  useEffect(() => {
    if (!autoOpened || told.current) return;
    told.current = true;
    patchTagOverview({ open: true, auto_opened: true }).catch(() => undefined);
  }, [autoOpened]);

  const remember = useCallback((next: { open: boolean; split: boolean }) => {
    setView(next);
    patchTagOverview(next).catch(() => undefined);
  }, []);

  // Squares or bars, chosen once, from the quote count, when it is first known (D19).
  const [squares, setSquares] = useState<boolean | null>(null);
  if (squares === null && quoteCount > 0) setSquares(chooseSquares(quoteCount, MAX_STACK));

  // ── Scales: grow-only while anything lands, one rescale when it ends (D19) ──
  const merged = useMemo(() => sumBins(books.map((b) => b.bins)), [books]);
  const charts = useMemo(
    () => [
      { id: MERGED, bins: merged, live: books.some((b) => b.live) },
      ...books.map((b) => ({ id: b.id, bins: b.bins, live: b.live })),
    ],
    [books, merged],
  );
  const [scales, setScales] = useState<Record<string, number> | null>(null);
  const computed = nextScales(scales, charts, MERGED);
  if (!sameScales(scales, computed)) setScales(computed);

  // ── The line ──
  if (exportMode || books.length === 0) {
    return (
      <div className="tag-sidebar-subtitle" data-testid="bn-tag-summary">
        {filterText ?? plainLine(t, plain)}
      </div>
    );
  }

  const one = books.length === 1;
  const tagTotal = books.reduce((s, b) => s + b.tagCount, 0);
  const tags = t("tags.countTags", { count: tagTotal });
  const toggle = () => remember({ open: !open, split });
  const onSplit = () => remember({ open: true, split: open ? !split : true });

  const review = (book: (typeof books)[number]) => (
    <span className="tag-overview-review">
      <span className="tag-filter-separator" aria-hidden="true">|</span>
      <button
        type="button"
        className="tag-filter-action"
        aria-disabled={book.coding || undefined}
        data-testid="bn-tag-overview-review"
        onClick={() => {
          if (!book.coding) onReview(book);
        }}
      >
        {t("codebook.reviewProposals")}
      </button>
    </span>
  );

  const summary = (words: ReactNode) => (
    <button
      type="button"
      className="tag-overview-summary"
      aria-expanded={open}
      aria-controls={open ? bodyId : undefined}
      onClick={toggle}
      data-testid="bn-tag-overview-toggle"
    >
      <Icon name="disclose" px={12} decorative className="codebook-disclosure tag-overview-chevron" />
      {words}
    </button>
  );

  let line: ReactNode;
  if (filterText !== null) {
    // Search or Used: the live match count, as shipped; the split link is part of the sentence
    // it replaces, so it waits for the filter to clear.
    line = <>{summary(filterText)}{one && review(books[0])}</>;
  } else if (one) {
    line = <>{summary(tags)}{review(books[0])}</>;
  } else {
    const sentence = t("tags.summaryFromCodebooks", { count: books.length, tags });
    const parts = splitAround(sentence, "link") ?? { before: sentence, inner: "", after: "" };
    line = (
      <>
        {summary(parts.before.trimEnd() || null)}
        {parts.inner && (
          <button
            type="button"
            className={`tag-filter-action tag-overview-split${split && open ? " tag-filter-action-active" : ""}`}
            aria-pressed={split && open}
            onClick={onSplit}
            data-testid="bn-tag-overview-split"
          >
            {parts.inner}
          </button>
        )}
        {parts.after.trim() && (
          // Words after the link (the codebook count leads in Japanese, Korean, Turkish and
          // Chinese): the same disclosure for a pointer. The keyboard has the chevron's button.
          <button
            type="button"
            className="tag-overview-summary tag-overview-after"
            tabIndex={-1}
            aria-hidden="true"
            onClick={toggle}
          >
            {parts.after.trim()}
          </button>
        )}
      </>
    );
  }

  const chart = (bins: ZoneBin[], scale: number, lines: Lines | null) => {
    const tally = tallyOf(bins);
    const labels = {
      excludedLabel: t("autocode.review.zoneExcluded"),
      tentativeLabel: t("autocode.review.zoneTentative"),
      acceptedLabel: t("autocode.review.zoneAccepted"),
      excluded: tally.excluded,
      tentative: tally.tentative,
      accepted: tally.accepted,
    };
    const sentence = t("autocode.review.tally", labels);
    const plainTally = markupRuns(sentence, ["exc", "ten", "acc"]).map((r) => r.text).join("");
    return (
      <div className="tag-overview-chart">
        <ZoneHistogram bins={bins} scale={scale} squares={squares ?? false} lines={lines} label={plainTally} />
        <div className="tag-overview-tally" aria-hidden="true">
          {markupRuns(sentence, ["exc", "ten", "acc"]).map((r, i) =>
            r.tag ? (
              <b key={i} className={`tag-overview-n tag-overview-n--${r.tag}`}>{r.text}</b>
            ) : (
              <span key={i}>{r.text}</span>
            ),
          )}
        </div>
      </div>
    );
  };

  const scaleOf = (id: string) => computed[id] ?? 5;

  return (
    <>
      <div className="tag-sidebar-subtitle tag-overview-line" data-testid="bn-tag-summary">
        {line}
      </div>
      {open && (
        <div className="tag-overview-body" id={bodyId} data-testid="bn-tag-overview">
          {one ? (
            chart(books[0].bins, scaleOf(books[0].id), books[0].lines)
          ) : split ? (
            books.map((b) => (
              <div key={b.id} className="tag-overview-book" data-testid="bn-tag-overview-book">
                <div className="tag-overview-book-name">
                  <span>{b.title}</span>
                  {review(b)}
                </div>
                {chart(b.bins, scaleOf(b.id), b.lines)}
              </div>
            ))
          ) : (
            // Merged: no ticks, no Review (their lines differ; reviewing across codebooks at
            // once is not an act anything builds).
            chart(merged, scaleOf(MERGED), null)
          )}
        </div>
      )}
    </>
  );
}

function tallyTotal(bins: readonly ZoneBin[]): number {
  const t = tallyOf(bins);
  return t.accepted + t.tentative + t.excluded;
}

/** D22's line: "43 tags", or "96 tags from 3 codebooks" as plain words with no link. */
function plainLine(
  t: ReturnType<typeof useTranslation>["t"],
  plain: { tags: number; codebooks: number },
): string {
  const tags = t("tags.countTags", { count: plain.tags });
  if (plain.codebooks <= 1) return tags;
  const sentence = t("tags.summaryFromCodebooks", { count: plain.codebooks, tags });
  const parts = splitAround(sentence, "link");
  return parts ? `${parts.before}${parts.inner}${parts.after}` : sentence;
}
