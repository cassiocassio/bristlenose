/**
 * Dashboard — React island for the Project tab dashboard.
 *
 * Renders stat cards, compact sessions table, featured quotes,
 * and section/theme navigation lists. Read-only — no user mutations.
 *
 * Navigation actions (stat card clicks, session row clicks, featured
 * quote clicks, nav link clicks) use React context when available
 * (PlayerContext for seekTo, navigation shims for tab/session nav),
 * falling back to vanilla JS globals for legacy island mode.
 */

import { useContext, useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Badge, PersonBadge, TimecodeLink } from "../components";
import { PlayerContext } from "../contexts/PlayerContext";
import { apiGet } from "../utils/api";
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
  window.location.href = `/report/sessions/${sid}${anchor}`;
}

function seekToGlobal(pid: string, seconds: number) {
  window.seekTo?.(pid, seconds);
}

// ── Stat link helpers ───────────────────────────────────────────────────

const TAB_ROUTES: Record<string, string> = {
  project: "/report/",
  sessions: "/report/sessions/",
  quotes: "/report/quotes/",
  codebook: "/report/codebook/",
  analysis: "/report/analysis/",
  settings: "/report/settings/",
  about: "/report/about/",
};

function statTargetToHref(target: string): string {
  const [tab, anchor] = target.split(":");
  const route = TAB_ROUTES[tab] ?? "/report/";
  return anchor ? `${route}#${anchor}` : route;
}

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
    <a
      className="bn-project-stat"
      href={statTargetToHref(target)}
      data-stat-link={target}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        handleStatLink(target);
      }}
    >
      <span className="bn-project-stat-value">{value}</span>
      <span className="bn-project-stat-label">{label}</span>
    </a>
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
        <a
          className="bn-project-stat--pair-half"
          href={statTargetToHref(left.target)}
          data-stat-link={left.target}
          onClick={(e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey) return;
            e.preventDefault();
            handleStatLink(left.target);
          }}
        >
          <span className="bn-project-stat-value">{left.value}</span>
          <span className="bn-project-stat-label">{left.label}</span>
        </a>
      )}
      {right && (
        <a
          className="bn-project-stat--pair-half"
          href={statTargetToHref(right.target)}
          data-stat-link={right.target}
          onClick={(e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey) return;
            e.preventDefault();
            handleStatLink(right.target);
          }}
        >
          <span className="bn-project-stat-value">{right.value}</span>
          <span className="bn-project-stat-label">{right.label}</span>
        </a>
      )}
    </div>
  );
}

