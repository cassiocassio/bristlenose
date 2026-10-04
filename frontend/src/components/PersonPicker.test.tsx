import { fireEvent, render, screen } from "@testing-library/react";

import i18n from "../i18n";
import { PersonPicker } from "./PersonPicker";
import {
  personPickerChoice,
  personPickerLabels,
  personPickerRows,
  type PersonPickerSlot,
} from "../utils/personPicker";

const labels = (slot: PersonPickerSlot) => personPickerLabels(slot, i18n.t);

const moderator = (name: string, confirmed: boolean): PersonPickerSlot => ({
  code: "m1",
  role: "moderator",
  name,
  confirmed,
});

const menu = () => document.querySelector(".bn-person-picker") as HTMLElement;
const items = () => Array.from(menu().querySelectorAll<HTMLElement>(".export-dropdown-item"));

describe("personPickerRows", () => {
  it("offers a moderator every moderator name known, once, the slot's own first if unseen", () => {
    expect(personPickerRows(moderator("Jo", false), ["Martin", "Kerri", "Martin", ""])).toEqual([
      "Jo",
      "Martin",
      "Kerri",
    ]);
  });

  it("offers a participant only themself: another name would be a merge, not built", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "Mary", confirmed: true };
    expect(personPickerRows(slot, ["Sarah", "Mary", "Bob"])).toEqual(["Mary"]);
    expect(personPickerRows({ ...slot, name: "" }, ["Sarah"])).toEqual([]);
  });
});

describe("personPickerChoice", () => {
  it("the slot's own proposed name is a yes", () => {
    expect(personPickerChoice(moderator("Martin", false), "Martin")).toEqual({ kind: "confirm" });
  });

  it("the slot's own confirmed name changes nothing", () => {
    expect(personPickerChoice(moderator("Martin", true), "Martin")).toBeNull();
  });

  it("any other name renames, trimmed; an empty one is nothing", () => {
    expect(personPickerChoice(moderator("Martin", true), "  Kerri ")).toEqual({ kind: "name", name: "Kerri" });
    expect(personPickerChoice(moderator("Martin", true), "   ")).toBeNull();
  });
});

