import { render, screen } from "@testing-library/react";
import { Sparkline } from "./Sparkline";
import type { SparklineItem } from "./Sparkline";

function makeItems(counts: number[]): SparklineItem[] {
  return counts.map((count, i) => ({
    key: `s${i}`,
    count,
    colour: `var(--colour-${i})`,
  }));
}

describe("Sparkline", () => {
  it("renders em-dash when all counts are zero", () => {
    const { container } = render(<Sparkline items={makeItems([0, 0, 0])} />);
    expect(container.textContent).toBe("\u2014");
  });

  it("renders em-dash for empty items array", () => {
    const { container } = render(<Sparkline items={[]} />);
    expect(container.textContent).toBe("\u2014");
  });

  it("renders custom emptyContent when all counts are zero", () => {
    render(
      <Sparkline items={makeItems([0, 0])} emptyContent={<span>No data</span>} />,
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("renders bars for non-zero items", () => {
    const { container } = render(
      <Sparkline items={makeItems([10, 5, 3])} data-testid="sp" />,
    );
    const bars = container.querySelectorAll(".bn-sparkline-bar");
    expect(bars).toHaveLength(3);
  });

  it("tallest bar gets maxHeight", () => {
    const { container } = render(
      <Sparkline items={makeItems([10, 5])} data-testid="sp" />,
    );
    const bars = container.querySelectorAll(".bn-sparkline-bar");
    expect(bars[0]).toHaveStyle({ height: "20px" });
  });

  it("non-zero bar respects minHeight", () => {
    const { container } = render(
      <Sparkline items={makeItems([100, 1])} />,
    );
    const bars = container.querySelectorAll(".bn-sparkline-bar");
    // 1/100 * 20 = 0.2 → rounded to 0, but minHeight is 2
    expect(bars[1]).toHaveStyle({ height: "2px" });
  });

  it("zero-count bar has height 0", () => {
    const { container } = render(
      <Sparkline items={makeItems([10, 0])} />,
    );
    const bars = container.querySelectorAll(".bn-sparkline-bar");
    expect(bars[1]).toHaveStyle({ height: "0px" });
  });

  it("applies colour from items", () => {
    const items: SparklineItem[] = [
      { key: "a", count: 5, colour: "var(--bn-sentiment-frustration)" },
    ];
    const { container } = render(<Sparkline items={items} />);
    const bar = container.querySelector(".bn-sparkline-bar");
    expect(bar).toHaveStyle({ background: "var(--bn-sentiment-frustration)" });
  });

  it("applies custom opacity", () => {
    const { container } = render(
      <Sparkline items={makeItems([5])} opacity={0.5} />,
    );
    const bar = container.querySelector(".bn-sparkline-bar");
    expect(bar).toHaveStyle({ opacity: 0.5 });
  });

  it("applies custom gap", () => {
    render(<Sparkline items={makeItems([5, 3])} gap={4} data-testid="sp" />);
    expect(screen.getByTestId("sp")).toHaveStyle({ gap: "4px" });
  });

  it("applies className to container", () => {
    render(
      <Sparkline items={makeItems([5])} className="custom" data-testid="sp" />,
    );
    const el = screen.getByTestId("sp");
    expect(el).toHaveClass("bn-sparkline");
    expect(el).toHaveClass("custom");
  });

  it("forwards data-testid", () => {
    render(<Sparkline items={makeItems([5])} data-testid="my-spark" />);
    expect(screen.getByTestId("my-spark")).toBeInTheDocument();
  });
});
