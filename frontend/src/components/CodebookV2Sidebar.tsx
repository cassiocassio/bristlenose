/**
 * CodebookV2Sidebar — codebook navigation for the v2 lens, in the standard
 * left sidebar.
 *
 * WHY THIS REPLACED AN IN-LENS RAIL
 * ---------------------------------
 * v2 shipped its navigation as a `<nav className="v2-rail">` inside the lens's
 * own content column. That is not where this app puts content navigation, and
 * building it there meant rebuilding — badly — a component that already exists:
 * the left panel `SidebarLayout` renders for Quotes, Sessions, Codebooks and
 * Analysis. Everything that panel does was lost by being outside it:
 *
 *   - the toolbar toggle on macOS (`toggleLeftPanel`) and `[` in the SPA
 *   - drag-to-resize, with min/max clamping (`useDragResize`)
 *   - rail hover-to-peek and the overlay mode (`useTocOverlay`)
 *   - the `panel-state` bridge post, which is how the native View menu knows
 *     whether to say Show or Hide
 *   - the 6-column grid, so the lens's content never actually narrowed
 *
 * None of that is reimplementable per-lens, and none of it should be. The IA
 * this presents is unchanged — Manual tags / Default / Frameworks, one row per
 * codebook, provenance under the title. The container, the typography and the
 * behaviours are now the house ones.
 *
 * TYPOGRAPHY IS THE SHIPPED NAVIGATOR'S, NOT A V2 DIALECT
 * -------------------------------------------------------
 * `.toc-heading` for sections and `.toc-link` + `.codebook-toc-link` for rows,
 * exactly as `CodebookSidebar` uses them — so section headings, row size,
 * weight, hover underline and the selected state all come from
 * `theme/organisms/sidebar.css` rather than being restated here.
 *
 * The selected state is the one worth naming: the rail used
 * `--bn-colour-active-bg`, which is `#f0fdf4` — a mint green, the palette's
 * *success* background. `.toc-link.active` uses `--bn-nav-selection-bg` (a
 * neutral `#efefef`) with the accent colour and emphasis weight. Selection is
 * not success, and a navigator that tints its current row green is telling the
 * researcher something that is not true.
 *
 * THE SWITCH STAYS
 * ----------------
 * Enable/disable rides on the row, at the size settled during the prototype:
 * the platform `<input type="checkbox" switch>` where the browser has it, and a
 * 26×15 `.sw.mini` fallback where it does not. That is a deliberate departure
 * from `CodebookSidebar`'s status *dot* — v2's rail is where a codebook is
 * turned on and off, and the dot only reports.
 *
 * @module CodebookV2Sidebar
 */

import { useCallback, useEffect, useState } from "react";
import {
  apiGet,
  getCodebook,
  getCodebookTemplates,
  getFrameworkStates,
  putFrameworkStates,
} from "../utils/api";
import type { CodebookResponse, TemplateListResponse } from "../utils/types";
import { selectCodebookV2, useCodebookV2Store } from "../contexts/CodebookV2Store";
import { isExportMode } from "../utils/exportData";

// ── The platform switch ────────────────────────────────────────────────────

/** True when this browser renders the real platform switch. */
const NATIVE_SWITCH = (() => {
  if (typeof document === "undefined") return false;
  const probe = document.createElement("input");
  probe.type = "checkbox";
  return "switch" in probe;
})();

// ── Types ──────────────────────────────────────────────────────────────────

export interface V2NavBook {
  /** `framework_id`, or `""` for the floor. */
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
  /** Under "Default" rather than "Frameworks" — derived from an absent author. */
  builtIn: boolean;
}

// ── Enable control ─────────────────────────────────────────────────────────

