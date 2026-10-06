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
  personPickerOffersNew,
  personPickerNewCode,
  personPickerRenamed,
  personPickerRolesOpen,
  personPickerRowsForRole,
  personPickerTyped,
  newPromptUnder,
  withName,
  type PersonPickerChoice,
  type PersonPickerLabels,
  type PersonPickerRow,
  type PersonPickerSlot,
  type PersonPickerSwap,
  type PickerRole,
  type PickerSessionSpeaker,
  type ParagraphTarget,
} from "../utils/personPicker";

const NEW = "\u0000new";
const SWAP = "\u0000swap";

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
  /** The speaker this one would swap with (§J7 call 4), when the session has
   *  exactly one participant and one moderator. */
  swap?: PersonPickerSwap;
  /** The transcript's scope switch (design-people.md §K): present only on a
   *  paragraph's badge. On Paragraph the picker answers "who said this one?"
   *  from this session's speakers; on Session it is the picker as everywhere
   *  else. */
  scope?: PickerScope;
  onChoose: (choice: PersonPickerChoice) => void;
  onClose: () => void;
}

export interface PickerScope {
  paragraph: boolean;
  speakers: PickerSessionSpeaker[];
  onScope: (paragraph: boolean) => void;
  /** Credit the paragraph to a speaker of the session, or to a new moderator. */
  onMove: (to: ParagraphTarget) => void;
}

export function PersonPicker(props: PersonPickerProps) {
  return props.scope?.paragraph
    ? <ParagraphPicker {...props} scope={props.scope} />
    : <SessionPicker {...props} />;
}

/** The scope words: plain text, the chosen one semibold (owner, 6 Oct 2026),
 *  so they read as a heading over the role toggle. A radio group: the chosen
 *  word is the Tab stop and the arrows move between them. */
function ScopeHead({ scope, labels, onEscape }: {
  scope: PickerScope; labels: PersonPickerLabels; onEscape: () => void;
}) {
  const words: [boolean, string][] = [[false, labels.scope.session], [true, labels.scope.paragraph]];
  return (
    <li className="bn-picker-scope" role="none">
      <span role="radiogroup" aria-label={labels.scope.group}>
        {words.map(([paragraph, word]) => (
          <button
            key={word}
            type="button"
            className="bn-picker-scope-btn"
            role="radio"
            aria-checked={paragraph === scope.paragraph}
            data-text={word}
            tabIndex={paragraph === scope.paragraph ? 0 : -1}
            onClick={() => scope.onScope(paragraph)}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                onEscape();
                return;
              }
              if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
              e.preventDefault();
              e.stopPropagation();
              // The other scope's picker mounts and takes focus into its rows;
              // hand it back to the chosen word once it has, so the arrows keep
              // moving between the two words.
              const anchor = e.currentTarget.closest(".bn-person-picker-anchor") ?? document;
              scope.onScope(!scope.paragraph);
              setTimeout(() => {
                anchor.querySelector<HTMLElement>('.bn-picker-scope-btn[aria-checked="true"]')?.focus();
              }, 0);
            }}
          >
            {word}
          </button>
        ))}
      </span>
    </li>
  );
}

/**
 * "Who said this one?" — the Paragraph scope (design-people.md §K). Lists this
 * session's speakers by role; a pick credits the one paragraph to them. No
 * rename (a name is the person's, everywhere) and no ✕. Under Moderator the
 * last row is a new moderator, unknown, for a call collapsed into one voice:
 * named afterwards from the paragraph's badge, as any unknown speaker is.
 */
