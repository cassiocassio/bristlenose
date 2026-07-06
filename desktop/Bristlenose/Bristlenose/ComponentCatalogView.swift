#if DEBUG
import AppKit
import SwiftUI

// MARK: - Component Catalogue — the native "Design Lens"
//
// Debug ▸ Component Catalogue. LEFT column: each design-system element rebuilt
// natively (SwiftUI) per the settled translation decisions. RIGHT column: the
// SAME element rendered by the web design system (real bn tokens) inside a
// WKWebView — the honest side-by-side, both engines on the same display.
//
// This is the keeper artefact of the native-experiment spike: the anatomy sheet
// made real. v1 covers the "recreate faithfully" set (quote card, tags, person
// badge, data badge) where the comparison matters most; grow it component by
// component. Presentation only — no engine, no bridge, no serve dependency (the
// web column is self-contained HTML with the real token values). Follows the
// TypeParityView harness pattern.
//
// NOTE: the light hex literals below (person-badge two-tone, quote-card fills)
// mirror the web design system's *light-mode* values verbatim so the comparison
// is faithful; dark-mode semantic-colour adaptation is a later slice.

struct ComponentCatalogView: View {
    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            HSplitView {
                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        Specimen(title: "Spacing rhythm", control: "4·8·12·16·20·24 · prefer .padding() default") {
                            SpacingRhythm()
                        }
                        Specimen(title: "Quote card", control: ".quote-card") {
                            NativeQuoteCard()
                        }
                        Specimen(title: "Sentiment / codebook tag", control: "NSTokenField · SF Mono · ✕ on hover") {
                            HStack(spacing: 6) {
                                CatalogTag("frustration", fg: 0xEA580C, bg: 0xFFF7ED)
                                CatalogTag("onboarding", fg: 0x1F4F8A, bg: 0xE3EDFB)
                            }
                        }
                        Specimen(title: "Person badge", control: "two-tone split · subtle hover") {
                            CatalogPersonBadge(code: "P1", name: "Rachel")
                        }
                        Specimen(title: "Data badge", control: "SF Mono · data-look") {
                            HStack(spacing: 6) {
                                CatalogDataBadge("AI")
                                CatalogDataBadge("0.82")
                            }
                        }
                        Specimen(title: "Masonry — SwiftUI Layout", control: "custom Layout · shortest-column · source order") {
                            MasonryLayout(columns: 3, spacing: 8) {
                                ForEach(SAMPLE_QUOTES.indices, id: \.self) { i in
                                    MasonryCard(quote: SAMPLE_QUOTES[i], n: i + 1)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(minWidth: 360)
                .background(Color(nsColor: .textBackgroundColor))

                ComponentCatalogWebView()
                    .frame(minWidth: 360)
            }
        }
        .frame(minWidth: 840, minHeight: 560)
    }

    private var header: some View {
        HStack(spacing: 10) {
            Text("Component Catalogue").font(.headline)
            Text("native  ·  vs  ·  web design system").font(.caption).foregroundStyle(.secondary)
            Spacer()
            Text("DEBUG · presentation only").font(.caption).foregroundStyle(.tertiary)
        }
        .padding(12)
    }
}

// MARK: - Layout helper

private struct Specimen<Content: View>: View {
    let title: String
    let control: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(title).font(.system(size: 12, weight: .semibold))
                Text(control).font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary)
            }
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Top-down: spacing rhythm

/// The macOS 4/8 rhythm made tangible. Native leans on multiples of 4/8 and,
/// wherever possible, *semantic* spacing (default stack spacing, bare
/// `.padding()`) rather than hardcoded numbers. Web bn tokens land off-grid
/// (2.4, 5.6) — snapping to 4/8 is the vanilla-wins translation.
private struct SpacingRhythm: View {
    private let steps: [Int] = [4, 8, 12, 16, 20, 24]

