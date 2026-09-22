---
status: partial
last-trued: 2026-09-22
trued-against: HEAD@main on 2026-09-22 (52bfc67d), measured against a Debug build of that tree
---

# Locale negotiation — desktop vs web

**Status (22 Sep 2026): the decision below was reversed, and then, on the evening of
21 September, half-implemented after all.** The original text is preserved unedited — it
is still the only written statement of the position — but do not read it as describing the
app. The banner that stood here from 20 Sep is also superseded: it was written hours
before the code moved, and one of its four rows became wrong in the opposite direction.

> ### ⚠️ Row by row, measured at HEAD
>
> | The decision said | Measured at HEAD | Verdict |
> |---|---|---|
> | "**No in-app language picker** in Settings ▸ Appearance" | A `Picker` listing 22 languages by autonym — `AppearanceSettingsView.swift:64-87` | **Still reversed.** The picker was kept deliberately (see *Why the picker stayed* below) |
> | "Set `UIPrefersShowingLanguageSettings = YES` in `Info.plist`" | Never set. Zero `INFOPLIST_KEY_UIPrefers…` in `xcodebuild -showBuildSettings -target Bristlenose -configuration Release`; not in the built `Info.plist` of either the 0.30.0 archive or a HEAD build | **Still true.** Never done |
> | "`I18n.swift` reads `Bundle.preferredLocalizations(from:forPreferences:)`" | **It does.** `I18n.systemPreferredLocale()` — `I18n.swift:128-133` — reached from `configure` at `I18n.swift:75-76` whenever the private `language` key is unset | **The 20 Sep banner said "nothing in `desktop/` reads the OS language preference at all". That is now false.** `b9ba08f2`, 21 Sep 17:15, four hours after the banner |
> | "Settings ▸ Appearance includes a hint paragraph pointing to System Settings" | Never written. The footer under the picker is an invitation to translate on Weblate (`AppearanceSettingsView.swift:88-95`) | **Still true.** Never done |
>
> ### What landed on 21 Sep 2026
>
> Three commits in one evening, all after the 20 Sep banner was written:
>
> - **`b9ba08f2` 17:15 — "declare the localisations, so Apple's own menus stop speaking
>   English."** 22 `.lproj` directories, `systemPreferredLocale()`, and the picker starts
>   writing `AppleLanguages`.
> - **`d480accc` 18:35 — "tell AppKit the language an existing install already chose."**
>   `adoptChosenLanguageForAppKit()`, called once from `BristlenoseApp.swift:175`.
> - **`2a3bcbe4` 19:29 — the relaunch prompt.** `SettingsWindow.promptToRelaunch()`,
>   `SettingsView.swift:197-227`.
>
> **None of it shipped in 0.30.0.** The release archive was built at 06:25 that morning,
> eleven hours before the first of the three: `desktop/build/Bristlenose-DeveloperID.xcarchive`
> (0.30.0, build 3578) carries **zero** `.lproj` directories, and a Debug build of HEAD
> carries **22**. Everything below is therefore unreleased behaviour landing in the next
> version.

## 1. Resolution order at launch — measured

`I18n.configure(localesDirectory:)` (`I18n.swift:62-88`) consults exactly two things, in
this order:

1. **The private `language` key** — `UserDefaults.standard.string(forKey: "language")`,
   `I18n.swift:75`. Written only by the picker (`@AppStorage("language")`,
   `AppearanceSettingsView.swift:15`).
2. **`systemPreferredLocale()`** — `I18n.swift:76`, and only when (1) is absent. That is
   `Bundle.preferredLocalizations(from: Array(supportedLocales), forPreferences: nil)`
   (`I18n.swift:128-133`), which reads the process's `AppleLanguages` — the app's own
   preference domain first, the global domain behind it.

The result is passed through `sanitized(_:)` (`I18n.swift:309-311`), which falls back to
`"en"` for anything not in `supportedLocales`. **`Bundle.preferredLocalizations` is not
consulted at all once the picker has been used, and the hardcoded `"en"` is reached only
when the matcher returns nothing or returns an unsupported code.**

Measured, with `AppleLanguages` set in an app's own preference domain — which is what
System Settings ▸ Apps writes — and the 22-code `supportedLocales` array:

| per-app `AppleLanguages` | `systemPreferredLocale()` |
|---|---|
| unset (inherits global `en-GB, es-GB, ca-GB`) | `en` |
| `fr` | `fr` |
| `ja` | `ja` |
| `pt-BR` | `pt-BR` |
| `zh-Hant-HK` | `zh-Hant-HK` |
| `nn-NO` | `nb` — Nynorsk falls to Bokmål |
| `zh-Hans` | `en` — we ship no Simplified, correct |

