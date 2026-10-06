/**
 * The session tapestry's dev-only playground toggle. English by design: it
 * renders only in a dev build (SessionsTable gates it on IS_DEV), so it lives
 * in its own file where the aria-label gate's _DEV_ONLY set can name it.
 */
export function TapestryPlaygroundToggle({ onToggle }: { onToggle: () => void }) {
  return (
    <button type="button" className="bn-tp-zoom-btn" aria-label="Tapestry playground (dev)"
      title="Tapestry playground (dev)" onClick={onToggle}>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4h10M3 8h10M3 12h10" /><circle cx="6" cy="4" r="1.5" /><circle cx="10" cy="8" r="1.5" /><circle cx="5" cy="12" r="1.5" /></svg>
    </button>
  );
}
