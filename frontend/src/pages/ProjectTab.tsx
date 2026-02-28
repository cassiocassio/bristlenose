import { Dashboard } from "../islands/Dashboard";
import { useProjectId } from "../hooks/useProjectId";

export function ProjectTab() {
  const projectId = useProjectId();
  return <Dashboard projectId={projectId} />;
}
