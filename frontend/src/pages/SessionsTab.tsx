import { useEffect } from "react";
import { SessionsTable } from "../islands/SessionsTable";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

export function SessionsTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return <SessionsTable projectId={projectId} refreshKey={refreshKey} />;
}
