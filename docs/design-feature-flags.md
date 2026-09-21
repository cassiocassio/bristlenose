---
status: current
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20 (5d42f031)
---

# Feature flags, build gates and mode switches — how each codebase gates a feature

*There is no single flag system. There are five mechanisms across three
codebases, and each answers a different question. Picking the wrong one is
the common mistake: a build gate used to park a half-finished feature, or a
runtime flag used to hide something that must never reach an App Store
reviewer. This doc records what exists, what each is for, and what verifies
it.*

## Changelog

- _2026-09-20_ — first version. Written the day the proposed-badge rationale
  tooltip became the third parked frontend feature (`5d42f031`), when the
  question "how do we do this on the other side?" had no written answer.

## TL;DR — pick by the question the gate answers

| The question | Mechanism | Codebase | Where |
|---|---|---|---|
| Is this feature **finished enough to show**? | Parked-feature flag | React SPA | `frontend/src/utils/featureFlags.ts` |
| **Which build** is this — dev, `.dmg` beta, App Store? | Compile-time condition | Swift | `#if DEBUG`, `DistributionChannel` |
| **Who is hosting me** — CLI, desktop, export, Vite? | Runtime mode detection | Python + SPA | `_BRISTLENOSE_*` env, `isEmbedded()`, `isExportMode()`, `isDesktop()` |
| Can I **fake a state** for QA on this machine? | Debug seed env var | Python + Swift | `BRISTLENOSE_DEBUG_*`, `BRISTLENOSE_FAKE_THUMBNAILS` |
| Does the user want this **diagnostic surface**? | User preference | Swift | `DiagnosticsPreference` |

Two things that look like flags and are not: a **hidden CLI option**
(`hidden=True`) is a compatibility or retirement gate, and a **configured but
unimplemented setting** is refused, not silently ignored. Both are at the end.

Python has **no parked-feature flag mechanism** today. If one is needed, the
shape to copy is the frontend one; see § "When the mechanism doesn't exist
yet".

## 1. Parked-feature flags — React SPA only

**File:** `frontend/src/utils/featureFlags.ts`. A typed object with three
booleans, all `false` in `DEFAULTS`, exported mutable so tests can flip them,
with `resetFeatureFlags()` to restore.

**What it means.** A flag here says the feature is *built, tested and
documented* but the interaction isn't good enough to ship, so the affordance
is withheld while the code, tests and rationale stay in the tree. The module
header states the three rules and they are the whole contract:

1. **Flags gate the affordance, not the code.** Everything behind a flag still
   compiles, type-checks and has passing tests. The server endpoint, the API
   helper, the store field, the locale strings and the export embed key all
   stay live. Only the client reveal is withheld.
2. **Each flag names its design doc**, and the doc carries the parked banner
   and the open questions that must be answered before the flag flips.
3. **Flipping a flag on is a design decision, not a cleanup.** If a revisit
   concludes the feature isn't worth finishing, delete the feature and the
   flag together in one commit.

**The three flags as of 20 Sep 2026:**

| Flag | Parked | Design doc | Why |
|---|---|---|---|
| `quoteContextExpansion` | 5 Aug 2026 | `design-quote-context-expansion.md` | chevrons read as decoration; expansion is one-way |
| `moderatorQuestionPill` | 5 Aug 2026 | `design-moderator-question-pill.md` | hover target is an unmarked zone |
| `proposalRationaleTooltip` | 20 Sep 2026 | `design-autocode.md` § Parked | lands over the next row and is z-index-clipped; the rationale text is verbose and restates the tag |

**Test discipline — this is what keeps a parked feature from rotting.** Two
shapes are in use; both are required, in the same file:

- **Flag forced on** for the tests that specify the parked behaviour.
  `QuoteCard.test.tsx` does it at file level (`beforeEach` sets both flags,
  `afterEach(resetFeatureFlags)`); `Badge.test.tsx` does it in a nested
  `describe`; `AutoCodeReportModal.test.tsx` does it inside one test with
  `try/finally`. Any of the three is fine. What is not fine is a test that
  passes only because the flag happens to be off.
- **Shipped state asserted separately.** A "parked" describe that leaves the
  flag at its default and asserts the affordance is absent (`queryByText` is
  null, the hover class is not present). This is the test that goes red the
  day someone flips the default, which is the point: a flag flip must fail a
  test so it is done on purpose.

