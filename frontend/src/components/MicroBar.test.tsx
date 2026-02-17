import { render, screen } from "@testing-library/react";
import { MicroBar } from "./MicroBar";

describe("MicroBar", () => {
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

  it("forwards className in bare mode", () => {
    render(<MicroBar value={0.5} className="extra" data-testid="bar" />);
    expect(screen.getByTestId("bar")).toHaveClass("tag-micro-bar", "extra");
  });

  it("forwards className in track mode", () => {
    render(<MicroBar value={0.5} track className="extra" data-testid="bar" />);
    expect(screen.getByTestId("bar")).toHaveClass("conc-bar-track", "extra");
  });

  it("forwards data-testid", () => {
    render(<MicroBar value={0.5} data-testid="my-bar" />);
    expect(screen.getByTestId("my-bar")).toBeInTheDocument();
  });
});
