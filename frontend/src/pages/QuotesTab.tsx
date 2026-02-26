import { Toolbar } from "../islands/Toolbar";
import { QuoteSections } from "../islands/QuoteSections";
import { QuoteThemes } from "../islands/QuoteThemes";
import { useProjectId } from "../hooks/useProjectId";

export function QuotesTab() {
  const projectId = useProjectId();
  return (
    <>
      <Toolbar />
      <QuoteSections projectId={projectId} />
      <QuoteThemes projectId={projectId} />
    </>
  );
}
