interface ThumbnailProps {
  hasMedia: boolean;
  className?: string;
  "data-testid"?: string;
}

export function Thumbnail({
  hasMedia,
  className,
  "data-testid": testId,
}: ThumbnailProps) {
  if (!hasMedia) return null;

  const classes = ["bn-video-thumb", className].filter(Boolean).join(" ");

  return (
    <div className={classes} data-testid={testId}>
      <span className="bn-play-icon">&#9654;</span>
    </div>
  );
}
