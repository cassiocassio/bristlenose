import Foundation

/// One row in the sidebar "lens" rail (spec §3.1, §5). The rail relocates the
/// former toolbar tab Picker into the top of the project sidebar; each lens
/// fires the same `switchToTab` bridge call the Picker did.
///
/// `LensItem.all` is the single source of the lens→Tab→icon mapping — the one
/// silent-regression seam this change introduces (spec §6.4). It's a pure value
/// type (no SwiftUI), mirroring `ProjectSubtitle.resolve`, so it's unit-testable
/// in `LensItemTests`. "lens" is a code-internal term; the product says "tabs"
/// (spec §6.5).
struct LensItem: Identifiable {
    let tab: Tab
    /// SF Symbol per spec §5 (settled icon set).
    let systemImage: String

    var id: String { tab.rawValue }

    /// Full sidebar label — the rail has the width, so it shows "Codebook" not
    /// the toolbar Picker's short "Codes". Reuses `Tab.fullLocalizedLabel` so the
    /// i18n fallback chain lives in one place.
    @MainActor func label(_ i18n: I18n) -> String {
        tab.fullLocalizedLabel(i18n)
    }

    /// The lenses, in sidebar order. Icons per spec §5 (settled).
    ///
    /// Codebook v2 was a second row here in DEBUG while it was built; it
    /// became the only Codebook lens on 31 Aug 2026 and took `tag` back from
    /// the temporary `tag.square` that distinguished the two.
    ///
    /// Discussion goes last of the shipping lenses, after Signals, so the five
    /// older lenses keep ⌘1–⌘5 and it takes ⌘6 (`questionmark.bubble`, chosen
    /// 3 Oct 2026). It was a flagged preview row until it shipped for beta the
    /// same day.
    ///
    /// Computed, not stored: the Screens row follows the Diagnostics
    /// preference (`docs/design-screens.md` — a rough lens for one trusted
    /// tester). Views that iterate this observe
    /// `@AppStorage(DiagnosticsPreference.key)` so they redraw on the switch —
    /// the shape the Discussion preview used while it rode its flag.
    static var all: [LensItem] {
        rail(.standard)
    }

    /// The rail a given defaults domain asks for — `all`, with the domain
    /// injectable so a test can read both states without writing the
    /// researcher's own preference.
    static func rail(_ defaults: UserDefaults) -> [LensItem] {
        lenses(screens: DiagnosticsPreference.isEnabled(defaults))
    }

    /// The rail for a given Diagnostics state — pure, so both states are
    /// testable. Screens goes after Discussion, so every shipping lens keeps its
    /// number and it takes ⌘7 (`macwindow.on.rectangle`: the windows and pages
    /// a participant shared).
    static func lenses(screens: Bool) -> [LensItem] {
        var lenses: [LensItem] = [
            LensItem(tab: .project,    systemImage: "target"),
            LensItem(tab: .sessions,   systemImage: "person.2"),
            LensItem(tab: .quotes,     systemImage: "text.quote"),
            LensItem(tab: .codebook,   systemImage: "tag"),
            LensItem(tab: .signals,    systemImage: "square.grid.3x3"),
            LensItem(tab: .discussion, systemImage: "questionmark.bubble"),
        ]
        if screens {
            lenses.append(LensItem(tab: .screens, systemImage: "macwindow.on.rectangle"))
        }
        return lenses
    }

    /// Icon for `tab`, resolved from `all` so every surface that shows a lens
    /// glyph reads the *same* settled set — the sidebar rail and the View menu's
    /// ⌘-number items can't drift apart. Read with Screens on, so a remembered
    /// Screens lens never draws a placeholder circle on a machine where
    /// Diagnostics is off. That set covers every `Tab` case (pinned by
    /// `LensItemTests`), so the fallback is unreachable; it exists only to keep
    /// the return non-optional at call sites.
    static func systemImage(for tab: Tab) -> String {
        lenses(screens: true).first { $0.tab == tab }?.systemImage ?? "circle"
    }
}
