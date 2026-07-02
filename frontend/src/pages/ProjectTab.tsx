import { lazy, useEffect } from "react";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

// Lazy-loaded so the island code-splits into its own chunk (kept out of the
// main bundle). The AppLayout Outlet provides the Suspense boundary.
const Dashboard = lazy(() =>
  import("../islands/Dashboard").then((m) => ({ default: m.Dashboard })),
);

export function ProjectTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return <Dashboard projectId={projectId} refreshKey={refreshKey} />;
}
