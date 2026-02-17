function formatTimecode(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) {
    return `${h}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}

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
