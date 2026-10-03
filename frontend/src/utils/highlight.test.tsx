import { render } from "@testing-library/react";
import { highlightText } from "./highlight";

describe("highlightText", () => {
  it("returns plain string when query is empty", () => {
    expect(highlightText("Hello world", "")).toBe("Hello world");
  });

  it("returns plain string for a one-character query", () => {
    expect(highlightText("Hello world", "H")).toBe("Hello world");
  });

  it("marks a two-character query where it starts a word", () => {
    const { container } = render(<>{highlightText("Hello world", "He")}</>);
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual(["He"]);
  });

  it("does not mark inside a word", () => {
    expect(highlightText("Hello world", "lo")).toBe("Hello world");
  });

  it("marks words typed together as one run, and nothing when they are out of order", () => {
    const { container } = render(<>{highlightText("more than the shelf", "than the")}</>);
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual(["than the"]);
    expect(container.textContent).toBe("more than the shelf");
    const out = render(<>{highlightText("more than the shelf", "shelf more")}</>);
    expect(out.container.querySelectorAll("mark")).toHaveLength(0);
  });

  it("marks a quoted phrase whole", () => {
    const { container } = render(<>{highlightText("more than the shelf", '"than the"')}</>);
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual(["than the"]);
  });

  it("marks the accented original when the query has no accent", () => {
    const { container } = render(<>{highlightText("José said no", "jose")}</>);
    expect(container.querySelector("mark")?.textContent).toBe("José");
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
