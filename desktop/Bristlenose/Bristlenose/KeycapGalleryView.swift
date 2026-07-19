#if DEBUG
import SwiftUI
import AppKit

/// Debug ▸ Keycap Gallery — the **native half** of "how do we show a key to
/// press?" Mirrors `docs/mockups/keycap-gallery.html` skin-for-skin (A–F) so a
/// SwiftUI cap can be held up against the CSS one across the sRGB (web) ↔
/// device-P3 (SwiftUI) seam. The decisions both halves build to are frozen in
/// `docs/design-keycaps.md`.
///
/// NOT a shipping surface — `#if DEBUG`, launched from the Debug menu like
/// Shimmer Tuner / Type Parity Inspector, and carries `.commandsRemoved()` on
/// its Window scene (per the debug-window-menu-doubling rule).
///
/// The one native decision this view exists to make concrete: **Unicode glyph
/// vs SF Symbol**. Toggle "SF Symbols" and compare. On macOS the Unicode glyph
/// renders from SF Pro and already matches the menu bar exactly; SF Symbols buy
/// you weight/scale control and optical alignment at the cost of a per-key
/// symbol lookup. Both paths are wired here so the choice is by eye, not theory.
struct KeycapGalleryView: View {
    @State private var dark = false
    @State private var useSF = false     // Unicode glyph (false) vs SF Symbol (true)
    @State private var split = false     // joined (⇧⌘S) vs split (⇧ ⌘ S)

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 30) {
                intro
                glyphNote
                skins
                composition
                inContext
                recommendation
            }
            .padding(30)
            .frame(maxWidth: 720, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color.token(.bg))
        .preferredColorScheme(dark ? .dark : .light)
        .toolbar {
            ToolbarItemGroup {
                Toggle("SF Symbols", isOn: $useSF)
                Toggle("Split", isOn: $split)
                Toggle("Dark", isOn: $dark)
            }
        }
        .frame(minWidth: 620, minHeight: 640)
    }

    // MARK: Sections

    private var intro: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Keycap Gallery")
                .font(.system(size: 22, weight: .semibold))
            Text("Six native skins for a key to press, mirroring the CSS gallery. Toggle SF Symbols to compare the two glyph sources; toggle Split to see joined vs discrete caps.")
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var glyphNote: some View {
        sectionCard {
            heading("Unicode vs SF Symbol")
            Text("On macOS the Unicode modifier glyphs live in SF Pro, so plain text already matches the menu bar. SF Symbols (command / option / shift / control / return / escape / delete.left / arrow.up) give weight + scale control and optical alignment — the native upgrade. Note: there is **no** SF Symbol for Tab; fall back to the ⇥ glyph (U+21E5).")
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 18) {
                labelled("Unicode") { Text("⇧⌘S").font(.system(size: 15, design: .monospaced)) }
                labelled("SF Symbol") {
                    HStack(spacing: 1) {
                        Image(systemName: "shift"); Image(systemName: "command"); Text("S")
                    }.font(.system(size: 15))
                }
            }
        }
    }

    private var skins: some View {
        VStack(alignment: .leading, spacing: 14) {
            heading("The six skins").padding(.top, 4)

            skinRow("A", "Flat", "Quietest cap — dense inline use.", .flat,
                    [.shift, .command, .char("S")])
            skinRow("B", "Raised", "Physical key — help & teaching. Recommended default.", .raised,
                    [.shift, .command, .char("S")], recommended: true)
            skinRow("C", "Outline", "Border only — vanishes into tinted panels.", .outline,
                    [.command, .char("K")])
            skinRow("D", "Solid", "Inverted chip — one hero shortcut per screen.", .solid,
                    [.command, .char("K")])
            skinRow("E", "Mono grid", "Uniform caps for aligned help lists.", .grid,
                    [.shift, .char("K")], recommended: true)
            skinRow("F", "Bare", "No cap — native menu/row idiom & CLI parity.", .bare,
                    [.command, .char("F")])
        }
    }

    private var composition: some View {
        sectionCard {
            heading("Joined vs split")
            Text("Joined = menu-bar truth, compact (default for glyphs). Split = teachable, each key discrete (onboarding + spelled-out words). Toggle “Split” in the toolbar to drive every cap above.")
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 40) {
                VStack(spacing: 8) {
                    combo([.shift, .command, .char("S")], skin: .raised, forceJoined: true)
                    Text("Joined").font(.caption).foregroundStyle(.secondary)
                }
                VStack(spacing: 8) {
                    combo([.shift, .command, .char("S")], skin: .raised, forceSplit: true)
                    Text("Split").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private var inContext: some View {
        VStack(alignment: .leading, spacing: 14) {
            heading("In context").padding(.top, 4)

            // Native menu rows — bare glyphs, right-aligned, secondary colour.
            sectionCard {
                Text("Native menu / list rows — skin F, never a drawn cap")
                    .font(.caption).foregroundStyle(.secondary)
                menuRow("Export Report…", [.shift, .command, .char("E")], selected: false)
                menuRow("Find…", [.command, .char("F")], selected: true)
                menuRow("Settings…", [.command, .char(",")], selected: false)
            }

            // Help list — mono grid, right-aligned keys.
            sectionCard {
                Text("Help list — skin E, keys right-aligned into a scannable column")
                    .font(.caption).foregroundStyle(.secondary)
                helpRow([.char("j")], "Next quote")
                helpRow([.char("s")], "Star")
                helpRow([.shift, .char("K")], "Extend selection up")
                helpRow([.command, .char(".")], "Toggle both sidebars")
                helpRow([.escape], "Close / clear")
            }
        }
    }

    private var recommendation: some View {
        sectionCard(tint: true) {
            Text("Recommendation")
                .font(.headline)
            Text("Raised (B) as the default; Flat (A) inline; Mono grid (E) for aligned lists; Bare (F) for native menus & CLI. Outline (C) and Solid (D) are situational. One glyph map, one SwiftUI file, one CSS file. Frozen in docs/design-keycaps.md.")
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: Row builders

    private func skinRow(_ tag: String, _ name: String, _ desc: String,
                         _ skin: CapSkin, _ tokens: [KeyToken],
                         recommended: Bool = false) -> some View {
        sectionCard(tint: recommended) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(tag)
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 5).padding(.vertical, 1)
                    .background(RoundedRectangle(cornerRadius: 3).fill(Color.token(.accent)))
                Text(name).font(.system(size: 15, weight: .semibold))
                if recommended {
                    Text("Recommended").font(.caption2.weight(.semibold))
                        .foregroundStyle(Color.token(.accent))
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .overlay(Capsule().strokeBorder(Color.token(.accent)))
                }
                Spacer()
            }
            Text(desc).font(.callout).foregroundStyle(.secondary)
            combo(tokens, skin: skin)
                .padding(.top, 2)
        }
    }

    private func menuRow(_ label: String, _ tokens: [KeyToken], selected: Bool) -> some View {
        HStack {
            Text(label).font(.system(size: 13))
                .foregroundStyle(selected ? Color.white : Color.token(.text))
            Spacer()
            combo(tokens, skin: .bare, tintOverride: selected ? Color.white.opacity(0.85) : nil,
                  forceJoined: true)
        }
        .padding(.horizontal, 9).padding(.vertical, 4)
        .background(RoundedRectangle(cornerRadius: 4)
            .fill(selected ? Color.token(.accent) : Color.clear))
    }

    private func helpRow(_ tokens: [KeyToken], _ what: String) -> some View {
        HStack(spacing: 12) {
            combo(tokens, skin: .grid, forceSplit: true)
                .frame(width: 66, alignment: .trailing)
            Text(what).font(.system(size: 13))
            Spacer()
        }
    }

    // MARK: Combo + primitives

    /// A key combination. Honours the toolbar Split toggle unless forced.
    private func combo(_ tokens: [KeyToken], skin: CapSkin,
                       tintOverride: Color? = nil,
                       forceJoined: Bool = false, forceSplit: Bool = false) -> some View {
        let isSplit = forceSplit || (split && !forceJoined)
        return HStack(spacing: isSplit ? 4 : (skin == .bare ? 0 : 2)) {
            ForEach(Array(tokens.enumerated()), id: \.offset) { _, tok in
                Keycap(token: tok, skin: skin, useSF: useSF, tintOverride: tintOverride)
            }
        }
    }

    private func heading(_ s: String) -> some View {
        Text(s).font(.system(size: 16, weight: .semibold))
    }

    private func labelled<V: View>(_ label: String, @ViewBuilder _ content: () -> V) -> some View {
        VStack(spacing: 6) {
            content()
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
    }

    private func sectionCard<V: View>(tint: Bool = false,
                                      @ViewBuilder _ content: () -> V) -> some View {
        VStack(alignment: .leading, spacing: 10) { content() }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(RoundedRectangle(cornerRadius: 8)
                .fill(tint ? Color.token(.accent).opacity(0.06) : Color.token(.panel)))
            .overlay(RoundedRectangle(cornerRadius: 8)
                .strokeBorder(tint ? Color.token(.accent).opacity(0.5) : Color.token(.border)))
    }
}

// MARK: - Keycap primitive

/// One key. The skin owns the decoration; the token owns the glyph source.
private struct Keycap: View {
    let token: KeyToken
    let skin: CapSkin
    let useSF: Bool
    var tintOverride: Color? = nil

    var body: some View {
        token.glyph(useSF: useSF)
            .font(.system(size: 12.5,
                          weight: skin == .solid ? .semibold : .medium,
                          design: .monospaced))
            .foregroundStyle(tintOverride ?? skin.foreground)
            .frame(minWidth: skin.minWidth, minHeight: skin == .bare ? nil : 22)
            .padding(.horizontal, skin.hPad)
            .background(decoration)
    }

    @ViewBuilder private var decoration: some View {
        let r: CGFloat = 5
        switch skin {
        case .flat, .grid:
            RoundedRectangle(cornerRadius: r).fill(Color.token(.badgeBg))
                .overlay(RoundedRectangle(cornerRadius: r).strokeBorder(Color.token(.border)))
        case .raised:
            ZStack {
                RoundedRectangle(cornerRadius: r).fill(Color.token(.capEdge)).offset(y: 1.5)
                RoundedRectangle(cornerRadius: r)
                    .fill(LinearGradient(colors: [Color.token(.capFace), Color.token(.capFaceLo)],
                                         startPoint: .top, endPoint: .bottom))
                    .overlay(RoundedRectangle(cornerRadius: r).strokeBorder(Color.token(.borderStrong)))
            }
        case .outline:
            RoundedRectangle(cornerRadius: r).strokeBorder(Color.token(.borderStrong))
        case .solid:
            RoundedRectangle(cornerRadius: r).fill(Color.token(.chipBg))
        case .bare:
            Color.clear
        }
    }
}

private enum CapSkin {
    case flat, raised, outline, solid, grid, bare

    var foreground: Color {
        switch self {
        case .solid: return Color.token(.chipText)
        case .bare:  return Color.token(.muted)
        default:     return Color.token(.text)
        }
    }
    var minWidth: CGFloat {
        switch self {
        case .bare: return 0
        case .grid: return 24   // uniform column
        default:    return 22
        }
    }
    var hPad: CGFloat { self == .bare ? 0 : 6 }
}

// MARK: - Key token (the glyph map, native side)

/// The native mirror of §2 of the gallery. `.mod` carries both the Unicode
/// glyph and its SF Symbol name; `.char` is a literal letter/punctuation.
private enum KeyToken {
    case mod(glyph: String, sf: String)
    case char(String)

    // Modifiers + specials — matches docs/design-keycaps.md §2.
    static let command = KeyToken.mod(glyph: "⌘", sf: "command")
    static let option  = KeyToken.mod(glyph: "⌥", sf: "option")
    static let shift   = KeyToken.mod(glyph: "⇧", sf: "shift")
    static let control = KeyToken.mod(glyph: "⌃", sf: "control")
    static let ret     = KeyToken.mod(glyph: "↩", sf: "return")
    static let escape  = KeyToken.mod(glyph: "⎋", sf: "escape")
    static let delete  = KeyToken.mod(glyph: "⌫", sf: "delete.left")

    @ViewBuilder func glyph(useSF: Bool) -> some View {
        switch self {
        case let .mod(glyph, sf):
            if useSF { Image(systemName: sf) } else { Text(glyph) }
        case let .char(c):
            Text(c)
        }
    }
}

// MARK: - Palette tokens (byte-matched to colors/palette-default.css)

private enum Tok {
    case bg, text, muted, border, borderStrong, accent, panel, badgeBg
    case chipBg, chipText, capFace, capFaceLo, capEdge
}

private extension Color {
    /// Dynamic light/dark colour matching the web palette-default tokens exactly,
    /// so the native cap and the CSS cap sit on the same seam.
    static func token(_ t: Tok) -> Color {
        let pair: (UInt, UInt)
        switch t {
        case .bg:           pair = (0xFFFFFF, 0x111111)
        case .text:         pair = (0x1A1A1A, 0xE5E7EB)
        case .muted:        pair = (0x6B7280, 0x9CA3AF)
        case .border:       pair = (0xE5E7EB, 0x2D2D2D)
        case .borderStrong: pair = (0xD1D5DB, 0x4B5563)
        case .accent:       pair = (0x007AFF, 0x0A84FF)
        case .panel:        pair = (0xF9F9FA, 0x1C1C1E)   // inspector-bg
        case .badgeBg:      pair = (0xF3F4F6, 0x252525)
        case .chipBg:       pair = (0x1A1A1A, 0xE5E7EB)
        case .chipText:     pair = (0xF4F4F5, 0x1A1A1A)
        case .capFace:      pair = (0xFBFBFC, 0x2C2C2E)
        case .capFaceLo:    pair = (0xF0F1F3, 0x232325)
        case .capEdge:      pair = (0xCFD2D7, 0x000000)
        }
        return Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
            return NSColor(rgb: isDark ? pair.1 : pair.0)
        })
    }
}

private extension NSColor {
    convenience init(rgb: UInt) {
        self.init(srgbRed: CGFloat((rgb >> 16) & 0xFF) / 255,
                  green: CGFloat((rgb >> 8) & 0xFF) / 255,
                  blue: CGFloat(rgb & 0xFF) / 255,
                  alpha: 1)
    }
}

#Preview { KeycapGalleryView() }
#endif
