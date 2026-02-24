import { render, screen } from "@testing-library/react";
import { ContextSegment } from "./ContextSegment";

describe("ContextSegment", () => {
  it("renders speaker code, timecode, and text", () => {
    render(
      <ContextSegment
        speakerCode="p1"
        isModerator={false}
        startTime={120}
        text="I found the menu quite confusing"
        data-testid="ctx-above-0"
      />,
    );
    expect(screen.getByTestId("ctx-above-0")).toBeInTheDocument();
    expect(screen.getByText(/I found the menu quite confusing/)).toBeInTheDocument();
  });

  it("renders participant badge for non-moderator", () => {
    const { container } = render(
      <ContextSegment
        speakerCode="p2"
        isModerator={false}
        startTime={60}
        text="Some text"
      />,
    );
    const badge = container.querySelector(".bn-person-badge");
    expect(badge).toBeInTheDocument();
    expect(badge?.textContent).toContain("p2");
  });

  it("renders badge for moderator segment", () => {
    const { container } = render(
      <ContextSegment
        speakerCode="m1"
        isModerator={true}
        startTime={55}
        text="Can you tell me more?"
      />,
    );
    const badge = container.querySelector(".bn-person-badge");
    expect(badge).toBeInTheDocument();
    expect(badge?.textContent).toContain("m1");
  });

  it("formats timecode correctly", () => {
    const { container } = render(
      <ContextSegment
        speakerCode="p1"
        isModerator={false}
        startTime={125}
        text="Some text"
      />,
    );
    const timecode = container.querySelector(".timecode");
    expect(timecode?.textContent).toMatch(/2:05/);
  });

  it("has the .context-segment class and .quote-row for grid alignment", () => {
    const { container } = render(
      <ContextSegment
        speakerCode="p1"
        isModerator={false}
        startTime={10}
        text="Hello"
      />,
    );
    expect(container.querySelector(".context-segment")).toBeInTheDocument();
    expect(container.querySelector(".context-segment .quote-row")).toBeInTheDocument();
  });
});
