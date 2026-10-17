import AppKit

/// Palette-aware colour lookups for the AppKit sidebar — Plan D "sidebar four"
/// (Paper, Ink, Accent, Lozenge).
///
/// Under `palette = "default"`, helpers return the system semantic colour
/// passed as `fallback` (`.labelColor`, etc.) — the sidebar tracks the user's
/// System Settings accent and appearance. Under any other palette (Edo and
/// the brand palettes), helpers return that palette's colorsets in
/// `Assets.xcassets` (Any + Dark variants — Xcode resolves the appearance match
/// at draw time, no manual dark-mode branch). Edo's were hand-authored; the
/// brand palettes' are written by `experiments/brand-palettes/gen.py` from the
/// same CSS tokens the report uses.
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
        /// Speaker-badge chip (sessions popover). Under Default these resolve
        /// to SYSTEM semantics, never sampled CSS hexes —
        /// `design-native-colour-alignment.md` §Principles: the CSS palette
        /// *samples* the OS colours (re-sampled at OS bumps) precisely because
        /// no canonical hex exists; in Swift we hold the live `NSColor`, so
        /// porting a sampled hex would run that pipeline backwards. System
        /// semantics also track appearance, Increase Contrast AND
        /// `backgroundStyle` for free, which is what lets the badge respond to
        /// the selection capsule instead of floating on it. Under Edo the
        /// colorsets (`PaletteEdoBadgebackground` / `PaletteEdoBadgetext`) are
        /// generated from `palette-edo.css`, not hand-authored; until they land
        /// the asset miss falls back to the same system semantics below.
        case badgeBackground, badgeText
        /// The chip's 1 pt outline, the web badge's `--bn-colour-border`. The
        /// system separator is that same hairline (10% label on either
        /// appearance; the CSS token samples it as #e5e7eb / #2d2d2d).
        case badgeBorder
    }

    /// Palettes that tint the native sidebar — every palette except Default,
    /// which leaves the system colours alone. Mirrors the picker in
    /// `AppearanceSettingsView` and `PALETTES` in the frontend.
    static let tinted: Set<String> = ["edo", "catppuccin", "gruvbox", "rose-pine", "solarized"]

    /// The active palette, read from `UserDefaults` (same key as
    /// `@AppStorage("palette")` in `AppearanceSettingsView`). An unknown value
    /// collapses to `"default"` — no throw, no log.
    static var current: String { normalised(UserDefaults.standard.string(forKey: "palette")) }

    static func normalised(_ raw: String?) -> String {
        guard let raw, tinted.contains(raw) else { return "default" }
        return raw
    }

    /// True when the active palette tints the sidebar.
    static var isTinted: Bool { current != "default" }

    /// The colorset stem for a palette id: "rose-pine" → "RosePine". Asset
    /// names carry no hyphen, so `String.capitalized` alone is wrong here.
    static func assetStem(_ palette: String) -> String {
        palette.split(separator: "-").map { $0.prefix(1).uppercased() + $0.dropFirst() }.joined()
    }

    /// The colorset name for a concept, e.g. `PaletteRosePineAccent`.
    static func assetName(_ concept: Concept, palette: String = current) -> String {
        "Palette" + assetStem(normalised(palette)) + concept.rawValue.capitalized
    }

    /// Direct asset lookup. Returns a dynamic `NSColor` (resolves Any/Dark
    /// on each draw against the effective `NSAppearance`). Build-time miss
    /// falls back to a sensible system semantic so the miss is visible
    /// rather than transparent placeholder magenta.
    static func nsColor(_ concept: Concept, palette: String = current) -> NSColor {
        if let asset = NSColor(named: assetName(concept, palette: palette)) {
            return asset
        }
        switch concept {
        case .paper:           return .windowBackgroundColor
        case .ink:             return .labelColor
        case .accent:          return .controlAccentColor
        case .lozenge:         return .selectedContentBackgroundColor
        case .badgeBackground: return .quaternaryLabelColor
        case .badgeText:       return .secondaryLabelColor
        case .badgeBorder:     return .separatorColor
        }
    }

    /// Ink for cell text — the palette's Ink when tinted, else the passed
    /// system semantic. Passing `.labelColor` preserves system tracking (dark
    /// mode, increased contrast) on Default.
    static func ink(fallback: NSColor) -> NSColor {
        isTinted ? nsColor(.ink) : fallback
    }

    /// Accent for BN-drawn row glyphs (lens icons, folder icons). Passing
    /// `nil` here mirrors `NSImageView.contentTintColor = nil` — system
    /// picks the tint (label colour, tracking the user's accent).
    static func accent(fallback: NSColor?) -> NSColor? {
        isTinted ? nsColor(.accent) : fallback
    }

    /// Ink override — `nil` under Default (leave whatever the caller had,
    /// which for text usually means system `backgroundStyle` tracking), the
    /// palette's Ink when tinted. Use at sites where the existing code did NOT
    /// force a text colour and you want to preserve that hands-off behaviour
    /// on Default while still shifting to Ink on a tinted palette.
    static var inkOverride: NSColor? {
        isTinted ? nsColor(.ink) : nil
    }

    /// Accent override — same "nil on Default" semantics as `inkOverride`.
    /// Preserves the system's `backgroundStyle`-driven icon tinting on
    /// Default (selected row → system accent) while forcing the palette's
    /// Accent when tinted (one accent across all rows, selected or not).
    static var accentOverride: NSColor? {
        isTinted ? nsColor(.accent) : nil
    }

    /// Sidebar paper tint. Nil under Default (leave the system material
    /// untouched); the palette's Paper when tinted, to be composited at low
    /// alpha above the sidebar material. The alpha is applied at the consumer
    /// site so this stays a token, not a rendered value.
    static var paperTint: NSColor? {
        isTinted ? nsColor(.paper) : nil
    }
}
