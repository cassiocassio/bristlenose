# Desktop debug: SQLAdmin panel as a beta-only affordance

*Plan for exposing the SQLAdmin database browser (`/admin`) via the macOS Debug
menu in TestFlight and direct betas, while keeping it out of the shipping App
Store release.*

Status: **planned, not built** (14 Jul 2026).

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

## The core seam — a distribution-channel check

`#if DEBUG` is stripped from **both** TestFlight and App Store archives (both
are Release config — see [`BuildInfo.swift:15`](../desktop/Bristlenose/Bristlenose/BuildInfo.swift)),
so it can't express "beta yes, final no." That needs a **runtime** channel
check — the standard Apple receipt idiom, which does not yet exist in the tree
(grep confirms zero `appStoreReceiptURL` / `sandboxReceipt` usage).

New file `desktop/Bristlenose/Bristlenose/DistributionChannel.swift`:

```swift
enum DistributionChannel {
    case debug         // local Xcode build (#if DEBUG)
    case developerID   // notarised direct .dmg beta (no MAS receipt)
    case testFlight    // sandboxReceipt present
    case appStore      // production receipt present

    static let current: DistributionChannel = {
        #if DEBUG
        return .debug
        #else
        guard let url = Bundle.main.appStoreReceiptURL,
              FileManager.default.fileExists(atPath: url.path) else { return .developerID }
        return url.lastPathComponent == "sandboxReceipt" ? .testFlight : .appStore
        #endif
    }()

    /// Debug tools show everywhere EXCEPT the shipping App Store build.
    var exposesDebugTools: Bool { self != .appStore }
}
```

This covers "TestFlight **and other betas**": `.developerID` catches direct
notarised `.dmg` builds, `.testFlight` catches TF; only `.appStore` returns
false.

> **Acknowledged tension.** This introduces the first real runtime *build-channel
> divergence*, which was previously parked ("the TF branch is a timing hold, not
> a build divergence; no `--test-flight` flag"). This plan reverses that stance
> deliberately, on explicit request — the debugging value is judged worth the
> one narrow divergence. Noting it so the reversal is a decision, not a drift.

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
  flag that sets `can_create/can_edit/can_delete = False` on every `ModelView`.
  On a user call you want to *look* at their data, not fat-finger a `DELETE` on
  their transcripts. Full CRUD stays only for local `serve --dev`.
- **Dependency:** keep `sqladmin` in the `serve` extra (it must ship in the
  bundle for TestFlight to serve it). This settles the earlier retire-vs-keep
  fork in favour of **keep** — it earns its ~3 MB by being a real diagnostic.

## Phase 2 — Swift: set the env var by channel

Where [`BristlenoseShared.swift:158`](../desktop/Bristlenose/Bristlenose/BristlenoseShared.swift:158)
sets `_BRISTLENOSE_DEV_ENDPOINTS` under `#if DEBUG`, add a channel-gated line:

```swift
if DistributionChannel.current.exposesDebugTools {
    env["_BRISTLENOSE_ADMIN_PANEL"] = "1"
}
```

Scope note: this gates **only the admin panel** to betas. The Run Inspector's
`_BRISTLENOSE_DEV_ENDPOINTS` stays `#if DEBUG` unless we separately decide the
inspector is also beta-worthy — not assumed here.

## Phase 3 — Swift: the Debug menu

The current shape at
[`MenuCommands.swift:73`](../desktop/Bristlenose/Bristlenose/MenuCommands.swift:73)
is **not** an inline set of buttons — it's `CommandMenu("Debug") {
DebugMenuContent(...) }`, and both the `CommandMenu` block *and* the
`DebugMenuContent` struct that holds every item (Type Parity, Run Inspector,
Shoal, reveal actions) are wrapped in `#if DEBUG`. So `DebugMenuContent` does
not exist at all in a Release build — and TestFlight is a Release build. The
runtime gate therefore cannot simply wrap the existing struct; it needs a **new
non-DEBUG view** that compiles in Release and embeds the existing DEBUG-only
harness behind an inner `#if DEBUG`:

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

In betas, `/admin` becomes an **unauthenticated-but-localhost-bound, read-only**
view over transcripts + PII. Read-only removes the mutation risk; localhost
binding removes the remote risk; it matches the existing SECURITY.md threat
model (local-process defence-in-depth). In the App Store build the `sqladmin`
dependency still ships in the bundle but the route is never mounted (the env var
is never set in the `.appStore` channel) — code present, endpoint absent.

## Verification

- `bristlenose doctor --self-test` — sidecar already carries `sqladmin`.
- **`.developerID` build** (local notarised): Debug menu present, `/admin`
  opens, panel is read-only. This is the practical local acceptance test, since
  it's a real beta channel and testable without TestFlight.
- **App Store archive**: Debug menu absent, `/admin` returns 404.
- **`.testFlight`** receipt detection can only be truly confirmed on a real
  TestFlight build → add one line to the desktop pre-submission checklist:
  *"confirm Debug menu appears in the TF build and is gone in the App Store
  validation build."*

## Open questions

1. Should the **Run Inspector** (and other `#if DEBUG` diagnostics) also move to
   the `exposesDebugTools` gate, so betas get the full debug surface, not just
   the DB browser? Deferred — this plan is scoped to the admin panel.
2. Should the read-only vs full-CRUD line be `dev`-vs-beta (as planned) or a
   separate opt-in even in dev? Planned split is the safe default.

## Effort

~half a day. Two new Swift files (`DistributionChannel.swift`,
`AdminPanelAction.swift`) plus edits to four existing sites (`app.py`,
`admin.py`, `BristlenoseShared.swift`, `MenuCommands.swift`). Riskiest parts:
Phase 3 — the existing `CommandMenu("Debug")` *and* its `DebugMenuContent`
struct are both `#if DEBUG`, so the refactor must introduce a non-DEBUG wrapper
view (`BetaDebugMenuContent`) that compiles in Release while keeping the
DEBUG-scene items behind an inner `#if DEBUG`; likewise `openAdminPanel` must
move out of the fully-`#if DEBUG` `DebugMenuActions` into a non-DEBUG helper.
And confirming TF-receipt detection, which can only close on a real TestFlight
build. Touches the sidecar, so it needs a rebuild + `doctor --self-test` before
the panel loads in a bundled build.
