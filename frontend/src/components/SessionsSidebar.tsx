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

import { useEffect, useRef, useState } from "react";
import { useMatch, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiGet } from "../utils/api";
import { reportHref } from "../utils/reportHref";
import { useProjectId } from "../hooks/useProjectId";
import type { SessionsListResponse } from "../utils/types";
import { SessionEntryRow, useSessionRowLayout } from "./SessionEntry";

// ── Component ─────────────────────────────────────────────────────

export function SessionsSidebar() {
  const { t } = useTranslation();
  const projectId = useProjectId();
  const navigate = useNavigate();
  const transcriptMatch = useMatch("/report/sessions/:sessionId");
  const activeSessionId = transcriptMatch?.params.sessionId ?? null;
  const activeRef = useRef<HTMLAnchorElement | null>(null);

  const [data, setData] = useState<SessionsListResponse | null>(null);
  const { navRef, layout } = useSessionRowLayout(data?.sessions ?? null);

  useEffect(() => {
    apiGet<SessionsListResponse>("/sessions")
      .then(setData)
      .catch(() => {});
  }, [projectId]);

  // Auto-scroll active session into view.
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [activeSessionId]);

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
    <nav aria-label={t("nav.sessions")} ref={navRef}>
      {data.sessions.map((session) => (
        <SessionEntryRow
          key={session.session_id}
          session={session}
          layout={layout}
          href={reportHref(`/report/sessions/${session.session_id}`)}
          active={session.session_id === activeSessionId}
          rowRef={activeRef}
          onClick={handleClick}
        />
      ))}
    </nav>
  );
}
