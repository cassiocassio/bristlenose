import { fireEvent, render, screen } from "@testing-library/react";

import { PickerSpecimen } from "./PickerSpecimen";

const menu = () => document.querySelector(".bn-person-picker") as HTMLElement | null;

describe("PickerSpecimen", () => {
  afterEach(() => window.history.replaceState(null, "", "/"));

  it("opens the production picker on the proposed moderator", () => {
    render(<PickerSpecimen />);
    expect(menu()).not.toBeNull();
    expect(document.querySelector(".bn-person-picker-trigger.bn-person-proposed")).not.toBeNull();
  });

  it("Enter says yes: the badge loses its ring and the picker closes", () => {
    render(<PickerSpecimen />);
    fireEvent.keyDown(menu()!, { key: "Enter" });
    expect(menu()).toBeNull();
    expect(document.querySelector(".bn-person-picker-trigger.bn-person-proposed")).toBeNull();
  });

  it("opens on the scenario the lab puts in the URL", () => {
    window.history.replaceState(null, "", "/report/picker-specimen?scenario=participant");
    render(<PickerSpecimen />);
    expect(screen.getByPlaceholderText("New name for p3")).toBeInTheDocument();
  });

  it("a new moderator becomes the answer and joins the list", () => {
    render(<PickerSpecimen />);
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "Mike Alvarez" } });
    fireEvent.keyDown(field, { key: "Enter" });
    fireEvent.click(document.querySelector(".bn-person-picker-trigger") as HTMLElement);
    const names = Array.from(menu()!.querySelectorAll(".bn-speaker-badge-name")).map((n) => n.textContent);
    expect(names).toContain("Mike Alvarez");
  });
});
