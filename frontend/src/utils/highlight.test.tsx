import { render } from "@testing-library/react";
import { highlightText } from "./highlight";

describe("highlightText", () => {
  it("returns plain string when query is empty", () => {
    expect(highlightText("Hello world", "")).toBe("Hello world");
  });

  it("returns plain string when query is shorter than 3 chars", () => {
    expect(highlightText("Hello world", "He")).toBe("Hello world");
  });

  it("returns plain string when query is exactly 2 chars", () => {
    expect(highlightText("Hello world", "lo")).toBe("Hello world");
  });

  it("returns plain string when there is no match", () => {
    const result = highlightText("Hello world", "xyz");
    expect(result).toBe("Hello world");
  });

  it("wraps a single match in <mark>", () => {
    const result = highlightText("Hello world", "world");
    const { container } = render(<>{result}</>);
    const marks = container.querySelectorAll("mark.search-mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("world");
    expect(container.textContent).toBe("Hello world");
  });

  it("wraps multiple matches", () => {
    const result = highlightText("foo bar foo baz foo", "foo");
    const { container } = render(<>{result}</>);
    const marks = container.querySelectorAll("mark.search-mark");
    expect(marks).toHaveLength(3);
  });

  it("matching is case-insensitive", () => {
    const result = highlightText("Hello World", "hello");
    const { container } = render(<>{result}</>);
    const marks = container.querySelectorAll("mark.search-mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("Hello");
  });

  it("preserves original case in highlighted text", () => {
    const result = highlightText("FoObAr", "foobar");
    const { container } = render(<>{result}</>);
    expect(container.querySelector("mark")?.textContent).toBe("FoObAr");
  });

  it("handles regex special characters in query", () => {
    const result = highlightText("price is $100 (USD)", "$100");
    const { container } = render(<>{result}</>);
    const marks = container.querySelectorAll("mark.search-mark");
    expect(marks).toHaveLength(1);
    expect(marks[0].textContent).toBe("$100");
  });

  it("handles query at start of text", () => {
    const result = highlightText("Hello world", "Hello");
    const { container } = render(<>{result}</>);
    expect(container.querySelector("mark")?.textContent).toBe("Hello");
  });

  it("handles query at end of text", () => {
    const result = highlightText("Hello world", "world");
    const { container } = render(<>{result}</>);
    expect(container.querySelector("mark")?.textContent).toBe("world");
  });

  it("handles query matching entire text", () => {
    const result = highlightText("test", "test");
    const { container } = render(<>{result}</>);
    const marks = container.querySelectorAll("mark.search-mark");
    expect(marks).toHaveLength(1);
    expect(container.textContent).toBe("test");
  });
});
