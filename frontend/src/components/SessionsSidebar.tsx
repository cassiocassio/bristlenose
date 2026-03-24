/**
 * SessionsSidebar — compact session list for the left sidebar.
 *
 * Renders on Sessions tab and Transcript pages. Data-adaptive:
 * detects 1:1 vs multi-participant, single vs multiple moderators,
 * video vs audio-only. Width-responsive via JS-driven visibility
 * (reads tocWidth from SidebarStore).
 *
 * @module SessionsSidebar
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMatch, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiGet } from "../utils/api";
import { formatCompactDuration, formatCompactDate } from "../utils/format";
import { useProjectId } from "../hooks/useProjectId";
import type { SessionsListResponse, SessionResponse, SpeakerResponse } from "../utils/types";

// ── Data-shape helpers ─────────────────────────────────────────────

function deriveShape(sessions: SessionResponse[]) {
  const allSpeakers = sessions.flatMap((s) => s.speakers);
  const moderators = new Set(
    allSpeakers.filter((sp) => sp.role === "moderator").map((sp) => sp.name),
  );
  const hasMultipleModerators = moderators.size > 1;

  // isOneToOne: every session has exactly 1 participant AND at most 1 moderator total
  const isOneToOne =
    moderators.size <= 1 &&
    sessions.every(
      (s) => s.speakers.filter((sp) => sp.role === "participant").length === 1,
    );

  const hasVideo = sessions.some((s) => s.has_video);
  return { isOneToOne, hasMultipleModerators, hasVideo };
}

function getShortName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts[0] || name;
}

// ── Layout constants (px) ──────────────────────────────────────────
// These match the CSS in sidebar.css. If the CSS changes, update here.
const BADGE_W = 24;       // .badge width
const GAP = 6;            // flex gap in session-entry-row
const DURATION_W = 36;    // "1h 03" at tabular-nums
const SEP_W = 10;         // " · " separator
const DATE_SHORT_W = 42;  // "12 Feb"
const DATE_DOW_W = 70;    // "Wed 12 Feb"
const THUMB_W = 48;       // thumbnail
const THUMB_GAP = 8;      // gap before thumbnail
const PAD = 16;           // horizontal padding (8px each side)

// ── Text measurement ──────────────────────────────────────────────

/** Measure the pixel width of the longest string using an offscreen span. */
function measureLongestText(texts: string[], font: string): number {
  if (texts.length === 0) return 0;
  const span = document.createElement("span");
  span.style.cssText =
    "position:absolute;left:-9999px;top:-9999px;visibility:hidden;white-space:nowrap;font:" +
    font;
  document.body.appendChild(span);
  let max = 0;
  for (const t of texts) {
    span.textContent = t;
    max = Math.max(max, span.offsetWidth);
  }
  document.body.removeChild(span);
  return max;
}

/** Compute content-adaptive breakpoint thresholds from actual name widths. */
function computeBreakpoints(
  sessions: SessionResponse[],
  shape: { isOneToOne: boolean; hasMultipleModerators: boolean; hasVideo: boolean },
  font: string,
) {
  // Collect short names (first name) and full names
  const participants = sessions.flatMap((s) =>
    s.speakers.filter((sp) => sp.role === "participant"),
  );
  const shortNames = participants.map((p) => getShortName(p.name));
  const fullNames = participants.map((p) => p.name);

  const shortW = measureLongestText(shortNames, font);
  const fullW = measureLongestText(fullNames, font);

  // Base = badge + gap + name + gap + padding
  const baseShort = BADGE_W + GAP + shortW + GAP + PAD;
  const baseFull = BADGE_W + GAP + fullW + GAP + PAD;

  // Duration threshold: base + date_short + duration + sep
  const durationAt = baseShort + DATE_SHORT_W + DURATION_W + SEP_W;

  // Day-of-week threshold: base + date_dow + duration + sep
  const dowAt = baseShort + DATE_DOW_W + DURATION_W + SEP_W;

  // Full names threshold: same layout but with full name width
  const fullNameAt = baseFull + DATE_SHORT_W + DURATION_W + SEP_W;

  // Thumbnail threshold: full names + thumb + thumb_gap + stacked date/duration
  const thumbAt = shape.hasVideo
    ? baseFull + THUMB_W + THUMB_GAP + Math.max(DATE_DOW_W, DURATION_W)
    : Infinity;

  return { durationAt, dowAt, fullNameAt, thumbAt };
}

// ── Component ─────────────────────────────────────────────────────

