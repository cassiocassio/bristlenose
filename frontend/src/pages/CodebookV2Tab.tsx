/**
 * Codebook v2 — the replacement lens, alongside the shipped one.
 *
 * Parallel rather than in place, per `docs/design-codebook-v2.md` D29:
 * `CodebookPanel.tsx` is ~1,500 lines with ten referencing files, so rewriting
 * it in place breaks the lens for the whole of the build. Running both lets the
 * four Indicative items in the fidelity map be judged against the shipped
 * control on real data, which a mockup on fixture data cannot do.
 *
 * **The flag is the deletion instrument, not just the shipping vehicle.** The
 * sequence is: both live → v2 defaults on → the flag visibly off while v2
 * carries real work → delete v1. Nothing breaking at that third step is the
 * evidence v1 is dead weight, and it is exactly what static render never had —
 * no flag, so no day on which switching it off proved anything.
 *
 * Route registration follows the `specimen` precedent: always registered,
 * lazy-loaded, and only the *link* is gated. A route costs nothing until
 * visited; a conditional route is a second thing to get wrong.
 */

import { lazy, useEffect, useState } from "react";
import { useProjectId } from "../hooks/useProjectId";
import { startLastRunPolling, useLastRun } from "../contexts/LastRunStore";
import { apiGet } from "../utils/api";

const CodebookV2 = lazy(() =>
  import("../islands/CodebookV2").then((m) => ({ default: m.CodebookV2 })),
);

export function CodebookV2Tab() {
  const projectId = useProjectId();
  const { refreshKey } = useLastRun();
  const [projectName, setProjectName] = useState<string | undefined>(undefined);

  useEffect(() => {
    startLastRunPolling(projectId);
  }, [projectId]);

  useEffect(() => {
    apiGet<{ project_name: string }>("/info")
      .then((info) => setProjectName(info.project_name))
      .catch(() => setProjectName(undefined));
  }, [projectId]);

  return (
    <CodebookV2
      projectId={projectId}
      refreshKey={refreshKey}
      projectName={projectName}
    />
  );
}
