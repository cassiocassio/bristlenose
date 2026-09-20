/**
 * The codebook lens. Mounted at `/report/codebook` (`router.tsx`) — the only
 * codebook lens there is.
 *
 * The "v2" in the name is historical: this shipped as a parallel replacement and
 * became *the* lens in 0.29.0, when v1 was deleted ("codebook v2 becomes the
 * codebook lens: v1 deleted, the icon back, and the i18n graduated"). The
 * feature flag and the `/report/codebook-v2` route are both gone with it. The
 * file keeps its name rather than churning ten importers for cosmetics.
 *
 * ── How it got here, and why the approach was right ────────────────────────
 *
 * Parallel rather than in place, per `docs/design-codebook-v2.md` D29:
 * `CodebookPanel.tsx` was ~1,500 lines with ten referencing files, so rewriting
 * it in place would have broken the lens for the whole of the build. Running
 * both let the four Indicative items in the fidelity map be judged against the
 * shipped control on real data, which a mockup on fixture data cannot do.
 *
 * **The flag was the deletion instrument, not just the shipping vehicle.** The
 * sequence ran: both live → v2 defaults on → the flag visibly off while v2
 * carried real work → delete v1. Nothing breaking at that third step was the
 * evidence v1 was dead weight, and it is exactly what static render never had —
 * no flag, so no day on which switching it off proved anything. That sequence
 * completed; the flag was removed once it had done its job.
 *
 * Route registration followed the `specimen` precedent: always registered,
 * lazy-loaded, and only the *link* gated. A route costs nothing until visited;
 * a conditional route is a second thing to get wrong.
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
