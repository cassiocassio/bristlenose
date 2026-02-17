import { useCallback, useEffect, useRef, type ReactNode } from "react";

interface ConfirmDialogProps {
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  variant?: "danger" | "primary";
  accentColour?: string;
  onConfirm: () => void;
  onCancel: () => void;
  "data-testid"?: string;
}

export function ConfirmDialog({
  title,
  body,
  confirmLabel = "Delete",
  variant = "danger",
  accentColour,
  onConfirm,
  onCancel,
  "data-testid": testId,
}: ConfirmDialogProps) {
  const btnRef = useRef<HTMLButtonElement>(null);

  // Auto-focus the confirm button on mount
  useEffect(() => {
    btnRef.current?.focus();
  }, []);

  // Escape → cancel (on the whole dialog, not just the button)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCancel();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onCancel]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onConfirm();
      }
    },
    [onConfirm],
  );

  const cardStyle: React.CSSProperties | undefined = accentColour
    ? { backgroundColor: `color-mix(in srgb, ${accentColour} 8%, var(--bn-colour-bg))` }
    : undefined;

  const btnClass = ["confirm-dialog-btn", `confirm-dialog-btn--${variant}`]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className="confirm-dialog"
      style={cardStyle}
      data-testid={testId}
      onKeyDown={handleKeyDown}
    >
      <p className="confirm-dialog-title">{title}</p>
      {body && <div className="confirm-dialog-body">{body}</div>}
      <div className="confirm-dialog-actions">
        <button className="confirm-dialog-btn confirm-dialog-btn--cancel" onClick={onCancel}>
          Cancel
        </button>
        <button ref={btnRef} className={btnClass} onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </div>
  );
}
