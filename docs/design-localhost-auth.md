# Localhost Auth Token — Design Plan

## Context

Bristlenose's serve mode API (`bristlenose serve`) listens on `127.0.0.1:8150-9149` with **zero authentication**. CORS blocks cross-origin browser requests, but any local process (malware, clipboard monitors, collab tools) can `curl http://127.0.0.1:8150/api/projects/1/quotes` and exfiltrate participant names, quotes, themes, and sentiment data. This is flagged as **must-fix before distribution** in the launch checklist.

**What this is**: a defence-in-depth speed bump against opportunistic local-process scraping. It is **not** an authentication boundary — a determined attacker with same-user privileges can still read the token from the HTML response or the SQLite file directly. The real security boundary is OS process isolation. This token stops lazy one-liner attacks (`curl localhost:8150/api/...`), which is the right level of protection for same-machine IPC.

## Threat model

- **Attacker**: malicious local process already running on the user's machine
- **Attack**: direct HTTP requests to the serve API (not browser-based — CORS irrelevant)
- **Assets at risk**: participant names, interview quotes, themes, sentiment, codebook, transcript text, **interview recordings via `/media/*`**
- **Out of scope**: remote network attacks (serve binds to 127.0.0.1 only), browser-based attacks (CORS already blocks)
- **Honest assessment**: a purposeful attacker can fetch `/report/`, extract the token from HTML, and call any API. The token raises the bar from zero-effort to trivial two-step. Worth doing as defence-in-depth; must not be overstated

## Design

### Token lifecycle

1. **Generation**: `create_app()` generates a 32-byte `secrets.token_urlsafe()` at startup (256 bits of entropy — brute-force infeasible)
2. **Storage**: stored on `app.state.auth_token` (in-memory only, never persisted to disk)
3. **Injection into HTML**: server injects `<script>window.__BRISTLENOSE_AUTH_TOKEN__ = {json.dumps(token)}</script>` into the SPA HTML — use `json.dumps()` not bare interpolation
4. **Injection into desktop**: `ServeManager` reads the token from stdout, validates format with regex, injects via `WKUserScript` at document start
5. **Frontend sends it**: `api.ts` reads `window.__BRISTLENOSE_AUTH_TOKEN__` and adds `Authorization: Bearer <token>` header to **all six** fetch helpers (`apiGet`, `apiPost`, `apiPatch`, `apiDelete`, `apiDeleteJson`, `firePut`)
6. **Server validates it**: Starlette middleware checks `Authorization` header on all `/api/*` and `/media/*` paths. Returns fixed `{"detail": "Unauthorized"}` (401) — no distinction between missing/wrong token, no hints

### Auth-exempt paths

Defined as a constant `_AUTH_EXEMPT_PREFIXES` in the middleware module. Tested explicitly.

| Path prefix | Reason |
|-------------|--------|
| `/api/health` | Version/status only, no project data. Desktop needs it pre-auth for version display |
| `/api/docs` | Swagger UI (dev convenience) |
| `/report/` | SPA shell HTML/CSS/JS — no sensitive data, and the token is embedded here |
| `/static/`, `/assets/` | Vite bundle files |

**`/media/*` REQUIRES auth** — interview recordings and audio are the most sensitive data in the system.

### Token delivery to desktop app

**Chosen approach: stdout line**

The serve process prints the token during `create_app()` (before the "Report:" readiness line):
```
[bristlenose] auth-token: <token>
```

**Ordering invariant**: token line MUST print before "Report:" so `ServeManager` has it before transitioning to `.running`. Document this with a comment in `create_app()`.

`ServeManager.swift` captures this line (same pattern as readiness signal), validates the format, stores as `@Published var authToken: String?`. Then injects into WKWebView via `WKUserScript`:

```swift
// Validate token contains only URL-safe characters before interpolation
// (enforces the safety invariant from secrets.token_urlsafe)
guard token.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil else {
    print("[ServeManager] invalid auth token format — not injecting")
    return
}
let script = WKUserScript(
    source: "window.__BRISTLENOSE_AUTH_TOKEN__ = '\(token)';",
    injectionTime: .atDocumentStart,
    forMainFrameOnly: true  // popout loads player.html which gets token from server-side injection
)
```

**`forMainFrameOnly: true`** (security review recommendation): the popout player loads `http://127.0.0.1:{port}/report/player.html` which receives the token via server-side HTML injection, same as the main SPA. No need to inject into sub-frames.

**Why not env var**: the token is generated fresh each startup, can't be set before process launch.
**Why not health endpoint**: chicken-and-egg — you need the token to call the API.

### Token delivery to browser (CLI serve)

The server injects the token into the HTML via `_build_spa_html()` and `_build_dev_html()`:
```python
token_script = f'<script>window.__BRISTLENOSE_AUTH_TOKEN__ = {json.dumps(app.state.auth_token)}</script>'
```

Uses `json.dumps()` for safe serialisation (even though `token_urlsafe` only produces `[a-zA-Z0-9_-]`).

### Frontend auth header

Centralised helper in `api.ts`:
```typescript
function authHeaders(): HeadersInit {
  const token = (window as any).__BRISTLENOSE_AUTH_TOKEN__;
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}
```

All six fetch helpers use this. When `__BRISTLENOSE_AUTH_TOKEN__` is absent (static HTML opened from disk), no header is sent — existing offline graceful degradation is unaffected.

