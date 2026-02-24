import { render, screen } from "@testing-library/react";
import { PersonBadge } from "./PersonBadge";

describe("PersonBadge", () => {
  it("renders code in split badge structure", () => {
    const { container } = render(<PersonBadge code="p1" role="participant" />);
    expect(screen.getByText("p1")).toBeInTheDocument();
    expect(screen.getByText("p1")).toHaveClass("bn-speaker-badge-code");
    expect(container.querySelector(".bn-speaker-badge--split")).toBeInTheDocument();
  });

  it("renders name when provided", () => {
    render(<PersonBadge code="p1" role="participant" name="Alice" />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toHaveClass("bn-speaker-badge-name");
  });

  it("does not render name span when name absent", () => {
    const { container } = render(<PersonBadge code="m1" role="moderator" />);
    expect(container.querySelector(".bn-speaker-badge-name")).not.toBeInTheDocument();
  });

  it("wraps in link when href provided", () => {
    render(<PersonBadge code="p2" role="participant" href="/transcript/p2" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/transcript/p2");
    expect(link).toHaveClass("speaker-link");
  });

  it("applies highlighted class", () => {
    render(<PersonBadge code="p1" role="participant" highlighted data-testid="pb" />);
    expect(screen.getByTestId("pb")).toHaveClass("bn-person-badge-highlighted");
  });

  it("retains bn-person-badge wrapper", () => {
    const { container } = render(<PersonBadge code="p1" role="participant" />);
    expect(container.querySelector(".bn-person-badge")).toBeInTheDocument();
  });
});
