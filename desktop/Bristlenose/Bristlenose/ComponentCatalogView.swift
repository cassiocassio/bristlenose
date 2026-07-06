#if DEBUG
import AppKit
import Charts
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
    @State private var scheme: ColorSchemeChoice = .auto

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            HSplitView {
                ScrollView {
                    VStack(alignment: .leading, spacing: 28) {
                        FoundationsSection()
                        AtomsSection()
                        MoleculesSection()
                        OrganismsSection()
                        ChartsSection()
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
        .preferredColorScheme(scheme.colorScheme)
    }

    private var header: some View {
        HStack(spacing: 10) {
            Text("Component Catalogue").font(.headline)
            Text("native  ·  vs  ·  web design system").font(.caption).foregroundStyle(.secondary)
            Spacer()
            Picker("Appearance", selection: $scheme) {
                ForEach(ColorSchemeChoice.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented).labelsHidden().fixedSize()
            Text("DEBUG").font(.caption).foregroundStyle(.tertiary)
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
    let sentiment: UInt
    @State private var hover = false

    init(_ text: String, sentiment: UInt) {
        self.text = text; self.sentiment = sentiment
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
        .foregroundStyle(Tok.sentiment(sentiment))
        .background(Tok.tagFill(sentiment), in: RoundedRectangle(cornerRadius: 3))
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
                .foregroundStyle(Tok.ink2)
                .padding(.horizontal, 6)
                .frame(maxHeight: .infinity)
                .background(Tok.codeBg)
            Text(name)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Tok.ink)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .frame(maxHeight: .infinity)
                .background(hover ? Color(nsColor: .textBackgroundColor) : Tok.surface)
        }
        .fixedSize()
        .overlay(RoundedRectangle(cornerRadius: 3).stroke(Tok.hairline))
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
                    Text("frustration").foregroundStyle(Tok.sentiment(0xC2410C))
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
                CatalogTag("friction", sentiment: 0x8A2F52)
            }
        }
        .padding(12)
        .frame(maxWidth: 340, alignment: .leading)
        .background(Color(nsColor: .textBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Tok.hairline))
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
                Circle().fill(Tok.sentiment(quote.sent)).frame(width: 6, height: 6)
                Text("\(n) · \(quote.who) · \(quote.time)")
                    .font(.system(size: 9.5, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tok.surface)
        .overlay(alignment: .leading) { Rectangle().fill(Tok.sentiment(quote.sent)).frame(width: 2) }
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

// MARK: - Sections (phased native rebuild)

private struct FoundationsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Specimen(title: "Spacing rhythm", control: "4·8·12·16·20·24 · prefer .padding() default") {
                SpacingRhythm()
            }
            Specimen(title: "Quote card", control: ".quote-card") {
                NativeQuoteCard()
            }
            Specimen(title: "Sentiment / codebook tag", control: "NSTokenField · SF Mono · ✕ on hover") {
                HStack(spacing: 6) {
                    CatalogTag("frustration", sentiment: 0xEA580C)
                    CatalogTag("onboarding", sentiment: 0x1F4F8A)
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
    }
}

// MARK: Phase 1 — atoms

private struct AtomsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Specimen(title: "Button", control: "Button · bordered / prominent") {
                HStack(spacing: 8) {
                    Button("Export") {}
                    Button("Star") {}.buttonStyle(.borderedProminent)
                }
            }
            Specimen(title: "Segmented", control: "Picker(.segmented)") {
                SegmentedDemo()
            }
            Specimen(title: "Toggle", control: "Toggle · .switch / .checkbox") {
                ToggleDemo()
            }
            Specimen(title: "Checkbox", control: "Toggle(.checkbox) · .controlSize(.small)") {
                CheckboxAtomDemo()
            }
            Specimen(title: "Search field", control: "NSSearchField (toolbar) — shipped") {
                HStack(spacing: 6) {
                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                    TextField("Search", text: .constant(""))
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 160)
                }
            }
            Specimen(title: "Progress ring", control: "Gauge(.accessoryCircularCapacity)") {
                Gauge(value: 0.7) {
                    Text("")
                } currentValueLabel: {
                    Text("70%").font(.system(size: 9))
                }
                .gaugeStyle(.accessoryCircularCapacity)
                .tint(.accentColor)
                .frame(width: 44, height: 44)
            }
        }
    }
}

private struct SegmentedDemo: View {
    @State private var sel = 0
    var body: some View {
        Picker("", selection: $sel) {
            Text("All").tag(0)
            Text("Starred").tag(1)
        }
        .pickerStyle(.segmented).labelsHidden().fixedSize()
    }
}

private struct ToggleDemo: View {
    @State private var sw = true
    @State private var cb = true
    var body: some View {
        HStack(spacing: 18) {
            Toggle("Switch", isOn: $sw).toggleStyle(.switch)
            Toggle("Checkbox", isOn: $cb).toggleStyle(.checkbox)
        }
    }
}

private struct CheckboxAtomDemo: View {
    @State private var a = true
    @State private var b = false
    var body: some View {
        HStack(spacing: 14) {
            Toggle("Included", isOn: $a).toggleStyle(.checkbox)
            Toggle("Hidden", isOn: $b).toggleStyle(.checkbox)
        }
        .controlSize(.small)
    }
}

// MARK: Phase 2 — molecules

private struct MoleculesSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Specimen(title: "Tag filter — dense checkbox field", control: "Toggle{Label} · .controlSize(.small) · row target") {
                TagFilterDemo()
            }
            Specimen(title: "Editable text — read-only", control: "Text now · TextField (inline edit) later") {
                Text("\u{201C}It felt confusing at first, but once I found the menu it was fine.\u{201D}")
                    .font(.system(size: 14))
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: 300, alignment: .leading)
            }
            Specimen(title: "Star toggle", control: "Image(systemName: star / star.fill)") {
                StarDemo()
            }
        }
    }
}

