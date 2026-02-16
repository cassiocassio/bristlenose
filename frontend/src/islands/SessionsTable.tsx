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
import { PersonBadge } from "../components";
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
  speakers: SpeakerResponse[];
  journey_labels: string[];
  sentiment_counts: Record<string, number>;
  source_files: SourceFileResponse[];
}

interface SessionsListResponse {
  sessions: SessionResponse[];
  moderator_names: string[];
  observer_names: string[];
}

// ---------------------------------------------------------------------------
// Constants (matching render_html.py sparkline config)
// ---------------------------------------------------------------------------

const SPARKLINE_ORDER = [
  "satisfaction",
  "delight",
  "confidence",
  "surprise",
  "doubt",
  "confusion",
  "frustration",
];

const SPARKLINE_MAX_H = 20; // px
const SPARKLINE_MIN_H = 2; // px — non-zero counts always visible
const SPARKLINE_GAP = 2; // px
const SPARKLINE_OPACITY = 0.8;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SentimentSparkline({
  counts,
}: {
  counts: Record<string, number>;
}) {
  const maxVal = Math.max(
    ...SPARKLINE_ORDER.map((s) => counts[s] || 0),
    0,
  );
  if (maxVal === 0) return <>{"\u2014"}</>;

  return (
    <div
      className="bn-sparkline"
      style={{ gap: `${SPARKLINE_GAP}px` }}
    >
      {SPARKLINE_ORDER.map((sentiment) => {
        const c = counts[sentiment] || 0;
        const h =
          c > 0
            ? Math.max(
                Math.round((c / maxVal) * SPARKLINE_MAX_H),
                SPARKLINE_MIN_H,
              )
            : 0;
        return (
          <span
            key={sentiment}
            className="bn-sparkline-bar"
            style={{
              height: `${h}px`,
              background: `var(--bn-sentiment-${sentiment})`,
              opacity: SPARKLINE_OPACITY,
            }}
          />
        );
      })}
    </div>
  );
}

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

  const { sessions, moderator_names, observer_names } = data;

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
            <th>Interviews</th>
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
    speakers,
    journey_labels,
    sentiment_counts,
    source_files,
  } = session;

  // Journey arrow chain
  const journey =
    journey_labels.length > 0 ? journey_labels.join(" \u2192 ") : "";

  // Source file display
  let sourceEl: React.ReactNode = "\u2014";
  if (source_files.length > 0) {
    const sf = source_files[0];
    const displayName = formatFinderFilename(sf.filename);
    const titleAttr =
      displayName !== sf.filename ? sf.filename : undefined;
    sourceEl = (
      <span title={titleAttr}>{displayName}</span>
    );
  }

  return (
    <tr data-session={session_id}>
      <td className="bn-session-id">
        <a
          href={`sessions/transcript_${session_id}.html`}
          data-session-link={session_id}
        >
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
        {journey && (
          <div className="bn-session-journey">{journey}</div>
        )}
      </td>
      <td className="bn-session-duration">
        {formatDuration(duration_seconds)}
      </td>
      <td>{sourceEl}</td>
      <td className="bn-session-thumb">
        {has_media && (
          <div className="bn-video-thumb">
            <span className="bn-play-icon">&#9654;</span>
          </div>
        )}
      </td>
      <td className="bn-session-sentiment">
        <SentimentSparkline counts={sentiment_counts} />
      </td>
    </tr>
  );
}
