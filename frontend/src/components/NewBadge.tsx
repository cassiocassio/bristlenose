/**
 * NewBadge — a body-sized highlighter "New" marker shown inline after a
 * section/theme title when the group is predominantly new material
 * (Phase 3, 3c "New" flag).
 *
 * Click to dismiss: it evaporates, no undo — it has served its purpose once
 * noticed.  Dismissal is persisted in localStorage keyed by the durable
 * heading id AND the server's `newSince` token, so a genuinely-fresh import
 * (new token) re-shows a previously-dismissed badge.
 */

import { useCallback, useState } from "react";

const STORAGE_PREFIX = "bn-new-dismissed:";

function readDismissed(dismissKey: string, newSince: string | null | undefined): boolean {
  if (!newSince) return false;
  try {
    return localStorage.getItem(STORAGE_PREFIX + dismissKey) === newSince;
  } catch {
    return false;
  }
}

interface NewBadgeProps {
  /** Server M3 gate — is this heading predominantly new material? */
  isNew: boolean;
  /** Durable heading id (section-cluster-{id} / theme-group-{id}) — the
   *  dismissal key, stable across label drift. */
  dismissKey: string;
  /** Token of the latest new-material import; scopes dismissal so fresh
   *  material re-shows the badge. */
  newSince: string | null | undefined;
}

export function NewBadge({ isNew, dismissKey, newSince }: NewBadgeProps) {
  const [dismissed, setDismissed] = useState(() => readDismissed(dismissKey, newSince));

  const handleDismiss = useCallback(() => {
    try {
      if (newSince) localStorage.setItem(STORAGE_PREFIX + dismissKey, newSince);
    } catch {
      // localStorage unavailable — dismiss for this view only.
    }
    setDismissed(true);
  }, [dismissKey, newSince]);

  // Require a token: a badge with no `newSince` can't be dismissed meaningfully.
  if (!isNew || !newSince || dismissed) return null;

  return (
    <button
      type="button"
      className="bn-new-badge"
      title="Click to dismiss"
      aria-label="New — click to dismiss"
      onClick={handleDismiss}
      data-testid={`bn-new-${dismissKey}`}
    >
      New
    </button>
  );
}
