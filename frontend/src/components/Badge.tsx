interface BadgeProps {
  text: string;
  variant: "ai" | "user" | "readonly";
  sentiment?: string;
  colour?: string;
  onDelete?: () => void;
  className?: string;
  "data-testid"?: string;
}

export function Badge({
  text,
  variant,
  sentiment,
  colour,
  onDelete,
  className,
  "data-testid": testId,
}: BadgeProps) {
  const classes = [
    "badge",
    variant === "ai" ? "badge-ai" : variant === "user" ? "badge-user" : null,
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

  if (variant === "user") {
    return (
      <span className={classes} style={style} data-testid={testId}>
        {text}
        {onDelete && (
          <button className="badge-delete" onClick={onDelete} aria-label={`Remove ${text}`}>
            &times;
          </button>
        )}
      </span>
    );
  }

  // readonly
  return (
    <span className={classes} style={style} data-testid={testId}>
      {text}
    </span>
  );
}
