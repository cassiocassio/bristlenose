/**
 * TagSpecimen — every state of a tag, in every context that draws one, drawn by
 * the code the app ships.
 *
 * Nothing here is a copy. Each context is the production component fed fixture
 * data: `QuoteCard` (Quotes and Discussion, and on the Screens stage),
 * `TagGroupCard` (the tag sidebar), `CodebookGroupColumn` (the Codebook lens),
 * `ZoneCounters` and `ProposalZoneList` (the AutoCode review dialog). Pulse, calm
 * and still go through `setPulse`, the switch a landing run uses
 * (contexts/AutoCodePlayback.ts, D8). The accept flash goes through each
 * component's own flash input. Hover and keyboard focus are the real pseudo-
 * classes: hover a tag, or Tab to one, to see them. Under each context, the
 * size the browser actually drew its first tag at, read from the page.
 *
 * The only things here that are not the app's are the frames around the
 * contexts: the containers each component sits in when the app draws it (their
 * own class names), and an inline style that undoes the tag sidebar's
 * reveal-on-open, so the panel shows without the layout that opens it.
 *
 * Not shown, because the app cannot draw them on this page: the export's
 * read-only tags (`isExportMode()` is global), the tag overview line (it reads
 * the project's own data), and the Codebook row's flash (driven by a running
 * AutoCode's playback).
 *
 * Route always registered at /report/tag-specimen and lazy-loaded, like
 * /report/specimen and /report/picker-specimen; kept out of the HTML export
 * (vite.export.config.ts). English-only by design (a dev tool).
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { SectionHeading } from "../components";
import { CodebookGroupColumn } from "../components/CodebookAuthoring";
import { ProposalZoneList } from "../components/ProposalZoneList";
import { TagGroupCard } from "../components/TagGroupCard";
import { ZoneCounters } from "../components/ZoneCounters";
import { setPulse } from "../contexts/AutoCodePlayback";
import { useSidebarSelector } from "../contexts/SidebarStore";
import { getGroupBg } from "../utils/colours";
import type {
  CodebookGroupResponse,
  ProposedTagBrief,
  ProposedTagResponse,
  QuoteResponse,
} from "../utils/types";
import { QuoteCard } from "./QuoteCard";
import { CARD_W } from "./screens/layout";
import "./screens/screens.css";

/** As QuoteGroup holds a flash: the key is `${domId}:${tagName}`, cleared after 500 ms. */
const FLASH_HOLD_MS = 500;

const noop = () => {};

// ── Fixtures ──────────────────────────────────────────────────────────

interface CardTag {
  id?: number;
  name: string;
  codebook_group: string;
  colour_set: string;
  colour_index: number;
}

interface CardState {
  quote: QuoteResponse;
  userTags: CardTag[];
  proposed: ProposedTagBrief[];
}

function quote(domId: string, text: string, sentiment: string | null, start: number): QuoteResponse {
  return {
    dom_id: domId,
    text,
    verbatim_excerpt: text,
    participant_id: "p2",
    session_id: "s2",
    speaker_name: "Sam",
    start_timecode: start,
    end_timecode: start + 12,
    sentiment,
    intensity: 2,
    researcher_context: null,
    quote_type: "screen_specific",
    topic_label: "Shopping bag",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: -1,
  };
}

function proposal(id: number, name: string, group: string, set: string, index: number, confidence: number): ProposedTagBrief {
  return {
    id,
    tag_definition_id: 100 + id,
    tag_name: name,
    group_name: group,
    colour_set: set,
    colour_index: index,
    confidence,
    rationale: "Fixture rationale.",
  };
}

function firstCard(domId: string): CardState {
  return {
    quote: quote(
      domId,
      "Get a shopping bag. Why do they call it a bag rather than a basket? What am I looking for? I'm going to do a search.",
      "delight",
      125,
    ),
    userTags: [{ id: 11, name: "convention expectation", codebook_group: "Jakob", colour_set: "ux", colour_index: 1 }],
    proposed: [
      proposal(1, "convention", "Jakob", "ux", 2, 0.62),
      proposal(2, "memory lapse", "Working memory", "emo", 3, 0.48),
    ],
  };
}

/** Two cards for the Quotes lens, and a copy of the first for the Screens stage (its own DOM id). */
function initialCards(): CardState[] {
  return [
    firstCard("q-tag-specimen-1"),
    {
      quote: quote(
        "q-tag-specimen-2",
        "Continue shopping. I'm going to go back to beds. Breadcrumb thing on the top left.",
        null,
        105,
      ),
      userTags: [],
      proposed: [proposal(3, "Doherty: waiting frustration", "Doherty", "task", 0, 0.22)],
    },
    firstCard("q-tag-specimen-3"),
  ];
}

