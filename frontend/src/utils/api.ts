/**
 * Fire-and-forget PUT helpers for the data API endpoints.
 *
 * Each function sends the full state map to the server. Failures are
 * logged to the console but not surfaced to the user — the local state
 * is the source of truth during a session.
 */

function apiBase(): string {
  return (
    (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE as string
  ) || "/api/projects/1";
}

function firePut(path: string, body: unknown): void {
  fetch(`${apiBase()}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch((err) => {
    console.error(`PUT ${path} failed:`, err);
  });
}

export function putHidden(data: Record<string, boolean>): void {
  firePut("/hidden", data);
}

export function putStarred(data: Record<string, boolean>): void {
  firePut("/starred", data);
}

export function putEdits(data: Record<string, string>): void {
  firePut("/edits", data);
}

export function putTags(data: Record<string, string[]>): void {
  firePut("/tags", data);
}

export function putDeletedBadges(data: Record<string, string[]>): void {
  firePut("/deleted-badges", data);
}
