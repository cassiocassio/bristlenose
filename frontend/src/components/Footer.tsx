/**
 * Footer — report footer with logo, version, bug report link, and help hint.
 *
 * Replicates bristlenose/theme/templates/footer.html.
 * Fetches version from `/api/health`.
 * Reuses existing CSS classes from atoms/footer.css.
 */

import { useEffect, useState } from "react";

interface FooterProps {
  onToggleHelp?: () => void;
}

export function Footer({ onToggleHelp }: FooterProps) {
  const [version, setVersion] = useState<string>("");

  useEffect(() => {
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.version) setVersion(data.version);
      })
      .catch(() => {});
  }, []);

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
      <div className="feedback-links">
        <a
          className="footer-link"
          href="https://github.com/cassiocassio/bristlenose/issues/new"
          target="_blank"
          rel="noopener noreferrer"
        >
          Report a bug
        </a>
        <span className="footer-link-sep">&middot;</span>
        {onToggleHelp && (
          <a
            className="footer-link feedback-trigger"
            role="button"
            tabIndex={0}
            onClick={onToggleHelp}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onToggleHelp();
            }}
          >
            Feedback
          </a>
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
