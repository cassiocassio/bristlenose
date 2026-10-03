/**
 * The search field as a combobox (docs/design-search.md §4–§6): the list
 * opens on typing, the keys move and choose, tokens are chips with a meaning
 * menu, and ⌫ / Esc behave as on the Mac. Driven through the DOM as a user
 * would, with the labels the real searchBridge builds.
 */
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SearchBox, type SearchCombo } from "./SearchBox";
import { personToken, tagToken, type SearchToken } from "../utils/searchTokens";
import type { Suggestion } from "../utils/searchSuggest";

const tag = { name: "Zoning", codebook_group: "g", colour_set: "ux", colour_index: 1 };
const rows: Suggestion[] = [
  { kind: "text", id: "text", query: "zo", count: 4 },
  { kind: "person", id: "person:p3", code: "p3", name: "Zoë Ng", count: 2 },
  { kind: "tag", id: "tag:zoning", tag, count: 1 },
];

function setup(tokens: SearchToken[] = [], value = "") {
  const combo: SearchCombo = {
    tokens,
    suggestions: rows,
    tagColour: () => ({ colourSet: "ux", colourIndex: 1 }),
    onChoose: vi.fn(),
    onTokenMode: vi.fn(),
    onTokenRemove: vi.fn(),
  };
  const onChange = vi.fn();
  const onClear = vi.fn();
  // The store echoes the committed query back as `value`, as the real one does.
  function Echoing() {
    const [v, setV] = useState(value);
    return (
      <SearchBox
        value={v}
        onChange={(q) => {
          onChange(q);
          setV(q);
        }}
        onClear={onClear}
        combo={combo}
        data-testid="s"
      />
    );
  }
  render(<Echoing />);
  const input = screen.getByTestId("s-input") as HTMLInputElement;
  return { combo, onChange, onClear, input };
}

/** Let the debounce send what was typed, so the rows are the query's. */
function settle() {
  act(() => vi.advanceTimersByTime(200));
}

