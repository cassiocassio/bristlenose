import { lazy, useEffect } from "react";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

// Like the other lenses, load the grid when its route opens. Keeping this
// eager also made its shared session-row code part of every first download.
const SessionsTable = lazy(() =>
  import("../islands/SessionsTable").then((m) => ({ default: m.SessionsTable })),
);

export function SessionsTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return <SessionsTable projectId={projectId} refreshKey={refreshKey} />;
}
