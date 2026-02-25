/**
 * Dashboard — React island for the Project tab dashboard.
 *
 * Renders stat cards, compact sessions table, featured quotes,
 * and section/theme navigation lists. Read-only — no user mutations.
 *
 * Navigation actions (stat card clicks, session row clicks, featured
 * quote clicks, nav link clicks) delegate to vanilla JS globals
 * defined in global-nav.js and player.js.
 */

import { useEffect, useState, useMemo } from "react";
import { Badge, PersonBadge, TimecodeLink } from "../components";
import { formatDuration, formatFinderDate, formatFinderFilename, formatTimecode } from "../utils/format";
import type {
  CoverageResponse,
  DashboardResponse,
  DashboardSessionResponse,
  FeaturedQuoteResponse,
  NavItem,
  SessionOmittedResponse,
  StatsResponse,
} from "../utils/types";

// ── Vanilla JS interop ─────────────────────────────────────────────────
// These functions are defined in global-nav.js and player.js.

declare global {
  interface Window {
    switchToTab?: (tab: string, pushHash?: boolean) => void;
    scrollToAnchor?: (anchorId: string, opts?: { block?: string; highlight?: boolean }) => void;
    navigateToSession?: (sid: string, anchorId?: string) => void;
    seekTo?: (pid: string, seconds: number) => void;
  }
}

function switchToTab(tab: string, pushHash?: boolean) {
  window.switchToTab?.(tab, pushHash);
}

function scrollToAnchor(anchorId: string, opts?: { block?: string; highlight?: boolean }) {
  window.scrollToAnchor?.(anchorId, opts);
}

function navigateToSession(sid: string, anchorId?: string) {
  const anchor = anchorId ? `#${anchorId}` : "";
  window.location.href = `sessions/transcript_${sid}.html${anchor}`;
}

function seekTo(pid: string, seconds: number) {
  window.seekTo?.(pid, seconds);
}

// ── Stat link handler ───────────────────────────────────────────────────

function handleStatLink(target: string) {
  // target format: "tab" or "tab:anchor"
  const [tab, anchor] = target.split(":");
  switchToTab(tab);
  if (anchor) {
    scrollToAnchor(anchor);
  }
}

// ── Sub-components ──────────────────────────────────────────────────────

// ---------- Stat cards ----------

function StatCard({
  value,
  label,
  target,
}: {
  value: string | number;
  label: string;
  target: string;
}) {
  return (
    <div
      className="bn-project-stat"
      data-stat-link={target}
      onClick={() => handleStatLink(target)}
    >
      <span className="bn-project-stat-value">{value}</span>
      <span className="bn-project-stat-label">{label}</span>
    </div>
  );
}

function PairStatCard({
  left,
  right,
}: {
  left: { value: string | number; label: string; target: string } | null;
  right: { value: string | number; label: string; target: string } | null;
}) {
  if (!left && !right) return null;
  return (
    <div className="bn-project-stat bn-project-stat--pair">
      {left && (
        <div
          className="bn-project-stat--pair-half"
          data-stat-link={left.target}
          onClick={() => handleStatLink(left.target)}
        >
          <span className="bn-project-stat-value">{left.value}</span>
          <span className="bn-project-stat-label">{left.label}</span>
        </div>
      )}
      {right && (
        <div
          className="bn-project-stat--pair-half"
          data-stat-link={right.target}
          onClick={() => handleStatLink(right.target)}
        >
          <span className="bn-project-stat-value">{right.value}</span>
          <span className="bn-project-stat-label">{right.label}</span>
        </div>
      )}
    </div>
  );
}

function StatsRow({ stats }: { stats: StatsResponse }) {
  // Duration label — the API returns total_duration_human which includes
  // the value, but we want just the value and a separate label.
  // total_duration_human is like "1h 23m" — we use it as the value.
  const hasDuration = stats.total_duration_seconds > 0;
  const hasWords = stats.total_words > 0;

  return (
    <div className="bn-dashboard-full">
      <div className="bn-project-stats">
        {/* Sessions count */}
        <StatCard
          value={stats.session_count}
          label={stats.session_count === 1 ? "session" : "sessions"}
          target="sessions"
        />

        {/* Duration + Words pair */}
        {(hasDuration || hasWords) && (
          <PairStatCard
            left={
              hasDuration
                ? {
                    value: stats.total_duration_human,
                    label: "of sessions",
                    target: "sessions",
                  }
                : null
            }
            right={
              hasWords
                ? {
                    value: stats.total_words.toLocaleString(),
                    label: "words",
                    target: "sessions",
                  }
                : null
            }
          />
        )}

        {/* Quotes + Themes pair */}
        <PairStatCard
          left={{
            value: stats.quotes_count,
            label: stats.quotes_count === 1 ? "quote" : "quotes",
            target: "quotes",
          }}
          right={
            stats.themes_count > 0
              ? {
                  value: stats.themes_count,
                  label: stats.themes_count === 1 ? "theme" : "themes",
                  target: "quotes:themes",
                }
              : null
          }
        />

        {/* Sections */}
        {stats.sections_count > 0 && (
          <StatCard
            value={stats.sections_count}
            label={stats.sections_count === 1 ? "section" : "sections"}
            target="quotes:sections"
          />
        )}

        {/* AI tags + User tags pair */}
        {(stats.ai_tags_count > 0 || stats.user_tags_count > 0) && (
          <PairStatCard
            left={
              stats.ai_tags_count > 0
                ? {
                    value: stats.ai_tags_count,
                    label: stats.ai_tags_count === 1 ? "AI tag" : "AI tags",
                    target: "analysis:section-x-sentiment",
                  }
                : null
            }
            right={
              stats.user_tags_count > 0
                ? {
                    value: stats.user_tags_count,
                    label: stats.user_tags_count === 1 ? "user tag" : "user tags",
                    target: "codebook",
                  }
                : null
            }
          />
        )}
      </div>
    </div>
  );
}

