import { render, screen, fireEvent } from "@testing-library/react";
import { ExpandableTimecode } from "./ExpandableTimecode";

describe("ExpandableTimecode", () => {
  const NOOP = () => {};

  it("renders children (the timecode element)", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span className="timecode">[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByText("[0:26]")).toBeInTheDocument();
  });

  it("renders up arrow when canExpandAbove is true", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={false}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByTestId("expand-arrow-up")).toBeInTheDocument();
    expect(screen.queryByTestId("expand-arrow-down")).not.toBeInTheDocument();
  });

  it("renders down arrow when canExpandBelow is true", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={false}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.queryByTestId("expand-arrow-up")).not.toBeInTheDocument();
    expect(screen.getByTestId("expand-arrow-down")).toBeInTheDocument();
  });

  it("renders both arrows when both can expand", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByTestId("expand-arrow-up")).toBeInTheDocument();
    expect(screen.getByTestId("expand-arrow-down")).toBeInTheDocument();
  });

  it("calls onExpandAbove when up arrow clicked", () => {
    const onAbove = vi.fn();
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={false}
        onExpandAbove={onAbove}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    fireEvent.click(screen.getByTestId("expand-arrow-up"));
    expect(onAbove).toHaveBeenCalledTimes(1);
  });

  it("calls onExpandBelow when down arrow clicked", () => {
    const onBelow = vi.fn();
    render(
      <ExpandableTimecode
        canExpandAbove={false}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={onBelow}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    fireEvent.click(screen.getByTestId("expand-arrow-down"));
    expect(onBelow).toHaveBeenCalledTimes(1);
  });

  it("up arrow is disabled when exhaustedAbove is true", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={false}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        exhaustedAbove={true}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByTestId("expand-arrow-up")).toBeDisabled();
  });

  it("down arrow is disabled when exhaustedBelow is true", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={false}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        exhaustedBelow={true}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByTestId("expand-arrow-down")).toBeDisabled();
  });

  it("arrow click stops propagation (does not trigger video seek)", () => {
    const parentClick = vi.fn();
    const onAbove = vi.fn();
    render(
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions,jsx-a11y/click-events-have-key-events
      <div onClick={parentClick}>
        <ExpandableTimecode
          canExpandAbove={true}
          canExpandBelow={false}
          onExpandAbove={onAbove}
          onExpandBelow={NOOP}
          data-testid="expand"
        >
          <span>[0:26]</span>
        </ExpandableTimecode>
      </div>,
    );
    fireEvent.click(screen.getByTestId("expand-arrow-up"));
    expect(onAbove).toHaveBeenCalledTimes(1);
    expect(parentClick).not.toHaveBeenCalled();
  });

  it("has .timecode-expandable class", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByTestId("expand")).toHaveClass("timecode-expandable");
  });

  it("arrows have correct data-dir attributes", () => {
    render(
      <ExpandableTimecode
        canExpandAbove={true}
        canExpandBelow={true}
        onExpandAbove={NOOP}
        onExpandBelow={NOOP}
        data-testid="expand"
      >
        <span>[0:26]</span>
      </ExpandableTimecode>,
    );
    expect(screen.getByTestId("expand-arrow-up")).toHaveAttribute("data-dir", "up");
    expect(screen.getByTestId("expand-arrow-down")).toHaveAttribute("data-dir", "down");
  });
});