**Prove the shipped-state test bites before committing it.** Flip the default
to `true`, run the two files, watch exactly those tests fail, restore. A
parked test that passes on arrival has shown nothing. (Done for
`proposalRationaleTooltip`; the 5 Aug pair were proved the same way.)

**How to add one:** add the boolean to `FeatureFlags` with a docstring that
says what it gates, when it was parked, *why*, and which doc holds the
questions; add it to `DEFAULTS` as `false`; gate the render site with
`featureFlags.<name> &&`; gate the CSS hook class too if the affordance is
CSS-driven (the tooltip's `has-tooltip` class is what makes `:hover` fire, so
leaving the class in place would have left a `position: relative` with
nothing inside, but a future rule could still match it); write both test
shapes; add the § Parked note to the design doc; update the `frontend/CLAUDE.md`
line that counts the parked features.

**What a parked flag is not for:** anything that differs by *host* or *build*.
A feature that exists on the desktop and not the CLI is a mode question
(§ 3), not a parking question. The flag file is for "not good enough yet",
full stop.

**CSS has no flag mechanism of its own.** The theme reacts to classes and
attributes the JS or the server sets: `.bn-export-mode` on `<body>` (set once,
in `routes/export.py`), `[data-platform="desktop"]` on `<html>` (set by the
server), and the ordinary component classes. Gating a style therefore means
gating the class in TSX, never adding a second switch in CSS. The
`tests/test_export_css_selectors.py` gate exists because a class renamed in
TSX silently un-gates every export rule that named it.

## 2. Compile-time conditions — Swift only

Swift's `#if` is a true preprocessor: code inside a false condition is not in
the binary, and neither are its string literals. That makes it the right tool
for anything that must be *provably absent* from a shipped build, and the
wrong tool for anything a tester on a real channel is meant to see.

**Two conditions are in use, and they compose into one enum:**

```swift
enum DistributionChannel {
    case debug                 // local Xcode build (#if DEBUG)
    case developerID           // direct notarised .dmg beta (DEVELOPER_ID_BETA flag)
    case appStoreOrTestFlight  // Release without the beta flag — App Store OR TestFlight
```

- **`#if DEBUG`** — every Cmd+R build. Dev escape hatches (`BRISTLENOSE_DEV_*`
  env reads in `ServeManager` / `PipelineRunner`), fake-state harnesses
  (`DiagnosticFixture`, `OllamaDownloadModel.DebugScene`, `AlphaBuild`'s days
  override), internal QA windows (`SeamLabView`, `KeycapGalleryView`,
  `TypeParityHTML` are whole files wrapped in `#if DEBUG`), the BuildInfo
  footer overlay, `webView.isInspectable`, and Section 3 of the Diagnostics
  menu.
- **`DEVELOPER_ID_BETA`** — set as `SWIFT_ACTIVE_COMPILATION_CONDITIONS` in
  the Developer-ID `.dmg` configuration only. Gates the developer-tools tier:
  the read-only SQLAdmin panel, Shoal tuning controls, `/api/dev/info`.

**Fail-closed by construction.** The App Store / TestFlight case is the
`#else` default. A misconfigured Release build cannot expose developer tools,
because there is no runtime state that flips them open; only a positive
compile flag does. This is a deliberate choice over a StoreKit receipt check,
which cannot distinguish a TestFlight tester from an App Review reviewer
(`DistributionChannel.swift` header explains the Guideline 2.1 risk).

**The audience tiers this produces** are the spec in
`docs/design-diagnostics-menu.md`, and the gate column is the thing to copy:

| Tier | Audience | Gate | Ships to |
|---|---|---|---|
| A — always-on | user | none | every channel |
| U — user diagnostics | user | `showDiagnosticsMenu` preference | every channel |
| V — developer tools | developer | `DistributionChannel.exposesDebugTools` | `.dmg` beta + local DEBUG |
| D — developer magic | nobody | `#if DEBUG` / build-time env | dev machines only |

