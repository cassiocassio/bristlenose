/**
 * The Sessions lens's web session row, shared by the two lists that draw it:
 * the Sessions lens's sidebar (SessionsSidebar — a row opens its transcript)
 * and the Quotes lens's content sidebar in Sessions grouping (TocSidebar — a
 * row scrolls to that session's quotes).
 *
 * `useSessionRowLayout` owns what both lists must agree on: the study's shape
 * (one participant per session or several, one moderator or more, video or
 * not) and the width rules, measured from the names and followed live as the
 * sidebar is dragged. `SessionEntryRow` draws one row. Each list keeps its own
 * click, its own active row and its own `<nav>`.
 *
 * @module SessionEntry
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatDurationHuman, formatCompactDate } from "../utils/format";
import type { SessionResponse, SpeakerResponse } from "../utils/types";

// ── Data-shape helpers ─────────────────────────────────────────────

/**
 * The m-code speaker's stored role is "researcher", never "moderator" (see the
 * SpeakerRole enum in bristlenose/models.py). Key off the badge code prefix the
 * way TranscriptPage/SessionsTable do — more robust than the role string.
 */
function isModerator(sp: SpeakerResponse): boolean {
  return sp.speaker_code.startsWith("m");
}

function deriveShape(sessions: SessionResponse[]) {
  const allSpeakers = sessions.flatMap((s) => s.speakers);
  const moderators = new Set(
    allSpeakers.filter(isModerator).map((sp) => sp.name),
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
const DURATION_W = 43;    // "4h 28m" — 6 mono chars at ~7.2px (was 36 = 5 chars,
                          // "1h 03"). 6 is the widest across the 236-session local
                          // trial-run corpus; the constant has always been a
                          // typical-widest estimate, not an absolute worst case.
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

  // Full names threshold: full name width, budgeting the day-of-week date.
  // dowAt <= fullNameAt always (baseShort <= baseFull), so by the time full
  // names show, "Wed 12 Feb" is already showing; budgeting the 42 px short
  // date here overflowed the row by up to 28 px at the threshold.
  const fullNameAt = baseFull + DATE_DOW_W + DURATION_W + SEP_W;

  // Thumbnail threshold: full names + thumb + thumb_gap + stacked date/duration
  const thumbAt = shape.hasVideo
    ? baseFull + THUMB_W + THUMB_GAP + Math.max(DATE_DOW_W, DURATION_W)
    : Infinity;

  return { durationAt, dowAt, fullNameAt, thumbAt };
}

// ── Layout hook ───────────────────────────────────────────────────

export interface SessionRowLayout {
  shape: { isOneToOne: boolean; hasMultipleModerators: boolean; hasVideo: boolean };
  showDuration: boolean;
  showDow: boolean;
  showThumb: boolean;
  showFullNames: boolean;
}

/**
 * The study's shape and the width rules for its rows. `sessions` is the whole
 * study, even when a list draws only some of it, so the shape and the
 * thresholds hold still as filters change. Attach `navRef` to the list's
 * `<nav>`: it is measured for its font and observed for its width.
 */
export function useSessionRowLayout(sessions: SessionResponse[] | null): {
  navRef: (node: HTMLElement | null) => void;
  layout: SessionRowLayout;
} {
  const navEl = useRef<HTMLElement | null>(null);
  const [liveWidth, setLiveWidth] = useState(280);
  const [navMounted, setNavMounted] = useState(false);

  // Track the sidebar's actual rendered width via ResizeObserver so
  // breakpoints update live during drag (not just on pointerup).
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const navRef = useCallback((node: HTMLElement | null) => {
    navEl.current = node;
    setNavMounted(!!node);
    resizeObserverRef.current?.disconnect();
    if (node && typeof ResizeObserver !== "undefined") {
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

  const shape = useMemo(() => {
    if (!sessions) return { isOneToOne: true, hasMultipleModerators: false, hasVideo: false };
    return deriveShape(sessions);
  }, [sessions]);

  // Compute content-adaptive breakpoints from actual name widths.
  // Reads the nav element's computed font so measurement matches rendering.
  const bp = useMemo(() => {
    if (!sessions || !navEl.current) return { durationAt: 260, dowAt: 320, fullNameAt: 360, thumbAt: 360 };
    const cs = getComputedStyle(navEl.current);
    const font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    return computeBreakpoints(sessions, shape, font);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- navMounted triggers recompute when element available
  }, [sessions, shape, navMounted]);

  return {
    navRef,
    layout: {
      shape,
      // Width-driven visibility booleans — uses live observed width.
      showDuration: liveWidth >= bp.durationAt,
      showDow: liveWidth >= bp.dowAt,
      showThumb: shape.hasVideo && liveWidth >= bp.thumbAt,
      showFullNames: liveWidth >= bp.fullNameAt,
    },
  };
}

// ── Row ───────────────────────────────────────────────────────────

export function SessionEntryRow({
  session,
  layout,
  href,
  active,
  rowRef,
  onClick,
  current,
}: {
  session: SessionResponse;
  layout: SessionRowLayout;
  /** Used as given: the caller decides between a route and an anchor. */
  href: string;
  active: boolean;
  rowRef?: React.Ref<HTMLAnchorElement>;
  onClick: (e: React.MouseEvent<HTMLAnchorElement>, sessionId: string) => void;
  /** Marks the active row for assistive tech, when the list is a table of contents. */
  current?: "location";
}) {
  const { i18n } = useTranslation();
  const { shape, showDuration, showDow, showThumb, showFullNames } = layout;
  const participants = session.speakers.filter((sp) => sp.role === "participant");
  const moderator = session.speakers.filter(isModerator);
  const duration = formatDurationHuman(session.duration_seconds);
  const dateStr = formatCompactDate(session.session_date, showDow, i18n.language);
  const common = {
    href,
    className: `session-entry${active ? " active" : ""}`,
    ref: active ? rowRef : undefined,
    "aria-current": active ? current : undefined,
    onClick: (e: React.MouseEvent<HTMLAnchorElement>) => onClick(e, session.session_id),
  };

  if (shape.isOneToOne) {
    // ── 1:1 variant: badge + name + date ────────────────────
    const p = participants[0];
    const displayName = showFullNames ? p?.name : getShortName(p?.name ?? "");
    return (
      <a {...common}>
        <div className="session-entry-row">
          <span className="badge">{p?.speaker_code ?? "p1"}</span>
          <span className="session-entry-name">{displayName}</span>
          {showDuration && (
            <span className="session-entry-duration">{duration}</span>
          )}
          {showDuration && <span className="session-entry-sep" aria-hidden="true">&middot;</span>}
          <span className="session-entry-date">{dateStr}</span>
        </div>
      </a>
    );
  }

  // ── Multi-participant variant ─────────────────────────────
  return (
    <a {...common}>
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
          <span className="session-entry-sep" aria-hidden="true">&middot;</span>
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
