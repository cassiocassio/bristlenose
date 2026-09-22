import Foundation
import Testing

@testable import Bristlenose

/// The Swift half of one CLDR rule that exists twice.
///
/// `I18n.pluralCategory` serves the Mac menus; `bristlenose/i18n.py`'s
/// `plural_category` serves the CLI and the server, and the server is what
/// renders a Miro board's per-column counts into a deliverable. Two
/// implementations of one rule drift, so neither owns the answer:
/// `tests/fixtures/cldr-plural-contract.json` does, and
/// `tests/test_plural_category_parity.py` asserts the same file from Python.
///
/// A failure here means the two sides disagree. Fix the implementation that is
/// wrong against the CLDR chart — do not edit the fixture to match.
/// `I18n` is `@MainActor`, so its statics are too — even `pluralCategory`,
/// which is a pure function of `(Int, String)`. Same note as `I18nTests`.
@MainActor
@Suite("CLDR plural contract")
struct PluralCategoryContractTests {

    /// Walk up from this file to `tests/fixtures/cldr-plural-contract.json`,
    /// the way `PipelineSummaryTests` does.
    private func contractURL() -> URL {
        // <worktree>/desktop/Bristlenose/BristlenoseTests/<this file>
        let here = URL(fileURLWithPath: #filePath)
        let worktree = here
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        return worktree.appendingPathComponent("tests/fixtures/cldr-plural-contract.json")
    }

    private func loadContract() throws -> (counts: [Int], categories: [String: [String]]) {
        let data = try Data(contentsOf: contractURL())
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let counts = json?["counts"] as? [Int],
              let categories = json?["categories"] as? [String: [String]]
        else {
            Issue.record("cldr-plural-contract.json is not the expected shape")
            return ([], [:])
        }
        return (counts, categories)
    }

    @Test("Every locale in the contract agrees with pluralCategory")
    func matchesTheContract() throws {
        let (counts, categories) = try loadContract()
        #expect(!counts.isEmpty, "the contract carries no counts — wrong file?")
        for (locale, expected) in categories.sorted(by: { $0.key < $1.key }) {
            let actual = counts.map { I18n.pluralCategory($0, locale: locale) }
            #expect(actual == expected, """
                \(locale) disagrees with the contract:
                  counts   \(counts)
                  swift    \(actual)
                  contract \(expected)
                """)
        }
    }

    @Test("Every locale the app offers has a contract row")
    func everyShippedLocaleIsCovered() throws {
        let (_, categories) = try loadContract()
        let missing = I18n.supportedLocales.filter { categories[$0] == nil }.sorted()
        #expect(missing.isEmpty, """
            \(missing) ship in the app but have no row in the plural contract. \
            Add one on the Python side (it writes the file) so both suites pin \
            the new language's shape rather than letting it fall through.
            """)
    }
}
