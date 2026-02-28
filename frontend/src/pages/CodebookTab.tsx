import { CodebookPanel } from "../islands/CodebookPanel";
import { useProjectId } from "../hooks/useProjectId";

export function CodebookTab() {
  const projectId = useProjectId();
  return <CodebookPanel projectId={projectId} />;
}
