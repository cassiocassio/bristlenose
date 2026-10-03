import { lazy } from "react";
import { Navigate } from "react-router-dom";
import { isEmbedded } from "../utils/embedded";

// Dev-gated lens (docs/design-discussion-lens-plan.md, Phase 4 behind IS_DEV).
// Lazy-loaded so it code-splits into its own chunk, with its CSS and synthetic
// fixture, out of the main bundle. The AppLayout Outlet provides Suspense.
const DiscussionLens = lazy(() =>
  import("../islands/discussion/DiscussionLens").then((m) => ({ default: m.DiscussionLens })),
);

/** Same signal as NavBar/AppLayout: `serve --dev` sets the global, Vite serves on 5173. */
const IS_DEV =
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_DEV__ === true ||
  location.port === "5173";

export function DiscussionTab() {
  // Outside dev the route redirects: the lens shows a synthetic study, which must
  // never reach a researcher who types the URL (review, 3 Oct 2026). The Mac app
  // is the exception — it has no address bar, so the only way here is the rail
  // row, which appears only when BristlenoseFlags.discussionLens is switched on.
  // The export build swaps this module for DiscussionTab.export.tsx, so neither
  // the lens nor its fixture is inlined into an exported report.
  if (!IS_DEV && !isEmbedded()) return <Navigate to="/report/" replace />;
  return <DiscussionLens />;
}