function StatsRow({ stats }: { stats: StatsResponse }) {
  const { t, i18n } = useTranslation();
  const hasDuration = stats.total_duration_seconds > 0;
  const hasWords = stats.total_words > 0;

  return (
    <div className="bn-dashboard-full">
      <div className="bn-project-stats">
        <StatCard
          value={stats.session_count}
          label={t("dashboard.session", { count: stats.session_count })}
          target="sessions"
        />

        {(hasDuration || hasWords) && (
          <PairStatCard
            left={
              hasDuration
                ? {
                    value: stats.total_duration_human,
                    label: t("dashboard.ofSessions"),
                    target: "sessions",
                  }
                : null
            }
            right={
              hasWords
                ? {
                    value: stats.total_words.toLocaleString(i18n.language),
                    label: t("dashboard.words"),
                    target: "sessions",
                  }
                : null
            }
          />
        )}

        <PairStatCard
          left={{
            value: stats.quotes_count,
            label: t("dashboard.quote", { count: stats.quotes_count }),
            target: "quotes",
          }}
          right={
            stats.themes_count > 0
              ? {
                  value: stats.themes_count,
                  label: t("dashboard.theme", { count: stats.themes_count }),
                  target: "quotes:themes",
                }
              : null
          }
        />

        {stats.sections_count > 0 && (
          <StatCard
            value={stats.sections_count}
            label={t("dashboard.section", { count: stats.sections_count })}
            target="quotes:sections"
          />
        )}

        {(stats.ai_tags_count > 0 || stats.user_tags_count > 0) && (
          <PairStatCard
            left={
              stats.ai_tags_count > 0
                ? {
                    value: stats.ai_tags_count,
                    label: t("dashboard.aiTag", { count: stats.ai_tags_count }),
                    target: "analysis:section-x-sentiment",
                  }
                : null
            }
            right={
              stats.user_tags_count > 0
                ? {
                    value: stats.user_tags_count,
                    label: t("dashboard.userTag", { count: stats.user_tags_count }),
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
  const { i18n } = useTranslation();
  const {
    session_id,
    session_number,
    session_date,
    duration_seconds,
    speakers,
    source_filename,
    has_media,
  } = session;

  const playerCtx = useContext(PlayerContext);
  const displayFilename = formatFinderFilename(source_filename);
  const fileTitle =
    displayFilename !== source_filename ? source_filename : undefined;

  // Media files open the popout player; non-media files are plain text.
  let sourceEl: React.ReactNode = "\u2014";
  if (source_filename) {
    if (has_media) {
      sourceEl = (
        <a
          href={`#t=0`}
          className="timecode"
          data-participant={session_id}
          data-seconds={0}
          data-end-seconds={0}
          title={fileTitle}
          onClick={(e) => {
            if (!playerCtx) return;
            if (e.metaKey || e.ctrlKey || e.shiftKey) return;
            e.preventDefault();
            playerCtx.seekTo(session_id, 0);
          }}
        >
          {displayFilename}
        </a>
      );
    } else {
      sourceEl = <span title={fileTitle}>{displayFilename}</span>;
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
        <div>{formatFinderDate(session_date, i18n.language)}</div>
      </td>
      <td className="bn-session-duration">
        {formatDuration(duration_seconds)}
      </td>
      <td>{sourceEl}</td>
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
  const { t } = useTranslation();
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
              <th>{t("dashboard.colId")}</th>
              <th>{t("dashboard.colParticipants")}</th>
              <th>{t("dashboard.colStart")}</th>
              <th className="bn-session-duration">{t("dashboard.colDuration")}</th>
              <th>{t("dashboard.colInterviews")}</th>
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
  const playerCtx = useContext(PlayerContext);
  const timecodeStr = formatTimecode(quote.start_timecode);

  const handleCardClick = (e: React.MouseEvent) => {
    // If the click originated on a link/button, let it handle itself.
    if ((e.target as HTMLElement).closest("a, button")) return;

    // Try video seek first.
    const seekFn = playerCtx?.seekTo ?? (window.seekTo ? seekToGlobal : null);
    if (quote.has_media && seekFn) {
      seekFn(quote.participant_id, quote.start_timecode);
      return;
    }

    // Fall back to session navigation.
    const anchor = `t-${quote.session_id}-${Math.floor(quote.start_timecode)}`;
    const url = `/report/sessions/${quote.session_id}#${anchor}`;
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
          href={`/report/sessions/${quote.session_id}#t-${quote.session_id}-${Math.floor(quote.start_timecode)}`}
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
  const { t } = useTranslation();
  return (
    <div>
      <p className="bn-coverage-session-title">{t("dashboard.coverageSession", { number: session.session_number })}</p>
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
  const { t } = useTranslation();
  const { pct_in_report, pct_moderator, pct_omitted, omitted_by_session } = coverage;

  return (
    <div className="bn-coverage-box bn-dashboard-full">
      <h3>{t("dashboard.transcriptCoverage")}</h3>

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
          <span className="bn-coverage-legend-value">{pct_in_report}%</span> {t("dashboard.inReport")}
        </span>
        {pct_moderator > 0 && (
          <span className="bn-coverage-legend-item">
            <span className="bn-coverage-legend-dot bn-coverage-legend-dot--moderator" />
            <span className="bn-coverage-legend-value">{pct_moderator}%</span> {t("dashboard.moderator")}
          </span>
        )}
        {pct_omitted > 0 && (
          <span className="bn-coverage-legend-item">
            <span className="bn-coverage-legend-dot bn-coverage-legend-dot--omitted" />
            <span className="bn-coverage-legend-value">{pct_omitted}%</span> {t("dashboard.omitted")}
          </span>
        )}
      </div>

      {/* Omitted segments disclosure */}
      {pct_omitted === 0 ? (
        <p className="bn-coverage-empty">
          {t("dashboard.nothingOmitted")}
        </p>
      ) : omitted_by_session.length > 0 ? (
        <details>
          <summary>{t("dashboard.showOmitted")}</summary>
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
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<DashboardResponse>("/dashboard")
      .then((json) => setData(json))
      .catch((err: Error) => setError(err.message));
  }, [projectId]);

  if (error) {
    return (
      <div className="bn-dashboard">
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          {t("dashboard.failedToLoad", { error })}
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bn-dashboard">
        <p style={{ opacity: 0.5, padding: "1rem" }}>{t("dashboard.loading")}</p>
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

      <NavList heading={t("quotes.sections")} items={data.sections} tabTarget="quotes" />
      <NavList heading={t("quotes.themes")} items={data.themes} tabTarget="quotes" />

      {data.coverage && <CoverageBox coverage={data.coverage} />}
    </div>
  );
}