private struct TagFilterDemo: View {
    @State private var on: Set<Int> = [0, 2]
    private let tags: [(String, UInt)] = [
        ("onboarding", 0x1F4F8A), ("friction", 0x8A2F52),
        ("delight", 0x059669), ("trust signal", 0x5A3A82), ("opportunity", 0x7A5A1F)
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            ForEach(tags.indices, id: \.self) { i in
                Toggle(isOn: Binding(
                    get: { on.contains(i) },
                    set: { if $0 { on.insert(i) } else { on.remove(i) } }
                )) {
                    HStack(spacing: 5) {
                        Circle().fill(Tok.sentiment(tags[i].1)).frame(width: 7, height: 7)
                        Text(tags[i].0).font(.system(size: 12, design: .monospaced))
                    }
                }
            }
        }
        .toggleStyle(.checkbox)
        .controlSize(.small)
    }
}

private struct StarDemo: View {
    @State private var on = false
    var body: some View {
        Image(systemName: on ? "star.fill" : "star")
            .font(.system(size: 15))
            .foregroundStyle(on ? Color.accentColor : Color.secondary)
            .onTapGesture { on.toggle() }
    }
}

// MARK: Phase 3 — organisms

private struct OrganismsSection: View {
    private let cols = [GridItem(.adaptive(minimum: 92), spacing: 10)]
    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Specimen(title: "Stat cards — LazyVGrid", control: "LazyVGrid(.adaptive) · GroupBox-ish") {
                LazyVGrid(columns: cols, spacing: 10) {
                    StatCard(value: "16", label: "Sessions")
                    StatCard(value: "342", label: "Quotes")
                    StatCard(value: "18h", label: "Duration")
                    StatCard(value: "24", label: "Themes")
                }
                .frame(maxWidth: 380)
            }
            Specimen(title: "Sessions — Table", control: "Table + TableColumn · select") {
                SessionsTableDemo()
            }
        }
    }
}

private struct StatCard: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(value).font(.system(size: 24, weight: .semibold)).monospacedDigit()
            Text(label).font(.system(size: 11)).foregroundStyle(.secondary)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Tok.surface, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Tok.hairline))
    }
}

private struct SessionItem: Identifiable {
    let id = UUID()
    let n: Int
    let who: String
    let dur: String
}

private struct SessionsTableDemo: View {
    @State private var rows = [
        SessionItem(n: 1, who: "Rachel", dur: "48:12"),
        SessionItem(n: 2, who: "Kerry", dur: "52:40"),
        SessionItem(n: 3, who: "Sam", dur: "39:05")
    ]
    @State private var selection: SessionItem.ID?
    var body: some View {
        Table(rows, selection: $selection) {
            TableColumn("#") { Text("\($0.n)") }.width(24)
            TableColumn("Participant") { Text($0.who) }
            TableColumn("Duration") { Text($0.dur).monospacedDigit() }
        }
        .frame(width: 320, height: 118)
    }
}

// MARK: Phase 4 — charts (Swift Charts)

private struct ChartsSection: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Specimen(title: "Sentiment bars — Swift Charts", control: "Chart { BarMark }") {
                SentimentBarsDemo()
            }
            Specimen(title: "Sparkline — Swift Charts", control: "Chart { LineMark } · axes hidden") {
                SparklineDemo()
            }
            Specimen(title: "Signal heatmap — Swift Charts", control: "Chart { RectangleMark }") {
                HeatmapDemo()
            }
        }
    }
}

private struct SentimentBarsDemo: View {
    private let data: [(name: String, n: Int, color: Color)] = [
        ("frustration", 7, Tok.sentiment(0xEA580C)),
        ("confusion", 4, Tok.sentiment(0xDC2626)),
        ("satisfaction", 9, Tok.sentiment(0x16A34A)),
        ("delight", 5, Tok.sentiment(0x059669))
    ]
    var body: some View {
        Chart(data, id: \.name) { d in
            BarMark(x: .value("count", d.n), y: .value("sentiment", d.name))
                .foregroundStyle(d.color)
        }
        .chartLegend(.hidden)
        .frame(width: 300, height: 130)
    }
}

private struct SparklineDemo: View {
    private let vals: [Double] = [3, 7, 5, 9, 4, 8, 6, 10]
    var body: some View {
        Chart(Array(vals.enumerated()), id: \.offset) { item in
            LineMark(x: .value("i", item.offset), y: .value("v", item.element))
                .foregroundStyle(Color.accentColor)
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .frame(width: 150, height: 40)
    }
}

private struct HeatCell: Identifiable {
    let id = UUID()
    let row: String
    let col: String
    let v: Int
}

private struct HeatmapDemo: View {
    private let cells: [HeatCell] = {
        let rows = ["Checkout", "Search", "Onboard"]
        let cols = ["neg", "neu", "pos"]
        let vals = [[2, 7, 11], [1, 5, 9], [4, 3, 8]]
        var out: [HeatCell] = []
        for (ri, r) in rows.enumerated() {
            for (ci, c) in cols.enumerated() {
                out.append(HeatCell(row: r, col: c, v: vals[ri][ci]))
            }
        }
        return out
    }()
    var body: some View {
        Chart(cells) { cell in
            RectangleMark(x: .value("col", cell.col), y: .value("row", cell.row))
                .foregroundStyle(Tok.sentiment(0x16A34A).opacity(Double(cell.v) / 12.0))
                .annotation(position: .overlay) {
                    Text("\(cell.v)").font(.system(size: 9)).foregroundStyle(.primary)
                }
        }
        .chartLegend(.hidden)
        .frame(width: 240, height: 130)
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
