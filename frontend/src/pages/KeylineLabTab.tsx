import { lazy } from "react";

// Lazy-loaded so the island code-splits into its own chunk, like TagSpecimenTab
// (a dev-only surface, kept out of the main bundle and out of the HTML export).
const KeylineLab = lazy(() =>
  import("../islands/KeylineLab").then((m) => ({ default: m.KeylineLab })),
);

export function KeylineLabTab() {
  return <KeylineLab />;
}
