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
    static let all: [LensItem] = {
        var lenses: [LensItem] = [
            LensItem(tab: .project,  systemImage: "target"),
            LensItem(tab: .sessions, systemImage: "person.2"),
            LensItem(tab: .quotes,   systemImage: "text.quote"),
            LensItem(tab: .codebook, systemImage: "tag"),
        ]
        lenses.append(LensItem(tab: .analysis, systemImage: "square.grid.3x3"))
        return lenses
    }()

    /// Icon for `tab`, resolved from `all` so every surface that shows a lens
    /// glyph reads the *same* settled set — the sidebar rail and the View menu's
    /// ⌘1–⌘5 items can't drift apart. `all` covers every `Tab` case (pinned by
    /// `LensItemTests`), so the fallback is unreachable; it exists only to keep
    /// the return non-optional at call sites.
    static func systemImage(for tab: Tab) -> String {
        all.first { $0.tab == tab }?.systemImage ?? "circle"
    }
}
