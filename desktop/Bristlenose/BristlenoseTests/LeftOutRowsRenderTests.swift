import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

/// The rows a done-with-warnings run's popover draws, rendered with the shipped locale files so
/// the glyph, the session id column and the plural text show in the result bundle
/// (`xcrun xcresulttool export attachments`) rather than only on a researcher's Mac.
@MainActor
@Suite struct LeftOutRowsRenderTests {
    private func render(locale: String, rows: [(sessionID: String, count: Int)]) throws -> (png: Data, size: CGSize) {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale(locale)
        let host = NSHostingView(rootView: LeftOutRows(rows: rows, i18n: i18n).padding(12).frame(width: 320))
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 320, height: 200),
                              styleMask: [.borderless], backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: .aqua)
        window.contentView = host
        host.layoutSubtreeIfNeeded()
        let size = host.fittingSize
        window.setContentSize(size)
        host.frame = NSRect(origin: .zero, size: size)
        host.layoutSubtreeIfNeeded()
        let rep = try #require(host.bitmapImageRepForCachingDisplay(in: host.bounds))
        host.cacheDisplay(in: host.bounds, to: rep)
        withExtendedLifetime(i18n) {}
        return (try #require(rep.representation(using: .png, properties: [:])), size)
    }

    @Test func theRowsDrawAtTheirRealWidthInThreeLanguages() throws {
        let rows = [(sessionID: "s2", count: 1), (sessionID: "s10", count: 3), (sessionID: "s11", count: 21)]
        for locale in ["en", "de", "ru"] {
            let (png, size) = try render(locale: locale, rows: rows)
            Attachment.record(png, named: "left-out-rows-\(locale).png")
            // three rows, each at least a footnote line tall, none cut to nothing
            #expect(size.height > 50)
        }
    }

    @Test func theCountSaysItsPluralFormInEnglishAndRussian() throws {
        let en = I18n()
        en.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        en.setLocale("en")
        #expect(ProjectDiagnosticPopover.leftOutText(count: 1, i18n: en) == "1 quote left out")
        #expect(ProjectDiagnosticPopover.leftOutText(count: 3, i18n: en) == "3 quotes left out")
        let ru = I18n()
        ru.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        ru.setLocale("ru")
        // CLDR: 1 one, 3 few, 5 many, 21 one
        #expect(ProjectDiagnosticPopover.leftOutText(count: 1, i18n: ru) == "Пропущена 1 цитата")
        #expect(ProjectDiagnosticPopover.leftOutText(count: 3, i18n: ru) == "Пропущено 3 цитаты")
        #expect(ProjectDiagnosticPopover.leftOutText(count: 5, i18n: ru) == "Пропущено 5 цитат")
        #expect(ProjectDiagnosticPopover.leftOutText(count: 21, i18n: ru) == "Пропущена 21 цитата")
    }

    /// The whole popover, as `NSPopover` would draw it, for a run that only left quotes out:
    /// headline, glyph and rows together. Attached to the result bundle.
    @Test func theWholePopoverDrawsForARunThatOnlyLeftQuotesOut() throws {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        var summary = PipelineSummary(
            transcripts: StageOutcome(attempted: 3, succeeded: 3, durationMs: 412_000, failed: []),
            topics: StageOutcome(attempted: 3, succeeded: 3, durationMs: 41_000, failed: []),
            quotes: StageOutcome(attempted: 3, succeeded: 3, durationMs: 82_000, failed: []),
            themes: StageOutcome(attempted: 1, succeeded: 1, durationMs: 14_000, failed: []))
        summary.quotesLeftOut = ["s2": 1, "s3": 3]
        let project = Project(id: UUID(), name: "Talismanic", path: "/tmp/talismanic")
        let view = ProjectDiagnosticPopover(
            project: project, state: .completedPartial(summary: summary), liveData: PipelineLiveData()
        ).environmentObject(i18n)
        let host = NSHostingView(rootView: view)
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 360, height: 300),
                              styleMask: [.borderless], backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: .aqua)
        window.contentView = host
        host.layoutSubtreeIfNeeded()
        let size = host.fittingSize
        window.setContentSize(size)
        host.frame = NSRect(origin: .zero, size: size)
        host.layoutSubtreeIfNeeded()
        let rep = try #require(host.bitmapImageRepForCachingDisplay(in: host.bounds))
        host.cacheDisplay(in: host.bounds, to: rep)
        Attachment.record(try #require(rep.representation(using: .png, properties: [:])),
                          named: "popover-quotes-left-out.png")
        withExtendedLifetime(i18n) {}
        #expect(size.height > 80)
    }
}
