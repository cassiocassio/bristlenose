import { AnalysisPage } from "../islands/AnalysisPage";
import { useProjectId } from "../hooks/useProjectId";

export function AnalysisTab() {
  const projectId = useProjectId();
  return <AnalysisPage projectId={projectId} />;
}
