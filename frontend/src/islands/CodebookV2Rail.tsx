/**
 * Codebook v2 — the rail. Phase 2.
 *
 * Three sections, installed-only, per **D17**: the shipped panel's IA, filtered
 * to what the researcher has. The headings are **unconditional** (**D25**) — an
 * absent heading does not read as "empty", it reads as "this category does not
 * exist", and the empty Frameworks heading paired with Browse Library is what
 * makes the first-run rail self-explaining without instructional copy.
 *
 * The enable control is the **platform switch** where the platform has one
 * (**D15**): Safari 17.4+ renders `<input type="checkbox" switch>` as the real
 * thing — real spring, real focus ring, honours Increase Contrast and Reduce
 * Motion — and ours is the fallback, not the default. Trailing, at 26×15
 * (**D16**), both measured rather than designed; the receipts are in
 * `docs/mockups/codebook-v2-parity.html` and `-rail.html`.
 *
 * Three shapes, not two (**D20**): the floor has no switch, sentiment has a
 * switch but no install, a framework has both.
 */

import type { CodebookGroupResponse, TemplateOut } from "../utils/types";

/** True when this browser renders the real platform switch. */
const NATIVE_SWITCH = (() => {
  if (typeof document === "undefined") return false;
  const probe = document.createElement("input");
  probe.type = "checkbox";
  return "switch" in probe;
})();

export interface RailBook {
  /** framework_id, or "" for the floor. */
  id: string;
  title: string;
  /** A person for a framework; for a built-in, where it came from (D23). */
  provenance: string;
  /** True when the provenance is a name and gets the D19 weight. */
  provenanceIsPerson: boolean;
  /** The researcher's own tags — no switch, no install (D20). */
  floor: boolean;
  enabled: boolean;
  /** Undecided proposals, for the count badge (D10). */
  pending: number;
}

interface Props {
  books: RailBook[];
  selectedId: string;
  onSelect: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
  /** Built-in ids — everything under "Default" rather than "Frameworks". */
  builtinIds: ReadonlySet<string>;
}

function EnableControl({
  book,
  onToggle,
}: {
  book: RailBook;
  onToggle: Props["onToggle"];
}) {
  // The floor is not a codebook you can switch off — it is your own tags.
  if (book.floor) return null;

  const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

  if (NATIVE_SWITCH) {
    return (
      <input
        className="enable"
        type="checkbox"
        // @ts-expect-error — `switch` is a real attribute in Safari 17.4+ and
        // is not yet in the React DOM typings. Rendering it is the point: this
        // is the platform control, not an approximation of one.
        switch=""
        checked={book.enabled}
        aria-label={book.title}
        onClick={stop}
        onChange={(e) => onToggle(book.id, e.target.checked)}
      />
    );
  }
  return (
    <span
      className={`sw mini ${book.enabled ? "" : "offstate"}`}
      role="switch"
      tabIndex={0}
      aria-checked={book.enabled}
      aria-label={book.title}
      onClick={(e) => {
        stop(e);
        onToggle(book.id, !book.enabled);
      }}
      onKeyDown={(e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        stop(e);
        onToggle(book.id, !book.enabled);
      }}
    />
  );
}

function Row({
  book,
  selected,
  onSelect,
  onToggle,
}: {
  book: RailBook;
  selected: boolean;
  onSelect: Props["onSelect"];
  onToggle: Props["onToggle"];
}) {
  return (
    <div
      className={`sb-row ${book.enabled ? "" : "off2"} ${selected ? "sel" : ""}`}
      role="button"
      tabIndex={0}
      aria-current={selected ? "true" : undefined}
      onClick={() => onSelect(book.id)}
      onKeyDown={(e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        onSelect(book.id);
      }}
      data-testid={`bn-v2-rail-row-${book.id || "floor"}`}
    >
      <span className="lbl2">
        <span className="r-title">{book.title}</span>
        {book.provenance && (
          // A person keeps D19's weight; a system fact does not borrow it.
          <span className={`r-author${book.provenanceIsPerson ? "" : " prov-system"}`}>
            {book.provenance}
          </span>
        )}
      </span>
      {book.pending > 0 && <span className="pcount">{book.pending}</span>}
      <EnableControl book={book} onToggle={onToggle} />
    </div>
  );
}

export function CodebookV2Rail({
  books,
  selectedId,
  onSelect,
  onToggle,
  builtinIds,
}: Props) {
  const floor = books.filter((b) => b.floor);
  const builtIn = books.filter((b) => !b.floor && builtinIds.has(b.id));
  const frameworks = books.filter((b) => !b.floor && !builtinIds.has(b.id));

  // Unconditional (D25). Only Frameworks can actually be empty — the floor is
  // always one row and Default always holds sentiment, which D20 made
  // uninstallable — but all three are unconditional so the rule has no
  // exception to remember and no special case to get wrong later.
  const section = (label: string, rows: RailBook[]) => (
    <>
      <div className="sb-h">{label}</div>
      {rows.map((b) => (
        <Row
          key={b.id || "floor"}
          book={b}
          selected={(b.id || "") === selectedId}
          onSelect={onSelect}
          onToggle={onToggle}
        />
      ))}
    </>
  );

  return (
    <nav className="v2-rail" aria-label="Codebooks" data-testid="bn-v2-rail">
      {section("Manual tags", floor)}
      {section("Default", builtIn)}
      {section("Frameworks", frameworks)}
    </nav>
  );
}

/** Exported for the test — the shape decisions live in one place. */
export const _NATIVE_SWITCH = NATIVE_SWITCH;

export type { CodebookGroupResponse, TemplateOut };
