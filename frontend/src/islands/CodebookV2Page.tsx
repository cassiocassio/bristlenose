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
 * **Nothing here re-implements a tag row, or a group.** The cards are
 * `CodebookGroupColumn` from `components/CodebookAuthoring.tsx` — the shipped
 * lens's own component, not a copy of it — so the histogram alignment, the
 * inline rename, the drag-to-merge and every confirmation this repo has already
 * paid for are inherited rather than approximated. The one thing v2 adds CSS
 * for is the page head, which has no shipped equivalent.
 *
 * The page had its own read-only `Group`/`TagRow` while the authoring apparatus
 * was still inside the shipped island; both were deleted on 30 Aug 2026 when it
 * came out. Two renderers for one card is the drift this lens exists to avoid.
 *
 * **Authoring follows the group, not the page.** `CodebookGroupColumn` reads
 * `is_default` / `framework_id` / export mode and decides for itself what is
 * editable, so a framework's groups are read-only here for exactly the reason
 * they are read-only in the shipped lens — one rule, in one place, rather than
 * each lens remembering.
 */

// By path, not through the `components` barrel: the barrel is in the chunk the
// landing route loads, and this apparatus is reachable only from the two lazy
// codebook islands.
import {
  CodebookGroupColumn,
  NewGroupPlaceholder,
} from "../components/CodebookAuthoring";
import type { CodebookAuthoring } from "../hooks/useCodebookAuthoring";
import { safeUrlOrNull } from "../utils/safeUrl";
import type { CodebookGroupResponse, TemplateOut } from "../utils/types";
import { renderLead } from "../utils/leadSentence";

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
  /**
   * The shared authoring apparatus. Passed for every codebook, not just the
   * floor: the group column knows which of its own controls apply, and a lens
   * that decided instead would be a second place for that rule to be wrong.
   */
  authoring: CodebookAuthoring;
  /** Every tag name in the codebook — the add-tag field excludes duplicates. */
  allTagNames: string[];
  /** Export mode — the artefact is read-only, so write controls are hidden. */
  readOnly?: boolean;
}

/**
 * Sentiment is permanent on the install axis and toggleable on the enable one
 * (**D20**). It arrives with the pipeline: there is nothing to install, and
 * uninstalling only destroys tags nothing can restore. The floor is not a
 * codebook you installed at all.
 */
/** English-only plural, because this lens's chrome is not enrolled in i18n yet.
 *
 * Deliberately NOT a new i18n key: phase 6 enrols this whole surface at once
 * (`docs/design-codebook-v2-plan.md`), and a key added now would be copy the
 * plan still wants reviewed, machine-translated into 21 locales ahead of that
 * review. But "1 tags" is wrong in the one language this currently ships in,
 * and a stat line that cannot count is not a stat line.
 *
 * Delete this with the literals when `t()` arrives — i18next does CLDR plurals
 * via `t(key, { count })`, so there is nothing here to carry forward.
 */
const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

const canInstall = (b: PageBook) => !b.floor && b.id !== "sentiment";

/** A door onto nothing is worse than no door (**D26**). */
/** Q14 — the door is hidden in an export, not disabled.
 *
 * The threshold modal reads `/autocode/proposals`, which is SERVER_ONLY and so
 * absent from a leave-behind, and its primary act is a write. Left visible, a
 * client opening the exported report offline would find a control that opens a
 * dialog which cannot load and cannot apply. v2's other controls escape this by
 * accident of the extraction — Uninstall carries `.framework-remove-btn` and
 * the authoring carries `.tag-add-row`, both of which `theme/templates/export.css`
 * already hides — but the Review door has no such class, so it needs the gate.
 */
const hasReviewDoor = (b: PageBook, tagCount: number, readOnly: boolean) =>
  !readOnly &&
  !b.floor && b.id !== "sentiment" && b.installed && tagCount > 0;

