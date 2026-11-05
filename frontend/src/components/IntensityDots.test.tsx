import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { IntensityDots } from "./IntensityDots";

const radii = (container: HTMLElement) =>
  [...container.querySelectorAll("circle")].map((c) => Number(c.getAttribute("r")));
const centres = (svg: Element) =>
  [...svg.querySelectorAll("circle")].map((c) => Number(c.getAttribute("cx")));
// Which of the three circles are drawn at full strength (the rest are ghosts).
const filled = (container: HTMLElement) =>
  [...container.querySelectorAll("circle")].map((c) => c.getAttribute("opacity") === "0.8");

describe("IntensityDots", () => {
  it("draws three circles that grow, at the chart's radii for m", () => {
    const { container } = render(<IntensityDots value={2} />);
    expect(radii(container)).toEqual([3.8, 4.6, 5.4]);
    expect(container.querySelector("svg")?.getAttribute("data-size")).toBe("m");
  });

  it("puts the centres on one line at an equal pitch, so the tangents run to a point", () => {
    const svg = render(<IntensityDots value={3} />).container.querySelector("svg")!;
    const cys = [...svg.querySelectorAll("circle")].map((c) => c.getAttribute("cy"));
    expect(new Set(cys).size).toBe(1);
    const [a, b, c] = centres(svg);
    expect(b - a).toBeCloseTo(c - b);
    // Radius is linear in position: the middle radius is the mean of the outer two.
    const [r1, r2, r3] = radii(svg.parentElement as HTMLElement);
    expect(r2).toBeCloseTo((r1 + r3) / 2);
  });

  it("draws the paragraph size 5% smaller in radius, in the same box and on the same centre line", () => {
    const m = render(<IntensityDots value={2} size="m" />).container.querySelector("svg")!;
    const s = render(<IntensityDots value={2} size="s" />).container.querySelector("svg")!;
    const rs = radii(s.parentElement as HTMLElement);
    [3.8, 4.6, 5.4].forEach((r, i) => expect(rs[i]).toBeCloseTo(r * 0.95));
    expect(s.getAttribute("width")).toBe(m.getAttribute("width"));
    expect(s.getAttribute("height")).toBe(m.getAttribute("height"));
    expect(s.querySelector("circle")?.getAttribute("cy")).toBe(m.querySelector("circle")?.getAttribute("cy"));
  });

  it("draws from the left edge for the chart and from the right edge for the paragraph", () => {
    const m = render(<IntensityDots value={3} size="m" />).container.querySelector("svg")!;
    const s = render(<IntensityDots value={3} size="s" />).container.querySelector("svg")!;
    const w = Number(m.getAttribute("width"));
    const mc = [...m.querySelectorAll("circle")];
    const sc = [...s.querySelectorAll("circle")];
    const mLeft = Number(mc[0].getAttribute("cx")) - Number(mc[0].getAttribute("r"));
    const sRight = Number(sc[2].getAttribute("cx")) + Number(sc[2].getAttribute("r"));
    // Flush to the edge it is drawn from, with one unit of clear space.
    expect(mLeft).toBeCloseTo(1, 1);
    expect(sRight).toBeCloseTo(w - 1, 1);
    // Neither overflows the box.
    for (const c of [...mc, ...sc]) {
      const cx = Number(c.getAttribute("cx"));
      const r = Number(c.getAttribute("r"));
      expect(cx - r).toBeGreaterThanOrEqual(0);
      expect(cx + r).toBeLessThanOrEqual(w);
    }
  });

  it("fills a circle per whole step and leaves the rest as ghosts, always three circles", () => {
    for (const [v, want] of [[1, [true, false, false]], [2, [true, true, false]], [3, [true, true, true]]] as const) {
      const c = render(<IntensityDots value={v} />).container;
      expect(radii(c).length).toBe(3);
      expect(filled(c)).toEqual(want);
    }
  });

  it("half-fills a half step: a ghost circle with its left half filled over it", () => {
    const half = render(<IntensityDots value={1.5} />).container;
    expect(half.querySelectorAll("clipPath").length).toBe(1);
    // Circle 1 filled, circle 2 a ghost plus a clipped fill, circle 3 a ghost: four circles.
    expect(radii(half).length).toBe(4);
    const clipped = [...half.querySelectorAll("circle")].filter((c) => c.getAttribute("clip-path"));
    expect(clipped.length).toBe(1);
    expect(Number(clipped[0].getAttribute("r"))).toBeCloseTo(4.6);
  });
});
