import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { redirectHashToPathname } from "./utils/hashRedirect";

// ── SPA mode (serve) ────────────────────────────────────────────────────
// When the server injects #bn-app-root, mount the full React Router app.
// This replaces the 11 separate createRoot() calls with a single root.

const appRoot = document.getElementById("bn-app-root");
if (appRoot) {
  redirectHashToPathname();
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
    import("./islands/Dashboard"),
    import("./islands/SessionsTable"),
    import("./islands/Toolbar"),
    import("./islands/QuoteSections"),
    import("./islands/QuoteThemes"),
    import("./islands/AnalysisPage"),
    import("./islands/CodebookPanel"),
    import("./islands/TranscriptPage"),
    import("./islands/SettingsPanel"),
    import("./islands/AboutPanel"),
  ]).then(([
    { HelloIsland },
    { Dashboard },
    { SessionsTable },
    { Toolbar },
    { QuoteSections },
    { QuoteThemes },
    { AnalysisPage },
    { CodebookPanel },
    { TranscriptPage },
    { SettingsPanel },
    { AboutPanel },
  ]) => {
    const helloRoot = document.getElementById("bn-react-root");
    if (helloRoot) {
      createRoot(helloRoot).render(<HelloIsland />);
    }

    const dashboardRoot = document.getElementById("bn-dashboard-root");
    if (dashboardRoot) {
      const projectId = dashboardRoot.getAttribute("data-project-id") || "1";
      createRoot(dashboardRoot).render(<Dashboard projectId={projectId} />);
    }

    const sessionsRoot = document.getElementById("bn-sessions-table-root");
    if (sessionsRoot) {
      const projectId = sessionsRoot.getAttribute("data-project-id") || "1";
      createRoot(sessionsRoot).render(<SessionsTable projectId={projectId} />);
    }

    const toolbarRoot = document.getElementById("bn-toolbar-root");
    if (toolbarRoot) {
      createRoot(toolbarRoot).render(<Toolbar />);
    }

    const sectionsRoot = document.getElementById("bn-quote-sections-root");
    if (sectionsRoot) {
      const projectId = sectionsRoot.getAttribute("data-project-id") || "1";
      createRoot(sectionsRoot).render(<QuoteSections projectId={projectId} />);
    }

    const themesRoot = document.getElementById("bn-quote-themes-root");
    if (themesRoot) {
      const projectId = themesRoot.getAttribute("data-project-id") || "1";
      createRoot(themesRoot).render(<QuoteThemes projectId={projectId} />);
    }

    const analysisRoot = document.getElementById("bn-analysis-root");
    if (analysisRoot) {
      const projectId = analysisRoot.getAttribute("data-project-id") || "1";
      createRoot(analysisRoot).render(<AnalysisPage projectId={projectId} />);
    }

    const codebookRoot = document.getElementById("bn-codebook-root");
    if (codebookRoot) {
      const projectId = codebookRoot.getAttribute("data-project-id") || "1";
      createRoot(codebookRoot).render(<CodebookPanel projectId={projectId} />);
    }

    const transcriptRoot = document.getElementById("bn-transcript-page-root");
    if (transcriptRoot) {
      const projectId = transcriptRoot.getAttribute("data-project-id") || "1";
      const sessionId = transcriptRoot.getAttribute("data-session-id") || "";
      createRoot(transcriptRoot).render(
        <TranscriptPage projectId={projectId} sessionId={sessionId} />
      );
    }

    const settingsRoot = document.getElementById("bn-settings-root");
    if (settingsRoot) {
      createRoot(settingsRoot).render(<SettingsPanel />);
    }

    const aboutRoot = document.getElementById("bn-about-root");
    if (aboutRoot) {
      createRoot(aboutRoot).render(<AboutPanel />);
    }
  });
}
