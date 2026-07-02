import { lazy } from "react";
import { useProjectId } from "../hooks/useProjectId";

// Lazy-loaded so the island code-splits into its own chunk (kept out of the
// main bundle). The AppLayout Outlet provides the Suspense boundary.
const AnalysisPage = lazy(() =>
  import("../islands/AnalysisPage").then((m) => ({ default: m.AnalysisPage })),
);

export function AnalysisTab() {
  const projectId = useProjectId();
  return <AnalysisPage projectId={projectId} />;
}
