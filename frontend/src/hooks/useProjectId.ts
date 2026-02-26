/**
 * useProjectId — reads the project ID from the app root DOM element.
 *
 * Falls back to "1" (single-project mode).
 */

import { useMemo } from "react";

export function useProjectId(): string {
  return useMemo(() => {
    const root = document.getElementById("bn-app-root");
    return root?.getAttribute("data-project-id") ?? "1";
  }, []);
}
