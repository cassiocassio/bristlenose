import Foundation
import SwiftUI

/// Lightweight i18n loader — reads JSON locale files from the canonical
/// `bristlenose/locales/` directory (shared with Python and React).
///
/// Usage:
///   i18n.t("common.nav.quotes")        → "Citas" (if locale is "es")
///   i18n.t("desktop.menu.file.print")   → "Imprimir"
///
/// Dotted key format: "namespace.path.to.key" — first segment is the filename
/// (e.g. "common" → common.json), remainder walks the JSON object.
///
/// Falls back to English, then returns the raw key.
@MainActor
final class I18n: ObservableObject {

    @Published private(set) var locale: String = "en"

    /// Loaded translations keyed by namespace, then nested JSON structure.
    private var strings: [String: Any] = [:]
    /// Fallback base for region/script variants (e.g. zh-Hant for zh-Hant-HK).
    /// Empty unless the active locale has a `fallbackBase` entry.
    private var baseStrings: [String: Any] = [:]
    private var englishStrings: [String: Any] = [:]

    /// Locale directory on disk — set once via `configure(localesDirectory:)`.
    private var localesDirectory: URL?

    // MARK: - Locale allowlist (security: prevents path traversal)

    nonisolated static let supportedLocales: Set<String> = [
        "en", "es", "ca", "ja", "fr", "de", "ko", "cs", "it", "pl", "ru", "uk", "da", "sv", "nb", "tr", "nl", "fi", "pt-BR", "pt-PT", "zh-Hant", "zh-Hant-HK",
    ]

    /// Region/script variants borrow missing keys from a base locale before
    /// English. zh-Hant-HK (Hong Kong) → zh-Hant (Taiwan Traditional) → en.
    /// TW/HK Traditional Chinese are mutually intelligible, so this is correct,
    /// not lossy — lets zh-Hant-HK ship as a thin override of HK-specific terms.
    private static let fallbackBase: [String: String] = ["zh-Hant-HK": "zh-Hant"]

    /// Namespaces to load — must match the JSON filenames in bristlenose/locales/.
    private static let namespaces = ["common", "settings", "enums", "desktop"]

    /// The namespaces that exist in `bristlenose/locales/` and are
    /// deliberately not loaded here — they belong to the CLI and the server,
    /// which are their own surfaces. Kept beside `namespaces` because the two
    /// are only meaningful as a pair: this is the complement, and the `t`
    /// assertion below is the only thing that reads it.
    private static let unloadedOnDiskNamespaces: Set<String> = [
        // `cli`, `doctor` and `pipeline` were deleted on 22 Sep 2026 — their
        // surfaces are English by decision, so their translations could never
        // be read. What is left is the genuine shape this assertion is for:
        // a namespace that exists in `bristlenose/locales/` and is not loaded
        // by this target, so a key in it can only ever render raw.
        "preflight", "server",
    ]

    // MARK: - Setup

    /// Set the locales directory and load the initial locale from UserDefaults.
    func configure(localesDirectory: URL) {
        self.localesDirectory = localesDirectory

        // Always load English as fallback.
        englishStrings = Self.loadAllNamespaces(locale: "en", from: localesDirectory)

        // Load the user's preferred locale. The picker's own key wins when it
        // is set, so an existing install keeps the language it was last given.
        // With no key — a fresh install — ask the OS rather than assuming
        // English: now that the app declares its localisations, Apple's BCP 47
        // matcher can answer from the user's own language preferences, which is
        // what `docs/design-locale-negotiation.md` decided and nothing had
        // implemented.
        let safe = Self.resolvedLocale
        locale = safe

        if safe != "en" {
            strings = Self.loadAllNamespaces(locale: safe, from: localesDirectory)
        } else {
            strings = englishStrings
        }
        baseStrings = Self.fallbackBase[safe].map {
            Self.loadAllNamespaces(locale: $0, from: localesDirectory)
        } ?? [:]
    }

