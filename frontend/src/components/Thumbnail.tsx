interface ThumbnailProps {
  hasMedia: boolean;
  thumbnailUrl?: string;
  className?: string;
  "data-testid"?: string;
  /** When set, clicking the thumbnail opens the popout player. Mouse-only
   *  affordance — the adjacent file link is the keyboard-accessible path,
   *  so the thumbnail stays out of the tab order to avoid a redundant stop. */
  onActivate?: () => void;
  /** Native tooltip (the source filename). */
  title?: string;
}

import { isExportMode } from "../utils/exportData";

export function Thumbnail({
  hasMedia,
  thumbnailUrl,
  className,
  "data-testid": testId,
  onActivate,
  title,
}: ThumbnailProps) {
  if (!hasMedia) return null;
  // v1 leave-behind: no video. The thumbnail URL is a /report/... path that
  // 404s from file://, and there's no player, so render nothing rather than a
  // broken image or a play icon implying playback. The session's thumbnail /
  // media identity stays in the embed so a future v2 (clips-in-report) can
  // inline the keyframe still without re-plumbing.
  if (isExportMode()) return null;

  const classes = ["bn-video-thumb", className].filter(Boolean).join(" ");
  const inner = thumbnailUrl ? (
    <img src={thumbnailUrl} alt="" loading="lazy" />
  ) : (
    <span className="bn-play-icon">&#9654;</span>
  );

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div
      className={classes}
      data-testid={testId}
      onClick={onActivate}
      title={title}
    >
      {inner}
    </div>
  );
}
