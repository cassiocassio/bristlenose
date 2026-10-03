import { act, fireEvent, render, screen } from "@testing-library/react";

import { PickerSpecimen } from "./PickerSpecimen";

vi.mock("../shims/bridge", () => ({ postSearchBadgeStyles: vi.fn() }));
vi.mock("../utils/badgeStyle", () => ({ probeBadgeStyles: vi.fn(() => ({ tags: {}, people: {} })) }));

const menu = () => document.querySelector(".bn-person-picker") as HTMLElement;
const items = () => Array.from(menu().querySelectorAll<HTMLElement>(".export-dropdown-item"));

describe("PickerSpecimen", () => {
  it("opens on the proposed moderator: ticked, ringed, and selected", () => {
    render(<PickerSpecimen />);
    const [m1, m2] = items();
    expect(m1.getAttribute("aria-checked")).toBe("true");
    expect(m1.querySelector(".bn-picker-tick svg")).not.toBeNull();
    expect(m1.querySelector(".badge-proposed")).not.toBeNull();
    expect(m2.querySelector(".bn-picker-tick")).toBeNull();
    expect(document.activeElement).toBe(m1);
  });

  it("Enter says yes: the anchor loses its ring", () => {
    render(<PickerSpecimen />);
    fireEvent.keyDown(menu(), { key: "Enter" });
    expect(menu()).toBeNull();
    const anchor = document.querySelector(".bn-picker-anchor") as HTMLElement;
    expect(anchor.querySelector(".badge-proposed")).toBeNull();
    expect(anchor.textContent).toContain("Martin B Storey");
  });

  it("the role segments switch the list, and Participant has no That's Me", () => {
    render(<PickerSpecimen />);
    fireEvent.click(screen.getByRole("radio", { name: "Participant" }));
    expect(items()).toHaveLength(6);
    expect(menu().querySelector(".bn-picker-me")).toBeNull();
    expect(screen.getByPlaceholderText("New participant")).toBeInTheDocument();
  });

  it("type-to-jump moves the selection by name", () => {
    render(<PickerSpecimen />);
    fireEvent.keyDown(menu(), { key: "k" });
    expect(document.activeElement).toBe(items()[1]);
  });

  it("a new name typed in the field becomes the confirmed answer", () => {
    render(<PickerSpecimen />);
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "Mike Alvarez" } });
    fireEvent.keyDown(field, { key: "Enter" });
    const anchor = document.querySelector(".bn-picker-anchor") as HTMLElement;
    expect(anchor.textContent).toContain("m3");
    expect(anchor.textContent).toContain("Mike Alvarez");
  });

  it("the native toolbar can set a scenario", () => {
    render(<PickerSpecimen />);
    act(() => window.__pickerLab?.setScenario("unknown"));
    expect(items().some((i) => i.getAttribute("aria-checked") === "true")).toBe(false);
    expect(document.querySelector(".bn-picker-anchor")?.textContent).toBe("Moderator");
  });
});
