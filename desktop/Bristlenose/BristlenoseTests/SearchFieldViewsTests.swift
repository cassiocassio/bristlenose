import AppKit
import SwiftUI
import Testing

@testable import Bristlenose

/// The Quotes search field's native parts (docs/design-search.md §5–§7): the
/// keyboard's decisions, the free-text row's emphasis, and badges painted to
/// the measured box. Driven from the shared contract fixture where it carries
/// the shape, so the views are tested against what the SPA actually sends.
@Suite("Search field views")
@MainActor
struct SearchFieldViewsTests {

    nonisolated private static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .deletingLastPathComponent()
        .appendingPathComponent("tests/fixtures/search-bridge-contract.json")

    private func webToNative() throws -> [String: Any] {
        let data = try Data(contentsOf: Self.fixtureURL)
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        return try #require(json["web_to_native"] as? [String: Any])
    }

    private func tokens() throws -> [SearchTokenChip] {
        let cases = try #require(try webToNative()["quotes_filter_tokens"] as? [[String: Any]])
        return SearchTokenChip.decodeAll(cases.first?["wire"])
    }

    private func styles() throws -> SearchBadgeStyles {
        let s = try #require(try webToNative()["search_badge_styles"] as? [String: Any])
        return SearchBadgeStyles(message: try #require(s["wire"] as? [String: Any]))
    }

    // MARK: keys

    @Test func arrowsMoveTheHighlightByRowAndWrap() {
        let ids = ["text", "person:p3", "tag:zoning"]
        // No highlight means the first row, so ↓ goes to the second.
        #expect(SearchFieldKeys.move(nil, by: 1, rows: ids) == "person:p3")
        #expect(SearchFieldKeys.move(nil, by: -1, rows: ids) == "tag:zoning")
        #expect(SearchFieldKeys.move("person:p3", by: 1, rows: ids) == "tag:zoning")
        #expect(SearchFieldKeys.move("tag:zoning", by: 1, rows: ids) == "text")
        #expect(SearchFieldKeys.move("text", by: -1, rows: ids) == "tag:zoning")
        #expect(SearchFieldKeys.move("text", by: 1, rows: []) == nil)
    }

    /// The highlight is kept by id: when rows re-arrive with the same subjects
    /// in another order, it stays on the same subject; when its row is gone,
    /// the free text (the first row) takes it back.
    @Test func theHighlightFollowsItsRowNotItsPosition() {
        #expect(SearchFieldKeys.highlighted("person:p3", rows: ["text", "tag:zoning", "person:p3"]) == "person:p3")
        #expect(SearchFieldKeys.highlighted("person:p3", rows: ["text", "tag:zoning"]) == "text")
        #expect(SearchFieldKeys.highlighted(nil, rows: ["text", "tag:zoning"]) == "text")
        #expect(SearchFieldKeys.highlighted(nil, rows: []) == nil)
    }

    /// The Mac's delete key sends U+007F; SwiftUI's `.delete` is U+0008 and
    /// never fires (measured 3 Oct 2026). The wiring is what broke, so pin it.
    @Test func backspaceIsWiredToTheKeyTheMacSends() {
        #expect(SearchFieldKeys.deleteKey.character == Character(UnicodeScalar(NSDeleteCharacter)!))
        #expect(SearchFieldKeys.deleteKey != .delete)
    }

    @Test func backspaceSelectsTheLastTokenThenRemovesIt() throws {
        let t = try tokens()
        let last = try #require(t.last?.subject)
        #expect(SearchFieldKeys.backspace(text: "", tokens: t, selected: nil) == .select(last))
        #expect(SearchFieldKeys.backspace(text: "", tokens: t, selected: last) == .remove(last))
        // Another token selected (the list changed under it): select the last.
        #expect(SearchFieldKeys.backspace(text: "", tokens: t, selected: t[0].subject) == .select(last))
        // With text, ⌫ edits the text; with no tokens, there is nothing to do.
        #expect(SearchFieldKeys.backspace(text: "ab", tokens: t, selected: last) == .passThrough)
        #expect(SearchFieldKeys.backspace(text: "", tokens: [], selected: nil) == .passThrough)
    }

    @Test func theListIsOpenOnlyWhileTypingIntoAFocusedFieldWithRows() {
        #expect(SearchFieldKeys.isOpen(focused: true, text: "zo", rows: 2, dismissed: false))
        #expect(!SearchFieldKeys.isOpen(focused: false, text: "zo", rows: 2, dismissed: false))
        #expect(!SearchFieldKeys.isOpen(focused: true, text: "", rows: 2, dismissed: false))
        #expect(!SearchFieldKeys.isOpen(focused: true, text: "zo", rows: 0, dismissed: false))
        #expect(!SearchFieldKeys.isOpen(focused: true, text: "zo", rows: 2, dismissed: true))
    }

    // MARK: rows

    /// Photos' rule: what was typed in primary, the rest in secondary — on
    /// the letters the SPA marked, which the label's emoji and accent would
    /// shift if the offsets were walked as Characters.
    @Test func theFreeTextRowEmphasisesWhatWasTyped() throws {
        let cases = try #require(try webToNative()["search_suggestions"] as? [[String: Any]])
        let menu = SearchSuggestions(message: try #require(cases.first?["wire"] as? [String: Any]))
        let row = menu.rows[0]
        let label = SuggestionLabel.attributed(row, highlighted: false)
        let primary = label.runs.filter { $0.foregroundColor == .primary }.map { String(label[$0.range].characters) }
        #expect(primary == ["zo"])
        // Highlighted, the row is one colour: the system's text on a selection.
        let on = SuggestionLabel.attributed(row, highlighted: true)
        #expect(on.runs.allSatisfy { $0.foregroundColor == SearchMenuColours.selectedText })
    }

    // MARK: chips

    @Test func aChipShowsTheChosenMeaningsWord() throws {
        let t = try tokens()
        #expect(t.map(\.word) == ["mentions", "said by", "not tagged"])
    }

    // MARK: badges

    @Test func cssWeightsMapOntoAppleNamedWeights() {
        #expect(SearchBadgeStyle.appKitWeight(css: 400) == Double(NSFont.Weight.regular.rawValue))
        #expect(SearchBadgeStyle.appKitWeight(css: 600) == Double(NSFont.Weight.semibold.rawValue))
        #expect(SearchBadgeStyle.appKitWeight(css: 50) == Double(NSFont.Weight.ultraLight.rawValue))
        let mid = SearchBadgeStyle.appKitWeight(css: 450)
        #expect(mid > Double(NSFont.Weight.regular.rawValue) && mid < Double(NSFont.Weight.medium.rawValue))
    }

    @Test func aMonoStyleUsesTheMonospacedFace() throws {
        let p3 = try #require(try styles().people["p3"])
        #expect(p3.code.nsFont.fontDescriptor.symbolicTraits.contains(.monoSpace))
        #expect(!(p3.name?.nsFont.fontDescriptor.symbolicTraits.contains(.monoSpace) ?? true))
    }

    /// The badge is the measured box: its height is the line box plus the top
    /// and bottom padding and border, as the card's is. Relational, not in
    /// points, so a system font revision does not break it.
    @Test func aTagBadgeIsTheMeasuredBox() throws {
        let style = try #require(try styles().tags["zoning"])
        let line = try #require(style.lineHeight)
        let size = NSHostingController(rootView: MeasuredTagBadge(text: "Zoning", style: style)).view.fittingSize
        let bw = style.border?.width ?? 0
        #expect(abs(Double(size.height) - (line + style.padY + style.padBottom + 2 * bw)) < 0.5)
        let wider = NSHostingController(rootView: MeasuredTagBadge(text: "Zoning permits", style: style))
            .view.fittingSize
        #expect(wider.width > size.width)
        #expect(abs(wider.height - size.height) < 0.5)
    }

    /// The name half is part of the badge when the report shows a name, and
    /// absent when the person is a code only.
    @Test func aPersonBadgeCarriesItsNameHalfOnlyWhenNamed() throws {
        let style = try #require(try styles().people["p3"])
        let named = NSHostingController(rootView: MeasuredPersonBadge(code: "p3", name: "Priya Shah", style: style))
            .view.fittingSize
        let codeOnly = NSHostingController(rootView: MeasuredPersonBadge(code: "p3", name: nil, style: style))
            .view.fittingSize
        #expect(named.width > codeOnly.width)
    }

    /// Before the first measurement arrives there is no style: the badge is
    /// drawn plainly, never with a guessed colour, and is not empty.
    @Test func anUnmeasuredBadgeIsPlainButPresent() {
        let size = NSHostingController(rootView: MeasuredTagBadge(text: "Zoning", style: nil)).view.fittingSize
        #expect(size.width > 0 && size.height > 0)
    }
}
