/**
 * Codebook v2 — the codebook page. Phase 3.
 *
 * The largest surface in the lens, and the one carrying three of the four
 * Indicative items in the fidelity map, so expect the buttons to move once they
 * are seen beside the shipped control. What is *not* indicative: the geometry
 * (two columns, the description's right edge meeting the graphic's), the three
 * shapes (**D20**), provenance (**D23**), the bleak empty state (**D26**), and
 * the Review door leading to the existing modal rather than a route (**Q15**).
 *
 * **Nothing here re-implements a tag row.** `Badge`, `MicroBar` and the colour
 * helpers are the shipped components, and the group markup emits the shipped
 * unscoped classes (`.codebook-group`, `.tag-row`, `.tag-bar-area`) so the
 * histogram alignment this repo has already paid for is inherited rather than
 * approximated. The one thing v2 adds CSS for is the page head, which has no
 * shipped equivalent.
 *
 * Scope: the **read** surface. The floor's authoring apparatus — add and delete
 * a group, add, rename and delete a tag, drag between groups — is lifted from
 * the shipped panel in a later step, deliberately: it is ~400 lines of
 * drag-and-drop whose value is that it already works.
 */

import { Badge } from "../components/Badge";
import { MicroBar } from "../components/MicroBar";
import { getBarColour, getTagBg } from "../utils/colours";
import { safeUrlOrNull } from "../utils/safeUrl";
import type { CodebookGroupResponse, TemplateOut } from "../utils/types";

export interface PageBook {
  id: string;
  title: string;
  provenance: string;
  provenanceIsPerson: boolean;
  floor: boolean;
  installed: boolean;
  enabled: boolean;
  pending: number;
  /** Distinct across the framework, not the sum of its groups (B6). */
  quotes: number;
  template?: TemplateOut;
}

interface Props {
  book: PageBook;
  groups: CodebookGroupResponse[];
  // Browse Library is NOT here: it lives on the zone-title row, which belongs
  // to the lens rather than to any one codebook. D22 makes it the unconditional
  // route to the catalogue, so it must not come and go with the selection.
  onReview: (frameworkId: string) => void;
  onInstall: (frameworkId: string) => void;
  onUninstall: (frameworkId: string) => void;
}

/**
 * Sentiment is permanent on the install axis and toggleable on the enable one
 * (**D20**). It arrives with the pipeline: there is nothing to install, and
 * uninstalling only destroys tags nothing can restore. The floor is not a
 * codebook you installed at all.
 */
const canInstall = (b: PageBook) => !b.floor && b.id !== "sentiment";

/** A door onto nothing is worse than no door (**D26**). */
const hasReviewDoor = (b: PageBook, tagCount: number) =>
  !b.floor && b.id !== "sentiment" && b.installed && tagCount > 0;

function TagRow({
  name,
  count,
  tentative,
  max,
  colourSet,
  index,
}: {
  name: string;
  count: number;
  tentative: number;
  max: number;
  colourSet: string;
  index: number;
}) {
  return (
    <div className="tag-row">
      <div className="tag-name-area">
        <Badge text={name} variant="readonly" colour={getTagBg(colourSet, index)} />
      </div>
      <div className="tag-bar-area">
        <MicroBar
          value={max > 0 ? count / max : 0}
          tentativeValue={max > 0 ? tentative / max : 0}
          colour={getBarColour(colourSet)}
          title={`${count} quotes${tentative ? `, ${tentative} undecided` : ""}`}
        />
        <span className="group-total-count">{count}</span>
      </div>
    </div>
  );
}