/** Focus and type, as a user does: the list opens only on an edit. */
function type(input: HTMLInputElement, text: string) {
  act(() => input.focus());
  fireEvent.change(input, { target: { value: text } });
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("the suggestions list", () => {
  it("stays closed until the researcher types, then opens with the free text highlighted", () => {
    const { input } = setup([], "zo");
    act(() => input.focus());
    expect(screen.queryByRole("listbox")).toBeNull(); // text the store put back
    type(input, "zoo");
    const list = screen.getByRole("listbox");
    const options = within(list).getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("role", "combobox");
    expect(input).toHaveAttribute("aria-expanded", "true");
    expect(input.getAttribute("aria-activedescendant")).toBe(options[0].id);
  });

  it("groups people and tags for screen readers", () => {
    const { input } = setup();
    type(input, "zo");
    expect(screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"))).toEqual(["People", "Tags"]);
  });

  it("↓ ↩ chooses a person, which becomes a token and clears the text", () => {
    const { input, combo } = setup();
    type(input, "zo");
    settle();
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(combo.onChoose).toHaveBeenCalledWith("person:p3");
    expect(input.value).toBe("");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("names each row by its label and count, a person with their code", () => {
    const { input } = setup();
    type(input, "zo");
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-label", "p3 Zoë Ng, 2");
  });

  it("within the debounce, ↓ sends the text now and ↩ never chooses a row from the last query", () => {
    const { input, combo, onChange } = setup([], "z");
    type(input, "zo"); // the rows on screen are still for "z"
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(onChange).toHaveBeenCalledWith("zo");
    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");
    type(input, "zon");
    fireEvent.keyDown(input, { key: "ArrowDown" }); // sends "zon"
    fireEvent.keyDown(input, { key: "ArrowDown" }); // now moves
    type(input, "zone"); // stale again, with a person highlighted
    fireEvent.keyDown(input, { key: "Enter" });
    expect(combo.onChoose).not.toHaveBeenCalled();
    expect(onChange).toHaveBeenLastCalledWith("zone");
  });

  it("↩ on the free text commits the query now, without the debounce wait", () => {
    const { input, onChange } = setup([], "");
    type(input, "zo");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("zo");
  });

  it("a click on a row chooses it, and a mousedown does not take the focus from the field", () => {
    const { input, combo } = setup();
    type(input, "zo");
    const tagRow = screen.getAllByRole("option")[2];
    const down = fireEvent.mouseDown(tagRow);
    expect(down).toBe(false); // default prevented: the input keeps focus
    fireEvent.click(tagRow);
    expect(combo.onChoose).toHaveBeenCalledWith("tag:zoning");
  });

  it("Esc closes the list first, then empties the field", () => {
    const { input, onClear } = setup();
    type(input, "zo");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(onClear).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("leaves the keys to an input method that is composing", () => {
    const { input, combo } = setup();
    type(input, "zo");
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    // Safari's confirming ↩ arrives after compositionend, marked only by 229.
    fireEvent.keyDown(input, { key: "Enter", keyCode: 229 });
    expect(combo.onChoose).not.toHaveBeenCalled();
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("opens the field when it takes the focus, however the focus arrived", () => {
    // The `/` shortcut focuses the input from outside React; typing must not
    // then collapse the field under the cursor.
    setup();
    const container = screen.getByTestId("s");
    const input = screen.getByTestId("s-input") as HTMLInputElement;
    expect(container).not.toHaveClass("expanded");
    type(input, "zo");
    expect(container).toHaveClass("expanded");
  });
});

describe("with a store that echoes the query, as the real one does", () => {
  function Echoing({ combo }: { combo: SearchCombo }) {
    const [value, setValue] = useState("");
    return <SearchBox value={value} onChange={setValue} combo={combo} data-testid="s" />;
  }

  it("the debounced echo of what was typed keeps the list open", () => {
    const combo: SearchCombo = {
      tokens: [], suggestions: rows, tagColour: () => null,
      onChoose: vi.fn(), onTokenMode: vi.fn(), onTokenRemove: vi.fn(),
    };
    render(<Echoing combo={combo} />);
    const input = screen.getByTestId("s-input") as HTMLInputElement;
    type(input, "zo");
    act(() => vi.advanceTimersByTime(200)); // the debounce fires, the store echoes "zo"
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });
});

describe("tokens", () => {
  const tokens = [personToken("p3", { full_name: "Zoë Ng", short_name: "Zoë" }), tagToken({ name: "Zoning" })];

  it("draw as chips: the meaning word, the badge, ▾", () => {
    setup(tokens, "");
    const chips = screen.getAllByTestId("s-token");
    expect(chips[0]).toHaveTextContent("said by");
    expect(chips[0]).toHaveTextContent("p3");
    expect(chips[0]).toHaveTextContent("Zoë Ng");
    expect(chips[1]).toHaveTextContent("tagged");
    // Named by what it shows, so a Voice Control user can say the code.
    expect(chips[0]).not.toHaveAttribute("aria-label");
  });

  it("a chip's menu changes the meaning, or removes the token", () => {
    const { combo } = setup(tokens, "");
    fireEvent.click(screen.getAllByTestId("s-token")[1]);
    const menu = screen.getByRole("menu");
    const items = within(menu).getAllByRole("menuitemradio");
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["true", "false", "false"]);
    fireEvent.click(items[2]);
    expect(combo.onTokenMode).toHaveBeenCalledWith(tokens[1], "not");
    expect(screen.queryByRole("menu")).toBeNull();
    fireEvent.click(screen.getAllByTestId("s-token")[0]);
    fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem"));
    expect(combo.onTokenRemove).toHaveBeenCalledWith(tokens[0]);
  });

  it("a chip's menu works from the keyboard: focus moves in, arrows cycle, Esc returns to the chip", () => {
    const { combo } = setup(tokens, "");
    const chip = screen.getAllByTestId("s-token")[1];
    act(() => chip.focus());
    fireEvent.click(chip); // Enter or Space on a button clicks it
    const menu = screen.getByRole("menu");
    const items = within(menu).getAllByRole("menuitemradio");
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(menu, { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(menu, { key: "ArrowUp" });
    fireEvent.keyDown(menu, { key: "ArrowUp" }); // wraps past the first to Remove
    expect(document.activeElement).toBe(within(menu).getByRole("menuitem"));
    fireEvent.keyDown(document.activeElement!, { key: "Enter" });
    expect(combo.onTokenRemove).toHaveBeenCalledWith(tokens[1]);
    act(() => vi.advanceTimersByTime(20));
    expect(document.activeElement).not.toBe(document.body); // never dropped to the page
    fireEvent.click(chip);
    fireEvent.keyDown(screen.getByRole("menu"), { key: "End" });
    expect(document.activeElement).toBe(within(screen.getByRole("menu")).getByRole("menuitem"));
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Home" });
    fireEvent.keyDown(document.activeElement!, { key: "Enter" }); // choose a meaning
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(chip);
    fireEvent.click(chip);
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(chip);
  });

  it("keys on a chip or in its menu never reach the report's shortcuts", () => {
    setup(tokens, "");
    const seen = vi.fn();
    document.addEventListener("keydown", seen);
    try {
      const chip = screen.getAllByTestId("s-token")[0];
      fireEvent.keyDown(chip, { key: "Enter" });
      fireEvent.keyDown(chip, { key: "s" });
      fireEvent.click(chip);
      const menu = screen.getByRole("menu");
      expect(menu).toHaveAttribute("aria-labelledby", chip.id);
      fireEvent.keyDown(document.activeElement!, { key: "s" });
      fireEvent.keyDown(document.activeElement!, { key: "Enter" });
      expect(seen).not.toHaveBeenCalled();
    } finally {
      document.removeEventListener("keydown", seen);
    }
  });

  it("⌫ in the empty field selects the last chip, and a second ⌫ removes it", () => {
    const { input, combo } = setup(tokens, "");
    act(() => input.focus());
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(screen.getAllByTestId("s-token")[1]).toHaveClass("selected");
    expect(combo.onTokenRemove).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Backspace", repeat: true }); // a held key does not count
    expect(combo.onTokenRemove).not.toHaveBeenCalled();
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(combo.onTokenRemove).toHaveBeenCalledWith(tokens[1]);
  });

  it("removing the last chip from a focused field leaves the field open", () => {
    const combo = (t: SearchToken[]): SearchCombo => ({
      tokens: t, suggestions: [], tagColour: () => null,
      onChoose: vi.fn(), onTokenMode: vi.fn(), onTokenRemove: vi.fn(),
    });
    const { rerender } = render(<SearchBox value="" onChange={vi.fn()} combo={combo(tokens)} data-testid="s" />);
    act(() => (screen.getByTestId("s-input") as HTMLInputElement).focus());
    rerender(<SearchBox value="" onChange={vi.fn()} combo={combo([])} data-testid="s" />);
    expect(screen.getByTestId("s")).toHaveClass("expanded");
  });

  it("Esc with tokens and no text empties the field", () => {
    const { input, onClear } = setup(tokens, "");
    act(() => input.focus());
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
