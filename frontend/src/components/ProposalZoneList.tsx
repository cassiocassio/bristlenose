/**
 * ProposalZoneList — collapsible list of proposals for one zone.
 *
 * Groups proposals by session ID with session headers.
 * Each row shows timecode, speaker, quote text, tag badge (with rationale tooltip),
 * confidence score, and zone-specific action buttons.
 */

import { useState, useMemo, useCallback, useEffect, useId } from "react";
import { useTranslation } from "react-i18next";
import type { ProposedTagResponse } from "../utils/types";
import { getTagBg } from "../utils/colours";
import { featureFlags } from "../utils/featureFlags";
import { reportHref } from "../utils/reportHref";
import { formatTimecode } from "../utils/format";
import { placeProps, windowPlace } from "../utils/contextPlace";
import { isEmbedded } from "../utils/embedded";
import { postOpenInNewWindow } from "../shims/bridge";
import { isPinned } from "../utils/recut";
import { confidenceText } from "../utils/confidenceStep";
import { Icon } from "./Icon";
import { RollingNumber } from "./RollingNumber";
import { TimecodeLink } from "./TimecodeLink";

type Zone = "accepted" | "tentative" | "excluded";

interface ProposalZoneListProps {
  zone: Zone;
  proposals: ProposedTagResponse[];
  defaultExpanded?: boolean;
  onAccept?: (proposalId: number) => void;
  onDeny?: (proposalId: number) => void;
  removing: Set<number>;
  /** Draw every quote whole rather than one line cut to fit. */
  wordWrap?: boolean;
}

const SESSION_ORDER = new Intl.Collator(undefined, { numeric: true });

const ZONE_LABEL_KEYS: Record<Zone, string> = {
  accepted: "autocode.review.zoneAccepted",
  tentative: "autocode.review.zoneTentative",
  excluded: "autocode.review.zoneExcluded",
};

