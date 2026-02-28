/**
 * Header — report header with logo, project name, and metadata.
 *
 * Replicates bristlenose/theme/templates/report_header.html.
 * Fetches project info from `/api/projects/{id}/info`.
 * Reuses existing CSS classes from atoms/logo.css.
 */

import { useEffect, useState } from "react";
import { apiGet } from "../utils/api";
import { useProjectId } from "../hooks/useProjectId";

interface ProjectInfo {
  project_name: string;
  session_count: number;
  participant_count: number;
}

export function Header() {
  const projectId = useProjectId();
  const [info, setInfo] = useState<ProjectInfo | null>(null);

  useEffect(() => {
    apiGet<ProjectInfo>(`/info`)
      .then(setInfo)
      .catch(() => {});
  }, [projectId]);

  const sessionLabel = info
    ? `${info.session_count}\u00a0session${info.session_count !== 1 ? "s" : ""}`
    : "";
  const participantLabel = info
    ? `${info.participant_count}\u00a0participant${info.participant_count !== 1 ? "s" : ""}`
    : "";

  return (
    <>
      <div className="report-header">
        <div className="header-left">
          <a href="/report/" className="report-logo-link">
            <picture>
              <source
                srcSet="/report/assets/bristlenose-logo-dark.png"
                media="(prefers-color-scheme: dark)"
              />
              <img
                className="report-logo"
                src="/report/assets/bristlenose-logo.png"
                alt="Bristlenose logo"
              />
            </picture>
          </a>
          <span className="header-title">
            <span className="header-logotype">Bristlenose</span>{" "}
            <span className="header-project">
              {info ? info.project_name : ""}
            </span>
          </span>
        </div>
        <div className="header-right">
          <span className="header-doc-title">Research Report</span>
          {info && (
            <span className="header-meta">
              {sessionLabel}, {participantLabel}
            </span>
          )}
        </div>
      </div>
      <hr />
    </>
  );
}
