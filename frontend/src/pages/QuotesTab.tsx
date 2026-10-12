import { lazy, useEffect, useState } from "react";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";
import { useLenses } from "../contexts/ConditionStore";
import { UncategorisedFloor } from "../islands/UncategorisedFloor";
import { QuoteGroupingToggle, useQuoteGrouping } from "../islands/QuoteGroupingToggle";

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
const QuoteSessions = lazy(() =>
  import("../islands/QuoteSessions").then((m) => ({ default: m.QuoteSessions })),
);

export function QuotesTab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();
  const lenses = useLenses();
  const [grouping, setGrouping] = useQuoteGrouping(projectId);

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  // During a first analysis the quotes arrive session by session and no
  // section or theme exists yet (the Signals lens waits for the same barrier),
  // so By session is the only grouping and there is nothing to choose
  // (docs/design-progressive-lenses.md, Phase 2). After it, the choice stays.
  const joined = lenses.signals;
  // §2: themes arriving never move the researcher. Someone reading By session
  // during the run is still reading By session when sections arrive, until
  // they pick. That is this visit's state, not a remembered choice: only a
  // click on the control is saved.
  const [readDuringRun, setReadDuringRun] = useState(!joined);
  const [picked, setPicked] = useState(false);
  if (!joined && !readDuringRun) setReadDuringRun(true);
  const shown = !joined || (readDuringRun && !picked) ? "session" : grouping;
  const choose = (g: typeof grouping) => {
    setPicked(true);
    setGrouping(g);
  };
  const control = joined ? (
    <QuoteGroupingToggle grouping={shown} onChange={choose} />
  ) : null;

  if (shown === "session") {
    return (
      <>
        <Toolbar />
        <QuoteSessions projectId={projectId} refreshKey={refreshKey} headingAction={control} />
      </>
    );
  }
  return (
    <>
      <Toolbar />
      <QuoteSections projectId={projectId} refreshKey={refreshKey} headingAction={control} />
      <QuoteThemes projectId={projectId} refreshKey={refreshKey} />
      <UncategorisedFloor />
    </>
  );
}
