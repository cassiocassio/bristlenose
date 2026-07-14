# Desktop debug: SQLAdmin panel as a beta-only affordance

*Plan for exposing the SQLAdmin database browser (`/admin`) via the macOS Debug
menu in TestFlight and direct betas, while keeping it out of the shipping App
Store release.*

Status: **implemented** (14 Jul 2026). Python + Swift landed; needs an Xcode
build + `doctor --self-test` and a real TestFlight build to close TF-receipt
detection (see Verification). Files: `DistributionChannel.swift`,
`AdminPanelAction.swift` (both new), edits to `MenuCommands.swift`,
`BristlenoseShared.swift`, `bristlenose/server/app.py`,
`bristlenose/server/admin.py`; tests in `tests/test_serve_admin_panel.py`.

## Why

If we ever do even one piece of useful debugging on a call with a cohort user —
"share your screen, let me look at what's actually in your database" — a live
DB browser pays for itself. Today that's impossible on a shipped build: the
SQLAdmin panel is gated behind full HMR dev mode (`if dev:` in
[`app.py`](../bristlenose/server/app.py)), which is unreachable in any bundled
sidecar. The panel exists, it's just walled off from the one context where it'd
help.

The goal is narrow: make `/admin` reachable from the **Debug menu** in
TestFlight + direct-notarised betas, **absent from the App Store final build**,
read-only, and needing no new dependency (SQLAdmin already ships in the `serve`
extra).

## This is not a code fork — it's shared Python + native chrome

Worth stating up front, because it's the obvious "are we drifting from the
single-codebase contract?" question.

The admin panel **is** shared Python — it lives in the serve layer that CLI and
macOS both run, unchanged. Per [`design-modularity.md`](design-modularity.md)
(the no-fork contract): *"Prefer macOS-native mechanisms… layer macOS chrome on
top"* and *"the same Python code path"* across channels.

The CLI already has its affordance for this exact endpoint: `_print_dev_urls()`
([`app.py:378`](../bristlenose/server/app.py:378)) prints
`Database browser: …/admin/` as a Cmd-clickable line. So the panel is one
shared Python feature with **two native launchers**:

| Channel | Launcher for the *same* `/admin` endpoint |
|---|---|
| CLI | Cmd-clickable URL in `serve` terminal output |
| macOS | "Open Admin Panel…" Debug-menu item |

The mount gate (below) is a Python env var, so the CLI can flip it too — parity
is preserved, nothing is reimplemented natively. The only native code is a menu
item that opens a URL. That's chrome, not a fork.

## The core seam — a compile-time channel flag (NOT a receipt check)

`#if DEBUG` is stripped from **both** TestFlight and App Store archives (both
are Release config — see [`BuildInfo.swift`](../desktop/Bristlenose/Bristlenose/BuildInfo.swift)),
so it can't express "beta yes, final no" on its own.

> **Why not the Apple receipt idiom (the original plan — rejected after review).**
> The first draft used `Bundle.main.appStoreReceiptURL` + a
> `lastPathComponent == "sandboxReceipt"` check to return `.testFlight` vs
> `.appStore`. Both the `app-store-police` and `security-review` passes killed
> it: **App Review runs under the StoreKit *sandbox*, so the reviewer's build
> presents a `sandboxReceipt` — identical to TestFlight.** The receipt check
> would classify the reviewer as `.testFlight`, expose the "Debug" menu + raw
> PII browser to them, and earn a probable Guideline 2.1 rejection. It also
> *failed open*: a missing/late receipt fell through to `.developerID`, which
> also exposed. You cannot safely distinguish a TestFlight tester from an App
> Store reviewer at runtime — both are sandbox receipts.
>
> **Decision (14 Jul 2026):** scope the panel to the **Developer-ID `.dmg`
> beta channel only**, identified by a *positive build-time flag we control*,
> and keep it out of **every** App Store *and* TestFlight archive. TestFlight
> exposure is dropped — the "debug a TF tester's DB on a call" case is not
> worth the submission risk.

New file `desktop/Bristlenose/Bristlenose/DistributionChannel.swift`:

