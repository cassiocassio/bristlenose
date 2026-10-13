import { describe, it, expect, vi, afterEach } from "vitest";
import { captureReadingAnchor, readerIsBusy, restoreReadingAnchor } from "./readingAnchor";

/** A transcript body whose paragraphs sit at the given tops, 100px tall. */
function body(starts: string[], tops: number[]): HTMLElement {
  const el = document.createElement("section");
  starts.forEach((start, i) => {
    const p = document.createElement("div");
    p.className = "transcript-segment";
    p.dataset.startSeconds = start;
    p.getBoundingClientRect = () => ({ top: tops[i], bottom: tops[i] + 100 }) as DOMRect;
    el.appendChild(p);
  });
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.body.innerHTML = "";
  window.getSelection()?.removeAllRanges();
  vi.restoreAllMocks();
});

describe("captureReadingAnchor", () => {
  it("takes the first paragraph not hidden under the header", () => {
    const b = body(["2", "10", "19"], [-150, -50, 50]);
    expect(captureReadingAnchor(b, 60)).toEqual({ start: "19", nth: 0, top: 50, scrollY: 0 });
    expect(captureReadingAnchor(b, 40)).toEqual({ start: "10", nth: 0, top: -50, scrollY: 0 });
  });

  it("tells apart the halves of a split, which share a start", () => {
    const b = body(["10", "10", "19"], [-150, 20, 120]);
    expect(captureReadingAnchor(b, 60)).toEqual({ start: "10", nth: 1, top: 20, scrollY: 0 });
  });

  it("has nothing to anchor in an empty transcript", () => {
    expect(captureReadingAnchor(body([], []), 0)).toBeNull();
  });
});

describe("restoreReadingAnchor", () => {
  it("scrolls by however far the paragraph moved", () => {
    const scroll = vi.spyOn(window, "scrollBy").mockImplementation(() => {});
    const b = body(["2", "10", "19"], [-110, -10, 90]); // a highlight above added 40px
    expect(restoreReadingAnchor(b, { start: "10", nth: 0, top: -50, scrollY: 0 })).toBe(40);
    expect(scroll).toHaveBeenCalledWith(0, 40);
  });

  it("does not scroll when nothing moved", () => {
    const scroll = vi.spyOn(window, "scrollBy").mockImplementation(() => {});
    const b = body(["2", "10"], [-150, -50]);
    restoreReadingAnchor(b, { start: "10", nth: 0, top: -50, scrollY: 0 });
    expect(scroll).not.toHaveBeenCalled();
  });

  it("leaves the reader's own scrolling alone", () => {
    const scroll = vi.spyOn(window, "scrollBy").mockImplementation(() => {});
    // The reader scrolled down 30px meanwhile; the paragraph moved 40px for it.
    vi.spyOn(window, "scrollY", "get").mockReturnValue(30);
    const b = body(["2", "10"], [-140, -40]);
    restoreReadingAnchor(b, { start: "10", nth: 0, top: -50, scrollY: 0 });
    expect(scroll).toHaveBeenCalledWith(0, 40);
  });

  it("falls back to the paragraph before one the re-read rebuilt", () => {
    const scroll = vi.spyOn(window, "scrollBy").mockImplementation(() => {});
    const b = body(["2", "10", "30"], [-150, 0, 100]);
    restoreReadingAnchor(b, { start: "19", nth: 0, top: -30, scrollY: 0 });
    expect(scroll).toHaveBeenCalledWith(0, 30); // the "10" paragraph, at 0
  });
});

describe("readerIsBusy", () => {
  it("is busy while text in the transcript is selected", () => {
    const b = body(["2"], [0]);
    b.firstElementChild!.textContent = "Thanks for joining.";
    const range = document.createRange();
    range.selectNodeContents(b.firstElementChild!);
    window.getSelection()!.addRange(range);
    expect(readerIsBusy(b)).toBe(true);
    window.getSelection()!.removeAllRanges();
    expect(readerIsBusy(b)).toBe(false);
  });

  it("is busy while a field has focus, and not for a selection elsewhere", () => {
    const b = body(["2"], [0]);
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    expect(readerIsBusy(b)).toBe(true);
    input.type = "checkbox"; // a focused control nobody types into
    expect(readerIsBusy(b)).toBe(false);
    input.blur();
    const outside = document.createElement("p");
    outside.textContent = "elsewhere";
    document.body.appendChild(outside);
    const range = document.createRange();
    range.selectNodeContents(outside);
    window.getSelection()!.addRange(range);
    expect(readerIsBusy(b)).toBe(false);
  });
});
