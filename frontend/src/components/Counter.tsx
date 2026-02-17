/**
 * Counter — hidden-quotes badge with expandable dropdown.
 *
 * Shows a count of hidden quotes per group with a toggle to reveal
 * truncated previews. Each preview can unhide a single quote; an
 * "Unhide all" link restores the entire group.
 *
 * Uses existing `molecules/hidden-quotes.css` classes — zero new CSS.
 */

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
            <span>Unhide:</span>
            {count > 1 && (
              <a
                href="#"
                className="bn-unhide-all"
                onClick={(e) => {
                  e.preventDefault();
                  onUnhideAll();
                }}
                data-testid={testId ? `${testId}-unhide-all` : undefined}
              >
                Unhide all
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
                  <a
                    className="timecode"
                    href="#"
                    data-participant={item.participantId}
                    data-seconds={item.seconds}
                    {...(item.endSeconds !== undefined && {
                      "data-end-seconds": item.endSeconds,
                    })}
                    title="Play video"
                  >
                    [{item.timecode}]
                  </a>
                ) : (
                  <span className="timecode">[{item.timecode}]</span>
                )}
                <span
                  className="bn-hidden-preview"
                  title="Unhide"
                  data-quote-id={item.domId}
                  onClick={(e) => {
                    e.preventDefault();
                    onUnhide(item.domId);
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
