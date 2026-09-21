---
status: partial
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20
---

# Locale negotiation — desktop vs web

**Status (20 Sep 2026): the decision below was REVERSED in shipped code, and no doc
recorded it.** The original text is preserved unedited — it is the only written statement
of the position — but do not read it as describing the app.

> ### ⚠️ What actually shipped, measured at HEAD
>
> | The decision said | What ships |
> |---|---|
> | "**No in-app language picker** in Settings → Appearance" | A `Picker` listing every supported language by autonym — `desktop/Bristlenose/Bristlenose/AppearanceSettingsView.swift:63` |
> | "Set `UIPrefersShowingLanguageSettings = YES` in `Info.plist`" | **Never set.** Zero hits across every `.plist`, `.swift` and `.pbxproj` in the repo |
> | "`I18n.swift` reads `Bundle.preferredLocalizations(from:forPreferences:)`" | **Nothing in `desktop/` reads the OS language preference at all** — zero hits for `preferredLocalizations`, `AppleLanguages` or `Locale.preferredLanguages` |
> | "Settings → Appearance includes a hint paragraph pointing to System Settings" | Never written. `settings.language.description` (`locales/en/settings.json`) says only that report content is not translated |
>
> ### 🔴 The live consequence — this doc named the bug, and the bug is what shipped
>
> The doc argues against an in-app picker partly because of a race it says we had already
> hit: *"We had this bug — System Settings → Apps → Bristlenose → Korean was being
> silently ignored because we read our private `language` key, not `AppleLanguages`."*
>
> **That is the current code path.** Four production sites read the private key and fall
> back to a hardcoded `"en"`:
>
> - `I18n.swift:55` — `UserDefaults.standard.string(forKey: "language") ?? "en"`
> - `BristlenoseShared.swift:256`
> - `BridgeHandler.swift:596`
> - `AppearanceSettingsView.swift:14` — `@AppStorage("language") … = "en"`
>
> **No production code seeds that key from the system locale** — the only writes to it
> anywhere are in `BristlenoseTests/ServeManagerEnvTests.swift:235,241`.
>
> So on a fresh install on a Korean Mac the key is absent, resolves to `"en"`, and the app
> **boots English** — directly contradicting this doc's "Do nothing → follow system.
> Korean Mac boots Korean." The user must find the in-app picker to get their own language.
>
> ### It is already tracked, and the fix is already decided
>
> **Correction to this banner's first draft, which claimed the reversal was recorded
> nowhere. It is.** The maintainer's private planning notes carry it as a Beta item,
> naming the same evidence independently — `I18n.swift:55`, the `?? "en"`, and the
> observation that this re-introduces the very race this doc documents as already fixed —
> plus a decided fix (**Option A, 2 Jul 2026**: seed from
> `Bundle.preferredLocalizations(from:)`, read/write `AppleLanguages`, drop the private key
> with a one-shot migration, keep `UIPrefersShowingLanguageSettings` for discoverability)
> and a full implementation brief.
>
> So the shipped picker is **not** an undocumented reversal — it is a known defect with a
> planned repair. What this doc got wrong is narrower: it says "approved, pending
> implementation" for a delegation design that was never implemented, while a picker was
> built instead.
>
> _The first draft searched `docs/` and the CLAUDE.md files and concluded "recorded
> nowhere". The record was in the gitignored maintainer-only notes — outside the corpus
> that was scanned. Scope of a search is not scope of the world._
>
> **Do not archive this doc yet.** The planned fix re-trues it: once the OS-canonical
> picker lands, the delegation design below becomes half-true again rather than wholly
> superseded, and the private notes' own breadcrumb says to re-true it *after* the fix.

---

_Original decision text, 5 May 2026, unedited below._

**Status:** approved 5 May 2026, pending implementation in branch `locale-system-delegation` (sibling to `i18n-text-sweep` which handles the unrelated mechanical translation gaps).

## Status — partly implemented, 21 Sep 2026

The decision below ("delegate to System Settings, no in-app picker") was never
implemented, and this doc's own correction banner above records that. What
shipped instead was an in-app picker writing a private `language` key, and
nothing reading the OS preference at all.

**What landed on 21 Sep 2026, and why it is a middle path rather than the
decision as written:**

- **The app declares its localisations.** 22 `.lproj` directories with an
  `InfoPlist.strings` apiece; Xcode picked them up into `knownRegions` on its
  own. Verified in the built bundle. This is the load-bearing half: without it
  macOS treats the app as English-only whatever `AppleLanguages` says.
- **The picker writes `AppleLanguages`** in the app's own domain, alongside the
  private key. That is the same key System Settings ▸ Apps ▸ Bristlenose ▸
  Language writes, so the two controls agree rather than compete.