### 401 response design

Fixed JSON body for all auth failures:
```json
{"detail": "Unauthorized"}
```

No distinction between missing token, wrong token, or expired token. No hints about expected format. No rate limiting needed (256-bit token, brute-force infeasible).

### Dev mode (uvicorn reload)

Token stashed in `os.environ["_BRISTLENOSE_AUTH_TOKEN"]` (follows `_BRISTLENOSE_PROJECT_DIR` convention). Factory recovers it on reload. Token survives hot-reload, changes on full restart.

## Files to modify

### Python (server side)

| File | Change |
|------|--------|
| `bristlenose/server/app.py` | Generate token in `create_app()`, store on `app.state.auth_token`, add middleware, inject into `_build_spa_html()` and `_build_dev_html()`, print stdout line |
| `bristlenose/server/middleware.py` | **New file** — `BearerTokenMiddleware`. Checks `Authorization: Bearer <token>` on `/api/*` and `/media/*` paths. `_AUTH_EXEMPT_PREFIXES` constant. Returns 401 JSON |
| `bristlenose/cli.py` | Store token in env var for dev-mode reload recovery |
| `SECURITY.md` | Add "Serve mode API access control" section — honest framing as defence-in-depth, not authentication |

### Swift (desktop side)

| File | Change |
|------|--------|
| `desktop/.../ServeManager.swift` | Parse `auth-token:` line from stdout, regex-validate format, store as `@Published var authToken: String?` |
| `desktop/.../WebView.swift` | Accept token parameter, inject as `WKUserScript` with `forMainFrameOnly: true` and format validation |

### TypeScript (frontend)

| File | Change |
|------|--------|
| `frontend/src/utils/api.ts` | `authHeaders()` helper, apply to all six fetch functions |

### Tests

| File | Change |
|------|--------|
| `tests/test_serve_auth.py` | **New** — token generation, middleware 401/200, every exempt path verified, `/media/*` requires auth, 401 response shape |
| `tests/test_serve_*.py` (existing) | Shared `auth_headers(app)` fixture/helper auto-injected into requests |
| `frontend/src/utils/api.test.ts` | Test `authHeaders()` with/without token, verify header on all six fetch paths |

## Implementation order

1. **Token generation + middleware** (`app.py`, new `middleware.py`) — core auth gate
2. **Shared test fixture** — `auth_headers(app)` helper so existing tests pass immediately
3. **Update existing Python tests** — inject auth headers via fixture
4. **New auth-specific tests** (`test_serve_auth.py`) — 401 without token, 200 with token, all exempt paths, `/media/*` auth required, response shape
5. **HTML injection** — `_build_spa_html()` and `_build_dev_html()` with `json.dumps()`
6. **Frontend `authHeaders()`** — centralised helper in `api.ts`, applied to all six functions
7. **Stdout token line** — print from `create_app()` before readiness signal
8. **Swift integration** — `ServeManager` parses + validates token, `WebView` injects via `WKUserScript`
9. **Frontend tests** — `api.test.ts`
10. **Dev-mode reload** — env var stash/recovery in `cli.py`
11. **SECURITY.md update** — document the access control model honestly

## Verification

1. `pytest tests/` — all existing + new tests pass
2. Manual: `bristlenose serve trial-runs/project-ikea` → browser loads, API works (token in HTML)
3. Manual: `curl http://127.0.0.1:8150/api/projects/1/quotes` → 401
4. Manual: `curl http://127.0.0.1:8150/api/health` → 200 (exempt)
5. Manual: `curl http://127.0.0.1:8150/media/interviews/video.mp4` → 401
6. Manual: `curl -H "Authorization: Bearer <token>" http://127.0.0.1:8150/api/projects/1/quotes` → 200
7. `cd frontend && npm test` — api.ts auth header tests pass
8. `ruff check .` — clean
9. Desktop: Xcode build + run → WKWebView loads, API calls succeed, token in stdout log

## Post-implementation updates

- **`docs/private/100days.md:154`** — update the localhost auth token line to reference this design plan and mark as in-progress/done:
  ```
  - ~~**Desktop security: localhost auth token**~~ — bearer token middleware, per-session `secrets.token_urlsafe(32)`, injected into HTML + WKUserScript. Design plan: `docs/design-localhost-auth.md`
  ```
- **Save the final plan** as `docs/design-localhost-auth.md` (committed, permanent reference for the security decision and threat model)

## Security review findings (incorporated above)

From adversarial security review, key changes from initial draft:

1. **Honest threat framing** — token is defence-in-depth speed bump, not auth boundary. Updated Context section
2. **`forMainFrameOnly: true`** — popout player gets token from server-side HTML injection instead. Avoids leaking token into sub-frames
3. **Regex-validate token in Swift** before string interpolation — enforces `[A-Za-z0-9_-]+` safety invariant, complies with security rule 3
4. **`json.dumps()` for Python injection** — safe serialisation habit
5. **`/media/*` requires auth** — interview recordings are the most sensitive data
6. **Fixed 401 body** — no information leakage (no missing-vs-wrong distinction)
7. **Centralised `authHeaders()`** — all six fetch paths covered, not just the obvious ones
8. **`_AUTH_EXEMPT_PREFIXES` as testable constant** — exempt paths are explicit and tested
9. **SECURITY.md framing** — "request validation" not "authentication". Honest about what it does and doesn't protect against
