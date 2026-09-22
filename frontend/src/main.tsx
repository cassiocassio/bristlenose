import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { isExportMode } from "./utils/exportData";
import { redirectHashToPathname } from "./utils/hashRedirect";

// Initialise i18next — must be imported before any component that uses useTranslation.
import "./i18n";

// Translucent chrome (spike): mirror __BRISTLENOSE_EMBEDDED__ into an HTML
// attribute the CSS cascade can gate on. The native WKUserScript sets
// __BRISTLENOSE_EMBEDDED__ at .atDocumentStart before the page loads; running
// this at module top-level (before createRoot below) lands the attribute
// before first paint, so body { background: transparent } takes effect on
// the first frame and there's no white flash for the toolbar frost to sample.
if (
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ === true
) {
  document.documentElement.setAttribute("data-embedded", "true");
}

// ── SPA mode (serve) / Export mode ──────────────────────────────────────
// When #bn-app-root exists, mount the full React Router app.
// In serve mode: browser router (pathname routes).
// In export mode: hash router (file:// has no server for History API).

const appRoot = document.getElementById("bn-app-root");
if (appRoot) {
  // Hash redirect only in serve mode — export uses hash router
  if (!isExportMode()) redirectHashToPathname();
  createRoot(appRoot).render(<RouterProvider router={router} />);
}

// ── Legacy island mode ──────────────────────────────────────────────────
// Fallback for transcript HTML files served as standalone pages (during
// transition) and for the static render path (bristlenose render).
// Each island checks for its own mount point and renders independently.

if (!appRoot) {
  // Lazy-import islands only when needed (not bundled into SPA path)
  void Promise.all([
    import("./islands/HelloIsland"),
    import("./islands/SessionsTable"),
  ]).then(([{ HelloIsland }, { SessionsTable }]) => {
    const helloRoot = document.getElementById("bn-react-root");
    if (helloRoot) {
      createRoot(helloRoot).render(<HelloIsland />);
    }

    const sessionsRoot = document.getElementById("bn-sessions-table-root");
    if (sessionsRoot) {
      const projectId = sessionsRoot.getAttribute("data-project-id") || "1";
      createRoot(sessionsRoot).render(<SessionsTable projectId={projectId} />);
    }
  });
}
