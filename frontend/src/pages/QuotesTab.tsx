import { lazy, useCallback, useEffect, useLayoutEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { QuotesArrival, arrivalAnchor } from "./QuotesArrival";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";
import { useLenses } from "../contexts/ConditionStore";
import { UncategorisedFloor } from "../islands/UncategorisedFloor";
import { QuoteGroupingToggle, useQuoteGrouping, type QuoteGrouping } from "../islands/QuoteGroupingToggle";
import { clearQuoteGrouping, publishQuoteGrouping } from "../contexts/QuoteGroupingSlot";
import { useTocShowing } from "../contexts/TocShowing";

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
  // A link to a section or theme (the transcript's gutter, Signals, the Dashboard) shows Sections &
  // themes for that visit: the anchor it names exists in no other grouping. Held for the visit (a
  // location), never saved over the remembered grouping, and given up as soon as the researcher
  // picks one (docs/design-transcript-gutter.md, "Arrival").
  const location = useLocation();
  const [arrivedFor, setArrivedFor] = useState<string | null>(null);
  if (arrivalAnchor(location.hash) && arrivedFor !== location.key) {
    setArrivedFor(location.key);
    setPicked(false);
  }
  const wantsSections = arrivedFor === location.key && !picked;
  const shown = !joined
    ? "session"
    : picked
      ? grouping
      : wantsSections
        ? "sections"
        : readDuringRun
          ? "session"
          : grouping;
  const choose = useCallback(
    (g: QuoteGrouping) => {
      setPicked(true);
      setGrouping(g);
    },
    [setGrouping],
  );

  // The content sidebar's header and list follow this decision; they never
  // make their own. Published before paint so the sidebar does not show one
  // grouping for a frame while the column shows the other.
  useLayoutEffect(() => {
    publishQuoteGrouping({ shown, controlVisible: joined, choose });
  }, [shown, joined, choose]);
  useEffect(() => clearQuoteGrouping, []);

  // One control, one place: at the top of the content sidebar while it is
  // showing (SidebarLayout renders it there), in the heading when it is not.
  const tocShowing = useTocShowing();
  const control = joined && !tocShowing ? (
    <QuoteGroupingToggle grouping={shown} onChange={choose} />
  ) : null;

  if (shown === "session") {
    return (
      <>
        <QuotesArrival />
        <Toolbar />
        <QuoteSessions projectId={projectId} refreshKey={refreshKey} headingAction={control} />
      </>
    );
  }
  return (
    <>
      <QuotesArrival />
      <Toolbar />
      <QuoteSections projectId={projectId} refreshKey={refreshKey} headingAction={control} />
      <QuoteThemes projectId={projectId} refreshKey={refreshKey} />
      <UncategorisedFloor />
    </>
  );
}