**Rule for env-var reads in Swift: the read lives inside `#if DEBUG`, not
just the use.** `SidecarMode.swift` spells out why: the string literal
`"BRISTLENOSE_DEV_SIDECAR_PATH"` must not exist in the Release Mach-O, so the
`ProcessInfo.processInfo.environment[...]` lookup itself is guarded and
Release passes `nil` into the resolver. `desktop/scripts/check-release-binary.sh`
runs `strings` over the archived binary and fails on any `BRISTLENOSE_DEV_`
prefix, so a refactor that moves a read outside the guard fails the archive
rather than shipping a Release build that honours dev overrides. It is wired
into `build-all.sh` (step 7) and `build-dmg.sh`; the same invariant has no gate for the
`BRISTLENOSE_DEBUG_*` seeds, which are read only under `#if DEBUG` by
convention.

**What `#if DEBUG` is not for:** parking a half-finished user feature. A
parked feature should be reachable by a tester who flips one boolean; a
compile-time gate is reachable only by rebuilding from Xcode, and its absence
from Release is invisible to every test that runs in Debug. Swift has no
parked-feature flag today (see § 6).

## 3. Runtime mode detection — "where am I running?"

These are not feature flags. They are facts about the host, set by the caller
that started the process, and the code branches on them. They never park
anything, and they are never user-settable.

### Python — `create_app(dev=…)` plus underscore-prefixed env vars

| Signal | Set by | Gates |
|---|---|---|
| `dev` param / `_BRISTLENOSE_DEV=1` | `bristlenose serve --dev` (`cli.py`) | Vite HMR mount, playground, SQLAdmin full CRUD, `/api/dev/*`, the `__BRISTLENOSE_DEV__` script tag |
| `_BRISTLENOSE_DEV_ENDPOINTS=1` | the DEBUG desktop build's sidecar spawn | `/api/dev/*` only — so the native Run Inspector works without flipping the app into HMR mode |
| `_BRISTLENOSE_ADMIN_PANEL=1` | the `.dmg` beta desktop host | read-only SQLAdmin at `/admin`, never in the App Store build because it never sets the var |
| `_BRISTLENOSE_HOSTED_BY_DESKTOP=1` | the desktop host | disk `.env` files ignored; credential resolution defers to the host |
| `_BRISTLENOSE_AUTH_TOKEN`, `_BRISTLENOSE_PORT`, `_BRISTLENOSE_PROJECT_DIR`, `_BRISTLENOSE_VERBOSE` | the CLI, for its own uvicorn reload children | plumbing, not gating |

**The leading underscore is the convention: internal, set by a caller, never
documented for users, never read from a `.env` file.** `bristlenose doctor`
even warns when `_BRISTLENOSE_AUTH_TOKEN` leaks into a shell environment,
because a user-set internal var is a symptom.

**The mount-selection trap:** `create_app(dev=True)` does *not* select the dev
report mount — mount selection reads `_BRISTLENOSE_DEV` (`hmr` inside
`create_app`), so a test that passes `dev=True` and expects HMR gets the prod
mount. `CLAUDE.md` § Gotchas carries the workaround (`_STATIC_DIR`
monkeypatch).

### React SPA — three cached detectors and one window global

| Helper | Reads | True when |
|---|---|---|
| `isEmbedded()` (`utils/embedded.ts`) | `window.__BRISTLENOSE_EMBEDDED__` or `?embedded` | inside the macOS WKWebView |
| `isExportMode()` (`utils/exportData.ts`) | `window.BRISTLENOSE_EXPORT` | opened from an exported HTML file |
| `isDesktop()` (`utils/platform.ts`) | `<html data-platform="desktop">` | server says the host is the desktop app |
| `__BRISTLENOSE_DEV__` (inline read in `NavBar.tsx`, `AppLayout.tsx`) | script tag injected by `create_app` when `dev` | responsive playground |

All three helpers cache on first read, so a test that needs a different mode
sets the global *before* the first call or resets the module. `isEmbedded()`
and `isExportMode()` hide native-duplicated or non-functional chrome; they are
the reason a component checks `!isEmbedded() && !isExportMode()` before
rendering a control the host renders itself. `dt()` / `ct()` in
`utils/platformTranslation.ts` are the text-forking siblings of these
(`docs/platform-text-map.md`).

