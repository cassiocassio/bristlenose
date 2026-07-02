import { lazy, useEffect } from "react";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

// Lazy-loaded so the islands code-split into their own chunks (kept out of the
// main bundle). The AppLayout Outlet provides the Suspense boundary.
const Toolbar = lazy(() =>
  import("../islands/Toolbar").then((m) => ({ default: m.Toolbar })),
);
const QuoteSections = lazy(() =>
  import("../islands/QuoteSections").then((m) => ({ default: m.QuoteSections })),
);
const QuoteThemes = lazy(() =>
  import("../islands/QuoteThemes").then((m) => ({ default: m.QuoteThemes })),
);

export function QuotesTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  return (
    <>
      <Toolbar />
      <QuoteSections projectId={projectId} refreshKey={refreshKey} />
      <QuoteThemes projectId={projectId} refreshKey={refreshKey} />
    </>
  );
}
