---
status: current
last-trued: 2026-05-06
trued-against: HEAD@main on 2026-05-06 (commit 0bb4370)
---

# Desktop asset serving — Plan A + Plan B

> Architecture decision. **Status: Plan A landed for alpha (5 May 2026), then required upstream `mimetypes` patch to be effective (6 May 2026); Plan B parked for post-alpha re-evaluation.** Sibling to `docs/design-modularity.md` and `docs/design-wkwebview-messaging.md`.

## Changelog

- **2026-05-06** — trued against shipped reality after `sandbox-mimetypes-init` (`768f9a4`). Replaced the pre-spike `sendfile()` hypothesis in `Problem` with the empirically confirmed `mimetypes.init()` cause; original guess preserved below as a baseline. Added "Shipped upstream fix" subsection. Reframed Plan A as the request-handler half of a two-part fix.
- **2026-05-05** — authored. Plan A queued for alpha; Plan B parked.

## Problem

Under macOS App Sandbox, the bundled Python sidecar's FastAPI `StaticFiles` mount returns **HTTP 500 Internal Server Error** for every existing file under `/static/assets/*` (and the `/assets/*` alias). 404 responses for missing files work correctly. So Starlette's `StaticFiles` can stat the path but throws when streaming the contents.

Symptom cascade:

- React entry script `main-Bk0xhbIx.js` 500s
- React never executes
- `<div id="bn-app-root">` stays empty
- All tabs render blank
- Bridge calls (`window.switchToTab`, `window.__bristlenose.menuAction`) silently fail because their JS handlers were never installed
- Cmd+? produces an OS error bell
- Help menu, tab switching, all Cmd+1-5 broken

Diagnosis confirmed by curl from outside the WKWebView — same 500 from any client. Not a WKWebView CORS / modulepreload / auth-token issue. Server-side problem in the sandboxed sidecar's StaticFiles handler.

**Confirmed root cause (6 May 2026):** Python's `mimetypes.init()` lazily walks `/etc/mime.types`, `/etc/apache2/mime.types`, etc. Under macOS App Sandbox these reads raise `PermissionError`, which CPython's `init()` doesn't catch. `mimetypes._db` is left in a partially-initialised, poisoned state, and every subsequent `mimetypes.guess_type()` call (Starlette's `StaticFiles` and our custom routes both rely on it) raises the same exception, surfacing as HTTP 500. HTML routes work because they don't pass through `guess_type` for the response media type.

> **Pre-diagnosis hypothesis (preserved as baseline, superseded 2026-05-06):**
> The original guess was that App Sandbox blocked the syscall Starlette uses for file streaming — `sendfile()` or an `aiofiles` async path. This led to Plan A below (replace streaming with in-memory `read_bytes`). The `read_bytes` swap was correct as a defence-in-depth simplification but was not the load-bearing fix; the load-bearing fix is upstream of any request handler. See "Shipped upstream fix" below.

## Peer-architecture context

We're at an unusual intersection: Mac App Store distribution + Python sidecar + React in WKWebView + sandbox-on. The "embed local web content in a Mac app" problem is well-trodden, but most peers solve it by relaxing one of those constraints:

| Distribution | Sandbox | Asset path | Examples |
|---|---|---|---|
| Outside App Store (direct download / Creative Cloud) | No | Custom runtime (UXP) or bundled Chromium (Electron) | Photoshop, Slack, VS Code, Notion |
| App Store, native UI | Yes | No web content | Indie Mac apps (Things, Bear, etc.) |
| App Store, WKWebView | Yes | `WKURLSchemeHandler` | Tauri apps, Capacitor apps |
| App Store, WKWebView + localhost | Yes | FastAPI / Flask / similar (this project) | Niche |

The genuinely comparable pattern is **Tauri / Capacitor** — both solve sandboxed asset serving with `WKURLSchemeHandler`. Apache Cordova-iOS migrated *from* a localhost server *to* `WKURLSchemeHandler` in PR #781 (2019). They identified the localhost-server-in-sandbox approach as error-prone and complicated, and switched.

