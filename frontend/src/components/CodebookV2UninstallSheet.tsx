/**
 * Uninstall confirmation — codebook v2, phase 5.
 *
 * **A terse modal measures.** The house precedent is the re-analyse sheet
 * (`ReAnalyseConfirmSheet.swift`): *"'This cannot be undone' tells a researcher
 * nothing they can weigh; counted lines let them decide in one read."* Same
 * shape here, from `/remove-framework/{id}/impact`.
 *
 * **And it now has more to say than it used to.** Under **D20 option A**
 * uninstall stops preserving: the AutoCode job and its proposals go with the
 * tags. The shipped copy — *"Tags will be removed from N quotes"* — was accurate
 * under the old preserving model and understates this one, so the sheet says
 * what actually goes.
 *
 * The buttons follow the HIG the way the re-analyse sheet had to be corrected
 * into doing: Cancel leads and is *not* the default, the confirm sits trailing
 * and carries the default, and `.destructive` styling is reserved for an action
 * the researcher did not deliberately choose — which this is not.
 *
 * **`impact` has THREE states, not two, and conflating them is a lie on a
 * destructive path.** The counts arrive after the sheet opens, so `null` means
 * either "still counting" or "the count failed" — and this sheet used to render
 * both as *"Nothing has been coded with it yet, so nothing is lost."* That
 * sentence is a measurement, and it must only appear when a measurement came
 * back saying so. A researcher told nothing is lost, who then discards a fully
 * coded framework, has been misinformed by the one screen whose entire job was
 * to inform them.
 */

import type { RemoveFrameworkInfo } from "../utils/types";

interface Props {
  title: string;
  /** The measured losses. `null` while counting, or if counting failed. */
  impact: RemoveFrameworkInfo | null;
  /** True once the impact fetch has failed. Distinguishes "unknown" from
   *  "still arriving" — both are `impact === null`, and only one of them is
   *  going to resolve. */
  impactFailed?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function CodebookV2UninstallSheet({
  title,
  impact,
  impactFailed = false,
  onCancel,
  onConfirm,
}: Props) {
  // One line per kind, zero-count kinds omitted — a "0 tags" line is noise in a
  // list whose whole job is to be read at a glance. Lifted from the re-analyse
  // sheet's `lossLines`, including the reasoning.
  const losses: string[] = [];
  if (impact) {
    if (impact.tag_count > 0) {
      losses.push(
        `${impact.tag_count} tag${impact.tag_count === 1 ? "" : "s"}`,
      );
    }
    if (impact.quote_count > 0) {
      losses.push(
        `tags on ${impact.quote_count} quote${impact.quote_count === 1 ? "" : "s"}`,
      );
    }
    if (impact.has_autocode) {
      // The line D20 option A made necessary: the run itself is gone, so
      // reinstalling costs money again. Without it the sheet describes the old
      // preserving model.
      losses.push("the AutoCode run and every proposal under it");
    }
  }

  return (
    // `.bn-overlay` + `.bn-modal` is the house pair from `atoms/modal.css`, and
    // the class this used to carry — `.bn-modal-overlay` — is defined nowhere.
    // A class that does not exist does not error: the backdrop simply had no
    // `position: fixed`, no z-index, no dimming and no centring, so a
    // destructive confirmation rendered INLINE at the bottom of the page. It
    // looked like a card because `.bn-modal` is real; only the overlay was
    // invented. Found by opening it and getting a blank screen.
    //
    // `.visible` is required, not decorative: `.bn-overlay` is
    // `opacity: 0; visibility: hidden` at rest, and the shipped modals toggle
    // the class rather than unmounting. This one mounts conditionally, so it
    // must arrive already visible.
    <div className="bn-overlay visible" data-testid="bn-v2-uninstall-sheet">
      <div className="bn-modal v2-uninstall-sheet" role="dialog" aria-modal="true">
        <h2 className="v2-uninstall-title">Uninstall &ldquo;{title}&rdquo;?</h2>
        {losses.length > 0 ? (
          <>
            <p className="v2-uninstall-lead">This will be discarded:</p>
            <ul className="v2-uninstall-losses">
              {losses.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </>
        ) : impactFailed ? (
          // Say we do not know. The alternative — reassurance we have not
          // earned — is the one outcome worse than an unhelpful sheet.
          <p className="v2-uninstall-lead" data-testid="bn-v2-uninstall-unknown">
            Couldn&rsquo;t check what this would discard. If it has been used
            for coding, that work goes with it.
          </p>
        ) : impact === null ? (
          <p className="v2-uninstall-lead" data-testid="bn-v2-uninstall-counting">
            Checking what this would discard&hellip;
          </p>
        ) : (
          // Reached only with a measurement in hand that says zero.
          <p className="v2-uninstall-lead" data-testid="bn-v2-uninstall-nothing">
            Nothing has been coded with it yet, so nothing is lost.
          </p>
        )}
        <p className="v2-uninstall-lead">
          Reinstalling starts over and costs a fresh run. To keep the results and
          stop using it for now, switch it off instead.
        </p>
        <div className="bn-modal-actions">
          <button className="bn-btn bn-btn-cancel" onClick={onCancel} data-testid="bn-v2-uninstall-cancel">
            Cancel
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={onConfirm}
            data-testid="bn-v2-uninstall-confirm"
            autoFocus
          >
            Uninstall
          </button>
        </div>
      </div>
    </div>
  );
}
