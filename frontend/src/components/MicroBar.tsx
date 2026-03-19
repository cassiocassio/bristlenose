/**
 * MicroBar — proportional horizontal bar for counts and distributions.
 *
 * Three rendering modes:
 *
 * 1. **Bare bar** (default) — single-colour bar, no background track.
 *    Used in codebook panel and tag sidebar for tag counts.
 *
 * 2. **Two-tone bar** (`tentativeValue` provided) — stacked bar showing
 *    tentative (pending autocode proposals) + accepted (committed) counts.
 *    Tentative segment is pale (30% opacity), accepted is solid. Order:
 *    [pale tentative | solid accepted] — solid hugs the right edge (near
 *    the count number), pale extends leftward. Total width is proportional
 *    to (tentativeValue + value). Both values are fractions 0–1 of the
 *    group maximum.
 *
 * 3. **Track bar** (`track={true}`) — fill inside a visible background
 *    track. Used in analysis signal cards.
 *
 * @module MicroBar
 */

interface MicroBarProps {
  /** Fraction 0–1 representing accepted/committed count (clamped). */
  value: number;
  /** Fraction 0–1 representing tentative/pending count (clamped).
   *  When provided, renders two-tone stacked bar. */
  tentativeValue?: number;
  /** CSS colour or variable for the fill. */
  colour?: string;
  /** Show a background track (analysis style) or bare bar (codebook style). */
  track?: boolean;
  /** Tooltip text shown on hover. */
  title?: string;
  className?: string;
  "data-testid"?: string;
}

export function MicroBar({
  value,
  tentativeValue,
  colour,
  track = false,
  title,
  className,
  "data-testid": testId,
}: MicroBarProps) {
  const clamp = (v: number) => Math.max(0, Math.min(1, v));
  const accepted = clamp(value);
  const tentative = tentativeValue != null ? clamp(tentativeValue) : 0;

  // ── Two-tone stacked bar ──────────────────────────────────────────
  if (tentativeValue != null) {
    const total = Math.min(1, accepted + tentative);
    if (total === 0) return null;

    const totalPct = Math.round(total * 100);
    const acceptedShare = total > 0 ? Math.round((accepted / total) * 100) : 0;
    const tentativeShare = 100 - acceptedShare;

    const colourStyle = colour ? { backgroundColor: colour } : {};
    const classes = ["tag-micro-bar-stack", className].filter(Boolean).join(" ");

    return (
      <span
        className={classes}
        style={{ width: `${totalPct}%` }}
        title={title}
        role="img"
        aria-label={title}
        data-testid={testId}
      >
        {tentativeShare > 0 && (
          <span
            className="tag-micro-bar-tentative"
            style={{ width: `${tentativeShare}%`, ...colourStyle }}
            aria-hidden="true"
            data-testid={testId ? `${testId}-tentative` : undefined}
          />
        )}
        {acceptedShare > 0 && (
          <span
            className="tag-micro-bar-accepted"
            style={{ width: `${acceptedShare}%`, ...colourStyle }}
            aria-hidden="true"
            data-testid={testId ? `${testId}-accepted` : undefined}
          />
        )}
      </span>
    );
  }

  // ── Track bar (analysis) ──────────────────────────────────────────
  const pct = `${Math.round(accepted * 100)}%`;
  const fillStyle: React.CSSProperties = {
    width: pct,
    ...(colour ? { backgroundColor: colour } : {}),
  };

  if (track) {
    const classes = ["conc-bar-track", className].filter(Boolean).join(" ");
    return (
      <span className={classes} title={title} role="img" aria-label={title} data-testid={testId}>
        <span className="conc-bar-fill" style={fillStyle} aria-hidden="true" />
      </span>
    );
  }

  // ── Bare bar (single colour) ──────────────────────────────────────
  const classes = ["tag-micro-bar", className].filter(Boolean).join(" ");
  return (
    <span
      className={classes}
      style={fillStyle}
      title={title}
      role="img"
      aria-label={title}
      data-testid={testId}
    />
  );
}
