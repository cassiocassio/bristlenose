import { lazy } from "react";
import { diagnosticsEnabled } from "../utils/diagnostics";

// The Screens lens (diagnostics; docs/design-screens.md S5). Lazy-loaded so it code-splits into
// its own chunk, with its CSS. The AppLayout Outlet provides Suspense.
const ScreensLens = lazy(() =>
  import("../islands/screens/ScreensLens").then((m) => ({ default: m.ScreensLens })),
);

export function ScreensTab() {
  if (!diagnosticsEnabled()) {
    return <div className="screens-lens-status">Screens are a diagnostics view. Turn on Diagnostics to see them.</div>;
  }
  return <ScreensLens />;
}
