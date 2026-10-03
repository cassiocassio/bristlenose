/**
 * The Discussion lens's one data seam.
 *
 * Fetches the stage's record (`GET /discussion`, speaker codes only) and the
 * session list (`/sessions`), and joins the two into the shape the lens
 * renders. Names come only from `/sessions`, which an anonymised export blanks,
 * so the lens shows codes there — never a name the export meant to remove.
 */

import { apiGet, getSessionList, type SessionListItem } from "../../utils/api";
import type { DiscussionData, DiscussionQuote, DiscussionSession } from "./types";

export type DiscussionStatus = "not_run" | "stale" | "ready" | "partial" | "failed";

interface RecordSession {
  id: string;
  number: number;
  participants: string[];
  duration: string;
  seconds: number;
  state?: DiscussionSession["state"];
}

type RecordQuote = Omit<DiscussionQuote, "key" | "name">;

interface DiscussionRecord extends Omit<DiscussionData, "sessions" | "quotes"> {
  sessions: RecordSession[];
  quotes: RecordQuote[];
}

interface DiscussionResponse {
  status: DiscussionStatus;
  record: DiscussionRecord | null;
}

export interface DiscussionLoad {
  status: DiscussionStatus;
  data: DiscussionData | null;
}

/** Codes to names, per session: a code like `p1` is one person in one session. */
export function joinNames(record: DiscussionRecord, sessions: SessionListItem[]): DiscussionData {
  const names = new Map<string, string>();
  for (const s of sessions) {
    for (const sp of s.speakers) names.set(`${s.session_id}|${sp.speaker_code}`, sp.name);
  }
  const nameOf = (session: string, code: string) => names.get(`${session}|${code}`) ?? "";
  return {
    ...record,
    sessions: record.sessions.map((s) => ({
      ...s,
      participants: s.participants.map((code) => ({ code, name: nameOf(s.id, code) })),
    })),
    quotes: record.quotes.map((q, i) => ({ ...q, key: `q${i}`, name: nameOf(q.session, q.participant) })),
  };
}

export async function loadDiscussion(): Promise<DiscussionLoad> {
  const [resp, sessions] = await Promise.all([
    apiGet<DiscussionResponse>("/discussion"),
    getSessionList(),
  ]);
  if (!resp.record) return { status: resp.status, data: null };
  if (resp.record.version !== 1) {
    throw new Error(`Discussion data version ${String(resp.record.version)} is not supported`);
  }
  return { status: resp.status, data: joinNames(resp.record, sessions) };
}
