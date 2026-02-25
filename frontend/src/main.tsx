import { createRoot } from "react-dom/client";
import { AboutPanel } from "./islands/AboutPanel";
import { AnalysisPage } from "./islands/AnalysisPage";
import { CodebookPanel } from "./islands/CodebookPanel";
import { Dashboard } from "./islands/Dashboard";
import { HelloIsland } from "./islands/HelloIsland";
import { QuoteSections } from "./islands/QuoteSections";
import { QuoteThemes } from "./islands/QuoteThemes";
import { SessionsTable } from "./islands/SessionsTable";
import { SettingsPanel } from "./islands/SettingsPanel";
import { Toolbar } from "./islands/Toolbar";
import { TranscriptPage } from "./islands/TranscriptPage";

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

// Mount Toolbar into the quotes tab (above sections/themes)
const toolbarRoot = document.getElementById("bn-toolbar-root");
if (toolbarRoot) {
  createRoot(toolbarRoot).render(<Toolbar />);
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

// Mount AnalysisPage into the analysis tab
const analysisRoot = document.getElementById("bn-analysis-root");
if (analysisRoot) {
  const projectId = analysisRoot.getAttribute("data-project-id") || "1";
  createRoot(analysisRoot).render(<AnalysisPage projectId={projectId} />);
}

// Mount CodebookPanel into the codebook tab
const codebookRoot = document.getElementById("bn-codebook-root");
if (codebookRoot) {
  const projectId = codebookRoot.getAttribute("data-project-id") || "1";
  createRoot(codebookRoot).render(<CodebookPanel projectId={projectId} />);
}

// Mount TranscriptPage into transcript pages (standalone session pages)
const transcriptRoot = document.getElementById("bn-transcript-page-root");
if (transcriptRoot) {
  const projectId = transcriptRoot.getAttribute("data-project-id") || "1";
  const sessionId = transcriptRoot.getAttribute("data-session-id") || "";
  createRoot(transcriptRoot).render(
    <TranscriptPage projectId={projectId} sessionId={sessionId} />
  );
}

// Mount SettingsPanel into the settings tab
const settingsRoot = document.getElementById("bn-settings-root");
if (settingsRoot) {
  createRoot(settingsRoot).render(<SettingsPanel />);
}

// Mount AboutPanel into the about tab (absorbs AboutDeveloper)
const aboutRoot = document.getElementById("bn-about-root");
if (aboutRoot) {
  createRoot(aboutRoot).render(<AboutPanel />);
}