**What mode detection is not for:** hiding a feature because it isn't
finished. If a control is missing on the desktop because the *native* shell
provides it, that is `isEmbedded()`. If it is missing because it doesn't work
yet, that is § 1.

## 4. Debug seeds — fake a state on a dev machine

Environment variables that inject a scenario for QA. They exist so a
contributor can reproduce a partial-completion popover or an expired alpha
without provoking the real thing.

| Var | Side | Effect |
|---|---|---|
| `BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE=<scenario>` | Swift | overrides a project's pipeline state with a synthesised summary (`DiagnosticFixture.swift`) |
| `BRISTLENOSE_DEBUG_ALPHA_DAYS=<n>` | Swift | pretend N days remain on the alpha build; `-1` = expired (`AlphaBuild.swift`) |
| `BRISTLENOSE_DEBUG_OLLAMA_PHASE`, `BRISTLENOSE_DEBUG_OLLAMA_TAG` | Swift | drive the Ollama setup pill through states |
| `BRISTLENOSE_DEV_EXTERNAL_PORT`, `BRISTLENOSE_DEV_SIDECAR_PATH` | Swift | sidecar resolution escape hatch (`SidecarMode`) — set by the three Xcode schemes |
| `BRISTLENOSE_FAKE_THUMBNAILS=1` | Python | thumbnail placeholders on every session, for layout work (`s12_render/dashboard.py`) |
| `BRISTLENOSE_DEBUG_500=1` | Python | only honoured when `dev`; renders the debug 500 page |

**Swift rule:** every one of these is read inside `#if DEBUG`, so the literal
is absent from Release (§ 2). **Python rule:** a module-level read
(`_FAKE_THUMBNAILS = os.environ.get(...) == "1"`) is fine because the CLI is
one binary for every channel; there is nothing to strip. The cost is that a
Python seed is *reachable in production* by anyone who sets the var, which is
why none of them does anything a user would mind and why `BRISTLENOSE_DEBUG_500`
is additionally gated on `dev`.

**Naming drift, recorded rather than fixed:** Swift consistently uses
`BRISTLENOSE_DEBUG_` for seeds and `BRISTLENOSE_DEV_` for the escape hatch.
Python has `BRISTLENOSE_FAKE_THUMBNAILS` and `BRISTLENOSE_DEBUG_500` under two
prefixes for the same class. New Python seeds should take `BRISTLENOSE_DEBUG_`;
renaming the existing one buys nothing.

**These are distinct from user-facing kill switches**, which are documented
config with the plain `BRISTLENOSE_` prefix and no debug intent:
`BRISTLENOSE_LLM_TELEMETRY=0` (stop writing `llm-calls.jsonl`),
`BRISTLENOSE_LOG_LEVEL`, `BRISTLENOSE_WHISPER_MODEL_DIR`,
`BRISTLENOSE_LLM_FORECAST=legacy` (a compatibility switch in pricing). A kill
switch is a supported setting; a seed is a QA tool.

## 5. User preferences that gate a surface — Swift

`DiagnosticsPreference` (`DiagnosticsActions.swift`): key `showDiagnosticsMenu`,
default `true` under `#if DEBUG` and `false` otherwise, read through
`isEnabled()`. This is Tier U above: a shipped, off-by-default toggle the user
owns. It is the right home for something a TestFlight tester should be able
to reach (the Diagnostics menu, `isInspectable` on the web view) that an
ordinary user should not see by default.

It is **not** a feature flag either: the feature is finished, the user
decides. Confusing the two is how a parked feature ends up as a Settings
toggle nobody asked for.

## 6. When the mechanism doesn't exist yet

**Python's parked-feature flags are fields on `Config`, not a register of their
own.** Two ship: `experimental_codebook_lab` (`config.py:232`, default `False`
since 20 Sep 2026) and `experimental_chat_lens` (`:238`, default `True`), each
gating a router mount in `server/app.py` (`:250`, `:265`). So the mechanism is
not missing — it is spelled differently from § 1's, and a reader told Python
has none will invent a third shape. _This section said "Python has no
parked-feature flag" on the day it was written, which was the same day the lab
flag was flipped default-off._ Neither has a `DEFAULTS` or a
`reset_feature_flags()`, which is the real gap; if a third is added, copy the
frontend shape rather than reaching for an env var: a `bristlenose/feature_flags.py`
holding a dataclass of booleans with a `DEFAULTS` and a `reset_feature_flags()`,
read by production code and flipped by tests. An env var is the wrong shape
because it is reachable by users, invisible to the type checker, and has no
"shipped state" test. This has not been exercised; the first use should
confirm the shape and update this section.

