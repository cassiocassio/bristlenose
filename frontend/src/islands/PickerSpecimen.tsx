/**
 * PickerSpecimen — the web half of Diagnostics ▸ Picker Lab.
 *
 * The moderator-identity picker (docs/design-people.md, "UX iteration 3"),
 * built from the shipped classes and the real `PersonBadge`, so it renders
 * with the real tokens under the real `data-platform`. The Mac app shows it
 * beside an AppKit twin in a real NSPopover; the point of the pair is to judge
 * web against native on the actual rendering, not on a mockup of either.
 *
 * The native half draws its person with the house native badge
 * (`SpeakerBadgeView`), so nothing here is sent across; this page is the
 * report's own look, unchanged by the native popover's menu hybrid.
 *
 * Route always registered at /report/picker-specimen and lazy-loaded, like
 * /report/specimen; reachable only from the Diagnostics menu. English-only by
 * design (a dev tool). The rules in PROPOSED_CSS are the proposal under test:
 * none of them ship, and each composes shipped tokens and classes.
 */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";

import { PersonBadge } from "../components/PersonBadge";

type Role = "moderator" | "participant" | "observer";
interface Person { code: string; name: string }

const ROLES: { id: Role; label: string; prefix: string; newLabel: string }[] = [
  { id: "moderator", label: "Moderator", prefix: "m", newLabel: "New moderator" },
  { id: "participant", label: "Participant", prefix: "p", newLabel: "New participant" },
  { id: "observer", label: "Observer", prefix: "o", newLabel: "New observer" },
];

const KNOWN: Record<Role, Person[]> = {
  moderator: [{ code: "m1", name: "Martin B Storey" }, { code: "m2", name: "Kerri Ng" }],
  participant: [
    { code: "p1", name: "Sarah Chen" }, { code: "p2", name: "Dr Amara Nwosu" },
    { code: "p3", name: "Mary Adeyemi" }, { code: "p4", name: "Marrian Boateng" },
    { code: "p5", name: "Mary Okafor" }, { code: "p6", name: "Mickael Hurley" },
  ],
  observer: [{ code: "o1", name: "Jane Smith" }],
};

const ME = "Martin Storey";
/** The row for someone new, in the list after the people it would join. */
const NEW = "new";

/** The slot's answer: who it is, and whether a person has said yes. */
interface Answer { code: string; name: string; confirmed: boolean }

export interface Scenario { role: Role; answer: Answer | null }

/** The same four the native half offers; chosen in the lab's toolbar, which
 *  reloads this page with `?scenario=<name>`. */
export const SCENARIOS: Record<string, Scenario> = {
  proposed: { role: "moderator", answer: { code: "m1", name: "Martin B Storey", confirmed: false } },
  confirmed: { role: "moderator", answer: { code: "m1", name: "Martin B Storey", confirmed: true } },
  unknown: { role: "moderator", answer: null },
  participant: { role: "participant", answer: { code: "p3", name: "Mary Adeyemi", confirmed: false } },
};

/** The shipped menu tick: ExportDropdown's check gutter draws a plain ✓ in
 *  text colour, the web counterpart of a Mac menu's checkmark. */
const CHECK = "\u2713";
const PERSON_CHECK = (
  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="8" cy="6.5" r="3" /><path d="M2.5 16.5c.6-3 2.8-4.6 5.5-4.6 1.2 0 2.3.3 3.2.9" /><path d="M12.5 15l2 2 3.5-4" />
  </svg>
);

