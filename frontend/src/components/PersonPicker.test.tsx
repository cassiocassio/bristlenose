import { fireEvent, render, screen } from "@testing-library/react";

import i18n from "../i18n";
import { PersonPicker } from "./PersonPicker";
import {
  personPickerChoice,
  personPickerLabels,
  personPickerNameTaken,
  personPickerNewCode,
  personPickerRows,
  personPickerTyped,
  type PersonPickerRow,
  type PersonPickerSlot,
} from "../utils/personPicker";

const labels = (slot: PersonPickerSlot) => personPickerLabels(slot, i18n.t);

/** Moderators known in the study, coded m1, m2… in the order given. */
const people = (...names: string[]): PersonPickerRow[] =>
  names.map((name, i) => ({ name, code: `m${i + 1}`, person: `id-${name}` }));

const moderator = (name: string, confirmed: boolean, code = "m1"): PersonPickerSlot => ({
  code,
  role: "moderator",
  name,
  confirmed,
  ...(name ? { person: `id-${name}` } : {}),
});

const menu = () => document.querySelector(".bn-person-picker") as HTMLElement;
const items = () => Array.from(menu().querySelectorAll<HTMLElement>(".export-dropdown-item"));

describe("personPickerRows", () => {
  it("offers a moderator every person known, once, the slot's own first if unseen", () => {
    const rows = personPickerRows(moderator("Jo", false, "m3"), [
      ...people("Martin", "Kerri"),
      { name: "Martin", code: "m1", person: "id-Martin" },
      { name: "", code: "m?" },
    ]);
    expect(rows.map((r) => [r.code, r.name])).toEqual([["m3", "Jo"], ["m1", "Martin"], ["m2", "Kerri"]]);
  });

  it("offers a participant only themself: another would be a merge, not built", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "Mary", confirmed: true };
    const known = [{ name: "Sarah", code: "p1" }, { name: "Mary", code: "p3" }];
    expect(personPickerRows(slot, known).map((r) => r.name)).toEqual(["Mary"]);
    expect(personPickerRows({ ...slot, name: "" }, known)).toEqual([]);
  });
});

describe("personPickerRows — only people someone has said yes to (§J8.10)", () => {
  const guess: PersonPickerRow = { name: "Kerri", code: "m2", person: "id-Kerri", confirmed: false };

  it("another session's guess is not offered", () => {
    const rows = personPickerRows(moderator("Martin", true), [...people("Martin"), guess]);
    expect(rows.map((r) => r.name)).toEqual(["Martin"]);
  });

  it("the speaker's own guess is", () => {
    const own: PersonPickerSlot = { code: "m2", role: "moderator", name: "Kerri", confirmed: false, person: "id-Kerri" };
    expect(personPickerRows(own, [...people("Martin"), guess]).map((r) => r.name)).toEqual(["Martin", "Kerri"]);
  });

  it("an unoffered guess still holds its name: someone new may not take it", () => {
    expect(personPickerNameTaken(moderator("", false, "m?"), [...people("Martin"), guess], "kerri")).toBe("Kerri");
  });
});

describe("personPickerNewCode", () => {
  it("is the next free number for the role (§J8.8)", () => {
    expect(personPickerNewCode(moderator("", false, "m?"), people("Martin", "Kerri"))).toBe("m3");
    expect(personPickerNewCode(moderator("", false, "m?"), [])).toBe("m1");
  });

  it("is a participant's own code", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "", confirmed: true };
    expect(personPickerNewCode(slot, [])).toBe("p3");
  });
});

describe("personPickerChoice", () => {
  it("the slot's own proposed answer is a yes", () => {
    expect(personPickerChoice(moderator("Martin", false), people("Martin")[0])).toEqual({ kind: "confirm" });
  });

  it("the slot's own confirmed answer changes nothing", () => {
    expect(personPickerChoice(moderator("Martin", true), people("Martin")[0])).toBeNull();
  });

  it("any other row is that person, never a rename", () => {
    const kerri = people("Martin", "Kerri")[1];
    expect(personPickerChoice(moderator("Martin", true), kerri)).toEqual({ kind: "person", row: kerri });
  });

  it("another person with the same name is still another person", () => {
    const other = { name: "Martin", code: "m2", person: "id-other" };
    expect(personPickerChoice(moderator("Martin", true), other)).toEqual({ kind: "person", row: other });
  });
});

