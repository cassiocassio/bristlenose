import { useContext, useCallback } from "react";
import { PlayerContext } from "../contexts/PlayerContext";
import { formatTimecode } from "../utils/format";

interface TimecodeLinkProps {
  seconds: number;
  endSeconds?: number;
  participantId: string;
  formatted?: string;
  "data-testid"?: string;
}

export function TimecodeLink({
  seconds,
  endSeconds,
  participantId,
  formatted,
  "data-testid": testId,
}: TimecodeLinkProps) {
  const playerCtx = useContext(PlayerContext);
  const display = formatted ?? `[${formatTimecode(seconds)}]`;

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!playerCtx) return; // Legacy island mode — vanilla JS handles clicks
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      playerCtx.seekTo(participantId, seconds);
    },
    [playerCtx, participantId, seconds],
  );

  return (
    <a
      className="timecode"
      href={`#t=${seconds}`}
      data-participant={participantId}
      data-seconds={seconds}
      {...(endSeconds !== undefined && { "data-end-seconds": endSeconds })}
      onClick={playerCtx ? handleClick : undefined}
      data-testid={testId}
    >
      <span className="timecode-bracket">[</span>
      {display.replace(/^\[/, "").replace(/\]$/, "")}
      <span className="timecode-bracket">]</span>
    </a>
  );
}
