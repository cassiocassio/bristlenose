/**
 * SessionsTable — React island that replaces the Jinja2 sessions table.
 *
 * Reads `data-project-id` from its mount point, fetches session data from
 * the API, and renders the full sessions table with visual parity to the
 * existing static HTML report.
 *
 * CSS classes match the existing theme so styles apply without changes.
 */

import { useEffect, useState } from "react";
import { JourneyChain, PersonBadge, Sparkline, Thumbnail } from "../components";
import type { SparklineItem } from "../components/Sparkline";
import { formatDuration, formatFinderDate, formatFinderFilename } from "../utils/format";

// ---------------------------------------------------------------------------
// API response types (mirrors Pydantic models in sessions.py)
// ---------------------------------------------------------------------------

interface SpeakerResponse {
  speaker_code: string;
  name: string;
  role: string;
}

interface SourceFileResponse {
  path: string;
  file_type: string;
  filename: string;
}

interface SessionResponse {
  session_id: string;
  session_number: number;
  session_date: string | null;
  duration_seconds: number;
  has_media: boolean;
  has_video: boolean;
  thumbnail_url: string | null;
  speakers: SpeakerResponse[];
  journey_labels: string[];
  sentiment_counts: Record<string, number>;
  source_files: SourceFileResponse[];
}

interface SessionsListResponse {
  sessions: SessionResponse[];
  moderator_names: string[];
  observer_names: string[];
  source_folder_uri: string;
}

// ---------------------------------------------------------------------------
// Sentiment → Sparkline mapping
// ---------------------------------------------------------------------------

const SENTIMENT_ORDER = [
  "frustration",
  "confusion",
  "doubt",
  "surprise",
  "confidence",
  "delight",
  "satisfaction",
];

function sentimentToSparklineItems(
  counts: Record<string, number>,
): SparklineItem[] {
  return SENTIMENT_ORDER.map((sentiment) => ({
    key: sentiment,
    count: counts[sentiment] || 0,
    colour: `var(--bn-sentiment-${sentiment})`,
  }));
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ModeratorHeader({
  moderatorNames,
}: {
  moderatorNames: string[];
}) {
  if (moderatorNames.length === 0) return null;
  const label = "Moderated by " + oxfordList(moderatorNames);
  return <p className="bn-session-moderators">{label}</p>;
}

function ObserverHeader({
  observerNames,
}: {
  observerNames: string[];
}) {
  if (observerNames.length === 0) return null;
  const noun = observerNames.length === 1 ? "Observer" : "Observers";
  const label = `${noun}: ` + oxfordList(observerNames);
  return <p className="bn-session-moderators">{label}</p>;
}

function FolderIcon() {
  return (
    <svg
      className="bn-folder-icon"
      width="14"
      height="12"
      viewBox="0 0 14 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M1.5 2.5a1 1 0 0 1 1-1h2.6l1.4 1.5h5a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1z" />
    </svg>
  );
}

function oxfordList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return items.slice(0, -1).join(", ") + ", and " + items[items.length - 1];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function SessionsTable({
  projectId,
}: {
  projectId: string;
}) {
  const [data, setData] = useState<SessionsListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/projects/${projectId}/sessions`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: SessionsListResponse) => setData(json))
      .catch((err: Error) => setError(err.message));
  }, [projectId]);

  if (error) {
    return (
      <section className="bn-session-table">
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          Failed to load sessions: {error}
        </p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="bn-session-table">
        <p style={{ opacity: 0.5, padding: "1rem" }}>Loading sessions\u2026</p>
      </section>
    );
  }

  const { sessions, moderator_names, observer_names, source_folder_uri } = data;

  const interviewsHeader = source_folder_uri ? (
    <a
      className="bn-interviews-link"
      href="#"
      onClick={(e: React.MouseEvent) => {
        e.preventDefault();
        navigator.clipboard.writeText(source_folder_uri);
      }}
      title="Copy folder path"
    >
      <FolderIcon /> Interviews
    </a>
  ) : (
    "Interviews"
  );

  return (
    <section className="bn-session-table">
      <ModeratorHeader moderatorNames={moderator_names} />
      <ObserverHeader observerNames={observer_names} />
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Speakers</th>
            <th>Start</th>
            <th className="bn-session-duration">Duration</th>
            <th>{interviewsHeader}</th>
            <th></th>
            <th>Sentiment</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((sess) => (
            <SessionRow key={sess.session_id} session={sess} />
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SessionRow({ session }: { session: SessionResponse }) {
  const {
    session_id,
    session_number,
    session_date,
    duration_seconds,
    has_media,
    thumbnail_url,
    speakers,
    journey_labels,
    sentiment_counts,
    source_files,
  } = session;

  // Journey arrow chain (now uses JourneyChain primitive)
  const hasJourney = journey_labels.length > 0;

  // Source file display — media files link to the popout player; others are
  // plain text.  The <a class="timecode"> is picked up by player.js event
  // delegation (no additional JS wiring needed).
  let sourceEl: React.ReactNode = "\u2014";
  if (source_files.length > 0) {
    const sf = source_files[0];
    const displayName = formatFinderFilename(sf.filename);
    const titleAttr =
      displayName !== sf.filename ? sf.filename : undefined;
    if (has_media) {
      sourceEl = (
        <a
          href="#"
          className="timecode"
          data-participant={session_id}
          data-seconds={0}
          data-end-seconds={0}
          title={titleAttr}
        >
          {displayName}
        </a>
      );
    } else {
      sourceEl = (
        <span title={titleAttr}>{displayName}</span>
      );
    }
  }

  return (
    <tr data-session={session_id}>
      <td className="bn-session-id">
        <a href={`/report/sessions/${session_id}`}>
          #{session_number}
        </a>
      </td>
      <td className="bn-session-speakers">
        {speakers.map((sp) => (
          <PersonBadge
            key={sp.speaker_code}
            code={sp.speaker_code}
            role={sp.role as "participant" | "moderator" | "observer"}
            name={sp.name || undefined}
          />
        ))}
      </td>
      <td className="bn-session-meta">
        <div>{formatFinderDate(session_date)}</div>
        {hasJourney && <JourneyChain labels={journey_labels} />}
      </td>
      <td className="bn-session-duration">
        {formatDuration(duration_seconds)}
      </td>
      <td>{sourceEl}</td>
      <td className="bn-session-thumb">
        <Thumbnail hasMedia={has_media} thumbnailUrl={thumbnail_url ?? undefined} />
      </td>
      <td className="bn-session-sentiment">
        <Sparkline items={sentimentToSparklineItems(sentiment_counts)} />
      </td>
    </tr>
  );
}
