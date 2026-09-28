---
status: mixed
last-trued: 2026-09-28
trued-against: HEAD@main on 2026-09-28 (717fb6a1)
---

## Changelog

- _2026-09-28 (later)_ — trued up: §"Cookie fallback" marks the
  unconditional cookie check superseded by `_is_own_navigation`; the
  as-built CSRF question became the measured record of probe and fix.
  Anchors: `middleware.py` `_is_own_navigation`,
  `tests/test_serve_auth.py::TestCookieIsForOwnNavigationsOnly`; commit
  "serve's auth cookie no longer rides along on requests from another
  loopback port".
- _2026-09-28_ — trued up: added §"As built — what the token does not
  cover", marked the six "`/media/*` requires auth" claims, the popout's
  server-side token injection, the "CORS blocks browser attacks" scoping and
  CSRF paragraph, and verification step 5 as superseded. Anchors:
  `middleware.py` `_AUTH_REQUIRED_PREFIXES` / `LoopbackHostMiddleware`,
  `app.py` `_contained_path`, `tests/test_serve_auth.py::test_media_exempt_from_auth`;
  commits "serve no longer hands out the pii re-identification key on
  /report/ without a token", "/media/ serves recordings only, no longer the
  unredacted transcript", "status page no longer shows the run log to
  unauthenticated callers", "serve refuses any non-loopback host, closing dns
  rebinding".
- _2026-05-10_ — trued up: added §"Cookie fallback for plain navigations"
  describing the `bristlenose_auth` HttpOnly/SameSite=Strict cookie set on
  SPA HTML responses, used by anchor-click downloads (export flow) under
  sandboxed WKWebView where the JS-injected `Authorization` header doesn't
  ride along. Anchors: `bristlenose/server/middleware.py:33-39, 70-74`,
  `bristlenose/server/app.py:_spa_response`,
  `tests/test_serve_auth.py::TestCookieFallback`.
- _2026-04-18_ — initial draft + dev-mode env-override gap captured.

# Localhost Auth Token — Design Plan

> **Truing status (28 Sep 2026):** the token mechanism below shipped as
> planned for `/api/*` (and later `/mcp`). What did **not** ship as planned is
> the scope: `/media/*` has never required the token since 27 Mar 2026, and
> several routes carry data without it. The plan text is kept below as the
> record of intent; §"As built" is authoritative for what the token covers.

## As built — what the token does not cover

The middleware checks the token only on `_AUTH_REQUIRED_PREFIXES` = `/api/`
and `/mcp` (`bristlenose/server/middleware.py`). `_AUTH_EXEMPT_PREFIXES` is
`/api/health`, `/api/docs`, `/openapi.json`. **Everything outside the
required prefixes is open by omission** — a new route not under `/api/` is
unauthenticated by default, so it needs its own guard. Today's open routes:

| Route | Why no token | What guards it |
|-------|--------------|----------------|
| `/media/*` | `<video>`/`<audio>` cannot send headers (unauthenticated since 27 Mar 2026, pinned by `tests/test_serve_auth.py::test_media_exempt_from_auth`) | `_contained_path` in `app.py`: rooted at the project dir, **recordings only** (`AUDIO_EXTENSIONS \| VIDEO_EXTENSIONS` from `models.py`), refuses any `.`-prefixed component before and after resolving, refuses anything outside the root. Until 28 Sep 2026 it also served `.txt`/`.docx`/`.srt`/`.vtt`/images — the pre-redaction `transcripts-raw/*.txt` included |
| `/report/<file>` | The WKWebView loads the SPA's files without a header | `_contained_path` again, rooted at `<output_dir>/assets/` only. Until 28 Sep 2026 it was a bare `output_dir / path`: it served `.bristlenose/pii_summary.txt` and `..%2F` escaped the output dir |
| `/report/*` (SPA HTML) | It is where the token is handed out | Nothing but the `Host` check below — the page carries the token and sets the cookie, so anything that can read it can call the API |
| `/report/*` (status page) | Shown instead of the SPA after a failed/cancelled run, or before any run | Carries the structured cause only. Until 28 Sep 2026 it appended the last 4 KB of `bristlenose.log` (absolute paths, input filenames, provider error text) |
| `/chat-lens` | Lab page that injects the token like the SPA | `Host` check; mounted when `experimental_chat_lens` is on (the default) |
| `/codebook-lab` | Lab page that injects the token | `Host` check; mounted only when `experimental_codebook_lab` is on (off by default) |
| `/admin` | Read-only DB browser (`serve --dev` or `_BRISTLENOSE_ADMIN_PANEL=1`) | `Host` check |
| `GET /mcp/` from a browser | Static explainer page, no data | — |

