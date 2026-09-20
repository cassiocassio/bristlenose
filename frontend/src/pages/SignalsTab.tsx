import { lazy } from "react";
import { useProjectId } from "../hooks/useProjectId";

// Lazy-loaded so the island code-splits into its own chunk (kept out of the
// main bundle). The AppLayout Outlet provides the Suspense boundary.
const SignalsPage = lazy(() =>
  import("../islands/SignalsPage").then((m) => ({ default: m.SignalsPage })),
);

export function SignalsTab() {
  const projectId = useProjectId();
  return <SignalsPage projectId={projectId} />;
}
