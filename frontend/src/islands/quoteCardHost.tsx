/**
 * The report's own quote card, hosted by a lens other than Quotes (Screens, Discussion).
 *
 * A quote looks and works the same wherever it is drawn (the owner, 15 and 19 Oct 2026): the
 * timecode plays, the badge opens the transcript, and the card stars, hides, tags, edits, drops its
 * sentiment and takes AutoCode proposals — through the one quotes store, so a gesture on any lens
 * shows on every other. This module is the one copy of that wiring:
 *
 *   useReportQuotes   — hydrates the store from /quotes (again on a refresh) and reads the
 *                       codebook's vocabulary, as the Quotes lens does.
 *   useQuoteCards     — draws a card, with QuoteGroup's gestures: a click on a card inside the
 *                       selection acts on the selection, narrowed to what the lens shows.
 *
 * Lifted out of the Screens lens (19 Oct 2026) when Discussion became its second user, so the two
 * cannot drift apart.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CounterItem } from "../components/Counter";
import type { TagVocabularyGroup } from "../components/TagInput";
import { useFocus } from "../contexts/FocusContext";
import { useLastRun } from "../contexts/LastRunStore";
import { useLensRead } from "../hooks/useLensRead";
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
  useQuotesStore,
} from "../contexts/QuotesContext";
import { toggleTagGroupHidden, useSidebarStore } from "../contexts/SidebarStore";
import { apiGet, getCodebook } from "../utils/api";
import { formatTimecode } from "../utils/format";
import type { SearchTerm } from "../utils/searchMatch";
import { deriveTagVisibility, type TagGroupMeta } from "../utils/tagVisibility";
import type { QuoteResponse, QuotesListResponse } from "../utils/types";
import { QuoteCard } from "./QuoteCard";

interface TagInfo extends TagGroupMeta {
  colour_set: string;
  colour_index: number;
}

export interface ReportQuotes {
  store: ReturnType<typeof useQuotesStore>;
  /** Every quote the report holds, by its id (`q-p1-123`). */
  byId: Map<string, QuoteResponse>;
  /** /quotes failed: a lens says so rather than drawing every count as zero. */
  failed: boolean;
  /** The store holds the report's quotes: this lens loaded them, or another lens already had. A
   *  failed load is not loaded (unless another lens's load is still in the store). */
  loaded: boolean;
  hasModerator: boolean;
  vocabulary: string[];
  groupedVocabulary: TagVocabularyGroup[];
  tagInfo: Record<string, TagInfo>;
}

const NO_FLASH = new Set<string>();
const noop = () => {};

/** The report's quotes and codebook, for a lens that draws quote cards. `lens` names it in the
 *  console only. */
export function useReportQuotes(lens: string): ReportQuotes {
  const { refreshKey } = useLastRun();
  const store = useQuotesStore();
  const [failed, setFailed] = useState(false);
  const [settled, setSettled] = useState(false);
  const [hasModerator, setHasModerator] = useState(false);
  const [vocabulary, setVocabulary] = useState<string[]>([]);
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);
  const [tagInfo, setTagInfo] = useState<Record<string, TagInfo>>({});

  // Hydrated as the Quotes lens hydrates it: on open, again after a run (once more if that fails,
  // useLensRead) and when tags change somewhere else (an AutoCode run or catch-up finishing, a
  // report applied), or this lens keeps its old tags and proposals until a run. A failed re-read
  // keeps what the store holds; only a first read that fails is the lens's to say (R86).
  const { reload } = useLensRead({
    read: () =>
      Promise.all([
        apiGet<QuotesListResponse>("/quotes"),
        getCodebook().catch((e: unknown) => {
          console.warn(`${lens}: no codebook, so no tag vocabulary`, e);
          return null;
        }),
      ]),
    apply: ([json, cb], kind) => {
      const all = [
        ...json.sections.flatMap((s) => s.quotes),
        ...json.themes.flatMap((th) => th.quotes),
        ...(json.unjoined ?? []),
      ];
      initFromQuotes(all, kind !== "first", json.uncategorised);
      setHasModerator(!!json.has_moderator);
      setFailed(false);
      setSettled(true);
      if (!cb) return;
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
    },
    onError: (_e, kind) => {
      if (kind === "first") setFailed(true);
    },
    refreshKey,
    key: lens,
    label: `${lens}: /quotes failed`,
  });
  useEffect(() => {
    document.addEventListener("bn:tags-changed", reload);
    return () => document.removeEventListener("bn:tags-changed", reload);
  }, [reload]);

  const byId = useMemo(() => {
    const m = new Map<string, QuoteResponse>();
    for (const q of [...store.quotes, ...(store.uncategorised ?? [])]) m.set(q.dom_id, q);
    return m;
  }, [store.quotes, store.uncategorised]);

  const loaded = settled || byId.size > 0;
  return { store, byId, failed, loaded, hasModerator, vocabulary, groupedVocabulary, tagInfo };
}

