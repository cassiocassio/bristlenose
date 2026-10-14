import { lazy } from "react";
import { useTranslation } from "react-i18next";
import { SectionHeading } from "../components/SectionHeading";
import { isExportMode } from "../utils/exportData";

// The Screens lens (docs/design-screens.md S5). Lazy-loaded so it code-splits into its own chunk,
// with its CSS. The AppLayout Outlet provides Suspense. The nav offers it only when the project has
// screens (islands/screens/availability.ts); reached any other way, the lens says why it is empty.
const ScreensLens = lazy(() =>
  import("../islands/screens/ScreensLens").then((m) => ({ default: m.ScreensLens })),
);

export function ScreensTab() {
  const { t } = useTranslation();
  if (isExportMode()) {
    // Participants' screens are server-only: an exported report carries none. Titled like every
    // other state of the lens, so it opens on the shared datum.
    return (
      <section>
        <SectionHeading>{t("screens.title")}</SectionHeading>
        <p className="bn-empty-state">{t("screens.notInExport")}</p>
      </section>
    );
  }
  return <ScreensLens />;
}
