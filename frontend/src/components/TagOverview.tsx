/**
 * TagOverview — the summary line at the top of the tag sidebar, and the AutoCode overview it
 * opens (docs/design-autocode-landing-plan.md Phase 6; the approved mockup is
 * docs/mockups/tag-sidebar-autocode-histogram.html).
 *
 * - **Before any run, and in an export** (D22): the line counts every tag in the sidebar but
 *   Sentiment's and those of a codebook whose eye is closed, as plain text. An export never
 *   reads the overview: proposals are server-only.
 * - **One reviewable codebook** (D17): "34 tags | Review". The line, chevron and words, is the
 *   disclosure; the chart below has the codebook's lines as ticks; Review opens the dialog.
 * - **Several**: "96 tags from **3 codebooks**", the count a link that splits the one merged
 *   chart (no ticks, no Review: their lines differ) into one chart per codebook, each with its
 *   own ticks and its own Review. Clicked while closed, it opens the overview split. The words
 *   around the link take their spacing from the translation, never from the layout: in Korean
 *   and Japanese the particle sits against the count.
 * - A reviewable codebook is one with a run, never Sentiment, never the researcher's own tags,
 *   and only while its eye is open and it is enabled. The line counts their tags only.
 * - **During a run** Review is drawn but inactive, so nothing moves when it ends (D17; the
 *   server refuses it, D49). The chart grows from the playback (D19): the scale only grows, in
 *   rounded steps; split charts that are not landing hold theirs; all rescale once at the end.
 *   Its ticks: the lower line at 0.30 and the upper at the run's live accept line (D47, D50).
 * - **Under search or Used** the line says what it always said there, the live match count.
 * - **Remembered per study, on the server** (D12): open/closed and merged/split; it opens by
 *   itself once, after a first run. After the first read each window keeps its own view
 *   (`contexts/TagOverviewStore.ts`).
 *
 * @module TagOverview
 */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { isExportMode } from "../utils/exportData";
import {
  liveZoneBins,
  markupRuns,
  nextScales,
  sameScales,
  splitAround,
  sumBins,
  tallyOf,
  ticksFor,
  zoneBins,
} from "../utils/tagOverview";
import type { OverviewBook } from "../utils/tagOverview";
import type { TagOverviewResponse, ZoneBin } from "../utils/types";
import { loadedEngine, snapshotHasRun, usePlayback } from "../contexts/AutoCodePlaybackView";
import {
  autoOpenOverview,
  loadTagOverview,
  rememberView,
  startTagOverview,
  useTagOverview,
} from "../contexts/TagOverviewStore";
import { ZoneHistogram } from "./ConfidenceHistogram";
import type { TickLines } from "./ConfidenceHistogram";
import { Icon } from "./Icon";

const MERGED = "__merged";
/** While a first apply lands here, the overview is read again this often, for the live accept
 *  line's tick: the playback carries the rows, not the line. */
const LIVE_LINE_READ_MS = 10_000;

type Served = TagOverviewResponse["codebooks"][number];

interface TagOverviewProps {
  /** Codebooks the line may count: enabled, eye open, not Sentiment, not the floor. */
  candidates: OverviewBook[];
  /** D22's counts: every tag in the sidebar but Sentiment's and eye-closed codebooks'. */
  plain: { tags: number; codebooks: number };
  /** Today's words under search or Used (the live match count), or null with no filter. */
  filterText: string | null;
  onReview: (book: OverviewBook) => void;
}