export interface CardOptions {
  highlight?: SearchTerm[];
  /** While hidden and collapsing, draw the Quotes lens's collapse (QuoteGroup's `.bn-hiding`)
   *  rather than the card. For a lens whose cards sit in the page's flow (Discussion); Screens
   *  places its cards on a board, where an emptied box would strand its grips and leader. */
  collapse?: boolean;
}

/** Draws quote cards for a lens. `scope` is every quote the lens shows, in its order: a click on a
 *  selected card acts on the selection narrowed to it, so nothing off the lens is touched. It is
 *  read when a gesture happens, not when a card is drawn, so a new scope redraws no card. */
export function useQuoteCards(host: ReportQuotes, scope: string[]) {
  const scopeRef = useRef(scope);
  useLayoutEffect(() => {
    scopeRef.current = scope;
  }, [scope]);
  const { store, tagInfo, vocabulary, groupedVocabulary, hasModerator } = host;
  const { selectedIds, clearSelection } = useFocus();
  const { hiddenTagGroups, disabledFrameworks } = useSidebarStore();
  const vis = useMemo(
    () => deriveTagVisibility(tagInfo, hiddenTagGroups, disabledFrameworks),
    [tagInfo, hiddenTagGroups, disabledFrameworks],
  );

  /** The selection the clicked card belongs to, narrowed to this lens; else the card alone. */
  const targets = useCallback(
    (domId: string) => (selectedIds.has(domId) ? scopeRef.current.filter((d) => selectedIds.has(d)) : [domId]),
    [selectedIds],
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

  // Stable while nothing it reads changes, so a lens can memoise a column of cards (Discussion's
  // All view keeps a splitter drag from re-rendering 1,800 of them).
  const renderCard = useCallback((q: QuoteResponse, opts: CardOptions = {}) => {
    const id = q.dom_id;
    // Hidden, and collapsing before it leaves: the Quotes lens's own collapse (QuoteGroup;
    // hidden-quotes.css .bn-hiding, HIDE_DURATION), for a lens that asks for it.
    if (opts.collapse && store.hiding.has(id)) return <blockquote key={id} id={id} className="quote-card bn-hiding" />;
    const allTags = store.tags[id] ?? [];
    const edited = store.edits[id] ?? null;
    const proposed = store.proposedTags[id] ?? [];
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
        // the moment". Only on the hosted lenses; the Quotes lens keeps it, and so does the code.
        // On Discussion the question is the line above the card anyway.
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
        highlight={opts.highlight}
      />
    );
  }, [store, vis, vocabulary, groupedVocabulary, hasModerator, onToggleStar, onToggleHide, onTagAdd, onProposedAccept]);

  /** The hidden-quotes Counter's rows for these quotes. */
  const { byId } = host;
  const counterItems = useCallback((ids: string[], hasMedia = false): CounterItem[] =>
    ids.flatMap((d) => {
      const q = byId.get(d);
      return q ? [{
        domId: d, timecode: formatTimecode(q.start_timecode), seconds: q.start_timecode,
        endSeconds: hasMedia ? q.end_timecode : undefined,
        participantId: q.participant_id, previewText: store.edits[d] ?? q.text, hasMedia,
      }] : [];
    }), [byId, store.edits]);

  return { renderCard, counterItems };
}
