import { lazy, useEffect, useState } from "react";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

// Like the other lenses, load the grid when its route opens. Keeping this
// eager also made its shared session-row code part of every first download.
type Table = typeof import("../islands/SessionsTable").SessionsTable;
let loadedTable: Table | undefined;
function loadTable() {
  return import("../islands/SessionsTable").then((m) => {
    loadedTable = m.SessionsTable;
    return { default: m.SessionsTable };
  });
}
const LazySessionsTable = lazy(loadTable);

// A lazy component that has to suspend commits the (empty) fallback, and React then holds
// the content back until 300 ms after that commit (FALLBACK_THROTTLE_MS), so a chunk that
// arrives in 10 ms still cost 280 ms on the first visit, with the main thread idle
// (measured 4 Nov 2026; a patched react-dom with the throttle at 0 started the read at
// 46 ms instead of 309). A plain import() does not help, because a fresh lazy() always
// suspends on its first render. So load the chunk when the browser is idle and render the
// loaded component itself, which suspends for nothing. The same timer fallback as
// PreloadSessionsSidebar, for browsers without requestIdleCallback.
export function preloadSessionsTable(): Promise<unknown> {
  return loadTable().catch(() => {});
}
if (typeof window !== "undefined" && import.meta.env.MODE !== "test") {
  const preload = () => { void preloadSessionsTable(); };
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(preload, { timeout: 2000 });
  } else {
    setTimeout(preload, 1500);
  }
}

export function SessionsTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();
  // Chosen once per mount: swapping the component type mid-life would remount the grid.
  const [SessionsTable] = useState<Table | typeof LazySessionsTable>(() => loadedTable ?? LazySessionsTable);

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return <SessionsTable projectId={projectId} refreshKey={refreshKey} />;
}
