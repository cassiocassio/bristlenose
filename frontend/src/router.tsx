/**
 * Router — defines all report routes for serve mode.
 *
 * Uses `createBrowserRouter` (React Router v7 data router API).
 * The AppLayout provides the NavBar; each route renders its tab content
 * inside the Outlet.
 */

import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { ProjectTab } from "./pages/ProjectTab";
import { SessionsTab } from "./pages/SessionsTab";
import { TranscriptTab } from "./pages/TranscriptTab";
import { QuotesTab } from "./pages/QuotesTab";
import { CodebookTab } from "./pages/CodebookTab";
import { AnalysisTab } from "./pages/AnalysisTab";
import { SettingsTab } from "./pages/SettingsTab";
import { AboutTab } from "./pages/AboutTab";

export const routes = [
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
      { path: "settings", element: <SettingsTab /> },
      { path: "about", element: <AboutTab /> },
      // Catch-all: unknown sub-paths redirect to project tab
      { path: "*", element: <Navigate to="/report/" replace /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