    /// Make AppKit's language agree with the researcher's choice.
    ///
    /// **Called once at app launch, deliberately not from `configure`.** The
    /// first version did it there and broke `CloudImportOutlineTests.dayLabels`:
    /// `configure` runs inside the `I18n` initialiser, every test that builds an
    /// `I18n` would have run it, and writing `AppleLanguages` moves
    /// `Locale.current` for the whole process — so a date formatter three files
    /// away started producing non-English month names. A loader must not have
    /// process-wide side effects; an app launching may.
    ///
    /// Only when the picker's key is set. A fresh install should go on
    /// following the system, and pinning it here would freeze the app at
    /// whatever the language happened to be on first launch.
    static func adoptChosenLanguageForAppKit() {
        guard let chosen = UserDefaults.standard.string(forKey: "language") else { return }
        let safe = sanitized(chosen)
        guard supportedLocales.contains(safe) else { return }
        // **Only when nothing has told AppKit yet.** This used to write
        // unconditionally, which meant it did not merely ignore a language set
        // in System Settings > Apps > Bristlenose — it OVERWROTE it on the next
        // launch, so the researcher's choice vanished from the System Settings
        // pane itself with nothing recording that they had ever made it.
        //
        // The population this exists for is an install that chose a language
        // before the `.lproj` declarations shipped (21 Sep 2026) and so never
        // told AppKit. That install has no explicit `AppleLanguages`, which is
        // exactly what distinguishes it from one where somebody chose.
        guard explicitAppleLanguages() == nil else { return }
        syncAppleLanguages(safe)
    }

    /// Point `AppleLanguages` at our own choice, in the app's own domain —
    /// the same key System Settings ▸ Apps ▸ Bristlenose ▸ Language writes, so
    /// the two controls agree rather than compete.
    ///
    /// Reads before writing because `UserDefaults` searches the global domain
    /// too: a first run finds the system's `en-GB` there, writes ours, and
    /// every run after that finds ours and leaves it alone.
    static func syncAppleLanguages(_ locale: String) {
        let defaults = UserDefaults.standard
        let current = defaults.array(forKey: "AppleLanguages") as? [String]
        guard current?.first != locale else { return }
        defaults.set([locale], forKey: "AppleLanguages")
    }

    /// The best of our supported locales for this user's language preferences,
    /// or `en`. Reads `AppleLanguages` through Apple's matcher rather than
    /// parsing it, so script and region subtags (`zh-Hant`, `zh-Hant-HK`,
    /// `pt-BR`) resolve the way the rest of macOS resolves them.
    /// The locale the app displays in: the picker's choice when set, otherwise
    /// the best match against the user's own system language preferences.
    ///
    /// Extracted so there is **one** statement of that rule. `configure` needs
    /// it to load strings, and `BristlenoseShared.childEnvironment` needs it to
    /// tell the pipeline what language to generate section and theme names in
    /// (`BRISTLENOSE_LANG` → `bristlenose/llm/output_language.py`). Two copies
    /// would drift the moment the fallback changed, and the symptom would be a
    /// researcher whose UI is Catalan getting Spanish themes — which looks like
    /// a model failure and is not one.
    /// `nonisolated` because `BristlenoseShared.childEnvironment` builds a
    /// subprocess environment off the main actor. Safe: this reads
    /// `UserDefaults` and `Bundle` and touches none of the class's
    /// `@MainActor` state.
    nonisolated static var resolvedLocale: String {
        sanitized(UserDefaults.standard.string(forKey: "language") ?? systemPreferredLocale())
    }

    /// **`forPreferences:` is passed explicitly, and that is load-bearing.**
    ///
    /// With `nil`, CoreFoundation resolves the user's language list once — on
    /// the FIRST call anywhere in the process — and caches it for the process
    /// lifetime. Measured 22 Sep 2026: write `AppleLanguages`, ask again in the
    /// same process, and you get the pre-write answer; `Locale.preferredLanguages`
    /// tracks the write, the `nil` form does not. And the cache is primed before
    /// any of our code runs, because AppKit resolves the main bundle's
    /// localisations during `NSApplicationMain` — a probe that reads
    /// `Bundle.main.preferredLocalizations` first and writes second gets the
    /// stale value, one that writes first gets the fresh one.
    ///
    /// So a `nil` here would make every caller after launch answer with the
    /// launch-time language: the picker would stop updating the report, and a
    /// migration could not read back what it had just written.
    nonisolated static func systemPreferredLocale() -> String {
        let best = Bundle.preferredLocalizations(
            from: Array(supportedLocales), forPreferences: Locale.preferredLanguages
        ).first
        return best.map(sanitized) ?? "en"
    }