**The `Host` check is what makes browser attacks out of scope, not CORS.**
A DNS-rebound page is same-origin to the browser, so CORS never fires and the
`SameSite=Strict` cookie rides along. `LoopbackHostMiddleware` (outermost in
`create_app`) refuses any `Host` other than `127.0.0.1`, `localhost` or
`[::1]` with a 400; before 28 Sep 2026 only `/mcp/` had that protection.
`SECURITY.md` §"Serve mode API access control" carries the user-facing
version of this table.

**Same-site CSRF from another loopback port — measured and closed 28 Sep
2026.** `SameSite` ignores the port, so a page served from `127.0.0.1:<other
port>` (any local dev server) is same-site to serve and passes the `Host`
check. Probed with Playwright in Chromium and WebKit: an auto-submitted form
and a `fetch(…, {mode: "no-cors", credentials: "include"})` from such a page
both carried the cookie, with `Sec-Fetch-Site: same-site`; a `localhost:<port>`
page (cross-site) did not. CORS hides the answer but does not stop a simple
request reaching the route, and the bodiless POSTs act on arrival — start an
AutoCode run, `synthesize`, accept/deny proposals, Miro disconnect. (JSON-body
POSTs were already refused by FastAPI's `strict_content_type`, after auth.)
The page could not have read the token itself: `/report/` is cross-origin to
it. **Fix:** `_is_own_navigation` in `middleware.py` honours the cookie only
for GET/HEAD, and not when `Sec-Fetch-Site` is `same-site` or `cross-site`.
An absent header passes, because WebKit sends none on the export download
navigation (measured). Pinned by `tests/test_serve_auth.py::TestCookieIsForOwnNavigationsOnly`.

**Smaller drift in the plan below, not banner-marked:** the port range is
8150–8159 on the CLI (`_find_open_port`) and `--port 0` from the desktop, not
8150–9149; `authHeaders(extra?)` serves every helper in `api.ts` (~40, and no
longer sets `Content-Type` itself), not "all six"; the test helper is
`AuthTestClient` + `LOOPBACK_BASE_URL` in `tests/conftest.py`, not an
`auth_headers(app)` fixture; `frontend/src/utils/api.test.ts` was never written.

## Context

Bristlenose's serve mode API (`bristlenose serve`) listens on `127.0.0.1:8150-9149` with **zero authentication**. CORS blocks cross-origin browser requests, but any local process (malware, clipboard monitors, collab tools) can `curl http://127.0.0.1:8150/api/projects/1/quotes` and exfiltrate participant names, quotes, themes, and sentiment data. This is flagged as **must-fix before distribution** in the launch checklist.

**What this is**: a defence-in-depth speed bump against opportunistic local-process scraping. It is **not** an authentication boundary — a determined attacker with same-user privileges can still read the token from the HTML response or the SQLite file directly. The real security boundary is OS process isolation. This token stops lazy one-liner attacks (`curl localhost:8150/api/...`), which is the right level of protection for same-machine IPC.

## Threat model

- **Attacker**: malicious local process already running on the user's machine
- **Attack**: direct HTTP requests to the serve API (not browser-based — CORS irrelevant)
- **Assets at risk**: participant names, interview quotes, themes, sentiment, codebook, transcript text, **interview recordings via `/media/*`**
- **Out of scope**: remote network attacks (serve binds to 127.0.0.1 only), browser-based attacks (CORS already blocks)
  > **Superseded 28 Sep 2026** — CORS does not block DNS rebinding (same-origin to the browser); the `Host` check does. See §"As built".
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

> **Superseded 27 Mar 2026** — `/media/` was taken out of the token check because `<video>`/`<audio>` cannot send headers (the player showed "Cannot play this format", `MediaError` 4). The same holds for every `/media/*` claim below (Design step 6, Files to modify, Tests, Implementation order 4, Verification 5, review finding 5). This table is also not the shipped `_AUTH_EXEMPT_PREFIXES`; see §"As built".

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

> **Superseded** — the popout loads `assets/bristlenose-player.html` (`PlayerContext.tsx`), a plain file with no token injected. It needs none: the only thing it fetches is `/media/`.

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

### Cookie fallback for plain navigations

`fetch()` calls authenticate via the JS-injected `Authorization: Bearer …` header. **Plain browser navigations don't** — when the React export modal triggers `<a download>` against `/api/projects/{id}/export…`, WKWebView (and any browser) issues a cooked navigation with no chance for JS to add a header. Under App Sandbox the click would 401 silently and never reach the WKDownload path.

To cover those cases, `_spa_response()` in `app.py` sets a `bristlenose_auth` cookie on every SPA HTML response carrying the same token. `BearerTokenMiddleware.dispatch` checks the cookie as a fallback after the header check fails:

```python
if request.cookies.get(AUTH_COOKIE_NAME) == expected:
    return await call_next(request)
```

> **Superseded 28 Sep 2026** — the check also requires `_is_own_navigation(request)`: GET/HEAD only, and refused when `Sec-Fetch-Site` is `same-site` or `cross-site`. A page on another loopback port is same-site and was getting this cookie sent with its POSTs. See §"As built".

Cookie attributes: `HttpOnly` (defence-in-depth — JS already has the same value via `window.__BRISTLENOSE_AUTH_TOKEN__`, but no need to expose the cookie itself), `SameSite=Strict` (CSRF), `Secure=False` (localhost is `http://`; the cookie never traverses a network), `Path=/`, no `Expires` (session-scoped, dies with the WKWebView's ephemeral data store).

CSRF is out of scope: the existing CORS middleware (`allow_origins=[]` by default) blocks every cross-origin request before the cookie ever ships. _(28 Sep 2026: true of cross-origin pages only. A DNS-rebound page and a page on another loopback port are both same-site, and the cookie rides along; `LoopbackHostMiddleware` refuses the first and `_is_own_navigation` the second — see §"As built".)_ The cookie carries no per-user/per-project information — it's the same opaque random string as the Bearer header, just in a delivery channel native to anchor-click navigations.

### 401 response design

Fixed JSON body for all auth failures:
```json
{"detail": "Unauthorized"}
```

No distinction between missing token, wrong token, or expired token. No hints about expected format. No rate limiting needed (256-bit token, brute-force infeasible).

### Dev mode (uvicorn reload)

Token stashed in `os.environ["_BRISTLENOSE_AUTH_TOKEN"]` (follows `_BRISTLENOSE_PROJECT_DIR` convention). Factory recovers it on reload. Token survives hot-reload, changes on full restart.

**Known gap (18 Apr 2026):** the env-override is currently unconditional — if `_BRISTLENOSE_AUTH_TOKEN` is set in the parent shell (e.g. leftover from a CI run or a dotfile), serve adopts it instead of generating random. `SECURITY.md` was corrected in v0.14.6 to describe this, and `bristlenose doctor` warns when the env var is set, but a proper gate behind `BRISTLENOSE_DEV_MODE=test` is deferred — tracked in `docs/private/100days.md` §6 Risk. The gate needs to preserve reload continuity (the whole point of the writeback above) while refusing inherited tokens, which is a non-trivial read-vs-write design question.

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