describe("PersonPicker", () => {
  it("opens on the proposed answer: ticked, ringed, selected", () => {
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} knownNames={["Martin", "Kerri"]} onChoose={vi.fn()} onClose={vi.fn()} />);
    const [martin, kerri] = items();
    expect(martin.querySelector(".export-dropdown-check")?.textContent).toBe("✓");
    expect(martin.querySelector(".bn-person-proposed")).not.toBeNull();
    expect(kerri.querySelector(".export-dropdown-check")?.textContent).toBe("");
    expect(document.activeElement).toBe(martin);
  });

  it("a proposed answer says so to assistive tech, a confirmed one does not", () => {
    const { unmount } = render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} knownNames={["Martin", "Kerri"]} onChoose={vi.fn()} onClose={vi.fn()} />);
    const [martin, kerri] = items();
    expect(martin.getAttribute("aria-label")).toBe("m1, proposed name Martin");
    expect(kerri.getAttribute("aria-label")).toBeNull();
    unmount();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} knownNames={["Martin"]} onChoose={vi.fn()} onClose={vi.fn()} />);
    expect(items()[0].getAttribute("aria-label")).toBeNull();
  });

  it("Enter on the proposed answer says yes", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} knownNames={["Martin"]} onChoose={onChoose} onClose={onClose} />);
    fireEvent.keyDown(menu(), { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "confirm" });
    expect(onClose).toHaveBeenCalled();
  });

  it("Space on a row chooses it once", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} knownNames={["Martin"]} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.keyDown(items()[0], { key: " " });
    expect(onChoose).toHaveBeenCalledTimes(1);
    expect(onChoose).toHaveBeenCalledWith({ kind: "confirm" });
  });

  it("a key the picker handles does not reach the page's shortcuts", () => {
    const onDocKey = vi.fn();
    document.addEventListener("keydown", onDocKey);
    try {
      render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} knownNames={["Martin"]} onChoose={vi.fn()} onClose={vi.fn()} />);
      fireEvent.keyDown(items()[0], { key: "Escape" });
      fireEvent.keyDown(screen.getByPlaceholderText("New moderator"), { key: "Escape" });
      expect(onDocKey).not.toHaveBeenCalled();
    } finally {
      document.removeEventListener("keydown", onDocKey);
    }
  });

  it("Escape and a choice hand focus back to the badge", () => {
    const slot = moderator("Martin", true);
    const { rerender } = render(
      <span>
        <button type="button" className="bn-person-picker-trigger">m1</button>
        <PersonPicker slot={slot} labels={labels(slot)} knownNames={["Martin", "Kerri"]} onChoose={vi.fn()} onClose={vi.fn()} />
      </span>,
    );
    const trigger = document.querySelector(".bn-person-picker-trigger");
    fireEvent.keyDown(menu(), { key: "Escape" });
    expect(document.activeElement).toBe(trigger);
    rerender(
      <span>
        <button type="button" className="bn-person-picker-trigger">m1</button>
        <PersonPicker key="again" slot={slot} labels={labels(slot)} knownNames={["Martin", "Kerri"]} onChoose={vi.fn()} onClose={vi.fn()} />
      </span>,
    );
    expect(document.activeElement).not.toBe(trigger);
    fireEvent.click(items()[1]);
    expect(document.activeElement).toBe(trigger);
  });

  it("choosing another name renames the slot", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} knownNames={["Martin", "Kerri"]} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.click(items()[1]);
    expect(onChoose).toHaveBeenCalledWith({ kind: "name", name: "Kerri" });
  });

  it("every row carries this slot's code — project-wide codes are not built", () => {
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} knownNames={["Martin", "Kerri"]} onChoose={vi.fn()} onClose={vi.fn()} />);
    const codes = Array.from(menu().querySelectorAll(".bn-speaker-badge-code")).map((c) => c.textContent);
    expect(codes).toEqual(["m1", "m1", "m1"]); // two names and the new row
  });

  it("an unknown slot pre-selects nothing, so Return cannot confirm a guess", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("", false)} labels={labels(moderator("", false))} knownNames={["Martin"]} onChoose={onChoose} onClose={vi.fn()} />);
    expect(document.activeElement).toBe(menu());
    fireEvent.keyDown(menu(), { key: "Enter" });
    expect(onChoose).not.toHaveBeenCalled();
    fireEvent.keyDown(menu(), { key: "ArrowDown" });
    expect(document.activeElement).toBe(items()[0]);
  });

  it("only the speaker's own role is enabled: changing role is not built", () => {
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} knownNames={[]} onChoose={vi.fn()} onClose={vi.fn()} />);
    const [mod, part, obs] = screen.getAllByRole("radio") as HTMLButtonElement[];
    expect([mod.disabled, part.disabled, obs.disabled]).toEqual([false, true, true]);
    expect(mod.getAttribute("aria-checked")).toBe("true");
  });

  it("someone new is typed into the next badge's name half", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} knownNames={["Martin"]} onChoose={onChoose} onClose={vi.fn()} />);
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "Mike Alvarez" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "name", name: "Mike Alvarez" });
  });

  it("a participant's field is a new name for that participant", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "Mary", confirmed: true };
    render(<PersonPicker slot={slot} labels={labels(slot)} knownNames={["Sarah"]} onChoose={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByPlaceholderText("New name for p3")).toBeInTheDocument();
    expect(items()).toHaveLength(2); // Mary and the field
  });

  it("type-to-jump lands on any word of a name", () => {
    render(<PersonPicker slot={moderator("Martin Storey", true)} labels={labels(moderator("Martin Storey", true))} knownNames={["Martin Storey", "Kerri Ng"]} onChoose={vi.fn()} onClose={vi.fn()} />);
    fireEvent.keyDown(menu(), { key: "n" });
    fireEvent.keyDown(menu(), { key: "g" });
    expect(document.activeElement).toBe(items()[1]);
  });

  it("Escape closes without choosing", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} knownNames={["Martin"]} onChoose={onChoose} onClose={onClose} />);
    fireEvent.keyDown(menu(), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
    expect(onChoose).not.toHaveBeenCalled();
  });
});
