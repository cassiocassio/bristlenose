import { createRoot } from "react-dom/client";
import { AboutDeveloper } from "./islands/AboutDeveloper";
import { CodebookPanel } from "./islands/CodebookPanel";
import { Dashboard } from "./islands/Dashboard";
import { HelloIsland } from "./islands/HelloIsland";
import { QuoteSections } from "./islands/QuoteSections";
import { QuoteThemes } from "./islands/QuoteThemes";
import { SessionsTable } from "./islands/SessionsTable";

// Mount HelloIsland (proof of concept — will be removed later)
const helloRoot = document.getElementById("bn-react-root");
if (helloRoot) {
  createRoot(helloRoot).render(<HelloIsland />);
}

// Mount Dashboard into the project tab
const dashboardRoot = document.getElementById("bn-dashboard-root");
if (dashboardRoot) {
  const projectId = dashboardRoot.getAttribute("data-project-id") || "1";
  createRoot(dashboardRoot).render(<Dashboard projectId={projectId} />);
}

// Mount SessionsTable into the sessions tab mount point
const sessionsRoot = document.getElementById("bn-sessions-table-root");
if (sessionsRoot) {
  const projectId = sessionsRoot.getAttribute("data-project-id") || "1";
  createRoot(sessionsRoot).render(<SessionsTable projectId={projectId} />);
}

// Mount QuoteSections into the sections content area
const sectionsRoot = document.getElementById("bn-quote-sections-root");
if (sectionsRoot) {
  const projectId = sectionsRoot.getAttribute("data-project-id") || "1";
  createRoot(sectionsRoot).render(<QuoteSections projectId={projectId} />);
}

// Mount QuoteThemes into the themes content area
const themesRoot = document.getElementById("bn-quote-themes-root");
if (themesRoot) {
  const projectId = themesRoot.getAttribute("data-project-id") || "1";
  createRoot(themesRoot).render(<QuoteThemes projectId={projectId} />);
}

// Mount CodebookPanel into the codebook tab
const codebookRoot = document.getElementById("bn-codebook-root");
if (codebookRoot) {
  const projectId = codebookRoot.getAttribute("data-project-id") || "1";
  createRoot(codebookRoot).render(<CodebookPanel projectId={projectId} />);
}

// Mount AboutDeveloper into the about tab — creates its own mount point
// since the static HTML doesn't include one (serve_mode isn't passed to the
// pipeline renderer). The component silently renders nothing if /api/dev/info
// isn't available (non-dev mode).
const aboutContainer = document.querySelector(".bn-about");
if (aboutContainer) {
  const aboutDevRoot = document.createElement("div");
  aboutDevRoot.id = "bn-about-developer-root";
  aboutContainer.appendChild(aboutDevRoot);
  createRoot(aboutDevRoot).render(<AboutDeveloper />);
}
