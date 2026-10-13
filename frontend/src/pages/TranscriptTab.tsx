import { lazy, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling } from "../contexts/LastRunStore";

// Lazy-loaded so the island code-splits into its own chunk (kept out of the
// main bundle). The AppLayout Outlet provides the Suspense boundary.
const TranscriptPage = lazy(() =>
  import("../islands/TranscriptPage").then((m) => ({ default: m.TranscriptPage })),
);

export function TranscriptTab() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const projectId = useProjectId();
  // The transcript re-reads when a run lands (TranscriptPage, the refresh key).
  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);
  return <TranscriptPage projectId={projectId} sessionId={sessionId ?? ""} />;
}
