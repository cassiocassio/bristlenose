/**
 * Shared route list and session discovery for E2E tests.
 *
 * Auth: Node-side fetch() calls need the bearer token explicitly —
 * Playwright's extraHTTPHeaders only applies to browser contexts.
 * Read from _BRISTLENOSE_AUTH_TOKEN env var (same one the server uses).
 */

const AUTH_TOKEN = process.env._BRISTLENOSE_AUTH_TOKEN;

function authHeaders(): Record<string, string> {
  return AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {};
}

export const STATIC_ROUTES = [
  '/report/',
  '/report/sessions/',
  '/report/quotes/',
  '/report/codebook/',
  '/report/analysis/',
  '/report/settings/',
  '/report/about/',
];

/**
 * Discover session pages dynamically from the sessions API.
 * Returns routes like ['/report/sessions/s1'].
 */
export async function discoverSessionRoutes(
  baseURL: string,
): Promise<string[]> {
  const res = await fetch(`${baseURL}/api/projects/1/sessions`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return (data.sessions ?? []).map(
    (s: { session_id: string }) => `/report/sessions/${s.session_id}`,
  );
}

/**
 * All routes: static + dynamically discovered session pages.
 */
export async function getAllRoutes(baseURL: string): Promise<string[]> {
  const sessionRoutes = await discoverSessionRoutes(baseURL);
  return [...STATIC_ROUTES, ...sessionRoutes];
}
