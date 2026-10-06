/**
 * PersonPicker — "who is this speaker?", the browser's picker for one speaker
 * slot in the Sessions grid (docs/design-people.md § UX iteration 3, v1.1).
 * The Mac app opens a native popover instead, from the same model
 * (`personPickerRows`), so the two cannot disagree about what is offered.
 *
 * As the owner set it (4 Oct 2026; revised 6 Oct, docs/design-people.md §J8):
 * - The current answer carries the menu's tick; a proposed answer also wears
 *   the dotted ring, and Enter on it says yes (`confirm`).
 * - Moderator and observer rows are the people known for that role across the
 *   study, each by their own code; a pick says this slot *is* that person.
 * - A participant's picker holds only that participant: choosing another
 *   participant would mean "the same person", a merge not built.
 * - The role segments show all three roles with only the current one enabled:
 *   changing a speaker's role is the §J recode, not built.
 * - Someone new is the next row: the next free code, with its name half as the
 *   field. An unknown speaker opens with the cursor there. A name another
 *   person in the list goes by is refused (§J8.11). No That's Me in the
 *   browser — there is no account to ask.
 * - Undo is ⌘Z, or picking again.
 */

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { PersonBadge } from "./PersonBadge";
import { Icon } from "./Icon";
import type { TFunction } from "i18next";

import {
  PICKER_ROLES,
  personPickerCanClear,
  personPickerCanRename,
  personPickerChoice,
  personPickerLabels,
  personPickerNameTaken,
  personPickerNewCode,
  personPickerRenamed,
  personPickerRolesOpen,
  personPickerRowsForRole,
  personPickerTyped,
  withName,
  type PersonPickerChoice,
  type PersonPickerLabels,
  type PersonPickerRow,
  type PersonPickerSlot,
  type PickerRole,
} from "../utils/personPicker";

const NEW = "\u0000new";

interface PersonPickerProps {
  slot: PersonPickerSlot;
  /** People known for this slot's role across the study (`personPickerRows`
   *  filters and orders them). */
  known: PersonPickerRow[];
  /** The people of the other roles, for browsing them to recode the speaker
   *  (§J7 R1). Without it the other role segments stay disabled. */
  knownByRole?: Partial<Record<PickerRole, PersonPickerRow[]>>;
  /** Its strings, localised by the caller (`personPickerLabels`): the same
   *  object the Mac app's native picker receives. */
  labels: PersonPickerLabels;
  onChoose: (choice: PersonPickerChoice) => void;
  onClose: () => void;
}

