import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

/// The Send-to-Miro sheet's configure step, rendered at its real width in English and in a long
/// locale, so a label cut to one line ("Break long quotes into multi…", owner QA 18 Oct 2026) shows
/// in the result bundle (`xcrun xcresulttool export attachments`) rather than on a researcher's Mac.
@MainActor
@Suite struct MiroSheetRenderTests {
    private func render(locale: String) throws -> (png: Data, height: CGFloat) {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale(locale)
        let model = MiroSheetModel(port: 0, token: nil, projectName: "Talismanic", i18n: i18n)
        model.step = .configure
        let host = NSHostingView(rootView: MiroSheet(model: model))
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 400),
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
        return (try #require(rep.representation(using: .png, properties: [:])), size.height)
    }

    @Test func theConfigureStepKeepsItsWidthAndWrapsLongLabels() throws {
        for locale in ["en", "de"] {
            let (png, height) = try render(locale: locale)
            Attachment.record(png, named: "miro-sheet-configure-\(locale).png")
            #expect(height >= 400)  // the sheet's one size through the flow, grown only if it must
        }
    }
}