- **`I18n.configure` falls back to `Bundle.preferredLocalizations`** when the
  private key is unset — so a *fresh* install honours the user's own language
  preferences, which is the part of the decision below that was always right.
  An existing install keeps its key, so nobody's language changes under them.

**The picker was kept, against the decision below.** It ships, it is registration
site 9 for a new language (`docs/adding-a-language.md` Step 8), and removing a
working control to satisfy a doc is the wrong order. The decision's substance —
the OS is the source of truth — is honoured by writing `AppleLanguages` rather
than by deleting the UI.

**What this buys, and it is the reason to do it at all:** File, Edit, View,
Window and Help are AppKit's menus, not ours, and so is every standard item
inside them — Minimize, Zoom, Bring All to Front, Cut/Copy/Paste, Enter Full
Screen. They rendered English in every locale because the app declared no
localisations. They now come back in **Apple's own reviewed wording**, which is
the `Choose`-button / TCC-prompt principle one level up: look it up, do not
translate it. The glossary already carried hand-written `Window,ウインドウ,ja`
and `Help,ヘルプ,ja` rows — evidence someone once reached for the wrong route.

**Takes effect at next launch, deliberately.** AppKit builds the menu bar once
per process. The app can be mid-analysis, so it does not relaunch itself; our own
chrome still switches live. Telling the researcher that in the UI is the one
piece still owed — it needs a new key in 21 locales and a decision about what to
do when a run is in flight.

---

## Two deployments, two answers

Bristlenose ships in two surfaces with different platform conventions for "what language should the UI be in":

| Surface | Canonical control | Our role |
|---|---|---|
| **macOS desktop app** | `System Settings → Apps → Bristlenose → Language` | Delegate. No in-app picker. |
| **CLI `bristlenose serve` (real browser)** | Browser/OS settings, but no per-site override on web | Provide an in-app picker. |

The desktop case is the interesting decision; the web case is conventional.

## Desktop — delegate to System Settings

### Decision

- **No in-app language picker** in Settings → Appearance.
- **`I18n.swift` reads `Bundle.preferredLocalizations(from:forPreferences:)`** on every launch — Apple's BCP 47 lookup matcher reading the user's `AppleLanguages` preference.
- **Set `UIPrefersShowingLanguageSettings = YES` in `Info.plist`** so the System Settings → Apps → Bristlenose → Language section is visible even for users with only one preferred language configured globally.
- **Settings → Appearance includes a hint paragraph** pointing to the System Settings location, translated in all six locales.

### Behaviour the user gets

- **Do nothing → follow system.** Korean Mac boots Korean. Switch macOS to Japanese later → next launch boots Japanese. No state of ours, no stale choice.
- **Want this app different → System Settings → Apps → Bristlenose → pick.** Mail stays Korean, Bristlenose flips to French. Persists; macOS owns the storage.
- **Undo override → System Settings → Apps → Bristlenose → "System Default".** App snaps back to following the OS.
- **Unsupported OS language (e.g. Vietnamese) → English fallback.** Apple's matcher walks `Locale.preferredLanguages` past unsupported entries.

### Why this and not an in-app picker

**Strong evidence the in-app picker is the wrong call:**

- **Apple's own apps don't ship one.** Mail, Notes, Reminders, Safari, Calendar — all rely on the system control. Loved indie Mac apps (Things, Reeder, Bear, Tot, Soulver) match. Mac good-taste convention is settled.
- **Two pickers diverge.** System Settings writes `AppleLanguages`; an in-app picker that writes a private UserDefaults key (or even reads/writes `AppleLanguages` itself) creates a race between two controls users will discover at different times. We had this bug — System Settings → Apps → Bristlenose → Korean was being silently ignored because we read our private `language` key, not `AppleLanguages`.
- **The OS-canonical mechanism gets free correctness.** BCP 47 lookup, script subtags (`zh-Hant` ≠ `zh-Hans`), region (`pt-BR` ≠ `pt-PT`), reset semantics, multi-language priority — all already implemented in Cocoa. Re-implementing is a re-implementation tax with no upside.

**Real evidence the System Settings control is poorly known / discoverable:**