So the matcher half of the original decision now works, and works well: script and region
subtags resolve the way the rest of macOS resolves them, which is the "free correctness"
the decision below argued for.

**Fresh install → the OS wins, for the native chrome only.** Measured: launching a HEAD
build against an empty preference container wrote nothing at all. `language` is unset, so
`configure` asks the matcher, and `adoptChosenLanguageForAppKit()` returns at its first
`guard` (`I18n.swift:104`).

> ### 🔴 Second defect — two readers never got the memo, and they own the bigger surface
>
> `I18n` is not the only reader of the private key. Five sites read it; three go through
> `I18n`, and **two bypass it entirely and default to `"en"` on their own**:
>
> - `BridgeHandler.swift:596` — `UserDefaults.standard.string(forKey: "language") ?? "en"`,
>   pushed into the WKWebView by `syncLocale()`. This is the language of **the report** —
>   the surface the researcher spends the day in.
> - `BristlenoseShared.swift:256` — `if let lang = defaults.string(forKey: "language"),
>   lang != "en"`, which sets `BRISTLENOSE_LANG` and `BRISTLENOSE_WHISPER_LANGUAGE` in the
>   sidecar's environment. Absent key → no env var → the server-rendered status page is
>   English.
>
> So on a fresh install on a French Mac at HEAD: **French SwiftUI chrome, French AppKit
> menus, an English report inside them.** *"Korean Mac boots Korean"* is true of the shell
> and false of the contents, which is close to the worst available outcome — it looks
> deliberate.
>
> The 20 Sep banner listed all four private-key readers. `b9ba08f2` changed the one in
> `I18n` and left the other two, and nothing was red, because no test asserts that the
> web layer and the native layer resolve the same locale. **Listed causes are a hypothesis;
> the unlisted ones are the unlooked-at ones** — here the list was right and only two
> thirds of it was acted on.

**Install that has used the picker → the private key wins,** permanently and
unconditionally. There is no expiry, no migration, and no path back: nothing anywhere
removes the `language` key. The one-shot `removeObject(forKey: "language")` the decision
below lists under *What we add* was never written.

## 2. Restart — what the researcher actually experiences

`AppearanceSettingsView.swift` carries three comments about the language row that read as
if they disagree — *"Live, NOT a restart"* (line 152, which is about **palette**, not
language), *"only at launch"* (line 165), *"does not get to relaunch itself behind the
researcher's back"* (line 174). They are all true, of different surfaces. The split:

| Surface | Reads from | When it changes |
|---|---|---|
| Everything drawn through `i18n.t(…)` — SwiftUI panes, toolbar, sidebar, our own menu titles | `I18n.locale`, `@Published` | **Live.** `setLocale` on `onChange` (`AppearanceSettingsView.swift:160`) |
| The Settings window's own toolbar/pane titles | rebuilt, not re-rendered | **Live**, via `SettingsWindow.rebuildForLocaleChange()` (`SettingsView.swift:155-169`) — the window is closed and reopened |
| File / Edit / View / Window / Help and every standard item inside them | AppKit, from `AppleLanguages`, once per process | **Next launch** |
| Save panels, system dialogs, `NSAlert` default buttons | same | **Next launch** |
| Date and month names in the cloud-import outline | `Locale.current`, which follows `AppleLanguages` | **Next launch** — documented at `CloudImportOutline.swift:521-531` |
| The web report in the WKWebView | bridge `syncLocale` → serve restart | **Live** (a sidecar restart, posted at `AppearanceSettingsView.swift:186`) |

**The researcher is told.** `promptToRelaunch()` (`SettingsView.swift:197-227`) raises an
`NSAlert` after the Settings window rebuild, offering *Relaunch Now* / *Don't Relaunch*.
The four strings are lifted verbatim out of Apple's own
`Localization.appex/Localizable.loctable` and are present in all 21 full locales
(`settings.language.{relaunchTitle,relaunchBody,relaunchNow,dontRelaunch}`). During an
analysis the alert states Apple's *"will not use the new language until relaunched"* and
offers no button, so a run is never killed to fix a cosmetic mismatch.

**This supersedes the 21 Sep note that telling the researcher was "the one piece still
owed".** It was owed for about ninety minutes.

## 3. The relationship with System Settings — half fixed, and the other half got worse