/* The proposal under test. Everything here composes shipped tokens/classes. */
const PROPOSED_CSS = `
.bn-picker-lab { padding: 1.5rem; display: flex; flex-direction: column; align-items: flex-start; gap: .6rem; }
.bn-picker-lab .bn-picker-anchor { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: .5rem; }
/* One dotted ring while proposed (design-people.md, iteration 3). */
.badge-proposed .bn-speaker-badge--split { border: 1px dashed currentColor; }
.badge-proposed .bn-speaker-badge-code,
.badge-proposed .bn-speaker-badge-name { border: none; }
/* Three segments: the shipped toggle draws its divider for two. */
.bn-person-picker .dimension-toggle { display: flex; width: 100%; }
.bn-person-picker .dimension-btn { flex: 1; }
.bn-person-picker .dimension-btn:first-child { border-right: none; }
.bn-person-picker .dimension-btn + .dimension-btn { border-left: 1px solid var(--bn-colour-border); }
.bn-person-picker .bn-picker-me svg { width: 1em; height: 1em; vertical-align: -0.125em; }
.bn-person-picker .bn-picker-me svg { color: var(--bn-colour-accent); flex: none; }
/* The Export menu's box, opened in place for the lab. */
.bn-person-picker.export-dropdown-menu { position: static; margin: 0; }
.bn-person-picker .bn-picker-head { padding: 0.4rem 0.85rem; list-style: none; }
/* Someone new is the next badge: the code it will get, and its name half as the
   field. The name half sizes to its text (a hidden copy sets the width, the
   input lies over it), so typing grows a badge like the ones above. */
.bn-person-picker .bn-picker-new-name { display: inline-grid; }
.bn-person-picker .bn-picker-new-name > * { grid-area: 1 / 1; font: inherit; white-space: pre; }
.bn-person-picker .bn-picker-new-name > span { visibility: hidden; min-width: 2ch; }
.bn-person-picker .bn-picker-new-name > input {
  width: 100%; min-width: 0; padding: 0; border: none; background: none; color: inherit; outline: none;
}
.bn-person-picker .bn-picker-new-name > input::placeholder { color: var(--bn-colour-muted); }
.bn-person-picker .bn-picker-new:focus-within { background: var(--bn-colour-hover); }
`;

/** The scenario the page opens on. The lab puts it in the URL rather than
 *  pushing it after load, so a reload, a project switch or a slow chunk can
 *  never leave the two halves on different scenarios. */
function initialScenario(): Scenario {
  const name = new URLSearchParams(window.location.search).get("scenario") ?? "proposed";
  return SCENARIOS[name] ?? SCENARIOS.proposed;
}

