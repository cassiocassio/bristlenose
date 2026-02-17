interface ToggleProps {
  active: boolean;
  onToggle: (newState: boolean) => void;
  children: React.ReactNode;
  className?: string;
  activeClassName?: string;
  "aria-label"?: string;
  "data-testid"?: string;
}

export function Toggle({
  active,
  onToggle,
  children,
  className,
  activeClassName,
  "aria-label": ariaLabel,
  "data-testid": testId,
}: ToggleProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    onToggle(!active);
  };

  const classes = [className, active && activeClassName]
    .filter(Boolean)
    .join(" ") || undefined;

  return (
    <button
      className={classes}
      onClick={handleClick}
      aria-label={ariaLabel}
      aria-pressed={active}
      data-testid={testId}
    >
      {children}
    </button>
  );
}
