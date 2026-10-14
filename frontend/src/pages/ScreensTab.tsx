import { lazy } from "react";
import { SectionHeading } from "../components/SectionHeading";
import { diagnosticsEnabled } from "../utils/diagnostics";

// The Screens lens (diagnostics; docs/design-screens.md S5). Lazy-loaded so it code-splits into
// its own chunk, with its CSS. The AppLayout Outlet provides Suspense.
const ScreensLens = lazy(() =>
  import("../islands/screens/ScreensLens").then((m) => ({ default: m.ScreensLens })),
);

export function ScreensTab() {
  if (!diagnosticsEnabled()) {
    // Titled like every other state of the lens, so it opens on the shared datum.
    return (
      <section>
        <SectionHeading>Screens</SectionHeading>
        <p className="bn-empty-state">Screens are a diagnostics view. Turn on Diagnostics to see them.</p>
      </section>
    );
  }
  return <ScreensLens />;
}