export function TagOverview({ candidates, plain, filterText, onReview }: TagOverviewProps) {
  const { t } = useTranslation();
  const exportMode = isExportMode();
  const bodyId = useId();
  const { read, settled, view } = useTagOverview();
  const snap = usePlayback();

  useEffect(() => {
    startTagOverview();
  }, []);

  // A run's follow leaving the playback: read once more, so the chart is the server's again.
  const following = useRef<Set<string>>(new Set());
  useEffect(() => {
    const now = new Set(snap.frameworks.keys());
    const left = [...following.current].some((id) => !now.has(id));
    following.current = now;
    if (left) loadTagOverview();
  }, [snap]);

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
      const lines: TickLines = ticksFor(c);
      const bins: ZoneBin[] = live
        ? liveZoneBins(engine?.liveProposals(book.id) ?? [], lines.lower)
        : zoneBins(c?.bins);
      // Review is inactive while a first apply codes (D17, D49); a catch-up keeps it live (D20).
      const coding = !!c?.coding || (!!fw && fw.kind === "first" && fw.handoverAt === null);
      return [{ ...book, bins, lines, live, coding, finished: !!c && !c.coding && !live }];
    });
  }, [candidates, read, snap]);

  // The live accept line rises batch by batch: read it again while a first apply lands.
  const landingFirst = books.some((b) => b.live && b.coding);
  useEffect(() => {
    if (!landingFirst) return;
    const timer = setInterval(loadTagOverview, LIVE_LINE_READ_MS);
    return () => clearInterval(timer);
  }, [landingFirst]);

  const open = view?.open ?? false;
  const split = view?.split ?? false;

  // Opens by itself once, after a first run (D12): a reviewable codebook whose run has ended
  // with something to show, on a study the overview never opened itself on.
  // `autoOpenOverview` opens it once per window, whatever a later read says.
  const shouldAutoOpen =
    !!read && !read.auto_opened && books.some((b) => b.finished && tallyTotal(b.bins) > 0);
  useEffect(() => {
    if (shouldAutoOpen) autoOpenOverview();
  }, [shouldAutoOpen]);

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
  if (!exportMode && !settled) {
    // The first read has not answered: the line keeps its height, so the wrong words never
    // flash before the right ones.
    return <div className="tag-sidebar-subtitle" data-testid="bn-tag-summary" aria-hidden="true">{" "}</div>;
  }
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
  const toggle = () => rememberView({ open: !open, split });
  const onSplit = () => rememberView({ open: true, split: open ? !split : true });

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

  const summary = (words: ReactNode, label?: string) => (
    <button
      type="button"
      className="tag-overview-summary"
      aria-expanded={open}
      aria-controls={open ? bodyId : undefined}
      aria-label={label}
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
    line = <>{summary(filterText)}{one && <>{" "}{review(books[0])}</>}</>;
  } else if (one) {
    line = <>{summary(tags)}{" "}{review(books[0])}</>;
  } else {
    const sentence = t("tags.summaryFromCodebooks", { count: books.length, tags });
    const parts = splitAround(sentence, "link") ?? { before: sentence, inner: "", after: "" };
    const before = parts.before.trimEnd();
    const after = parts.after.trimStart();
    line = (
      <>
        {/* The button holds only the words before the link, so it is named by the whole
            sentence, as a screen reader should hear it. */}
        {summary(before || null, joined(parts))}
        {/* Spacing from the translation: a space only where the sentence has one. */}
        {before !== parts.before && " "}
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
        {after !== parts.after && " "}
        {after && (
          // Words after the link (the count leads in Japanese, Korean, Turkish and Chinese): the
          // same disclosure for a pointer. The keyboard has the chevron's button.
          <button
            type="button"
            className="tag-overview-summary tag-overview-after"
            tabIndex={-1}
            aria-hidden="true"
            onClick={toggle}
          >
            {after}
          </button>
        )}
      </>
    );
  }

  const chart = (bins: ZoneBin[], scale: number, lines: TickLines | null) => {
    const tally = tallyOf(bins);
    const sentence = t("autocode.review.tally", {
      excludedLabel: t("autocode.review.zoneExcluded"),
      tentativeLabel: t("autocode.review.zoneTentative"),
      acceptedLabel: t("autocode.review.zoneAccepted"),
      excluded: tally.excluded,
      tentative: tally.tentative,
      accepted: tally.accepted,
    });
    const runs = markupRuns(sentence, ["exc", "ten", "acc"]);
    return (
      <div className="tag-overview-chart">
        <ZoneHistogram bins={bins} scale={scale} lines={lines} label={runs.map((r) => r.text).join("")} />
        <div className="tag-overview-tally" aria-hidden="true">
          {runs.map((r, i) =>
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
                  <span>{b.title}</span>{" "}{review(b)}
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

function joined(parts: { before: string; inner: string; after: string }): string {
  return `${parts.before}${parts.inner}${parts.after}`;
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
  return parts ? joined(parts) : sentence;
}
