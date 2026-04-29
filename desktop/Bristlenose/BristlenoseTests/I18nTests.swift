import Testing
import Foundation
@testable import Bristlenose

/// I18n is @MainActor — all tests must be @MainActor too.
@MainActor
@Suite("I18n translation")
struct I18nTests {

    /// Path to the test locale fixtures bundled alongside the test sources.
    /// Falls back to the source tree path (when running from Xcode without
    /// the fixtures copied to the test bundle).
    private static var fixturesURL: URL {
        // Try the test bundle first (if fixtures are added as bundle resources)
        if let bundlePath = Bundle(for: BundleAnchor.self).resourcePath {
            let bundleFixtures = URL(fileURLWithPath: bundlePath)
                .appendingPathComponent("Fixtures")
            if FileManager.default.fileExists(
                atPath: bundleFixtures.appendingPathComponent("en/common.json").path
            ) {
                return bundleFixtures
            }
        }
        // Fallback: source tree path (works in Xcode when files aren't bundled)
        return URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .appendingPathComponent("Fixtures")
    }

    // MARK: - Key lookup

    @MainActor @Test func t_simpleKey_returnsTranslation() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        #expect(i18n.t("common.nav.project") == "Project")
    }

    @MainActor @Test func t_nestedKey_returnsTranslation() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        #expect(i18n.t("desktop.menu.file.print") == "Print…")
    }

    @MainActor @Test func t_missingKey_returnsRawKey() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        #expect(i18n.t("common.nonexistent.key") == "common.nonexistent.key")
    }

    @MainActor @Test func t_missingNamespace_returnsRawKey() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        #expect(i18n.t("bogus.some.key") == "bogus.some.key")
    }

    @MainActor @Test func t_noDotsInKey_returnsRawKey() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        #expect(i18n.t("nodots") == "nodots")
    }

    // MARK: - Locale switching

    @MainActor @Test func setLocale_spanish_returnsSpanishTranslation() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        i18n.setLocale("es")
        #expect(i18n.locale == "es")
        #expect(i18n.t("common.nav.quotes") == "Citas")
    }

    @MainActor @Test func setLocale_spanish_fallsBackToEnglish() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        i18n.setLocale("es")
        // "actions.save" exists in English but not Spanish fixture
        #expect(i18n.t("common.actions.save") == "Save")
    }

    @MainActor @Test func setLocale_unsupported_fallsBackToEnglish() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        i18n.setLocale("xx")
        #expect(i18n.locale == "en")
        #expect(i18n.t("common.nav.project") == "Project")
    }

    // MARK: - Locale allowlist

    @Test func supportedLocales_containsExpected() {
        let expected: Set<String> = ["en", "es", "ja", "fr", "de", "ko"]
        #expect(I18n.supportedLocales == expected)
    }
}

/// Anchor class for finding the test bundle at runtime.
private class BundleAnchor {}
