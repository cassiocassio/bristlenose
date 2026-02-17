import { render, screen } from "@testing-library/react";
import { TimecodeLink } from "./TimecodeLink";

describe("TimecodeLink", () => {
  it("renders formatted timecode", () => {
    render(
      <TimecodeLink
        seconds={83}
        participantId="p1"
        formatted="[01:23]"
        data-testid="tc"
      />,
    );
    const link = screen.getByTestId("tc");
    expect(link.textContent).toBe("[01:23]");
  });

  it("auto-formats when no formatted prop", () => {
    render(
      <TimecodeLink seconds={83} participantId="p1" data-testid="tc" />,
    );
    const link = screen.getByTestId("tc");
    expect(link.textContent).toBe("[01:23]");
  });

  it("auto-formats hours when >= 3600", () => {
    render(
      <TimecodeLink seconds={3723} participantId="p1" data-testid="tc" />,
    );
    expect(screen.getByTestId("tc").textContent).toBe("[1:02:03]");
  });

  it("has correct data attributes", () => {
    render(
      <TimecodeLink
        seconds={90}
        endSeconds={120}
        participantId="p2"
        data-testid="tc"
      />,
    );
    const link = screen.getByTestId("tc");
    expect(link).toHaveAttribute("data-participant", "p2");
    expect(link).toHaveAttribute("data-seconds", "90");
    expect(link).toHaveAttribute("data-end-seconds", "120");
  });

  it("renders as anchor element", () => {
    render(
      <TimecodeLink seconds={10} participantId="p1" data-testid="tc" />,
    );
    expect(screen.getByTestId("tc").tagName).toBe("A");
  });

  it("omits data-end-seconds when not provided", () => {
    render(
      <TimecodeLink seconds={10} participantId="p1" data-testid="tc" />,
    );
    expect(screen.getByTestId("tc")).not.toHaveAttribute("data-end-seconds");
  });
});
