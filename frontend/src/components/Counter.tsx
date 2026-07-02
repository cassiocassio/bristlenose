/**
 * Counter — hidden-quotes badge with expandable dropdown.
 *
 * Shows a count of hidden quotes per group with a toggle to reveal
 * truncated previews. Each preview can unhide a single quote; an
 * "Unhide all" link restores the entire group.
 *
 * Uses existing `molecules/hidden-quotes.css` classes — zero new CSS.
 */

import { useTranslation } from "react-i18next";

export interface CounterItem {
  domId: string;
  timecode: string;
  seconds: number;
  endSeconds?: number;
  participantId: string;
  previewText: string;
  hasMedia: boolean;
}

interface CounterProps {
  count: number;
  items: CounterItem[];
  isOpen: boolean;
  onToggle: () => void;
  onUnhide: (domId: string) => void;
  onUnhideAll: () => void;
  "data-testid"?: string;
}

/** Truncate quote text to a maximum length with smart quotes. */
function truncateQuote(text: string, max: number): string {
  if (!text) return "";
  // Strip smart quotes for the preview.
  const stripped = text.replace(/^[\u201c\u201d"]+|[\u201c\u201d"]+$/g, "").trim();
  if (stripped.length <= max) return `\u201c${stripped}\u201d`;
  return `\u201c${stripped.substring(0, max).trim()}\u2026\u201d`;
}

export function Counter({
  count,
  items,
  isOpen,
  onToggle,
  onUnhide,
  onUnhideAll,
  "data-testid": testId,
}: CounterProps) {
  const { t } = useTranslation();
  if (count === 0) return null;

  const label = `${count} hidden quote${count !== 1 ? "s" : ""}`;

  return (
    <div className="bn-hidden-badge" data-testid={testId}>
      <button
        className="bn-hidden-toggle"
        aria-expanded={isOpen}
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        data-testid={testId ? `${testId}-toggle` : undefined}
      >
        {label} <span className="bn-hidden-chevron">&#x25BE;</span>
      </button>
      {isOpen && (
        <div className="bn-hidden-dropdown" data-testid={testId ? `${testId}-dropdown` : undefined}>
          <div className="bn-hidden-header">
            <span>{t("quotes.unhideHeader")}</span>
            {count > 1 && (
              // Link-styled action; keyboard-accessible via role/tabIndex/onKeyDown.
              // eslint-disable-next-line jsx-a11y/anchor-is-valid
              <a
                href="#"
                className="bn-unhide-all"
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.preventDefault();
                  onUnhideAll();
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onUnhideAll();
                  }
                }}
                data-testid={testId ? `${testId}-unhide-all` : undefined}
              >
                {t("quotes.unhideAll")}
              </a>
            )}
          </div>
          <div className="bn-hidden-list">
            {items.map((item) => (
              <div
                className="bn-hidden-item"
                key={item.domId}
                data-quote-id={item.domId}
              >
                {item.hasMedia ? (
                  // Link-styled seek action; activated via delegated click, keyboard-accessible via role/tabIndex/onKeyDown.
                  // eslint-disable-next-line jsx-a11y/anchor-is-valid
                  <a
                    className="timecode"
                    href="#"
                    role="button"
                    tabIndex={0}
                    data-participant={item.participantId}
                    data-seconds={item.seconds}
                    {...(item.endSeconds !== undefined && {
                      "data-end-seconds": item.endSeconds,
                    })}
                    title={t("quotes.playVideo")}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        e.currentTarget.click();
                      }
                    }}
                  >
                    [{item.timecode}]
                  </a>
                ) : (
                  <span className="timecode">[{item.timecode}]</span>
                )}
                <span
                  className="bn-hidden-preview"
                  role="button"
                  tabIndex={0}
                  aria-label={`${t("quotes.unhide")}: ${truncateQuote(item.previewText, 50)}`}
                  title={t("quotes.unhide")}
                  data-quote-id={item.domId}
                  onClick={(e) => {
                    e.preventDefault();
                    onUnhide(item.domId);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onUnhide(item.domId);
                    }
                  }}
                  data-testid={testId ? `${testId}-preview-${item.domId}` : undefined}
                >
                  {truncateQuote(item.previewText, 50)}
                </span>
                <span className="speaker-link">{item.participantId}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
