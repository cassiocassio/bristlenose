/**
 * Codebook v2 — the browse grid. Phase 4.
 *
 * The catalogue, per **D12**: title, provenance, version, description, a status
 * line, and **one button that swaps its verb** — Install out, Uninstall in, one
 * footprint. No enable toggle (**D11** — each control appears exactly once, and
 * enabling lives in the rail). No "New" badge, deliberately: that is a
 * store-merchandising device for a catalogue that turns over, and ours is nine
 * bundled codebooks that change rarely.
 *
 * **The whole card navigates; the button is the only region that does not.**
 *
 * Reuses the shipped `.picker-card*` classes wholesale — they already carry the
 * hover, the disabled state and the toggle's `min-width: 96px` that stops the
 * verb swap from resizing the button.
 */

import type { TemplateOut } from "../utils/types";
import { reachPhrase, vocabularyPhrase } from "../utils/codebookCounts";

export interface BrowseBook {
  id: string;
  title: string;
  /** A person, or where a built-in came from (D23). */
  provenance: string;
  provenanceIsPerson: boolean;
  installed: boolean;
  enabled: boolean;
  /** Distinct across the framework (B6), 0 when not installed. */
  quotes: number;
  tags: number;
  template?: TemplateOut;
}

interface Props {
  books: BrowseBook[];
  /** Scopes the reach count — "…applied to 2 quotes in Ikea". */
  projectName: string;
  onOpen: (id: string) => void;
  onInstall: (id: string) => void;
  onUninstall: (id: string) => void;
}

/** Sentiment cannot be installed or uninstalled (D20). */
const canInstall = (b: BrowseBook) => b.id !== "sentiment";

/**
 * D12 wants **9–18 words**; all nine shipped descriptions run 44–75, because
 * they were written for a full page.
 *
 * First sentence is what the design doc proposes as *"a useful starting draft,
 * not a rule"* — it lands in budget for 5 of 9, leaving sentiment (7w) and uxr
 * (8w) short and cli-ux (19w) and Plato (25w) long. Used here as the interim
 * because the alternatives are worse: the full text makes cards tall and
 * uneven, and D12 rules out truncation outright — *"truncating prose written
 * for a full page will read as truncated."*
 *
 * The real fix is **Q7**: one model field and nine hand-written lines. That is
 * content, not plumbing.
 */
function shortDescription(text: string): string {
  const stop = text.search(/\.\s/);
  return stop === -1 ? text : text.slice(0, stop + 1);
}


function Card({
  book,
  projectName,
  onOpen,
  onInstall,
  onUninstall,
}: {
  book: BrowseBook;
  projectName: string;
  onOpen: Props["onOpen"];
  onInstall: Props["onInstall"];
  onUninstall: Props["onUninstall"];
}) {
  const tpl = book.template;
  const version = (tpl as { version?: string } | undefined)?.version;
  const open = () => onOpen(book.id);

  return (
    <div
      // `off2`, not the shipped `disabled`: that class sets
      // `pointer-events: none`, and a switched-off codebook is still fully
      // interactive — you open it, you read it, you uninstall it. Different
      // state, different name (D27a).
      className={`picker-card${book.installed && !book.enabled ? " off2" : ""}`}
      role="button"
      tabIndex={0}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        open();
      }}
      data-testid={`bn-v2-card-${book.id}`}
    >
      <div className="picker-card-title">
        {book.title}
        {/* Version renders only if present — no dash, no placeholder (D12). */}
        {version && <span className="picker-card-version"> v{version}</span>}
      </div>

      {book.provenance && (
        <div
          className={`picker-card-author${book.provenanceIsPerson ? "" : " prov-system"}`}
        >
          {book.provenance}
        </div>
      )}

      {tpl?.description && (
        <div className="picker-card-desc">{shortDescription(tpl.description)}</div>
      )}

      <div className="picker-card-footrow">
        <span className="picker-card-status">
          {book.installed
            ? reachPhrase(book.tags, book.quotes, projectName)
            : vocabularyPhrase(book.tags)}
        </span>
        {/* Sentiment gets NO action and no substitute text. The first draft put
            "On by default" here, and the card then said it twice — the
            provenance line above already carries it, which is where "what is
            this and where did it come from" belongs. A second copy in the
            button's place is the absence of a control pretending to be one. */}
        {canInstall(book) ? (
          <button
            // INSTALL LEADS. The two were byte-identical at rest — the
            // uninstall modifier styles only `:hover` — so on a nine-card grid
            // the eye could not sort them without reading every label. Ranked
            // by what you came to do rather than by danger: this is a
            // catalogue, installing is the frequent intent, and Uninstall is
            // already gated by a sheet that measures what it costs. Painting it
            // red here would warn about something this click cannot do, and the
            // house rule keeps `.destructive` for what was NOT chosen, in the
            // confirm. Chosen from `docs/mockups/button-catalogue.html` §5 (D).
            className={`bn-btn ${
              book.installed
                ? "bn-btn-secondary picker-card-toggle picker-card-toggle-uninstall"
                : "bn-btn-primary picker-card-toggle"
            }`}
            // The one region of the card that does not navigate (D12).
            onClick={(e) => {
              e.stopPropagation();
              (book.installed ? onUninstall : onInstall)(book.id);
            }}
            data-testid={`bn-v2-card-action-${book.id}`}
          >
            {book.installed ? "Uninstall" : "Install"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function CodebookV2Browse({
  books,
  projectName,
  onOpen,
  onInstall,
  onUninstall,
}: Props) {
  return (
    <div data-testid="bn-v2-browse-grid">
      <div className="v2-card-grid">
        {books.map((b) => (
          <Card
            key={b.id}
            book={b}
            projectName={projectName}
            onOpen={onOpen}
            onInstall={onInstall}
            onUninstall={onUninstall}
          />
        ))}
      </div>
    </div>
  );
}

export { shortDescription as _shortDescription };
