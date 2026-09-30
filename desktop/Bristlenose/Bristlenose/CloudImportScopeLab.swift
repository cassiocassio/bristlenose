import AppKit
import SwiftUI

// Diagnostics ▸ Cloud Import ▸ Scope Control / Window Tint.
//
// The import window's "Last 30 days ⌄" sits in a Liquid Glass capsule as big as
// the search field beside it, and reads in accent blue like a link. A review on
// 30 Sep 2026 produced five placements and two colour levers, and most of what
// separates them — does an un-glassed toolbar item still answer hover, which
// source makes it blue, how heavy a footer pull-down feels — cannot be settled
// by reading code, because `ImageRenderer` does not draw toolbars. So every
// option is switchable live here, against a real listing.
//
// Both keys are unset on every machine that has not used this menu, which is
// the shipping rendering: nothing below changes a build nobody has touched.
// Remove the lab once a choice lands.

/// How the time-scope control is drawn and where it lives.
enum ScopeLabStyle: String, CaseIterable, Identifiable {
    /// What ships: borderless pull-down, toolbar glass, window tint.
    case shipping
    /// Option 2 — keep the glass, take the colour out.
    case glassPrimary
    case glassSecondary
    /// The glass alone off, colour untouched — isolates the capsule from the blue.
    case noGlass
    /// Option 1 — no glass, neutral colour.
    case noGlassSecondary
    /// Option 1 in the non-deprecated spelling the SDK 27 interface asks for
    /// (`.menuStyle(.button)` + `.buttonStyle(.borderless)`).
    case noGlassButtonBorderless
    /// Option 3 — the scope qualifies the footer's count.
    case footer
    /// Option 4 — stated in the subtitle, no control (the View-menu twin that
    /// would make this viable is not built).
    case subtitleOnly
    /// Option 5 — a Finder-style scope bar under the toolbar.
    case scopeBar

    static let key = "BristlenoseDiagImportScopeStyle"

    var id: String { rawValue }

    var menuTitle: String {
        switch self {
        case .shipping:                return "Shipping — glass, window tint"
        case .glassPrimary:            return "Glass, primary colour"
        case .glassSecondary:          return "Glass, secondary colour"
        case .noGlass:                 return "No glass, window tint"
        case .noGlassSecondary:        return "No glass, secondary colour"
        case .noGlassButtonBorderless: return "No glass, .button + .borderless, secondary"
        case .footer:                  return "In the footer, after the count"
        case .subtitleOnly:            return "Subtitle only, no control"
        case .scopeBar:                return "Scope bar under the toolbar"
        }
    }

    /// Whether the control is a toolbar item at all.
    var inToolbar: Bool {
        switch self {
        case .footer, .subtitleOnly, .scopeBar: return false
        default: return true
        }
    }

    var hidesToolbarGlass: Bool {
        switch self {
        case .noGlass, .noGlassSecondary, .noGlassButtonBorderless: return true
        default: return false
        }
    }
}

/// Which tint the import window's scene carries — the other suspect for the blue.
enum ScopeLabTint: String, CaseIterable, Identifiable {
    /// What ships: the palette's fixed accent (`#007AFF` on Default).
    case palette
    /// The user's own System Settings accent (Graphite, Purple, …).
    case systemAccent
    /// No tint on the window at all.
    case none

    static let key = "BristlenoseDiagImportWindowTint"

    var id: String { rawValue }

    var menuTitle: String {
        switch self {
        case .palette:      return "Palette accent (shipping)"
        case .systemAccent: return "System Settings accent"
        case .none:         return "No window tint"
        }
    }
}

/// The scope pull-down, drawn per `style`. The choices are passed in so the
/// one-of-N `Picker` (and its checkmark) stays the window's own.
struct ScopeLabMenu<Choices: View>: View {
    let style: ScopeLabStyle
    let title: String
    let help: String
    @ViewBuilder let choices: () -> Choices

    var body: some View {
        styled
            .fixedSize()
            .help(help)
    }

    @ViewBuilder
    private var styled: some View {
        let menu = Menu { choices() } label: { Text(title) }
        switch style {
        case .glassPrimary:
            menu.menuStyle(.borderlessButton).tint(.primary)
        case .glassSecondary, .noGlassSecondary:
            menu.menuStyle(.borderlessButton).tint(.secondary)
        case .noGlassButtonBorderless:
            menu.menuStyle(.button).buttonStyle(.borderless).tint(.secondary)
        case .footer:
            menu.menuStyle(.button).buttonStyle(.borderless).tint(.secondary)
                .controlSize(.small)
        case .shipping, .noGlass, .subtitleOnly, .scopeBar:
            menu.menuStyle(.borderlessButton)
        }
    }
}

/// Option 5's bar: one push-button per window choice, Finder-scope-bar style.
struct ScopeLabBar: View {
    let choices: [Int]
    @Binding var selection: Int
    let label: (Int) -> String

    var body: some View {
        HStack(spacing: 4) {
            ForEach(choices, id: \.self) { days in
                Toggle(label(days), isOn: Binding(
                    get: { selection == days },
                    set: { if $0 { selection = days } }
                ))
                .toggleStyle(.button)
            }
            Spacer()
        }
        .buttonStyle(.accessoryBar)
        .padding(.horizontal, 12)
        .padding(.vertical, 5)
    }
}

/// Re-tints the import window when the Diagnostics tint is not the shipping
/// one. Inner `.tint` wins over the scene's, so the shipping case adds nothing.
struct ScopeLabWindowTint: ViewModifier {
    @AppStorage(ScopeLabTint.key) private var tint: ScopeLabTint = .palette

    func body(content: Content) -> some View {
        switch tint {
        case .palette:      content
        case .systemAccent: content.tint(Color(nsColor: .controlAccentColor))
        case .none:         content.tint(nil)
        }
    }
}
