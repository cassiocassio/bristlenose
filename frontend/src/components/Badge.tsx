interface BadgeProps {
  text: string;
  variant: "ai" | "user" | "readonly" | "deletable";
  sentiment?: string;
  colour?: string;
  onDelete?: () => void;
  onClick?: () => void;
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
  className,
  "data-testid": testId,
}: BadgeProps) {
  const classes = [
    "badge",
    variant === "ai" ? "badge-ai" : variant === "user" || variant === "deletable" ? "badge-user" : null,
    sentiment ? `badge-${sentiment}` : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const style = colour ? { backgroundColor: colour } : undefined;

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
