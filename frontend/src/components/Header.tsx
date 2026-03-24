/**
 * Header — report header with logo, project name, and metadata.
 *
 * Replicates bristlenose/theme/templates/report_header.html.
 * Fetches project info from `/api/projects/{id}/info`.
 * Reuses existing CSS classes from atoms/logo.css.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { apiGet } from "../utils/api";
import { useProjectId } from "../hooks/useProjectId";

interface ProjectInfo {
  project_name: string;
  session_count: number;
  participant_count: number;
}

export function Header() {
  const { t } = useTranslation();
  const projectId = useProjectId();
  const [info, setInfo] = useState<ProjectInfo | null>(null);

  useEffect(() => {
    apiGet<ProjectInfo>(`/info`)
      .then(setInfo)
      .catch(() => {});
  }, [projectId]);

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
                alt={t("header.logoAlt")}
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
          <span className="header-doc-title">{t("header.researchReport")}</span>
          {info && (
            <span className="header-meta">
              {t("header.session", { count: info.session_count })},{" "}
              {t("header.participant", { count: info.participant_count })}
            </span>
          )}
        </div>
      </div>
      <hr />
    </>
  );
}
