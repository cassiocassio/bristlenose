import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JourneyChain } from "./JourneyChain";

describe("JourneyChain", () => {
  it("renders nothing when labels is empty", () => {
    const { container } = render(<JourneyChain labels={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders a single label without separator", () => {
    render(<JourneyChain labels={["Onboarding"]} data-testid="jc" />);
    const el = screen.getByTestId("jc");
    expect(el.textContent).toBe("Onboarding");
    expect(el.querySelectorAll(".bn-journey-sep")).toHaveLength(0);
  });

  it("renders multiple labels with arrow separators", () => {
    render(
      <JourneyChain
        labels={["Onboarding", "Dashboard", "Checkout"]}
        data-testid="jc"
      />,
    );
    const el = screen.getByTestId("jc");
    expect(el.textContent).toBe("Onboarding \u2192 Dashboard \u2192 Checkout");
  });

  it("uses the default bn-session-journey class", () => {
    render(<JourneyChain labels={["A"]} data-testid="jc" />);
    expect(screen.getByTestId("jc").className).toBe("bn-session-journey");
  });

  it("appends custom className", () => {
    render(
      <JourneyChain labels={["A"]} className="custom" data-testid="jc" />,
    );
    expect(screen.getByTestId("jc").className).toBe(
      "bn-session-journey custom",
    );
  });

  it("supports custom separator", () => {
    render(
      <JourneyChain
        labels={["A", "B"]}
        separator=" | "
        data-testid="jc"
      />,
    );
    expect(screen.getByTestId("jc").textContent).toBe("A | B");
  });

  it("marks separators as aria-hidden", () => {
    render(
      <JourneyChain labels={["A", "B", "C"]} data-testid="jc" />,
    );
    const seps = screen.getByTestId("jc").querySelectorAll(".bn-journey-sep");
    expect(seps).toHaveLength(2);
    seps.forEach((sep) => {
      expect(sep.getAttribute("aria-hidden")).toBe("true");
    });
  });

  it("wraps each label in a bn-journey-label span", () => {
    render(
      <JourneyChain labels={["X", "Y"]} data-testid="jc" />,
    );
    const labels = screen.getByTestId("jc").querySelectorAll(".bn-journey-label");
    expect(labels).toHaveLength(2);
    expect(labels[0].textContent).toBe("X");
    expect(labels[1].textContent).toBe("Y");
  });
});