Both controls write **the same key in the same domain**: `AppleLanguages` under the app's
own preference domain. The picker writes it at `AppearanceSettingsView.swift:176`; System
Settings ▸ Apps ▸ Bristlenose ▸ Language writes it as the platform's per-app override. So
there is no storage conflict. The conflict is over which one `I18n` reads, and it is
one-sided.

Measured decision table. Each row is a launch; the last column is the state left behind
*after* `.onAppear` has run `adoptChosenLanguageForAppKit()`:

| Starting state | `I18n` chrome | AppKit's own menus | `AppleLanguages` after launch |
|---|---|---|---|
| fresh — no `language`, no per-app override | `en` (follows global) | `en` | untouched |
| System Settings ▸ Apps → French; picker never used | **`fr`** ✅ | **`fr`** ✅ | untouched ✅ |
| picker → German, then System Settings ▸ Apps → French | **`de`** ❌ | **`fr`** ❌ | **rewritten to `de`** ❌ |
| …the launch after that | `de` | `de` | `de` (guard trips, no write) |

> ### 🔴 Defect — the per-app override is not merely ignored now, it is reverted
>
> The decision below argues against an in-app picker partly because of a race it says we
> had already hit: *"System Settings ▸ Apps ▸ Bristlenose ▸ Korean was being silently
> ignored because we read our private `language` key, not `AppleLanguages`."*
>
> **Row 2 above fixes that. Row 3 reintroduces it and adds a second failure on top.**
>
> Once the picker has been touched even once, a researcher who then sets a language in
> System Settings gets:
>
> 1. **A French menu bar over a German app** on the next launch — the exact mismatch
>    `promptToRelaunch` exists to prevent, arriving through a door that raises no prompt,
>    because the prompt hangs off the picker's `onChange` and System Settings does not go
>    through it.
> 2. **Their System Settings choice silently discarded.** `adoptChosenLanguageForAppKit()`
>    (`I18n.swift:103-108`) fires unconditionally whenever `language` is set, and
>    `syncAppleLanguages` (`I18n.swift:117-122`) overwrites `AppleLanguages` with the
>    picker's value. By the second launch the System Settings pane itself reads German,
>    and nothing records that the user ever asked for French. The guard at `I18n.swift:120`
>    (`current?.first != locale`) only suppresses a redundant write; it does not detect
>    that the value it is about to clobber was set by somebody else.
>
> The write-back is the right fix for the problem it was written for — `d480accc`, an
> install that chose a language before `.lproj` existed and never told AppKit. It has no
> way to tell that case apart from a deliberate per-app override, because absence of
> provenance is the same shape as both.
>
> **Not fixed here.** This is a truing pass, and the repair is a product decision: either
> the private key goes (Option A in the maintainer's private planning notes, decided
> 2 Jul 2026 — seed from the matcher, read and write `AppleLanguages` only, drop the key
> with a one-shot migration), or the write-back learns to notice that `AppleLanguages`
> changed underneath it and defer. The first is the decision below, finally taken.

## 4. Does the per-app pane appear at all?

