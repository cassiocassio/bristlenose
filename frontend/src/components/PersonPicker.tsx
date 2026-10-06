/**
 * PersonPicker — "who is this speaker?", the browser's picker for one speaker
 * slot in the Sessions grid (docs/design-people.md § UX iteration 3, v1.1).
 * The Mac app opens a native popover instead, from the same model
 * (`personPickerRows`), so the two cannot disagree about what is offered.
 *
 * v1.1, as the owner set it (4 Oct 2026):
 * - The current answer carries the menu's tick; a proposed answer also wears
 *   the dotted ring, and Enter on it says yes (`confirm`).
 * - Moderator and observer rows are the names known for that role across the
 *   study, every row carrying this slot's own code ("this session's m1 is…"),
 *   because project-wide person codes are route C Phase 1, not built.
 * - A participant's picker holds only that participant: choosing another
 *   participant's name would mean "the same person", a merge not built.
 * - The role segments show all three roles with only the current one enabled:
 *   changing a speaker's role is the §J recode, not built.
 * - Someone new is the next row: this slot's code, with its name half as the
 *   field. No That's Me in the browser — there is no account to ask.
 * - Undo is picking again.
 */

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { PersonBadge } from "./PersonBadge";
import { Icon } from "./Icon";
import type { TFunction } from "i18next";

import {
  PICKER_ROLES,
  personPickerChoice,
  personPickerLabels,
  personPickerRows,
  type PersonPickerChoice,
  type PersonPickerLabels,
  type PersonPickerSlot,
} from "../utils/personPicker";

const NEW = "\u0000new";

interface PersonPickerProps {
  slot: PersonPickerSlot;
  /** Names known for this slot's role across the study (`personPickerRows`
   *  filters and orders them). */
  knownNames: string[];
  /** Its strings, localised by the caller (`personPickerLabels`): the same
   *  object the Mac app's native picker receives. */
  labels: PersonPickerLabels;
  onChoose: (choice: PersonPickerChoice) => void;
  onClose: () => void;
}

