/**
 * PickerSpecimen — the web half of Diagnostics ▸ Picker Lab.
 *
 * The moderator-identity picker (docs/design-people.md, "UX iteration 3"),
 * built from the shipped classes and the real `PersonBadge`, so it renders
 * with the real tokens under the real `data-platform`. The Mac app shows it
 * beside an AppKit twin in a real NSPopover; the point of the pair is to judge
 * web against native on the actual rendering, not on a mockup of either.
 *
 * It also measures the real badges (`probeBadgeStyles`) and posts them over
 * the production `search-badge-styles` message, so the native half draws its
 * badges from what this page resolved — the same path the search chips use
 * (docs/design-search.md §7a). Nothing on the native side holds a colour.
 *
 * Route always registered at /report/picker-specimen and lazy-loaded, like
 * /report/specimen; reachable only from the Diagnostics menu. English-only by
 * design (a dev tool). The rules in PROPOSED_CSS are the proposal under test:
 * none of them ship, and each composes shipped tokens and classes.
 */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";

import { PersonBadge } from "../components/PersonBadge";
import { useAppearanceSignature } from "../components/NativeSearchSync";
import { postSearchBadgeStyles } from "../shims/bridge";
import { probeBadgeStyles } from "../utils/badgeStyle";

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

/** The slot's answer: who it is, and whether a person has said yes. */
interface Answer { code: string; name: string; confirmed: boolean }

export interface Scenario { role: Role; answer: Answer | null }

/** The same four the native half offers; set from the lab's toolbar. */
export const SCENARIOS: Record<string, Scenario> = {
  proposed: { role: "moderator", answer: { code: "m1", name: "Martin B Storey", confirmed: false } },
  confirmed: { role: "moderator", answer: { code: "m1", name: "Martin B Storey", confirmed: true } },
  unknown: { role: "moderator", answer: null },
  participant: { role: "participant", answer: { code: "p3", name: "Mary Adeyemi", confirmed: false } },
};

const CHECK = (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3.5 8.5l3 3 6-7" />
  </svg>
);
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
/* The tick, only in the picker, in the shipped check gutter. */
.bn-person-picker .bn-picker-tick { color: var(--bn-colour-positive); }
.bn-person-picker .export-dropdown-check svg,
.bn-person-picker .bn-picker-me svg { width: 1em; height: 1em; vertical-align: -0.125em; }
.bn-person-picker .bn-picker-me svg { color: var(--bn-colour-accent); flex: none; }
/* The Export menu's box, opened in place for the lab. */
.bn-person-picker.export-dropdown-menu { position: static; margin: 0; }
.bn-person-picker .bn-picker-head,
.bn-person-picker .bn-picker-field { padding: 0.4rem 0.85rem; list-style: none; }
.bn-person-picker .bn-picker-field .tag-input-box {
  display: block; font-family: var(--bn-font-body); font-size: var(--bn-text-label);
  border-color: var(--bn-colour-border); background: var(--bn-colour-bg);
}
.bn-person-picker .bn-picker-field .tag-input-box:focus-within { border-color: var(--bn-field-edit-edge); }
.bn-person-picker .bn-picker-field .tag-input { width: 100%; font: inherit; }
`;

declare global {
  interface Window { __pickerLab?: { setScenario: (name: string) => void } }
}

export function PickerSpecimen() {
  const [people, setPeople] = useState<Record<Role, Person[]>>(KNOWN);
  const [role, setRole] = useState<Role>("moderator");
  const [answer, setAnswer] = useState<Answer | null>(SCENARIOS.proposed.answer);
  const [open, setOpen] = useState(true);
  const [selected, setSelected] = useState<string>("m1");
  const [draft, setDraft] = useState("");
  const itemRefs = useRef<Record<string, HTMLLIElement | null>>({});
  const typed = useRef({ buffer: "", at: 0 });
  const appearance = useAppearanceSignature(true);

  const rowsFor = useCallback(
    (r: Role) => [...people[r].map((p) => p.code), ...(r === "participant" ? [] : ["me"])],
    [people],
  );
  const rows = rowsFor(role);

  const applyScenario = useCallback((s: Scenario) => {
    setRole(s.role);
    setAnswer(s.answer);
    setSelected(s.answer?.code ?? KNOWN[s.role][0].code);
    setDraft("");
    setOpen(true);
  }, []);

  useEffect(() => {
    window.__pickerLab = { setScenario: (name) => SCENARIOS[name] && applyScenario(SCENARIOS[name]) };
    return () => { delete window.__pickerLab; };
  }, [applyScenario]);

  // The keyboard selection is real focus, so the shipped :focus styles draw it.
  useEffect(() => {
    if (open) itemRefs.current[selected]?.focus();
  }, [open, selected, role]);

  // Measure the real badges and hand them to the native half.
  useEffect(() => {
    const host = document.getElementById("bn-app-root") ?? document.body;
    const all = Object.values(people).flat();
    const timer = window.setTimeout(() => {
      postSearchBadgeStyles(probeBadgeStyles(host, { tags: [], people: all }));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [people, appearance]);

  const choose = (id: string) => {
    if (id === "me") setAnswer({ code: answer?.code ?? "m1", name: ME, confirmed: true });
    else {
      const p = people[role].find((x) => x.code === id);
      if (p) setAnswer({ code: p.code, name: p.name, confirmed: true });
    }
    setOpen(false);
  };

  const create = () => {
    const name = draft.trim();
    if (!name) return;
    const prefix = ROLES.find((r) => r.id === role)!.prefix;
    const code = `${prefix}${people[role].length + 1}`;
    setPeople((prev) => ({ ...prev, [role]: [...prev[role], { code, name }] }));
    setAnswer({ code, name, confirmed: true });
    setDraft("");
    setOpen(false);
  };

  const onListKey = (e: KeyboardEvent<HTMLUListElement>) => {
    if ((e.target as HTMLElement).tagName === "INPUT") return;
    const i = rows.indexOf(selected);
    if (e.key === "ArrowDown") { e.preventDefault(); setSelected(rows[Math.min(i + 1, rows.length - 1)]); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSelected(rows[Math.max(i - 1, 0)]); }
    else if (e.key === "Enter") { e.preventDefault(); choose(selected); }
    else if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
    else if (e.key.length === 1 && /\S/.test(e.key) && !e.metaKey && !e.ctrlKey) {
      // Type-to-jump, on code or name, the way a menu does.
      const now = Date.now();
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
                onMouseEnter={() => setSelected(p.code)}
              >
                <span className={`export-dropdown-check${isAnswer ? " bn-picker-tick" : ""}`}>{isAnswer && CHECK}</span>
                <BadgeFor code={p.code} name={p.name} proposed={isAnswer && !answer!.confirmed} />
              </li>
            );
          })}
          <li className="export-dropdown-separator" role="separator" />
          {role !== "participant" && (
            <li
              ref={(el) => { itemRefs.current.me = el; }}
              className="export-dropdown-item export-dropdown-scope bn-picker-me"
              role="menuitem"
              tabIndex={-1}
              onClick={() => choose("me")}
              onKeyDown={(e) => { if (e.key === " ") { e.preventDefault(); choose("me"); } }}
              onMouseEnter={() => setSelected("me")}
            >
              <span className="export-dropdown-check" />
              {PERSON_CHECK}
              <span>That’s Me ({ME})</span>
            </li>
          )}
          <li className="bn-picker-field">
            <span className="tag-input-box">
              <input
                className="tag-input"
                placeholder={roleMeta.newLabel}
                aria-label={roleMeta.newLabel}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); create(); } }}
              />
            </span>
          </li>
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
