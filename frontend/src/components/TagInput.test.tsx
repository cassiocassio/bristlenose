import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagInput } from "./TagInput";
import type { TagVocabularyGroup } from "./TagInput";

const VOCAB = ["apple", "apricot", "banana", "blueberry", "cherry"];

describe("TagInput", () => {
  it("renders input with default placeholder", () => {
    render(<TagInput vocabulary={[]} onCommit={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByPlaceholderText("tag")).toBeInTheDocument();
  });

  it("renders custom placeholder", () => {
    render(
      <TagInput vocabulary={[]} onCommit={vi.fn()} onCancel={vi.fn()} placeholder="add tag..." />,
    );
    expect(screen.getByPlaceholderText("add tag...")).toBeInTheDocument();
  });

  it("auto-focuses on mount", () => {
    render(<TagInput vocabulary={[]} onCommit={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByPlaceholderText("tag")).toHaveFocus();
  });

  it("typing filters suggestions from vocabulary", async () => {
    const { container } = render(
      <TagInput vocabulary={VOCAB} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toBe("apple");
    expect(items[1].textContent).toBe("apricot");
  });

  it("excluded tags do not appear in suggestions", async () => {
    const { container } = render(
      <TagInput
        vocabulary={VOCAB}
        exclude={["apple"]}
        onCommit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items).toHaveLength(1);
    expect(items[0].textContent).toBe("apricot");
  });

  it("exact match does not appear in suggestions", async () => {
    const { container } = render(
      <TagInput vocabulary={VOCAB} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "apple");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items).toHaveLength(0);
  });

  it("arrow down highlights first suggestion", async () => {
    const { container } = render(
      <TagInput vocabulary={VOCAB} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    const input = screen.getByPlaceholderText("tag");
    await userEvent.type(input, "ap");
    await userEvent.keyboard("{ArrowDown}");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items[0]).toHaveClass("active");
    expect(items[1]).not.toHaveClass("active");
  });

  it("arrow down cycles through suggestions and wraps to none", async () => {
    const { container } = render(
      <TagInput vocabulary={VOCAB} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    const input = screen.getByPlaceholderText("tag");
    await userEvent.type(input, "ap");
    // Down → first, Down → second, Down → wraps to none
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items[0]).not.toHaveClass("active");
    expect(items[1]).not.toHaveClass("active");
  });

  it("arrow up highlights last suggestion from neutral", async () => {
    const { container } = render(
      <TagInput vocabulary={VOCAB} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    const input = screen.getByPlaceholderText("tag");
    await userEvent.type(input, "ap");
    await userEvent.keyboard("{ArrowUp}");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items[0]).not.toHaveClass("active");
    expect(items[1]).toHaveClass("active");
  });

  it("Enter commits current input value", async () => {
    const onCommit = vi.fn();
    render(<TagInput vocabulary={[]} onCommit={onCommit} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("tag"), "newtag");
    await userEvent.keyboard("{Enter}");
    expect(onCommit).toHaveBeenCalledWith("newtag");
  });

  it("Enter with ghost text accepts ghost first then commits", async () => {
    const onCommit = vi.fn();
    render(<TagInput vocabulary={["apple"]} onCommit={onCommit} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    await userEvent.keyboard("{Enter}");
    expect(onCommit).toHaveBeenCalledWith("apple");
  });

  it("Enter with highlighted suggestion commits that suggestion", async () => {
    const onCommit = vi.fn();
    render(<TagInput vocabulary={VOCAB} onCommit={onCommit} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(onCommit).toHaveBeenCalledWith("apricot");
  });

  it("Escape calls onCancel", async () => {
    const onCancel = vi.fn();
    render(<TagInput vocabulary={[]} onCommit={vi.fn()} onCancel={onCancel} />);
    await userEvent.type(screen.getByPlaceholderText("tag"), "something");
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("Tab commits and calls onCommitAndReopen if provided", async () => {
    const onCommitAndReopen = vi.fn();
    const onCommit = vi.fn();
    render(
      <TagInput
        vocabulary={["apple"]}
        onCommit={onCommit}
        onCancel={vi.fn()}
        onCommitAndReopen={onCommitAndReopen}
      />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    await userEvent.keyboard("{Tab}");
    expect(onCommitAndReopen).toHaveBeenCalledWith("apple");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("Tab commits via onCommit when onCommitAndReopen absent", async () => {
    const onCommit = vi.fn();
    render(<TagInput vocabulary={["apple"]} onCommit={onCommit} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    await userEvent.keyboard("{Tab}");
    expect(onCommit).toHaveBeenCalledWith("apple");
  });

  it("ArrowRight accepts ghost text", async () => {
    const { container } = render(
      <TagInput vocabulary={["apple"]} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    const input = screen.getByPlaceholderText("tag");
    await userEvent.type(input, "ap");
    // Ghost should show "ple"
    const ghost = container.querySelector(".tag-ghost");
    expect(ghost?.textContent).toBe("ple");
    await userEvent.keyboard("{ArrowRight}");
    expect(input).toHaveValue("apple");
  });

  it("click on suggestion commits it", async () => {
    const onCommit = vi.fn();
    render(<TagInput vocabulary={VOCAB} onCommit={onCommit} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    const items = document.querySelectorAll(".tag-suggest-item");
    // mouseDown on "apricot" (second item)
    fireEvent.mouseDown(items[1]);
    expect(onCommit).toHaveBeenCalledWith("apricot");
  });

  it("ghost text shows suffix of best prefix match", async () => {
    const { container } = render(
      <TagInput vocabulary={["apple", "apricot"]} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
    const ghost = container.querySelector(".tag-ghost");
    expect(ghost?.textContent).toBe("ple");
  });

  it("no ghost text when no prefix match", async () => {
    const { container } = render(
      <TagInput vocabulary={["banana"]} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    // "an" is a contains-match for "banana" but not a prefix match
    await userEvent.type(screen.getByPlaceholderText("tag"), "an");
    const ghost = container.querySelector(".tag-ghost");
    expect(ghost?.textContent).toBe("");
  });

  it("max 12 suggestions shown by default", async () => {
    const bigVocab = Array.from({ length: 16 }, (_, i) => `a-tag-${i}`);
    const { container } = render(
      <TagInput vocabulary={bigVocab} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "a");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items).toHaveLength(12);
  });

  it("forwards data-testid", () => {
    render(
      <TagInput
        vocabulary={[]}
        onCommit={vi.fn()}
        onCancel={vi.fn()}
        data-testid="my-tag-input"
      />,
    );
    expect(screen.getByTestId("my-tag-input")).toBeInTheDocument();
  });

  describe("hiddenTags eye icon", () => {
    it("shows eye icon on suggestions whose tag is in hiddenTags", async () => {
      const hidden = new Set(["apple"]);
      const { container } = render(
        <TagInput
          vocabulary={VOCAB}
          hiddenTags={hidden}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
      const items = container.querySelectorAll(".tag-suggest-item");
      // "apple" should have an eye icon, "apricot" should not.
      expect(items[0].querySelector(".tag-suggest-hidden-icon")).toBeTruthy();
      expect(items[1].querySelector(".tag-suggest-hidden-icon")).toBeNull();
    });

    it("does not show eye icon when hiddenTags is not provided", async () => {
      const { container } = render(
        <TagInput vocabulary={VOCAB} onCommit={vi.fn()} onCancel={vi.fn()} />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
      const icons = container.querySelectorAll(".tag-suggest-hidden-icon");
      expect(icons).toHaveLength(0);
    });

    it("committing a hidden tag still calls onCommit normally", async () => {
      const onCommit = vi.fn();
      const hidden = new Set(["apple"]);
      render(
        <TagInput
          vocabulary={["apple"]}
          hiddenTags={hidden}
          onCommit={onCommit}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
      await userEvent.keyboard("{Enter}");
      expect(onCommit).toHaveBeenCalledWith("apple");
    });
  });

  describe("blur behaviour", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("blur with non-empty text commits", async () => {
      const onCommit = vi.fn();
      render(<TagInput vocabulary={[]} onCommit={onCommit} onCancel={vi.fn()} />);
      const input = screen.getByPlaceholderText("tag");
      // Use fireEvent since userEvent doesn't work well with fake timers
      fireEvent.change(input, { target: { value: "hello" } });
      fireEvent.blur(input);
      vi.advanceTimersByTime(150);
      expect(onCommit).toHaveBeenCalledWith("hello");
    });

    it("blur with empty text cancels", () => {
      const onCancel = vi.fn();
      render(<TagInput vocabulary={[]} onCommit={vi.fn()} onCancel={onCancel} />);
      const input = screen.getByPlaceholderText("tag");
      fireEvent.blur(input);
      vi.advanceTimersByTime(150);
      expect(onCancel).toHaveBeenCalledOnce();
    });
  });

  // ── Grouped vocabulary tests ──────────────────────────────────────────

  describe("groupedVocabulary", () => {
    const GROUPED: TagVocabularyGroup[] = [
      {
        groupName: "Norman Principles",
        colourSet: "ux",
        tags: [
          { name: "affordance", colourIndex: 0 },
          { name: "feedback", colourIndex: 1 },
          { name: "mapping", colourIndex: 2 },
        ],
      },
      {
        groupName: "Emotion",
        colourSet: "emo",
        tags: [
          { name: "frustration", colourIndex: 0 },
          { name: "delight", colourIndex: 1 },
        ],
      },
      {
        groupName: "User Tags",
        colourSet: "",
        tags: [
          { name: "feedback loop", colourIndex: 0 },
        ],
      },
    ];

    const ALL_NAMES = [
      "affordance", "feedback", "mapping",
      "frustration", "delight", "feedback loop",
    ];

    it("renders group headers when groupedVocabulary is provided", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "f");
      const headers = container.querySelectorAll(".tag-suggest-header");
      expect(headers.length).toBeGreaterThanOrEqual(1);
      // Should show Norman Principles header (contains "feedback") and
      // Emotion header (contains "frustration") and User Tags (contains "feedback loop")
      const headerTexts = Array.from(headers).map((h) => h.textContent);
      expect(headerTexts).toContain("Norman Principles");
      expect(headerTexts).toContain("Emotion");
      expect(headerTexts).toContain("User Tags");
    });

    it("shows tags as pills inside suggestion items", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "aff");
      const pills = container.querySelectorAll(".tag-suggest-pill");
      expect(pills).toHaveLength(1);
      expect(pills[0].textContent).toBe("affordance");
    });

    it("arrow keys skip group headers", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      // "feed" matches "feedback" (Norman) and "feedback loop" (User Tags)
      await userEvent.type(screen.getByPlaceholderText("tag"), "feed");
      // First ArrowDown → first tag (feedback)
      await userEvent.keyboard("{ArrowDown}");
      const activeItems = container.querySelectorAll(".tag-suggest-item.active");
      expect(activeItems).toHaveLength(1);
      expect(activeItems[0].querySelector(".tag-suggest-pill")?.textContent).toBe("feedback");

      // No header should be active
      const activeHeaders = container.querySelectorAll(".tag-suggest-header.active");
      expect(activeHeaders).toHaveLength(0);
    });

    it("typing a group name shows all its tags", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "norman");
      // Should show all Norman Principles tags
      const pills = container.querySelectorAll(".tag-suggest-pill");
      const pillTexts = Array.from(pills).map((p) => p.textContent);
      expect(pillTexts).toContain("affordance");
      expect(pillTexts).toContain("feedback");
      expect(pillTexts).toContain("mapping");
    });

    it("Enter on highlighted grouped suggestion commits the tag name", async () => {
      const onCommit = vi.fn();
      render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={onCommit}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "del");
      await userEvent.keyboard("{ArrowDown}{Enter}");
      expect(onCommit).toHaveBeenCalledWith("delight");
    });

    it("click on grouped suggestion commits the tag name", async () => {
      const onCommit = vi.fn();
      render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={onCommit}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "del");
      const items = document.querySelectorAll(".tag-suggest-item");
      fireEvent.mouseDown(items[0]);
      expect(onCommit).toHaveBeenCalledWith("delight");
    });

    it("excludes tags from grouped suggestions", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          exclude={["feedback"]}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "feed");
      const pills = container.querySelectorAll(".tag-suggest-pill");
      const texts = Array.from(pills).map((p) => p.textContent);
      expect(texts).not.toContain("feedback");
      expect(texts).toContain("feedback loop");
    });

    it("hides groups with zero matching tags", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      // "mapp" only matches "mapping" (Norman Principles)
      await userEvent.type(screen.getByPlaceholderText("tag"), "mapp");
      const headers = container.querySelectorAll(".tag-suggest-header");
      expect(headers).toHaveLength(1);
      expect(headers[0].textContent).toBe("Norman Principles");
      // Only one tag item
      const items = container.querySelectorAll(".tag-suggest-item");
      expect(items).toHaveLength(1);
    });

    it("respects maxSuggestions across groups", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          maxSuggestions={2}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      // "f" matches: feedback (Norman), frustration (Emotion), feedback loop (User Tags)
      // With maxSuggestions=2, should only show first 2 tags
      await userEvent.type(screen.getByPlaceholderText("tag"), "f");
      const items = container.querySelectorAll(".tag-suggest-item");
      expect(items).toHaveLength(2);
    });

    it("ghost text works with grouped vocabulary", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "aff");
      const ghost = container.querySelector(".tag-ghost");
      expect(ghost?.textContent).toBe("ordance");
    });

    it("falls back to flat mode when groupedVocabulary is empty", async () => {
      const { container } = render(
        <TagInput
          vocabulary={VOCAB}
          groupedVocabulary={[]}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "ap");
      // Should work like flat mode — no headers
      const headers = container.querySelectorAll(".tag-suggest-header");
      expect(headers).toHaveLength(0);
      const items = container.querySelectorAll(".tag-suggest-item");
      expect(items).toHaveLength(2);
    });

    it("shows tag pills with background style when colourSet is provided", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      await userEvent.type(screen.getByPlaceholderText("tag"), "aff");
      const pill = container.querySelector(".tag-suggest-pill") as HTMLElement;
      expect(pill).toBeTruthy();
      // Should have a background style from getTagBg()
      expect(pill.style.background).toMatch(/var\(--bn-ux-/);
    });

    it("does not set background style on pills from groups without colourSet", async () => {
      const { container } = render(
        <TagInput
          vocabulary={ALL_NAMES}
          groupedVocabulary={GROUPED}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />,
      );
      // "feedback loop" is in "User Tags" group with colourSet=""
      await userEvent.type(screen.getByPlaceholderText("tag"), "feedback lo");
      const pills = container.querySelectorAll(".tag-suggest-pill") as NodeListOf<HTMLElement>;
      const loopPill = Array.from(pills).find((p) => p.textContent === "feedback loop");
      expect(loopPill).toBeTruthy();
      // No inline background style (empty colourSet)
      expect(loopPill!.style.background).toBe("");
    });
  });
});