function Group({ group }: { group: CodebookGroupResponse }) {
  // The bar scale is the group's own busiest tag, matching the shipped panel:
  // a framework-wide scale would flatten a group whose counts are all small,
  // which is the comparison a researcher is actually making inside one card.
  const max = Math.max(
    1,
    ...group.tags.map((t) => t.count + (t.tentative_count ?? 0)),
  );
  return (
    <div className="codebook-group" style={{ background: `var(--bn-group-${group.colour_set}, var(--bn-group-none))` }}>
      <div className="group-title-area">
        <div className="group-title">
          <span className="group-title-text">{group.name}</span>
        </div>
        {group.subtitle && <div className="group-subtitle">{group.subtitle}</div>}
      </div>
      {group.tags.map((t, i) => (
        <TagRow
          key={t.id}
          name={t.name}
          count={t.count}
          tentative={t.tentative_count ?? 0}
          max={max}
          colourSet={group.colour_set}
          index={t.colour_index ?? i}
        />
      ))}
    </div>
  );
}

export function CodebookV2Page({
  book,
  groups,
  onReview,
  onInstall,
  onUninstall,
}: Props) {
  const tagCount = groups.reduce((n, g) => n + g.tags.length, 0);
  const tpl = book.template;
  const links = (tpl?.author_links ?? [])
    .map((l) => ({ label: l.label, href: safeUrlOrNull(l.url) }))
    .filter((l): l is { label: string; href: string } => l.href !== null);

  return (
    <div className={book.enabled ? undefined : "pageoff"} data-testid="bn-v2-page">
      <div className="pg-head">
        <div className="pg-headmain">
          <div>
            <div className="pg-title">{book.title}</div>
            {book.provenance && (
              <div
                className={`pg-author${book.provenanceIsPerson ? "" : " prov-system"}`}
              >
                {book.provenance}
              </div>
            )}
          </div>

          {hasReviewDoor(book, tagCount) ? (
            // The verb is the button; the counts are text on its baseline. A
            // sentence wearing a border is not a control, and it read as more
            // prominent than Install, which it must not be.
            <div className="pg-review-row">
              <button
                className="bn-btn bn-btn-sm"
                onClick={() => onReview(book.id)}
                data-testid="bn-v2-review"
              >
                Review
              </button>
              <span className="pg-review-meta">
                {tagCount} tags on {book.quotes} quotes
                {book.pending > 0 && (
                  <span className="undec"> &middot; {book.pending} undecided</span>
                )}
              </span>
            </div>
          ) : (
            <div className="pg-stat">
              {book.installed
                ? `${tagCount} tags${book.quotes ? ` on ${book.quotes} quotes` : ""}`
                : `${tagCount} tags · not installed`}
            </div>
          )}

          {tpl?.description && <p className="pg-desc">{tpl.description}</p>}
        </div>

        {/* A fixed-width gutter, not a fixed box (D13). What fills it — a
            jacket, initials, a headshot, nothing — is deferred per codebook;
            the reserved space is what the layout depends on. */}
        <div className="pg-side">
          <div className="pg-graphic" aria-hidden="true" />
          {canInstall(book) && (
            <div className="pg-actions">
              {book.installed ? (
                <button
                  className="bn-btn framework-remove-btn"
                  onClick={() => onUninstall(book.id)}
                  data-testid="bn-v2-uninstall"
                >
                  Uninstall
                </button>
              ) : (
                <button
                  className="bn-btn bn-btn-primary"
                  onClick={() => onInstall(book.id)}
                  data-testid="bn-v2-install"
                >
                  Install
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {(tpl?.author_bio || links.length > 0) && (
        <div className="preview-body-sidebar">
          <div className="preview-author">
            {book.provenanceIsPerson && (
              <div className="preview-author-name">{book.provenance}</div>
            )}
            {tpl?.author_bio && (
              <div className="preview-author-bio">{tpl.author_bio}</div>
            )}
            {links.length > 0 && (
              <div className="preview-author-links">
                {links.map((l) => (
                  <a
                    key={l.href}
                    href={l.href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {l.label} &#x2197;
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tagCount === 0 ? (
        // Bleak on purpose (D26): no illustration, no call to action, no
        // reframing of the absence as an opportunity. The fact is the message.
        <div className="pg-empty" data-testid="bn-v2-empty">
          This codebook has no tags.
        </div>
      ) : (
        <div className="v2-groups">
          {groups.map((g) => (
            <Group key={g.id} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}

export { canInstall as _canInstall, hasReviewDoor as _hasReviewDoor };