Bristlenose ships a Python sidecar specifically because the same FastAPI app serves CLI users (browser on localhost) — so the localhost server is load-bearing for the CLI distribution, even if it's wrong shape for the sandboxed Desktop one. This is what makes our niche distinctive.

## Constraint context

**No-fork principle** (from `docs/design-modularity.md`): the same Python code path serves the same content for CLI users (browser-on-localhost) and Desktop users (WKWebView-on-localhost). Switching the Desktop's asset-serving away from Python without affecting the CLI matters.

**Existing precedent for Mac-native bypasses** that respect the no-fork principle:

| Concern | CLI path | Desktop path |
|---|---|---|
| Keychain | `/usr/bin/security` subprocess | `Security.framework` + env-var injection |
| Process introspection | `/bin/ps`, `/usr/sbin/lsof` | `libproc` (Swift, native) |
| FFmpeg | system / homebrew | bundled binary, path helper |
| Static asset serving (proposed) | FastAPI `StaticFiles` | `WKURLSchemeHandler` reading bundle |

Each row: Python path that works for CLI but breaks under sandbox → thin Swift bypass that reads the same data via a Mac-native API. That's the established pattern. A WKURLSchemeHandler-based static-asset path would be symmetrical, not a violation.

## Plan A — minimal patch (alpha)

**Goal:** make `/static/*` return 200 with the correct bytes under sandbox, with the smallest possible change. Ship TestFlight.

### Mechanism

Replace FastAPI's `StaticFiles` mount with a custom route handler that:

1. Resolves the requested path against `_STATIC_DIR`
2. Reads the file with `await asyncio.to_thread(target.read_bytes)` (async-safe blocking read)
3. Returns a `Response(content=bytes, media_type=guess_type(path), headers={...cache-control...})` — note: `guess_type` is itself the failure surface under sandbox; this step depends on `mimetypes.knownfiles` being emptied at package import (see "Shipped upstream fix" below). Without that, both this custom route and the original `StaticFiles` mount fail identically.

This bypasses Starlette's sendfile-based streaming. Works on any platform. Loses the streaming optimisation for very large files (irrelevant for ~80 small JS chunks). Adds an exception logger so any future failure surfaces a real Python traceback instead of generic 500. **Shipped 5 May 2026 (`40e78bf`); proved insufficient on its own** — see "Shipped upstream fix".

### Files touched

- `bristlenose/server/app.py` — replace `app.mount("/static", StaticFiles(...))` with a `@app.get("/static/{path:path}")` handler. Same for `/assets` alias.
- `tests/server/test_static_serving.py` (new) — assert 200 on a known asset, 404 on missing, correct `Content-Type` for `.js` / `.css` / `.html`.

### Risk

Low. Custom file-reading is well-understood. Bypassing streaming for assets at this size has no observable performance impact. No protocol change for clients (still HTTP, still localhost, still same URLs).

### What it doesn't fix

Doesn't address the broader architectural friction (localhost server in a sandbox vs. native scheme handler). Just gets the request-handler half of the sandbox StaticFiles failure out of the alpha path. The request handler is necessary but not sufficient — see next section.

## Shipped upstream fix — `mimetypes.knownfiles = []` at package import (6 May 2026)

**Goal:** make `mimetypes.guess_type()` safe to call under sandbox, for *all* call sites. Plan A's custom route still tripped the same lazy init; the fix has to land before any caller of `guess_type` can reach the system-files walk.

### Mechanism

In `bristlenose/__init__.py`, before any submodule loads:

```python
import mimetypes as _mimetypes
_mimetypes.knownfiles = []          # drop /etc/mime.types et al. before any init
_mimetypes.add_type("application/javascript", ".js")
_mimetypes.add_type("text/css",                ".css")
_mimetypes.add_type("text/html",               ".html")
_mimetypes.add_type("application/json",        ".json")
_mimetypes.add_type("image/svg+xml",           ".svg")
_mimetypes.add_type("font/woff2",              ".woff2")
del _mimetypes
```

