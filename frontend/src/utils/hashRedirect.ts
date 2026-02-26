/**
 * Hash-to-pathname redirect for bookmarked hash-based tab URLs.
 *
 * Converts `#project`, `#sessions`, `#quotes`, etc. to pathname routes.
 * Non-tab hashes (e.g. `#t-123`, `#sections`) are left alone — they're
 * scroll anchors, not navigation targets.
 *
 * Called once at startup before the React Router mounts.
 */

const TAB_ROUTES: Record<string, string> = {
  project: "/report/",
  sessions: "/report/sessions/",
  quotes: "/report/quotes/",
  codebook: "/report/codebook/",
  analysis: "/report/analysis/",
  settings: "/report/settings/",
  about: "/report/about/",
};

export function redirectHashToPathname(): void {
  const hash = window.location.hash.replace("#", "");
  const route = TAB_ROUTES[hash];
  if (route) {
    window.history.replaceState(null, "", route);
  }
}
