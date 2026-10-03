import { lazy } from "react";

// Lazy-loaded so the island code-splits into its own chunk, like SpecimenTab
// (a dev-only surface, kept out of the main bundle and the size gate).
const PickerSpecimen = lazy(() =>
  import("../islands/PickerSpecimen").then((m) => ({ default: m.PickerSpecimen })),
);

export function PickerSpecimenTab() {
  return <PickerSpecimen />;
}