const SIDEBAR_GROUP: CodebookGroupResponse = {
  id: 901,
  name: "Jakob's law",
  subtitle: "Users expect it to work the way other products taught them",
  colour_set: "ux",
  order: 0,
  tags: [
    { id: 11, name: "convention expectation", count: 5, tentative_count: 0, colour_index: 1 },
    { id: 12, name: "convention", count: 3, tentative_count: 4, colour_index: 2 },
    { id: 13, name: "transfer confusion", count: 0, tentative_count: 2, colour_index: 3 },
  ],
  total_quotes: 8,
  is_default: false,
  framework_id: null,
};

function reviewRow(
  id: number,
  text: string,
  name: string,
  set: string,
  index: number,
  confidence: number,
  status: ProposedTagResponse["status"],
  decidedBy: ProposedTagResponse["decided_by"],
): ProposedTagResponse {
  return {
    id,
    quote_id: id,
    dom_id: `q-tag-specimen-r${id}`,
    session_id: "s1",
    speaker_code: "p1",
    start_timecode: 60 + id * 7,
    quote_text: text,
    tag_definition_id: 200 + id,
    tag_name: name,
    group_name: "Fixture",
    colour_set: set,
    colour_index: index,
    confidence,
    rationale: "Fixture rationale.",
    status,
    decided_by: decidedBy,
  };
}

function initialReview(): ProposedTagResponse[] {
  return [
    reviewRow(31, "This is my test file. I'm going to go looking for a bed.", "Doherty: waiting frustration", "task", 0, 0.22, "pending", null),
    reviewRow(32, "Click and collect at Greenwich, add shopping bag.", "Gestalt: grouping confusion", "emo", 1, 0.24, "pending", null),
    reviewRow(33, "Beds, modern, white, floating design.", "Tesler: complexity absorbed", "ux", 2, 0.81, "accepted", "threshold"),
    reviewRow(34, "Oh, I like that. It asks you to log in and says a greeting.", "Kurosu: beauty trust", "trust", 1, 0.72, "accepted", "researcher"),
    reviewRow(35, "Is Greenwich my default store?", "Tesler: complexity burden", "ux", 3, 0.12, "denied", "threshold"),
  ];
}

// ── Measurement ───────────────────────────────────────────────────────

/** The size the browser drew the first tag in `root` at — what the page shows, not a token's name. */
function Measured({ root, selector, version }: { root: React.RefObject<HTMLElement | null>; selector: string; version: unknown }) {
  // Written straight into the DOM after layout: the reading is of the page as drawn, so it
  // follows the render rather than causing another one.
  const out = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    if (!out.current) return;
    const el = root.current?.querySelector<HTMLElement>(selector);
    if (!el) {
      out.current.textContent = "none drawn";
      return;
    }
    const s = getComputedStyle(el);
    const face = s.fontFamily.split(",")[0]?.trim() ?? "";
    out.current.textContent =
      `${s.fontSize} / ${s.lineHeight}, weight ${s.fontWeight}, padding ${s.paddingTop} ${s.paddingRight}, ` +
      `border ${s.borderTopWidth} ${s.borderTopStyle}, ${face}`;
  }, [root, selector, version]);
  return (
    <p data-testid="bn-tag-specimen-measured" style={{ color: "var(--bn-colour-muted)", fontSize: "var(--bn-text-caption)" }}>
      Measured <code>{selector}</code>: <span ref={out} />
    </p>
  );
}

