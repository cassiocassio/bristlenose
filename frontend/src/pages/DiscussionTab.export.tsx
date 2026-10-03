import { Navigate } from "react-router-dom";

// Export-build stand-in for DiscussionTab (aliased in vite.export.config.ts).
// The export inlines every dynamic import into one file, so the real module
// would carry the dev-gated lens and its synthetic fixture into every report.
export function DiscussionTab() {
  return <Navigate to="/report/" replace />;
}
