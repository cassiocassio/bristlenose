import { lazy } from "react";

// Lazy-loaded so the island code-splits into its own chunk, like SpecimenTab
// (a dev-only surface, kept out of the main bundle and the size gate).
const TagSpecimen = lazy(() =>
  import("../islands/TagSpecimen").then((m) => ({ default: m.TagSpecimen })),
);

export function TagSpecimenTab() {
  return <TagSpecimen />;
}
