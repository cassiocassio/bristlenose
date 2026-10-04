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
import type { PersonPickerLabels, PersonPickerSlot, PickerRole } from "../utils/personPicker";

/** The names the study knows, per role. */
const KNOWN: Record<PickerRole, string[]> = {
  moderator: ["Martin B Storey", "Kerri Ng"],
  participant: ["Sarah Chen", "Dr Amara Nwosu", "Mary Adeyemi"],
  observer: ["Jane Smith"],
};

/** The same four the native half offers; chosen in the lab's toolbar, which
 *  reloads this page with `?scenario=<name>`. */
const SCENARIOS: Record<string, PersonPickerSlot> = {
  proposed: { code: "m1", role: "moderator", name: "Martin B Storey", confirmed: false },
  confirmed: { code: "m1", role: "moderator", name: "Martin B Storey", confirmed: true },
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
            knownNames={known[slot.role]}
            labels={labels(slot)}
            onChoose={(choice) => {
              const name = choice.kind === "name" ? choice.name : slot.name;
              setSlot({ ...slot, name, confirmed: true });
              if (!known[slot.role].includes(name)) {
                setKnown({ ...known, [slot.role]: [...known[slot.role], name] });
              }
            }}
            onClose={() => setOpen(false)}
          />
        )}
      </span>
    </div>
  );
}
