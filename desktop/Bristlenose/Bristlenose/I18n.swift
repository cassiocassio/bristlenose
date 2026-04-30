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
    private var englishStrings: [String: Any] = [:]

    /// Locale directory on disk — set once via `configure(localesDirectory:)`.
    private var localesDirectory: URL?

    // MARK: - Locale allowlist (security: prevents path traversal)

    static let supportedLocales: Set<String> = ["en", "es", "ja", "fr", "de", "ko"]

    /// Namespaces to load — must match the JSON filenames in bristlenose/locales/.
    private static let namespaces = ["common", "settings", "enums", "desktop"]

    // MARK: - Setup

    /// Set the locales directory and load the initial locale from UserDefaults.
    func configure(localesDirectory: URL) {
        self.localesDirectory = localesDirectory

        // Always load English as fallback.
        englishStrings = Self.loadAllNamespaces(locale: "en", from: localesDirectory)

        // Load the user's preferred locale.
        let saved = UserDefaults.standard.string(forKey: "language") ?? "en"
        let safe = Self.sanitized(saved)
        locale = safe

        if safe != "en" {
            strings = Self.loadAllNamespaces(locale: safe, from: localesDirectory)
        } else {
            strings = englishStrings
        }
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

        // Try current locale
        if let ns = strings[namespace] {
            if let value = Self.resolve(ns, parts: parts) {
                return value
            }
        }

        // Fallback to English
        if locale != "en", let ns = englishStrings[namespace] {
            if let value = Self.resolve(ns, parts: parts) {
                return value
            }
        }

        return key
    }

    // MARK: - Private

    private static func sanitized(_ code: String) -> String {
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
    /// Priority:
    /// 1. Dev mode — repo source tree (fastest iteration)
    /// 2. Bundled .app — host target's Copy Sidecar Resources phase
    /// 3. Bundled .app — PyInstaller sidecar (legacy fallback)
    /// 4. Homebrew / pipx — site-packages
    static func findLocalesDirectory() -> URL? {
        let fm = FileManager.default

        // 1. Dev mode: source tree (most common during development)
        let devPath = NSString("~/Code/bristlenose/bristlenose/locales")
            .expandingTildeInPath
        let devURL = URL(fileURLWithPath: devPath)
        if fm.fileExists(atPath: devURL.appendingPathComponent("en/common.json").path) {
            return devURL
        }

        // 2. App bundle: host-target Resources/locales (copied by the
        // "Copy Sidecar Resources" build phase). This is the canonical
        // location for shipped builds — independent of the sidecar's
        // PyInstaller layout.
        if let resourcePath = Bundle.main.resourcePath {
            let bundledPath = URL(fileURLWithPath: resourcePath)
                .appendingPathComponent("locales")
            if fm.fileExists(atPath: bundledPath.appendingPathComponent("en/common.json").path) {
                return bundledPath
            }

            // 3. Legacy fallback: PyInstaller sidecar's _internal dir.
            // Kept for older builds where locales weren't copied to the
            // host bundle directly.
            let sidecarPath = URL(fileURLWithPath: resourcePath)
                .appendingPathComponent("bristlenose-sidecar/_internal/bristlenose/locales")
            if fm.fileExists(atPath: sidecarPath.appendingPathComponent("en/common.json").path) {
                return sidecarPath
            }
        }

        // 3. Homebrew / pipx: find site-packages via known binary locations
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
