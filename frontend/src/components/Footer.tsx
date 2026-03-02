/**
 * Footer — report footer with logo, version, bug report link, feedback link,
 * and help hint.
 *
 * Replicates bristlenose/theme/templates/footer.html.
 * Reuses existing CSS classes from atoms/footer.css.
 */

import type { HealthResponse } from "../utils/health";
import {
  DEFAULT_GITHUB_ISSUES_URL,
} from "../utils/health";

interface FooterProps {
  health?: HealthResponse | null;
  onOpenFeedback?: () => void;
  onToggleHelp?: () => void;
}

export function Footer({ health, onOpenFeedback, onToggleHelp }: FooterProps) {
  const version = health?.version ?? "";
  const githubIssuesUrl =
    health?.links.github_issues_url ?? DEFAULT_GITHUB_ISSUES_URL;
  const feedbackEnabled = health?.feedback.enabled ?? true;

  return (
    <footer className="report-footer">
      <div className="footer-left">
        <picture className="footer-logo-picture">
          <source
            srcSet="/report/assets/bristlenose-logo-dark.png"
            media="(prefers-color-scheme: dark)"
          />
          <img
            className="footer-logo"
            src="/report/assets/bristlenose-logo.png"
            alt=""
          />
        </picture>
        <span className="footer-logotype">Bristlenose</span>{" "}
        <a
          className="footer-version"
          href="https://github.com/cassiocassio/bristlenose"
        >
          {version ? `version ${version}` : ""}
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
          Report a bug
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
              Feedback
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
          <kbd>?</kbd> for Help
        </a>
      )}
    </footer>
  );
}