    var body: some View {
        HStack(alignment: .bottom, spacing: 14) {
            ForEach(steps, id: \.self) { s in
                VStack(spacing: 4) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.accentColor.opacity(0.16))
                        .overlay(RoundedRectangle(cornerRadius: 2).stroke(Color.accentColor.opacity(0.45)))
                        .frame(width: CGFloat(s), height: CGFloat(s))
                    Text("\(s)").font(.system(size: 9, design: .monospaced)).foregroundStyle(.secondary)
                }
            }
        }
    }
}

// MARK: - Native component recreations

/// SF Mono tag, tight 3px radius, existing colour, native ✕ close on hover.
private struct CatalogTag: View {
    let text: String
    let fg: UInt
    let bg: UInt
    @State private var hover = false

    init(_ text: String, fg: UInt, bg: UInt) {
        self.text = text; self.fg = fg; self.bg = bg
    }

    var body: some View {
        HStack(spacing: 4) {
            Text(text).font(.system(size: 11, design: .monospaced))
            if hover {
                Text("✕").font(.system(size: 9, design: .monospaced)).opacity(0.5)
            }
        }
        .padding(.horizontal, 7)
        .padding(.vertical, 2)
        .foregroundStyle(hx(fg))
        .background(hx(bg), in: RoundedRectangle(cornerRadius: 3))
        .onHover { hover = $0 }
    }
}

/// SF Mono status label — "very data, for nerds."
private struct CatalogDataBadge: View {
    let text: String
    init(_ text: String) { self.text = text }

    var body: some View {
        Text(text)
            .font(.system(size: 11, design: .monospaced))
            .padding(.horizontal, 7)
            .padding(.vertical, 2)
            .foregroundStyle(.secondary)
            .background(Color.secondary.opacity(0.14), in: RoundedRectangle(cornerRadius: 3))
    }
}

/// Two-tone split speaker chip — mono code | name, subtle hover (name bg lightens).
private struct CatalogPersonBadge: View {
    let code: String
    let name: String
    @State private var hover = false

    var body: some View {
        HStack(spacing: 0) {
            // Code half stretches to the pill height (set by the taller name
            // half) with its text vertically centred — otherwise the smaller
            // mono box centres as a short box and the code rides high.
            Text(code)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(hx(0x3C3C43))
                .padding(.horizontal, 6)
                .frame(maxHeight: .infinity)
                .background(hx(0xF3F4F6))
            Text(name)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(hx(0x1A1A1A))
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .frame(maxHeight: .infinity)
                .background(hover ? Color(nsColor: .textBackgroundColor) : hx(0xF9FAFB))
        }
        .fixedSize()
        .overlay(RoundedRectangle(cornerRadius: 3).stroke(Color.black.opacity(0.14)))
        .clipShape(RoundedRectangle(cornerRadius: 3))
        .onHover { hover = $0 }
    }
}

/// Quote card — native rounded surface + macOS padding, existing layout kept:
/// context line, corner star (SF Symbol), person badge + tag row.
private struct NativeQuoteCard: View {
    @State private var starred = false

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .top, spacing: 6) {
                HStack(spacing: 0) {
                    Text("Checkout · ").foregroundStyle(.secondary)
                    Text("frustration").foregroundStyle(hx(0xC2410C))
                }
                .font(.system(size: 11))
                Spacer()
                Image(systemName: starred ? "star.fill" : "star")
                    .font(.system(size: 12))
                    .foregroundStyle(starred ? Color.accentColor : Color.secondary.opacity(0.5))
                    .onTapGesture { starred.toggle() }
            }
            Text("\u{201C}I couldn\u{2019}t tell if it had actually saved.\u{201D}")
                .font(.system(size: 14))
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 8) {
                CatalogPersonBadge(code: "P3", name: "12:04")
                CatalogTag("friction", fg: 0x8A2F52, bg: 0xFBE6EC)
            }
        }
        .padding(12)
        .frame(maxWidth: 340, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.black.opacity(0.1)))
    }
}

// MARK: - Top-down: masonry (SwiftUI Layout)

