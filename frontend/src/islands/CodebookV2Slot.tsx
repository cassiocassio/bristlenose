/**
 * The codebook pages' top-right slot: AutoCode → AutoCoding… → Applied.
 *
 * One slot on the catalogue card and the codebook page, always in the same state
 * (owner, 24 Nov 2026; `docs/mockups/codebook-applied-slot.html`): our regular
 * button one size down, then plain shimmering words while AutoCode runs, then the
 * green "Applied" cartouche when the run completes. The words and the cartouche
 * are not controls: no box, no hover, no focus.
 *
 * Its words sit on the title's first baseline (alignment B): the row that holds it
 * aligns on baselines, so a wrapped title keeps the slot on its first line.
 */

import { useTranslation } from "react-i18next";
import { Icon } from "../components/Icon";
import type { AutoCodeRunState } from "../utils/types";

/** What the slot shows: the button, the running words, the cartouche, or nothing. */
export type SlotState = "act" | "run" | "done" | null;

/**
 * The slot for one codebook.
 *
 * Sentiment is applied by the pipeline and never offers a button (D20). A codebook
 * not installed, never started, or unfinished (stopped, failed, partly failed)
 * offers AutoCode, which resumes; a completed run says Applied however little it
 * applied. `localRun` is a run this window's activity chips know is going, which
 * the server's answer may not show yet.
 *
 * A switched-off codebook offers no button: off means off, and switching it off
 * is what stopped its run. Switching it on is the way back.
 */
export function slotState(
  id: string,
  installed: boolean,
  enabled: boolean,
  server: AutoCodeRunState | undefined,
  localRun: boolean,
): SlotState {
  if (id === "sentiment") return "done";
  if (!installed) return "act";
  if (localRun || server === "running") return "run";
  if (server === "applied") return "done";
  return enabled ? "act" : null;
}

export function CodebookSlot({
  state,
  onAutoCode,
  testId,
}: {
  state: SlotState;
  /** Absent: no button (an export, which is read-only). */
  onAutoCode?: () => void;
  testId: string;
}) {
  const { t } = useTranslation();
  if (state === null) return null;
  // Without the button's action this is an exported report, which is read-only and
  // cannot change: words that shimmer for ever would say a run is going.
  if ((state === "act" || state === "run") && !onAutoCode) return null;
  if (state === "act" && onAutoCode) {
    return (
      <button
        type="button"
        className="bn-btn bn-btn-primary bn-btn-sm cb-act"
        data-testid={testId}
        onClick={(e) => {
          // On a card the button is the one region that does not navigate (D12).
          e.stopPropagation();
          onAutoCode();
        }}
        onKeyDown={(e) => e.stopPropagation()}
      >
        {t("codebook.autocodeAction")}
      </button>
    );
  }
  if (state === "run") {
    return (
      <span className="cb-running bn-thinking-shimmer" data-testid={testId}>
        {t("codebook.autocodeRunning")}
        {/* The ellipsis grows ". .. ..." and repeats; frozen it reads "...". The dots
            fade rather than appear, so the slot's width holds still. */}
        <span className="cb-dots" aria-hidden="true">
          <i>.</i>
          <i>.</i>
          <i>.</i>
        </span>
      </span>
    );
  }
  return (
    <span className="cb-applied" data-testid={testId}>
      <Icon name="check" decorative />
      <span>{t("codebook.autocodeApplied")}</span>
    </span>
  );
}
