/**
 * Quote card — `islands/QuoteCard.tsx`, the card every quote lens draws, in
 * each state it can show, fed fixture quotes. The cards sit in `.quote-group`,
 * the container the Quotes lens gives them (the tag specimen's pattern), so
 * the group's own rules apply. Focus and selection go through the app's focus
 * store (`useFocus`, which AppLayout provides), exactly as the keyboard sets
 * them; search marks come from `highlightTermsOf`, the function the Quotes lens
 * calls. Under each group, the size and padding the browser drew.
 *
 * Not drawn here: tag states (every one is on /report/tag-specimen); the
 * moderator-question pill and quote context expansion, both parked behind
 * feature flags (utils/featureFlags.ts), so the card draws nothing for them.
 */

import { useEffect, useState } from "react";

import { Counter, type CounterItem } from "../../../components/Counter";
import { useFocus } from "../../../contexts/FocusContext";
import { EMPTY_TAG_FILTER, highlightTermsOf } from "../../../utils/filter";
import type { QuoteResponse } from "../../../utils/types";
import { QuoteCard } from "../../QuoteCard";
import type { SpecimenMeta, SpecimenStory } from "../csf";
import { Measured } from "../measure";

export default {
  title: "Quote card/States",
  description:
    "QuoteCard (organisms/blockquote.css with the badge-row, quote-actions and editable-text molecules) in a .quote-group, and the hidden-quotes Counter from the group heading.",
  caveat:
    "Hover a card for its star, hide and add-tag controls; click its text to edit (edits are not saved). Tags and their states are on the tag specimen.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["AtRest", "Marked", "FocusAndSelection", "SearchMatch", "Paragraphs", "HiddenCounter"] as const;

const noop = () => {};

function quote(domId: string, text: string, overrides: Partial<QuoteResponse> = {}): QuoteResponse {
  return {
    dom_id: domId,
    text,
    verbatim_excerpt: text,
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Sarah Chen",
    start_timecode: 754,
    end_timecode: 769,
    sentiment: null,
    intensity: 2,
    researcher_context: null,
    quote_type: "general",
    topic_label: "Checkout",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: -1,
    ...overrides,
  };
}

const USER_TAG = { id: 21, name: "delivery anxiety", codebook_group: "Trust", colour_set: "trust", colour_index: 2 };

interface CardOptions {
  displayText?: string;
  isStarred?: boolean;
  isEdited?: boolean;
  hasMedia?: boolean;
  userTags?: (typeof USER_TAG)[];
  deletedBadges?: string[];
  researcherBreaks?: number[] | null;
  highlight?: ReturnType<typeof highlightTermsOf>;
}

function Card({ q, o = {} }: { q: QuoteResponse; o?: CardOptions }) {
  const userTags = o.userTags ?? [];
  return (
    <QuoteCard
      quote={q}
      displayText={o.displayText ?? q.text}
      isStarred={o.isStarred ?? false}
      isHidden={false}
      userTags={userTags}
      allTagNames={userTags.map((t) => t.name)}
      deletedBadges={o.deletedBadges ?? []}
      isEdited={o.isEdited ?? false}
      tagVocabulary={[]}
      sessionId={q.session_id}
      hasMedia={o.hasMedia ?? false}
      hasModerator={false}
      proposedTags={[]}
      flashingTags={new Set()}
      moderatorQuestion={null}
      isQuestionOpen={false}
      isPillVisible={false}
      researcherBreaks={o.researcherBreaks ?? null}
      highlight={o.highlight}
      onToggleStar={noop}
      onToggleHide={noop}
      onEditCommit={noop}
      onTagAdd={noop}
      onTagRemove={noop}
      onBadgeDelete={noop}
      onBadgeRestore={noop}
      onProposedAccept={noop}
      onProposedDeny={noop}
      onToggleQuestion={noop}
      onQuoteHoverEnter={noop}
      onQuoteHoverLeave={noop}
      onPillHoverEnter={noop}
      onPillHoverLeave={noop}
    />
  );
}

function Group({ children }: { children: React.ReactNode }) {
  return (
    <Measured selectors={[".quote-card", ".quote-text"]}>
      <div className="quote-group">{children}</div>
    </Measured>
  );
}

export const AtRest: SpecimenStory = {
  name: "At rest: AI sentiment and a tag, no recording; with a recording and the moderator's question",
  render: () => (
    <Group>
      <Card
        q={quote("q-sg-rest-1", "I didn't know if it would come before the weekend, so I just closed the tab.", { sentiment: "frustration" })}
        o={{ userTags: [USER_TAG] }}
      />
      <Card
        q={quote("q-sg-rest-2", "Oh, that's nice, it remembers my address from last time.", {
          participant_id: "p2",
          speaker_name: "Mary Adeyemi",
          sentiment: "delight",
          researcher_context: "When asked about saved details",
        })}
        o={{ hasMedia: true }}
      />
    </Group>
  ),
};

export const Marked: SpecimenStory = {
  name: "Starred, edited (undo shows), AI sentiment removed (restore shows)",
  render: () => (
    <Group>
      <Card q={quote("q-sg-starred", "This is the bit I'd show my manager.", { sentiment: "confidence" })} o={{ isStarred: true }} />
      <Card
        q={quote("q-sg-edited", "So I I went back and um changed the size.")}
        o={{ isEdited: true, displayText: "So I went back and changed the size." }}
      />
      <Card q={quote("q-sg-restore", "The button just sat there greyed out.", { sentiment: "frustration" })} o={{ deletedBadges: ["frustration"] }} />
    </Group>
  ),
};

/** Sets focus and a selection through the app's own focus store, and clears both on leaving. */
function FocusedCards() {
  const { setFocus, toggleSelection, clearSelection } = useFocus();
  useEffect(() => {
    setFocus("q-sg-focused", { scroll: false });
    toggleSelection("q-sg-selected-1");
    toggleSelection("q-sg-selected-2");
    return () => {
      setFocus(null, { scroll: false });
      clearSelection();
    };
    // Once on mount: the store is the app's, and the reader may move focus from here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <Group>
      <Card q={quote("q-sg-focused", "Where's the basket gone? It was up here a second ago.")} />
      <Card q={quote("q-sg-selected-1", "I'd expect it to say how much delivery is before I pay.", { participant_id: "p3", speaker_name: "Dr Amara Nwosu" })} />
      <Card q={quote("q-sg-selected-2", "Twelve pounds for delivery? No.", { participant_id: "p3", speaker_name: "Dr Amara Nwosu", sentiment: "frustration" })} />
    </Group>
  );
}

export const FocusAndSelection: SpecimenStory = {
  name: "Keyboard focus (first) and a two-card selection, set through the focus store",
  render: () => <FocusedCards />,
};

const SEARCH = highlightTermsOf({
  searchQuery: "delivery",
  searchTokens: [],
  viewMode: "all",
  tagFilter: EMPTY_TAG_FILTER,
  hidden: {},
  starred: {},
  tags: {},
  edits: {},
});

export const SearchMatch: SpecimenStory = {
  name: "Search for “delivery”: the match marked as the Quotes lens marks it",
  render: () => (
    <Group>
      <Card q={quote("q-sg-search", "I'd expect it to say how much delivery is before I pay, not after.")} o={{ highlight: SEARCH }} />
    </Group>
  ),
};

const LONG =
  "Normally I'd go straight to the basket. But this time there was a banner about next-day delivery, " +
  "so I clicked it to see if it applied to beds. It took me to a page about kitchens. " +
  "After that I didn't really trust the banners, so I used the search box instead, which was fine.";

export const Paragraphs: SpecimenStory = {
  name: "A long quote in the researcher's own paragraphs",
  render: () => (
    <Group>
      <Card q={quote("q-sg-long", LONG, { start_timecode: 1830, end_timecode: 1874 })} o={{ researcherBreaks: [6, 35] }} />
    </Group>
  ),
};

const HIDDEN: CounterItem[] = [
  { domId: "q-sg-h1", timecode: "03:12", seconds: 192, participantId: "p1", previewText: "Yeah, that's fine.", hasMedia: false },
  { domId: "q-sg-h2", timecode: "11:40", seconds: 700, participantId: "p2", previewText: "Can you repeat the question?", hasMedia: false },
  { domId: "q-sg-h3", timecode: "24:05", seconds: 1445, participantId: "p3", previewText: "Sorry, my cat walked on the keyboard.", hasMedia: false },
];

function LiveCounter() {
  const [open, setOpen] = useState(false);
  return (
    <Counter
      count={HIDDEN.length}
      items={HIDDEN}
      isOpen={open}
      onToggle={() => setOpen((v) => !v)}
      onUnhide={noop}
      onUnhideAll={() => setOpen(false)}
    />
  );
}

export const HiddenCounter: SpecimenStory = {
  name: "Hidden-quotes counter from a group heading (live: open it)",
  render: () => <LiveCounter />,
};
