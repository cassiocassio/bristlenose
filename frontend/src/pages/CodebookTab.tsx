import { useEffect, useState } from "react";
import { CodebookPanel } from "../islands/CodebookPanel";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";
import { apiGet } from "../utils/api";

export function CodebookTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();
  const [projectName, setProjectName] = useState<string | undefined>(undefined);

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  // Project name for the codebook's "<project> tags" section header. Fetched
  // here (the page) rather than inside CodebookPanel so the panel stays free
  // of an extra side-fetch. Falls back to "Your tags" in the panel if absent.
  useEffect(() => {
    apiGet<{ project_name: string }>("/info")
      .then((info) => setProjectName(info.project_name))
      .catch(() => setProjectName(undefined));
  }, [projectId]);

  return (
    <CodebookPanel projectId={projectId} refreshKey={refreshKey} projectName={projectName} />
  );
}
