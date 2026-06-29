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
        let expected: Set<String> = [
            "en", "es", "ja", "fr", "de", "ko", "cs", "it", "pt-BR", "pt-PT", "zh-Hant", "zh-Hant-HK",
        ]
        #expect(I18n.supportedLocales == expected)
    }

    // MARK: - CLDR plural category

    /// Czech is the first four-form locale (one/few/many/other). The prior
    /// binary `count == 1 ? one : other` selector could never request `few`,
    /// so Czech counts 2–4 rendered the grammatically-wrong `_other` form.
    @MainActor @Test func pluralCategory_czech_picksFewForCounts2to4() {
        let i18n = I18n()
        i18n.setLocale("cs")
        #expect(i18n.pluralCategory(1) == "one")
        #expect(i18n.pluralCategory(2) == "few")
        #expect(i18n.pluralCategory(3) == "few")
        #expect(i18n.pluralCategory(4) == "few")
        #expect(i18n.pluralCategory(5) == "other")
        #expect(i18n.pluralCategory(0) == "other")
        #expect(i18n.pluralCategory(11) == "other")
    }

    @MainActor @Test func pluralCategory_binaryAndSingleFormLocales() {
        let i18n = I18n()
        i18n.setLocale("en")  // one = 1, other = else
        #expect(i18n.pluralCategory(1) == "one")
        #expect(i18n.pluralCategory(2) == "other")
        i18n.setLocale("fr")  // French: 0 and 1 are both "one"
        #expect(i18n.pluralCategory(0) == "one")
        #expect(i18n.pluralCategory(1) == "one")
        #expect(i18n.pluralCategory(3) == "other")
        i18n.setLocale("ja")  // single-form — always "other"
        #expect(i18n.pluralCategory(1) == "other")
        #expect(i18n.pluralCategory(3) == "other")
    }

    /// End-to-end: `localisedOverflowText` must select the `overflow_<category>`
    /// form, not the binary one. Asserts equality with the directly-resolved
    /// form (no hardcoded Czech string) so it survives copy revisions.
    @MainActor @Test func localisedOverflowText_czech_selectsFewForm() {
        guard let dir = I18n.findLocalesDirectory() else { return }  // skip if no locales
        let i18n = I18n()
        i18n.configure(localesDirectory: dir)
        i18n.setLocale("cs")
        let base = "desktop.pipeline.diagnostic.overflow"
        for (count, form) in [(1, "one"), (3, "few"), (7, "other")] {
            let out = ProjectDiagnosticPopover.localisedOverflowText(
                message: "… and \(count) more failures truncated", i18n: i18n)
            let expected = i18n.t("\(base)_\(form)", ["count": String(count)])
            #expect(out == expected, "cs count=\(count) should pick overflow_\(form)")
        }
    }

    /// The sidebar chrome count strings (`ProjectRow.deltaText`) select their
    /// form via `pluralCategory` the same way. `deltaText` is a private view
    /// method, so this pins the data+selector contract it depends on: for cs,
    /// counts 1/3/7 must resolve to distinct `chrome.interviewCount_<form>`
    /// strings (one/few/other), proving the four-form keys exist and the legacy
    /// binary split is gone.
    @MainActor @Test func chromeInterviewCount_czech_selectsCldrForm() {
        guard let dir = I18n.findLocalesDirectory() else { return }  // skip if no locales
        let i18n = I18n()
        i18n.configure(localesDirectory: dir)
        i18n.setLocale("cs")
        let base = "desktop.chrome.interviewCount"
        var rendered: [String] = []
        for (count, form) in [(1, "one"), (3, "few"), (7, "other")] {
            #expect(i18n.pluralCategory(count) == form,
                    "cs count=\(count) should map to \(form)")
            let out = i18n.t("\(base)_\(i18n.pluralCategory(count))", ["count": String(count)])
            // Form must exist (not the raw key echoed back) and interpolate.
            #expect(out != "\(base)_\(form)", "cs is missing chrome.interviewCount_\(form)")
            #expect(out.contains(String(count)), "cs interviewCount_\(form) dropped {{count}}")
            rendered.append(out)
        }
        // one/few/other are grammatically distinct in Czech — a collapsed
        // binary split would render two of these identically.
        #expect(Set(rendered).count == 3, "cs one/few/other should be distinct: \(rendered)")
    }

    // MARK: - I18n.plural (centralised CLDR selection + _other fallback)

    /// `plural` must select the active locale's CLDR form, byte-identical to the
    /// hand-rolled `t("\(base)_\(category)")` the five call sites used to inline.
    /// Czech exercises one/few/other against a fixture key that carries all
    /// forms, with `{{count}}` interpolated.
    @MainActor @Test func plural_selectsCldrForm_matchesDirectResolution() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        i18n.setLocale("cs")
        let base = "common.pluralFixture.full"
        for (count, form) in [(1, "one"), (3, "few"), (7, "other")] {
            let out = i18n.plural(base, count: count)
            #expect(out == i18n.t("\(base)_\(form)", ["count": String(count)]),
                    "cs count=\(count) should resolve full_\(form)")
            #expect(out.contains(String(count)), "plural dropped {{count}} for \(form)")
        }
    }

    /// The future-proofing guarantee for pl/ru/uk: when the selected category's
    /// stem is absent, `plural` degrades to `_other` rather than leaking the raw
    /// `<base>_<category>` key into chrome. `sparse` carries only `_one`/`_other`,
    /// so a Czech `few` (count 3) request misses and must fall back. This is the
    /// exact code path a `many` miss would take once those locales return `many`
    /// for integers — category-agnostic, so cs's `few` proves it today.
    @MainActor @Test func plural_missingStem_fallsBackToOther() {
        let i18n = I18n()
        i18n.configure(localesDirectory: Self.fixturesURL)
        i18n.setLocale("cs")
        let base = "common.pluralFixture.sparse"
        let out = i18n.plural(base, count: 3)  // cs(3) → "few", sparse_few absent
        #expect(out == i18n.t("\(base)_other", ["count": "3"]),
                "missing sparse_few should fall back to sparse_other")
        #expect(out != "\(base)_few", "must not leak the raw _few key")
        #expect(out.contains("3"), "fallback should still interpolate {{count}}")
    }
}

/// Anchor class for finding the test bundle at runtime.
private class BundleAnchor {}