function ParagraphPicker({ slot, labels, onClose, scope }: PersonPickerProps & { scope: PickerScope }) {
  const current = scope.speakers.find((s) => s.code === slot.code);
  const [browsing, setBrowsing] = useState<PickerRole>(current?.role ?? slot.role);
  const rows = scope.speakers.filter((s) => s.role === browsing);
  const [selected, setSelected] = useState<string | null>(
    (rows.find((r) => r.code === slot.code) ?? rows[0])?.slot ?? null,
  );
  const menuRef = useRef<HTMLUListElement>(null);
  const itemRefs = useRef<Record<string, HTMLElement | null>>({});
  // Moderator is always open: its new-moderator row is how a session with
  // none gets one.
  const roles = PICKER_ROLES.filter(
    (r) => r === "moderator" || scope.speakers.some((s) => s.role === r),
  );
  const keys = [...rows.map((r) => r.slot), ...(browsing === "moderator" ? [NEW] : [])];

  useEffect(() => {
    if (selected) itemRefs.current[selected]?.focus();
    else menuRef.current?.focus();
  }, [selected]);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const anchor = menuRef.current?.parentElement;
      if (anchor && !anchor.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [onClose]);

  const finish = (target: string | null) => {
    if (target === NEW) scope.onMove({ new: "moderator" });
    else if (target && target !== current?.slot) scope.onMove({ slot: target });
    menuRef.current?.parentElement?.querySelector<HTMLElement>(".bn-person-picker-trigger")?.focus();
    onClose();
  };

  const browse = (role: PickerRole) => {
    setBrowsing(role);
    setSelected(scope.speakers.find((s) => s.role === role)?.slot ?? (role === "moderator" ? NEW : null));
  };

  const onListKey = (e: KeyboardEvent<HTMLUListElement>) => {
    if ((e.target as HTMLElement).tagName === "BUTTON") return;
    const handled = () => { e.preventDefault(); e.stopPropagation(); };
    const i = selected === null ? -1 : keys.indexOf(selected);
    if (e.key === "ArrowDown") { handled(); setSelected(keys[Math.min(i + 1, keys.length - 1)] ?? null); }
    else if (e.key === "ArrowUp") { handled(); setSelected(keys[Math.max(i - 1, 0)] ?? null); }
    else if (e.key === "Enter" || e.key === " ") { handled(); finish(selected); }
    else if (e.key === "Escape") { handled(); finish(null); }
    else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && roles.length > 1) {
      handled();
      const at = roles.indexOf(browsing);
      browse(roles[(at + (e.key === "ArrowRight" ? 1 : roles.length - 1)) % roles.length]);
    }
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
      <ScopeHead scope={scope} labels={labels} onEscape={() => finish(null)} />
      <li className="bn-picker-head" role="none">
        <span className="dimension-toggle" role="radiogroup" aria-label={labels.roleGroup}>
          {PICKER_ROLES.map((r) => (
            <button
              key={r}
              type="button"
              className={`dimension-btn${r === browsing ? " active" : ""}`}
              role="radio"
              aria-checked={r === browsing}
              disabled={!roles.includes(r)}
              onClick={() => browse(r)}
              tabIndex={-1}
            >
              {labels.roles[r]}
            </button>
          ))}
        </span>
      </li>
      {rows.map((row) => {
        const isAnswer = row.code === slot.code;
        return (
          // eslint-disable-next-line jsx-a11y/click-events-have-key-events
          <li
            key={row.slot}
            ref={(el) => { itemRefs.current[row.slot] = el; }}
            className="export-dropdown-item export-dropdown-scope"
            role="menuitemradio"
            aria-checked={isAnswer}
            tabIndex={-1}
            onClick={() => finish(row.slot)}
          >
            <span className="export-dropdown-check" aria-hidden="true">{isAnswer && <Icon name="check" size="menu" />}</span>
            <PersonBadge code={row.code} role={row.role} name={row.name} />
          </li>
        );
      })}
      {browsing === "moderator" && (
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events
        <li
          ref={(el) => { itemRefs.current[NEW] = el; }}
          className="export-dropdown-item export-dropdown-scope bn-picker-new"
          role="menuitem"
          tabIndex={-1}
          onClick={() => finish(NEW)}
        >
          <span className="export-dropdown-check" aria-hidden="true" />
          <span className="bn-person-badge">
            <span className="bn-speaker-badge--split">
              <span className="bn-speaker-badge-code">m?</span>
              <span className="bn-speaker-badge-name unnamed">{labels.newPromptFor?.moderator ?? labels.newPrompt}</span>
            </span>
          </span>
        </li>
      )}
    </ul>
  );
}

