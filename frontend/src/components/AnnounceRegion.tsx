/**
 * AnnounceRegion — visually-hidden aria-live region for screen-reader
 * announcements.  Mount once in AppLayout.
 */

import { useCallback } from "react";
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

  return <div ref={ref} role="status" aria-live="polite" aria-atomic="true" style={STYLE} />;
}
