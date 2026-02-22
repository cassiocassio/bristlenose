interface ThumbnailProps {
  hasMedia: boolean;
  thumbnailUrl?: string;
  className?: string;
  "data-testid"?: string;
}

export function Thumbnail({
  hasMedia,
  thumbnailUrl,
  className,
  "data-testid": testId,
}: ThumbnailProps) {
  if (!hasMedia) return null;

  const classes = ["bn-video-thumb", className].filter(Boolean).join(" ");

  return (
    <div className={classes} data-testid={testId}>
      {thumbnailUrl ? (
        <img src={thumbnailUrl} alt="" loading="lazy" />
      ) : (
        <span className="bn-play-icon">&#9654;</span>
      )}
    </div>
  );
}
