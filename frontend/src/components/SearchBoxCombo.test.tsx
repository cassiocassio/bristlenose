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
  render(<SearchBox value={value} onChange={onChange} onClear={onClear} combo={combo} data-testid="s" />);
  const input = screen.getByTestId("s-input") as HTMLInputElement;
  return { combo, onChange, onClear, input };
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
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(combo.onChoose).toHaveBeenCalledWith("person:p3");
    expect(input.value).toBe("");
    expect(screen.queryByRole("listbox")).toBeNull();
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
    expect(combo.onChoose).not.toHaveBeenCalled();
    expect(screen.getByRole("listbox")).toBeInTheDocument();
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
    expect(chips[1]).toHaveAttribute("aria-label", "Tagged “Zoning”");
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

  it("Esc with tokens and no text empties the field", () => {
    const { input, onClear } = setup(tokens, "");
    act(() => input.focus());
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
