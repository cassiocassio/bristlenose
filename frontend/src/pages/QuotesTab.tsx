import { useEffect } from "react";
import { Toolbar } from "../islands/Toolbar";
import { QuoteSections } from "../islands/QuoteSections";
import { QuoteThemes } from "../islands/QuoteThemes";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";

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