When the lazy `init()` eventually runs (via `guess_type`), the loop walks an empty list. No system-file reads, no `PermissionError`, no poisoned `_db`.

### Why `mimetypes.init([])` doesn't work

The intuitive escape hatch — call `init([])` early to skip the system walk — **does not work in Python 3.12+**. CPython 3.12.13's `mimetypes.py:378` does:

```python
if files is None:
    files = knownfiles
else:
    files = knownfiles + list(files)   # ← appends to knownfiles
```

So `init([])` reads `knownfiles + []` = the full system list. Trying that landed in commit `3349944` and was reverted in `2151a52` once verified to still 500. The reliable escape hatch is to mutate `knownfiles` itself — that's what the shipped fix does.

### Files touched

- `bristlenose/__init__.py:8-22` — the seven lines above plus the why-comment.
- `tests/test_static_serving.py::TestMimetypesKnownfilesEmptied` — regression guard. Two cases: `mimetypes.knownfiles == []` after import, and the six explicit registrations resolve. Future contributors who delete this code will fail this test.

### Verification

End-to-end under sandbox-on Debug, 6 May 2026: every `/static/assets/*.js` chunk returns 200, log shows zero `PermissionError` lines on `/static/*` paths, React UI mounts and all tabs render. Commit `768f9a4`.

## Plan B — adopt `WKURLSchemeHandler` for desktop asset serving (post-alpha)

**Goal:** align the desktop with Apple-canonical local-content delivery. Same pattern Tauri / Capacitor use today.

### Mechanism

Inside the desktop app only:

1. Register a custom URL scheme (e.g. `bristlenose://`) with WKWebView via `WKWebViewConfiguration.setURLSchemeHandler(_, forURLScheme:)`
2. Implement Swift `WKURLSchemeHandler` that, for any `bristlenose://...` request, reads the corresponding file from `Bundle.main.resourceURL/.../static/` and responds with bytes + correct MIME
3. Adjust the HTML response (or strip during desktop bootstrap) so `/static/*` and `/assets/*` paths use `bristlenose://...` scheme inside the desktop WebView; CLI users keep `http://localhost:port/static/*`
4. API calls (`/api/*`) keep using `http://localhost:port` — only static asset paths fork

### What stays single-codebase

- React frontend (single build, single bundle)
- Python pipeline (transcription, LLM calls, analysis, export)
- All FastAPI API routes (`/api/*`)
- HTML template
- CSS

### What forks

- ~50 lines of Swift (`WKURLSchemeHandler` implementation)
- Possibly: HTML rewriting on the desktop boot path so `/static/` becomes `bristlenose://` (or use `<base href>` trick)
- Possibly: drop the `/static/*` route from the desktop's bundled Python sidecar (the desktop sidecar still serves `/api/*`, `/report/`, etc., but not static — they come from Swift)

This fork is symmetrical with existing Keychain/libproc/FFmpeg bypasses. The "no-fork" principle is preserved at the level it cares about (React, pipeline, methodology).

### Why not now

Three blockers, all checkable post-alpha:

1. **`.nonPersistent()` + custom scheme crash on macOS 26** (per `desktop/CLAUDE.md` gotcha list). Tester is on 26.1 (build 25B78). Need to re-test the gotcha on 26.1 before assuming it still applies — the WebKit team fixed several `WKURLSchemeHandler` regressions through 26.x betas. Spike: build a 30-line throwaway target with custom scheme + `.nonPersistent()` + a `<script>`, confirm whether it crashes.
2. **macOS deployment-target test matrix.** WKURLSchemeHandler has been available since macOS 10.13 (8 years), so the API itself is fine. But behaviour under sandbox + `.nonPersistent()` may differ across macOS 15, 16, …, 25, 26.0, 26.1+. Need a test matrix; possibly support `.nonPersistent()` only on 26.1+ and use a different ephemeral strategy on older OSes, or fall back to localhost on broken versions.
3. **Per-project ephemeral isolation.** Currently each project gets `WKWebsiteDataStore.nonPersistent()` for cookie/sessionStorage isolation. If `.nonPersistent()` + custom scheme is genuinely incompatible on some macOS version, we'd need either: (a) accept persistent stores with manual scoping, or (b) keep localhost on broken versions, custom scheme on others.

