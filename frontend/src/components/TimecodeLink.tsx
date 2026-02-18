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
  const display = formatted ?? `[${formatTimecode(seconds)}]`;

  return (
    <a
      className="timecode"
      href={`#t=${seconds}`}
      data-participant={participantId}
      data-seconds={seconds}
      {...(endSeconds !== undefined && { "data-end-seconds": endSeconds })}
      data-testid={testId}
    >
      <span className="timecode-bracket">[</span>
      {display.replace(/^\[/, "").replace(/\]$/, "")}
      <span className="timecode-bracket">]</span>
    </a>
  );
}