**Swift has no parked-feature flag.** `#if DEBUG` is the wrong tool (§ 2):
it hides from Release only, and a tester cannot flip it. If a native feature
needs parking, an `enum FeatureFlags { static var … }` with the same three
rules and the same two test shapes is the shape to copy, and the flag must
default off in *every* build configuration, `DEBUG` included, so the Swift
suite runs against the shipped state. Also unexercised.

## 7. Decision table

| I want to… | Use | Not |
|---|---|---|
| ship a build with a feature switched off until the design is fixed | § 1 parked flag (SPA) or its § 6 sibling | `#if DEBUG`, an env var, commenting out |
| keep a debug surface out of App Store review, provably | § 2 `DistributionChannel` / `#if DEBUG` | a runtime preference, a receipt check |
| let TestFlight testers reach a diagnostic | § 5 preference (Tier U) | `#if DEBUG` (they can't build it) |
| hide chrome the native shell already provides | § 3 `isEmbedded()` | a parked flag |
| hide controls in an exported report | § 3 `isExportMode()` + `export.css` | a parked flag |
| reproduce a failure state on my machine | § 4 debug seed | a permanent code path |
| retire a CLI option without breaking a caller | `hidden=True` + a message (§ 8) | deleting it (`grep desktop/ .github/` first) |
| declare a setting that isn't implemented yet | refuse the run (§ 8) | warn and continue |

## 8. Two things that look like flags

**Hidden CLI options and commands** (`typer.Option(hidden=True)`,
`app.command(hidden=True)`): `--no-serve` is hidden because it is the desktop
sidecar's flag, not a user path; `analyse` is a hidden British-spelling alias;
`render` is a hidden tombstone that prints where the command went. Hiding is
about the `--help` surface, never about whether the code runs.

**Configured-but-unimplemented settings refuse, they don't warn.**
`pii_llm_pass` and `pii_custom_names` are declared on `Settings` and wired to
nothing; setting either makes `s07_pii_removal` raise before the stage runs
(`fa78e936`, 14 Aug 2026). The reasoning is specific to privacy controls but
the shape generalises: a setting that exists in the schema and does nothing
is a feature flag with a lie for a default. Either implement it, delete it, or
refuse it.

## 9. What verifies each mechanism

| Mechanism | Gate | Blind spot |
|---|---|---|
| § 1 parked flags | the two test shapes per flag; `QuoteCard.test.tsx` "parked features" describe | a flag added without the shipped-state test is unguarded — nothing enumerates the flags against the tests |
| § 2 `#if DEBUG` env reads | `desktop/scripts/check-release-binary.sh` (`BRISTLENOSE_DEV_` prefix, on the archive) | `BRISTLENOSE_DEBUG_*` literals are not scanned; the invariant holds by convention |
| § 2 `DistributionChannel` | fail-closed `#else`; `tests/test_entitlements_split.py` covers the sibling config split, not this flag | nothing asserts `DEVELOPER_ID_BETA` is absent from the App Store configuration |
| § 3 mode detection | `test_export_css_selectors.py` (export classes); `prod_app_factory` tests for the prod mount | `isEmbedded()` chrome-hiding has per-component tests only |
| § 4 seeds | none | a seed honoured in a non-`dev` Python path would ship silently — only `BRISTLENOSE_DEBUG_500` is double-gated |

## Related

- `docs/design-diagnostics-menu.md` — the audience tiers and the menu that
  presents them
- `docs/design-desktop-debug-admin-panel.md` — `DistributionChannel`'s origin
- `docs/design-moderator-question-pill.md`, `docs/design-quote-context-expansion.md`,
  `docs/design-autocode.md` § Parked — the three parked frontend features
- `docs/platform-text-map.md` — `dt()` / `ct()`, the text side of § 3
- `docs/design-modularity.md` — why CLI and desktop run the same Python (no
  fork), which is why Python has host facts rather than build variants
