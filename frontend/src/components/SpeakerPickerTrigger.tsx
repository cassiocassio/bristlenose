/**
 * A speaker's badge as the person picker's button, on a surface that does not
 * hold the study's speakers itself — the transcript and the project dashboard
 * (docs/design-people.md §J8.7; the Sessions grid has its own, with drawing it
 * owns). The same picker opens: on the speaker's current role, the cursor in
 * the new-person field for an unknown speaker, the native popover in the Mac
 * app. The speaker is read fresh from /sessions when it opens.
 *
 * Import by path: the dashboard is first paint, and the picker itself loads
 * only when someone opens it.
 */

import { Suspense, lazy, useState, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";

import { PersonBadge } from "./PersonBadge";
import { isExportMode } from "../utils/exportData";
import { isEmbedded } from "../utils/embedded";
import {
  applySpeakerChoice,
  hasNativePersonPicker,
  loadSpeakerContext,
  openNativePicker,
  refuseTakenName,
  type SpeakerPickContext,
} from "../utils/speakerPicking";

const PersonPickerPopover = lazy(() =>
  import("./PersonPicker").then((m) => ({ default: m.PersonPickerPopover })),
);

interface SpeakerPickerTriggerProps {
  sessionId: string;
  /** The code the badge shows (`m1`, `mA?`, `p3`). */
  code: string;
  role: "participant" | "moderator" | "observer";
  name?: string;
  /** False for a badge repeated on every paragraph: a click target, but not
   *  a Tab stop each, or a long transcript would be hundreds of them. */
  tabbable?: boolean;
}

export function SpeakerPickerTrigger({ sessionId, code, role, name, tabbable = true }: SpeakerPickerTriggerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState<SpeakerPickContext | null>(null);
  const badge = <PersonBadge code={code} role={role} name={name} />;

  // An exported report draws the badge plain: nothing it does could be saved.
  if (isExportMode()) return badge;

  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (open) {
      setOpen(null);
      return;
    }
    const anchor = e.currentTarget;
    void loadSpeakerContext(sessionId, code).then((ctx) => {
      if (!ctx) return;
      if (isEmbedded() && hasNativePersonPicker()) {
        openNativePicker(
          {
            sessionId,
            code,
            slot: ctx.slot,
            known: ctx.known,
            apply: (choice) => applySpeakerChoice(ctx, choice),
            refuse: refuseTakenName,
          },
          anchor,
        );
      } else {
        setOpen(ctx);
      }
    });
  };

  return (
    <span className="bn-person-picker-anchor">
      <button
        type="button"
        className="bn-person-picker-trigger"
        aria-haspopup="menu"
        aria-expanded={open !== null}
        tabIndex={tabbable ? 0 : -1}
        data-testid={`bn-speaker-trigger-${code}`}
        onClick={onClick}
      >
        {badge}
      </button>
      {open && (
        <Suspense fallback={null}>
          <PersonPickerPopover
            slot={open.slot}
            known={open.known}
            t={t}
            onChoose={(choice) => applySpeakerChoice(open, choice)}
            onClose={() => setOpen(null)}
          />
        </Suspense>
      )}
    </span>
  );
}
