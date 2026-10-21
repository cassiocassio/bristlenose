/**
 * AnnounceRegion — visually-hidden aria-live region for screen-reader
 * announcements.  Mount once in AppLayout.
 *
 * Portalled to `document.body`, outside `#bn-app-root`: `useInert` makes that
 * root inert while a modal is open, and an inert live region is silent, so a
 * toast or announcement made with a dialog up was never heard.
 */

import { useCallback } from "react";
import { createPortal } from "react-dom";
import { setAnnounceElement } from "../utils/announce";

const STYLE: React.CSSProperties = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  whiteSpace: "nowrap",
  border: 0,
};

export function AnnounceRegion() {
  const ref = useCallback((node: HTMLDivElement | null) => {
    setAnnounceElement(node);
  }, []);

  return createPortal(
    <div ref={ref} role="status" aria-live="polite" aria-atomic="true" style={STYLE} />,
    document.body,
  );
}
