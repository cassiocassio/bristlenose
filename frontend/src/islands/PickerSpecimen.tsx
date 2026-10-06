/**
 * PickerSpecimen — the web half of Diagnostics ▸ Picker Lab.
 *
 * The production `PersonPicker` (the browser's "who is this speaker?",
 * docs/design-people.md § UX iteration 3), opened from a badge on fixture
 * names, so the lab shows the Mac app's native picker beside exactly what the
 * browser ships. The native half draws its own person with the house badge,
 * so nothing is sent across from here.
 *
 * Route always registered at /report/picker-specimen and lazy-loaded, like
 * /report/specimen; reachable only from the Diagnostics menu. English-only by
 * design (a dev tool).
 */

import { useState } from "react";

import { PersonBadge } from "../components/PersonBadge";
import { PersonPicker } from "../components/PersonPicker";
import type {
  PersonPickerLabels,
  PersonPickerRow,
  PersonPickerSlot,
  PickerRole,
} from "../utils/personPicker";

/** The people the study knows, per role. */
const KNOWN: Record<PickerRole, PersonPickerRow[]> = {
  moderator: [
    { name: "Martin B Storey", code: "m1", person: "lab-martin" },
    { name: "Kerri Ng", code: "m2", person: "lab-kerri" },
  ],
  participant: [
    { name: "Sarah Chen", code: "p1" },
    { name: "Dr Amara Nwosu", code: "p2" },
    { name: "Mary Adeyemi", code: "p3" },
  ],
  observer: [{ name: "Jane Smith", code: "o1", person: "lab-jane" }],
};

/** The same four the native half offers; chosen in the lab's toolbar, which
 *  reloads this page with `?scenario=<name>`. */
const SCENARIOS: Record<string, PersonPickerSlot> = {
  proposed: { code: "m1", role: "moderator", name: "Martin B Storey", confirmed: false, person: "lab-martin" },
  confirmed: { code: "m1", role: "moderator", name: "Martin B Storey", confirmed: true, person: "lab-martin" },
  unknown: { code: "m1", role: "moderator", name: "", confirmed: false },
  participant: { code: "p3", role: "participant", name: "Mary Adeyemi", confirmed: false },
};

/** The scenario the page opens on. The lab puts it in the URL rather than
 *  pushing it after load, so a reload, a project switch or a slow chunk can
 *  never leave the two halves on different scenarios. */
function initialScenario(): PersonPickerSlot {
  const name = new URLSearchParams(window.location.search).get("scenario") ?? "proposed";
  return SCENARIOS[name] ?? SCENARIOS.proposed;
}

/** English, as Grid Specimen is: a page that imports no i18n keeps the
 *  first-paint chunks as they were (a translation import here split
 *  `useTranslation` out of the landing bundle, measured 4 Oct 2026). */
function labels(slot: PersonPickerSlot): PersonPickerLabels {
  return {
    roles: { moderator: "Moderator", participant: "Participant", observer: "Observer" },
    roleGroup: "Role",
    newPrompt:
      slot.role === "moderator" ? "New moderator"
      : slot.role === "observer" ? "New observer"
      : `New name for ${slot.code}`,
    thatsMe: null,
    menu: `Edit name for ${slot.code}`,
    proposed: slot.name && !slot.confirmed ? `${slot.code}, proposed name ${slot.name}` : null,
    nameTaken: "{{name}} is already in the list. Pick them, or add something to tell the two apart.",
    notThisPerson: "Not {{name}}",
  };
}

export function PickerSpecimen() {
  const [slot, setSlot] = useState<PersonPickerSlot>(initialScenario);
  const [known, setKnown] = useState(KNOWN);
  const [open, setOpen] = useState(true);

  const proposed = !!slot.name && !slot.confirmed;

  return (
    <div className="bn-picker-lab">
      <span className="bn-session-speaker-entry bn-person-picker-anchor">
        <button
          type="button"
          className={`bn-person-picker-trigger${proposed ? " bn-person-proposed" : ""}`}
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
        >
          <PersonBadge code={slot.code} role={slot.role} name={slot.name || undefined} />
        </button>
        {open && (
          <PersonPicker
            slot={slot}
            known={known[slot.role]}
            labels={labels(slot)}
            onChoose={(choice) => {
              if (choice.kind === "person") {
                const { row } = choice;
                setSlot({ ...slot, code: row.code, name: row.name, person: row.person, confirmed: true });
              } else if (choice.kind === "new" || choice.kind === "name") {
                const person = choice.kind === "new" ? `lab-${known[slot.role].length + 1}` : slot.person;
                const row = { name: choice.name, code: slot.code, person };
                setSlot({ ...slot, name: choice.name, person, confirmed: true });
                setKnown({ ...known, [slot.role]: [...known[slot.role], row] });
              } else if (choice.kind === "clear") {
                setSlot({ ...slot, name: "", person: undefined, confirmed: false });
              } else {
                setSlot({ ...slot, confirmed: true });
              }
            }}
            onClose={() => setOpen(false)}
          />
        )}
      </span>
    </div>
  );
}
