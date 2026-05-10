import { useEffect } from "react";
import { Dashboard } from "../islands/Dashboard";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

export function ProjectTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return <Dashboard projectId={projectId} refreshKey={refreshKey} />;
}
