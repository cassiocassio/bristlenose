import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Annotation } from "./Annotation";

describe("Annotation", () => {
  it("renders nothing when no label, sentiment, or tags", () => {
    const { container } = render(<Annotation quoteId="q1" />);
    expect(container.innerHTML).toBe("");
  });

  it("renders a label as an anchor linking to the quote", () => {
    render(<Annotation quoteId="q1" label="Homepage" data-testid="ann" />);
    const link = screen.getByTestId("ann").querySelector(".margin-label") as HTMLAnchorElement;
    expect(link).not.toBeNull();
    expect(link.textContent).toBe("Homepage");
    expect(link.getAttribute("href")).toBe("#q-q1");
  });

  it("renders without label when only sentiment is provided", () => {
    render(
      <Annotation
        quoteId="q1"
        sentiment={{ text: "frustration", sentiment: "frustration" }}
        data-testid="ann"
      />,
    );
    const el = screen.getByTestId("ann");
    expect(el.querySelector(".margin-label")).toBeNull();
    expect(el.querySelector(".margin-tags")).not.toBeNull();
  });

  it("renders without label when only tags are provided", () => {
    render(
      <Annotation
        quoteId="q1"
        tags={[{ name: "usability" }]}
        data-testid="ann"
      />,
    );
    const el = screen.getByTestId("ann");
    expect(el.querySelector(".margin-label")).toBeNull();
    expect(el.querySelector(".margin-tags")).not.toBeNull();
  });

  it("renders an AI sentiment badge", () => {
    render(
      <Annotation
        quoteId="q1"
        sentiment={{ text: "delight", sentiment: "delight" }}
        data-testid="ann"
      />,
    );
    const badge = screen.getByTestId("ann-sentiment");
    expect(badge.textContent).toBe("delight");
    expect(badge.classList.contains("badge-ai")).toBe(true);
    expect(badge.classList.contains("badge-delight")).toBe(true);
  });

  it("calls sentiment onDelete when AI badge is clicked", async () => {
    const onDelete = vi.fn();
    render(
      <Annotation
        quoteId="q1"
        sentiment={{ text: "frustration", sentiment: "frustration", onDelete }}
        data-testid="ann"
      />,
    );
    await userEvent.click(screen.getByTestId("ann-sentiment"));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("renders user tag badges", () => {
    render(
      <Annotation
        quoteId="q1"
        tags={[
          { name: "usability", colour: "#ff0000" },
          { name: "onboarding" },
        ]}
        data-testid="ann"
      />,
    );
    expect(screen.getByTestId("ann-tag-usability").textContent).toContain("usability");
    expect(screen.getByTestId("ann-tag-onboarding").textContent).toContain("onboarding");
  });

  it("calls onTagDelete with tag name when user badge delete is clicked", async () => {
    const onTagDelete = vi.fn();
    render(
      <Annotation
        quoteId="q1"
        tags={[{ name: "usability" }]}
        onTagDelete={onTagDelete}
        data-testid="ann"
      />,
    );
    const deleteBtn = screen.getByTestId("ann-tag-usability").querySelector(".badge-delete");
    expect(deleteBtn).not.toBeNull();
    await userEvent.click(deleteBtn!);
    expect(onTagDelete).toHaveBeenCalledWith("usability");
  });

  it("does not render delete button when onTagDelete is not provided", () => {
    render(
      <Annotation
        quoteId="q1"
        tags={[{ name: "usability" }]}
        data-testid="ann"
      />,
    );
    const deleteBtn = screen.getByTestId("ann-tag-usability").querySelector(".badge-delete");
    expect(deleteBtn).toBeNull();
  });

  it("renders both label and tags together", () => {
    render(
      <Annotation
        quoteId="q1"
        label="Checkout"
        sentiment={{ text: "trust", sentiment: "trust" }}
        tags={[{ name: "payment" }]}
        data-testid="ann"
      />,
    );
    const el = screen.getByTestId("ann");
    expect(el.querySelector(".margin-label")).not.toBeNull();
    expect(el.querySelector(".margin-tags")).not.toBeNull();
    expect(el.querySelectorAll(".badge")).toHaveLength(2);
  });

  it("uses margin-annotation as the base class", () => {
    render(<Annotation quoteId="q1" label="Test" data-testid="ann" />);
    expect(screen.getByTestId("ann").className).toBe("margin-annotation");
  });

  it("appends custom className", () => {
    render(<Annotation quoteId="q1" label="Test" className="extra" data-testid="ann" />);
    expect(screen.getByTestId("ann").className).toBe("margin-annotation extra");
  });

  it("sets data-quote-id attribute", () => {
    render(<Annotation quoteId="abc-123" label="Test" data-testid="ann" />);
    expect(screen.getByTestId("ann").getAttribute("data-quote-id")).toBe("abc-123");
  });

  it("applies user tag colour as background", () => {
    render(
      <Annotation
        quoteId="q1"
        tags={[{ name: "ux", colour: "rgb(255, 0, 0)" }]}
        data-testid="ann"
      />,
    );
    const badge = screen.getByTestId("ann-tag-ux");
    expect(badge.style.backgroundColor).toBe("rgb(255, 0, 0)");
  });
});
