import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { IntensityDots } from "./IntensityDots";

const radii = (container: HTMLElement) =>
  [...container.querySelectorAll("circle")].map((c) => Number(c.getAttribute("r")));

describe("IntensityDots", () => {
  it("draws three circles, m at the chart's radius", () => {
    const { container } = render(<IntensityDots value={2} />);
    expect(radii(container)).toEqual([5, 5, 5]);
    expect(container.querySelector("svg")?.getAttribute("data-size")).toBe("m");
  });

  it("draws the paragraph size 5% smaller in radius, on the same centre line and width", () => {
    const m = render(<IntensityDots value={2} size="m" />).container.querySelector("svg")!;
    const s = render(<IntensityDots value={2} size="s" />).container.querySelector("svg")!;
    expect(radii(s.parentElement as HTMLElement)).toEqual([4.75, 4.75, 4.75]);
    expect(4.75 / 5).toBeCloseTo(0.95);
    // Both sizes occupy the same box and sit on the same centre line, so they share a baseline.
    expect(s.getAttribute("width")).toBe(m.getAttribute("width"));
    expect(s.getAttribute("height")).toBe(m.getAttribute("height"));
    expect(s.querySelector("circle")?.getAttribute("cy")).toBe(m.querySelector("circle")?.getAttribute("cy"));
  });

  it("fills a circle per whole step and half-fills a half step", () => {
    const whole = render(<IntensityDots value={2} />).container;
    expect([...whole.querySelectorAll("circle")].map((c) => c.getAttribute("fill") !== "none"))
      .toEqual([true, true, false]);
    const half = render(<IntensityDots value={1.5} />).container;
    // Two full-size circles are clipped halves of the second dot.
    expect(half.querySelectorAll("clipPath").length).toBe(2);
  });
});