- **The per-app language section is hidden by default for users with only one preferred language.** [Apple Developer Forums #721302](https://developer.apple.com/forums/thread/721302) — a Korean-only Mac user opens System Settings → Apps → Bristlenose and sees nothing about language. They'd need to first add a second preferred language globally for the section to appear.
- **Apple themselves shipped an opt-in fix.** [`UIPrefersShowingLanguageSettings`](https://developer.apple.com/news/?id=u2cfuj88) is an `Info.plist` key that forces the per-app language section to always show. The existence of the key is Apple's acknowledgement that the default invisibility is a design problem.
- **Ventura's System Settings redesign is widely panned.** Lapcat Software ([Why Ventura System Settings is bad](https://lapcatsoftware.com/articles/SystemSettings.html)), Macworld ([needs a massive overhaul](https://www.macworld.com/article/836295/macos-ventura-system-settings-preferences-problems.html)), Eclectic Light Co ([a turn for the worse](https://eclecticlight.co/2022/09/20/system-settings-in-ventura-a-turn-for-the-worse/)). Things you used to find in one click are now buried.
- **Major cross-platform apps don't trust it.** Slack, Zoom, Firefox, VS Code all ship in-app pickers. The cross-platform-consistency excuse is real; the "couldn't trust the system control" subtext is also real.

**The reconciling move** is to set `UIPrefersShowingLanguageSettings = YES` so the per-app section appears unconditionally. This converts "delegate to a control nobody can find" into "delegate to a control Apple has prepared to be findable." We then get:

- OS-default-just-works (95% case)
- Per-app override (5% case)
- Reset to default (0.5% case)

… without writing or maintaining a single line of picker UI ourselves.

### What we delete in this transition

- The language `Picker` in `AppearanceSettingsView.swift` (~30 lines)
- The `setLocale(_:)` call site (~5 lines)
- Locale keys for the picker (`appearance.languageLabel`, `appearance.languageHint`, language option labels — × 6 locales)
- The "explicit-choice-wins precedence ladder" mental model from prior plan iterations — the OS owns it now

### What we add

- One key in the generated `Info.plist`: `INFOPLIST_KEY_UIPrefersShowingLanguageSettings = YES` added to the `Bristlenose` target's build settings in `desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj`. (The project uses Xcode's `GENERATE_INFOPLIST_FILE = YES` flow — there's no separate `Info.plist` file in the source tree; keys flow through `INFOPLIST_KEY_*` build settings.)
- One line in `I18n.swift`: `Bundle.preferredLocalizations(from: Array(supportedLocales), forPreferences: nil).first ?? "en"`
- One translated hint paragraph in `AppearanceSettingsView.swift` and six locale files: *"Bristlenose follows your macOS language. Change it in System Settings → General → Language & Region → Apps → Bristlenose."*
- One-shot migration: `UserDefaults.standard.removeObject(forKey: "language")` on launch, to clear the stale key from existing installs that wrote it under the old code path.

## Web (CLI `bristlenose serve`) — keep the in-app picker

### Decision

- **Settings modal in the React SPA keeps a language dropdown** (status quo).
- **`frontend/src/i18n/LocaleStore.ts` precedence:** stored localStorage choice → `navigator.language` ∩ supported → English fallback.
- **Auto-detect uses BCP 47 lookup, not naive prefix-strip on `-`** (same `zh-Hant` / `zh-Hans` correctness as desktop). Audit during the desktop branch; if `LocaleStore` does prefix-strip, file a sibling fix.

### Why keep the picker on the web side

- **Browsers have no per-site language override** the way macOS has per-app. The browser-wide `navigator.language` is set in OS or browser preferences and applies to every site. A user who wants Bristlenose specifically in French on an English Mac browser has no system-level path; they need our picker.
- **Linux/Windows users running `bristlenose serve` from CLI** have OS locale conventions (`LANG`, etc.) that the browser already negotiates into `navigator.language`. The OS-default-just-works case is covered by `navigator.language`. The picker is the only escape hatch.
- **Embedded mode (WKWebView in the desktop app) hides the web picker** already (see `docs/design-i18n.md`). Native Settings is the single control point in desktop. With the desktop picker gone, the web picker is hidden in WKWebView and shown only in real-browser CLI serve mode — which is exactly right.

## Open follow-ups

None block alpha. Tracked outside this doc:

- Frontend `LocaleStore.ts` BCP 47 lookup audit (sibling-branch material).
- "Reset to system default" UX in the web Settings modal (matches `localStorage.removeItem` semantics; the analogue of System Settings → Apps → System Default for the web case).

## See also

- **i18n design overall:** `docs/design-i18n.md` (terminology, namespaces, six-locale fill order).
- **Desktop Settings architecture:** `docs/design-desktop-settings.md` (Appearance pane composition).
- **Apple's developer note:** [How to support per-app language settings in your app](https://developer.apple.com/news/?id=u2cfuj88) — the canonical documentation for the `UIPrefersShowingLanguageSettings` key and the System Settings → Apps mechanism.
- **Apple Developer Forums:** [Localization settings hidden if only 1 preferred language](https://developer.apple.com/forums/thread/721302) — the discoverability bug we're working around.

## Decision log

- **5 May 2026 — Approved.** Earlier plan iterations proposed a three-layer precedence ladder with our own picker preserved. Multi-agent review flagged the duplication-of-system-feature problem. Web research surfaced the `UIPrefersShowingLanguageSettings` key, which dissolved the discoverability counter-argument. Final design: delete picker on desktop, keep on web, set Info.plist key.