```swift
enum DistributionChannel {
    case debug                 // local Xcode build (#if DEBUG)
    case developerID           // direct notarised .dmg beta (DEVELOPER_ID_BETA flag)
    case appStoreOrTestFlight  // Release without the beta flag — App Store OR TestFlight

    static let current: DistributionChannel = {
        #if DEBUG
        return .debug
        #elseif DEVELOPER_ID_BETA
        return .developerID
        #else
        return .appStoreOrTestFlight
        #endif
    }()

    /// Debug tools show ONLY in local dev and the Developer-ID beta.
    var exposesDebugTools: Bool {
        switch self {
        case .debug, .developerID: return true
        case .appStoreOrTestFlight: return false
        }
    }
}
```

**Fail-closed by construction.** The App Store / TestFlight path is the `#else`
default, so the absence of the positive `DEVELOPER_ID_BETA` marker hides the
tools — no runtime state (missing receipt, sandbox quirk) can flip it open.
There is zero receipt logic in the tree.

**Wiring the beta channel (build-config task, not code):** set
`SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEVELOPER_ID_BETA` in the Developer-ID
`.dmg` build configuration **only** — never in the App Store / TestFlight
archive config. Until that config exists the panel is dormant everywhere except
local `#if DEBUG` builds, which is the safe state. This is the only remaining
open build-side task; the Swift/Python code is complete.

> **Resolved tension.** The original plan introduced a runtime *build-channel
> divergence* (previously parked: "the TF branch is a timing hold, not a build
> divergence; no `--test-flight` flag"). The reviewed design narrows that to a
> single **compile-time** flag scoped to the Developer-ID beta — App Store and
> TestFlight archives are byte-identical to each other w.r.t. this feature
> (neither defines the flag), so the "no TF/AppStore divergence" stance is in
> fact *preserved*; only the separate `.dmg` beta pipeline diverges.

## Phase 1 — Python: decouple the mount from full `dev`

Today [`app.py:234`](../bristlenose/server/app.py:234) mounts SQLAdmin only
under full HMR `dev`. Add an independent env gate so a bundled (non-HMR) sidecar
can serve it:

```python
_admin_enabled = dev or os.environ.get("_BRISTLENOSE_ADMIN_PANEL") == "1"
if _admin_enabled:
    from sqladmin import Admin as SQLAdmin
    from bristlenose.server.admin import register_admin_views
    sqladmin_app = SQLAdmin(app, engine, base_url="/admin")
    register_admin_views(sqladmin_app, read_only=not dev)
```

- `serve --dev` (browser, contributor) keeps full CRUD via the `dev` arm.
- **Read-only when beta-exposed.** `register_admin_views` grows a `read_only`
  flag that sets `can_create/can_edit/can_delete = False` **and `can_export =
  False`** on every `ModelView`. On a user call you want to *look* at their
  data, not fat-finger a `DELETE` on their transcripts. The `can_export` half
  is load-bearing per the `security-review` pass: SQLAdmin's
  `/{identity}/export/csv` is an **unauthenticated GET that dumps a whole table
  unbounded** — leaving it on would let read-only `/admin` exfiltrate the full
  transcript + `Person` tables in one request. Full CRUD + export stays only
  for local `serve --dev`. (Mutation is enforced at the HTTP layer — SQLAdmin's
  create/edit/delete routes raise 403 when the flag is off, not just a hidden
  button.)
- **Dependency:** keep `sqladmin` in the `serve` extra (it must ship in the
  bundle for the beta to serve it). This settles the earlier retire-vs-keep
  fork in favour of **keep** — it earns its ~3 MB by being a real diagnostic.
  (Shipping it in the App Store bundle with the route never mounted is *not* a
  review risk — unused dependency code is fine; per `app-store-police`.)

## Phase 2 — Swift: set the env var by channel

Where [`BristlenoseShared.swift:158`](../desktop/Bristlenose/Bristlenose/BristlenoseShared.swift:158)
sets `_BRISTLENOSE_DEV_ENDPOINTS` under `#if DEBUG`, add a channel-gated line:

```swift
if DistributionChannel.current.exposesDebugTools {
    env["_BRISTLENOSE_ADMIN_PANEL"] = "1"
}
```

Scope note: this gates **only the admin panel** to the Developer-ID beta. The
Run Inspector's `_BRISTLENOSE_DEV_ENDPOINTS` stays `#if DEBUG` unless we
separately decide the inspector is also beta-worthy — not assumed here. Because
`exposesDebugTools` is compile-time (App Store / TestFlight → `false`), the env
var is simply never set in those archives.

## Phase 3 — Swift: the Debug menu

The current shape at
[`MenuCommands.swift:73`](../desktop/Bristlenose/Bristlenose/MenuCommands.swift:73)
is **not** an inline set of buttons — it's `CommandMenu("Debug") {
DebugMenuContent(...) }`, and both the `CommandMenu` block *and* the
`DebugMenuContent` struct that holds every item (Type Parity, Run Inspector,
Shoal, reveal actions) are wrapped in `#if DEBUG`. So `DebugMenuContent` does
not exist at all in a Release build — and the Developer-ID `.dmg` beta is a
Release build. The channel gate therefore cannot simply wrap the existing
struct; it needs a **new non-DEBUG view** that compiles in Release and embeds
the existing DEBUG-only harness behind an inner `#if DEBUG`:

```swift
// MenuCommands.swift — replace the #if DEBUG CommandMenu block with:
if DistributionChannel.current.exposesDebugTools {
    CommandMenu("Debug") {
        BetaDebugMenuContent(ollamaDownload: ollamaDownload,
                             serveManager: serveManager)
    }
}

// New non-DEBUG view (compiles in Release):
private struct BetaDebugMenuContent: View {
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    @ObservedObject var serveManager: ServeManager

    var body: some View {
        Button("Open Admin Panel…") {
            AdminPanelAction.open(serveManager: serveManager)
        }
        .disabled(serveManager.runningPort == nil)
        #if DEBUG
        Divider()
        // The existing DEBUG-only harness, unchanged — Type Parity, Run
        // Inspector, Shoal, reveal actions all open #if DEBUG window scenes,
        // so they stay compiled out of Release even inside this runtime menu.
        DebugMenuContent(ollamaDownload: ollamaDownload, serveManager: serveManager)
        #endif
    }
}
```

Why "Open Admin Panel…" is the right *first* beta-safe item: it opens an
**external browser**, so it needs no `#if DEBUG` SwiftUI window scene (unlike
Run Inspector / Type Parity, whose scenes are DEBUG-only). It composes cleanly.

## Phase 4 — the action

`DebugMenuActions` ([`DebugMenuActions.swift`](../desktop/Bristlenose/Bristlenose/DebugMenuActions.swift))
is **itself entirely `#if DEBUG`** (the whole file, lines 1–87). So
`openAdminPanel` cannot live there — it would be absent in the Release/TestFlight
build that needs it. Put it in a **new non-DEBUG helper**, e.g.
`AdminPanelAction`:

```swift
// New file, no #if DEBUG guard — must compile in Release:
@MainActor
enum AdminPanelAction {
    static func open(serveManager: ServeManager) {
        guard let port = serveManager.runningPort else { return }
        NSWorkspace.shared.open(URL(string: "http://127.0.0.1:\(port)/admin/")!)
    }
}
```

Note the port property is `runningPort`
([`ServeManager.swift:109`](../desktop/Bristlenose/Bristlenose/ServeManager.swift:109)),
not `servedPort` (which does not exist).

**No auth token needed.** `/admin` is *not* under `/api/`, so it is not behind
`BearerTokenMiddleware` ([`middleware.py`](../bristlenose/server/middleware.py)
guards only the `/api/` prefix). Localhost-binding is its sole protection —
which is consistent with `SECURITY.md`'s framing of the token as
defence-in-depth, not an auth boundary. Guard against "no project served yet"
via the `.disabled(serveManager.runningPort == nil)` modifier above.

## Security posture

In the Developer-ID beta, `/admin` becomes an
**unauthenticated-but-localhost-bound, read-only** view over transcripts + PII.
Read-only (incl. `can_export=False`) removes the mutation *and* bulk-exfil risk;
localhost binding removes the remote risk; it matches the existing SECURITY.md
threat model (local-process defence-in-depth — the bearer token is a
defence-in-depth speed bump, not the boundary; `/report/*` and `/media/*` are
already exempt for the same reason). In the App Store *and* TestFlight builds
the `sqladmin` dependency still ships in the bundle but the route is never
mounted (the env var is never set in the `.appStoreOrTestFlight` channel) — code
present, endpoint absent.