function EnableControl({
  book,
  onToggle,
}: {
  book: V2NavBook;
  onToggle: (id: string, enabled: boolean) => void;
}) {
  // The floor is not a codebook you can switch off — it is your own tags.
  if (book.floor) return null;

  const stop = (e: { stopPropagation: () => void }) => e.stopPropagation();

  if (NATIVE_SWITCH) {
    return (
      <input
        className="enable"
        type="checkbox"
        // @ts-expect-error — `switch` is a real attribute in Safari 17.4+ and is
        // not yet in the React DOM typings. Rendering it is the point: this is
        // the platform control, not an approximation of one.
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

// ── Row ────────────────────────────────────────────────────────────────────

function Row({
  book,
  selected,
  onToggle,
  readOnly,
}: {
  book: V2NavBook;
  selected: boolean;
  onToggle: (id: string, enabled: boolean) => void;
  readOnly: boolean;
}) {
  return (
    // `.toc-link` + `.codebook-toc-link` are the shipped navigator's row — same
    // padding, radius, size, weight, hover underline and selected treatment.
    // `.v2-nav-row` adds only what a two-line row with a trailing control needs.
    // <a href="#"> is a JS action, not navigation; native Enter activation on
    // the anchor handles keyboard, as it does in CodebookSidebar.
    // eslint-disable-next-line jsx-a11y/anchor-is-valid
    <a
      href="#"
      className={`toc-link codebook-toc-link v2-nav-row${selected ? " active" : ""}${
        book.enabled ? "" : " codebook-disabled"
      }`}
      aria-current={selected ? "location" : undefined}
      onClick={(e) => {
        e.preventDefault();
        selectCodebookV2(book.id);
      }}
      data-testid={`bn-v2-nav-row-${book.id || "floor"}`}
    >
      <span className="v2-nav-text">
        <span className="codebook-toc-label">{book.title}</span>
        {book.provenance && (
          // A person keeps D19's weight; a system fact does not borrow it.
          <span
            className={`v2-nav-provenance${book.provenanceIsPerson ? "" : " prov-system"}`}
          >
            {book.provenance}
          </span>
        )}
      </span>
      {book.pending > 0 && <span className="v2-nav-pending">{book.pending}</span>}
      {!readOnly && <EnableControl book={book} onToggle={onToggle} />}
    </a>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export function CodebookV2Sidebar() {
  const { selectedId } = useCodebookV2Store();
  const [books, setBooks] = useState<V2NavBook[] | null>(null);
  const readOnly = isExportMode();

  const load = useCallback(() => {
    // One pass. `/codebook/templates` is SERVER_ONLY, so it is absent from an
    // export — tolerated separately (Q14): unavailable offline is not the same
    // as broken, and the navigator must still list what the reader has.
    // `/info` carries the project name, which the codebook payload does not,
    // and is the same source the shipped sidebar reads it from.
    Promise.all([
      getCodebook(),
      getCodebookTemplates().catch(() => null),
      getFrameworkStates(),
      apiGet<{ project_name: string }>("/info").catch(() => null),
    ])
      .then(([codebook, templates, states, info]) =>
        setBooks(
          buildBooks(codebook, templates, states, info?.project_name ?? ""),
        ),
      )
      .catch(() => setBooks([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The lens and this navigator both mutate the codebook (install, uninstall,
  // authoring), and neither owns the other. `codebook-changed` is the event the
  // shipped sidebar already listens on, so v2 joins that convention rather than
  // inventing a second one.
  useEffect(() => {
    const handler = () => load();
    window.addEventListener("codebook-changed", handler);
    return () => window.removeEventListener("codebook-changed", handler);
  }, [load]);

  const onToggle = useCallback((id: string, enabled: boolean) => {
    // Optimistic: the switch is the researcher's statement, not a request for
    // permission. A failure re-reads rather than silently reverting.
    setBooks((prev) =>
      prev ? prev.map((b) => (b.id === id ? { ...b, enabled } : b)) : prev,
    );
    putFrameworkStates({ [id]: enabled })
      .then(() => window.dispatchEvent(new CustomEvent("codebook-changed")))
      .catch(() => load());
  }, []);

  if (books === null) return null;

  const floor = books.filter((b) => b.floor);
  const builtIn = books.filter((b) => !b.floor && b.builtIn);
  const frameworks = books.filter((b) => !b.floor && !b.builtIn);

  // Unconditional (D25). Only Frameworks can actually be empty — the floor is
  // always one row and Default always holds sentiment, which D20 made
  // uninstallable — but all three are unconditional so the rule has no
  // exception to remember and no special case to get wrong later.
  const section = (label: string, rows: V2NavBook[]) => (
    <>
      <div className="toc-heading">{label}</div>
      {rows.map((b) => (
        <Row
          key={b.id || "floor"}
          book={b}
          selected={(b.id || "") === selectedId}
          onToggle={onToggle}
          readOnly={readOnly}
        />
      ))}
    </>
  );

  return (
    <nav aria-label="Codebooks" data-testid="bn-v2-nav">
      {section("Manual tags", floor)}
      {section("Default", builtIn)}
      {section("Frameworks", frameworks)}
    </nav>
  );
}

// ── Data shaping ───────────────────────────────────────────────────────────

/**
 * Build the navigator's rows.
 *
 * Exported for the test, and because the shape decisions live in one place:
 * built-in is derived from an ABSENT AUTHOR, never a hardcoded id list — a
 * hardcoded list files the next built-in under Frameworks silently.
 */
export function buildBooks(
  codebook: CodebookResponse,
  templates: TemplateListResponse | null,
  states: Record<string, boolean>,
  projectName: string,
): V2NavBook[] {
  const installed = new Set(
    codebook.groups
      .map((g) => g.framework_id)
      .filter((f): f is string => f != null),
  );
  const pendingByFramework: Record<string, number> = {};
  for (const g of codebook.groups) {
    if (!g.framework_id) continue;
    pendingByFramework[g.framework_id] =
      (pendingByFramework[g.framework_id] ?? 0) +
      g.tags.reduce((n, t) => n + (t.tentative_count ?? 0), 0);
  }

  const floorPending = codebook.groups
    .filter((g) => !g.framework_id)
    .reduce((n, g) => n + g.tags.reduce((m, t) => m + (t.tentative_count ?? 0), 0), 0);

  const rows: V2NavBook[] = [
    {
      id: "",
      title: projectName ? `${projectName} tags` : "Your tags",
      provenance: "",
      provenanceIsPerson: false,
      floor: true,
      enabled: true,
      pending: floorPending,
      builtIn: false,
    },
  ];

  // Installed-only (D17): a framework belongs here when it has groups in this
  // project, which is exactly what "installed" means. Driven off the CODEBOOK,
  // not the template list — `/codebook/templates` is SERVER_ONLY, so in an
  // export it is absent, and a navigator that listed nothing there would leave
  // the reader with a lens they cannot navigate (Q14).
  const byId = new Map((templates?.templates ?? []).map((t) => [t.id, t]));
  for (const fid of installed) {
    const tpl = byId.get(fid);
    const author = tpl?.author ?? "";
    rows.push({
      id: fid,
      title: tpl?.title ?? fid,
      provenance:
        author || (fid === "sentiment" ? "On by default" : "Available by default"),
      provenanceIsPerson: !!author,
      floor: false,
      enabled: states[fid] !== false,
      pending: pendingByFramework[fid] ?? 0,
      // Built-in is derived from an ABSENT AUTHOR, never a hardcoded id list —
      // a list files the next built-in under Frameworks silently.
      builtIn: !author.trim(),
    });
  }
  return rows;
}