function SessionPicker({ slot, known, knownByRole, labels, onChoose, onClose, swap, scope }: PersonPickerProps) {
  // The role being looked at. A segment click only browses (§J8.10): nothing
  // is written until a name is chosen under it.
  const [browsing, setBrowsing] = useState<PickerRole>(slot.role);
  const recoding = browsing !== slot.role;
  const knownFor = (role: PickerRole) => (role === slot.role ? known : knownByRole?.[role] ?? []);
  // The team, whose names may not repeat (§J8.11); participants may.
  const everyone = [...knownFor("moderator"), ...knownFor("observer")];
  const people = personPickerRowsForRole(slot, browsing, knownFor(browsing));
  const keyOf = (r: PersonPickerRow) => r.person ?? `name:${r.name}`;
  // The swap is an act on this speaker as they are, so it is offered under
  // their own role only.
  const swapRow = swap && !recoding ? swap : undefined;
  const offersNew = personPickerOffersNew(slot, browsing);
  const rows = [...people.map(keyOf), ...(swapRow ? [SWAP] : []), ...(offersNew ? [NEW] : [])];
  const own = recoding
    ? undefined
    : people.find((r) => (slot.person ? r.person === slot.person : r.name === slot.name));
  // The picker opens with the current name as a field, selected, so typing
  // replaces it (owner, 6 Oct 2026); Tab or an arrow moves to the list. With
  // no answer, the cursor starts in the new-person field (§J8.10) — and a
  // single Return there, empty, does nothing.
  const [selected, setSelected] = useState<string | null>(own ? keyOf(own) : NEW);
  const [draft, setDraft] = useState("");
  const [taken, setTaken] = useState<string | null>(null);
  // Rename in place (§J8.8): the current row's name as a field.
  const [renaming, setRenaming] = useState(() => !!own && personPickerCanRename(slot, own));
  const [renameDraft, setRenameDraft] = useState(() => own?.name ?? "");
  const renameRef = useRef<HTMLInputElement>(null);
  const newCode = personPickerNewCode(
    browsing === slot.role ? slot : { ...slot, role: browsing, code: "p?" },
    people,
    knownFor(browsing),
  );
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
    if (key === SWAP && swapRow) {
      finish({ kind: "swap", slot: swapRow.slot });
      return;
    }
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

  /** Leave the name field for the list, as Tab or an arrow does. */
  const leaveRename = (delta: number) => {
    setRenaming(false);
    setTaken(null);
    if (!own) return;
    const i = rows.indexOf(keyOf(own));
    const next = rows[Math.min(Math.max(i + delta, 0), rows.length - 1)];
    setSelected(next);
    itemRefs.current[next]?.focus();
  };

  const submitDraft = () => {
    const clash = personPickerNameTaken(slot, everyone, draft, browsing);
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

  const newPrompt = newPromptUnder(labels, browsing, recoding, newCode);
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
      {scope && <ScopeHead scope={scope} labels={labels} onEscape={dismiss} />}
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
                        // Escape abandons the edit and the picker, as it
                        // would a menu: the field is where the picker opens.
                        else if (e.key === "Escape") { handled(); dismiss(); }
                        else if (e.key === "ArrowDown" || (e.key === "Tab" && !e.shiftKey)) { handled(); leaveRename(1); }
                        else if (e.key === "ArrowUp" || (e.key === "Tab" && e.shiftKey)) { handled(); leaveRename(-1); }
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
            {isAnswer && personPickerCanClear(slot) && (
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
      {swapRow && (
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events
        <li
          ref={(el) => { itemRefs.current[SWAP] = el; }}
          className="export-dropdown-item export-dropdown-scope bn-picker-swap"
          role="menuitem"
          tabIndex={-1}
          onClick={() => choose(SWAP)}
        >
          <span className="export-dropdown-check" aria-hidden="true" />
          {labels.swapWith.replace("{{code}}", swapRow.code)}
        </li>
      )}
      {offersNew && (
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
      )}
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