### Reference implementations

- **Tauri** (Rust + WKWebView) — ships Mac App Store, uses custom scheme handler. Source: `tauri-runtime-wry/src/webview.rs` for the Apple-platform handler.
- **Apache Cordova-iOS** — migrated *from* localhost server *to* `WKURLSchemeHandler` in PR #781 (2019). Same problem space.
- **Readium swift-toolkit** — Issue #117 captures the same trade-off discussion.

## Deployment-target implications of Plan B

Question: "If we did Plan B, would we only work on macOS 15 and macOS 26.1+?"

Honest answer: **don't know without the spike.** The shape of the answer:

- **API availability:** WKURLSchemeHandler exists on macOS 10.13+. No deployment-target lift needed.
- **Behavioural reliability:** WebKit on 26.0 had multiple `WKURLSchemeHandler` regressions, fixed through 26.x. macOS 15 and 16 (et al.) have the API working in production for years (Tauri, Cordova, Capacitor are all evidence).
- **Specific gotcha (`.nonPersistent()` crash):** observed on early 26. Need 30-min re-test on 26.1 to know if it's fixed there.

Three plausible outcomes from the spike:

- **Best case:** crash is fixed in 26.1, pattern works on macOS 15+ and 26.1+. Just skip 26.0. Document 26.0 as "use 26.1 update or fall back to localhost."
- **Middle case:** `.nonPersistent()` is broken on all macOS 26 but works on 15. Either keep `.nonPersistent()` only on 15, or migrate the per-project isolation strategy off `.nonPersistent()` entirely (use one persistent store with manual partitioning).
- **Worst case:** the pattern is unreliable enough that Plan A becomes the long-term answer too. Custom file handler in Python serves Desktop fine; we just live with the architectural ick.

Until the spike runs, "macOS 26.1+ only" is a worst-case framing that may not be necessary.

## Decision recommendation

1. **Alpha:** Plan A *plus* the upstream `mimetypes.knownfiles = []` patch in `bristlenose/__init__.py`. Both are required — the custom request handler alone (`40e78bf`) was insufficient until the upstream patch landed (`768f9a4`). End-to-end verified under sandbox-on Debug 6 May 2026.
2. **Post-alpha (week of TestFlight cohort feedback):** 30-min `.nonPersistent()` + custom-scheme spike on 26.1. Decides whether Plan B is even on the table.
3. **If Plan B viable:** narrow branch implementing WKURLSchemeHandler for desktop only, with deployment-target gating if needed. ~1 week incl. test matrix.
4. **If Plan B not viable on broad macOS range:** stay on Plan A indefinitely. Revisit if Apple ships a bigger fix in 26.x or 27.

## Triggers for moving from A to B

Adopt Plan B if any of:

- Apple deprecates the localhost-on-WKWebView pattern (no signal of this)
- Multiple TestFlight cohort users report sandbox-related serving issues we patch around in Plan A
- A 100days iteration touches WebView lifecycle anyway (e.g. Background Assets work) and the cost of also-doing Plan B is small
- We hit a sandbox limitation Plan A can't fix (e.g. some other syscall blocked)

Stay on Plan A if:

- Plan A holds up across macOS 15-27 with no new sandbox blockers
- Spike confirms `.nonPersistent()` + custom scheme is still flaky in current macOS
- The 50 Swift lines aren't trivial to maintain alongside the Python path

## Cross-references

- `docs/design-modularity.md` — no-fork principle, what ships where
- `desktop/CLAUDE.md` — WKWebView gotchas, sandbox iteration playbook
- `docs/design-wkwebview-messaging.md` — `.nonPersistent()` rules, BroadcastChannel constraint
- WebKit bugs: 296698, 188358, 201180, 191362 — historical `WKURLSchemeHandler` issues

Established 5 May 2026 during Track B walkthrough. Re-evaluate at first TestFlight cohort feedback checkpoint.