// ---------- Compact sessions table ----------

function CompactSessionRow({
  session,
}: {
  session: DashboardSessionResponse;
}) {
  const {
    session_id,
    session_number,
    session_date,
    duration_seconds,
    speakers,
    source_filename,
  } = session;

  const displayFilename = formatFinderFilename(source_filename);
  const fileTitle =
    displayFilename !== source_filename ? source_filename : undefined;

  return (
    <tr data-session={session_id}>
      <td className="bn-session-id">
        <a href={`sessions/transcript_${session_id}.html`}>
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
      </td>
      <td className="bn-session-duration">
        {formatDuration(duration_seconds)}
      </td>
      <td>
        {source_filename ? (
          <span title={fileTitle}>{displayFilename}</span>
        ) : (
          "\u2014"
        )}
      </td>
    </tr>
  );
}

function CompactSessionsTable({
  sessions,
  moderatorHeader,
  observerHeader,
}: {
  sessions: DashboardSessionResponse[];
  moderatorHeader: string;
  observerHeader: string;
}) {
  return (
    <div className="bn-dashboard-pane bn-dashboard-full">
      <section className="bn-session-table">
        {moderatorHeader && (
          <p className="bn-session-moderators">{moderatorHeader}</p>
        )}
        {observerHeader && (
          <p className="bn-session-moderators">{observerHeader}</p>
        )}
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Participants</th>
              <th>Start</th>
              <th className="bn-session-duration">Duration</th>
              <th>Interviews</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((sess) => (
              <CompactSessionRow key={sess.session_id} session={sess} />
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

// ---------- Featured quotes ----------

function FeaturedQuote({ quote }: { quote: FeaturedQuoteResponse }) {
  const timecodeStr = formatTimecode(quote.start_timecode);

  const handleCardClick = (e: React.MouseEvent) => {
    // If the click originated on a link/button, let it handle itself.
    if ((e.target as HTMLElement).closest("a, button")) return;

    // Try video seek first.
    if (quote.has_media && window.seekTo) {
      seekTo(quote.participant_id, quote.start_timecode);
      return;
    }

    // Fall back to session navigation.
    const anchor = `t-${quote.session_id}-${Math.floor(quote.start_timecode)}`;
    const url = `sessions/transcript_${quote.session_id}.html#${anchor}`;
    if (e.metaKey || e.ctrlKey || e.shiftKey) {
      window.open(url, "_blank");
      return;
    }
    navigateToSession(quote.session_id, anchor);
  };

  return (
    <div
      className="bn-featured-quote"
      data-quote-id={quote.dom_id}
      data-rank={quote.rank}
      onClick={handleCardClick}
    >
      {quote.researcher_context && (
        <span className="context">[{quote.researcher_context}]</span>
      )}

      <span className="quote-text">
        &ldquo;{quote.text}&rdquo;
      </span>

      <div className="bn-featured-footer">
        {quote.has_media ? (
          <TimecodeLink
            seconds={quote.start_timecode}
            endSeconds={quote.end_timecode}
            participantId={quote.participant_id}
          />
        ) : (
          <span className="timecode">[{timecodeStr}]</span>
        )}

        <a
          href={`sessions/transcript_${quote.session_id}.html#t-${quote.session_id}-${Math.floor(quote.start_timecode)}`}
          className="speaker-link"
        >
          <PersonBadge
            code={quote.participant_id}
            role="participant"
            name={
              quote.speaker_name !== quote.participant_id
                ? quote.speaker_name
                : undefined
            }
          />
        </a>

        {quote.sentiment && (
          <Badge
            text={quote.sentiment}
            variant="ai"
            sentiment={quote.sentiment}
          />
        )}
      </div>
    </div>
  );
}

function FeaturedQuotesRow({
  quotes,
}: {
  quotes: FeaturedQuoteResponse[];
}) {
  // Reshuffle logic: prefer starred, exclude hidden, show top 3.
  const visible = useMemo(() => {
    const candidates = quotes.filter((q) => !q.is_hidden);
    // Starred first, then by original rank.
    candidates.sort((a, b) => {
      if (a.is_starred !== b.is_starred) return a.is_starred ? -1 : 1;
      return a.rank - b.rank;
    });
    return candidates.slice(0, 3);
  }, [quotes]);

  if (visible.length === 0) return null;

  return (
    <div
      className="bn-featured-row bn-dashboard-full"
      data-visible-count="3"
    >
      {visible.map((q) => (
        <FeaturedQuote key={q.dom_id} quote={q} />
      ))}
    </div>
  );
}

// ---------- Section/theme nav lists ----------

function NavList({
  heading,
  items,
  tabTarget,
}: {
  heading: string;
  items: NavItem[];
  tabTarget: string;
}) {
  if (items.length === 0) return null;

  return (
    <div className="bn-dashboard-pane">
      <nav className="bn-dashboard-nav">
        <h3>{heading}</h3>
        <ul>
          {items.map((item) => (
            <li key={item.anchor}>
              <a
                href={`#${item.anchor}`}
                onClick={(e) => {
                  if (e.metaKey || e.ctrlKey || e.shiftKey) return;
                  e.preventDefault();
                  switchToTab(tabTarget);
                  scrollToAnchor(item.anchor);
                }}
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

// ---------- Coverage box ----------

function OmittedSession({
  session,
}: {
  session: SessionOmittedResponse;
}) {
  return (
    <div>
      <p className="bn-coverage-session-title">Session {session.session_number}</p>
      {session.full_segments.map((seg, i) => (
        <div className="bn-coverage-segment" key={i}>
          <TimecodeLink
            seconds={seg.start_time}
            participantId={seg.speaker_code}
          />
          <PersonBadge
            code={seg.speaker_code}
            role="participant"
          />
          <span>{seg.text}</span>
        </div>
      ))}
      {session.fragments_html && (
        <p
          className="bn-coverage-fragments"
          dangerouslySetInnerHTML={{ __html: session.fragments_html }}
        />
      )}
    </div>
  );
}

function CoverageBox({
  coverage,
}: {
  coverage: CoverageResponse;
}) {
  const { pct_in_report, pct_moderator, pct_omitted, omitted_by_session } = coverage;

  return (
    <div className="bn-coverage-box bn-dashboard-full">
      <h3>Transcript coverage</h3>

      {/* Stacked bar */}
      <div className="bn-coverage-bar">
        <div
          className="bn-coverage-bar-segment bn-coverage-bar-segment--report"
          style={{ width: `${pct_in_report}%` }}
        />
        {pct_moderator > 0 && (
          <div
            className="bn-coverage-bar-segment bn-coverage-bar-segment--moderator"
            style={{ width: `${pct_moderator}%` }}
          />
        )}
        {pct_omitted > 0 && (
          <div
            className="bn-coverage-bar-segment bn-coverage-bar-segment--omitted"
            style={{ width: `${pct_omitted}%` }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="bn-coverage-legend">
        <span className="bn-coverage-legend-item">
          <span className="bn-coverage-legend-dot bn-coverage-legend-dot--report" />
          <span className="bn-coverage-legend-value">{pct_in_report}%</span> in report
        </span>
        {pct_moderator > 0 && (
          <span className="bn-coverage-legend-item">
            <span className="bn-coverage-legend-dot bn-coverage-legend-dot--moderator" />
            <span className="bn-coverage-legend-value">{pct_moderator}%</span> moderator
          </span>
        )}
        {pct_omitted > 0 && (
          <span className="bn-coverage-legend-item">
            <span className="bn-coverage-legend-dot bn-coverage-legend-dot--omitted" />
            <span className="bn-coverage-legend-value">{pct_omitted}%</span> omitted
          </span>
        )}
      </div>

      {/* Omitted segments disclosure */}
      {pct_omitted === 0 ? (
        <p className="bn-coverage-empty">
          Nothing omitted &mdash; all participant speech is in the report.
        </p>
      ) : omitted_by_session.length > 0 ? (
        <details>
          <summary>Show omitted quotes</summary>
          <div>
            {omitted_by_session.map((sess) => (
              <OmittedSession key={sess.session_id} session={sess} />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────

interface DashboardProps {
  projectId: string;
}

export function Dashboard({ projectId }: DashboardProps) {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/projects/${projectId}/dashboard`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: DashboardResponse) => setData(json))
      .catch((err: Error) => setError(err.message));
  }, [projectId]);

  if (error) {
    return (
      <div className="bn-dashboard">
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          Failed to load dashboard: {error}
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bn-dashboard">
        <p style={{ opacity: 0.5, padding: "1rem" }}>Loading dashboard&hellip;</p>
      </div>
    );
  }

  return (
    <div className="bn-dashboard">
      <StatsRow stats={data.stats} />

      <CompactSessionsTable
        sessions={data.sessions}
        moderatorHeader={data.moderator_header}
        observerHeader={data.observer_header}
      />

      <FeaturedQuotesRow quotes={data.featured_quotes} />

      <NavList heading="Sections" items={data.sections} tabTarget="quotes" />
      <NavList heading="Themes" items={data.themes} tabTarget="quotes" />

      {data.coverage && <CoverageBox coverage={data.coverage} />}
    </div>
  );
}
