import { lazy } from "react";

// Dev-gated lens (docs/design-discussion-lens-plan.md, Phase 4 behind IS_DEV).
// Lazy-loaded so it code-splits into its own chunk, with its CSS and synthetic
// fixture, out of the main bundle. The AppLayout Outlet provides Suspense.
const DiscussionLens = lazy(() =>
  import("../islands/discussion/DiscussionLens").then((m) => ({ default: m.DiscussionLens })),
);

export function DiscussionTab() {
  return <DiscussionLens />;
}
