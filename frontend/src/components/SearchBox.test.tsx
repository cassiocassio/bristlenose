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

  it("adds has-query class when query >= 3 chars", () => {
    const { getByTestId } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    fireEvent.change(getByTestId("search-input"), { target: { value: "abc" } });
    expect(getByTestId("search").classList.contains("has-query")).toBe(true);
  });

  it("does not add has-query class when query < 3 chars", () => {
    const { getByTestId } = render(
      <SearchBox value="" onChange={vi.fn()} data-testid="search" />,
    );
    fireEvent.click(getByTestId("search-toggle"));
    fireEvent.change(getByTestId("search-input"), { target: { value: "ab" } });
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