Two follow-ups the `security-review` pass flagged for the pre-submission SIG
story (not code blockers):

- **SECURITY.md paragraph** scoping `/admin` (beta-channel-only, read-only,
  unauthenticated by the same defence-in-depth rationale as `/report/*`, never
  mounted in App Store/TestFlight builds) — so the "why is one data endpoint
  unauthenticated?" question is an *explained* decision.
- **Support-runbook note + non-PII landing view.** The intended use (screen-
  share the DB on a cohort call) funnels a maintainer's eyes onto the most
  re-identifying tables (`Person.full_name`, raw `TranscriptSegment.text` —
  past the p1/p2 anonymisation boundary). Everything shown is already plaintext
  on the researcher's own machine (no new egress, Level 0 of the consent
  gradient), but the runbook should steer diagnostic calls toward structural
  tables (`ImportConflict`, `Session` counts), and `_ADMIN_VIEWS` could be
  ordered so a non-PII table is the landing view rather than `Person`.

## Verification

Python side (done, automated): `tests/test_serve_admin_panel.py` pins the mount
gate (absent with no env/no dev; present under the env gate; present under
`dev`) and the read-only flag (`can_create/edit/delete/export = False`, and that
the flags don't leak across calls).

Swift + build side (needs Xcode / a real build):

- `bristlenose doctor --self-test` — sidecar already carries `sqladmin`.
- **Local `#if DEBUG` build** (Cmd+R): Debug menu present, "Open Admin Panel…"
  opens `/admin`, panel is read-only. This is the practical acceptance test —
  no receipt or channel plumbing needed, `.debug` exposes.
- **Developer-ID `.dmg` beta** (once `DEVELOPER_ID_BETA` is wired into that
  build config): Debug menu present, `/admin` read-only. This is the shipping
  beta path.
- **App Store *and* TestFlight archives**: Debug menu absent, `/admin` returns
  404 — because neither defines `DEVELOPER_ID_BETA`, so `exposesDebugTools`
  is a compile-time `false`. No receipt build needed to confirm; it's static.
- Pre-submission checklist line: *"confirm the App Store / TestFlight archive
  has no Debug menu and `/admin` 404s; confirm the Developer-ID .dmg beta shows
  it read-only."*

## Remaining work

- **Wire `DEVELOPER_ID_BETA`** into the Developer-ID `.dmg` build configuration
  (`SWIFT_ACTIVE_COMPILATION_CONDITIONS`), and confirm no App Store / TestFlight
  config defines it. Until then the panel is dormant outside local DEBUG (safe).
- **Xcode build + sidecar rebuild** (`doctor --self-test`) — the Python change
  ships in the sidecar, so a bundled build needs a rebuild before `/admin` loads.
- **SECURITY.md paragraph + support-runbook note** (see Security posture).

## Open questions

1. Should the **Run Inspector** (and other `#if DEBUG` diagnostics) also move to
   the `exposesDebugTools` gate, so the Developer-ID beta gets the full debug
   surface, not just the DB browser? Deferred — this plan is scoped to the
   admin panel.
2. Should the read-only vs full-CRUD line be `dev`-vs-beta (as built) or a
   separate opt-in even in dev? Built split is the safe default.

## Effort

Landed in ~half a day. Two new Swift files (`DistributionChannel.swift`,
`AdminPanelAction.swift`) + edits to four existing sites (`app.py`, `admin.py`,
`BristlenoseShared.swift`, `MenuCommands.swift`) + `tests/test_serve_admin_panel.py`.
The trickiest part was Phase 3 — the existing `CommandMenu("Debug")` *and* its
`DebugMenuContent` struct are both `#if DEBUG`, so the refactor introduced a
non-DEBUG wrapper view (`BetaDebugMenuContent`) that compiles in Release while
keeping the DEBUG-scene items behind an inner `#if DEBUG`; `openAdminPanel`
likewise moved out of the fully-`#if DEBUG` `DebugMenuActions` into the new
non-DEBUG `AdminPanelAction`. The receipt-based channel detection in the first
draft was dropped after review (see the core-seam section) in favour of the
compile-time flag — which removed the "confirm on a real TestFlight build"
uncertainty entirely.
