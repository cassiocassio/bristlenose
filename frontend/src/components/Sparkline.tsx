export interface SparklineItem {
  key: string;
  count: number;
  colour: string;
}

interface SparklineProps {
  items: SparklineItem[];
  maxHeight?: number;
  minHeight?: number;
  gap?: number;
  opacity?: number;
  emptyContent?: React.ReactNode;
  className?: string;
  "data-testid"?: string;
}

export function Sparkline({
  items,
  maxHeight = 20,
  minHeight = 2,
  gap = 2,
  opacity = 0.8,
  emptyContent = "\u2014",
  className,
  "data-testid": testId,
}: SparklineProps) {
  const maxVal = Math.max(...items.map((i) => i.count), 0);

  if (maxVal === 0) return <>{emptyContent}</>;

  const classes = ["bn-sparkline", className].filter(Boolean).join(" ");

  return (
    <div
      className={classes}
      style={{ gap: `${gap}px` }}
      data-testid={testId}
    >
      {items.map((item) => {
        const h =
          item.count > 0
            ? Math.max(
                Math.round((item.count / maxVal) * maxHeight),
                minHeight,
              )
            : 0;
        return (
          <span
            key={item.key}
            className="bn-sparkline-bar"
            style={{
              height: `${h}px`,
              background: item.colour,
              opacity,
            }}
          />
        );
      })}
    </div>
  );
}
