/**
 * Toast — minimal notification component.
 *
 * Portal-rendered to document.body. Auto-dismisses after `duration`.
 * One toast at a time; `utils/toast.ts` decides which one wins (a confirmation does not replace a failure).
 * Reuses atoms/toast.css (.clipboard-toast).
 *
 * Anatomy: an optional kind icon, then either one regular line, or a title
 * (emphasis weight) over a quieter body when the message is two sentences.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { MessageKind } from "../utils/messageKind";
import { Icon, type IconName } from "./Icon";

/** A toast draws four of the five kinds; `skipped` is a neutral note, so it draws as info. */
const KIND_ICON: Record<MessageKind, { name: IconName; tone: Exclude<MessageKind, "skipped"> }> = {
  success: { name: "success", tone: "success" },
  info: { name: "info", tone: "info" },
  warning: { name: "warning", tone: "warning" },
  error: { name: "failed", tone: "error" },
  skipped: { name: "info", tone: "info" },
};

interface ToastProps {
  message: string;
  onDismiss: () => void;
  duration?: number;
  /** One of the five kinds. Omit for a plain toast with no icon. */
  kind?: MessageKind;
  /** A heading over `message`, for a message that splits into what and what next. */
  title?: string;
  /** Already on screen: an identical repeat restarts its timer without replaying the fade-in. */
  instant?: boolean;
}

export function Toast({ message, onDismiss, duration = 2000, kind, title, instant = false }: ToastProps) {
  const [visible, setVisible] = useState(instant);

  // Trigger fade-in on mount
  useEffect(() => {
    // Force reflow before adding .show (matches vanilla pattern)
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  // Auto-dismiss
  useEffect(() => {
    let fade: ReturnType<typeof setTimeout> | undefined;
    const timer = setTimeout(() => {
      setVisible(false);
      // Wait for fade-out transition before unmounting
      fade = setTimeout(onDismiss, 300);
    }, duration);
    // Both timers go with the toast: a replaced one must not dismiss its successor.
    return () => {
      clearTimeout(timer);
      clearTimeout(fade);
    };
  }, [duration, onDismiss]);

  const glyph = kind ? KIND_ICON[kind] : null;

  return createPortal(
    <div
      className={`clipboard-toast${visible ? " show" : ""}${kind ? " has-kind" : ""}`}
      data-testid="bn-toast"
      data-kind={kind}
    >
      {glyph && (
        <span className={`toast-glyph toast-glyph--${glyph.tone}`} aria-hidden="true">
          <Icon name={glyph.name} decorative />
        </span>
      )}
      <div className="toast-text">
        {title && <div className="toast-title">{title}</div>}
        <div className={title ? "toast-body" : "toast-message"}>{message}</div>
      </div>
    </div>,
    document.body,
  );
}
