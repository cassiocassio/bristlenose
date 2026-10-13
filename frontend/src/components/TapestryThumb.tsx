/**
 * The hover thumbnail's two marks, drawn by each SessionTapestry slice for its own session:
 * the outline of the stretch the frame stands for (inside the SVG) and the preview itself
 * (a fixed layer on document.body, so the slice's horizontal scroll cannot clip it). Behaviour
 * and timings: utils/tapestryThumb.ts.
 */

import { type RefObject, useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { formatTimecode } from "../utils/format";
import { useTapestryThumb } from "../utils/tapestryThumb";

interface OutlineProps {
  sessionId: string;
  x: (sec: number) => number;
  y: number;
  h: number;
}

/** The stretch of the participant track the preview's frame stands for. */
export function ThumbOutline({ sessionId, x, y, h }: OutlineProps) {
  const v = useTapestryThumb();
  if (!v || v.sessionId !== sessionId) return null;
  const f = v.frames[v.index];
  const x0 = x(f.a);
  return (
    <rect className="bn-tp-thumb-src" x={x0} y={y} width={Math.max(2, x(f.b) - x0)} height={h} rx={2}
      aria-hidden="true" />
  );
}

interface PreviewProps {
  sessionId: string;
  /** The speaker lane: the preview sits just below it. */
  laneRef: RefObject<SVGRectElement | null>;
  /** The slice's scroller: the preview stays within its sides. */
  scrollRef: RefObject<HTMLDivElement | null>;
  width: number;
}

export function ThumbPreview({ sessionId, laneRef, scrollRef, width }: PreviewProps) {
  const v = useTapestryThumb();
  const ref = useRef<HTMLDivElement>(null);
  const mine = v !== null && v.sessionId === sessionId;
  // Placed after layout, from the lane and the scroller as they are now: just below the lane,
  // centred on the pointer, kept within the slice's sides.
  useLayoutEffect(() => {
    const el = ref.current;
    const lane = laneRef.current?.getBoundingClientRect();
    const wrap = scrollRef.current?.getBoundingClientRect();
    if (!el || !lane || !wrap || !v) return;
    const outer = width + 8; // the 3px padding and 1px border each side
    const left = Math.max(wrap.left + 4, Math.min(wrap.right - outer - 4, v.clientX - outer / 2));
    el.style.left = `${Math.round(left)}px`;
    el.style.top = `${Math.round(lane.bottom + 6)}px`;
  }, [v, width, laneRef, scrollRef]);
  if (!mine) return null;
  const f = v.frames[v.index];
  return createPortal(
    <div ref={ref} className="bn-tp-thumb" aria-hidden="true" data-testid="bn-tp-thumb"
      style={{ "--bn-tp-thumb-w": `${width}px` } as React.CSSProperties}>
      <img src={f.src} alt="" />
      <span className="bn-tp-thumb-tc">{formatTimecode(f.t)}</span>
    </div>,
    document.body,
  );
}
