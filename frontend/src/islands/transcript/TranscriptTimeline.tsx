/**
 * The session timeline in the transcript's sticky slot: the Sessions grid's timeline
 * (components/SessionTapestry.tsx), fitted to this one session, with what the reader can see drawn
 * on it as a window and the popout player's moment as a mark. A click scrolls the transcript;
 * it never navigates. docs/mockups/transcript-timeline-toggle.html.
 *
 * Its own component so a scroll or a player tick re-renders the timeline only, never the
 * transcript. The page owns scrolling (`onJump`, `onScrub`): it holds the paragraphs and the
 * arrival flash.
 */

import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { TapestrySession } from "../../utils/types";
import type { TapestryLanes } from "../../components/SessionTapestry";
import { fitSession } from "../../utils/tapestryScale";
import { screenInk } from "../../utils/sceneInk";
import { usePlayerTime } from "../../contexts/PlayerContext";

// Lazy, as in the grid: the timeline is not on the transcript's first-paint path.
const SessionTapestry = lazy(() => import("../../components/SessionTapestry"));

interface Props {
  session: TapestrySession;
  lanes: TapestryLanes;
  /** The transcript body: its paragraphs carry data-start-seconds / data-end-seconds. */
  bodyRef: React.RefObject<HTMLElement | null>;
  /** The sticky header: the reading area starts at its bottom edge. */
  headerRef: React.RefObject<HTMLElement | null>;
  nameOf: (slot: string) => string;
  onJump: (seconds: number) => void;
  onScrub: (seconds: number) => void;
}

/** The time span of the paragraphs between the header's bottom and the window's, interpolated
 *  within the first and last so the window glides rather than steps. Null before layout. */
export function readingWindow(body: HTMLElement, top: number, bottom: number): [number, number] | null {
  const els = body.querySelectorAll<HTMLElement>(".transcript-segment");
  let a: number | null = null;
  let b: number | null = null;
  for (const el of els) {
    const r = el.getBoundingClientRect();
    // Safari reports impossible rects during a smooth scroll (frontend/CLAUDE.md): skip them.
    if (r.height <= 0 || r.bottom < r.top) continue;
    if (r.bottom <= top) continue;
    if (r.top >= bottom) break;
    const t0 = Number(el.dataset.startSeconds);
    const t1 = Number(el.dataset.endSeconds);
    if (!Number.isFinite(t0) || !Number.isFinite(t1)) continue;
    const span = Math.max(0, t1 - t0);
    if (a === null) a = t0 + span * Math.min(1, Math.max(0, (top - r.top) / r.height));
    b = t0 + span * Math.min(1, Math.max(0, (bottom - r.top) / r.height));
  }
  return a === null || b === null ? null : [a, b];
}

/** The last section flagged at or before a moment: the flag that stays raised. -1 before the first. */
export function sectionAt(sections: readonly { t0: number }[], sec: number): number {
  let i = -1;
  sections.forEach((f, k) => {
    // Half a second's grace: a flag sits on its paragraph's start, which the window's left edge
    // reaches as the paragraph's top meets the header.
    if (f.t0 <= sec + 0.5) i = k;
  });
  return i;
}

export function TranscriptTimeline({ session, lanes, bodyRef, headerRef, nameOf, onJump, onScrub }: Props) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [win, setWin] = useState<[number, number] | null>(null);
  const player = usePlayerTime(session.session_id);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    setWidth(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // The reading window follows the page's scroll, once per frame.
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      const body = bodyRef.current;
      if (!body) return;
      const top = headerRef.current?.getBoundingClientRect().bottom ?? 0;
      const next = readingWindow(body, top, window.innerHeight);
      setWin((prev) => (prev && next && Math.abs(prev[0] - next[0]) < 0.05 && Math.abs(prev[1] - next[1]) < 0.05 ? prev : next));
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    // The header grows when the timeline's lazy chunk lands, with no scroll to say so.
    const header = headerRef.current;
    const ro = header && typeof ResizeObserver !== "undefined" ? new ResizeObserver(schedule) : null;
    if (header) ro?.observe(header);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      ro?.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [bodyRef, headerRef, session, lanes]);

  const clipInk = useMemo(
    () => screenInk(session.turns.flatMap((tn) => (tn.colour ? [tn.colour] : []))),
    [session.turns],
  );
  const current = win ? sectionAt(session.sections, win[0]) : -1;

  // Closed from outside (the Mac's View menu, or a re-read with no timeline) while focus is inside:
  // hand focus to the split control's button rather than dropping it on the page. A layout
  // effect's cleanup runs while the timeline is still in the document.
  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    return () => {
      if (wrap && wrap.contains(document.activeElement)) {
        requestAnimationFrame(() => document.querySelector<HTMLElement>(".bn-timeline-split__main")?.focus({ preventScroll: true }));
      }
    };
  }, []);

  return (
    <div className="bn-transcript-timeline" ref={wrapRef} data-testid="transcript-timeline">
      {width > 0 && (
        <Suspense fallback={null}>
          <SessionTapestry
            session={session}
            sPerPx={fitSession(session.duration_seconds, width)}
            nameOf={nameOf}
            clipInk={clipInk}
            onJump={onJump}
            lanes={lanes}
            readingWindow={win}
            onScrub={onScrub}
            current={current}
            player={player}
            quoteAction="jump"
          />
        </Suspense>
      )}
    </div>
  );
}