export function PersonPicker({ slot, knownNames, labels, onChoose, onClose }: PersonPickerProps) {
  const names = personPickerRows(slot, knownNames);
  const rows = [...names, NEW];
  // The selection opens on the current answer; with no answer, nothing is
  // pre-selected, so a single Return cannot confirm a guess.
  const [selected, setSelected] = useState<string | null>(slot.name && names.includes(slot.name) ? slot.name : null);
  const [draft, setDraft] = useState("");
  const menuRef = useRef<HTMLUListElement>(null);
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  const typed = useRef({ buffer: "", at: 0 });

  // The keyboard selection is real focus, so the shipped :focus styles draw it.
  useEffect(() => {
    if (selected) itemRefs.current[selected]?.focus();
    else menuRef.current?.focus();
  }, [selected]);

  // Click outside closes, as a menu does. The speaker the picker hangs from is
  // not outside: its badge toggles the picker and its pencil hands over to the
  // inline editor, and both say so themselves.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const anchor = menuRef.current?.parentElement;
      if (anchor && !anchor.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [onClose]);

  // A choice or Escape hands focus back to the badge, as a menu button does;
  // a click elsewhere leaves it where the click put it.
  const returnFocus = () =>
    menuRef.current?.parentElement
      ?.querySelector<HTMLElement>(".bn-person-picker-trigger")
      ?.focus();

  const choose = (name: string) => {
    const choice = personPickerChoice(slot, name);
    if (choice) onChoose(choice);
    returnFocus();
    onClose();
  };

  const dismiss = () => {
    returnFocus();
    onClose();
  };

  const move = (delta: number) => {
    const i = selected === null ? (delta > 0 ? -1 : rows.length) : rows.indexOf(selected);
    const next = rows[Math.min(Math.max(i + delta, 0), rows.length - 1)];
    setSelected(next);
  };

  const onListKey = (e: KeyboardEvent<HTMLUListElement>) => {
    const tag = (e.target as HTMLElement).tagName;
    if (tag === "INPUT" || tag === "BUTTON") return;
    // A key the picker handles goes no further: the page's own shortcuts
    // listen on document (Escape there also clears the search).
    const handled = () => { e.preventDefault(); e.stopPropagation(); };
    if (e.key === "ArrowDown") { handled(); move(1); }
    else if (e.key === "ArrowUp") { handled(); move(-1); }
    else if (e.key === "Enter" || e.key === " ") {
      handled();
      if (selected && selected !== NEW) choose(selected);
    }
    else if (e.key === "Escape") { handled(); dismiss(); }
    else if (e.key.length === 1 && /\S/.test(e.key) && !e.metaKey && !e.ctrlKey) {
      // Type-to-jump on any word of a name, the way a menu does.
      const now = e.timeStamp;
      typed.current.buffer = (now - typed.current.at < 800 ? typed.current.buffer : "") + e.key.toLowerCase();
      typed.current.at = now;
      const hit = names.find((n) =>
        n.toLowerCase().split(/\s+/).some((w) => w.startsWith(typed.current.buffer)),
      );
      if (hit) setSelected(hit);
    }
  };

  const newPrompt = labels.newPrompt;

  return (
    <ul
      ref={menuRef}
      className="export-dropdown-menu bn-person-picker"
      role="menu"
      aria-label={labels.menu}
      tabIndex={-1}
      onKeyDown={onListKey}
    >
      <li className="bn-picker-head" role="none">
        <span className="dimension-toggle" role="radiogroup" aria-label={labels.roleGroup}>
          {PICKER_ROLES.map((r) => (
            <button
              key={r}
              type="button"
              className={`dimension-btn${r === slot.role ? " active" : ""}`}
              role="radio"
              aria-checked={r === slot.role}
              disabled={r !== slot.role}
              tabIndex={-1}
            >
              {labels.roles[r]}
            </button>
          ))}
        </span>
      </li>
      {names.map((name) => {
        const isAnswer = name === slot.name;
        return (
          // Keys are the list's (onListKey: arrows, Enter, Space, type-to-jump).
          // A key handler here as well chose twice on one Space press.
          // eslint-disable-next-line jsx-a11y/click-events-have-key-events
          <li
            key={name}
            ref={(el) => { itemRefs.current[name] = el; }}
            className="export-dropdown-item export-dropdown-scope"
            role="menuitemradio"
            aria-checked={isAnswer}
            aria-label={isAnswer && labels.proposed ? labels.proposed : undefined}
            tabIndex={-1}
            onClick={() => choose(name)}
          >
            <span className="export-dropdown-check" aria-hidden="true">{isAnswer && <Icon name="check" size="menu" />}</span>
            {isAnswer && !slot.confirmed ? (
              <span className="bn-person-proposed">
                <PersonBadge code={slot.code} role={slot.role} name={name} />
              </span>
            ) : (
              <PersonBadge code={slot.code} role={slot.role} name={name} />
            )}
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
            <span className="bn-speaker-badge-code">{slot.code}</span>
            <span className="bn-speaker-badge-name bn-picker-new-name">
              <span aria-hidden="true">{draft || newPrompt}</span>
              <input
                ref={(el) => { itemRefs.current[NEW] = el; }}
                placeholder={newPrompt}
                aria-label={newPrompt}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onFocus={() => setSelected(NEW)}
                onKeyDown={(e) => {
                  const handled = () => { e.preventDefault(); e.stopPropagation(); };
                  if (e.key === "Enter") { handled(); choose(draft); }
                  else if (e.key === "Escape") { handled(); dismiss(); }
                  else if (e.key === "ArrowUp") { handled(); move(-1); }
                }}
              />
            </span>
          </span>
        </span>
      </li>
    </ul>
  );
}

/**
 * The picker as the Sessions grid opens it: the strings are built here, inside
 * this lazily-loaded module, so the grid — part of first paint — carries none
 * of the picker's code until someone opens it. `t` is the grid's own.
 */
export function PersonPickerPopover({
  t,
  ...props
}: Omit<PersonPickerProps, "labels"> & { t: TFunction }) {
  return <PersonPicker {...props} labels={personPickerLabels(props.slot, t)} />;
}
