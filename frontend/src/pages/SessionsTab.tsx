import { SessionsTable } from "../islands/SessionsTable";
import { useProjectId } from "../hooks/useProjectId";

export function SessionsTab() {
  const projectId = useProjectId();
  return <SessionsTable projectId={projectId} />;
}
