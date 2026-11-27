import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

// The paywall's footnote links (Terms, Privacy, Restore Purchases, Manage
// Subscription) broke mid-word in 12 of 21 locales at the old 460 pt sheet.
// Owner, 27 Nov 2026: "make German work and stack the others". So German is
// on one line, and a locale whose line is wider than the sheet stacks its
// links, one a line, rather than wrapping inside a label.
//
// The widths are SwiftUI's own, on this Mac's system font: German has 9 pt
// to spare, and a font with wider metrics would stack it (legible, not
// broken), which this suite reports as a failure of the German case only.

@Suite("Paywall link row")
@MainActor
struct PaywallLinkRowTests {

    nonisolated private static let localesURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("bristlenose/locales")

    /// Every full locale on disk. zh-Hant-HK is a thin override fork and
    /// inherits these keys from zh-Hant.
    nonisolated private static var locales: [String] {
        let dirs = (try? FileManager.default.contentsOfDirectory(atPath: localesURL.path)) ?? []
        return dirs.filter { I18n.supportedLocales.contains($0) && $0 != "zh-Hant-HK" }.sorted()
    }

    /// The locale, loaded: `t` falls back to English, so a locale that failed
    /// to load would otherwise measure English and pass.
    private func i18n(_ locale: String) -> I18n {
        let i = I18n()
        i.configure(localesDirectory: Self.localesURL)
        i.setLocale(locale)
        #expect(i.locale == locale)
        if locale != "en" {
            #expect(i.t("desktop.subscription.restore") != "Restore Purchases", "\(locale) did not load")
        }
        return i
    }

    private func same(_ a: CGFloat, _ b: CGFloat) -> Bool { abs(a - b) < 0.5 }

    private func size<V: View>(_ view: V) -> CGSize {
        NSHostingView(rootView: view).fittingSize
    }

    private func row(_ i: I18n, manage: Bool) -> PaywallLinkRow {
        PaywallLinkRow(i18n: i, manage: manage, working: false, restore: {})
    }

    @Test("Every shipped locale is found")
    func localesAreFound() {
        #expect(Self.locales.count == 21)
    }

    @Test("German's links are on one line")
    func germanIsOneLine() {
        let i = i18n("de")
        let line = size(row(i, manage: true).line)
        #expect(line.width <= PaywallView.contentWidth,
                "German's link row is \(line.width) pt; the sheet has \(PaywallView.contentWidth) pt")
    }

    @Test("The links are on one line where it fits, otherwise one a line, never broken",
          arguments: PaywallLinkRowTests.locales, [true, false])
    func oneLineOrStacked(locale: String, manage: Bool) {
        let i = i18n(locale)
        let r = row(i, manage: manage)
        let line = size(r.line), stack = size(r.stack)
        let shown = size(r.frame(width: PaywallView.contentWidth, alignment: .leading))
        let expected = line.width <= PaywallView.contentWidth ? line : stack
        #expect(same(shown.height, expected.height),
                "\(locale): \(shown.height) pt tall; one line is \(line.height), stacked \(stack.height)")
        #expect(stack.width <= PaywallView.contentWidth, "\(locale): a single link is wider than the sheet")
    }

    /// The stacked layout in every locale, not only in the one (Russian) that
    /// needs it today: a row one point too narrow for its line stacks, and
    /// stacked is taller than the line.
    @Test("A row too narrow for its line stacks its links, in every locale",
          arguments: PaywallLinkRowTests.locales, [true, false])
    func tooNarrowStacks(locale: String, manage: Bool) {
        let i = i18n(locale)
        let r = row(i, manage: manage)
        let line = size(r.line), stack = size(r.stack)
        let shown = size(r.frame(width: line.width - 1, alignment: .leading))
        #expect(stack.height > line.height + 1)
        #expect(same(shown.height, stack.height),
                "\(locale): \(shown.height) pt tall; stacked is \(stack.height)")
    }

    @Test("Russian's offer face stacks at the sheet's width")
    func russianOfferStacks() {
        let i = i18n("ru")
        let r = row(i, manage: true)
        let line = size(r.line), stack = size(r.stack)
        #expect(line.width > PaywallView.contentWidth)
        let shown = size(r.frame(width: PaywallView.contentWidth, alignment: .leading))
        #expect(same(shown.height, stack.height))
    }
}
