import { useRef, useEffect, useCallback } from "react";

interface BadgeProps {
  text: string;
  variant: "ai" | "user" | "readonly" | "deletable" | "proposed";
  sentiment?: string;
  colour?: string;
  onDelete?: () => void;
  onClick?: () => void;
  onAccept?: () => void;
  onDeny?: () => void;
  rationale?: string;
  className?: string;
  "data-testid"?: string;
}

/** Returns true if the event target is a text-entry element (input, textarea, contenteditable). */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
}

function ProposedBadge({
  classes,
  style,
  testId,
  text,
  rationale,
  onAccept,
  onDeny,
}: {
  classes: string;
  style: React.CSSProperties | undefined;
  testId: string | undefined;
  text: string;
  rationale: string | undefined;
  onAccept: (() => void) | undefined;
  onDeny: (() => void) | undefined;
}) {
  const hoveredRef = useRef(false);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!hoveredRef.current) return;
      if (isTypingTarget(e.target)) return;
      const key = e.key.toLowerCase();
      if (key === "a") {
        e.preventDefault();
        onAccept?.();
      } else if (key === "d") {
        e.preventDefault();
        onDeny?.();
      }
    },
    [onAccept, onDeny],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <span
      className={classes}
      style={style}
      data-testid={testId}
      onMouseEnter={() => { hoveredRef.current = true; }}
      onMouseLeave={() => { hoveredRef.current = false; }}
    >
      {text}
      <span className="badge-action-pill">
        <span
          className="badge-action-deny"
          onClick={(e) => { e.stopPropagation(); onDeny?.(); }}
          title="Deny (d)"
          data-testid={testId ? `${testId}-deny` : undefined}
        >
          &times;
        </span>
        <span
          className="badge-action-accept"
          onClick={(e) => { e.stopPropagation(); onAccept?.(); }}
          title="Accept (a)"
          data-testid={testId ? `${testId}-accept` : undefined}
        >
          &#x2713;
        </span>
      </span>
      {rationale && <span className="tooltip">{rationale}</span>}
    </span>
  );
}

export function Badge({
  text,
  variant,
  sentiment,
  colour,
  onDelete,
  onClick,
  onAccept,
  onDeny,
  rationale,
  className,
  "data-testid": testId,
}: BadgeProps) {
  const classes = [
    "badge",
    variant === "ai" ? "badge-ai"
      : variant === "user" || variant === "deletable" ? "badge-user"
      : variant === "proposed" ? "badge-proposed has-tooltip"
      : null,
    sentiment ? `badge-${sentiment}` : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const style = colour ? { backgroundColor: colour } : undefined;

  if (variant === "proposed") {
    return (
      <ProposedBadge
        classes={classes}
        style={style}
        testId={testId}
        text={text}
        rationale={rationale}
        onAccept={onAccept}
        onDeny={onDeny}
      />
    );
  }

  if (variant === "ai") {
    return (
      <span
        className={classes}
        style={style}
        onClick={onDelete}
        data-testid={testId}
      >
        {text}
      </span>
    );
  }

  if (variant === "user" || variant === "deletable") {
    return (
      <span className={classes} style={style} onClick={onClick} data-testid={testId}>
        {text}
        {onDelete && (
          <button
            className="badge-delete"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            aria-label={`Delete ${text}`}
          >
            &times;
          </button>
        )}
      </span>
    );
  }

  // readonly
  return (
    <span className={classes} style={style} onClick={onClick} data-testid={testId}>
      {text}
    </span>
  );
}
