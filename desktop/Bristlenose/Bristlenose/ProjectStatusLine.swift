import AppKit
import SwiftUI

/// The one builder for a project row's status line (the second line of the
/// two-line sidebar cell).
///
/// **The contract, whatever the kind:** the returned view draws `text` from its
/// own leading edge at any width it is given, truncates at the tail, and yields
/// horizontally before the row's trailing ring or badge does. The cell pins the
/// view's leading edge and may stretch it; no kind may answer a stretch by
/// centring. Pinned by `ProjectStatusLineTests`, which draws every kind
/// stretched and reads where the ink starts.
///
/// It exists because the three kinds are three unrelated view types with three
/// different defaults: a label draws from the left, an `NSButton` centres its
/// title, and SwiftUI centres unframed content in a wider `NSHostingView`. (A
/// hosting view whose content has a maximum width also carries its own required
/// max-size constraint, which fights the row's trailing pin; content that fills,
/// as `fillAlignment` makes it, has no maximum and so no fight.) Built
/// inline, each branch had to remember alignment for itself, and the shimmer
/// branch did not (16 Nov 2026: "Screens · 2 of 3" sat centred under the name).
/// A new kind goes here, and into the test's list.
enum ProjectStatusLine {

    enum Kind {
        /// Static text.
        case plain
        /// The thinking shimmer (design-motion §4.7.1). The caller has already
        /// gated it on the animation preference and Reduce Motion.
        case shimmer
        /// Text that is a control. The caller makes the button (its target,
        /// action and payload are the caller's); this styles it to read exactly
        /// like `.plain`.
        case button(NSButton)
    }

    static func make(text: String, kind: Kind) -> NSView {
        let view: NSView
        switch kind {
        case .plain:
            let field = NSTextField(labelWithString: text)
            field.font = ProjectCellSpec.subtitleFont
            field.textColor = .secondaryLabelColor
            field.lineBreakMode = .byTruncatingTail
            view = field
        case .shimmer:
            view = NSHostingView(rootView: ShimmerText(
                text: text,
                rest: Color(nsColor: .secondaryLabelColor),
                font: Font(ProjectCellSpec.subtitleFont as CTFont),
                lineLimit: 1,
                fillAlignment: .leading))
        case .button(let button):
            button.isBordered = false
            button.setButtonType(.momentaryChange)
            button.alignment = .natural       // NSButton centres by default.
            let para = NSMutableParagraphStyle()
            para.lineBreakMode = .byTruncatingTail
            para.alignment = .natural
            // No underline, no tint: indistinguishable from the plain label.
            button.attributedTitle = NSAttributedString(string: text, attributes: [
                .font: ProjectCellSpec.subtitleFont,
                .foregroundColor: NSColor.secondaryLabelColor,
                .paragraphStyle: para,
            ])
            button.setAccessibilityLabel(text)
            view = button
        }
        view.translatesAutoresizingMaskIntoConstraints = false
        // Yield (truncate) before pushing the trailing ring/glyph off the edge,
        // and accept a stretch without resisting it.
        view.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        view.setContentHuggingPriority(.defaultLow, for: .horizontal)
        return view
    }
}
