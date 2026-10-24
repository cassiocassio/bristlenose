import { useContext, useCallback } from "react";
import { PlayerContext } from "../contexts/PlayerContext";
import { formatTimecode } from "../utils/format";
import { momentPlace, placeProps } from "../utils/contextPlace";

interface TimecodeLinkProps {
  seconds: number;
  endSeconds?: number;
  participantId: string;
  /** The session the moment is in, so the Mac's right-click can offer its transcript. Without it
   *  the menu offers Play alone: the player is keyed by participant code, which names no session. */
  sessionId?: string;
  formatted?: string;
  "data-testid"?: string;
}

export function TimecodeLink({
  seconds,
  endSeconds,
  participantId,
  sessionId,
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
      {...placeProps(momentPlace("play", sessionId, seconds, participantId))}
      data-testid={testId}
    >
      <span className="timecode-bracket">[</span>
      {display.replace(/^\[/, "").replace(/\]$/, "")}
      <span className="timecode-bracket">]</span>
    </a>
  );
}
