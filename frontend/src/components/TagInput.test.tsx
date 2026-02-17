import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagInput } from "./TagInput";

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

  it("max 8 suggestions shown by default", async () => {
    const bigVocab = Array.from({ length: 12 }, (_, i) => `a-tag-${i}`);
    const { container } = render(
      <TagInput vocabulary={bigVocab} onCommit={vi.fn()} onCancel={vi.fn()} />,
    );
    await userEvent.type(screen.getByPlaceholderText("tag"), "a");
    const items = container.querySelectorAll(".tag-suggest-item");
    expect(items).toHaveLength(8);
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
});
