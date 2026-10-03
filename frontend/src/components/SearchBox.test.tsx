import { render, fireEvent, act } from "@testing-library/react";
import { SearchBox } from "./SearchBox";

describe("SearchBox", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders collapsed by default when value is empty", () => {
    const { getByTestId } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    expect(getByTestId("search").classList.contains("expanded")).toBe(false);
  });

  it("renders expanded when value is non-empty", () => {
    const { getByTestId } = render(
      <SearchBox value="hello" onChange={vi.fn()} data-testid="search" />,
    );
    expect(getByTestId("search").classList.contains("expanded")).toBe(true);
  });

  it("expands on toggle click", () => {
    const { getByTestId } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    expect(getByTestId("search").classList.contains("expanded")).toBe(true);
  });

  it("collapses and clears on toggle click when expanded", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(
      <SearchBox value="test" onChange={onChange} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    expect(getByTestId("search").classList.contains("expanded")).toBe(false);
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("debounces input changes", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(
      <SearchBox value="" onChange={onChange} debounce={150} data-testid="search" />,
    );

    // Expand first
    fireEvent.click(getByTestId("search-toggle"));

    // Type into input
    fireEvent.change(getByTestId("search-input"), { target: { value: "test" } });

    // Not called yet (debounce)
    expect(onChange).not.toHaveBeenCalled();

    // Advance past debounce
    act(() => vi.advanceTimersByTime(150));
    expect(onChange).toHaveBeenCalledWith("test");
  });

  it("clears on clear button click", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(
      <SearchBox value="hello" onChange={onChange} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-clear"));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("ⓧ and Esc clear the whole search through onClear when it is given", () => {
    const onChange = vi.fn();
    const onClear = vi.fn();
    const { getByTestId } = render(
      <SearchBox value="hello" onChange={onChange} onClear={onClear} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-clear"));
    expect(onClear).toHaveBeenCalledTimes(1);
    expect(onChange).not.toHaveBeenCalledWith("");

    // Esc in the field, with text in it, goes the same way.
    const input = getByTestId("search").querySelector("input")!;
    fireEvent.change(input, { target: { value: "late" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClear).toHaveBeenCalledTimes(2);
  });

  it("re-reads the store's value when syncKey changes, even if the value did not", () => {
    const onChange = vi.fn();
    const { getByTestId, rerender } = render(
      <SearchBox value="" onChange={onChange} syncKey={1} data-testid="search" />,
    );
    const input = getByTestId("search").querySelector("input")!;
    fireEvent.change(input, { target: { value: "p3 " } });
    expect(input.value).toBe("p3 ");
    // The store took "p3 " as a token: its query is "" again, as before.
    rerender(<SearchBox value="" onChange={onChange} syncKey={2} data-testid="search" />);
    expect(input.value).toBe("");
  });

  it("adds has-query class once the query is long enough to filter by (2 chars)", () => {
    const { getByTestId } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    fireEvent.change(getByTestId("search-input"), { target: { value: "ab" } });
    expect(getByTestId("search").classList.contains("has-query")).toBe(true);
  });

  it("does not add has-query class for one character", () => {
    const { getByTestId } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    fireEvent.change(getByTestId("search-input"), { target: { value: "a" } });
    expect(getByTestId("search").classList.contains("has-query")).toBe(false);
  });

  it("Escape clears query when input has text", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(
      <SearchBox value="" onChange={onChange} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    fireEvent.change(getByTestId("search-input"), { target: { value: "test" } });
    fireEvent.keyDown(getByTestId("search-input"), { key: "Escape" });
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("Escape collapses when input is empty", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(
      <SearchBox value="" onChange={onChange} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    expect(getByTestId("search").classList.contains("expanded")).toBe(true);
    fireEvent.keyDown(getByTestId("search-input"), { key: "Escape" });
    expect(getByTestId("search").classList.contains("expanded")).toBe(false);
  });

  it("syncs local value when parent value changes", () => {
    const { getByTestId, rerender } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    rerender(<SearchBox value="new" onChange={vi.fn()} data-testid="search" />);
    expect((getByTestId("search-input") as HTMLInputElement).value).toBe("new");
  });
});
