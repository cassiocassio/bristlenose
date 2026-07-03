import AppKit

/// Palette-aware colour lookups for the AppKit sidebar — Plan D "sidebar four"
/// (Paper, Ink, Accent, Lozenge).
///
/// Under `palette = "default"`, helpers return the system semantic colour
/// passed as `fallback` (`.labelColor`, etc.) — the sidebar tracks the user's
/// System Settings accent and appearance. Under `palette = "edo"`, helpers
/// return values authored in `Assets.xcassets` (Any + Dark variants — Xcode
/// resolves the appearance match at draw time, no manual dark-mode branch).
///
/// Concepts map onto the CSS palette tokens the web report uses, so the
/// sidebar and the report share one semantic vocabulary. Colorsets are
/// flat-named (`PaletteEdoPaper`, `PaletteEdoInk`, …) — Xcode folder
/// namespacing needs a `provides-namespace` flag not used elsewhere in this
/// asset catalogue; flat names sidestep it.
///
/// **Lozenge is authored, not consumed by AppKit.** The source-list capsule
/// is drawn by AppKit's internal path (see `SourceListSelectionRowView` doc
/// at `ProjectSidebarOutline.swift:1240` — internal composite, no public
/// UI-element-colour token matches it, verified by sampling). The Lozenge
/// colorset exists so the web report and any future SwiftUI selection surface
/// share the same "sympathetic to native" value.
enum SidebarPalette {
    enum Concept: String {
        case paper, ink, accent, lozenge
    }

    /// The active palette, read from `UserDefaults` (same key as
    /// `@AppStorage("palette")` in `AppearanceSettingsView`). Anything other
    /// than `"edo"` collapses to `"default"` — no throw, no log.
    static var current: String {
        let raw = UserDefaults.standard.string(forKey: "palette") ?? "default"
        return raw == "edo" ? "edo" : "default"
    }

    /// Direct asset lookup. Returns a dynamic `NSColor` (resolves Any/Dark
    /// on each draw against the effective `NSAppearance`). Build-time miss
    /// falls back to a sensible system semantic so the miss is visible
    /// rather than transparent placeholder magenta.
    static func nsColor(_ concept: Concept, palette: String = current) -> NSColor {
        let assetName = "Palette" + palette.capitalized + concept.rawValue.capitalized
        if let asset = NSColor(named: assetName) {
            return asset
        }
        switch concept {
        case .paper:   return .windowBackgroundColor
        case .ink:     return .labelColor
        case .accent:  return .controlAccentColor
        case .lozenge: return .selectedContentBackgroundColor
        }
    }

    /// Ink for cell text — Edo Ink under Edo, else the passed system
    /// semantic. Passing `.labelColor` preserves system tracking (dark mode,
    /// increased contrast) on Default.
    static func ink(fallback: NSColor) -> NSColor {
        current == "edo" ? nsColor(.ink, palette: "edo") : fallback
    }

    /// Accent for BN-drawn row glyphs (lens icons, folder icons). Passing
    /// `nil` here mirrors `NSImageView.contentTintColor = nil` — system
    /// picks the tint (label colour, tracking the user's accent).
    static func accent(fallback: NSColor?) -> NSColor? {
        current == "edo" ? nsColor(.accent, palette: "edo") : fallback
    }

    /// Ink override — `nil` under Default (leave whatever the caller had,
    /// which for text usually means system `backgroundStyle` tracking), Edo
    /// Ink under Edo. Use at sites where the existing code did NOT force a
    /// text colour and you want to preserve that hands-off behaviour on
    /// Default while still shifting to Ink on Edo.
    static var inkOverride: NSColor? {
        current == "edo" ? nsColor(.ink, palette: "edo") : nil
    }

    /// Accent override — same "nil on Default" semantics as `inkOverride`.
    /// Preserves the system's `backgroundStyle`-driven icon tinting on
    /// Default (selected row → system accent) while forcing Edo Accent on
    /// Edo (consistent Prussian across all rows, selected or not).
    static var accentOverride: NSColor? {
        current == "edo" ? nsColor(.accent, palette: "edo") : nil
    }

    /// Sidebar paper tint. Nil under Default (leave the system material
    /// untouched); a parchment `NSColor` under Edo, to be composited at
    /// low alpha above the sidebar material. The alpha is applied at the
    /// consumer site so this stays a token, not a rendered value.
    static var paperTint: NSColor? {
        current == "edo" ? nsColor(.paper, palette: "edo") : nil
    }
}