export function CodebookV2Page({
  book,
  groups,
  onReview,
  onInstall,
  onUninstall,
  authoring,
  allTagNames,
  readOnly = false,
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

          {hasReviewDoor(book, tagCount, readOnly) ? (
            // The verb is the button; the counts are text on its baseline. A
            // sentence wearing a border is not a control, and it read as more
            // prominent than Install, which it must not be.
            <div className="pg-review-row">
              {/* The counts lead, the verb follows. The button read as the
                  subject of the row when it came first; the sentence is the
                  finding and Review is what you do about it. */}
              <span className="pg-review-meta">
                {tagCount} {plural(tagCount, "tag", "tags")} on {book.quotes}{" "}
                {plural(book.quotes, "quote", "quotes")}
                {book.pending > 0 && (
                  <span className="undec"> &middot; {book.pending} undecided</span>
                )}
              </span>
              {/* `bn-btn-secondary`, not a bare `bn-btn`. The base atom sets
                  font, padding, radius and border but declares NO background,
                  so a bare `.bn-btn` falls through to the browser's own
                  `buttonface` — measured rgb(239,239,239) on black, a grey
                  belonging to no palette and the one thing on the page that
                  survived a palette switch unchanged. That is what read as
                  "low contrast and yet too noticeable, and a bit dead": an
                  unstyled control, not a styling choice.

                  `secondary` over `cancel`: the two declare identical
                  properties, so the pixels are the same, but `cancel` is a
                  dismissal verb and this button reviews. */}
              <button
                className="bn-btn bn-btn-secondary bn-btn-sm"
                onClick={() => onReview(book.id)}
                data-testid="bn-v2-review"
              >
                Review
              </button>
            </div>
          ) : (
            <div className="pg-stat">
              {book.installed
                ? `${tagCount} ${plural(tagCount, "tag", "tags")}${
                    book.quotes
                      ? ` on ${book.quotes} ${plural(book.quotes, "quote", "quotes")}`
                      : ""
                  }`
                : `${tagCount} ${plural(tagCount, "tag", "tags")} · not installed`}
            </div>
          )}

          {tpl?.description && (
            // `autoSplit`: codebook descriptions are hand-written YAML and carry
            // no `||`. Waiting for all nine to be re-authored would mean shipping
            // no treatment at all in the meantime.
            <p className="pg-desc bn-lead-para">
              {renderLead(tpl.description, { autoSplit: true })}
            </p>
          )}
        </div>

        {/* A fixed-width gutter, not a fixed box (D13). What fills it — a
            jacket, initials, a headshot, nothing — is deferred per codebook;
            the reserved space is what the layout depends on.

            The author card fills it for now. It was rendering below the page,
            bottom-left, which put the one piece of provenance a researcher
            might actually weigh — who wrote this framework, and what they are
            known for — furthest from the title that raises the question.

            PARKED, not deleted: the graphic placeholder. It reserved the
            gutter for a jacket / initials / headshot that has not been
            designed, and while it is undesigned it is a large grey rectangle
            competing with the thing now occupying the same space. D13's
            contract is the WIDTH, which the gutter still holds, so restoring
            it is uncommenting one line.
            <div className="pg-graphic" aria-hidden="true" /> */}
        <div className="pg-side">
          {/* `.preview-author` and its children are the shipped card from the
              codebook picker — same treatment, same type, same link styling.
              Its wrapper there (`.preview-body-sidebar`, a fixed 260px column)
              is deliberately NOT reused: `.pg-side` already is the column, and
              two elements declaring a width is how a gutter stops being one
              number. */}
          {(tpl?.author_bio || links.length > 0) && (
            <div className="preview-author" data-testid="bn-v2-author">
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
          )}
          {canInstall(book) && !readOnly && (
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

      {tagCount === 0 && !book.floor ? (
        // Bleak on purpose (D26): no illustration, no call to action, no
        // reframing of the absence as an opportunity. The fact is the message.
        //
        // The floor is exempt, and not as a softening. D26 governs "a codebook
        // with no tags", and the floor is not a codebook you installed — it is
        // the surface you author. Replacing its controls with a sentence would
        // leave a researcher with no way to begin, which is precisely the state
        // the shipped lens never puts them in.
        <div className="pg-empty" data-testid="bn-v2-empty">
          This codebook has no tags.
        </div>
      ) : (
        <div className="v2-groups">
          {groups.map((g) => (
            <CodebookGroupColumn
              key={g.id}
              group={g}
              allTagNames={allTagNames}
              {...authoring.groupProps}
            />
          ))}
          {/* Only the floor grows groups. A framework's structure is its
              author's; the card would be an offer we must not make. */}
          {book.floor && (
            <NewGroupPlaceholder
              onCreateGroup={authoring.onCreateGroup}
              onDropNewGroup={authoring.onDropNewGroup}
            />
          )}
        </div>
      )}
    </div>
  );
}

export { canInstall as _canInstall, hasReviewDoor as _hasReviewDoor };
