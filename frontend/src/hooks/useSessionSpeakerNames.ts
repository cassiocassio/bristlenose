import { useCallback, useEffect, useState } from "react";

import { getSessionList } from "../utils/api";
import { useSpeakersChanged } from "./useSpeakersChanged";

/** Key for a speaker's name in `useSessionSpeakerNames`: the session and the code in it. */
export function speakerNameKey(sessionId: string, code: string): string {
  return `${sessionId}|${code}`;
}

/**
 * The names the researcher has given speakers, by session and code, for a lens whose
 * own payload carries codes only (Signals). A name equal to its code is no name, so
 * it is left out and the badge shows the code alone, as elsewhere. Empty until the
 * read lands, and on a failed read: the code on its own is the honest fallback.
 */
export function useSessionSpeakerNames(): ReadonlyMap<string, string> {
  const [names, setNames] = useState<ReadonlyMap<string, string>>(() => new Map());
  const load = useCallback(() => {
    getSessionList()
      .then((sessions) => {
        const next = new Map<string, string>();
        for (const s of sessions) {
          for (const sp of s.speakers) {
            if (sp.name && sp.name !== sp.speaker_code) {
              next.set(speakerNameKey(s.session_id, sp.speaker_code), sp.name);
            }
          }
        }
        setNames(next);
      })
      .catch(() => {});
  }, []);
  useEffect(load, [load]);
  useSpeakersChanged(load);
  return names;
}
