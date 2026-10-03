#if DEBUG
import AppKit
import Testing
@testable import Bristlenose

/// Picker Lab's native rows: the house speaker badge in a pinned column, then
/// the name in the menu font (design-people.md, iteration 3, the owner's
/// hybrid of 3 Oct 2026).
@MainActor
@Suite("Picker Lab rows")
struct PickerRowViewTests {
    private func row(_ code: String, _ name: String, column: CGFloat,
                     editable: Bool = false, metrics: PickerMetrics = .init(small: false)) -> PickerRowView {
        let field = editable ? PickerRowView.nameField(text: "", prompt: "New moderator")
                             : NSTextField(labelWithString: name)
        field.font = metrics.nameFont
        let r = PickerRowView(tick: code == "p1", lead: PickerBadge(code: code, proposed: false),
                              name: field, column: column, metrics: metrics)
        r.frame = NSRect(x: 0, y: 0, width: 260, height: metrics.rowHeight)
        r.layoutSubtreeIfNeeded()
        return r
    }

    @Test func namesLineUpAcrossCodesOfDifferentWidths() {
        let column = ["p1", "p10"].map(SpeakerBadgeView.width(for:)).max()!
        let narrow = row("p1", "Sarah Chen", column: column)
        let wide = row("p10", "Mickael Hurley", column: column)
        #expect(SpeakerBadgeView.width(for: "p1") < SpeakerBadgeView.width(for: "p10"))
        #expect(narrow.name.frame.minX == wide.name.frame.minX)
    }

    /// Typing a long name used to squeeze the new row's code into an ellipsis.
    @Test func theNewRowsCodeKeepsItsWidthWhileTyping() {
        let r = row("m3", "", column: SpeakerBadgeView.width(for: "m3"), editable: true)
        r.name.stringValue = String(repeating: "A very long new moderator name ", count: 5)
        r.layoutSubtreeIfNeeded()
        #expect(r.lead.frame.width == SpeakerBadgeView.width(for: "m3"))
    }

    @Test func smallUsesTheSmallMenuFontAndKeepsTheRow() {
        #expect(PickerMetrics(small: true).nameFont.pointSize == NSFont.systemFontSize(for: .small))
        #expect(PickerMetrics(small: false).nameFont.pointSize == NSFont.systemFontSize)
        #expect(PickerMetrics(small: true).rowHeight == PickerMetrics(small: false).rowHeight)
    }

    /// A picture of the rows at both sizes, light and dark, attached to the
    /// result bundle (`xcresulttool export attachments`) for a reviewer's eye.
    @Test func renderForReview() throws {
        let width: CGFloat = 300
        let codes = [("p1", "Sarah Chen"), ("p2", "Dr Amara Nwosu"), ("p10", "Mickael Hurley")]
        for small in [false, true] {
            for dark in [false, true] {
                let m = PickerMetrics(small: small)
                let column = (codes.map(\.0) + ["p11"]).map(SpeakerBadgeView.width(for:)).max()!
                let stack = NSView(frame: NSRect(x: 0, y: 0, width: width, height: m.rowHeight * 4 + 16))
                stack.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
                stack.wantsLayer = true
                stack.layer?.backgroundColor = (dark ? NSColor.black : NSColor.white).cgColor
                var y = stack.frame.height - 8 - m.rowHeight
                for (i, (code, name)) in (codes + [("p11", "")]).enumerated() {
                    let r = row(code, name, column: column, editable: i == codes.count, metrics: m)
                    r.frame.origin = NSPoint(x: 12, y: y)
                    stack.addSubview(r)
                    y -= m.rowHeight
                }
                stack.layoutSubtreeIfNeeded()
                let rep = try #require(stack.bitmapImageRepForCachingDisplay(in: stack.bounds))
                stack.cacheDisplay(in: stack.bounds, to: rep)
                let png = try #require(rep.representation(using: .png, properties: [:]))
                Attachment.record(png, named: "picker-rows-\(small ? "small" : "regular")-\(dark ? "dark" : "light").png")
            }
        }
    }
}
#endif