`UIPrefersShowingLanguageSettings` is set nowhere — confirmed against the build system,
not the file tree, and confirmed again in the built `Info.plist`. So the discoverability
argument the decision below rests on is **unaddressed**: per
[Apple Developer Forums #721302](https://developer.apple.com/forums/thread/721302), the
per-app Language section is hidden for a user who has configured only one preferred
language globally.

What *has* changed is the other precondition. The pane needs the app to be localised for
more than one language, and at HEAD it is: the built bundle reports **22** localisations
(`Bundle(path:).localizations`, measured), against **1** for the shipped 0.30.0. So the
row is now capable of appearing where before it could not appear at all — for a
multi-language user. For a single-language user it still needs the key.

**Not measured here:** whether the row is actually drawn in System Settings ▸ Apps on this
machine. Reading an app's sandboxed preference container needs Full Disk Access, which
this session did not have; the container writes were simulated in a throwaway bundle with
the same APIs. The remaining check is a human one — build, launch once, then look at
System Settings ▸ General ▸ Language & Region ▸ Applications.

## 5. `knownRegions`, `.lproj`, and what the matcher is really matching

Root `CLAUDE.md` recorded that `knownRegions = (en, Base)` and no `.lproj` ship. **Both
halves went stale on 21 Sep 2026**, and that line is corrected in the same commit as this
pass. Measured: `knownRegions` holds `en`, `Base` and all
22 language codes (`project.pbxproj:172-196`), 22 `.lproj` directories are tracked under
`desktop/Bristlenose/Bristlenose/`, and a HEAD build copies all 22 into
`Contents/Resources`. Each holds one `InfoPlist.strings` containing **only a comment** —
the declaration is the whole payload, and Xcode's filesystem-synchronised group picks the
directories up without a single file reference in the project.

**Two different mechanisms are at work here, and the code comments conflate them.**

- **`Bundle.preferredLocalizations(from:forPreferences:)` — the static — ignores the
  bundle entirely.** It matches the array you hand it against the process's language
  preferences. Measured from a process whose main bundle declares only English: it
  returned `fr`, `ja`, `de`, `nb` and `pt-BR` correctly. So `systemPreferredLocale()`
  would work identically with zero `.lproj`, and the comment at `I18n.swift:70-74`
  crediting the declaration for it (*"now that the app declares its localisations, Apple's
  BCP 47 matcher can answer"*) attributes the wrong cause. Harmless today; misleading to
  anyone who later wonders whether the `.lproj` can go.
- **What the `.lproj` *do* buy is every other bundle in the process, AppKit's included.**
  Measured directly: a probe app declaring only `en`, with its per-app `AppleLanguages` set
  to `fr`, resolved `AppKit.framework` (45 localisations) to `["en"]`. Adding a single
  `fr.lproj/InfoPlist.strings` to the *probe* — same process, same preference, one marker
  file — flipped AppKit to `["fr"]`. **The main bundle's declared localisations gate every
  other bundle's resolution in the process.** That is precisely why File / Edit / View /
  Window / Help were English, and why they will not be from the next release.
- **Graceful degradation.** Same probe, preference `de`, probe declaring only `en`/`fr`/`ja`:
  AppKit resolved to `["en"]`. An undeclared language costs you Apple's menus, not the app.

> ### ⚠️ New registration site, gated by nothing
>
> `docs/adding-a-language.md` does not mention `.lproj` or `knownRegions` — zero hits.
> Neither does root `CLAUDE.md`'s three-site Swift list, and no test anywhere asserts that
> the `.lproj` set matches `I18n.supportedLocales` (zero hits for `lproj` across
> `BristlenoseTests/`, `tests/` and `scripts/`).
>
> So a 23rd language added by following the guide gets 21 full locale files, five Swift
> and Python registrations, a green `check-locales.py`, a green suite — and File / Edit /
> View silently in English for that language alone. The degradation is graceful, which is
> what makes it survivable and also what makes it invisible. Fixing the guide and adding
> the gate is follow-up work, not part of this pass.

## Why the picker stayed

It ships, it is a registration site for a new language (`docs/adding-a-language.md`
Step 8), and removing a working control to satisfy a doc is the wrong order. The
decision's substance — *the OS is the source of truth* — is honoured by writing
`AppleLanguages` rather than by deleting the UI. What the decision below got right and
what shipped now agree on the fresh-install path; they still disagree on precedence once
a choice has been made, and §3 is the cost of that disagreement.

**What this all buys, and it is the reason to do it at all:** File, Edit, View, Window and
Help are AppKit's menus, not ours, and so is every standard item inside them — Minimize,
Zoom, Bring All to Front, Cut/Copy/Paste, Enter Full Screen. They rendered English in
every locale because the app declared no localisations. They now come back in **Apple's
own reviewed wording**, which is the `Choose`-button / TCC-prompt principle one level up:
look it up, do not translate it. The glossary already carried hand-written
`Window,ウインドウ,ja` and `Help,ヘルプ,ja` rows — evidence someone once reached for the
wrong route.

## Where this doc and `design-i18n.md` disagreed

Both were wrong, in different places, and neither wins wholesale:

- **This doc was right** that `Bundle.preferredLocalizations` is the mechanism, that
  `AppleLanguages` is the key both controls must share, and that reading a private key
  ahead of it re-opens the per-app-override race. §3 is that prediction coming true a
  second time.
- **`design-i18n.md` was right** that the picker exists and that
  `UIPrefersShowingLanguageSettings` was never set — two things this doc asserted in the
  present tense for four months.
- **Both were wrong about the standard menus.** `design-i18n.md` §"The *standard* menus
  are a different mechanism — and still English" was measured on 21 Sep and obsolete by
  that evening; this doc's own 20 Sep banner said nothing in `desktop/` read the OS
  preference, four hours before it did.

There is no precedence rule between them and "trust the older doc" has been falsified
twice now. Read the code.

---

_Original decision text, 5 May 2026, unedited below._

**Status:** approved 5 May 2026, pending implementation in branch `locale-system-delegation` (sibling to `i18n-text-sweep` which handles the unrelated mechanical translation gaps).

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