    /// `AppleLanguages` as set for THIS app specifically, or `nil` when the app
    /// domain has none and the value is inherited from the global domain.
    ///
    /// `UserDefaults.standard.array(forKey:)` cannot answer this — it searches
    /// the global domain too, so it returns the system's list and makes "nobody
    /// has chosen" indistinguishable from "chose the system default".
    nonisolated static func explicitAppleLanguages() -> [String]? {
        CFPreferencesCopyValue(
            "AppleLanguages" as CFString,
            kCFPreferencesCurrentApplication,
            kCFPreferencesCurrentUser,
            kCFPreferencesAnyHost
        ) as? [String]
    }

    /// Change the active locale. Reloads JSON from disk.
    func setLocale(_ code: String) {
        let safe = Self.sanitized(code)
        locale = safe

        guard let dir = localesDirectory else { return }

        if safe != "en" {
            strings = Self.loadAllNamespaces(locale: safe, from: dir)
        } else {
            strings = englishStrings
        }
        baseStrings = Self.fallbackBase[safe].map {
            Self.loadAllNamespaces(locale: $0, from: dir)
        } ?? [:]
    }

    // MARK: - Translation

    /// Translate a dotted key. Format: "namespace.path.to.key".
    ///
    /// Tries the current locale first, falls back to English, then returns
    /// the raw key (which for desktop.json is the English string itself).
    func t(_ key: String) -> String {
        guard let dotIndex = key.firstIndex(of: ".") else { return key }
        let namespace = String(key[key.startIndex..<dotIndex])
        let remainder = String(key[key.index(after: dotIndex)...])
        let parts = remainder.split(separator: ".").map(String.init)

        // A namespace that exists in `bristlenose/locales/` but is NOT in
        // `namespaces` above can never resolve here, and `t` has no error path —
        // it returns the raw key, which renders as `server.statusPage.help` on
        // screen and reads like a missing *translation* rather than an
        // unreachable *namespace*. Assert in DEBUG so the mistake is loud where
        // it is cheap.
        //
        // Deliberately NOT `!namespaces.contains(namespace)`: an entirely unknown
        // namespace returning the raw key is a tested contract
        // (`I18nTests.t_missingNamespace_returnsRawKey`, which passes
        // "bogus.some.key"), and the graceful degradation it pins is wanted. The
        // bug this catches is the opposite shape — a key that exists on disk and
        // is unreachable from this target.
        assert(
            !Self.unloadedOnDiskNamespaces.contains(namespace),
            "i18n: '\(namespace)' is a real namespace in bristlenose/locales/ but this target does not "
                + "load it (loaded: \(Self.namespaces.joined(separator: ", "))). Key '\(key)' can never "
                + "resolve and will render raw. Add it to I18n.namespaces, or re-home the key."
        )

        // Try current locale
        if let ns = strings[namespace], let value = Self.resolve(ns, parts: parts) {
            return value
        }

        // Fallback to the base locale (region/script variants, e.g. zh-Hant-HK → zh-Hant)
        if let ns = baseStrings[namespace], let value = Self.resolve(ns, parts: parts) {
            return value
        }

        // Fallback to English
        if locale != "en", let ns = englishStrings[namespace], let value = Self.resolve(ns, parts: parts) {
            return value
        }

        return key
    }

    /// Translate with `{{name}}` substitution.
    ///
    /// Used for whole-string interpolation where the locale-specific text
    /// surrounding the variable differs (leading space, full-width vs
    /// half-width parens, suffix vs prefix word order). Suffix-concat
    /// breaks across locales — use this instead.
    ///
    ///   i18n.t("desktop.transcriptionSettings.modelRecommended",
    ///          ["model": "large-v3-turbo"])
    ///   → en: "large-v3-turbo (recommended)"
    ///   → ja: "large-v3-turbo（推奨）"
    func t(_ key: String, _ vars: [String: String]) -> String {
        var s = t(key)
        for (k, v) in vars {
            s = s.replacingOccurrences(of: "{{\(k)}}", with: v)
        }
        return s
    }

    // MARK: - Plurals

    /// CLDR plural category — "one" / "few" / "many" / "other" — for an integer
    /// `count` in the active locale. Bristlenose's i18n is JSON-based (not
    /// Apple `.stringsdict`), so the category is computed here and the caller
    /// selects the `<key>_<category>` form (e.g. `overflow_few`).
    ///
    /// Delegates to the pure static so the rule is testable without registering
    /// the locale in `supportedLocales` (`setLocale` would otherwise sanitise an
    /// unregistered code to `en`). Tests call `I18n.pluralCategory(_:locale:)`
    /// directly; production reads the active `locale`.
    func pluralCategory(_ count: Int) -> String {
        Self.pluralCategory(count, locale: locale)
    }

