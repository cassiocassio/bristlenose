interface JourneyChainProps {
  labels: string[];
  separator?: string;
  className?: string;
  "data-testid"?: string;
}

export function JourneyChain({
  labels,
  separator = " \u2192 ",
  className,
  "data-testid": testId,
}: JourneyChainProps) {
  if (labels.length === 0) return null;

  const classes = ["bn-session-journey", className].filter(Boolean).join(" ");

  return (
    <div className={classes} data-testid={testId}>
      {labels.map((label, i) => (
        <span key={i}>
          {i > 0 && <span className="bn-journey-sep" aria-hidden="true">{separator}</span>}
          <span className="bn-journey-label">{label}</span>
        </span>
      ))}
    </div>
  );
}
