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
import { getExportData, isExportMode } from "../utils/exportData";
import { useProjectId } from "../hooks/useProjectId";

interface ProjectInfo {
  project_name: string;
  session_count: number;
  participant_count: number;
  /**
   * Did the pipeline run that produced this report redact PII before
   * analysing? Stated in the header when true, silent when false — a
   * "not redacted" line on every report is noise, and faintly alarming to a
   * client who never asked the question.
   *
   * Distinct from the export "Anonymise" checkbox, which the researcher
   * chooses at export time and which strips participant display names.
   * Redaction is deliberately absent from the export surfaces so the two are
   * never read as one setting (13 Sep 2026 decision).
   *
   * Optional so an export embed or a server predating the field decodes
   * cleanly and the header simply says nothing.
   */
  pii_redacted?: boolean;
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

  const exportLogos = isExportMode() ? getExportData()?.logos : undefined;
  const lightSrc = exportLogos?.light ?? "/report/assets/bristlenose-logo.png";
  const darkSrc = exportLogos?.dark ?? "/report/assets/bristlenose-logo-dark.png";

  return (
    <>
      <div className="report-header">
        <div className="header-left">
          <a href={isExportMode() ? "#/report/" : "/report/"} className="report-logo-link">
            <picture>
              <source
                srcSet={darkSrc}
                media="(prefers-color-scheme: dark)"
              />
              <img
                className="report-logo"
                src={lightSrc}
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
              {info.pii_redacted && (
                <>
                  {", "}
                  {t("header.piiRedacted")}{" "}
                  <a
                    href="https://bristlenose.app/docs/redact-pii.html"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("header.piiRedactedAction")}
                  </a>
                </>
              )}
            </span>
          )}
        </div>
      </div>
      <hr />
    </>
  );
}
