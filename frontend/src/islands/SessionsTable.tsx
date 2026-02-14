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
// Formatting helpers
// ---------------------------------------------------------------------------

/** Format seconds as MM:SS or HH:MM:SS. */
function formatDuration(seconds: number): string {
  if (seconds <= 0) return "\u2014"; // em dash
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  if (h > 0) {
    return `${h}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}

const MONTH_ABBR = [
  "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** Format a date string as Finder-style relative date. */
function formatFinderDate(isoDate: string | null): string {
  if (!isoDate) return "\u2014";
  const dt = new Date(isoDate);
  if (isNaN(dt.getTime())) return "\u2014";

  const now = new Date();
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const dtDate = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;

  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  const timePart = `${hh}:${mm}`;

  if (dtDate === todayStr) {
    return `Today at ${timePart}`;
  }

  // Check yesterday
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;
  if (dtDate === yesterdayStr) {
    return `Yesterday at ${timePart}`;
  }

  const month = MONTH_ABBR[dt.getMonth() + 1];
  return `${dt.getDate()} ${month} ${dt.getFullYear()} at ${timePart}`;
}

/** Truncate a filename Finder-style with middle ellipsis. */
function formatFinderFilename(name: string, maxLen: number = 24): string {
  if (name.length <= maxLen) return name;
  const dot = name.lastIndexOf(".");
  if (dot === -1) {
    return name.slice(0, maxLen - 1) + "\u2026";
  }
  const ext = name.slice(dot); // includes dot
  const stem = name.slice(0, dot);
  const budget = maxLen - ext.length - 1; // 1 for ellipsis
  if (budget <= 0) {
    return name.slice(0, maxLen - 1) + "\u2026";
  }
  const front = Math.ceil((budget * 2) / 3);
  const back = budget - front;
  if (back > 0) {
    return stem.slice(0, front) + "\u2026" + stem.slice(-back) + ext;
  }
  return stem.slice(0, front) + "\u2026" + ext;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SpeakerBadge({ speaker }: { speaker: SpeakerResponse }) {
  return (
    <div className="bn-person-id">
      <span className="badge">{speaker.speaker_code}</span>
      {speaker.name && (
        <span className="bn-person-id-name">{speaker.name}</span>
      )}
    </div>
  );
}

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
          <SpeakerBadge key={sp.speaker_code} speaker={sp} />
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
