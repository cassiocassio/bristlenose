# Diagnostics vs developer tools — sorting debug affordances by audience

*Plan for sorting every debug/dev affordance by **who it's for**: users (understand
their own run), the developer (dig into SQL/internals when something's broken),
or nobody outside the building (fake-state harnesses). Three shipping tiers plus
dev-only, each with its own gate.*

Status: **planned** (14 Jul 2026). Extends
[`design-desktop-debug-admin-panel.md`](design-desktop-debug-admin-panel.md) —
the `DistributionChannel` gating committed there is **kept**, as the gate for the
developer tier (below). This doc adds the separate user-facing tier.

## Why — the axis is audience, not just "ships or not"

- **For the user** — understand *their own* run: what's happening, why it's slow,
  where the logs are. Comprehensible, safe, reassuring to a non-technical
  researcher.
- **For the developer** — dig into the SQL / raw internals when something's
  actually broken. The person driving is *you*, on a call. A raw DB browser is a
  power tool that reads as alarming/incomprehensible to a researcher — "a step
  too far for most users."
- **For nobody outside the building** — fake-state injectors, typography
  harnesses, the branch-name overlay. These actively *mislead* (a synthesized
  "Failed" pill over a project that's fine) and must never ship.

That gives four buckets, three of which can appear in a shipping build:

| Tier | Audience | Gate | Ships to |
|---|---|---|---|
| **A — Always-on** | user | none | every channel |
| **U — User Diagnostics** | user | `showDiagnosticsMenu` preference (off by default) | every channel |
| **V — Developer tools** | developer | `DistributionChannel.exposesDebugTools` (Developer-ID `.dmg` beta + local DEBUG) | beta + dev only, **never** App Store/TestFlight |
| **D — Developer magic** | nobody | `#if DEBUG` / build-time env | dev machines only |

## The sort

### Tier A — always-on
The **About panel** (`orderFrontStandardAboutPanel`) — version + build number in
the title, full provenance tucked in the Credits area (so an About screenshot
already carries enough to disambiguate a build) · `doctor` CLI. The separate
`Build Info…` menu item + `BuildInfoSheet` were **deleted** (14 Jul 2026) —
redundant with the About panel, which is the one home for build detail. Full
copyable provenance is still available via "Copy Build Provenance" in the
Diagnostics menu (Section 1) when a support call needs it.

### Tier U — user diagnostics (ship everywhere, off-by-default preference)
Mostly **native Swift actions** (no sidecar surface). The one exception is Run
Inspector, whose run-introspection endpoints ship in the public binary — they're
`/api/`-token-authed + read-only, but that means they clear at the **App Store**
security bar (Phase 2), not just the beta bar.

| Item | Location today | Change |
|---|---|---|
| Reveal `.bristlenose/` in Finder | `DebugMenuActions.revealInternalDir` | Move to the pref-gated Diagnostics menu |
| Open Log in Console | `DebugMenuActions.openLog` | Same |
| Copy Build Provenance | `DebugMenuActions.copyBuildProvenance` | Same |
| Web Inspector (`isInspectable`) | `WebView.swift:105/576` `#if DEBUG` | `isInspectable = showDiagnosticsMenu`. **NOT a menu item** — there's no public API to open a hosted WKWebView's inspector from a menu command (Safari's ⌥⌘I opens Safari's own). It's a side-effect of the toggle; surface it in the toggle's **helper text** ("…also enables the Web Inspector"), and users right-click ▸ Inspect Element. Per HIG (Menus), menu items are commands only — no instructional rows. |
| **Run Inspector** (understand the run / why slow) | `RunInspectorView.swift` → `run-inspector` window; `/api/dev/*` | **Section 1, ships to everyone** — this is the "understand your run" tool. Endpoints are under `/api/` → already **token-authed + read-only + localhost**. Work (Phase 2): split its endpoints out of `/api/dev/*`, hold back `/api/dev/info` (system info, path-leaky) to devtools-only, and clear the shipped subset via `security-review` for the **App Store** bar (higher than the beta bar). Caveat: current `RunInspectorView` presentation is developer-raw; a friendlier "why was this slow" framing is optional polish, not a blocker. |
| Shoal Screensaver — the animation only | new thin non-DEBUG window hosting `ShoalView(showsDebugControls: false, tuning: ShoalTuning())` (defaults = shipping `ShoalConfig` constants) | Add a pref-gated `shoal-view` window scene showing the animation at defaults, no inspector. **Beta-era, not a permanent user feature** (remove/revisit by GA). Rationale: the point is tester hardware feedback ("is this smooth on your M1/Intel?") — needs **TestFlight reach**, and a benign murmuration is not a §2.1 risk, so the pref is its safe home. Clean split confirmed: `ShoalView` already parametrises `showsDebugControls`, so the animation detaches from the tuning UI without refactor. |

### Tier V — developer tools (Section 2; Developer-ID `.dmg` beta only)
These appear as **Section 2 of the single Diagnostics menu**, only on builds
where `exposesDebugTools` is true (`.dmg` beta + local DEBUG). Reachable by the
developer on a fragile-alpha screen-share with a cohort tester (all on-machine,
no egress — better than emailing a PII-bearing DB file). The alpha cohort is
5–10 trusted UR-veteran peers, so a devtools section on their beta build is
acceptable; the App Store / GA public never sees Section 2.

| Item | Location today | Change |
|---|---|---|
| Open Admin Panel (read-only SQL browser) | `AdminPanelAction.swift`, `admin.py`, `app.py` | Keep committed `DistributionChannel` gating; Section 2, NOT the user section |
| Shoal **tuning controls** (sliders/presets/FPS probe) | `ShoalDebugView.swift` (`shoal` window), currently `#if DEBUG` | Promote `#if DEBUG` → `exposesDebugTools` (Section 2), so the cohort can play with the feel on the `.dmg` beta. Technically low-risk (self-contained SwiftUI, no network/data/PII), but the FPS-counter + sliders read as debug tooling → keep OUT of Section 1 (App Store §2.1). `/api/dev/info` (system info, path-leaky) also lives here. |

### Tier D — developer magic (never ships; `#if DEBUG` / build-time env)

| Affordance | Why D |
|---|---|
| Type Parity Inspector (`type-parity` window, `TypeParity*.swift`) | Internal typography QA |
| Diagnostic fixtures ▸ selected project (`DiagnosticFixture.swift`) | **Injects fake pipeline states** — actively misleads |
| Cycle Ollama pill / pill state harness (`OllamaDownloadModel.DebugScene`) | Fake-state harness |
| BuildInfo footer overlay (branch/SHA over report) | "Leaks branch names, looks unprofessional" (own note in `BuildInfo.swift`) |
| `BRISTLENOSE_DEBUG_500`, `_FAKE_THUMBNAILS`, `_DEBUG_DIAGNOSTIC_FIXTURE`, `_DEBUG_OLLAMA_PHASE`, `_DEBUG_OLLAMA_TAG` | QA env seeds / internals leaks |
| `BRISTLENOSE_DEV` / `_DEV_SIDECAR_PATH` / `_DEV_EXTERNAL_PORT`; Python `--dev` **playground**; dev **telemetry test-stub** (`/api/dev/telemetry`) | Build/dev plumbing + contributor test infra |

## One menu, contents gated by build

There is **one** `CommandMenu("Diagnostics")`, shown when the preference is on.
Its item list is the union of the sections this build qualifies for — the
gates *compound inside the single menu*, they don't spawn a second menu:

```swift
if showDiagnosticsMenu {
    CommandMenu("Diagnostics") {
        // Section 1 — benign, every channel ("cute things")
        DiagnosticsUserItems(...)              // Run Inspector, Reveal, Open Log,
                                               // Copy Provenance, Shoal animation
                                               // (Web Inspector = toggle side-effect,
                                               //  not a menu item — see below)

        if DistributionChannel.current.exposesDebugTools {
            Divider()
            // Section 2 — Apple-review-unfriendly devtools (.dmg beta + DEBUG)
            DiagnosticsDevToolsItems(...)      // Open Admin Panel (SQL), Shoal tuning
        }

        #if DEBUG
        Divider()
        // Section 3 — full-fat harness, dev machines only
        DiagnosticsHarnessItems(...)           // fake-state injectors, Type Parity,
                                               // Ollama pill
        #endif
    }
}
```

What you see, by build (toggle on):

| Build | Section 1 (cute) | Section 2 (devtools) | Section 3 (harness) |
|---|---|---|---|
| App Store / TestFlight | ✓ Run Inspector, Reveal, Log, Provenance, Shoal animation (+ Web Inspector enabled ambiently) | — | — |
| Developer-ID `.dmg` beta | ✓ | ✓ SQL browser, Shoal tuning, `/dev/info` | — |
| Local `#if DEBUG` | ✓ | ✓ | ✓ fake-state injectors, Type Parity, Ollama pill |

The App-Store constraint holds automatically: a reviewer who flips the toggle
gets Section 1 only — the SQL browser is `exposesDebugTools`-gated inside the
menu, so it cannot appear on their build. Toggle off → no menu at all, every
channel.

## Mechanism

**The preference** — Safari's pattern, one switch:
- `@AppStorage("showDiagnosticsMenu")`, default `false`, a single toggle in the
  **Appearance** settings tab (alongside the existing random-project-icons
  toggle — no new tab). Helper text: "…also enables the Web Inspector" (that's
  where Web Inspector is disclosed — it's not a menu item). Ships in every
  channel; disclosed + off-by-default is App-Store-legal (§2.3.1 targets
  *hidden / dormant / auto-activating* features — a visible user toggle is none
  of those).
- **HIG discipline (verified against Menus, DocC).** Menu items are *commands*
  only — a verb/verb-phrase label, optional symbol, optional keyboard shortcut,
  optional checkmark state, optional submenu chevron. No instructional text
  rows. Unavailable commands **dim** (e.g. "Open Admin Panel…" when no project
  is served); separators group the three sections; submenus stay one level,
  ≤~5 items.
- Optional nicety: default it **on** under `#if DEBUG` only (dev convenience),
  off in every Release. One `#if DEBUG` around the `@AppStorage` default.

**Section-2/3 gates** — already exist, composed *inside* the menu: Section 2 is
`DistributionChannel.exposesDebugTools` (the committed gate); Section 3 is
`#if DEBUG`. No new gating primitive.

**Python devtools env** — the SQL admin + run-introspection endpoints mount on
`_BRISTLENOSE_DEVTOOLS=1`, set by `childEnvironment` whenever `exposesDebugTools`
(channel-based, independent of the pref — so the endpoint is ready if the user
later flips the toggle; the *menu item* to reach it is what the pref gates).
Renamed from `_BRISTLENOSE_ADMIN_PANEL` to cover both endpoints after the
Phase-2 split. Never set on App Store / TestFlight.

## Phases

**Phase 1 — the single Diagnostics menu. Pure Swift, no Python.**
- Add the `showDiagnosticsMenu` toggle to the **Appearance** settings tab.
- Rename/rework the committed `BetaDebugMenuContent` → `DiagnosticsMenuContent`,
  now pref-gated (`if showDiagnosticsMenu { CommandMenu("Diagnostics") { … } }`)
  with the three compounding sections:
  - **Section 1** (always): Reveal `.bristlenose/`, Open Log, Copy Provenance,
    Web Inspector toggle, Shoal animation (new `shoal-view` scene).
  - **Section 2** (`exposesDebugTools`): the committed "Open Admin Panel" item.
  - **Section 3** (`#if DEBUG`): the existing harness (`DebugMenuContent` —
    Type Parity, fixtures, Shoal tuning, Ollama pill), unchanged, folded in.
- Move Reveal/Open-Log/Copy-Provenance **out** of the `#if DEBUG`
  `DebugMenuActions` file so they compile in Release (re-guard only the D
  members, or split the file).
- Gate Web Inspector on the pref (`isInspectable = showDiagnosticsMenu`).
- Add the `shoal-view` window scene (non-DEBUG, `showsDebugControls: false`).
- Delete the standalone `#if DEBUG CommandMenu("Debug")` — it's now Section 3
  inside the single Diagnostics menu.
- Confirm live menu-toggle in `Commands` works; fall back to "applies on next
  launch" if `@AppStorage` doesn't re-evaluate menu presence (see risk 1).

**Phase 2 — split `/api/dev/*`; promote Run Inspector to Section 1 (everyone).**
Three-way split of `routes/dev.py`:
- **Run-introspection → ships to every channel.** `/run.json`, `/run`,
  `/sessions-table-html` → `routes/diagnostics.py`, mounted **unconditionally**
  (they're `/api/`-prefixed → token-authed, read-only, over the user's own run
  data — same posture as the report). Verify the `/api/dev/*` → `/api/` prefix so
  the bearer-auth actually covers them.
- **`/info` (system info, path-leaky) → devtools only.** Stays gated on
  `_BRISTLENOSE_DEVTOOLS` (Section 2), NOT shipped to App Store.
- **Playground + telemetry stub → stay `#if DEBUG` / `--dev`.**
- Move the `run-inspector` window scene + menu item from `#if DEBUG` to
  **Section 1** (always, pref-gated). Move Shoal tuning (`ShoalDebugView` +
  `shoal` window) from `#if DEBUG` to **Section 2** (`exposesDebugTools`).
- Rename `_BRISTLENOSE_ADMIN_PANEL` → `_BRISTLENOSE_DEVTOOLS` (now gates SQL
  admin + `/info`).
- **`security-review` pass required — at the App Store bar, not just beta.** The
  run-introspection router now ships in the *public* binary. Confirm: `/api/`
  bearer-auth actually covers it, read-only only, no path/env/PII leakage in the
  payloads, and no telemetry/write/playground surface leaked across the split.
  This is the gate that decides whether Run-Inspector-for-everyone actually
  clears — if the payloads can't be made App-Store-clean, fall back to Section 2.

**Phase 3 — reorder `_ADMIN_VIEWS` + lock the D boundary.**
- Reorder `_ADMIN_VIEWS` so a non-PII table (`ImportConflict` / `Session`) is the
  landing view, not `Person` (carried from the admin-panel security review).
- Confirm every Tier-D affordance is absent from a Release archive
  (`check-release-binary.sh` + manual archive check); add the `BRISTLENOSE_DEBUG_*`
  literals to the scan if not covered.
- SECURITY.md paragraph scoping the two tiers (user pref vs developer beta gate).

## Implementation risks / open questions

1. **Live menu toggle in SwiftUI `Commands` is finicky.** `@AppStorage` may not
   re-evaluate menu *presence* on change (same weakness that forces the
   View-inside-Commands pattern). Fallback: "applies on next launch"
   (Safari-acceptable; appearance/language prefs already restart). Confirm live
   first.
2. ~~Advanced tab vs a row under Appearance.~~ **Resolved:** a single toggle in
   the **Appearance** tab (next to random-project-icons) — no new tab.
3. **`DEVELOPER_ID_BETA` still needs wiring** into the `.dmg` build config
   (`SWIFT_ACTIVE_COMPILATION_CONDITIONS`) for Tier V to light up on the beta —
   the outstanding build-side task from the admin-panel doc, unchanged.
4. **Run Inspector presentation polish.** Run Inspector *is* the
   understand-your-run tool for everyone (Section 1), but the current
   `RunInspectorView` is developer-raw. Shipping it as-is is fine for alpha; a
   friendlier "why was this slow" framing for App Store users is optional
   follow-up, not a blocker. The gate that actually decides Section-1-vs-2 is
   the Phase-2 security pass on its payloads (App Store bar).

## Relationship to committed work (`3a69b170`)

- `DistributionChannel.swift`, `AdminPanelAction.swift`, the Python read-only
  mount — **kept** (they realise Section 2 / Tier V). The committed
  `BetaDebugMenuContent` struct is **renamed/reworked** into
  `DiagnosticsMenuContent` (one menu, three sections) in Phase 1 — the
  channel-gate logic inside it is reused verbatim as the Section-2 condition.
- Net-new here: the Tier-U `showDiagnosticsMenu` preference + Diagnostics menu
  (Phase 1), and the `/api/dev/*` split + Run Inspector promotion (Phase 2).
- Rename only: `_BRISTLENOSE_ADMIN_PANEL` → `_BRISTLENOSE_DEVTOOLS` (Phase 2).