    /// Pure integer CLDR plural rule. `count` is always an `Int`, so the decimal
    /// fraction `v` is 0 and the `other` category (decimals-only for the Slavic
    /// family) never fires for these locales — the helper falls back to `_other`
    /// if a stem is missing, so that's harmless.
    ///
    /// Verified against the CLDR plural-rules chart. Note `many`: it is the
    /// Czech *decimals-only* category (so cs never returns it for an integer),
    /// but for pl/ru/uk it is a live *integer* category (5+, with the teens
    /// exception). Do NOT copy the `cs` branch when adding a Slavic locale — its
    /// "no many for integers" shape is cs-specific and wrong for the others.
    static func pluralCategory(_ count: Int, locale: String) -> String {
        let n = abs(count)
        let mod10 = n % 10
        let mod100 = n % 100
        switch locale {
        case "cs":
            // Czech: one = 1; few = 2–4; other = 0, 5+ (many is decimals-only).
            if n == 1 { return "one" }
            if (2...4).contains(n) { return "few" }
            return "other"
        case "pl":
            // Polish: one = 1; few = mod10 2–4 except teens; many = the rest
            // (0, 5–21, …). 21 → many (≠ ru/uk, where 21 → one).
            if n == 1 { return "one" }
            if (2...4).contains(mod10) && !(12...14).contains(mod100) { return "few" }
            return "many"
        case "ru", "uk":
            // Russian + Ukrainian share an identical integer rule:
            // one = mod10 1 except 11; few = mod10 2–4 except teens; many = rest.
            if mod10 == 1 && mod100 != 11 { return "one" }
            if (2...4).contains(mod10) && !(12...14).contains(mod100) { return "few" }
            return "many"
        case "fr":
            // French: 0 and 1 are both "one".
            return n <= 1 ? "one" : "other"
        case "ja", "ko", "zh-Hant", "zh-Hant-HK":
            // Single-form locales — always "other".
            return "other"
        default:
            // en, es, de (and any unmapped locale): one = 1, other = else.
            return n == 1 ? "one" : "other"
        }
    }

    /// Resolve a CLDR-pluralised string. Appends the active locale's plural
    /// category for `count` to `base` (`<base>_one` / `_few` / `_many` /
    /// `_other`), substitutes `{{count}}` plus any extra `vars`, and degrades to
    /// the `_other` form when the selected category's stem is absent.
    ///
    /// The `_other` fallback covers two real cases: single-form locales (ja/ko
    /// carry only `_other`), and a locale that simply lacks a `_many` stem for a
    /// given key. A locale whose `pluralCategory` returns `many` for integers
    /// (pl/ru/uk — unlike cs, where `many` is decimals-only) is the first to
    /// exercise the latter, so this is the single home for the pattern that
    /// ContentView, ProjectRow, SidebarSubtitleText, ProjectDiagnosticPopover
    /// and MiroSheet each used to inline. Keeping it in one place means a new
    /// call site can't forget the guard and ship a raw `<base>_many` key.
    func plural(_ base: String, count: Int, _ vars: [String: String] = [:]) -> String {
        var merged = vars
        merged["count"] = String(count)
        let key = "\(base)_\(pluralCategory(count))"
        let rendered = t(key, merged)
        // `t` returns the raw key on a miss (the `_<category>` stem has no
        // `{{count}}` placeholder, so substitution is a no-op) — that's the
        // signal to retry the always-present `_other` form.
        if rendered == key {
            return t("\(base)_other", merged)
        }
        return rendered
    }

    // MARK: - Private

    nonisolated private static func sanitized(_ code: String) -> String {
        supportedLocales.contains(code) ? code : "en"
    }

    /// Walk a nested dictionary by key parts and return the leaf string.
    private static func resolve(_ data: Any, parts: [String]) -> String? {
        var current: Any = data
        for part in parts {
            guard let dict = current as? [String: Any],
                  let next = dict[part] else {
                return nil
            }
            current = next
        }
        return current as? String
    }

