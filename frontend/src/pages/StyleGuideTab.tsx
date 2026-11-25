import { lazy } from "react";

// Lazy-loaded so the island code-splits into its own chunk, like SpecimenTab
// (a dev-only surface, kept out of the main bundle and the size gate).
const StyleGuide = lazy(() =>
  import("../islands/StyleGuide").then((m) => ({ default: m.StyleGuide })),
);

export function StyleGuideTab() {
  return <StyleGuide />;
}
