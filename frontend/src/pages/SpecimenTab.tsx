import { lazy } from "react";

// Lazy-loaded so the island code-splits into its own chunk (kept out of the
// main bundle and excluded from the size gate — dev-only surface). The
// AppLayout Outlet provides the Suspense boundary.
const GridSpecimen = lazy(() =>
  import("../islands/GridSpecimen").then((m) => ({ default: m.GridSpecimen })),
);

export function SpecimenTab() {
  return <GridSpecimen />;
}