    /// Load all namespace JSONs for a locale into a single dictionary.
    private static func loadAllNamespaces(
        locale: String,
        from directory: URL
    ) -> [String: Any] {
        var result: [String: Any] = [:]
        let localeDir = directory.appendingPathComponent(locale)

        for ns in namespaces {
            let file = localeDir.appendingPathComponent("\(ns).json")
            guard let data = try? Data(contentsOf: file),
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else {
                continue  // Missing file — English fallback covers it
            }
            result[ns] = json
        }
        return result
    }

    // MARK: - Locale directory discovery

    /// Find the bristlenose locales directory based on common install locations.
    ///
    /// Priority (bundle first — canonical for any built app, works under sandbox):
    /// 1. Bundled .app — host target's Copy Sidecar Resources phase
    /// 2. Bundled .app — PyInstaller sidecar `_internal` (legacy fallback)
    /// 3. Dev mode — this source file's enclosing worktree (only reached when
    ///    the bundle has no locales, e.g. iterating on the build phase itself)
    /// 4. Dev mode — `~/Code/bristlenose/bristlenose/locales` legacy fallback
    /// 5. Homebrew / pipx — site-packages
    ///
    /// The bundle path comes first because under App Sandbox the dev paths
    /// (`#filePath` worktree, `~/Code/...`) are technically still resolvable
    /// via stat() in some configurations (debugger-attached, prior bookmark
    /// grants), so checking them first risks returning a path the app can
    /// stat but not read. Bundle.main.resourcePath is always reachable.
    static func findLocalesDirectory() -> URL? {
        let fm = FileManager.default

        // 1. App bundle: host-target Resources/locales (copied by the
        // "Copy Sidecar Resources" build phase). This is the canonical
        // location for shipped builds and works under App Sandbox.
        if let resourcePath = Bundle.main.resourcePath {
            let bundledPath = URL(fileURLWithPath: resourcePath)
                .appendingPathComponent("locales")
            if fm.fileExists(atPath: bundledPath.appendingPathComponent("en/common.json").path) {
                return bundledPath
            }

            // 2. Legacy fallback: PyInstaller sidecar's _internal dir.
            // Kept for older builds where locales weren't copied to the
            // host bundle directly.
            let sidecarPath = URL(fileURLWithPath: resourcePath)
                .appendingPathComponent("bristlenose-sidecar/_internal/bristlenose/locales")
            if fm.fileExists(atPath: sidecarPath.appendingPathComponent("en/common.json").path) {
                return sidecarPath
            }
        }

        // 3. Dev mode: locales relative to this source file. `#filePath` is
        // resolved at compile time, so each worktree's build points at its
        // own `bristlenose/locales/`. Path layout from this file:
        //   <worktree>/desktop/Bristlenose/Bristlenose/I18n.swift
        // → strip 4 components to reach <worktree>, then append the locales path.
        // Only reached when the bundle has no locales — e.g. iterating on
        // the Copy Sidecar Resources phase itself before it's wired up.
        let sourceFile = URL(fileURLWithPath: #filePath)
        let worktreeURL = sourceFile
            .deletingLastPathComponent()  // Bristlenose/
            .deletingLastPathComponent()  // Bristlenose/ (Xcode project)
            .deletingLastPathComponent()  // desktop/
            .deletingLastPathComponent()  // <worktree>
        let worktreeLocales = worktreeURL.appendingPathComponent("bristlenose/locales")
        if fm.fileExists(atPath: worktreeLocales.appendingPathComponent("en/common.json").path) {
            return worktreeLocales
        }

        // 4. Dev mode: main-repo fallback (covers builds where #filePath
        // resolution doesn't reach a checkout — e.g. archived debug builds).
        let devPath = NSString("~/Code/bristlenose/bristlenose/locales")
            .expandingTildeInPath
        let devURL = URL(fileURLWithPath: devPath)
        if fm.fileExists(atPath: devURL.appendingPathComponent("en/common.json").path) {
            return devURL
        }

        // 5. Homebrew / pipx: find site-packages via known binary locations
        let pythonPrefixes = [
            "/opt/homebrew/lib/python3",
            "/usr/local/lib/python3",
            NSString("~/.local/lib/python3").expandingTildeInPath,
        ]
        for prefix in pythonPrefixes {
            // Try python3.10 through python3.13
            for minor in 10...13 {
                let path = "\(prefix).\(minor)/site-packages/bristlenose/locales"
                let url = URL(fileURLWithPath: path)
                if fm.fileExists(atPath: url.appendingPathComponent("en/common.json").path) {
                    return url
                }
            }
        }

        return nil
    }
}