export function PickerSpecimen() {
  const [start] = useState(initialScenario);
  const [people, setPeople] = useState<Record<Role, Person[]>>(KNOWN);
  const [role, setRole] = useState<Role>(start.role);
  const [answer, setAnswer] = useState<Answer | null>(start.answer);
  const [open, setOpen] = useState(true);
  const [selected, setSelected] = useState<string>(start.answer?.code ?? KNOWN[start.role][0].code);
  const [draft, setDraft] = useState("");
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const typed = useRef({ buffer: "", at: 0 });

  const rowsFor = useCallback(
    (r: Role) => [...people[r].map((p) => p.code), NEW, ...(r === "participant" ? [] : ["me"])],
    [people],
  );
  const rows = rowsFor(role);
  const prefix = ROLES.find((r) => r.id === role)!.prefix;
  /** The code someone new would get: the next number in this role. */
  const nextCode = `${prefix}${people[role].length + 1}`;

  // The keyboard selection is real focus, so the shipped :focus styles draw it.
  useEffect(() => {
    if (open) itemRefs.current[selected]?.focus();
  }, [open, selected, role]);

  const choose = (id: string) => {
    if (id === "me") setAnswer({ code: meCode(), name: ME, confirmed: true });
    else {
      const p = people[role].find((x) => x.code === id);
      if (p) setAnswer({ code: p.code, name: p.name, confirmed: true });
    }
    setOpen(false);
  };

  /** That's Me answers this slot, so it keeps the slot's role prefix. */
  const meCode = () => (answer?.code.startsWith(prefix) ? answer.code : nextCode);

  const create = () => {
    const name = draft.trim();
    if (!name) return;
    const code = nextCode;
    setPeople((prev) => ({ ...prev, [role]: [...prev[role], { code, name }] }));
    setAnswer({ code, name, confirmed: true });
    setDraft("");
    setOpen(false);
  };

  const onListKey = (e: KeyboardEvent<HTMLUListElement>) => {
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "BUTTON") return;
    const i = rows.indexOf(selected);
    if (e.key === "ArrowDown") { e.preventDefault(); setSelected(rows[Math.min(i + 1, rows.length - 1)]); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSelected(rows[Math.max(i - 1, 0)]); }
    else if (e.key === "Enter") { e.preventDefault(); if (selected !== NEW) choose(selected); }
    else if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
    else if (e.key.length === 1 && /\S/.test(e.key) && !e.metaKey && !e.ctrlKey) {
      // Type-to-jump, on code or name, the way a menu does.
      const now = e.timeStamp;
      typed.current.buffer = (now - typed.current.at < 800 ? typed.current.buffer : "") + e.key.toLowerCase();
      typed.current.at = now;
      const hit = people[role].find(
        (p) => p.code.startsWith(typed.current.buffer) || p.name.toLowerCase().startsWith(typed.current.buffer),
      );
      if (hit) setSelected(hit.code);
    }
  };

  const roleMeta = ROLES.find((r) => r.id === role)!;

  return (
    <div className="bn-picker-lab">
      <style>{PROPOSED_CSS}</style>
      <button type="button" className="bn-picker-anchor" onClick={() => setOpen((o) => !o)}>
        {answer ? (
          <BadgeFor code={answer.code} name={answer.name} proposed={!answer.confirmed} />
        ) : (
          <span className="bn-speaker-editable-name unnamed">{roleMeta.label}</span>
        )}
      </button>
      {open && (
        <ul className="export-dropdown-menu bn-person-picker" role="menu" onKeyDown={onListKey}>
          <li className="bn-picker-head">
            <span className="dimension-toggle" role="radiogroup" aria-label="Role">
              {ROLES.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={`dimension-btn${r.id === role ? " active" : ""}`}
                  role="radio"
                  aria-checked={r.id === role}
                  onClick={() => { setRole(r.id); setSelected(rowsFor(r.id)[0]); }}
                >
                  {r.label}
                </button>
              ))}
            </span>
          </li>
          {people[role].map((p) => {
            const isAnswer = answer?.code === p.code && answer.name === p.name;
            return (
              <li
                key={p.code}
                ref={(el) => { itemRefs.current[p.code] = el; }}
                className="export-dropdown-item export-dropdown-scope"
                role="menuitemradio"
                aria-checked={isAnswer}
                tabIndex={-1}
                onClick={() => choose(p.code)}
                onKeyDown={(e) => { if (e.key === " ") { e.preventDefault(); choose(p.code); } }}
              >
                <span className="export-dropdown-check" aria-hidden="true">{isAnswer ? CHECK : ""}</span>
                <BadgeFor code={p.code} name={p.name} proposed={isAnswer && !answer!.confirmed} />
              </li>
            );
          })}
          <li
            className="export-dropdown-item export-dropdown-scope bn-picker-new"
            role="none"
            onClick={() => setSelected(NEW)}
          >
            <span className="export-dropdown-check" aria-hidden="true" />
            <span className="bn-person-badge">
              <span className="bn-speaker-badge--split">
                <span className="bn-speaker-badge-code">{nextCode}</span>
                <span className="bn-speaker-badge-name bn-picker-new-name">
                  <span aria-hidden="true">{draft || roleMeta.newLabel}</span>
                  <input
                    ref={(el) => { itemRefs.current[NEW] = el; }}
                    placeholder={roleMeta.newLabel}
                    aria-label={roleMeta.newLabel}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onFocus={() => setSelected(NEW)}
                    onKeyDown={(e) => {
                      const i = rows.indexOf(NEW);
                      if (e.key === "Enter") { e.preventDefault(); create(); }
                      else if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
                      else if (e.key === "ArrowUp") { e.preventDefault(); setSelected(rows[Math.max(i - 1, 0)]); }
                      else if (e.key === "ArrowDown" && i < rows.length - 1) { e.preventDefault(); setSelected(rows[i + 1]); }
                    }}
                  />
                </span>
              </span>
            </span>
          </li>
          {role !== "participant" && <li className="export-dropdown-separator" role="separator" />}
          {role !== "participant" && (
            <li
              ref={(el) => { itemRefs.current.me = el; }}
              className="export-dropdown-item export-dropdown-scope bn-picker-me"
              role="menuitem"
              tabIndex={-1}
              onClick={() => choose("me")}
              onKeyDown={(e) => { if (e.key === " ") { e.preventDefault(); choose("me"); } }}
            >
              <span className="export-dropdown-check" aria-hidden="true">{answer?.name === ME ? CHECK : ""}</span>
              {PERSON_CHECK}
              <span>That’s Me ({ME})</span>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function BadgeFor({ code, name, proposed }: { code: string; name: string; proposed: boolean }) {
  const role = code.startsWith("m") ? "moderator" : code.startsWith("o") ? "observer" : "participant";
  // PersonBadge takes no extra class, so the proposed ring hangs off a wrapper.
  return proposed ? (
    <span className="badge-proposed">
      <PersonBadge code={code} role={role} name={name} />
    </span>
  ) : (
    <PersonBadge code={code} role={role} name={name} />
  );
}
