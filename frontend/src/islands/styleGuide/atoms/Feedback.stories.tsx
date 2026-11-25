/**
 * Atoms / Feedback — the three ways the app reports back: an activity chip
 * for a background job, a toast for a moment, a confirmation card for a
 * choice. The chips and the card draw inline, as they do in the app (only the
 * chips' stack is fixed-position; the codebook draws the card in place). The
 * toast floats over the page, so it opens from a button, by `toast()`.
 */

import { useState } from "react";

import { ActivityChip, type ActivityChipJob } from "../../../components/ActivityChip";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { ToolbarButton } from "../../../components/ToolbarButton";
import type { MessageKind } from "../../../utils/messageKind";
import { toast } from "../../../utils/toast";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Atoms/Feedback",
  description:
    "ActivityChip (atoms/activity-chip.css), toast() (atoms/toast.css) and ConfirmDialog (.confirm-dialog), with the props their callers pass.",
  caveat:
    "Chips appear here without the fixed stack that pins them bottom-right in the app. Button text the components own (Cancel, OK) comes from the app's locale.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Chips", "Toasts", "Confirm"] as const;

const BASE: Omit<ActivityChipJob, "id" | "status"> = {
  label: "AutoCode: Norman's usability heuristics",
  completedLabel: "AutoCode finished: Norman's usability heuristics",
  progressLabel: null,
  durationLabel: null,
  errorMessage: null,
};

const JOBS: ActivityChipJob[] = [
  { ...BASE, id: "running", status: "running", progressLabel: "48 of 120" },
  { ...BASE, id: "completed", status: "completed", durationLabel: "2 min 14 s" },
  { ...BASE, id: "partial", status: "partial", durationLabel: "2 min 40 s", partialMessage: "3 of 5 batches finished. 72 of 120 quotes were coded." },
  { ...BASE, id: "failed", status: "failed", errorMessage: "Claude said the account has no credit left" },
  { ...BASE, id: "cancelled", status: "cancelled" },
];

export const Chips: SpecimenStory = {
  name: "Activity chip, every status",
  render: () => (
    <div className="bn-sg-stack">
      {JOBS.map((job) => (
        <div key={job.id} data-testid={`bn-sg-chip-${job.status}`}>
          <ActivityChip
            job={job}
            onAction={() => {}}
            actionLabel="Review"
            actionHref="#atoms-feedback"
            onDismiss={() => {}}
            onCancel={() => {}}
          />
        </div>
      ))}
    </div>
  ),
};

const TOASTS: Array<{ kind?: MessageKind; label: string; message: string; title?: string }> = [
  { label: "Plain", message: "Copied" },
  { kind: "success", label: "Success", message: "Exported 42 quotes" },
  { kind: "info", label: "Info", message: "Nothing to undo" },
  { kind: "warning", label: "Warning", message: "Two sessions have no recording, so their timecodes do not play." },
  {
    kind: "error",
    label: "Error with title",
    title: "The tag was not saved",
    message: "Bristlenose could not reach its server. Check it is still running, then try again.",
  },
];

export const Toasts: SpecimenStory = {
  name: "Toast, each kind (opens the real toast)",
  render: () => (
    <div className="bn-sg-specimens">
      {TOASTS.map((t) => (
        <ToolbarButton
          key={t.label}
          label={t.label}
          onClick={() => toast(t.message, undefined, t.kind, t.title ? { title: t.title } : undefined)}
        />
      ))}
    </div>
  ),
};

/** Each card focuses its confirm button on mount, as the app needs; drawn at
 *  load they would scroll the page to the last one, so they appear on a click,
 *  which is also how the app shows one. */
function ConfirmCards() {
  const [shown, setShown] = useState(false);
  if (!shown) return <ToolbarButton label="Show the confirmation cards" onClick={() => setShown(true)} />;
  return (
    <div className="bn-sg-stack">
      <ConfirmDialog
        title="Delete the tag “Slow checkout”?"
        body={<span>It is on 14 quotes. They keep their other tags.</span>}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
      <ConfirmDialog
        title="Accept 38 proposed tags?"
        body={<span>They become ordinary tags you can remove one by one.</span>}
        confirmLabel="Accept"
        variant="primary"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
      <ConfirmDialog
        title="The export is ready"
        body={<span>It opens from your Downloads folder.</span>}
        hideCancel
        onConfirm={() => {}}
        onCancel={() => {}}
      />
      <ConfirmDialog
        title="Delete the tag “Trust in delivery dates”?"
        body={<span>It is on 3 quotes.</span>}
        confirmLabel="Delete"
        variant="danger"
        accentColour="var(--bn-bar-trust)"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    </div>
  );
}

export const Confirm: SpecimenStory = {
  name: "Confirmation card: danger, primary, acknowledgement, on a codebook group's tint",
  render: () => <ConfirmCards />,
};
