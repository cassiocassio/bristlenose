/**
 * Organisms / Session timeline — the session tapestry (`components/SessionTapestry.tsx`) as the
 * Sessions grid draws it under a row (`.bn-tapestry > .bn-tapestry-cell`, with the transcription
 * diagnostics inside its scroll), and as the transcript page's sticky timeline draws it
 * (`.bn-transcript-timeline`, two, three or five lanes, with the reading window and the player).
 *
 * Both components are lazy here as in the app (SessionsTable, TranscriptTimeline): they are not on
 * any first-paint path, and a static import would pull them into this page's chunk.
 */

import { lazy, type RefObject, Suspense, useLayoutEffect, useRef, useState } from "react";

import type { TranscriptionQuality } from "../../../components/TranscriptionDiagnostics";
import type { TapestryLanes } from "../../../components/SessionTapestry";
import { fitSession } from "../../../utils/tapestryScale";
import type { SpecimenMeta, SpecimenStory } from "../csf";
import { NAMES, QUALITY_GATE_FAILED, QUALITY_SPARSE, QUALITY_WHISPER, TAPESTRY_SESSION } from "./tapestryFixture";

const SessionTapestry = lazy(() => import("../../../components/SessionTapestry"));
const TranscriptionDiagnostics = lazy(() => import("../../../components/TranscriptionDiagnostics"));

export default {
  title: "Organisms/Session timeline",
  description:
    "SessionTapestry (organisms/session-tapestry.css) and TranscriptionDiagnostics (organisms/transcription-diagnostics.css) on a 45-minute fixture interview.",
  caveat:
    "Fixture session without video: the clips carry one scene colour per section, with no scene strip and no hover thumbnail. Clicking the timeline jumps nowhere here (in the app it opens the transcript). The diagnostics show only with the diagnostics preference on, closed until you click them; they are English by design.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["GridSlice", "TranscriptTimeline", "Diagnostics"] as const;

const nameOf = (slot: string) => NAMES[slot] ?? slot;
const noJump = () => {};

/** The container's width, which is what both callers fit the session to. jsdom lays nothing out: 900. */
function useWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setWidth(el.clientWidth || 900);
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

function Slice({ record }: { record?: TranscriptionQuality }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const sPerPx = fitSession(TAPESTRY_SESSION.duration_seconds, width || 900);
  return (
    <div className="bn-tapestry" ref={ref}>
      <div className="bn-tapestry-cell">
        {width > 0 && (
          <Suspense fallback={null}>
            <SessionTapestry session={TAPESTRY_SESSION} sPerPx={sPerPx} nameOf={nameOf} onJump={noJump}>
              {record && (
                <TranscriptionDiagnostics
                  record={record}
                  durationSeconds={TAPESTRY_SESSION.duration_seconds}
                  sPerPx={sPerPx}
                  onJump={noJump}
                />
              )}
            </SessionTapestry>
          </Suspense>
        )}
      </div>
    </div>
  );
}

export const GridSlice: SpecimenStory = {
  name: "Under a Sessions row: five lanes, with the diagnostics",
  render: () => <Slice record={QUALITY_WHISPER} />,
};

/** The section index a moment falls in, as the transcript works out its current section. */
const sectionIndex = (sec: number) =>
  TAPESTRY_SESSION.sections.reduce((at, s, i) => (s.t0 <= sec ? i : at), -1);

function Timeline({ lanes }: { lanes: TapestryLanes }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [start, setStart] = useState(1660);
  const span = 140;
  return (
    <div className="bn-transcript-timeline" ref={ref}>
      {width > 0 && (
        <Suspense fallback={null}>
          <SessionTapestry
            session={TAPESTRY_SESSION}
            sPerPx={fitSession(TAPESTRY_SESSION.duration_seconds, width)}
            nameOf={nameOf}
            onJump={(sec) => setStart(Math.max(0, sec))}
            lanes={lanes}
            readingWindow={[start, start + span]}
            onScrub={(sec) => setStart(Math.max(0, sec))}
            current={sectionIndex(start)}
            player={start + 40}
            quoteAction="jump"
          />
        </Suspense>
      )}
    </div>
  );
}

export const TranscriptTimeline: SpecimenStory = {
  name: "The transcript's sticky timeline at two, three and five lanes (live: drag the reading window)",
  render: () => (
    <div className="bn-sg-stack bn-sg-fill">
      {([2, 3, 5] as const).map((n) => (
        <Timeline key={n} lanes={n} />
      ))}
    </div>
  ),
};

function DiagnosticsAlone({ record }: { record: TranscriptionQuality }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  return (
    <div className="bn-tapestry-scroll" ref={ref}>
      {width > 0 && (
        <Suspense fallback={null}>
          <TranscriptionDiagnostics
            record={record}
            durationSeconds={TAPESTRY_SESSION.duration_seconds}
            sPerPx={fitSession(TAPESTRY_SESSION.duration_seconds, width)}
            onJump={noJump}
          />
        </Suspense>
      )}
    </div>
  );
}

export const Diagnostics: SpecimenStory = {
  name: "Diagnostics: Apple's speech model left for Whisper, and a backend that measured less",
  render: () => (
    <div className="bn-sg-stack bn-sg-fill">
      <DiagnosticsAlone record={QUALITY_GATE_FAILED} />
      <DiagnosticsAlone record={QUALITY_SPARSE} />
    </div>
  ),
};
