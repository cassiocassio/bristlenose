/**
 * Re-read a surface's speakers after a picker write, or its undo or redo,
 * has landed (docs/design-people.md §J8.7). The transcript and the dashboard
 * do not draw a pick optimistically as the Sessions grid does: a pick can
 * renumber codes, which only the server knows, so they simply ask again.
 */

import { useEffect, useRef } from "react";

import { PEOPLE_CHANGED_EVENT } from "../utils/peopleChanged";

/** The speakers-written event name, repeated here so a first-paint surface
 *  need not load the picking module to listen. */
const SPEAKERS_WRITTEN_EVENT = "bn:speakers-written";

export function useSpeakersChanged(reload: () => void): void {
  const latest = useRef(reload);
  useEffect(() => {
    latest.current = reload;
  }, [reload]);

  useEffect(() => {
    const onWritten = () => latest.current();
    // An undo or redo announces before its write is queued; wait for it.
    const onUndone = () => {
      void import("../utils/speakerNames").then(({ speakerWritesSettled }) =>
        Promise.resolve().then(speakerWritesSettled).then(() => latest.current()),
      );
    };
    window.addEventListener(SPEAKERS_WRITTEN_EVENT, onWritten);
    window.addEventListener(PEOPLE_CHANGED_EVENT, onUndone);
    return () => {
      window.removeEventListener(SPEAKERS_WRITTEN_EVENT, onWritten);
      window.removeEventListener(PEOPLE_CHANGED_EVENT, onUndone);
    };
  }, []);
}
