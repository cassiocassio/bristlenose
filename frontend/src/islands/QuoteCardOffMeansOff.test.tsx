import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuoteCard } from "./QuoteCard";
import type { QuoteResponse } from "../utils/types";

// N189. "Off means off" (design-codebook-state-model.md §5; tagVisibility.ts): a switched-off
// codebook's tags drop out of the autocomplete so the "invisible add" (apply a tag whose badge the
// filter then hides) cannot happen. The exclusion only reaches the suggestion list: a tag typed in
// full and committed with Return still goes to onTagAdd, and its badge is then hidden.

const NOOP = () => {};

function quote(): QuoteResponse {
  return {
    dom_id: "q-p1-26",
    text: "The navigation was hidden behind a hamburger menu",
    verbatim_excerpt: "The navigation was hidden",
    participant_id: "p1",
    session_id: "s1",
    speaker_name: "Alice",
    start_timecode: 26,
    end_timecode: 35,
    sentiment: null,
    intensity: 1,
    researcher_context: null,
    quote_type: "screen_specific",
    topic_label: "Dashboard",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 3,
  };
}

function renderCard(onTagAdd: (domId: string, name: string) => void) {
  const q = quote();
  return render(
    <QuoteCard
      quote={q}
      displayText={q.text}
      isStarred={false}
      isHidden={false}
      userTags={[]}
      allTagNames={[]}
      disabledTagNames={new Set(["wayfinding"])}
      deletedBadges={[]}
      isEdited={false}
      tagVocabulary={["wayfinding", "friction"]}
      sessionId="s1"
      hasMedia={false}
      hasModerator={true}
      proposedTags={[]}
      flashingTags={new Set()}
      moderatorQuestion={null}
      isQuestionOpen={false}
      isPillVisible={false}
      onToggleStar={NOOP}
      onToggleHide={NOOP}
      onEditCommit={NOOP}
      onTagAdd={onTagAdd}
      onTagRemove={NOOP}
      onBadgeDelete={NOOP}
      onBadgeRestore={NOOP}
      onProposedAccept={NOOP}
      onProposedDeny={NOOP}
      onToggleQuestion={NOOP}
      onQuoteHoverEnter={NOOP}
      onQuoteHoverLeave={NOOP}
      onPillHoverEnter={NOOP}
      onPillHoverLeave={NOOP}
    />,
  );
}

async function typeTag(text: string) {
  fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-add-tag"));
  const input = document.querySelector("input.tag-input") as HTMLInputElement;
  await userEvent.type(input, `${text}{Enter}`);
}

describe("QuoteCard tag input: a switched-off codebook's tag (N189)", () => {
  it("does not offer it as a suggestion (shipped: off means off for the dropdown)", async () => {
    renderCard(vi.fn());
    fireEvent.click(screen.getByTestId("bn-quote-q-p1-26-add-tag"));
    await userEvent.type(document.querySelector("input.tag-input") as HTMLInputElement, "way");
    expect(document.querySelector(".tag-suggest")).toBeNull();
  });

  it("adds a tag from a codebook that is on (control)", async () => {
    const onTagAdd = vi.fn();
    renderCard(onTagAdd);
    await typeTag("friction");
    expect(onTagAdd).toHaveBeenCalledWith("q-p1-26", "friction");
  });

  // Strict pin, owner ruling needed (decisions-pending): typing the whole name and pressing Return
  // still applies the tag. Remove `.fails` when the ruling is built.
  it.fails("does not apply it when its whole name is typed and Return is pressed", async () => {
    const onTagAdd = vi.fn();
    renderCard(onTagAdd);
    await typeTag("wayfinding");
    expect(onTagAdd).not.toHaveBeenCalled();
  });
});
