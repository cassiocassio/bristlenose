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
      <span className={classes} style={style} data-testid={testId}>
        {text}
        <span className="badge-action-pill">
          <span
            className="badge-action-deny"
            onClick={(e) => { e.stopPropagation(); onDeny?.(); }}
            title="Deny"
            data-testid={testId ? `${testId}-deny` : undefined}
          >
            &times;
          </span>
          <span
            className="badge-action-accept"
            onClick={(e) => { e.stopPropagation(); onAccept?.(); }}
            title="Accept"
            data-testid={testId ? `${testId}-accept` : undefined}
          >
            &#x2713;
          </span>
        </span>
        {rationale && <span className="tooltip">{rationale}</span>}
      </span>
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
