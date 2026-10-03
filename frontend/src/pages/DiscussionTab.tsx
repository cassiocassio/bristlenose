import { lazy } from "react";

// The Discussion lens (docs/design-discussion-lens-plan.md). Lazy-loaded so it
// code-splits into its own chunk, with its CSS, out of the main bundle. The
// AppLayout Outlet provides Suspense.
const DiscussionLens = lazy(() =>
  import("../islands/discussion/DiscussionLens").then((m) => ({ default: m.DiscussionLens })),
);

export function DiscussionTab() {
  return <DiscussionLens />;
}