export function ProposalZoneList({
  zone,
  proposals,
  defaultExpanded = false,
  onAccept,
  onDeny,
  removing,
  wordWrap = false,
}: ProposalZoneListProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(defaultExpanded);
  // Open and done opening. The body clips its rows only while it opens or closes (the
  // height animates); once settled open it clips nothing, so a long zone shows every row
  // and a row gliding in is seen all the way (owner, 24 Nov 2026). Rows in a zone not
  // settled open count as hidden to the motion (`data-flip-collapsed`).
  const [settled, setSettled] = useState(defaultExpanded);
  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => setSettled(true), 220); // the 0.2 s open, in the CSS
    return () => clearTimeout(timer);
  }, [isOpen]);
  const bodyId = useId();

  // A row whose decision is in flight stays where it is, dimmed, and is counted here,
  // until it lands where the decision puts it (then the counts roll).
  const visibleCount = proposals.length;

  /** Group proposals by session, sessions in number order (s2 before s10), sorted by
   *  confidence desc within each session. */
  const groupedBySession = useMemo(() => {
    const sorted = [...proposals].sort((a, b) => b.confidence - a.confidence);
    const map = new Map<string, ProposedTagResponse[]>();
    for (const p of sorted) {
      if (!map.has(p.session_id)) map.set(p.session_id, []);
      map.get(p.session_id)!.push(p);
    }
    return new Map([...map.entries()].sort(([a], [b]) => SESSION_ORDER.compare(a, b)));
  }, [proposals]);

  const toggleOpen = useCallback(() => {
    setSettled(false);
    setIsOpen((prev) => !prev);
  }, []);

  if (visibleCount === 0 && !isOpen) return null;

  return (
    <div className="threshold-zone-list" data-testid={`bn-zone-${zone}`} data-flip-zone="">
      {/* A button, so the zone opens from the keyboard too. It sticks to the top of the
          scroll while its rows pass under it, until the next zone pushes it away. */}
      <button
        type="button"
        className="threshold-zone-list-header"
        onClick={toggleOpen}
        aria-expanded={isOpen}
        aria-controls={bodyId}
        data-testid={`bn-zone-header-${zone}`}
        data-flip={`zone-${zone}`}
        data-flip-landing=""
      >
        <span className={`threshold-zone-list-chevron${isOpen ? " threshold-zone-list-chevron--open" : ""}`}>
          <Icon name="disclose" decorative />
        </span>
        <span>{t(ZONE_LABEL_KEYS[zone])}</span>
        <span className="threshold-zone-list-count">(<RollingNumber value={visibleCount} />)</span>
      </button>

      {/* A closed zone is inert: its rows are out of the Tab order and the accessibility
          tree, as `aria-expanded="false"` says. */}
      <div
        id={bodyId}
        className={`threshold-zone-list-body${isOpen ? " threshold-zone-list-body--open" : ""}${
          isOpen && settled ? " threshold-zone-list-body--settled" : ""}`}
        data-flip-collapsed={isOpen && settled ? undefined : ""}
        inert={!isOpen}
      >
        <div className="threshold-zone-list-inner">
        <table
          className={`threshold-proposal-table${wordWrap ? " threshold-proposal-table--wrap" : ""}`}
        >
          <tbody>
            {Array.from(groupedBySession.entries()).map(([sessionId, items]) => (
              <SessionRows
                key={sessionId}
                sessionId={sessionId}
                items={items}
                zone={zone}
                removing={removing}
                onAccept={onAccept}
                onDeny={onDeny}
              />
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}

// ── Session row group ─────────────────────────────────────────────────

interface SessionRowsProps {
  sessionId: string;
  items: ProposedTagResponse[];
  zone: Zone;
  removing: Set<number>;
  onAccept?: (proposalId: number) => void;
  onDeny?: (proposalId: number) => void;
}

function SessionRows({ sessionId, items, zone, removing, onAccept, onDeny }: SessionRowsProps) {
  const { t, i18n } = useTranslation();
  if (items.length === 0) return null;
  // A row gliding to its new place ignores a click: the button under a still pointer is
  // passing, not the one aimed at (utils/reviewMotion.ts sets `data-flip-moving`).
  const act = (fn: ((id: number) => void) | undefined, id: number) =>
    (e: React.MouseEvent<HTMLButtonElement>) => {
      if (e.currentTarget.closest("[data-flip-moving]")) return;
      fn?.(id);
    };

  return (
    <>
      <tr data-flip={`session-${zone}-${sessionId}`}>
        <td colSpan={6} className="report-session-header">
          {/^s\d+$/.test(sessionId) ? t("autocode.sessionLabel", { id: sessionId.slice(1) }) : sessionId}
        </td>
      </tr>
      {items.map((p) => (
        <tr
          key={p.id}
          className={`report-row${removing.has(p.id) ? " report-row--deciding" : ""}`}
          data-testid={`bn-proposal-row-${p.id}`}
          data-flip={`row-${p.id}`}
        >
          {/* The timecode plays, as every blue timecode does (owner, 7 Nov 2026); the speaker
              opens the transcript at that moment, in a new tab or window so the review stays
              open. The player is keyed by session: a speaker code is not unique across them. */}
          <td className="report-timecode">
            <TimecodeLink
              seconds={p.start_timecode}
              participantId={p.session_id}
              sessionId={p.session_id}
              formatted={formatTimecode(p.start_timecode)}
            />
          </td>
          <td className="report-speaker">
            <a
              className="badge"
              href={reportHref(`/report/sessions/${p.session_id}#t-${Math.floor(p.start_timecode)}`)}
              target="_blank"
              rel="noreferrer"
              {...placeProps(windowPlace(p.session_id, p.start_timecode))}
              onClick={(e) => {
                // A new tab in a browser; a window of the study in the Mac app, which never
                // opens a report page in a browser-style popup.
                const place = windowPlace(p.session_id, p.start_timecode);
                if (!isEmbedded() || !place || e.button !== 0) return;
                e.preventDefault();
                postOpenInNewWindow(place, false);
              }}
              data-testid={`bn-proposal-speaker-${p.id}`}
            >
              {p.speaker_code}
            </a>
          </td>
          <td className="report-quote" title={p.quote_text}>
            {p.quote_text}
          </td>
          <td className="report-tag">
            <span
              // A tag Apply would leave tentative wears the tentative tag's dotted
              // outline, without its fade or its pulse (owner, 24 Nov 2026).
              className={[
                "badge",
                zone === "tentative" ? "threshold-tag-tentative" : "",
                featureFlags.proposalRationaleTooltip ? "has-tooltip" : "",
              ].filter(Boolean).join(" ")}
              style={{ backgroundColor: getTagBg(p.colour_set, p.colour_index) }}
            >
              {p.tag_name}
              {featureFlags.proposalRationaleTooltip && (
                <span className="tooltip">{p.rationale}</span>
              )}
            </span>
          </td>
          <td className="threshold-confidence">
            {confidenceText(p.confidence, i18n.language)}
            {/* A decision a person made (or one from before who decided was recorded): the
                lines never move it (landing plan D2, D39). */}
            {isPinned(p) && (
              <span className="threshold-pin" title={t("autocode.review.yourDecision")}
                data-testid={`bn-proposal-pin-${p.id}`}>
                <Icon name="pinned" label={t("autocode.review.yourDecision")} />
              </span>
            )}
          </td>
          <td className="threshold-actions">
            {/* Accepted zone: only deny (override) */}
            {zone === "accepted" && onDeny && (
              <button
                className="threshold-action-btn threshold-action-deny"
                aria-disabled={removing.has(p.id) || undefined}
                onClick={act(onDeny, p.id)}
                title={t("autocode.deny")}
              >
                <Icon name="close" decorative />
              </button>
            )}
            {/* Tentative zone: accept + deny */}
            {zone === "tentative" && (
              <>
                {onAccept && (
                  <button
                    className="threshold-action-btn threshold-action-accept"
                aria-disabled={removing.has(p.id) || undefined}
                    onClick={act(onAccept, p.id)}
                    title={t("autocode.accept")}
                  >
                    <Icon name="check" decorative />
                  </button>
                )}
                {onDeny && (
                  <button
                    className="threshold-action-btn threshold-action-deny"
                aria-disabled={removing.has(p.id) || undefined}
                    onClick={act(onDeny, p.id)}
                    title={t("autocode.deny")}
                  >
                    <Icon name="close" decorative />
                  </button>
                )}
              </>
            )}
            {/* Excluded zone: only accept (rescue) */}
            {zone === "excluded" && onAccept && (
              <button
                className="threshold-action-btn threshold-action-accept"
                aria-disabled={removing.has(p.id) || undefined}
                onClick={act(onAccept, p.id)}
                title={t("autocode.accept")}
              >
                <Icon name="check" decorative />
              </button>
            )}
          </td>
        </tr>
      ))}
    </>
  );
}
