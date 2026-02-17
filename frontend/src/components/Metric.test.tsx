import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Metric } from "./Metric";
import type { MetricViz } from "./Metric";

describe("Metric", () => {
  // ── Rendering structure ───────────────────────────────────────

  it("renders label, value, and viz spans", () => {
    render(
      <Metric
        label="Signal strength:"
        displayValue="2.45"
        viz={{ type: "none" }}
        data-testid="m"
      />,
    );
    expect(screen.getByTestId("m-label").textContent).toBe("Signal strength:");
    expect(screen.getByTestId("m-value").textContent).toBe("2.45");
    expect(screen.getByTestId("m-viz")).toBeDefined();
  });

  it("renders title tooltip on label", () => {
    render(
      <Metric
        label="Concentration:"
        title="Times overrepresented"
        displayValue="3.1\u00d7"
        viz={{ type: "none" }}
        data-testid="m"
      />,
    );
    expect(screen.getByTestId("m-label").getAttribute("title")).toBe(
      "Times overrepresented",
    );
  });

  it("uses metric-label and metric-value CSS classes", () => {
    render(
      <Metric
        label="L"
        displayValue="V"
        viz={{ type: "none" }}
        data-testid="m"
      />,
    );
    expect(screen.getByTestId("m-label").className).toBe("metric-label");
    expect(screen.getByTestId("m-value").className).toBe("metric-value");
    expect(screen.getByTestId("m-viz").className).toBe("metric-viz");
  });

  // ── Bar visualization ─────────────────────────────────────────

  it("renders a bar with correct fill width", () => {
    const { container } = render(
      <Metric
        label="Concentration:"
        displayValue="3.1\u00d7"
        viz={{ type: "bar", percentage: 38 }}
        data-testid="m"
      />,
    );
    const fill = container.querySelector(".conc-bar-fill") as HTMLElement;
    expect(fill).not.toBeNull();
    expect(fill.style.width).toBe("38%");
  });

  it("clamps bar percentage to 0–100", () => {
    const { container: c1 } = render(
      <Metric label="L" displayValue="V" viz={{ type: "bar", percentage: 150 }} />,
    );
    expect((c1.querySelector(".conc-bar-fill") as HTMLElement).style.width).toBe("100%");

    const { container: c2 } = render(
      <Metric label="L" displayValue="V" viz={{ type: "bar", percentage: -10 }} />,
    );
    expect((c2.querySelector(".conc-bar-fill") as HTMLElement).style.width).toBe("0%");
  });

  it("renders bar track with correct class", () => {
    const { container } = render(
      <Metric label="L" displayValue="V" viz={{ type: "bar", percentage: 50 }} />,
    );
    expect(container.querySelector(".conc-bar-track")).not.toBeNull();
  });

  // ── Dots visualization ────────────────────────────────────────

  it("renders intensity dots SVG", () => {
    render(
      <Metric
        label="Intensity:"
        displayValue="2.5"
        viz={{ type: "dots", value: 2.5 }}
        data-testid="m"
      />,
    );
    const svg = screen.getByTestId("bn-metric-dots");
    expect(svg.tagName.toLowerCase()).toBe("svg");
    expect(svg.classList.contains("intensity-dots-svg")).toBe(true);
  });

  it("renders 3 dot groups for intensity dots", () => {
    const { container } = render(
      <Metric label="L" displayValue="V" viz={{ type: "dots", value: 2 }} />,
    );
    const circles = container.querySelectorAll("circle");
    // value=2 → dot 1 filled (1 circle), dot 2 filled (1 circle), dot 3 empty (1 circle)
    expect(circles.length).toBe(3);
  });

  it("renders half-filled dots for fractional values", () => {
    const { container } = render(
      <Metric label="L" displayValue="V" viz={{ type: "dots", value: 1.5 }} />,
    );
    // value=1.5 → dot 1 filled (1), dot 2 half (3 circles + clipPaths), dot 3 empty (1)
    const clipPaths = container.querySelectorAll("clipPath");
    expect(clipPaths.length).toBe(2); // left and right clips for the half dot
  });

  it("renders all empty dots for value 0", () => {
    const { container } = render(
      <Metric label="L" displayValue="V" viz={{ type: "dots", value: 0 }} />,
    );
    const circles = container.querySelectorAll("circle");
    // All 3 empty — each is one circle with stroke only
    expect(circles.length).toBe(3);
    circles.forEach((c) => {
      expect(c.getAttribute("fill")).toBe("none");
    });
  });

  it("renders all filled dots for value 3", () => {
    const { container } = render(
      <Metric label="L" displayValue="V" viz={{ type: "dots", value: 3 }} />,
    );
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBe(3);
    circles.forEach((c) => {
      expect(c.getAttribute("fill")).not.toBe("none");
      expect(c.getAttribute("opacity")).toBe("0.7");
    });
  });

  // ── None visualization ────────────────────────────────────────

  it("renders empty viz span for type none", () => {
    render(
      <Metric label="L" displayValue="V" viz={{ type: "none" }} data-testid="m" />,
    );
    const viz = screen.getByTestId("m-viz");
    expect(viz.children).toHaveLength(0);
  });

  // ── Type safety ───────────────────────────────────────────────

  it("accepts all three viz types", () => {
    const vizzes: MetricViz[] = [
      { type: "none" },
      { type: "bar", percentage: 50 },
      { type: "dots", value: 2 },
    ];
    vizzes.forEach((viz) => {
      const { unmount } = render(
        <Metric label="L" displayValue="V" viz={viz} />,
      );
      unmount();
    });
  });
});
