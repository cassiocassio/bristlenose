import { render, screen } from "@testing-library/react";
import { MicroBar } from "./MicroBar";

describe("MicroBar", () => {
  // ── Bare bar mode (no track, no tentative) ──────────────────────────

  it("renders a bare bar (no track) by default", () => {
    render(<MicroBar value={0.5} data-testid="bar" />);
    const el = screen.getByTestId("bar");
    expect(el).toHaveClass("tag-micro-bar");
    expect(el.style.width).toBe("50%");
  });

  it("clamps value=0 to 0%", () => {
    render(<MicroBar value={0} data-testid="bar" />);
    expect(screen.getByTestId("bar").style.width).toBe("0%");
  });

  it("clamps value=1 to 100%", () => {
    render(<MicroBar value={1} data-testid="bar" />);
    expect(screen.getByTestId("bar").style.width).toBe("100%");
  });

  it("clamps values above 1", () => {
    render(<MicroBar value={1.5} data-testid="bar" />);
    expect(screen.getByTestId("bar").style.width).toBe("100%");
  });

  it("clamps negative values to 0", () => {
    render(<MicroBar value={-0.3} data-testid="bar" />);
    expect(screen.getByTestId("bar").style.width).toBe("0%");
  });

  it("rounds fractional percentages", () => {
    render(<MicroBar value={0.333} data-testid="bar" />);
    expect(screen.getByTestId("bar").style.width).toBe("33%");
  });

  it("applies custom colour as backgroundColor", () => {
    render(<MicroBar value={0.5} colour="var(--bn-bar-emo)" data-testid="bar" />);
    expect(screen.getByTestId("bar").style.backgroundColor).toBe("var(--bn-bar-emo)");
  });

  // ── Track mode ──────────────────────────────────────────────────────

  it("renders track mode with outer track and inner fill", () => {
    const { container } = render(<MicroBar value={0.75} track data-testid="track" />);
    const track = screen.getByTestId("track");
    expect(track).toHaveClass("conc-bar-track");
    const fill = container.querySelector(".conc-bar-fill") as HTMLElement;
    expect(fill).toBeTruthy();
    expect(fill.style.width).toBe("75%");
  });

  it("track mode applies colour to fill, not track", () => {
    const { container } = render(
      <MicroBar value={0.5} track colour="red" data-testid="track" />,
    );
    const track = screen.getByTestId("track");
    expect(track.style.backgroundColor).toBe("");
    const fill = container.querySelector(".conc-bar-fill") as HTMLElement;
    expect(fill.style.backgroundColor).toBe("red");
  });

  // ── Two-tone stacked bar ────────────────────────────────────────────

  it("renders two-tone bar when tentativeValue is provided", () => {
    render(
      <MicroBar value={0.25} tentativeValue={0.5} data-testid="bar" />,
    );
    const stack = screen.getByTestId("bar");
    expect(stack).toHaveClass("tag-micro-bar-stack");
    // Total = 0.25 + 0.5 = 0.75 → 75%
    expect(stack.style.width).toBe("75%");
  });

  it("two-tone bar has tentative and accepted segments", () => {
    render(
      <MicroBar value={0.25} tentativeValue={0.5} data-testid="bar" />,
    );
    const tentative = screen.getByTestId("bar-tentative");
    const accepted = screen.getByTestId("bar-accepted");
    expect(tentative).toHaveClass("tag-micro-bar-tentative");
    expect(accepted).toHaveClass("tag-micro-bar-accepted");
    // 0.5 / 0.75 ≈ 67% tentative, 0.25 / 0.75 ≈ 33% accepted
    expect(tentative.style.width).toBe("67%");
    expect(accepted.style.width).toBe("33%");
  });

  it("two-tone bar renders tentative-only when value=0", () => {
    render(
      <MicroBar value={0} tentativeValue={0.6} data-testid="bar" />,
    );
    const stack = screen.getByTestId("bar");
    expect(stack.style.width).toBe("60%");
    // Only tentative segment should exist
    expect(screen.getByTestId("bar-tentative")).toBeInTheDocument();
    expect(screen.queryByTestId("bar-accepted")).not.toBeInTheDocument();
  });

  it("two-tone bar renders accepted-only when tentativeValue=0", () => {
    render(
      <MicroBar value={0.4} tentativeValue={0} data-testid="bar" />,
    );
    const stack = screen.getByTestId("bar");
    expect(stack.style.width).toBe("40%");
    expect(screen.queryByTestId("bar-tentative")).not.toBeInTheDocument();
    expect(screen.getByTestId("bar-accepted")).toBeInTheDocument();
  });

  it("two-tone bar returns null when both values are 0", () => {
    const { container } = render(
      <MicroBar value={0} tentativeValue={0} data-testid="bar" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("two-tone bar applies colour to both segments", () => {
    render(
      <MicroBar value={0.3} tentativeValue={0.3} colour="var(--bn-bar-ux)" data-testid="bar" />,
    );
    const tentative = screen.getByTestId("bar-tentative");
    const accepted = screen.getByTestId("bar-accepted");
    expect(tentative.style.backgroundColor).toBe("var(--bn-bar-ux)");
    expect(accepted.style.backgroundColor).toBe("var(--bn-bar-ux)");
  });

  it("two-tone bar clamps total to 100%", () => {
    render(
      <MicroBar value={0.8} tentativeValue={0.8} data-testid="bar" />,
    );
    const stack = screen.getByTestId("bar");
    expect(stack.style.width).toBe("100%");
  });

  it("two-tone bar forwards title attribute", () => {
    render(
      <MicroBar value={0.3} tentativeValue={0.2} title="3 tentative + 2 accepted" data-testid="bar" />,
    );
    expect(screen.getByTestId("bar")).toHaveAttribute("title", "3 tentative + 2 accepted");
  });

  // ── Shared props ────────────────────────────────────────────────────

  it("forwards className in bare mode", () => {
    render(<MicroBar value={0.5} className="extra" data-testid="bar" />);
    expect(screen.getByTestId("bar")).toHaveClass("tag-micro-bar", "extra");
  });

  it("forwards className in track mode", () => {
    render(<MicroBar value={0.5} track className="extra" data-testid="bar" />);
    expect(screen.getByTestId("bar")).toHaveClass("conc-bar-track", "extra");
  });

  it("forwards className in two-tone mode", () => {
    render(<MicroBar value={0.3} tentativeValue={0.2} className="extra" data-testid="bar" />);
    expect(screen.getByTestId("bar")).toHaveClass("tag-micro-bar-stack", "extra");
  });

  it("forwards data-testid", () => {
    render(<MicroBar value={0.5} data-testid="my-bar" />);
    expect(screen.getByTestId("my-bar")).toBeInTheDocument();
  });

  it("forwards title in bare mode", () => {
    render(<MicroBar value={0.5} title="hello" data-testid="bar" />);
    expect(screen.getByTestId("bar")).toHaveAttribute("title", "hello");
  });

  // ── Accessibility ──────────────────────────────────────────────────

  it("two-tone bar has role=img and aria-label from title", () => {
    render(
      <MicroBar value={0.3} tentativeValue={0.2} title="2 tentative + 3 accepted" data-testid="bar" />,
    );
    const stack = screen.getByTestId("bar");
    expect(stack).toHaveAttribute("role", "img");
    expect(stack).toHaveAttribute("aria-label", "2 tentative + 3 accepted");
  });

  it("two-tone segments are aria-hidden", () => {
    render(
      <MicroBar value={0.3} tentativeValue={0.2} data-testid="bar" />,
    );
    expect(screen.getByTestId("bar-tentative")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByTestId("bar-accepted")).toHaveAttribute("aria-hidden", "true");
  });

  it("track bar has role=img and aria-hidden fill", () => {
    const { container } = render(
      <MicroBar value={0.5} track title="50%" data-testid="track" />,
    );
    const track = screen.getByTestId("track");
    expect(track).toHaveAttribute("role", "img");
    expect(track).toHaveAttribute("aria-label", "50%");
    const fill = container.querySelector(".conc-bar-fill") as HTMLElement;
    expect(fill).toHaveAttribute("aria-hidden", "true");
  });

  it("bare bar has role=img and aria-label", () => {
    render(<MicroBar value={0.5} title="5 quotes" data-testid="bar" />);
    const el = screen.getByTestId("bar");
    expect(el).toHaveAttribute("role", "img");
    expect(el).toHaveAttribute("aria-label", "5 quotes");
  });
});
