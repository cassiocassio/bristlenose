import { useEffect } from "react";
import { CodebookPanel } from "../islands/CodebookPanel";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

export function CodebookTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return <CodebookPanel projectId={projectId} refreshKey={refreshKey} />;
}