export function SessionsSidebar() {
  const { i18n } = useTranslation();
  const projectId = useProjectId();
  const navigate = useNavigate();
  const transcriptMatch = useMatch("/report/sessions/:sessionId");
  const activeSessionId = transcriptMatch?.params.sessionId ?? null;
  const activeRef = useRef<HTMLAnchorElement | null>(null);
  const navRef = useRef<HTMLElement | null>(null);

  const [data, setData] = useState<SessionsListResponse | null>(null);
  const [liveWidth, setLiveWidth] = useState(280);
  const [navMounted, setNavMounted] = useState(false);

  // Track the sidebar's actual rendered width via ResizeObserver so
  // breakpoints update live during drag (not just on pointerup).
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const navCallbackRef = useCallback((node: HTMLElement | null) => {
    navRef.current = node;
    setNavMounted(!!node);
    resizeObserverRef.current?.disconnect();
    if (node) {
      const ro = new ResizeObserver((entries) => {
        const w = entries[0]?.contentRect.width ?? 0;
        if (w > 0) setLiveWidth(w);
      });
      resizeObserverRef.current = ro;
      ro.observe(node);
    }
  }, []);

  useEffect(() => {
    return () => resizeObserverRef.current?.disconnect();
  }, []);

  useEffect(() => {
    apiGet<SessionsListResponse>("/sessions")
      .then(setData)
      .catch(() => {});
  }, [projectId]);

  // Auto-scroll active session into view.
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [activeSessionId]);

  const shape = useMemo(() => {
    if (!data) return { isOneToOne: true, hasMultipleModerators: false, hasVideo: false };
    return deriveShape(data.sessions);
  }, [data]);

  // Compute content-adaptive breakpoints from actual name widths.
  // Reads the nav element's computed font so measurement matches rendering.
  const bp = useMemo(() => {
    if (!data || !navRef.current) return { durationAt: 260, dowAt: 320, fullNameAt: 360, thumbAt: 360 };
    const cs = getComputedStyle(navRef.current);
    const font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    return computeBreakpoints(data.sessions, shape, font);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- navMounted triggers recompute when element available
  }, [data, shape, navMounted]);

  // Width-driven visibility booleans — uses live observed width.
  const showDuration = liveWidth >= bp.durationAt;
  const showDow = liveWidth >= bp.dowAt;
  const showThumb = shape.hasVideo && liveWidth >= bp.thumbAt;
  const showFullNames = liveWidth >= bp.fullNameAt;

  const handleClick = (
    e: React.MouseEvent<HTMLAnchorElement>,
    sessionId: string,
  ) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    navigate(`/report/sessions/${sessionId}`);
  };

  if (!data) return null;

  return (
    <nav aria-label="Sessions" ref={navCallbackRef}>
      {data.sessions.map((session) => {
        const isActive = session.session_id === activeSessionId;
        const path = `/report/sessions/${session.session_id}`;
        const participants = session.speakers.filter((sp) => sp.role === "participant");
        const moderator = session.speakers.filter((sp) => sp.role === "moderator");
        const duration = formatCompactDuration(session.duration_seconds);
        const dateStr = formatCompactDate(session.session_date, showDow, i18n.language);

        if (shape.isOneToOne) {
          // ── 1:1 variant: badge + name + date ────────────────────
          const p = participants[0];
          const displayName = showFullNames ? p?.name : getShortName(p?.name ?? "");
          return (
            <a
              key={session.session_id}
              href={path}
              className={`session-entry${isActive ? " active" : ""}`}
              ref={isActive ? activeRef : undefined}
              onClick={(e) => handleClick(e, session.session_id)}
            >
              <div className="session-entry-row">
                <span className="badge">{p?.speaker_code ?? "p1"}</span>
                <span className="session-entry-name">{displayName}</span>
                {showDuration && (
                  <span className="session-entry-duration">{duration}</span>
                )}
                {showDuration && <span className="session-entry-sep">&middot;</span>}
                <span className="session-entry-date">{dateStr}</span>
              </div>
            </a>
          );
        }

        // ── Multi-participant variant ─────────────────────────────
        return (
          <a
            key={session.session_id}
            href={path}
            className={`session-entry${isActive ? " active" : ""}`}
            ref={isActive ? activeRef : undefined}
            onClick={(e) => handleClick(e, session.session_id)}
          >
            <div className="session-entry-row">
              <span className="badge session-id-badge">#{session.session_number}</span>
              <div className="session-entry-speakers">
                {renderSpeakerRows(moderator, participants, shape.hasMultipleModerators, showFullNames)}
              </div>
              {/* Inline duration/sep/date — shown when no thumbnail */}
              {!showThumb && showDuration && (
                <span className="session-entry-duration">{duration}</span>
              )}
              {!showThumb && showDuration && (
                <span className="session-entry-sep">&middot;</span>
              )}
              {!showThumb && (
                <span className="session-entry-date">{dateStr}</span>
              )}
              {/* Stacked date/duration + thumbnail — shown at 360px+ with video */}
              {showThumb && (
                <div className="session-entry-right">
                  <span className="session-entry-date">{dateStr}</span>
                  <span className="session-entry-duration">{duration}</span>
                </div>
              )}
              {showThumb && (
                <div className="session-entry-thumb">
                  {session.thumbnail_url ? (
                    <img src={session.thumbnail_url} alt="" />
                  ) : null}
                </div>
              )}
            </div>
          </a>
        );
      })}
    </nav>
  );
}

// ── Speaker rows helper ─────────────────────────────────────────

function renderSpeakerRows(
  moderators: SpeakerResponse[],
  participants: SpeakerResponse[],
  showModeratorBadges: boolean,
  showFullNames: boolean,
) {
  const rows: React.ReactNode[] = [];

  // First participant row — may include moderator badge
  for (let i = 0; i < participants.length; i++) {
    const p = participants[i];
    const displayName = showFullNames ? p.name : getShortName(p.name);
    rows.push(
      <div key={p.speaker_code} className="session-entry-speaker-row">
        {showModeratorBadges && i === 0 && moderators[0] && (
          <span className="badge">{moderators[0].speaker_code}</span>
        )}
        <span className="badge">{p.speaker_code}</span>
        <span className="session-entry-name">{displayName}</span>
      </div>,
    );
  }

  return rows;
}
