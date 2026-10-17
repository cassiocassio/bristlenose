import { describe, expect, it } from "vitest";
import { keylinePath } from "./useGutterHover";

/** An element whose line boxes are the rects given (jsdom lays nothing out). */
function el(rects: { left: number; right: number; top: number; bottom: number }[]): HTMLElement {
  const e = document.createElement("span");
  e.getClientRects = () => rects.map((r) => ({ ...r, width: r.right - r.left, height: r.bottom - r.top })) as unknown as DOMRectList;
  return e;
}
const rect = (left: number, top: number, right: number, bottom: number) => ({ left, top, right, bottom }) as DOMRect;

describe("keylinePath", () => {
  const column = rect(100, 0, 500, 200);
  const origin = rect(0, 0, 1000, 1000);

  it("draws one line as a box padded round the words", () => {
    expect(keylinePath([el([{ left: 200, right: 300, top: 10, bottom: 30 }])], column, origin))
      .toBe("M196.25,8.25 H304.25 V32.25 H196.25 Z");
  });

  it("draws a quote over three lines as one block, notched where it starts and ends", () => {
    // Starts mid-line, runs a full line, ends mid-line: the middle line and the block's straight
    // edges run the column's measure; only the first line's start and the last line's end notch it.
    const d = keylinePath(
      [el([{ left: 300, right: 480, top: 10, bottom: 30 }, { left: 100, right: 470, top: 32, bottom: 52 },
        { left: 100, right: 250, top: 54, bottom: 74 }])],
      column, origin,
    );
    expect(d).toBe("M296.25,8.25 H504.25 V31.25 H504.25 V53.25 H254.25 V76.25 H96.25 V53.25 H96.25 V31.25 H296.25 Z");
  });

  it("joins the words of one line drawn as several spans", () => {
    const d = keylinePath(
      [el([{ left: 200, right: 240, top: 10, bottom: 30 }]), el([{ left: 244, right: 300, top: 10, bottom: 30 }])],
      column, origin,
    );
    expect(d).toBe("M196.25,8.25 H304.25 V32.25 H196.25 Z");
  });

  it("draws nothing for nothing laid out", () => {
    expect(keylinePath([el([])], column, origin)).toBe("");
  });
});