function Context({ title, note, selector, version, children }: {
  title: string;
  note: string;
  selector: string;
  version: unknown;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <section style={{ marginBottom: "var(--bn-space-xl)" }} data-testid="bn-tag-specimen-context">
      <h2>{title}</h2>
      <p style={{ color: "var(--bn-colour-muted)" }}>{note}</p>
      <div ref={ref}>{children}</div>
      <Measured root={ref} selector={selector} version={version} />
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

type PulseState = "pulse" | "calm" | "still";

export function TagSpecimen() {
  const [pulse, setPulseState] = useState<PulseState>("still");
  const [cards, setCards] = useState<CardState[]>(initialCards);
  const [cardFlash, setCardFlash] = useState<Set<string>>(new Set());
  const [sidebarFlash, setSidebarFlash] = useState<Set<string>>(new Set());
  const [review, setReview] = useState<ProposedTagResponse[]>(initialReview);
  const tagsWidth = useSidebarSelector((s) => s.tagsWidth);
  const timers = useRef<number[]>([]);

  // The pulse is the root attribute a landing run sets, set by the same switch.
  useEffect(() => {
    setPulse(pulse === "still" ? null : pulse);
  }, [pulse]);
  useEffect(
    () => () => {
      setPulse(null);
      timers.current.forEach((id) => window.clearTimeout(id));
    },
    [],
  );

  const flash = useCallback((cardKeys: string[], sidebarNames: string[]) => {
    setCardFlash((prev) => new Set([...prev, ...cardKeys]));
    setSidebarFlash((prev) => new Set([...prev, ...sidebarNames]));
    timers.current.push(
      window.setTimeout(() => {
        setCardFlash((prev) => new Set([...prev].filter((k) => !cardKeys.includes(k))));
        setSidebarFlash((prev) => new Set([...prev].filter((k) => !sidebarNames.includes(k))));
      }, FLASH_HOLD_MS),
    );
  }, []);

  const accept = useCallback(
    (domId: string, proposalId: number, tagName: string) => {
      setCards((prev) =>
        prev.map((c) => {
          if (c.quote.dom_id !== domId) return c;
          const p = c.proposed.find((x) => x.id === proposalId);
          if (!p) return c;
          return {
            ...c,
            proposed: c.proposed.filter((x) => x.id !== proposalId),
            userTags: [
              ...c.userTags,
              { id: p.tag_definition_id ?? undefined, name: tagName, codebook_group: p.group_name, colour_set: p.colour_set, colour_index: p.colour_index },
            ],
          };
        }),
      );
      flash([`${domId}:${tagName}`], []);
    },
    [flash],
  );

  const deny = useCallback((domId: string, proposalId: number) => {
    setCards((prev) =>
      prev.map((c) => (c.quote.dom_id === domId ? { ...c, proposed: c.proposed.filter((x) => x.id !== proposalId) } : c)),
    );
  }, []);

  const replayFlash = useCallback(() => {
    const keys = cards.flatMap((c) => c.userTags.map((t) => `${c.quote.dom_id}:${t.name}`));
    flash(keys, SIDEBAR_GROUP.tags.map((t) => t.name));
  }, [cards, flash]);

  const reset = useCallback(() => {
    setCards(initialCards());
    setReview(initialReview());
  }, []);

  const decide = useCallback((id: number, status: "accepted" | "denied") => {
    setReview((prev) => prev.map((r) => (r.id === id ? { ...r, status, decided_by: "researcher" } : r)));
  }, []);

  const renderCard = (c: CardState) => (
    <QuoteCard
      key={c.quote.dom_id}
      quote={c.quote}
      displayText={c.quote.text}
      isStarred={false}
      isHidden={false}
      userTags={c.userTags}
      allTagNames={[...c.userTags.map((t) => t.name), ...c.proposed.map((p) => p.tag_name)]}
      deletedBadges={[]}
      isEdited={false}
      tagVocabulary={[]}
      sessionId={c.quote.session_id}
      hasMedia={false}
      hasModerator={false}
      proposedTags={c.proposed}
      flashingTags={cardFlash}
      moderatorQuestion={null}
      isQuestionOpen={false}
      isPillVisible={false}
      onToggleStar={noop}
      onToggleHide={noop}
      onEditCommit={noop}
      onTagAdd={noop}
      onTagRemove={noop}
      onBadgeDelete={noop}
      onBadgeRestore={noop}
      onProposedAccept={(proposalId, tagName) => accept(c.quote.dom_id, proposalId, tagName)}
      onProposedDeny={(proposalId) => deny(c.quote.dom_id, proposalId)}
      onToggleQuestion={noop}
      onQuoteHoverEnter={noop}
      onQuoteHoverLeave={noop}
      onPillHoverEnter={noop}
      onPillHoverLeave={noop}
    />
  );

  const tentativeRows = review.filter((r) => r.status === "pending");
  const acceptedRows = review.filter((r) => r.status === "accepted");
  const excludedRows = review.filter((r) => r.status === "denied");
  const tagCounts = Object.fromEntries(SIDEBAR_GROUP.tags.map((t) => [t.name.toLowerCase(), t.count]));
  const tentativeCounts = Object.fromEntries(SIDEBAR_GROUP.tags.map((t) => [t.name.toLowerCase(), t.tentative_count ?? 0]));
  const version = [pulse, cards, review];

  return (
    <div data-testid="bn-tag-specimen">
      <SectionHeading>Tag specimen</SectionHeading>
      <p>
        Every tag below is drawn by the component the app ships, with fixture data. Hover a tag or Tab to
        it for its hover and focus states; accept or deny a tentative tag to see what follows.
      </p>
      <div role="group" aria-label="Tentative tags" style={{ display: "flex", flexWrap: "wrap", gap: "var(--bn-space-sm)", margin: "var(--bn-space-md) 0 var(--bn-space-xl)" }}>
        {(["pulse", "calm", "still"] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={`bn-btn ${pulse === s ? "bn-btn-primary" : "bn-btn-secondary"}`}
            aria-pressed={pulse === s}
            onClick={() => setPulseState(s)}
            data-testid={`bn-tag-specimen-${s}`}
          >
            {s === "pulse" ? "Pulse" : s === "calm" ? "Calm (30 s from pulse)" : "Still"}
          </button>
        ))}
        <button type="button" className="bn-btn bn-btn-secondary" onClick={replayFlash} data-testid="bn-tag-specimen-flash">
          Replay accept flash
        </button>
        <button type="button" className="bn-btn bn-btn-secondary" onClick={reset} data-testid="bn-tag-specimen-reset">
          Reset
        </button>
      </div>

      <Context
        title="Quote card"
        note="QuoteCard as the Quotes and Discussion lenses draw it: an AI sentiment, an accepted tag, tentative tags."
        selector=".badge-proposed"
        version={version}
      >
        <div className="quote-group">{cards.slice(0, 2).map(renderCard)}</div>
      </Context>

      <Context
        title="Quote card on the Screens stage"
        note="The same QuoteCard inside the Screens lens's card, at its width; screens.css sets the gap between tags."
        selector=".badge-proposed"
        version={version}
      >
        <div className="screens-stage">
          <div className="screens-card" style={{ width: CARD_W }}>
            {renderCard(cards[2])}
          </div>
        </div>
      </Context>

      <Context
        title="Tag sidebar"
        note="TagGroupCard: tentative counts draw the pale segment of the bar; Replay accept flash flashes the row's tag."
        selector=".tag-sidebar .badge"
        version={version}
      >
        <aside
          className="tag-sidebar"
          // Undo the panel's reveal-on-open and its toolbar bleed, which need the layout that opens it.
          style={{ visibility: "visible", opacity: 1, position: "static", height: "auto", marginTop: 0, paddingTop: "var(--bn-space-md)", width: tagsWidth }}
        >
          <div className="codebook-body">
            <TagGroupCard
              name={SIDEBAR_GROUP.name}
              subtitle={SIDEBAR_GROUP.subtitle}
              colourSet={SIDEBAR_GROUP.colour_set}
              tags={SIDEBAR_GROUP.tags}
              groupBg={getGroupBg(SIDEBAR_GROUP.colour_set)}
              tagCounts={tagCounts}
              tentativeCounts={tentativeCounts}
              uncheckedSet={new Set()}
              clearAll={false}
              onToggleTag={noop}
              flashingTags={sidebarFlash}
            />
          </div>
        </aside>
      </Context>

      <Context
        title="Codebook"
        note="CodebookGroupColumn, as the Codebook lens draws a group: tentative counts draw the pale segment of each bar."
        selector=".codebook-group .badge"
        version={version}
      >
        <div className="v2-groups">
          <CodebookGroupColumn
            group={SIDEBAR_GROUP}
            allTagNames={SIDEBAR_GROUP.tags.map((t) => t.name)}
            onUpdateGroup={noop}
            onDeleteGroup={noop}
            onCreateTag={noop}
            onDeleteTag={noop}
            onRenameTag={noop}
            onDragStart={noop}
            onDragEnd={noop}
            onDropTag={noop}
            onMergeDrop={noop}
          />
        </div>
      </Context>

      <Context
        title="AutoCode review dialog"
        note="ZoneCounters and ProposalZoneList in the dialog's own body: a tentative row's tag is dotted and still; a decision you made carries a pin."
        selector=".threshold-tag-tentative"
        version={version}
      >
        <div className="codebook-modal-body threshold-body" style={{ maxWidth: "56rem" }}>
          <ZoneCounters excluded={excludedRows.length} tentative={tentativeRows.length} accepted={acceptedRows.length} />
          <ProposalZoneList zone="accepted" proposals={acceptedRows} removing={new Set()} onDeny={(id) => decide(id, "denied")} />
          <ProposalZoneList
            zone="tentative"
            proposals={tentativeRows}
            defaultExpanded={true}
            removing={new Set()}
            onAccept={(id) => decide(id, "accepted")}
            onDeny={(id) => decide(id, "denied")}
          />
          <ProposalZoneList zone="excluded" proposals={excludedRows} removing={new Set()} onAccept={(id) => decide(id, "accepted")} />
        </div>
      </Context>
    </div>
  );
}
