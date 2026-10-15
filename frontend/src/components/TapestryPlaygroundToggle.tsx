/**
 * The session tapestry's dev-only playground toggle. English by design: it
 * renders only in a dev build (SessionsTable gates it on IS_DEV), so it lives
 * in its own file where the aria-label gate's _DEV_ONLY set can name it.
 */

import { Icon } from "./Icon";
export function TapestryPlaygroundToggle({ onToggle }: { onToggle: () => void }) {
  return (
    <button type="button" className="bn-tp-zoom-btn" aria-label="Tapestry playground (dev)"
      title="Tapestry playground (dev)" onClick={onToggle}>
      <Icon name="playground" decorative />
    </button>
  );
}
