---
status: current
last-trued: 2026-08-21 (the package re-fits on tab activation only — recorded with the two consequences for pane authors)
previous-trued: 2026-08-18 (three slices — cloud-import added Tab 4; accounts-pane-i18n closed the unlocalised flag; miro-disconnect reframed the two surfaces around need, not mechanism)
trued-against: HEAD@main on 2026-08-21 (028d539b)
---

## Changelog

- _2026-08-21_ — **Truing pass (`--doc`): "sizes each pane on every switch" was true and read as a guarantee it does not make.** The doc described `fittingSize` + animated `setFrame` and stopped there, which a cold reader takes as "the window looks after its own height". It does not: `setWindowFrame` has exactly two callers and both are tab activation, and the pane view is pinned by *required* constraints that beat `NSHostingView`'s 750-priority intrinsic size — so a pane that changes height while on screen compresses or clips, silently. Found by building the MCP Agents register, whose height is data. Recorded here with the two consequences for pane authors: use `SettingsWindow.refitToContent()` when a pane's height depends on its own state, and note that pinning a region to a fixed height to prevent reflow is only free while that region is the last thing in the pane — MCP Agents' 170pt payload region was invisible dead space until the register landed below it and turned it into a hole. Anchors: `SettingsTabViewController.swift` (the two `setWindowFrame` callers), `Utilities.constrainToSuperviewBounds`, `SettingsView.swift` (`refitToContent`), `MCPAgentsSettingsView.swift` (`payloadPane`).
- _2026-08-18_ — **Truing pass (`--topic miro-disconnect`): the Tab 4 cross-pane note described a mechanism and called it a user distinction.** It led with "Settings is the only surface that *fully* disconnects Miro" — false once both paths converged on `MiroConnectionStore.disconnect` (`2b2be42e`), and self-contradicted three clauses later by its own "**Both paths now post `.bristlenosePrefsChanged`**". The replacement claim, "Settings is the only surface that can disconnect without a serve running", was mechanically true and **worse**: it answers a question no researcher asks. Corrected on the maintainer's steer — the two surfaces exist because they serve two needs. The sheet is mid-journey and urgent (you are one click from putting client A's quotes on client B's board); Accounts is the overview, and half its value is disclosing that the integrations exist at all. The four-copy token mechanics are kept, demoted to explaining *why one implementation* rather than *why one surface*. Standing lesson, and the reason this entry is longer than the edit: **a cross-surface claim stated in implementation terms will read as true to the person who just wrote the implementation.** Both wrong versions were written by someone with the call stack in front of them. Anchors: `MiroConnectionStore.swift:88` (the shared sequence), `MiroSheet.swift:153` (the caller), `MiroDisconnectTests.swift` (pins both entry points reach it).
- _2026-08-18_ — **Truing pass (`--topic cloud-import`): the pane count was five and six ship.** **Accounts** landed 18 Aug between Transcription and MCP Agents and was enumerated nowhere in this doc — added as Tab 4 below, along with the five decisions that were only in code comments. Same sweep: the locale count 21 → 22 (Catalan, 0.26.0) in three places here, and the matching "five Settings panes" comment in `SettingsView.swift:10`. ~~**Flagged, not fixed** (belongs to an i18n pass, not this doc): the Accounts pane ships **unlocalised** — zero `i18n.t` call sites in `AccountsSettingsView.swift`, its title hardcoded `"Accounts"` while the other five read `desktop.settingsTabs.*`, and no `accounts` key in `en/desktop.json`.~~ **Fixed the same day (`d0478b15`)** — 21 keys (`desktop.settingsTabs.accounts` plus a 20-key `desktop.accounts`) seeded across all 21 full locales, `zh-Hant-HK` inheriting rather than pinned; the title now reads `i18n.t("desktop.settingsTabs.accounts")`. The *reason* it had to be flagged here rather than caught anywhere is the durable part and it stands: **`check-locales.py` diffs en→locale, so an absent en key can never be reported missing** — the pane was invisible to the gate by construction, not by oversight, and `--strict` would have run just as green. Promoted to `CLAUDE.md:231` as a standing failure mode.
- _2026-08-17_ — **New first pane, General, holding one row: where new projects go.** Three of the four project-creation doors (loose-file drops on the sidebar and on the welcome screen, the import window) open an `NSSavePanel` and now share a three-rung ladder in `ProjectFolderDefaults`: **configured** (this pane) → **remembered** (the parent of the last project made) → **`~/Documents`**. The fourth door, `+ New Project`, deliberately proposes nothing and **must stay that way** — `ProjectIndex.renameProject` writes `.name` and never `.path`, so eagerly creating `<configured>/New project/` and dropping into inline rename would leave the sidebar saying "Ikea Study" while the folder on disk stayed `New project`, silently and permanently. Here the folder *is* the document, so two names for one document is the worst available outcome; the invariant that prevents it is precisely that the placeholder has no path. Also fixed in the same pass: **the `~/Documents` floor never resolved to `~/Documents`** — `FileManager.urls(for: .documentDirectory, in: .userDomainMask)` returns the app's *private container* Documents under App Sandbox (the container symlinks Desktop/Downloads/Movies/Music/Pictures out to the real folders but keeps Documents private), so a project made from a first-run panel would have landed inside the container: invisible in Finder, wiped by `reset-sandbox-state.sh`. New `UserHome` reads the passwd entry via `getpwuid`, which the sandbox does not rewrite, and also repairs two dead `NSHomeDirectory()` comparisons that meant the undo toast and the location breadcrumb never abbreviated to `~` (VoiceOver read "Users, cassio, …" first). And `ProjectIndex.detectLocation`'s three-prefix cloud allowlist became structural (`isUbiquitousItemKey` + a `CloudStorage/<Provider>` read), which adds Google Drive/Box/Proton and — the real bug — stops reporting a **synced `~/Documents` as "On this Mac"**, i.e. the app's own default location on any Mac with iCloud Drive on. Anchors: `GeneralSettingsView.swift`, `ProjectFolderDefaults.swift`, `UserHome.swift`, `SettingsView.swift` (`.general`, first), `ProjectIndex.swift` (`cloudProviderLabel`), `RemoveToast.swift`, `ContentView.swift` (`breadcrumbSegments`).
- _2026-08-04_ — **Switching light↔dark no longer restarts the serve (and so no longer cold-remounts the report).** The Appearance picker's `.onChange` posted `.bristlenosePrefsChanged`, which `ServeManager` answers with `restartIfRunning()` — drain the warm sidecar, shut down, respawn. Because the respawn takes a fresh `bind(0)` port, the detail WebView's `.id("<project>-<port>")` changed and SwiftUI tore down and rebuilt the whole `NSViewRepresentable`: the SPA cold-mounted, losing route, scroll position, open panels and focus, plus a couple of seconds of sidecar boot — all to serve **byte-identical HTML**, since `appearance` appears nowhere in `BristlenoseShared.childEnvironment`. Deleted; the pref now reaches the report purely through `NSApp.appearance` → WKWebView → `prefers-color-scheme`. The control experiment that proves the restart was always redundant: on "auto", flipping the *system* theme posts nothing, restarts nothing, and re-themes the report anyway. Typography and Language keep their posts — they genuinely produce env vars (`BRISTLENOSE_TYPOGRAPHY`, `BRISTLENOSE_WHISPER_LANGUAGE`). Same pass trued two stale claims here: the `syncAppearance()` bridge call (removed 30 Jul 2026) and the mapping table's "bridge, not env". Anchors: `AppearanceSettingsView.swift` (the comment where the `.onChange` was), `ServeManager.swift:421` (`restartIfRunning`), `ContentView.swift:2306` (the port-keyed `.id`).
- _2026-07-31_ — **Settings window follows the appearance preference live.** The window is AppKit-hosted (the `Settings` package's `SettingsWindowController`), so the panes' `.preferredColorScheme` never reaches the window chrome — only `window.appearance` does, and that was set once in `show()` ("changing appearance while Settings is open is an accepted edge"). Clicking Dark in the Appearance pane left the Settings window itself light until reopened. Now `SettingsPaneChrome` re-applies `SettingsWindow.applyAppearance()` via `.onChange(of: appearance)` — sufficient because the Appearance pane is the pref's only writer, so the modifier is on-screen whenever the value changes. Anchors: `SettingsView.swift` (`applyAppearance`, `SettingsPaneChrome`).
- _2026-07-26_ — **Settings window rebuilt on Sindre Sorhus's `Settings` package** (AppKit `SettingsWindowController` + `NSViewController` panes), replacing the SwiftUI `Settings {}` + `TabView` **and** the same-day hand-rolled `SettingsWindowHeightAnimator` shim described in the entry below — which high-water-marked, scrolled content under the toolbar, and never shipped past local iteration. The package sizes each pane to `fittingSize` and animates `setFrame` both ways: no high-water-mark, no shim, no per-tab constants. Deep-research verified this is the canonical solution (Apple Forums 682046 documents the `TabView` sizing behaviour; the package is the MASPreferences-lineage standard). Also: `showSettingsWindow:` now answered by `AppDelegate`; Cmd+, via `CommandGroup(replacing: .appSettings)`; `SettingsLink` → `SettingsWindow.shared.show(pane:)`; the `PkgSettings` typealias (`SettingsPackageAlias.swift`) resolves the package-vs-SwiftUI `Settings` name clash. The subtitle/keyline/Language-under-Typography/660-width work (next entry) survives unchanged. Anchors: `SettingsView.swift` (`SettingsWindow`), `SettingsPackageAlias.swift`, `BristlenoseApp.swift`, `WelcomeHomeView.swift`.
- _2026-07-26_ — Settings window sizing trued to shipped reality + polish. Width is now genuinely 660 across all tabs (LLM was 720 — the 60pt jump on visiting LLM is gone). Height animates per tab via the new `SettingsWindowHeightAnimator` (drives `NSWindow.setFrame(animate:)`, since SwiftUI's Settings+TabView only grows, never shrinks). Appearance help text moved to in-cell subtitles (no row keylines, Stage-Manager idiom); Language picker relocated under Typography with the Weblate line as a section footer. Anchors: `SettingsView.swift` (`targetContentHeight`/`SettingsWindowHeightAnimator`), `AppearanceSettingsView.swift`, `TranscriptionSettingsView.swift`, `LLMSettingsView.swift:58`.
- _2026-07-26_ — Full truing pass (archetype C), same day as the sizing note above. **§Tab 1 (Appearance) rewritten** — the shipped tab is appearance/palette/typography/language pickers + three toggles with in-cell subtitles, not the old "theme radio + delegate-language-to-System-Settings"; the "No in-app language picker" claim was false (picker shipped, `AppearanceSettingsView.swift:63`). **Activation semantics corrected** — the guard is `canActivate` (key present + not known-bad: `.online`/`.outOfCredit`/`.unavailable` all activate), not a live `.online` (`LLMSettingsView.swift:677`, `LLMProvider.swift:279`). **`.outOfCredit` added to the status table** — a 402 is a sticky observed-negative, distinct from transient `.unavailable` (`LLMProvider.swift:238`). **§"Provider status lifecycle (planned)" banner re-annotated** — the eager board, activation-on-truth, and 402-split have since shipped; rung-3 probe reuse, offline three-bucket grey, and refocus-recheck remain design-forward. Tab 2 core mechanics + Tab 3 verified fresh, unchanged.
- _2026-06-21_ — repointed the `degradedBody` reference from the deleted `PipelineActivityItem.swift` to `ProjectDiagnosticPopover.swift` (the failure popover was extracted there, commit `02ad258`).
- _2026-06-06_ — Corrected the eager-board §"Online behaviour" verification gate after grounding it in Apple docs + prior art: the "3× Keychain prompt cascade" is a *legacy file-based keychain* symptom (Always-Allow grant bound to the binary's code-directory hash), **not** a "dev/DerivedData artifact." We already migrated to the data-protection keychain (`8b2ef51`), which validates by Team ID and has no ACLs, so own-access-group reads don't prompt on a team-signed build. Gate narrowed from "discover whether eager is viable" → "confirm the build isn't ad-hoc." Refs: Apple TN3137, steipete/CodexBar #585. Also recorded Martin's "no rung-3/billing call on open" decision and the open "green = valid vs runnable?" offline-rendering question (pending ponder). The stale `desktop/CLAUDE.md` Debug-signing note was reconciled to the data-protection model in the same pass.
- _2026-06-06_ — Added §"Provider status lifecycle (planned)" — the truthful-effort-free-board design that supersedes the parked NWPathMonitor-toast coverage gap. Captures the four-rung cost ladder (in-memory / Keychain / network-auth / real-work-call), the online optimistic-from-cache + silent-background-reconfirm policy (kills the lazy-load "dashboard of lies"), the offline three-bucket model ("worked before" vs "never configured" vs "not set up"), the 402-masked-as-green fix (split `.unavailable` into observation-failed vs observed-a-negative), the refocus-recheck for credit top-ups, and the shared `probe(provider, model)` rung-3 unit (key-entry / refocus / `scripts/llm-weather.py`). Also records the activation-no-op root cause (lazy status → radio guard bails) and the `overlayPreferences` model-without-provider leak fix. Section is design-forward (not yet shipped) — clearly delineated from the shipped Beat 3/3b flow above. Anchors: `BristlenoseShared.swift` `overlayPreferences`, `LLMSettingsView.swift` `applyPresenceAndCache`/`refreshStatuses`/`kickOffValidation`, `LLMValidator.swift` `classify`/`buildRequest`.
- _2026-04-30_ — Beat 3b + post-merge review fixes reconciled. Ollama URL hardwired to `localhost:11434/v1` in the desktop GUI (commit `dbd54ec`); editable TextField removed and replaced with static read-only display. CLI/CI override via parent-process `BRISTLENOSE_LOCAL_URL` env var only (`ServeManager.swift:351-357`, `BristlenoseShared.swift:122-127`). `localURL` UserDefaults key dropped from the env-injection table — no longer touched by the GUI. Added §"Validation invariants" subsection capturing the "presence-and-cache reader never sets `.checking`" contract that prevents radio-toggle stranded-spinner regressions, and the Azure focus-blur revalidation pattern that deliberately replaced per-keystroke validation. AIConsent + OllamaSetupSheet first-run flow cross-referenced (canonical home is the parked `design-first-run-flow.md` — see 100days §3 Should). Anchors: `LLMSettingsView.swift:331-348`, `LLMSettingsView.swift:524-536`, `LLMSettingsView.swift:629-637`.
- _2026-04-29_ — Beat 3 reconciled: round-trip credential validation now shipped via new `LLMValidator.swift`. ProviderStatus table augmented to cover Azure 404 → `.invalid` and Anthropic forward-compat (any 4xx ≠ 401/403/402/429 → `.online`, robust against haiku-model deprecation). New §"Validation flow" subsection documents the verdict cache (SHA256-prefix keyed, UserDefaults), 60s TTL gate, offline survival via cache fallback on transient `.unavailable`, `.checking` rendered as `ProgressView` (Mail-style spinner), animated dot transitions, and the "Last verified Xm ago" line. Tightened Ollama line to specify HTTP probe target (`<url>/api/tags`). Anchors: `desktop/Bristlenose/Bristlenose/LLMValidator.swift`, `desktop/Bristlenose/Bristlenose/LLMSettingsView.swift`, `desktop/Bristlenose/Bristlenose/LLMProvider.swift`.
- _2026-04-21_ — trued up, minor additions: noted Ollama status derives from URL reachability (no key-injection); noted `overlayPreferences` don't-override-default guard (only explicitly-set values get emitted); noted `KeychainStore` protocol + `InMemoryKeychain` test shim; promoted threat-model rationale (env-vars vs keychain-access-groups residual-risk delta) from `ServeManager.swift:366-371` comment; added cross-ref to `design-settings-ui.md` for the serve-mode web-UI path (complement, not competitor) and `design-keychain.md` §Desktop credential path.
- _2026-04-20_ — trued in C3 closeout pass; structural accuracy confirmed against `SettingsView.swift`, `ServeManager.swift`, `LLMProvider.swift`.

# Desktop Settings Window (Cmd+,)

Canonical macOS Settings window with 6 icon-toolbar panes (General, Appearance, LLM Provider, Transcription, Accounts, MCP Agents), built on **Sindre Sorhus's `Settings` package** — an AppKit `SettingsWindowController` swapping `NSViewController` panes — **NOT** a SwiftUI `Settings {}` + `TabView`. Constant 660pt width; the window sizes each pane to its `view.fittingSize` fresh on every switch and animates `NSWindow.setFrame` in **both** directions, so shorter panes genuinely shrink.

**"On every switch" is the whole contract — it does not re-fit while you are looking at a pane.** Measured against the vendored source 21 Aug 2026: `SettingsTabViewController.setWindowFrame(for:)` has exactly two callers, `immediatelyDisplayTab` and `animateTabTransition`. Both are tab activation. And the pane's view is pinned to the container by *required* `V:|-0-[subview]-0-|` constraints (`Utilities.constrainToSuperviewBounds`) while `NSHostingView`'s intrinsic height is only 750-priority — so the required constraint wins and a pane that grows or shrinks under its own steam **compresses or clips instead of resizing the window**. Nothing errors; the content just runs out of room.

This never bit while every pane was fixed-height by construction. It bites the moment a pane's height depends on its own state — a picker that swaps content of different lengths, a table whose row count is data. Two consequences for pane authors:

- **A pane whose height varies with its own state must ask for a re-fit.** `SettingsWindow.refitToContent()` (`SettingsView.swift`) runs the same arithmetic on demand: `layoutSubtreeIfNeeded`, read `fittingSize`, set the frame from the top-left so the title bar stays put, with a half-point deadband so layout noise cannot animate the window. It is deliberately the package's own question asked again, not a reimplementation of layout — if the package ever grows a public re-fit, it becomes a one-line forward.
- **Pinning a region to a fixed height to prevent reflow is only free while that region is LAST in the pane.** Dead space at the bottom of a window is invisible; the same dead space with anything below it is a hole. MCP Agents pinned its client-payload region at 170pt for exactly that reason and got away with it until the projects register landed underneath — at which point the shortest tab showed ~150pt of nothing through the middle of the pane. Unpinning it is also what makes `fittingSize` honest, which is what lets the window take the height each tab actually needs. The high-water-mark that a SwiftUI `Settings`+`TabView` suffers — it grows to the tallest tab and never shrinks back, because a greedy `.formStyle(.grouped)` Form gives the window no natural-height signal — is architecturally absent here. **Do NOT reintroduce a `TabView`**: the whole hand-rolled `NSWindow.setFrame` shim + per-tab height constants that a TabView required were deleted when the package landed (they high-water-marked and slid content under the toolbar; the package is the canonical fix — Apple Forums 682046 documents the TabView sizing behaviour, and fittingSize + animated setFrame via VC-swap is the MASPreferences-lineage standard the package implements).

`SettingsWindow` (`SettingsView.swift`) owns the controller and wraps the six SwiftUI pane views (each with `.environmentObject(i18n)` + a `SettingsPaneChrome` modifier for live palette tint + appearance). `AppDelegate.showSettingsWindow(_:)` answers the responder-chain callers (web bridge "open-settings", out-of-credit pill); `CommandGroup(replacing: .appSettings)` provides the App-menu item + Cmd+,; the welcome "Setup →" deep-links via `SettingsWindow.shared.show(pane: .llm)`. **Namespace gotcha:** the package's `enum Settings` collides with SwiftUI's `struct Settings` (scene), so the pane types are reached through `PkgSettings` — a typealias defined in `SettingsPackageAlias.swift`, a deliberately SwiftUI-free file where `Settings` resolves unambiguously to the package.

Help text in Appearance + Transcription is an **in-cell subtitle** (title + secondary `Text` in the control's label — the System Settings idiom, no row keyline); the Language picker sits under Typography. Working context lives in `desktop/CLAUDE.md`. Related: `design-settings-ui.md` (serve-mode web UI — complementary, not competing: web UI is the CLI/serve path; this is the embedded-alpha path), `design-keychain.md` §Desktop (sandboxed) credential path (canonical home for the Swift→env-var→Python architecture).

## Tab 0: General (gearshape) — where new projects go

**One row, and its default state is the whole design.** With nothing configured the popup reads **"Last location used"** — not "None", which would imply the app has no behaviour (false, and worse than the setting itself). Documents-then-remember is what Xcode and Final Cut both do, *neither of which offers a preference at all* — Xcode stores the parent of the folder you last navigated to as a plain path in `IDETemplateCompletionDefaultPath`, and FCP remembers the last location for new libraries while keeping a per-library storage sheet for a different question. So this row is an override on a behaviour Apple's own pro apps consider sufficient, and it should say so rather than present itself as the normal path.

**Controls:** a pop-up button (not a bare `Choose…`), showing the folder's real Finder icon via `NSWorkspace.icon(forFile:)` — this is one specific folder, not the concept of a folder, and a custom folder icon is how the researcher recognises it. Its menu is `Other…` / divider / `Use Last Location`, so the reset has a home without a second button competing for the row. The second line carries whichever fact matters in the current state: the help sentence when unset, the `~`-abbreviated path when set, or the reason when unreachable. Help text is an in-cell subtitle, matching Appearance and Transcription.

**Configured is a security-scoped bookmark; remembered is a plain path.** Remembered only ever pre-*navigates* a panel, and under App Sandbox the panel itself is what grants access — so a path we hold no grant for is fine. A folder chosen once in Settings and consulted on a later launch has no live panel grant behind it, and a value the researcher set deliberately must not evaporate the first time they rename its parent. Consequence, stated rather than glossed: **renaming loses a remembered location and keeps a configured one.** That asymmetry is the point of the bookmark.

**A missing folder is not a decision.** An unplugged drive does not mean the researcher changed their mind, so `suggestedDirectory()` falls through to the next rung while the row keeps naming the folder it was pointed at and says why: *"On **Iona**, which isn't connected."* — naming the volume, as `cantFind(.unmountedVolume(name:))` already does elsewhere — or *"This folder has been deleted."* Never silently clear the preference; never silently swap the row to Documents.

**Cloud folders get a neutral named badge, never a warning** — `~/Library/CloudStorage/Dropbox/Acme/Studies — in Dropbox`, same weight as the path. A project folder inside the client's tree is the *intended* configuration (`design-project-storage.md` §3: name the provider, and never frame it as privacy). Attribution earns its place because when a run stalls for minutes materialising a dataless file, the researcher needs to already know this folder is Dropbox's, or the stall reads as Bristlenose being slow.

**Known consequence, not yet addressed:** this pane converts an occasional cloud-folder *choice* into the configured default at every door — one of which (drag-import) holds `FileManager.copyItem`, which blocks **indefinitely and uncancellably** on a dataless source. The pane does not cause that bug, but it multiplies the rate at which it is reached, which is what makes the coordinated-reads work in `design-project-storage.md` §3 stop being deferrable.

**Why a pane and not a row in Appearance.** The others are chrome, the two engines, and who can read your work; a storage location is none of those, and Appearance-as-the-roomiest-pane is how Appearance stops meaning anything. Deliberately *not* named "Storage" — `design-project-storage.md` spent nine rejected models establishing that Bristlenose manages none, and that name re-opens every one of them. "General" is the pane a Mac user checks for app-level behaviour, and it absorbs the next two or three preferences without a rename. Its 22 locale strings reuse the already-reviewed `settings.settingsNav.general` twin, which matches macOS's own System Settings term in each language (一般, 일반, Allgemein, Основные).

**Deliberately not built:** the save-panel accessory-view checkbox ("Use this location for new projects"). The HIG sanctions accessory views, and it was the right answer while the choice was *nothing vs something* — but once this row exists, a checkbox writing the same value is a second writer on the surface where the researcher is mid-task and least wants a policy decision, and it cannot serve the placeholder door, which never opens a panel. If a second path is wanted, the good one is a project-row context item ("Use This Folder for New Projects") — a verb on a folder whose grant we already hold, same shape as Turn On Agent Access: the menu is the act, the pane is the audit.

## Tab 1: Appearance (paintbrush)

Grouped controls, top to bottom: **Application appearance** radio (auto/light/dark), **Colour palette** pop-up (default/edo), **Typography** pop-up (SF Pro/Inter), **Language** pop-up (22 locale autonyms) with a Weblate contribute link as the section footer, then three toggles — **random project icons**, **show-analysis-animation**, **show-diagnostics-menu** — each carrying its help text as an in-cell subtitle (title + secondary `Text` in the control's label, the System Settings idiom, no row keyline). Anchors: `AppearanceSettingsView.swift:38` (palette), `:49` (typography), `:63` (language), `:100`/`:108`/`:121` (toggles).

- **Appearance** — `@AppStorage("appearance")` drives `.preferredColorScheme` on the main window (a SwiftUI scene); the Settings window is AppKit-hosted, so it follows `window.appearance` instead — set in `SettingsWindow.show()` and re-applied live by `SettingsPaneChrome.onChange` when the pref changes (see 31 Jul changelog entry). **It reaches the web report through the platform, not through us** — `AppAppearance` sets `NSApp.appearance`, the WKWebView inherits its window's effective appearance, and the report CSS follows `prefers-color-scheme`. No bridge call and no env var: the `syncAppearance()` this bullet used to name was removed 30 Jul 2026 (nothing consumed it — see `BridgeHandler.swift:258`), and there is no `.onChange` posting `.bristlenosePrefsChanged` either (see 4 Aug changelog entry). The web Settings modal hides its own appearance picker in embedded mode — native wins.
- **Colour palette** — live swap, no restart: posts `.bristlenosePaletteChanged` → `bridgeHandler.setColorPalette()`; the `@AppStorage("palette")` value also seeds `BRISTLENOSE_PALETTE` for the next serve start. Options mirror the frontend `PALETTES` list.
- **Typography** — SF Pro (native scale) vs Inter (matches the web report). Lands on the next serve start via `BRISTLENOSE_TYPOGRAPHY` (posts `.bristlenosePrefsChanged`). See `docs/design-native-typography-grid.md`.
- **Language** — `@AppStorage("language")`, 22 autonyms (never translated). `.onChange` calls `i18n.setLocale` and posts `.bristlenosePrefsChanged` to restart serve (`BRISTLENOSE_WHISPER_LANGUAGE`).

> **Superseded 2026 (in-app picker shipped).** The earlier design had **no in-app language picker** and delegated entirely to System Settings → General → Language & Region → Apps → Bristlenose (`INFOPLIST_KEY_UIPrefersShowingLanguageSettings = YES`; `I18n.swift` reads `Bundle.preferredLocalizations(from:forPreferences:)` on launch). That macOS path still exists, but the in-app Language picker above is now the primary control. Canonical locale-negotiation design: `docs/design-locale-negotiation.md`. The web Settings modal in CLI serve mode keeps its own language picker — browsers have no per-site override.

## Tab 2: LLM (brain) — Mail Accounts pattern

Left sidebar list of 5 pre-populated providers (Claude, ChatGPT, Gemini, Azure, Ollama) with two orthogonal indicators per row:
- **Radio/checkmark** — which provider is active (user choice, `@AppStorage("activeProvider")`)
- **Status dot** — whether the provider is configured (green "Online" / grey "Not set up" / red "Invalid" / orange "Unavailable")

Right detail pane shows the selected provider's settings: API key (`SecureField` → Keychain via `KeychainHelper`), model picker (per-provider known models + "Custom…"), concurrency slider. Azure adds endpoint/deployment/version fields. Ollama shows a **read-only** static display of the URL (`localhost:11434`) — the field is hardwired in the desktop GUI as a trust-boundary closure (commit `dbd54ec`, 30 Apr 2026): a social-engineered user pasting an attacker URL would silently exfiltrate transcripts over plain HTTP, contradicting the "transcripts stay on your Mac" claim. Status derives from an HTTP probe to `<hardwired-url>/api/tags`, parsing the models list to distinguish "not running" from "running but no models pulled"; see `LLMValidator.probeOllama`. CLI users and CI keep the override path via the `BRISTLENOSE_LOCAL_URL` env var (parent-process only — see §Preferences below).

**Activation guard**: a provider can be activated (radio or toggle) when its status `canActivate` — a key is present and not known-bad (`.online`, `.outOfCredit`, or `.unavailable` all qualify), **not** a live `.online`. An out-of-credit or momentarily-unreachable provider is a legitimate choice; only `.notSetUp` (no key), `.invalid` (confirmed-bad credentials), and `.checking` block. Single home for the contract: `LLMSettingsView.swift:677` (`guard statusFor(provider).canActivate`), backed by `LLMProvider.canActivate` (`:279`). One provider must always be active.

**Per-provider model storage**: `UserDefaults` key `llmModel_{provider}` stores each provider's selected model. When a provider becomes active, its model is written to the global `llmModel` key for ServeManager.

## Tab 3: Transcription (waveform)

Whisper backend picker (Auto/MLX/faster-whisper) + model picker (large-v3-turbo through tiny). `@AppStorage` for both.

## Tab 4: Accounts (person.crop.circle) — what Bristlenose talks to on your behalf

One section per service — the shipping meeting platforms in `design-cloud-import.md` §5's sequence,
then Miro, the only one that *sends* rather than fetches. Anchors: `AccountsSectionModel.swift`
(the model), `AccountsSettingsView.swift` (the view), `SettingsView.swift:96-113` (registration).

**The pane makes no network call, and that is the design.** Every state is derived from what is
already on disk — the Keychain, the OAuth config, and the address stored beside the tokens. A
Settings pane that probed on appear would be slow, would do I/O the researcher did not ask for, and
would turn *"you are offline"* into something the pane **asserts** rather than observes.
Reachability belongs in the import window, where a call is actually being made. The consequence is
worth stating plainly because it constrains every future row: **any state knowable only from a call
must be persisted when that call happens**, not discovered here. Google's account tier is free
because it falls out of the address domain; Microsoft's does not, and is the one state still owed a
writer.

**Four states** (`AccountSectionState`): `unavailable(strandedIdentity:)` · `notConnected` ·
`connected(identity:)` · `attention(identity:, AccountAttention)`. Only `attention` is recoverable
from here (`isRecoverable` ⇔ `.signInAgain`). `strandedIdentity` is the sharp edge: a grant that
outlived the client id it was obtained with. It is the only reason `unavailable` ever carries an
account key, and the row **says so** rather than implying nothing is there.

**`AccountService` is deliberately not `CloudPlatform`.** That enum means "a meeting platform with
an import adapter", and adding `.miro` would put Miro in the import window's platform picker, in
`CloudPlatform.built`, and in the fixture harness. To the person using it they are the same kind of
thing — an account you connect, see, and remove — so the sameness lives in `AccountService` instead
of being forced into the platform enum.

**The list reads `shipping`, not `built` — a parked service is not listed at all.** It read `built`
for one release, on the argument that a catalogue hiding what is not ready cannot answer "what can
this thing talk to?". That argument was wrong about the reader: a permanent row saying Bristlenose
cannot sign in to Zoom answers a question nobody asked and spends a quarter of the pane doing it.
**Safe only because a parked platform cannot hold a grant** — `accountKeys` returns nothing for one,
so hiding it cannot strand a credential where no UI can reach it. *Check that again before parking a
service that has ever stored a sign-in.*

**No SF-Symbol stand-ins for vendor marks — the missing icons are the answer, not an interim.** The
licence boundary is the sign-in button: the name is free, the product mark needs a licence from each
vendor, and Google's brand terms ban monochrome treatments outright. A borrowed glyph would be a
worse lie than an absent one.

**Cross-pane dependency — there are two disconnect surfaces because they answer two different
needs, and neither is a lesser copy of the other.** The export sheet's Disconnect is *mid-journey
and urgent*: you are about to push a study to Miro, you notice the connected account is the wrong
client's, and you disconnect right there rather than land client A's quotes on client B's board.
Settings ▸ Accounts is the *overview*: what every integration's state is and — as much to the point
— that the integrations exist at all ("oh, you do Miro and Zoom too"). This doc previously called
Settings the only surface that *fully* disconnects. That was wrong once both paths converged, and it
was beside the point either way: **nobody using this is thinking about a server.** They are thinking
about which client's board they are one click from writing to.

What they are entitled to assume is that disconnecting *took*, from either door. That is why there
is one implementation and not two — `MiroConnectionStore.disconnect` (18 Aug 2026); the sheet kept
its own three-quarter copy until then. The missing quarter is the reason this pane takes
`serveManager` (`SettingsView.swift:96-113`): the token has **four** copies, not one — the Keychain
item, the server's in-memory session, the cached identity line, and the one no HTTP call can reach,
`BRISTLENOSE_MIRO_ACCESS_TOKEN`, which `overlayMiroToken` bakes into every sidecar at spawn and the
server resolves *before* the session. Clear the first three and a live process can still export.
`.bristlenosePrefsChanged` drains the parked sidecar and restarts the fronted one, which is what
makes the confirmation true; it is also why the sheet dismisses itself afterwards, since the restart
takes a fresh port and the sheet's own API client dies with the old one. This coupling belongs in
this doc and nowhere else.

**Localised through `desktop.accounts.*`** (`d0478b15`), and one seam is worth naming because it is easy to get backwards: `AccountAttention.sentence` takes `I18n` — `@MainActor func sentence(_ i18n: I18n)`, matching `CloudPlatform.windowTitle(_:)` — rather than reading a global. The state engine stays a pure function over values with no locale of its own; **the locale arrives with the render, not with the verdict**, which is what keeps the whole model testable without a view, a Keychain or a network. The vendor product names are the deliberate exception and are never keyed: they interpolate as `{{service}}` from `AccountService.displayName`, for the same trademark reason §9a gives for not redrawing the marks.

**MCP Agents (Tab 5) stays enumerated-but-not-sectioned by design** — its pane is specified in
`docs/design-mcp-extension.md` §3.7. Accounts, by contrast, had no home at all; its behavioural spec
is here and its per-platform sign-in flows are in `docs/design-cloud-import.md` §9.

## Preferences → serve process

`BristlenoseShared.overlayPreferences()` reads `UserDefaults` and injects values as environment variables into the `Process.environment` dictionary before launching `bristlenose serve`. **Don't-override-default guard**: `overlayPreferences` only emits an env var when the user has explicitly set the value (e.g. `BRISTLENOSE_WHISPER_LANGUAGE` only set when `lang != "en"`; concurrency only set when the user has touched the slider). This lets Python-side defaults stay authoritative when the user hasn't expressed a preference. See `BristlenoseShared.swift:221-287`.

API keys are injected via `ServeManager.overlayAPIKeys()` (C3, Apr 2026) — Swift reads Keychain via `Security.framework` (through the `KeychainStore` protocol; tests use `InMemoryKeychain`) and sets `BRISTLENOSE_<PROVIDER>_API_KEY` on the same env dict. Python never touches Keychain in this deployment; pydantic-settings reads the env vars directly. **Threat-model rationale** (from `ServeManager.swift:366-371` comment): env vars are visible to same-UID attackers via `ps -E`, but a same-UID attacker can already call `SecItemCopyMatching` directly; the net delta is small. Sandbox protects against *other* UIDs, not same-UID code execution. Documenting the residual risk honestly beats security theatre (keychain-access-groups wouldn't raise the bar against the real threat model). Full credential-flow discussion in `design-keychain.md` §Desktop (sandboxed) credential path.

`ServeManager` subscribes to `Notification.Name.bristlenosePrefsChanged`. When any writer posts this notification — not only a settings view; `MiroConnectionStore` and `MiroSheetModel` both do and a serve process is running, `restartIfRunning()` stops and re-starts with the new environment.

| Setting | UserDefaults key | Env var |
|---------|-----------------|---------|
| Active provider | `activeProvider` | `BRISTLENOSE_LLM_PROVIDER` |
| Model | `llmModel` | `BRISTLENOSE_LLM_MODEL` |
| Concurrency | `llmConcurrency` | `BRISTLENOSE_LLM_CONCURRENCY` |
| Whisper backend | `whisperBackend` | `BRISTLENOSE_WHISPER_BACKEND` |
| Whisper model | `whisperModel` | `BRISTLENOSE_WHISPER_MODEL` |
| Language | `language` | `BRISTLENOSE_WHISPER_LANGUAGE` |
| Azure endpoint | `azureEndpoint` | `BRISTLENOSE_AZURE_ENDPOINT` |
| Azure deployment | `azureDeployment` | `BRISTLENOSE_AZURE_DEPLOYMENT` |
| Azure API version | `azureAPIVersion` | `BRISTLENOSE_AZURE_API_VERSION` |
| Ollama URL | *(parent process env only)* | `BRISTLENOSE_LOCAL_URL` |
| Appearance | `appearance` | *(neither — WKWebView inherits `NSApp.appearance`)* |

> **Note on `BRISTLENOSE_LOCAL_URL`:** the desktop GUI hardwires the Ollama URL (no editable field). `overlayPreferences` therefore reads only the **parent process environment** for `BRISTLENOSE_LOCAL_URL` and forwards it to the sidecar if set — there's no UserDefaults round-trip. CLI users and CI keep the override path; desktop alpha users are locked to localhost. See `ServeManager.swift:351-357`, `BristlenoseShared.swift:122-127`, and `LLMSettingsView.swift` `hardwiredOllamaURL` constant.
| API keys | **Keychain** | *(Python reads directly)* |

## Provider status model

`ProviderStatus` in `LLMProvider.swift` — normalised account status. Mapping
from HTTP response → status lives in `LLMValidator.classify(provider:status:)`.

| Status | Dot | Detection |
|--------|-----|-----------|
| `.online` | Green | 2xx from test call; OR cached `.ok` verdict for current key; OR Anthropic 4xx ≠ 401/403/402/429 (auth-before-payload, robust against haiku-model deprecation); OR Ollama reachable with at least one model pulled |
| `.notSetUp` | Grey | No key in Keychain (or empty Ollama URL) |
| `.invalid` | Red | 401/403 from test call; OR Azure 404 (endpoint/deployment not found — message points at endpoint, not key); OR Azure URL missing https:// scheme |
| `.unavailable` | Orange | 429/network error/timeout; OR Azure key entered but endpoint blank (started-but-incomplete) — transient/unverified, survives offline via cache |
| `.outOfCredit` | Orange | 402 from test call — an *observed* negative (not a transient miss). Sticky and shown; deliberately NOT cache-masked back to `.online`. `LLMProvider.swift:238` |
| `.checking` | Spinner | Validation in progress — rendered as `ProgressView().controlSize(.small)` in both sidebar and detail pane (Mail "Status: Connecting…" pattern) |

Activation is gated on `canActivate`, **not** a live `.online`: `.online`,
`.outOfCredit`, and `.unavailable` all activate (key present, not
confirmed-bad). Only `.notSetUp` (no key), `.invalid` (confirmed-bad
credentials), and `.checking` block. Previously-validated keys survive
offline because the cache fallback promotes them back to `.online` (see
Validation flow below); `.outOfCredit` is the deliberate exception — a 402
is an observed negative, so it stays sticky rather than being cache-masked.

## Validation flow (Beat 3)

`LLMValidator` does round-trip credential validation natively in Swift —
not via the sidecar — so Settings works before any project is loaded.
URLSession.ephemeral, 5s timeout, per-provider auth-check endpoints
(Anthropic POST `/v1/messages` `max_tokens=1`, OpenAI GET `/v1/models`,
Azure GET `/openai/deployments`, Gemini GET `/v1beta/models`,
Ollama GET `/api/tags`).

**Verdict cache.** Per-provider entries in `UserDefaults` keyed by truncated
SHA-256 of the credential (8 bytes, ~5×10⁻¹⁰ collision rate at single-entry
scale). Stores three fields: `_keyHash`, `_status` (`ok` / `invalid`),
`_lastCheckedAt` (ISO 8601). Only definitive verdicts (`.online`,
`.invalid`) write the cache; transient `.unavailable` never overwrites.
The full credential lives in Keychain — UserDefaults stores opaque
identity, not secret material. (Threat-model: a same-UID process can
fingerprint provider config + rotation history but cannot recover the key.)

**Offline survival.** When validation returns `.unavailable` (timeout,
no connectivity, 402/429) AND the cache holds a definitive verdict for
this exact key, the cache wins: `.online` from cache survives a flaky café
connection; `.invalid` from cache survives an offline relaunch. The user
keeps the radio activatable on a previously-good key without a fresh
network round-trip. Net guarantee: the dot reflects last-known-truth, not
"can we reach the network right now."

**TTL gating.** `LLMSettingsView.cacheTTL = 60s`. `revalidateAll()` skips
`kickOffValidation` for cloud providers whose cache entry is younger
than the TTL — opening Settings 20×/day to tweak concurrency doesn't
hammer four LLM APIs. Ollama is exempt (localhost is cheap, always
probed).

**`.checking` is always shown during validation.** `kickOffValidation`
synchronously sets `statuses[provider] = .checking` before the await.
SwiftUI batches state writes within the same tick, so even when the cache
pre-set the dot to `.online`, the rendered transition is dot → spinner →
settled — never a misleading green-flash-red on a rotated key.

**"Last verified" UI.** Detail pane shows a `.tertiary`-coloured "Last
verified Xm ago" line under the status row when a definitive verdict
exists. `RelativeDateTimeFormatter` for the relative string; a 30s ticker
keeps the label honest as time passes.

**Coverage gap (parked → superseded).** `LLMValidator` runs only when
Settings is open or on Save. There's no app-wide background revalidation —
a key rotated server-side while the user is offline isn't detected until
they next open Settings. The original follow-up proposed `NWPathMonitor` +
a **toast** on cached-`.ok` → fresh-`.invalid` transitions. **The toast is
withdrawn** (toasts are an attention-theft pattern — see project memory);
the replacement design is inline status that's eagerly truthful on open
plus a refocus-recheck, captured in §"Provider status lifecycle (planned)"
below. `NWPathMonitor` survives as the reachability gate in that design.

## Validation invariants

These contracts protect against regressions seen during Beat 3b QA:

**`applyPresenceAndCache` never sets `.checking`.** Only `kickOffValidation`
does — and it sets `.checking` synchronously before the await. The
presence-and-cache reader is purely a "show last-known state" function. If
it ever wrote `.checking` itself, any code path that calls `refreshStatuses`
without following up with `kickOffValidation` (radio-toggle, active-toggle)
would strand the provider in a forever-spinner. Masked for cloud providers
by the verdict cache; immediately surfaced for Ollama because Ollama doesn't
use the cache. Comment block at `LLMSettingsView.swift:629-637` is the
load-bearing record.

**Azure revalidation fires on focus blur, not per-keystroke.** Typing
`https://my-instance.openai.azure.com` would otherwise issue ~30 validation
requests, each one a billed Azure call plus a rate-limit hit. `revalidateAzure()`
(`LLMSettingsView.swift:524-536`) is wired through `@FocusState` for the
endpoint and `apiVersion` fields with `onSubmit` (Enter) as the secondary
trigger. Per-keystroke `.onChange` is retained only for the prefs notification
(cheap UI signal, no network round-trip).

**Consent recorded BEFORE prefs notification on Ollama setup.** When the
"Use Ollama Instead" path completes (`AIConsentView.swift:60-69`), `recordConsent`
runs first, then `activeProvider` is set, then `bristlenosePrefsChanged`
posts. If the order were reversed, a prefs-change-driven serve start could
fire pre-consent. Consent gate downstream still catches it — but the
ordering is deliberate, not incidental.

Status is orthogonal to active selection. Providers don't expose balance, free-tier, or trial status via API — we report only what we can detect.

## Provider status lifecycle (planned)

> **Status: partly shipped (trued 2026-07-26).** This section was written
> design-forward. Several of its targets have since shipped and are now the
> *reality*, not the intent — do NOT read the old "shipped behaviour is the
> defect" framing against them:
> - ✅ **Shipped:** the eager, self-refreshing board (`refreshAllStatuses` /
>   `revalidateAllStale`, `LLMSettingsView.swift:74`); activation-acts-on-truth
>   via `canActivate` (`:677`, `LLMProvider.swift:279`); the 402-masking split
>   into a sticky `.outOfCredit` (`LLMProvider.swift:238`).
> - ⬜ **Still design-forward:** the shared rung-3 `probe(provider, model)` unit,
>   the offline three-bucket grey ("worked before" vs "never configured" vs
>   "not set up"), and the `NSApplication.didBecomeActive` refocus-recheck for
>   credit top-ups.
>
> The product principle below (a truthful, effortless board) still holds as
> intent for the unshipped items.

### Product principle: the board is truthful and effortless

The LLM tab reads as a **dashboard of status lights**, so it must *be* one.
Two failures, observed in alpha QA, are non-negotiably wrong:

1. **A board that lies** — lights that are unlit because the app was lazy, not
   because the state is unknown. The user reads the board as truth; it must be.
2. **"Rocks to look under"** — making the user click each row to make its light
   come on. That hands the app's own job back to the user.

The user's correct expectations: **with a network, a live, real-time view that
keeps itself honest with zero clicks; history leveraged so a previously-good
provider is silently and magically reconfirmed.** The *only* genuinely
ambiguous case is no-network — and even there, local history distinguishes
"worked before" from "never configured." **The user never pays, sees, or
manages the cost of keeping the board honest.**

### The cost ladder (backstage only)

These "costs" are the *implementation's* to absorb and hide — never a
user-facing concept. They exist to explain *which technique runs when*.

| Rung | Operation | Cost | Proves | Cannot tell us |
|------|-----------|------|--------|----------------|
| **0. In-memory** | read cached verdict (`verdictStore`) | free, instant, offline-ok | what we concluded last time | anything current |
| **1. Local API** | Keychain `SecItemCopyMatching` | a syscall; real cost = **prompt risk in unsigned/dev builds**; offline-ok | a credential *exists* (+ value to hash) | is it valid? endpoint up? credit? model real? |
| **2. Network auth** | minimal auth round-trip (`LLMValidator.buildRequest`) | ~1s, needs net, < $0.0001 | endpoint *reachable* + key *authenticates* (200 vs 401) | credit? model valid? |
| **3. Real work call** | structured `analyze()` against a fixture | fractions of a cent, needs net | credit OK (402 vs 200) + model exists (vs 404) + model does structured output → *a real run will succeed* | — this **is** ground truth |

**Rung 2→3 is a wall the providers built, not one we can engineer around.**
They check auth (401) *before* billing (402) — so a 200 on rung 2 is
structurally incapable of reporting credit. Note the asymmetry in the shipped
rung-2 pings: Claude uses `POST /v1/messages max_tokens=1` (brushes billing →
*would* catch a 402), while ChatGPT/Gemini/Azure use `GET …/models` (pure auth
→ a 200 says nothing about credit). So a green light honestly means **"set up ·
key valid · reachable,"** not **"will produce work."** Copy must not over-claim.

### Online behaviour — live, self-reconfirming, zero clicks

On Settings open *with* a network:

1. **Paint instantly from history (rung 0).** Every configured provider shows
   its last-known verdict immediately — no spinner wall. This is the
   "leverage history" the user expects.
2. **Silently reconfirm in the background (rung 2) for *all* rows, not just
   selected+active.** Lights settle into present-tense truth over ~1s. This is
   the "silently and magically reconfirmed" behaviour.

This **replaces the lazy-load policy** (which only read selected+active and
left every other row grey-by-laziness). The lazy-load's sole justification was
the "3× Keychain prompt cascade" (sandbox walk #7) — which Apple's documentation
and prior art say a properly-signed build **won't** exhibit. The cascade is a
*legacy file-based keychain* symptom: that keychain binds each "Always Allow"
grant to the binary's **code-directory hash**, so any rebuild or re-sign
invalidates every grant and re-prompts (Apple TN3137; steipete/CodexBar #585 hit
and fixed this exact thing). We already migrated off it (2 Jun, `8b2ef51`):
`KeychainHelper` passes `kSecUseDataProtectionKeychain` on every operation, with
a team-scoped `keychain-access-groups` entitlement
(`$(AppIdentifierPrefix)app.bristlenose`) and no biometric `SecAccessControl`.
The data-protection keychain validates by **Team ID, not binary hash**, has no
ACLs, and does **not** prompt an app reading its *own* access-group items — so
eager all-providers reads are expected to be silent on any team-signed build.

**Verification gate (narrowed):** the question is no longer "is eager viable" —
the documented default is *no prompts*. It is "**is the running build ad-hoc?**"
Ad-hoc (`None` + `Sign to Run Locally`) has an empty `$(AppIdentifierPrefix)`,
which breaks the access group and falls back to the legacy keychain → prompts.
Confirm the build is team-signed (`Z56GZVA2QB`); TestFlight/MAS builds always
are. **Fallback if a prompt ever appears on a signed build** (the surprise
case, now requiring explanation rather than expected): render the rung-0 cache
for all rows (it lives in UserDefaults, not Keychain) and defer the Keychain
read.

**Do not over-poll billing on open.** Upgrading the open-time reconfirm to a
rung-3 (billing-touching) call for every provider buys marginal extra truth
(credit) at the cost of token spend, rate-limit risk, and "why is it calling
Anthropic every time I open Settings." Credit only *bites* at two moments, both
handled truthfully there: refocus-after-paying and the Run itself. Green =
"valid & reachable" is honest enough provided the Run is never gated on a stale
light.

> **Decided (2026-06-06, Martin):** no rung-3/billing call on Settings-open.
> Open-time reconfirm stays at rung 2 ("is the endpoint alive + does the key
> authenticate"). Simpler is better at this stage; we don't spend even sub-cent
> amounts just to light up lights with marginally more certainty. Credit truth
> is bought only at refocus-after-paying and at Run.

### Status indicator vocabulary — decided (2026-06-06, Martin)

The status light is **colour + the text label, nothing else**. No per-state
glyphs. Two independent reasons, either sufficient:

1. **Every glyph is a "what does that symbol mean?" tax.** The label already
   says "Online" / "Out of credit" / "Invalid key" — a glyph adds a thing to
   parse, not information. ("Absence is information — no glyph for the normal
   case.")
2. **Two ticks, one row.** The sidebar row *already* carries a **blue**
   `checkmark.circle.fill` for the *active/selected* provider. A **green**
   status checkmark on `.online` would put two ticks on the same line — blue
   "selected" beside green "OK" — a real collision of meanings. So `.online`
   stays a plain green dot. (This kills the glyph-every-state option outright,
   independent of reason 1.)

Accessibility: for a colour-blind user the **text label** carries the meaning
(the two ambers read "Unavailable" vs "Out of credit"). This is an accepted
**deferral** for TF/alpha — the one tracked a11y debt — not a resolution. If a
shape-per-state is ever added, it must dodge the blue/green tick collision above.

**No "settling" indicator** during background reconfirm ("too cute"). The dot
just changes if the verdict changes; the silent reconfirm is the whole point of
the eager board.

**`.checking` (the spinner) stays — and earns its keep at exactly one moment:
first validation on key paste.** Key entry is the high-anxiety step (a trailing
space, a fat-fingered paste — everyone has the story), so the user wants live
"Checking…" feedback *there*. Hence the split in `kickOffValidation`:
`silent: false` on the paste/`saveAPIKey` path (spinner shown — reassurance),
`silent: true` on background reconfirm of an already-cached provider (no spinner
wall).

### Offline behaviour — the only ambiguous case; three buckets

> **Decided (2026-06-07, Martin): leave as shipped for TF — no grey-when-offline.**
> The board keeps its last-known colour when the network drops: **green stays
> green, red stays red** (already the shipped behaviour — `resolveStatus` defers a
> transient `.unavailable` to the cached verdict). The three-bucket grey model
> below is **deferred, not built** — kept as the record of the reasoning, not the
> plan of record. Two load-bearing reasons, both Martin's:
>
> 1. **Don't diverge text from colour, and don't hide the truth.** If the label
>    says "Invalid key" the dot must stay red — greying it offline would both
>    split text-from-colour *and* hide the important fact that the key was invalid
>    last time we tried. That's worse than a slightly-stale green.
> 2. **Bristlenose is a Mac app; no-network is a normal ambient state.** Verbatim:
>    *"apple mail just doesn't care — it's a mac app on your mac and the outbox
>    just has 1 queued mail that can't go so it sits there… the lack of internet
>    is a normal state for a mac app, it's on your local device, it will send when
>    it gets network. that's bn.app. gmail is a bit more needy, and has a global 'I
>    would be happier with internet' but it doesn't change the state of the detailed
>    preference pane based on no network. for TF we are fine."* A global no-network
>    condition isn't worth dramatising per-provider: the lights report **credential
>    validity** (last-known truth); the transient "couldn't reach it just now" rides
>    as a hover caption, not a colour change.

With no network we cannot reconfirm, but local state (rung 0/1) still
distinguishes a track record from its absence. Render three buckets, not the
shipped green-or-grey collapse:

| Offline state | Local signal | Render |
|---------------|--------------|--------|
| **Worked before** | cached `.ok` exists | confident-but-dimmed: *"ready · last confirmed Tue · offline"* — history honoured, **not** a live green that implies "runnable now" |
| **Never successfully configured** | key present, no successful verdict ever (e.g. pasted while offline) | neutral: *"set up — never confirmed"* |
| **Not set up** | no key | grey *"not set up"* |
| **Known bad** | cached `.invalid` (real 401) | red, sticky — survives offline |

Connectivity is a **caption on the neutral ladder, never its own colour**
(colour belongs to credential validity). Greying-out-on-offline is *wrong* — it
discards a true fact (the key is good) to express a different one (unreachable
now); a caption carries the latter without destroying the former.

#### Resolved (2026-06-07) — green = *validity*, kept as shipped (see Decided box above). Original analysis retained:

Martin challenges the "confident-but-dimmed **green** when offline + cached `.ok`"
row above. The crux is what the colour channel *means*:

- **Validity reading (table above):** colour = credential validity, which is
  network-independent. A good key is a good key offline → stays green, caption
  notes unreachability. Doesn't discard the true fact.
- **Runnability reading (Martin's lean):** green = "I can run *now*." A cloud
  provider offline can't run now, so green over-claims → render **grey**
  ("ready · last confirmed Tue · offline"), reserving green for genuinely-
  runnable. **Local models (Ollama) are the exception** — network-independent,
  so they *stay green* offline.

Note the asymmetry Martin draws, and it's deliberate: **red survives offline**
(a known-`.invalid` key won't become valid by reconnecting — greying it would
imply "flip the wifi and it might go green," which is the lie), while **green
does not** survive offline for cloud (can't claim runnable). That puts two
different questions on one colour channel — green answers "runnable now," red
answers "credential valid." Coherent for users ("green = go"), but it breaks the
single-axis "colour = validity" rule the table above asserts. The purist counter
(raised and noted): *no network = make no claims*, which would grey everything
unconfirmable — but that throws away useful local truth (the red, and the track
record). **Resolution pending Martin's ponder.**

Two sub-decisions ride on it:

1. **`no key` glyph.** Today grey. Martin: maybe a **hollow/open circle** (or
   nothing) instead — so "never set up" is visually distinct from "set up but
   unconfirmed/offline," which would *also* be grey under the runnability
   reading. (Cf. project memory "Absence is information — no glyph for the
   normal case": an empty slot arguably *is* the normal/empty case.) If both
   "no key" and "cached-ok-offline" are grey dots, the caption is the only
   differentiator — the has-key breadcrumb (Finding 18) becomes load-bearing.
2. **`key + no cache`** = a credential exists (rung-1 read found a value) but no
   verdict was ever recorded — e.g. key pasted while offline, or written by the
   Python CLI and never validated by the Swift side, or cache evicted. Renders
   as the "set up — never confirmed" bucket: grey, distinct from both "no key"
   (nothing in Keychain) and "cached `.ok`" (validated before). It means
   *"we have a key but have never seen it work."*

### Credit / 402 — fix the masking, then re-check at the right moment

**Bug to fix:** out-of-credit (402) currently maps to `.unavailable`, and the
offline-survival rule (`cache wins on .unavailable`) promotes it back to green.
A credit-exhausted provider shows green while runs fail on quota. The fix is to
**split `.unavailable` by provenance:**

- **Observation *failed*** (timeout / no network / can't reach) → trust the
  cache; green stays green. ✅ (correct today)
- **Observation *succeeded* and reported a negative** (402 out of credit) →
  **show it** (amber "top up · re-check"); do *not* fall back to stale green.
  402 is a fresh true fact, not a failed observation. (429 rate-limit is
  borderline — self-clears in a minute — so masking it behind cache-green is
  defensible; 402 is not.)

**Top-up detection is fundamentally not free** (rung 3, see the wall above), so
don't chase a free signal. Fire the unavoidable sub-cent re-check at the
**natural moment**: `NSApplication.didBecomeActive` → re-check **only**
providers currently in a transient-failure state, **and** only if their cache
is stale (TTL debounce). Pay at the provider's console → click back to
Bristlenose → the amber row silently goes green. Plus a manual "Re-check"
control as the explicit fallback. **The Run is never gated on a stale light** —
if the user has paid and hits Run, it works; the light is a hint, the run is
truth.

**Known limitation — cached green is *network-validity*, not *credit-confirmed*.**
You cannot observe a 402 you never received: if an account runs out of credit
while the user is **offline**, every reconfirm times out, the 402 is never seen,
and the cache stays `.ok` → the row shows green and is activatable, yet runs will
fail on quota. This is a logical limit of credit-detection-requires-network, not
a defect, and it's the backstop, not the front line: the now-named run-time quota
message ("Claude is out of credits…") surfaces it clearly at Run. We accept it
rather than chase a free offline credit signal that doesn't exist. (How a cached
`.ok` *renders* while offline — confident green vs dimmed — is the open
green-vs-runnable question above; this limitation is one input to it.)

### Activation must act on truth, not on a lazily-empty status

**Root-cause record (Defect L):** the radio-activation guard
(`guard statusFor(provider).isConfigured else { return }`) and the
`.disabled(!isConfigured && …)` modifier silently no-op when the target
provider's status is `.notSetUp` — which, under lazy-load, it always is until
the user clicks into the row. So clicking a fresh provider's radio first does
nothing and `activeProvider` never persists → runs hit the previously-active
provider. **This is the same lazy-status defect as the "dashboard of lies."**
Making the board eagerly truthful (online section above) gives the guard a real
status to act on and fixes activation as a side-effect — *one change, two
payoffs.* For a provider whose status is still cold at click time, the radio
should **load-then-activate** (run presence-and-cache for that provider on
click, activate once it resolves `.online`), never swallow the click.

### `overlayPreferences` — never inject a model without a provider

**Root-cause record (Defect M, fixed):** the env overlay had an `else if` arm
that injected the bare global `llmModel` key when `activeProvider` was unset —
so Python fell back to its *default* provider (anthropic) but ran it against
whatever model the global key last held (e.g. `gpt-4o` from a prior ChatGPT
session), producing a cross-provider 404 (`model: gpt-4o` rejected by
Anthropic). **Invariant:** only inject `BRISTLENOSE_LLM_MODEL` when
`BRISTLENOSE_LLM_PROVIDER` is also set; when no provider is active, inject
neither and let Python default both coherently. The global `llmModel` key is a
footgun — it tracks the active provider's model only while `syncGlobalModel`
runs; spawning off it after a provider revert produces a mismatch. Prefer the
per-provider `llmModel_<provider>` keys as the source of truth.

### The rung-3 probe is one reusable unit

Key-entry validation, refocus-recheck, and the maintainer "weather station"
(`scripts/llm-weather.py` — provider × every-known-model sweep, see
`docs/design-llm-weather.md` if/when written) are **the same operation**:
`probe(provider, model) → ok / 404-unknown-model / 402-no-credit / auth /
schema-malformed / unreachable`. Build it **once** as a reusable unit; call it
from all three sites. Key-entry currently does *not* do rung 3 (it pings a
fixed endpoint/model, not the chosen model) — so a typo'd-but-dead model name
isn't caught at entry; adding the rung-3 probe at key-entry is deferred but
cheap to reverse once the probe exists.

### Error copy when a run fails

- `humanSummary(for:)` returns provider-less strings ("LLM provider rejected
  the request"). Thread the active provider's display name through →
  **"Claude rejected the request."**
- `degradedBody` (`ProjectDiagnosticPopover.swift`) renders the captured `message`
  *and then unconditionally* appends "Detailed cause not captured." — show
  `noStructuredCause` **only when `message` is empty**. The cause *is* captured
  (event log + `last-run-failure.log`); surface the "Provider says: …" detail
  and explain a 404 plainly ("that model name isn't valid for this provider").
