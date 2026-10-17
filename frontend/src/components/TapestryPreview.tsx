/**
 * The closed timeline: a skinny strip under a Sessions-grid row, the whole interview at a
 * glance, and a click target that opens the full timeline (SessionTapestry) under the row.
 *
 * Participants only, merged into one lane when a session has several: every participant turn
 * in its scene colour, on the timeline's own track. The gaps are where the team spoke. The
 * strip fills the row whatever the session's length; the open timeline uses the shared scale.
 * A quarter the height of the open timeline's participant clips, the clips at 60% under a
 * 0.5 px keyline, no text — and no hover but a tint (owner, 17 Oct 2026). Mockup and the
 * reasoning: docs/mockups/sessions-timeline-strip.html.
 *
 * A pointer convenience, like the row's click-to-transcript: hidden from assistive technology
 * and out of the tab order, because the row's disclosure button already opens the same timeline.
 */
import type { TapestrySession } from "../utils/types";
import { CLIP_THRESHOLD, TAPESTRY_GUTTER, TAPESTRY_RIGHT } from "../utils/tapestryScale";

/** A quarter of the open timeline's participant clips (18 px). */
export const PREVIEW_H = 4.5;

interface Props {
  session: TapestrySession;
  /** The grid's width: the strip spans it, its track lined up with the open timeline's. */
  width: number;
  /** Whether a turn is the team's: the server's answer, else the displayed code's letter. */
  isTeam: (turn: TapestrySession["turns"][number]) => boolean;
  /** Open the timeline (or, once open, close it: the strip stays under the pointer while it
   *  fades, so a double-click must not fall through to the row). `all` = Option-click. */
  onToggle: (all: boolean) => void;
}

export function TapestryPreview({ session, width, isTeam, onToggle }: Props) {
  const usable = width - TAPESTRY_GUTTER - TAPESTRY_RIGHT;
  if (usable <= 0 || !(session.duration_seconds > 0)) return null;
  const sPerPx = session.duration_seconds / usable;
  const x = (sec: number) => TAPESTRY_GUTTER + Math.min(sec, session.duration_seconds) / sPerPx;
  const clips = sPerPx <= CLIP_THRESHOLD;
  return (
    <div
      className="bn-tapestry-preview"
      data-own-click
      aria-hidden="true"
      onClick={(e) => {
        e.stopPropagation();
        onToggle(e.altKey);
      }}
    >
      <svg
        className="bn-tapestry-preview-svg"
        width={width}
        height={PREVIEW_H + 4}
        data-x0={TAPESTRY_GUTTER}
        data-px-per-sec={1 / sPerPx}
      >
        <g transform="translate(0,2)">
          <rect className="bn-tp-pv-track" x={TAPESTRY_GUTTER} y={0} width={x(session.duration_seconds) - TAPESTRY_GUTTER}
            height={PREVIEW_H} rx={1.5} />
          <g className="bn-tp-pv-clips">
            {session.turns.map((tn, i) => {
              if (isTeam(tn)) return null;
              const x0 = x(tn.t0);
              const w = x(tn.t1) - x0;
              // The open timeline's geometry: inset half a pixel each side, corners up to half
              // the clip, at the strip's height. Too thin to draw at this scale: skipped.
              const g = clips
                ? (w < 1 ? null : { x: x0 + 0.5, w: Math.max(1, w - 1), rx: Math.min(1, w / 2) })
                : { x: x0, w: Math.max(0.5, w), rx: 0 };
              if (!g) return null;
              return (
                <g key={i}>
                  <rect className="bn-tp-pv-clip" x={g.x} y={0} width={g.w} height={PREVIEW_H} rx={g.rx || undefined}
                    style={tn.colour ? { fill: tn.colour } : undefined} />
                  <rect className="bn-tp-pv-edge" x={g.x} y={0} width={g.w} height={PREVIEW_H} rx={g.rx || undefined} />
                </g>
              );
            })}
          </g>
        </g>
      </svg>
    </div>
  );
}