export function PersonPicker({ slot, known, knownByRole, labels, onChoose, onClose }: PersonPickerProps) {
  // The role being looked at. A segment click only browses (§J8.10): nothing
  // is written until a name is chosen under it.
  const [browsing, setBrowsing] = useState<PickerRole>(slot.role);
  const recoding = browsing !== slot.role;
  const knownFor = (role: PickerRole) => (role === slot.role ? known : knownByRole?.[role] ?? []);
  const everyone = [...known, ...Object.entries(knownByRole ?? {})
    .filter(([role]) => role !== slot.role && role !== "participant")
    .flatMap(([, rows]) => rows ?? [])];
  const people = personPickerRowsForRole(slot, browsing, knownFor(browsing));
  const keyOf = (r: PersonPickerRow) => r.person ?? `name:${r.name}`;
  const rows = [...people.map(keyOf), NEW];
  const own = recoding
    ? undefined
    : people.find((r) => (slot.person ? r.person === slot.person : r.name === slot.name));
  // The selection opens on the current answer. With no answer there is nothing
  // to confirm, so the cursor starts in the new-person field (§J8.10) — and a
  // single Return there, empty, does nothing.
  const [selected, setSelected] = useState<string | null>(own ? keyOf(own) : NEW);
  const [draft, setDraft] = useState("");
  const [taken, setTaken] = useState<string | null>(null);
  // Rename in place (§J8.8): the current, confirmed row's name as a field.
  const [renaming, setRenaming] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");
  const renameRef = useRef<HTMLInputElement>(null);
  const newCode = personPickerNewCode({ ...slot, role: browsing }, people);
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

  const finish = (choice: PersonPickerChoice | null) => {
    if (choice) onChoose(choice);
    returnFocus();
    onClose();
  };

  useEffect(() => {
    if (!renaming) return;
    renameRef.current?.focus();
    renameRef.current?.select();
  }, [renaming]);

  const choose = (key: string) => {
    const row = people.find((r) => keyOf(r) === key);
    if (!row) return;
    // The current, confirmed answer has nothing to choose, so a click or
    // Return on it is the rename, the way Finder renames a selected name.
    if (!recoding && personPickerCanRename(slot, row)) {
      if (!renaming) {
        setRenameDraft(row.name);
        setTaken(null);
        setRenaming(true);
      }
      return;
    }
    finish(personPickerChoice(slot, row, browsing));
  };

  const submitRename = () => {
    const clash = personPickerNameTaken(slot, everyone, renameDraft);
    if (clash) {
      setTaken(clash);
      return;
    }
    const choice = personPickerRenamed(slot, renameDraft);
    if (choice) finish(choice);
    else cancelRename();
  };

  const cancelRename = () => {
    setRenaming(false);
    setTaken(null);
    if (own) itemRefs.current[keyOf(own)]?.focus();
  };

  const submitDraft = () => {
    const clash = personPickerNameTaken(slot, everyone, draft);
    if (clash) {
      setTaken(clash);
      return;
    }
    finish(personPickerTyped(slot, draft, browsing));
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
    else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && knownByRole && open.length > 1) {
      // Left and right move between the roles a recode can browse (§J7 R1),
      // since the segments themselves take no Tab stop.
      handled();
      const i = open.indexOf(browsing);
      browse(open[(i + (e.key === "ArrowRight" ? 1 : open.length - 1)) % open.length]);
    }
    else if ((e.key === "Delete" || e.key === "Backspace") && own && selected === keyOf(own)) {
      if (personPickerCanClear(slot)) { handled(); finish({ kind: "clear" }); }
    }
    else if (e.key.length === 1 && /\S/.test(e.key) && !e.metaKey && !e.ctrlKey) {
      // Type-to-jump on any word of a name, the way a menu does.
      const now = e.timeStamp;
      typed.current.buffer = (now - typed.current.at < 800 ? typed.current.buffer : "") + e.key.toLowerCase();
      typed.current.at = now;
      const hit = people.find((r) =>
        r.name.toLowerCase().split(/\s+/).some((w) => w.startsWith(typed.current.buffer)),
      );
      if (hit) setSelected(keyOf(hit));
    }
  };

  const newPrompt = (recoding && labels.newPromptFor?.[browsing]) || labels.newPrompt;
  const open = personPickerRolesOpen(slot);
  const browse = (role: PickerRole) => {
    if (role === browsing) return;
    setBrowsing(role);
    setDraft("");
    setTaken(null);
    setRenaming(false);
    const first = personPickerRowsForRole(slot, role, knownFor(role))[0];
    setSelected(first ? keyOf(first) : NEW);
  };

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
              className={`dimension-btn${r === browsing ? " active" : ""}`}
              role="radio"
              aria-checked={r === browsing}
              disabled={r !== slot.role && (!open.includes(r) || !knownByRole)}
              onClick={() => browse(r)}
              tabIndex={-1}
            >
              {labels.roles[r]}
            </button>
          ))}
        </span>
      </li>
      {people.map((row) => {
        const key = keyOf(row);
        const isAnswer = row === own;
        return (
          // Keys are the list's (onListKey: arrows, Enter, Space, type-to-jump).
          // A key handler here as well chose twice on one Space press.
          // eslint-disable-next-line jsx-a11y/click-events-have-key-events
          <li
            key={key}
            ref={(el) => { itemRefs.current[key] = el; }}
            className="export-dropdown-item export-dropdown-scope"
            role="menuitemradio"
            aria-checked={isAnswer}
            aria-label={isAnswer && labels.proposed ? labels.proposed : undefined}
            tabIndex={-1}
            onClick={() => choose(key)}
          >
            <span className="export-dropdown-check" aria-hidden="true">{isAnswer && <Icon name="check" size="menu" />}</span>
            {isAnswer && renaming ? (
              <span className="bn-person-badge">
                <span className="bn-speaker-badge--split">
                  <span className="bn-speaker-badge-code">{row.code}</span>
                  <span className="bn-speaker-badge-name bn-picker-new-name">
                    <span aria-hidden="true">{renameDraft || row.name}</span>
                    <input
                      ref={renameRef}
                      aria-label={labels.menu}
                      aria-invalid={taken !== null}
                      aria-describedby={taken !== null ? "bn-picker-taken" : undefined}
                      value={renameDraft}
                      onChange={(e) => { setRenameDraft(e.target.value); setTaken(null); }}
                      onKeyDown={(e) => {
                        const handled = () => { e.preventDefault(); e.stopPropagation(); };
                        if (e.key === "Enter") { handled(); submitRename(); }
                        else if (e.key === "Escape") { handled(); cancelRename(); }
                      }}
                    />
                  </span>
                </span>
              </span>
            ) : isAnswer && !slot.confirmed ? (
              <span className="bn-person-proposed">
                <PersonBadge code={row.code} role={slot.role} name={row.name} />
              </span>
            ) : (
              <PersonBadge code={row.code} role={slot.role} name={row.name} />
            )}
            {isAnswer && !renaming && personPickerCanClear(slot) && (
              // "Not this person": shown on hover and on the selected row, and
              // on Delete or Backspace there. Not a list stop of its own.
              <button
                type="button"
                className="bn-picker-clear"
                tabIndex={-1}
                aria-label={withName(labels.notThisPerson, row.name)}
                title={withName(labels.notThisPerson, row.name)}
                onClick={(e) => { e.stopPropagation(); finish({ kind: "clear" }); }}
              >
                <Icon name="x" size="menu" />
              </button>
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
            <span className="bn-speaker-badge-code">{newCode}</span>
            <span className="bn-speaker-badge-name bn-picker-new-name">
              <span aria-hidden="true">{draft || newPrompt}</span>
              <input
                ref={(el) => { itemRefs.current[NEW] = el; }}
                placeholder={newPrompt}
                aria-label={newPrompt}
                aria-invalid={taken !== null}
                aria-describedby={taken !== null ? "bn-picker-taken" : undefined}
                value={draft}
                onChange={(e) => { setDraft(e.target.value); setTaken(null); }}
                onFocus={() => setSelected(NEW)}
                onKeyDown={(e) => {
                  const handled = () => { e.preventDefault(); e.stopPropagation(); };
                  if (e.key === "Enter") { handled(); submitDraft(); }
                  else if (e.key === "Escape") { handled(); dismiss(); }
                  else if (e.key === "ArrowUp") { handled(); move(-1); }
                }}
              />
            </span>
          </span>
        </span>
      </li>
      {taken !== null && (
        <li id="bn-picker-taken" className="export-dropdown-hint" role="alert">
          {withName(labels.nameTaken, taken)}
        </li>
      )}
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