/// Sample quotes with a wide length spread — the digital reality that makes
/// masonry earn its keep (a one-word quote next to a five-line one).
private struct SampleQuote { let text: String; let sent: UInt; let who: String; let time: String }
private let SAMPLE_QUOTES: [SampleQuote] = [
    .init(text: "I couldn\u{2019}t tell if it had actually saved.", sent: 0xEA580C, who: "P3", time: "12:04"),
    .init(text: "Too many steps.", sent: 0xEA580C, who: "P1", time: "04:11"),
    .init(text: "I kept going back to check whether my changes were still there, because the first time I tried it the whole thing reset and I lost everything I\u{2019}d typed.", sent: 0x7C3AED, who: "P2", time: "18:52"),
    .init(text: "Where\u{2019}s the back button?", sent: 0xDC2626, who: "P5", time: "02:20"),
    .init(text: "It felt confusing at first, but once I found the menu it was fine.", sent: 0x16A34A, who: "P4", time: "09:33"),
    .init(text: "I\u{2019}d expect it to remember where I left off, honestly.", sent: 0x7C3AED, who: "P2", time: "21:07"),
    .init(text: "The colour coding helped me spot the pattern without reading every one.", sent: 0x059669, who: "P6", time: "14:40"),
    .init(text: "Yes.", sent: 0x16A34A, who: "P1", time: "00:48"),
]

/// Compact quote card for the masonry field: left sentiment stripe, text, meta.
/// The `n` (source-order index) is shown so you can see 1,2,3 land across the top.
private struct MasonryCard: View {
    let quote: SampleQuote
    let n: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(quote.text)
                .font(.system(size: 12))
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 5) {
                Circle().fill(hx(quote.sent)).frame(width: 6, height: 6)
                Text("\(n) · \(quote.who) · \(quote.time)")
                    .font(.system(size: 9.5, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(hx(0xF9FAFB))
        .overlay(alignment: .leading) { Rectangle().fill(hx(quote.sent)).frame(width: 2) }
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

/// Shortest-column masonry via the SwiftUI `Layout` protocol (macOS 13+). Walks
/// subviews in SOURCE ORDER, dropping each into the currently-shortest column —
/// so reading / focus order is preserved (unlike CSS multicolumn). Eager: it
/// measures every subview, which is fine for a demo; the production quotes lens
/// uses NSCollectionView + a custom layout to virtualise this to hundreds.
private struct MasonryLayout: Layout {
    var columns: Int = 3
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.replacingUnspecifiedDimensions().width
        let colW = columnWidth(for: width)
        var heights = Array(repeating: CGFloat(0), count: max(columns, 1))
        for sv in subviews {
            let h = sv.sizeThatFits(ProposedViewSize(width: colW, height: nil)).height
            let c = shortest(heights)
            heights[c] += h + spacing
        }
        let tallest = (heights.max() ?? spacing) - spacing
        return CGSize(width: width, height: max(tallest, 0))
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let colW = columnWidth(for: bounds.width)
        var heights = Array(repeating: CGFloat(0), count: max(columns, 1))
        for sv in subviews {
            let h = sv.sizeThatFits(ProposedViewSize(width: colW, height: nil)).height
            let c = shortest(heights)
            let x = bounds.minX + CGFloat(c) * (colW + spacing)
            let y = bounds.minY + heights[c]
            sv.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(width: colW, height: h))
            heights[c] += h + spacing
        }
    }

    private func columnWidth(for total: CGFloat) -> CGFloat {
        let n = CGFloat(max(columns, 1))
        return (total - spacing * (n - 1)) / n
    }

    private func shortest(_ heights: [CGFloat]) -> Int {
        var idx = 0
        for i in 1..<heights.count where heights[i] < heights[idx] { idx = i }
        return idx
    }
}

// MARK: - Hex helper (catalogue-local; mirrors the web light-mode tokens)

private func hx(_ v: UInt) -> Color {
    Color(.sRGB,
          red: Double((v >> 16) & 0xFF) / 255.0,
          green: Double((v >> 8) & 0xFF) / 255.0,
          blue: Double(v & 0xFF) / 255.0,
          opacity: 1)
}
#endif