describe("personPickerTyped and personPickerNameTaken", () => {
  it("a typed name is someone new; empty or unchanged is nothing", () => {
    expect(personPickerTyped(moderator("Martin", true), "  Mike ")).toEqual({ kind: "new", name: "Mike" });
    expect(personPickerTyped(moderator("Martin", true), "   ")).toBeNull();
    expect(personPickerTyped(moderator("Martin", true), "Martin")).toBeNull();
  });

  it("a participant's typed name names that participant", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "Mary", confirmed: true };
    expect(personPickerTyped(slot, "Mary A")).toEqual({ kind: "name", name: "Mary A" });
  });

  it("a name another person goes by is taken, in any case (§J8.11)", () => {
    const rows = people("Martin Storey", "Kerri");
    expect(personPickerNameTaken(moderator("", false, "m?"), rows, "martin storey")).toBe("Martin Storey");
    expect(personPickerNameTaken(moderator("Martin Storey", true), rows, "Martin Storey")).toBeNull();
    expect(personPickerNameTaken(moderator("", false, "m?"), rows, "Martin S")).toBeNull();
  });
});

describe("PersonPicker", () => {
  it("opens on the proposed answer: ticked, ringed, selected", () => {
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin", "Kerri")} onChoose={vi.fn()} onClose={vi.fn()} />);
    const [martin, kerri] = items();
    expect(martin.querySelector(".export-dropdown-check .bn-icon-check")).not.toBeNull();
    expect(martin.querySelector(".bn-person-proposed")).not.toBeNull();
    expect(kerri.querySelector(".export-dropdown-check .bn-icon-check")).toBeNull();
    expect(document.activeElement).toBe(martin);
  });

  it("a proposed answer says so to assistive tech, a confirmed one does not", () => {
    const { unmount } = render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin", "Kerri")} onChoose={vi.fn()} onClose={vi.fn()} />);
    const [martin, kerri] = items();
    expect(martin.getAttribute("aria-label")).toBe("m1, proposed name Martin");
    expect(kerri.getAttribute("aria-label")).toBeNull();
    unmount();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin")} onChoose={vi.fn()} onClose={vi.fn()} />);
    expect(items()[0].getAttribute("aria-label")).toBeNull();
  });

  it("Enter on the proposed answer says yes", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin")} onChoose={onChoose} onClose={onClose} />);
    fireEvent.keyDown(menu(), { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "confirm" });
    expect(onClose).toHaveBeenCalled();
  });

  it("Space on a row chooses it once", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin")} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.keyDown(items()[0], { key: " " });
    expect(onChoose).toHaveBeenCalledTimes(1);
    expect(onChoose).toHaveBeenCalledWith({ kind: "confirm" });
  });

  it("a key the picker handles does not reach the page's shortcuts", () => {
    const onDocKey = vi.fn();
    document.addEventListener("keydown", onDocKey);
    try {
      render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin")} onChoose={vi.fn()} onClose={vi.fn()} />);
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
        <PersonPicker slot={slot} labels={labels(slot)} known={people("Martin", "Kerri")} onChoose={vi.fn()} onClose={vi.fn()} />
      </span>,
    );
    const trigger = document.querySelector(".bn-person-picker-trigger");
    fireEvent.keyDown(menu(), { key: "Escape" });
    expect(document.activeElement).toBe(trigger);
    rerender(
      <span>
        <button type="button" className="bn-person-picker-trigger">m1</button>
        <PersonPicker key="again" slot={slot} labels={labels(slot)} known={people("Martin", "Kerri")} onChoose={vi.fn()} onClose={vi.fn()} />
      </span>,
    );
    expect(document.activeElement).not.toBe(trigger);
    fireEvent.click(items()[1]);
    expect(document.activeElement).toBe(trigger);
  });

  it("choosing another row picks that person", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.click(items()[1]);
    expect(onChoose).toHaveBeenCalledWith({ kind: "person", row: people("Martin", "Kerri")[1] });
  });

  it("every row shows its person's own code, and the new row the next free one (§J8.8)", () => {
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={vi.fn()} onClose={vi.fn()} />);
    const codes = Array.from(menu().querySelectorAll(".bn-speaker-badge-code")).map((c) => c.textContent);
    expect(codes).toEqual(["m1", "m2", "m3"]);
  });

  it("an unknown slot opens in the new-person field, and an empty Return does nothing (§J8.10)", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("", false, "m?")} labels={labels(moderator("", false, "m?"))} known={people("Martin")} onChoose={onChoose} onClose={vi.fn()} />);
    const field = screen.getByPlaceholderText("New moderator");
    expect(document.activeElement).toBe(field);
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).not.toHaveBeenCalled();
    fireEvent.keyDown(field, { key: "ArrowUp" });
    expect(document.activeElement).toBe(items()[0]);
  });

  it("a name another person already goes by is refused, and the picker stays open (§J8.11)", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("", false, "m?")} labels={labels(moderator("", false, "m?"))} known={people("Martin Storey")} onChoose={onChoose} onClose={onClose} />);
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "martin storey" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Martin Storey");
    expect(field.getAttribute("aria-invalid")).toBe("true");
    fireEvent.change(field, { target: { value: "Martin S" } });
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "new", name: "Martin S" });
  });

  it("only the speaker's own role is enabled: changing role is not built", () => {
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people()} onChoose={vi.fn()} onClose={vi.fn()} />);
    const [mod, part, obs] = screen.getAllByRole("radio") as HTMLButtonElement[];
    expect([mod.disabled, part.disabled, obs.disabled]).toEqual([false, true, true]);
    expect(mod.getAttribute("aria-checked")).toBe("true");
  });

  it("someone new is typed into the next badge's name half", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin")} onChoose={onChoose} onClose={vi.fn()} />);
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "Mike Alvarez" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "new", name: "Mike Alvarez" });
  });

  it("a participant's field is a new name for that participant", () => {
    const slot: PersonPickerSlot = { code: "p3", role: "participant", name: "Mary", confirmed: true };
    render(<PersonPicker slot={slot} labels={labels(slot)} known={[{ name: "Sarah", code: "p1" }]} onChoose={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByPlaceholderText("New name for p3")).toBeInTheDocument();
    expect(items()).toHaveLength(2); // Mary and the field
  });

  it("type-to-jump lands on any word of a name", () => {
    render(<PersonPicker slot={moderator("Martin Storey", true)} labels={labels(moderator("Martin Storey", true))} known={people("Martin Storey", "Kerri Ng")} onChoose={vi.fn()} onClose={vi.fn()} />);
    fireEvent.keyDown(menu(), { key: "n" });
    fireEvent.keyDown(menu(), { key: "g" });
    expect(document.activeElement).toBe(items()[1]);
  });

  it("the ✕ on the current row says not this person (§J8.8)", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={onChoose} onClose={vi.fn()} />);
    const clears = menu().querySelectorAll<HTMLButtonElement>(".bn-picker-clear");
    expect(clears).toHaveLength(1);
    expect(items()[0].contains(clears[0])).toBe(true);
    expect(clears[0].getAttribute("aria-label")).toBe("Not Martin");
    fireEvent.click(clears[0]);
    expect(onChoose).toHaveBeenCalledWith({ kind: "clear" });
  });

  it("Delete on the current row clears it; on another row it does nothing", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.keyDown(menu(), { key: "ArrowDown" });
    fireEvent.keyDown(menu(), { key: "Delete" });
    expect(onChoose).not.toHaveBeenCalled();
    fireEvent.keyDown(menu(), { key: "ArrowUp" });
    fireEvent.keyDown(menu(), { key: "Backspace" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "clear" });
  });

  it("an unknown speaker or a participant has no ✕", () => {
    render(<PersonPicker slot={moderator("", false, "m?")} labels={labels(moderator("", false, "m?"))} known={people("Martin")} onChoose={vi.fn()} onClose={vi.fn()} />);
    expect(menu().querySelector(".bn-picker-clear")).toBeNull();
  });

  it("a click on the current, confirmed row renames it in place (§J8.8)", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={onChoose} onClose={onClose} />);
    fireEvent.click(items()[0]);
    const field = items()[0].querySelector("input") as HTMLInputElement;
    expect(field.value).toBe("Martin");
    expect(document.activeElement).toBe(field);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.change(field, { target: { value: "Martyn" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).toHaveBeenCalledWith({ kind: "name", name: "Martyn" });
  });

  it("Return on the current, confirmed row renames too; Escape goes back to the list, open", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={onChoose} onClose={onClose} />);
    fireEvent.keyDown(menu(), { key: "Enter" });
    const field = items()[0].querySelector("input") as HTMLInputElement;
    expect(field).not.toBeNull();
    fireEvent.keyDown(field, { key: "Escape" });
    expect(items()[0].querySelector("input")).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
    expect(onChoose).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(items()[0]);
  });

  it("a proposed answer still confirms on click, it is not renamed", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin")} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.click(items()[0]);
    expect(onChoose).toHaveBeenCalledWith({ kind: "confirm" });
  });

  it("a rename to another person's name is refused in place; an unchanged one does nothing", () => {
    const onChoose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={people("Martin", "Kerri")} onChoose={onChoose} onClose={vi.fn()} />);
    fireEvent.click(items()[0]);
    const field = items()[0].querySelector("input") as HTMLInputElement;
    fireEvent.change(field, { target: { value: "kerri" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Kerri");
    fireEvent.change(field, { target: { value: "Martin" } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onChoose).not.toHaveBeenCalled();
    expect(items()[0].querySelector("input")).toBeNull();
  });

  describe("recoding a speaker's role (§J7 R1, R2)", () => {
    const byRole = {
      moderator: people("Martin", "Kerri"),
      participant: [],
      observer: [{ name: "Jane", code: "o1", person: "id-Jane" }],
    };
    const segments = () => screen.getAllByRole("radio") as HTMLButtonElement[];

    it("every segment is open on a moderator", () => {
      render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={byRole.moderator} knownByRole={byRole} onChoose={vi.fn()} onClose={vi.fn()} />);
      const [mod, part, obs] = segments();
      expect([mod.disabled, part.disabled, obs.disabled]).toEqual([false, false, false]);
    });

    it("browsing writes nothing, and lists the same person first, by the code they would carry", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={byRole.moderator} knownByRole={byRole} onChoose={onChoose} onClose={vi.fn()} />);
      fireEvent.click(segments()[2]);
      expect(onChoose).not.toHaveBeenCalled();
      expect(segments()[2].getAttribute("aria-checked")).toBe("true");
      const rows = items().map((li) => li.textContent);
      expect(rows[0]).toContain("o2Martin");
      expect(rows[1]).toContain("o1Jane");
      expect(screen.getByPlaceholderText("New observer")).toBeInTheDocument();
    });

    it("choosing the same person under Observer recodes the speaker", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={byRole.moderator} knownByRole={byRole} onChoose={onChoose} onClose={vi.fn()} />);
      fireEvent.click(segments()[2]);
      fireEvent.click(items()[0]);
      expect(onChoose).toHaveBeenCalledWith({
        kind: "person", role: "observer", row: { name: "Martin", code: "o2", person: "id-Martin" },
      });
    });

    it("someone new under Observer is a new observer", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={byRole.moderator} knownByRole={byRole} onChoose={onChoose} onClose={vi.fn()} />);
      fireEvent.keyDown(menu(), { key: "ArrowRight" });
      fireEvent.keyDown(menu(), { key: "ArrowRight" });
      expect(segments()[2].getAttribute("aria-checked")).toBe("true");
      const field = screen.getByPlaceholderText("New observer");
      fireEvent.change(field, { target: { value: "Dana" } });
      fireEvent.keyDown(field, { key: "Enter" });
      expect(onChoose).toHaveBeenCalledWith({ kind: "new", name: "Dana", role: "observer" });
    });

    it("a name an observer goes by is taken from a moderator's picker too", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={moderator("", false, "m?")} labels={labels(moderator("", false, "m?"))} known={byRole.moderator} knownByRole={byRole} onChoose={onChoose} onClose={vi.fn()} />);
      const field = screen.getByPlaceholderText("New moderator");
      fireEvent.change(field, { target: { value: "jane" } });
      fireEvent.keyDown(field, { key: "Enter" });
      expect(onChoose).not.toHaveBeenCalled();
    });

    const participants = [{ name: "Mary", code: "p1" }, { name: "Ann", code: "p2" }];
    const withParticipants = { ...byRole, participant: participants };
    const mary: PersonPickerSlot = { code: "p1", role: "participant", name: "Mary", confirmed: true };

    it("under Participant, a moderator is offered alone, numbered after every participant", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={moderator("Martin", true)} labels={labels(moderator("Martin", true))} known={byRole.moderator} knownByRole={withParticipants} onChoose={onChoose} onClose={vi.fn()} />);
      fireEvent.click(segments()[1]);
      expect(items().map((li) => li.textContent)[0]).toContain("p3Martin");
      expect(items().filter((li) => li.textContent?.includes("Mary"))).toHaveLength(0);
      expect(screen.getByPlaceholderText("New name for p3")).toBeInTheDocument();
      fireEvent.click(items()[0]);
      expect(onChoose).toHaveBeenCalledWith({
        kind: "person", role: "participant", row: { name: "Martin", code: "p3", person: "id-Martin" },
      });
    });

    it("a participant's picker opens every segment, and under Moderator offers the team", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={mary} labels={labels(mary)} known={participants} knownByRole={withParticipants} onChoose={onChoose} onClose={vi.fn()} />);
      const [mod, part, obs] = segments();
      expect([mod.disabled, part.disabled, obs.disabled]).toEqual([false, false, false]);
      fireEvent.click(mod);
      const rows = items().map((li) => li.textContent);
      expect(rows.some((r) => r?.includes("Mary"))).toBe(false);
      fireEvent.click(items()[0]);
      expect(onChoose).toHaveBeenCalledWith({
        kind: "person", role: "moderator", row: expect.objectContaining({ name: "Martin" }),
      });
    });

    it("a new moderator typed from a participant's picker may not take a team name", () => {
      const onChoose = vi.fn();
      render(<PersonPicker slot={mary} labels={labels(mary)} known={participants} knownByRole={withParticipants} onChoose={onChoose} onClose={vi.fn()} />);
      fireEvent.click(segments()[0]);
      const field = screen.getByPlaceholderText("New moderator");
      fireEvent.change(field, { target: { value: "jane" } });
      fireEvent.keyDown(field, { key: "Enter" });
      expect(onChoose).not.toHaveBeenCalled();
      fireEvent.change(field, { target: { value: "Mary" } });
      fireEvent.keyDown(field, { key: "Enter" });
      expect(onChoose).toHaveBeenCalledWith({ kind: "new", name: "Mary", role: "moderator" });
    });
  });

  it("Escape closes without choosing", () => {
    const onChoose = vi.fn();
    const onClose = vi.fn();
    render(<PersonPicker slot={moderator("Martin", false)} labels={labels(moderator("Martin", false))} known={people("Martin")} onChoose={onChoose} onClose={onClose} />);
    fireEvent.keyDown(menu(), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
    expect(onChoose).not.toHaveBeenCalled();
  });
});
