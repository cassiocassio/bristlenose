interface MicroBarProps {
  /** Fraction 0–1 (clamped). */
  value: number;
  /** CSS colour or variable for the fill. */
  colour?: string;
  /** Show a background track (analysis style) or bare bar (codebook style). */
  track?: boolean;
  className?: string;
  "data-testid"?: string;
}

export function MicroBar({
  value,
  colour,
  track = false,
  className,
  "data-testid": testId,
}: MicroBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = `${Math.round(clamped * 100)}%`;
  const fillStyle: React.CSSProperties = {
    width: pct,
    ...(colour ? { backgroundColor: colour } : {}),
  };

  if (track) {
    const classes = ["conc-bar-track", className].filter(Boolean).join(" ");
    return (
      <span className={classes} data-testid={testId}>
        <span className="conc-bar-fill" style={fillStyle} />
      </span>
    );
  }

  const classes = ["tag-micro-bar", className].filter(Boolean).join(" ");
  return (
    <span className={classes} style={fillStyle} data-testid={testId} />
  );
}
