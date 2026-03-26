/**
 * Footer — report footer with logo, version, bug report link, feedback link,
 * and help hint.
 *
 * Replicates bristlenose/theme/templates/footer.html.
 * Reuses existing CSS classes from atoms/footer.css.
 */

import { useTranslation } from "react-i18next";
import { getExportData, isExportMode } from "../utils/exportData";
import {
  DEFAULT_GITHUB_ISSUES_URL,
  type HealthResponse,
} from "../utils/health";

interface FooterProps {
  health?: HealthResponse | null;
  onOpenFeedback?: () => void;
  onToggleHelp?: () => void;
}

export function Footer({ health, onOpenFeedback, onToggleHelp }: FooterProps) {
  const { t } = useTranslation();
  const version = health?.version ?? "";
  const githubIssuesUrl =
    health?.links.github_issues_url ?? DEFAULT_GITHUB_ISSUES_URL;
  const feedbackEnabled = health?.feedback.enabled ?? true;
  const exportLogos = isExportMode() ? getExportData()?.logos : undefined;
  const lightSrc = exportLogos?.light ?? "/report/assets/bristlenose-logo.png";
  const darkSrc = exportLogos?.dark ?? "/report/assets/bristlenose-logo-dark.png";

  return (
    <footer className="report-footer">
      <div className="footer-left">
        <picture className="footer-logo-picture">
          <source
            srcSet={darkSrc}
            media="(prefers-color-scheme: dark)"
          />
          <img
            className="footer-logo"
            src={lightSrc}
            alt=""
          />
        </picture>
        <span className="footer-logotype">Bristlenose</span>{" "}
        <a
          className="footer-version"
          href="https://github.com/cassiocassio/bristlenose"
        >
          {version ? t("footer.version", { version }) : ""}
        </a>
      </div>
      <div
        className={`feedback-links${feedbackEnabled ? " feedback-links-visible" : ""}`}
      >
        <a
          className="footer-link"
          href={githubIssuesUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("footer.reportBug")}
        </a>
        {feedbackEnabled && onOpenFeedback && (
          <>
            <span className="footer-link-sep">&middot;</span>
            <a
              className="footer-link feedback-trigger"
              role="button"
              tabIndex={0}
              onClick={onOpenFeedback}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onOpenFeedback();
              }}
            >
              {t("footer.feedback")}
            </a>
          </>
        )}
      </div>
      {onToggleHelp && (
        <a
          className="footer-keyboard-hint"
          role="button"
          tabIndex={0}
          onClick={onToggleHelp}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") onToggleHelp();
          }}
        >
          <kbd>?</kbd> {t("footer.helpHint")}
        </a>
      )}
    </footer>
  );
}
