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
import { RouteError } from "./components/RouteError";
import { ProjectTab } from "./pages/ProjectTab";
import { SessionsTab } from "./pages/SessionsTab";
import { TranscriptTab } from "./pages/TranscriptTab";
import { QuotesTab } from "./pages/QuotesTab";
import { CodebookTab } from "./pages/CodebookTab";
import { AnalysisTab } from "./pages/AnalysisTab";
import { SpecimenTab } from "./pages/SpecimenTab";
import { isExportMode } from "./utils/exportData";

export const routes = [
  // Root redirect — needed for hash router in export mode where the initial
  // URL is #/ (not #/report/).  Browser router never hits this because the
  // server redirects / → /report/.
  { path: "/", element: <Navigate to="/report/" replace /> },
  {
    path: "/report",
    element: <AppLayout />,
    // Single route-level boundary — catches render errors in the layout and
    // every tab (and loader/action rejections), so a crash shows a calm
    // fallback instead of a white screen or dev-facing stack trace.
    errorElement: <RouteError />,
    children: [
      { index: true, element: <ProjectTab /> },
      { path: "sessions", element: <SessionsTab /> },
      { path: "sessions/:sessionId", element: <TranscriptTab /> },
      { path: "quotes", element: <QuotesTab /> },
      { path: "codebook", element: <CodebookTab /> },
      { path: "analysis", element: <AnalysisTab /> },
      // Debug lens — test content on a visible grid (dev-gated NavBar link;
      // desktop entry via Diagnostics menu). Route always registered: the
      // page is benign specimen content and lazy-loads only when visited.
      { path: "specimen", element: <SpecimenTab /> },
      { path: "about", element: <Navigate to="/report/" replace /> },
      // Catch-all: unknown sub-paths redirect to project tab
      { path: "*", element: <Navigate to="/report/" replace /> },
    ],
  },
];

export const router = isExportMode()
  ? createHashRouter(routes)
  : createBrowserRouter(routes);
