/**
 * Router — defines all report routes for serve mode and export mode.
 *
 * Uses `createBrowserRouter` in serve mode (History API) and
 * `createHashRouter` in export mode (file:// has no server).
 * The AppLayout provides the NavBar; each route renders its tab content
 * inside the Outlet.
 */

import { createBrowserRouter, createHashRouter, Navigate } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { ProjectTab } from "./pages/ProjectTab";
import { SessionsTab } from "./pages/SessionsTab";
import { TranscriptTab } from "./pages/TranscriptTab";
import { QuotesTab } from "./pages/QuotesTab";
import { CodebookTab } from "./pages/CodebookTab";
import { AnalysisTab } from "./pages/AnalysisTab";
import { AboutTab } from "./pages/AboutTab";
import { isExportMode } from "./utils/exportData";

export const routes = [
  // Root redirect — needed for hash router in export mode where the initial
  // URL is #/ (not #/report/).  Browser router never hits this because the
  // server redirects / → /report/.
  { path: "/", element: <Navigate to="/report/" replace /> },
  {
    path: "/report",
    element: <AppLayout />,
    children: [
      { index: true, element: <ProjectTab /> },
      { path: "sessions", element: <SessionsTab /> },
      { path: "sessions/:sessionId", element: <TranscriptTab /> },
      { path: "quotes", element: <QuotesTab /> },
      { path: "codebook", element: <CodebookTab /> },
      { path: "analysis", element: <AnalysisTab /> },
      { path: "about", element: <AboutTab /> },
      // Catch-all: unknown sub-paths redirect to project tab
      { path: "*", element: <Navigate to="/report/" replace /> },
    ],
  },
];

export const router = isExportMode()
  ? createHashRouter(routes)
  : createBrowserRouter(routes);
