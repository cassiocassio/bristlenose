/**
 * The event an undo or redo of a speaker name fires, so views showing that
 * slot redraw it. Its own module so a view can listen without loading the
 * write path (`speakerNames`, fetched on demand at the first rename).
 */

/** What one speaker slot holds. */
export interface SpeakerNameState {
  /** Undefined when the caller does not know it (a payload from before
   *  `/sessions` reported it): the write then leaves the stored value alone,
   *  rather than blanking a full name nobody asked to change. */
  full_name?: string;
  short_name: string;
  confirmed: boolean;
}

export const PEOPLE_CHANGED_EVENT = "bn:people-changed";

export interface PeopleChangedDetail {
  sessionId: string;
  code: string;
  state: SpeakerNameState;
}
