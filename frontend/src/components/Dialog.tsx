/**
 * Dialog — the one modal shell every dialog in the report draws through.
 *
 * Owns what each modal used to hand-roll: the portal to `document.body`, the
 * inert page behind (`useInert`), Escape for the topmost dialog only, the ×,
 * focus in on open and back to the opener on close, the Tab loop, and the
 * dialog's role and name. The look is the shared atom (`atoms/modal.css`):
 * the macOS sheet, measured, its values in `tokens.css` § Dialogs.
 *
 * Two rules, both decided 24 Oct 2026:
 * - A click on the backdrop never closes a dialog. Escape and the dialog's own
 *   buttons do. There is deliberately no prop to turn it on: a dialog that
 *   seems to want it probably should not be a modal.
 * - The × sits on the shell, outside any crash boundary the content is wrapped
 *   in, because a crashed dialog's own buttons crash with it and the × is then
 *   the mouse's only way out (`docs/mockups/modal-crash-way-out.html`).
 *
 * A dialog may stay mounted and toggle `open`, or mount already open; both
 * animate in: a toggle transitions from the resting style, and a dialog that
 * mounts open starts from the `@starting-style` in `atoms/modal.css`.
 *
 * @module Dialog
 */

import {
  useEffect,
  useLayoutEffect,
  useRef,
  type ReactNode,
  type Ref,
} from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import { Icon } from "./Icon";

interface DialogProps {
  open: boolean;
  /** Escape and the ×. The dialog's own buttons call what they need. */
  onClose: () => void;
  children: ReactNode;
  /** The card's own class: its width and layout (`feedback-modal`, `codebook-modal`). */
  className?: string;
  /** An extra class on the backdrop, for rules scoped to one dialog. */
  overlayClassName?: string;
  /** `data-testid` on the backdrop. */
  testId?: string;
  /** `data-testid` on the card. */
  modalTestId?: string;
  /** The id of the element that names the dialog, usually its heading. */
  labelledBy?: string;
  /** A name for a dialog with no heading to point at. */
  label?: string;
  /** `alertdialog` for a confirmation that interrupts. */
  role?: "dialog" | "alertdialog";
  /** The shell's ×. Off only where the dialog draws its own in the same place. */
  closeButton?: boolean;
  /** For a dialog that wants the × to take focus on open. */
  closeButtonRef?: Ref<HTMLButtonElement>;
}

/** Open dialogs, oldest first: only the last one answers Escape. */
const stack: symbol[] = [];

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Dialog({
  open,
  onClose,
  children,
  className,
  overlayClassName,
  testId,
  modalTestId,
  labelledBy,
  label,
  role = "dialog",
  closeButton = true,
  closeButtonRef,
}: DialogProps) {
  const { t } = useTranslation();
  useInert(open);
  const cardRef = useRef<HTMLDivElement>(null);

  // What opened the dialog, so focus can go back to it. Read in the layout
  // phase, before any child's effect moves focus inside (ConfirmDialog focuses
  // its button in a passive effect, which runs after every layout effect).
  const openerRef = useRef<Element | null>(null);

  useLayoutEffect(() => {
    if (open) openerRef.current = document.activeElement;
  }, [open]);

  // The keyboard, for the topmost dialog only: Escape closes it, and Tab stays
  // inside it. Capture phase, so a dialog answers before the report's own
  // shortcuts; a dialog underneath lets the key pass.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    if (!open) return;
    const me = Symbol("dialog");
    stack.push(me);
    const handler = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== me) return;
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const card = cardRef.current;
      if (!card) return;
      const focusable = card.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === card)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => {
      document.removeEventListener("keydown", handler, true);
      const i = stack.indexOf(me);
      if (i !== -1) stack.splice(i, 1);
    };
  }, [open]);

  // Focus moves in, because the page behind is inert. A dialog that places it
  // itself (a heading, a confirm button, the ×) does so in its own effect; only
  // when nothing inside has it does the card take it. On close, or when the
  // dialog unmounts open, focus goes back to the opener if it is still there.
  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      const card = cardRef.current;
      if (card && !card.contains(document.activeElement)) card.focus();
    });
    return () => {
      cancelAnimationFrame(frame);
      const opener = openerRef.current;
      openerRef.current = null;
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, [open]);

  const overlayClass = ["bn-overlay", overlayClassName, open ? "visible" : ""]
    .filter(Boolean)
    .join(" ");

  return createPortal(
    // The backdrop. It never closes the dialog (see the module comment).
    <div className={overlayClass} aria-hidden={!open} data-testid={testId}>
      <div
        ref={cardRef}
        className={["bn-modal", className].filter(Boolean).join(" ")}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : label}
        tabIndex={-1}
        data-testid={modalTestId}
      >
        {closeButton && (
          <button
            ref={closeButtonRef}
            type="button"
            className="bn-modal-close"
            onClick={onClose}
            aria-label={t("buttons.close")}
          >
            <Icon name="close" decorative />
          </button>
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}
