import SwiftUI
import WebKit
import Combine

// MARK: - Welcome-screen illustrations
//
// One tiny looping illustration per rotator-cell pool item — five for the
// "Scientific background" cell (design-welcome-screen.md §Cell 2) and five for
// "Study tools" (design-welcome-studytools-illustrations.md).
//
// Science cell (decisions agreed with Martin, TF-play):
//   1 Seven sentiments      → native SwiftUI fan (SentimentFanView)
//   2 Signals               → webview (the real signal card + trainboard flip)
//   3 Dignity               → webview (the strike-and-collapse quote)
//   4 Source books          → native SwiftUI hat-tip shelf, one cell, synced caption (BookShelfView)
//   5 Emergent themes       → webview (the two-theme swoop, EmergentThemesView).
//                             NOT the real ShoalView boids — that's the delight /
//                             analysing screensaver, which wants a big canvas.
// Study tools: AutoCode · Codebooks (manual tags) · Tag · Star & hide ·
//   Connect an AI agent · Send to Miro — webviews (see that brief's build-target
//   section) — and Ingest · Video clips, native SwiftUI (SF Symbols + SF Pro,
//   replacing the last PNG screenshots on 14 Aug 2026).
//
// Native pieces use exact-ish fonts (SF Mono for the chips); the webviews reuse
// the mockup CSS/JS verbatim — slight font-rendering differences accepted.
// All are decorative — accessibilityHidden, inert, reduce-motion aware — except
// BookShelfView, which carries real content and stays accessible.

/// Which illustration a Welcome-screen rotator slot carries (`.none` = plain text slot).
enum WelcomeIllustration: Equatable {
    case none, sentimentFan, books, emergentThemes, quote, signal,
         autocode, manualTags, tag, starHide, agentChat, ingest, clips, miro
}

/// sRGB colour from a 0xRRGGBB literal (file-private helper).
private func rgb(_ v: UInt) -> Color {
    Color(.sRGB,
          red: Double((v >> 16) & 0xff) / 255,
          green: Double((v >> 8) & 0xff) / 255,
          blue: Double(v & 0xff) / 255)
}

// MARK: - 1 · Seven sentiments (native — 2-row deal)

/// The seven sentiment chips rest as a readable two-row grid (the codebook-badge
/// look) and animate by dealing out from a gathered deck and gathering back,
/// staggered per chip. Words stay upright; widths are measured so the rows centre
/// and fill the slot without crashing into the surrounding text. Chip typography
/// matches the report badge (SF Mono + the sentiment colour tokens).
struct SentimentFanView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @State private var sizes: [Int: CGSize] = [:]
    @State private var dealt = false

    private struct Chip { let name: String; let fgL, fgD, bgL, bgD: UInt }
    private let chips: [Chip] = [
        .init(name: "frustration",  fgL: 0xea580c, fgD: 0xfb923c, bgL: 0xfff7ed, bgD: 0x2d1d0e),
        .init(name: "confusion",    fgL: 0xdc2626, fgD: 0xf87171, bgL: 0xfef2f2, bgD: 0x2d1515),
        .init(name: "doubt",        fgL: 0x7c3aed, fgD: 0xa78bfa, bgL: 0xf5f3ff, bgD: 0x1e1533),
        .init(name: "surprise",     fgL: 0xd97706, fgD: 0xfbbf24, bgL: 0xfffbeb, bgD: 0x2d2305),
        .init(name: "satisfaction", fgL: 0x16a34a, fgD: 0x4ade80, bgL: 0xf0fdf4, bgD: 0x0f2918),
        .init(name: "delight",      fgL: 0x059669, fgD: 0x34d399, bgL: 0xecfdf5, bgD: 0x0d261c),
        .init(name: "confidence",   fgL: 0x2563eb, fgD: 0x60a5fa, bgL: 0xeff6ff, bgD: 0x111d2e),
    ]
    // 4 / 3 two-row split in valence order; row bands + gap mirror the mockup.
    private let topRow = [0, 1, 2, 3]
    private let bottomRow = [4, 5, 6]
    private let gap: CGFloat = 8
    private static var tempo: Double { WelcomeTempo.stretch(for: .sentimentFan) }

    var body: some View {
        GeometryReader { geo in
            ZStack {
                ForEach(chips.indices, id: \.self) { i in
                    chipView(i)
                        .background(sizeReader(i))
                        .offset(dealt ? homeOffset(i, in: geo.size) : .zero)   // deck = centre
                        .zIndex(Double(i))
                        .animation(reduceMotion ? nil
                                   : .easeInOut(duration: 1.0 * Self.tempo).delay(Double(i) * 0.12 * Self.tempo),
                                   value: dealt)                                // per-chip deal stagger, on the group tempo
                }
            }
            .frame(width: geo.size.width, height: geo.size.height)
        }
        .onPreferenceChange(SentimentChipSizeKey.self) { sizes = $0 }
        .accessibilityHidden(true)
        // Baton: deal only while this cell holds it; otherwise rest on the open fan.
        .task(id: active && !reduceMotion) {
            guard active && !reduceMotion else { await MainActor.run { dealt = true }; return }
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(2.4 * Self.tempo))    // gathered (deck) hold — clears the 3s opening floor at the group tempo
                await MainActor.run { dealt = true }
                try? await Task.sleep(for: .seconds(5.6 * Self.tempo))    // dealt (readable) hold — likewise clears the 3s end floor
                await MainActor.run { dealt = false }
            }
        }
    }

    private func chipView(_ i: Int) -> some View {
        let chip = chips[i]
        return Text(chip.name)
            .font(.system(size: 11, weight: .regular, design: .monospaced))
            .foregroundStyle(scheme == .dark ? rgb(chip.fgD) : rgb(chip.fgL))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(RoundedRectangle(cornerRadius: 3)
                .fill(scheme == .dark ? rgb(chip.bgD) : rgb(chip.bgL)))
            .shadow(color: .black.opacity(scheme == .dark ? 0.45 : 0.12), radius: 1, y: 0.5)
            .fixedSize()
    }

    private func sizeReader(_ i: Int) -> some View {
        GeometryReader { p in
            Color.clear.preference(key: SentimentChipSizeKey.self, value: [i: p.size])
        }
    }

    /// Centre-relative offset for the dealt 2-row layout (deck = .zero = ZStack centre).
    private func homeOffset(_ i: Int, in size: CGSize) -> CGSize {
        let row = topRow.contains(i) ? topRow : bottomRow
        let widths = row.map { sizes[$0]?.width ?? 0 }
        let total = widths.reduce(0, +) + gap * CGFloat(row.count - 1)
        let pos = row.firstIndex(of: i) ?? 0
        let before = widths.prefix(pos).reduce(0, +) + gap * CGFloat(pos)
        let dx = -total / 2 + before + (widths[pos] / 2)
        let dy = (topRow.contains(i) ? 0.34 : 0.66) * size.height - size.height / 2
        return CGSize(width: dx, height: dy)
    }
}

private struct SentimentChipSizeKey: PreferenceKey {
    static let defaultValue: [Int: CGSize] = [:]
    static func reduce(value: inout [Int: CGSize], nextValue: () -> [Int: CGSize]) {
        value.merge(nextValue(), uniquingKeysWith: { $1 })
    }
}

// MARK: - 4 · Book shelf (native — one synced cell for all the source books)

/// A single "thinking you can leverage" shelf: the source books overlap and
/// slide front-to-back, and the author + one-line contribution + Learn-more link
/// update in sync with whichever cover is on top. Each line states how that work
/// is in the product out of the box — a ready-made codebook, the themes method,
/// the sentiments — so the framework-vs-method distinction stays an
/// implementation detail. Extend by adding a `Book` + its `welcome-book-<slug>`
/// imageset. Real cover when the asset lands; typographic placeholder until then.
///
/// Bending: the caption and link hold fixed semantic sizes and shed WORDS when
/// the slot is short (clause cut, then ellipsis); only the cover fan scales,
/// because only it cannot reflow. Until 20 Aug 2026 a single `scaleEffect`
/// wrapped the lot, so a narrow window shrank the prose along with the covers.
struct BookShelfView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var front = 0

    private struct Book {
        let author, title, line, href: String
        let spine: UInt
        var image: String? = nil
    }
    // Hat-tip, not feature pitch — the themes / signals / sentiment cells show the
    // features; this shelf credits the thinking they stand on. Each line names the
    // contribution. (Links point at our docs today; a future affiliate link to the
    // book itself is the clickable-cover idea from the author outreach.)
    private let books: [Book] = [
        .init(author: "Don Norman", title: "The Design of Everyday Things",
              line: "The book that made human-centred design a discipline — blame the design, not the user.",
              href: "https://bristlenose.app/docs/codebook-frameworks.html", spine: 0x334155, image: "welcome-book-norman"),
        .init(author: "Jakob Nielsen", title: "Usability Engineering",
              line: "Ten usability heuristics that still anchor how the field spots friction.",
              href: "https://bristlenose.app/docs/codebook-frameworks.html", spine: 0x0f5c9e, image: "welcome-book-nielsen"),
        .init(author: "Braun & Clarke", title: "Thematic Analysis",
              line: "The practical guide to reflexive thematic analysis — themes from participants’ own words.",
              href: "https://bristlenose.app/docs/research-foundations.html", spine: 0x7c3aed, image: "welcome-book-braun-clarke"),
        .init(author: "Richard Lazarus", title: "Emotion & Adaptation",
              line: "Appraisal theory — emotion as how we weigh what happens to us.",
              href: "https://bristlenose.app/docs/signals.html", spine: 0xb45309, image: "welcome-book-lazarus"),
    ]
    private let cardW: CGFloat = 106     // 80×114 grown ~33% to use more of the cell
    private let cardH: CGFloat = 152
    private let off: CGFloat = 34        // horizontal peek between covers — more separation, less overlap
    /// Width the fan wants: one full cover plus a peek per extra cover.
    private var fanWidth: CGFloat { cardW + off * CGFloat(max(0, books.count - 1)) }
    /// Caption reserve: two lines of `.body`, held constant so the fan does not
    /// jump as the front cover changes and the line length with it.
    private let captionReserve: CGFloat = 38
    @Environment(\.welcomeAnimationActive) private var active
    private let timer = Timer.publish(every: 3.8 * WelcomeTempo.stretch(for: .books), on: .main, in: .common).autoconnect()

    var body: some View {
        let n = books.count
        let current = books[min(front, n - 1)]
        return VStack(alignment: .leading, spacing: 6) {
            caption(current)
            coverFan
            if let url = URL(string: current.href) {
                Link("Learn more →", destination: url)
                    .font(.callout)
                    .id("lnk-\(front)")
                    .transition(.opacity)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .onReceive(timer) { _ in
            guard active && !reduceMotion else { return }   // baton: advance only while holding it
            withAnimation(.easeInOut(duration: 0.6)) { front = (front + 1) % n }
        }
    }

    // Caption — synced to the front cover, cross-fades on change.
    //
    // Fixed semantic sizes. It used to sit inside the whole-shelf `scaleEffect`
    // below, which meant a short cell shrank the PROSE: at the 700pt minimum
    // window the scale reaches 0.29, rendering `.title3` smaller than the
    // unscaled `.subheadline` cell tag beside it — the type hierarchy inverted.
    // Scaling is for the covers, which cannot reflow; text bends by losing
    // words, never by losing size. (docs/design-welcome-screen.md §2.)
    private func caption(_ b: Book) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(b.author).font(.title3).fontWeight(.semibold)
            // Longest candidate that fits, in order. NO `.fixedSize` — that
            // would force each candidate to demand its full height and defeat
            // the fit test. The ellipsis is the last resort, not the first:
            // it is honest (`…` marks omission) but it promises a disclosure
            // this cell cannot offer, so a shorter complete reading wins.
            ViewThatFits(in: .vertical) {
                captionLine(b.line, limit: nil)
                if let short = WelcomeClauseFit.shortened(b.line) {
                    captionLine(short, limit: nil)
                }
                captionLine(b.line, limit: 2)
            }
            .frame(height: captionReserve, alignment: .topLeading)
        }
        .id("cap-\(front)")
        .transition(.opacity)
    }

    private func captionLine(_ s: String, limit: Int?) -> some View {
        Text(s)
            .font(.body).foregroundStyle(.secondary)
            .lineLimit(limit)
            .truncationMode(.tail)
            .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    // The fan of covers — front on top, LEFT-aligned so it opens rightward.
    //
    // The ONLY thing that scales, and on BOTH axes: the fan is 208pt wide at
    // four covers while the science cell is ~165pt at minimum window size, so a
    // height-only scale drops the fourth cover off the edge. (The old
    // whole-shelf scale hid this by shrinking the fan horizontally too.)
    //
    // `aspectRatio` is load-bearing, not tidiness. `scaleEffect` is a DRAWING
    // transform — it never changes the frame the layout reserved. So when width
    // was the binding constraint the fan drew `cardH × widthRatio` tall inside a
    // frame the VStack had sized from leftover *height*, and the two disagreed:
    // the covers spilled downward over the Learn-more link, and the unused
    // reserve read as a gap under the caption. Giving the box the fan's natural
    // ratio makes the reserved frame and the drawn size the same thing, so one
    // `s` satisfies both axes and the VStack packs tight underneath.
    private var coverFan: some View {
        GeometryReader { geo in
            let s = min(1, geo.size.width / fanWidth, geo.size.height / cardH)
            ZStack {
                ForEach(books.indices, id: \.self) { i in
                    let d = ((i - front) % books.count + books.count) % books.count
                    bookCard(books[i])
                        .offset(x: CGFloat(d) * off)
                        .opacity(d > 3 ? 0 : 1 - Double(d) * 0.14)   // show up to 4; fade with depth
                        .zIndex(Double(100 - d))
                }
            }
            // topLeading on both: GeometryReader places content at the top, so a
            // centre anchor would scale about the midline of the unscaled box.
            .frame(width: fanWidth, height: cardH, alignment: .topLeading)
            .scaleEffect(s, anchor: .topLeading)
            .frame(width: geo.size.width, height: geo.size.height, alignment: .topLeading)
        }
        .aspectRatio(fanWidth / cardH, contentMode: .fit)
        .frame(maxWidth: fanWidth, maxHeight: cardH, alignment: .topLeading)   // never upscale
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityHidden(true)   // covers are decorative; the caption conveys the book
    }

    @ViewBuilder private func bookCard(_ b: Book) -> some View {
        Group {
            if let name = b.image, let ns = NSImage(named: name) {   // real cover when the asset lands
                Image(nsImage: ns)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: cardW, height: cardH)
                    .clipShape(RoundedRectangle(cornerRadius: 5))
            } else {
                placeholderCard(b)   // typographic fallback (no asset / copyright not cleared)
            }
        }
        .shadow(color: .black.opacity(0.22), radius: 6, y: 4)
    }

    private func placeholderCard(_ b: Book) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(b.title).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(.white)
            Spacer(minLength: 0)
            Text(b.author).font(.system(size: 10.5)).foregroundStyle(.white.opacity(0.82))
        }
        .padding(EdgeInsets(top: 12, leading: 14, bottom: 11, trailing: 11))
        .frame(width: cardW, height: cardH, alignment: .leading)
        .background(
            LinearGradient(colors: [rgb(b.spine), rgb(b.spine).opacity(0.72)],
                           startPoint: .topLeading, endPoint: .bottomTrailing),
            in: RoundedRectangle(cornerRadius: 5)
        )
        .overlay(alignment: .leading) {
            Rectangle().fill(.white.opacity(0.22)).frame(width: 1).padding(.leading, 5)
        }
    }
}

// MARK: - 5 · Emergent themes (the mockup's simple two-theme swoop, via webview)

/// The clear, simple murmuration from the mockup: demo quote-fragments swirl as
/// one flock, swoop into two labelled themes, then rejoin — induction, looping.
/// Deliberately NOT the real `ShoalView` (that's the delight / analysing
/// screensaver — it wants a big canvas and is for fun; this cell has to make a
/// point). Reuses the approved mockup verbatim, so the feel is preserved exactly.
struct EmergentThemesView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.emergentThemes(dark: scheme == .dark, reduce: still))
            .id("themes-\(scheme)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

// MARK: - 2 & 3 · Webview-backed illustrations

/// Transparent, inert WKWebView that renders a self-contained HTML illustration.
/// No external resources (loadHTMLString, baseURL nil) — sandbox-clean; fonts are
/// the system stack. Transparency via the documented `drawsBackground` KVC.
private struct IllustrationWebView: NSViewRepresentable {
    let html: String

    func makeNSView(context: Context) -> WKWebView {
        let wv = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        wv.setValue(false, forKey: "drawsBackground")   // paint transparent (see WebView.swift)
        wv.loadHTMLString(html, baseURL: nil)
        return wv
    }
    func updateNSView(_ nsView: WKWebView, context: Context) {}
}

/// #3 — the dignity strike-and-collapse quote.
struct QuoteIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.quote(dark: scheme == .dark, reduce: still))
            .id("quote-\(scheme)-\(still)")   // reload on appearance / reduce-motion / baton change
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// #2 — the real analysis signal card ticking through examples.
struct SignalIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.signal(dark: scheme == .dark, palette: palette, reduce: still))
            .id("signal-\(scheme)-\(palette)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// Study-tools #1 — AutoCode: a real quote card types in, the AI code arrives
/// proposed, is accepted, goes solid, and rests. Ported from
/// docs/mockups/welcome-studytools-animations.html. Reuses the shipped badge +
/// quote CSS (badge.css, blockquote.css) so it re-syncs when the report styling
/// changes — the reason study-tool illustrations that reproduce report chrome are
/// webviews, not native rebuilds (matches the Signals / Dignity science cells).
struct AutoCodeIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.autocode(dark: scheme == .dark, palette: palette, reduce: still))
            .id("autocode-\(scheme)-\(palette)-\(still)")   // reload on appearance / palette / reduce-motion / baton
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// Manual tags (Codebooks) — the researcher hand-builds codebook groups by hand
/// (title + description + codes typed, in real codebook colours). Human counterpart
/// to AutoCode; ported from docs/mockups/welcome-studytools-animations.html.
struct ManualTagsIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.manualTags(dark: scheme == .dark, palette: palette, reduce: still))
            .id("manualtags-\(scheme)-\(palette)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// Study-tools #3 — Tag: the pointer arcs onto a quote's chrome (not the words, which
/// would open trim/edit), a plain click focuses + single-selects it, a raised `t` keycap
/// presses under the cursor, and a code types itself in as a real `.badge-user` chip.
/// Ported from docs/mockups/welcome-studytools-animations.html.
struct TagIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.tag(dark: scheme == .dark, palette: palette, reduce: still))
            .id("tag-\(scheme)-\(palette)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// Study-tools #4 — Star & hide: press `s` to keep (star + left rule pick up the starred
/// tint, body weight bumps), press `h` to hide (real `.bn-hiding` collapse) and the hidden
/// count ticks up by one. Ported from docs/mockups/welcome-studytools-animations.html.
struct StarHideIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.starHide(dark: scheme == .dark, palette: palette, reduce: still))
            .id("starhide-\(scheme)-\(palette)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// Study-tools #5 — Connect an AI agent: a faked-up Claude Code session in a terminal
/// panel. The researcher's question types in, the agent calls the real MCP tool
/// (`search_quotes` — the actual tool name the /mcp/ endpoint exposes), the result
/// line lands, and a cited answer streams back word-by-word. Drawn, not screenshotted:
/// no window chrome, theme- and palette-aware like every other webview illustration.
struct AgentChatIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active
    @AppStorage("palette") private var palette: String = "default"

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.agentChat(dark: scheme == .dark, palette: palette, reduce: still))
            .id("agentchat-\(scheme)-\(palette)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

/// Study-tools #6 — Ingest: one example of every kind of file or folder Bristlenose
/// imports, as a native list — SF Symbols for the icons, SF Pro for the names, and a
/// small surtitle over each name saying what kind it is and which formats that path
/// ingests (the four decode paths of `classify_file` in `bristlenose/models.py`, plus
/// the folder shapes `discover_files` walks). Each icon blinks in, then the name types
/// out. Reduce Motion — or losing the baton — shows the finished list. Content sits at
/// x = 0: the Swift frame owns the cell inset (no second, illustration-side padding).
struct IngestIllustrationView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active

    private struct Row { let icon, surtitle, name: String }
    private static let rows: [Row] = [
        .init(icon: "film",
              surtitle: "Video — MP4 · MOV · MKV · WebM · AVI · M4V",
              name: "usability-test-03.mp4"),
        .init(icon: "waveform",
              surtitle: "Audio — WAV · MP3 · M4A · FLAC · OGG · AAC · WMA",
              name: "interview-with-anna.m4a"),
        .init(icon: "captions.bubble",
              surtitle: "Captions — VTT · SRT, matched to their video by name",
              name: "usability-test-03.vtt"),
        .init(icon: "doc.text",
              surtitle: "Transcripts — Word exports from Zoom, Teams or Meet",
              name: "Discovery call - Transcript.docx"),
        .init(icon: "folder",
              surtitle: "Folders — one session’s files together, any mix",
              name: "2026-01-15 14.30 Usability study"),
    ]

    @State private var iconOn = [Bool](repeating: false, count: 5)
    @State private var detailOn = [Bool](repeating: false, count: 5)
    @State private var typed = [Int](repeating: 0, count: 5)

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(Self.rows.indices, id: \.self) { i in row(i) }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .accessibilityHidden(true)
        .task(id: active && !reduceMotion) { await drive() }
    }

    private func row(_ i: Int) -> some View {
        let r = Self.rows[i]
        // Opacity (never conditional views) so every row keeps its space — nothing
        // reflows while icons blink and names type.
        return VStack(alignment: .leading, spacing: 1) {
            Text(r.surtitle)
                .font(.system(size: 10.5)).foregroundStyle(.secondary)
                .opacity(detailOn[i] ? 1 : 0)
            HStack(spacing: 8) {
                Image(systemName: r.icon)
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                    .frame(width: 18)
                    .opacity(iconOn[i] ? 1 : 0)
                Text(String(r.name.prefix(typed[i])))
                    .font(.system(size: 13))
                Spacer(minLength: 0)
            }
            .frame(height: 18)
        }
    }

    @MainActor private func setComplete() {
        iconOn = [Bool](repeating: true, count: 5)
        detailOn = [Bool](repeating: true, count: 5)
        typed = Self.rows.map(\.name.count)
    }

    private static var tempo: Double { WelcomeTempo.stretch(for: .ingest) }
    /// One beat, scaled by the group tempo (× this illustration's local pace).
    private func nap(_ ms: Double) async {
        try? await Task.sleep(for: .milliseconds(ms * Self.tempo))
    }

    private func drive() async {
        guard active && !reduceMotion else { await MainActor.run { setComplete() }; return }
        while !Task.isCancelled {
            await MainActor.run {
                iconOn = [Bool](repeating: false, count: 5)
                detailOn = [Bool](repeating: false, count: 5)
                typed = [Int](repeating: 0, count: 5)
            }
            // Rest on the empty opening frame (absolute — holds don't scale).
            try? await Task.sleep(for: .seconds(WelcomeTempo.leadInSeconds))
            for i in Self.rows.indices {
                if Task.isCancelled { return }
                // Blink: on — off — on, hard cuts (a fade would read as a fade-in).
                await MainActor.run { iconOn[i] = true }
                await nap(90)
                await MainActor.run { iconOn[i] = false }
                await nap(70)
                await MainActor.run {
                    iconOn[i] = true
                    withAnimation(.easeOut(duration: 0.25)) { detailOn[i] = true }
                }
                await nap(140)
                for c in 1...Self.rows[i].name.count {
                    if Task.isCancelled { return }
                    await MainActor.run { typed[i] = c }
                    await nap(26)
                }
                await nap(280)
            }
            // Rest on the finished list before looping.
            try? await Task.sleep(for: .seconds(WelcomeTempo.holdEndSeconds))
        }
    }
}

/// Study-tools #7 — Video clips: the real Export-menu item (film icon, "Extract Video
/// Clips…", its "Trimmed clip per quote" subtitle) drawn native, a pointer slides in
/// and clicks it — with the macOS highlight-flash a real menu does — then the clips
/// land one at a time: fake thumbnail first, filename assembling one logical unit at a
/// beat (participant code · timecode · quote snippet · .mp4) so the naming scheme
/// reads. Pause on the finished set, then loop back to the menu choice.
struct ClipsIllustrationView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active

    private struct Clip { let units: [String]; let a, b: UInt }
    private static let clips: [Clip] = [
        .init(units: ["p1", "00m14", "Ive got this little thing", ".mp4"], a: 0x8FA1B8, b: 0x39445A),
        .init(units: ["p1", "02m46", "its a new thing", ".mp4"], a: 0xD9B38A, b: 0x6E5136),
        .init(units: ["p2", "07m11", "back to the homepage", ".mp4"], a: 0x9CBCAA, b: 0x46685A),
    ]
    /// First n units joined the way the exporter names files: spaces between units,
    /// the extension glued on.
    private static func filename(_ clip: Clip, units n: Int) -> String {
        var s = ""
        for (i, u) in clip.units.prefix(n).enumerated() {
            if i > 0 && !u.hasPrefix(".") { s += " " }
            s += u
        }
        return s
    }

    @State private var menuOn = false
    @State private var highlight = false
    @State private var pressed = false
    @State private var pointerOn = false
    @State private var pointerHome = false
    @State private var thumbOn = [false, false, false]
    @State private var unitsShown = [0, 0, 0]

    var body: some View {
        ZStack(alignment: .topLeading) {
            rows
            menu.opacity(menuOn ? 1 : 0)
            pointer
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .accessibilityHidden(true)
        .task(id: active && !reduceMotion) { await drive() }
    }

    private var rows: some View {
        VStack(alignment: .leading, spacing: 7) {
            ForEach(Self.clips.indices, id: \.self) { i in
                HStack(spacing: 8) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(LinearGradient(colors: [rgb(Self.clips[i].a), rgb(Self.clips[i].b)],
                                             startPoint: .topLeading, endPoint: .bottomTrailing))
                        .frame(width: 34, height: 19)
                        .overlay(RoundedRectangle(cornerRadius: 3)
                            .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
                        .opacity(thumbOn[i] ? 1 : 0)
                        .scaleEffect(thumbOn[i] ? 1 : 0.7)
                    Text(Self.filename(Self.clips[i], units: unitsShown[i]))
                        .font(.system(size: 13))
                    Spacer(minLength: 0)
                }
                .frame(height: 19)
            }
        }
    }

    // The Export-menu row, verbatim strings from the real menu. Approximated menu
    // surface (windowBackgroundColor + shadow) — a real NSMenu material isn't
    // reachable from a decorative SwiftUI view, and the row is the point.
    private var menu: some View {
        HStack(spacing: 8) {
            Image(systemName: "film")
                .font(.system(size: 15))
                .foregroundStyle(highlight ? AnyShapeStyle(.white) : AnyShapeStyle(Color.accentColor))
            VStack(alignment: .leading, spacing: 1) {
                Text("Extract Video Clips…")
                    .font(.system(size: 13))
                    .foregroundStyle(highlight ? .white : .primary)
                Text("Trimmed clip per quote")
                    .font(.system(size: 11))
                    .foregroundStyle(highlight ? AnyShapeStyle(.white.opacity(0.85)) : AnyShapeStyle(.secondary))
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 9).padding(.vertical, 5)
        .frame(width: 218, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 5)
            .fill(highlight ? Color.accentColor : Color.clear))
        .padding(5)
        .background(RoundedRectangle(cornerRadius: 8)
            .fill(Color(nsColor: .windowBackgroundColor))
            .shadow(color: .black.opacity(0.25), radius: 10, y: 4))
        .overlay(RoundedRectangle(cornerRadius: 8)
            .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
    }

    private var pointer: some View {
        Image(systemName: "cursorarrow")
            .font(.system(size: 15, weight: .medium))
            .foregroundStyle(.primary)
            .shadow(color: .black.opacity(0.35), radius: 0.8, y: 0.5)
            .scaleEffect(pressed ? 0.85 : 1, anchor: .topLeading)
            .offset(x: pointerHome ? 130 : 230, y: pointerHome ? 26 : 78)
            .opacity(pointerOn ? 1 : 0)
    }

    @MainActor private func setComplete() {
        menuOn = false; pointerOn = false; highlight = false; pressed = false; pointerHome = false
        thumbOn = [true, true, true]
        unitsShown = Self.clips.map(\.units.count)
    }

    @MainActor private func reset() {
        menuOn = false; pointerOn = false; highlight = false; pressed = false; pointerHome = false
        thumbOn = [false, false, false]
        unitsShown = [0, 0, 0]
    }

    private static var tempo: Double { WelcomeTempo.stretch(for: .clips) }
    /// One beat, scaled by the group tempo (× this illustration's local pace).
    private func nap(_ ms: Double) async {
        try? await Task.sleep(for: .milliseconds(ms * Self.tempo))
    }

    private func drive() async {
        guard active && !reduceMotion else { await MainActor.run { setComplete() }; return }
        while !Task.isCancelled {
            await MainActor.run { reset() }
            // Rest on the empty opening frame (absolute — holds don't scale).
            try? await Task.sleep(for: .seconds(WelcomeTempo.leadInSeconds))
            await MainActor.run { withAnimation(.easeOut(duration: 0.25)) { menuOn = true; pointerOn = true } }
            await nap(250)
            await MainActor.run { withAnimation(.easeInOut(duration: 0.55 * Self.tempo)) { pointerHome = true } }
            await nap(620)
            await MainActor.run { highlight = true }
            await nap(350)
            await MainActor.run { withAnimation(.easeIn(duration: 0.09)) { pressed = true } }
            await nap(100)
            await MainActor.run { withAnimation(.easeOut(duration: 0.12)) { pressed = false } }
            for _ in 0..<2 {   // the real menu's confirmation flash
                await MainActor.run { highlight = false }
                await nap(70)
                await MainActor.run { highlight = true }
                await nap(70)
            }
            await nap(180)
            await MainActor.run { withAnimation(.easeIn(duration: 0.3)) { menuOn = false; pointerOn = false } }
            await nap(380)
            for i in Self.clips.indices {
                if Task.isCancelled { return }
                await MainActor.run { withAnimation(.spring(duration: 0.3, bounce: 0.35)) { thumbOn[i] = true } }
                await nap(330)
                for u in 1...Self.clips[i].units.count {
                    if Task.isCancelled { return }
                    await MainActor.run { unitsShown[i] = u }
                    await nap(430)
                }
                await nap(240)
            }
            // Rest on the finished set before looping back to the menu.
            try? await Task.sleep(for: .seconds(WelcomeTempo.holdEndSeconds))
        }
    }
}

/// Study-tools #8 — Send to Miro: just the stickies, no board chrome (the toolbar and
/// grid distract; the famous colours ARE the recognition). Webview so the sticky type
/// and hand-set line wrapping stay exact. Appears in order, then holds.
struct MiroIllustrationView: View {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.welcomeAnimationActive) private var active

    var body: some View {
        let still = reduceMotion || !active   // baton: animate only while this cell holds it
        return IllustrationWebView(html: WelcomeIllustrationHTML.miro(dark: scheme == .dark, reduce: still))
            .id("miro-\(scheme)-\(still)")
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

// MARK: - Embedded HTML (ported verbatim from docs/mockups/welcome-science-animations.html)

enum WelcomeIllustrationHTML {

    static func quote(dark: Bool, reduce: Bool) -> String {
        let kind = WelcomeIllustration.quote
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{ --ink:#1a1a1a; --faint:#6b7280; --danger:#dc2626; }
          html[data-appearance="dark"]{ --ink:#e5e7eb; --faint:#9ca3af; --danger:#f87171; }
          html,body{ margin:0; height:100%; background:transparent; }
          body{ display:flex; align-items:center; justify-content:center; padding:6px 12px;
                font-family:-apple-system,"SF Pro Text",system-ui,sans-serif; color:var(--ink); }
          .q{ font-size:15px; line-height:1.5; }
          .qm{ color:var(--faint); }
          .tok{ display:inline; }
          .tok.trim{ display:inline-block; white-space:pre; max-width:20ch; opacity:1;
                     transition:max-width .5s cubic-bezier(.6,.02,.2,1), opacity .35s ease, color .3s ease, text-decoration-color .3s ease;
                     text-decoration:line-through; text-decoration-color:transparent; }
          .q.marked .tok.trim{ color:var(--danger); text-decoration-color:var(--danger); }
          .q.tidied .tok.trim{ max-width:0; opacity:0; }
          @media (prefers-reduced-motion:reduce){ *{ transition:none !important; } }
        </style></head>
        <body><div class="q" id="q"></div>
        <script>
          var R = document.documentElement.getAttribute("data-reduce")==="1" || matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind));
          var T=[{t:"So, ",x:1},{t:"um, ",x:1},{t:"The checkout",k:1},{t:", like,",x:1},{t:" was",k:1},
                 {t:" honestly,",x:1},{t:" the—the",x:1},{t:" confusing",k:1},{t:", you know?",x:1},
                 {t:" I couldn’t",k:1},{t:" actually",x:1},{t:" figure out where to",k:1},{t:" pay.",k:1}];
          var q=document.getElementById("q");
          q.innerHTML='<span class="qm">“</span>';
          T.forEach(function(o){ var s=document.createElement("span"); s.className="tok "+(o.x?"trim":"kept"); s.textContent=o.t; q.appendChild(s); });
          var c=document.createElement("span"); c.className="qm"; c.textContent="”"; q.appendChild(c);
          var S=[["",3800],["marked",3000],["marked tidied",4800],["marked",1400],["",1000]];
          var i=0;
          function set(){ q.className="q "+S[i][0]; }
          if(R){ i=1; set(); } else { set(); (function loop(){ setTimeout(function(){ i=(i+1)%S.length; set(); loop(); }, Math.round(S[i][1]*PACE)); })(); }
        </script></body></html>
        """
    }

    static func signal(dark: Bool, palette: String, reduce: Bool) -> String {
        let kind = WelcomeIllustration.signal
        let accent = palette == "edo" ? (dark ? "#4d9fe0" : "#0f5c9e") : (dark ? "#0a84ff" : "#007aff")
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{
            --ink:#1a1a1a; --faint:#6b7280; --line:#e5e7eb; --paper:#fff; --card:#f9f9fa;
            --accent:\(accent);
            --mono:"SF Mono",ui-monospace,Menlo,monospace;
            --badge-bg:#f3f4f6; --badge-text:#374151;
            --bn-sentiment-frustration:#ea580c; --bn-sentiment-frustration-bg:#fff7ed;
            --bn-sentiment-confusion:#dc2626;   --bn-sentiment-confusion-bg:#fef2f2;
            --bn-sentiment-doubt:#7c3aed;       --bn-sentiment-doubt-bg:#f5f3ff;
            --bn-sentiment-surprise:#d97706;    --bn-sentiment-surprise-bg:#fffbeb;
            --bn-sentiment-satisfaction:#16a34a;--bn-sentiment-satisfaction-bg:#f0fdf4;
            --bn-sentiment-delight:#059669;     --bn-sentiment-delight-bg:#ecfdf5;
            --bn-sentiment-confidence:#2563eb;  --bn-sentiment-confidence-bg:#eff6ff;
          }
          html[data-appearance="dark"]{
            --ink:#e5e7eb; --faint:#9ca3af; --line:#2d2d2d; --paper:#1c1c1e; --card:#232326;
            --badge-bg:#252525; --badge-text:#d1d5db;
            --bn-sentiment-frustration:#fb923c; --bn-sentiment-frustration-bg:#2d1d0e;
            --bn-sentiment-confusion:#f87171;   --bn-sentiment-confusion-bg:#2d1515;
            --bn-sentiment-doubt:#a78bfa;       --bn-sentiment-doubt-bg:#1e1533;
            --bn-sentiment-surprise:#fbbf24;    --bn-sentiment-surprise-bg:#2d2305;
            --bn-sentiment-satisfaction:#4ade80;--bn-sentiment-satisfaction-bg:#0f2918;
            --bn-sentiment-delight:#34d399;     --bn-sentiment-delight-bg:#0d261c;
            --bn-sentiment-confidence:#60a5fa;  --bn-sentiment-confidence-bg:#111d2e;
          }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }  /* clip → never a scrollbar */
          body{ font-family:-apple-system,"SF Pro Text",system-ui,sans-serif; color:var(--ink); position:relative; }
          .badge{ display:inline-block; font-family:var(--mono); font-size:0.72rem; padding:0.15rem 0.45rem; border-radius:3px; background:var(--badge-bg); color:var(--badge-text); line-height:1.35; white-space:nowrap; }
          .badge-frustration{ background:var(--bn-sentiment-frustration-bg); color:var(--bn-sentiment-frustration); }
          .badge-confusion{ background:var(--bn-sentiment-confusion-bg); color:var(--bn-sentiment-confusion); }
          .badge-doubt{ background:var(--bn-sentiment-doubt-bg); color:var(--bn-sentiment-doubt); }
          .badge-surprise{ background:var(--bn-sentiment-surprise-bg); color:var(--bn-sentiment-surprise); }
          .badge-satisfaction{ background:var(--bn-sentiment-satisfaction-bg); color:var(--bn-sentiment-satisfaction); }
          .badge-delight{ background:var(--bn-sentiment-delight-bg); color:var(--bn-sentiment-delight); }
          .badge-confidence{ background:var(--bn-sentiment-confidence-bg); color:var(--bn-sentiment-confidence); }
          /* Fixed natural size, centred, then uniformly scaled to fit (see fit()).
             Absolute (not a flex item) so width is honoured exactly — a flex item's
             default min-width:auto would inflate it to min-content and reflow. */
          .signal-card{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); transform-origin:center;
                        border:1px solid var(--line); border-radius:3px; padding:1rem; background:var(--paper); width:440px; }
          .signal-card-top{ display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
          .signal-card-identity{ flex:1; min-width:0; }
          .signal-card-source{ display:block; font-size:0.72rem; font-weight:420; text-transform:uppercase; letter-spacing:0.04em; color:var(--faint); margin-bottom:0.1rem; }
          .signal-card-location{ font-size:18px; line-height:1.3; font-weight:490; margin-bottom:0.35rem; color:var(--ink); }
          .signal-card-tags{ display:flex; gap:0.35rem; align-items:center; flex-wrap:wrap; }
          .signal-card-metrics{ flex-shrink:0; display:grid; grid-template-columns:auto auto auto; gap:0.2rem 0.6rem; align-items:center; font-size:0.8125rem; white-space:nowrap; }
          .metric-label{ color:var(--faint); text-align:right; }
          .metric-value{ font-family:var(--mono); font-size:0.8125rem; color:var(--ink); text-align:right; }
          .metric-viz{ display:flex; align-items:center; }
          .conc-bar-track{ display:block; width:96px; height:6px; background:var(--line); border-radius:3px; overflow:hidden; }
          .conc-bar-fill{ display:block; height:100%; border-radius:3px; background:var(--ink); opacity:0.45; transition:width 0.3s ease; }
          .intensity-dots-svg{ display:flex; align-items:center; gap:2px; width:46px; }
          .signal-sparkbars{ display:inline-flex; align-items:flex-end; gap:2px; height:28px; width:96px; }
          .signal-sparkbar{ width:12px; border-radius:1px 1px 0 0; }
          .pattern-label{ display:inline-block; font-family:var(--mono); font-size:0.72rem; font-weight:520; text-transform:uppercase; letter-spacing:0.06em; padding:0.15rem 0.45rem; border-radius:3px; opacity:0.9; }
          .pattern-success{ background:#dcfce7; color:#166534; } .pattern-tension{ background:#fef3c7; color:#92400e; }
          .pattern-gap{ background:#fee2e2; color:#991b1b; } .pattern-recovery{ background:#e0f2fe; color:#075985; }
          html[data-appearance="dark"] .pattern-success{ background:#14532d; color:#86efac; }
          html[data-appearance="dark"] .pattern-tension{ background:#451a03; color:#fcd34d; }
          html[data-appearance="dark"] .pattern-gap{ background:#450a0a; color:#fca5a5; }
          html[data-appearance="dark"] .pattern-recovery{ background:#0c4a6e; color:#7dd3fc; }
          .flap{ display:inline-block; overflow:hidden; vertical-align:bottom; }
          .flap .roll{ display:block; }
          .flap.flip .roll{ animation:flap-flip .3s ease-in; }
          @keyframes flap-flip{ 0%{ transform:translateY(-105%); opacity:.15; } 100%{ transform:translateY(0); opacity:1; } }
          @media (prefers-reduced-motion:reduce){ .flap.flip .roll{ animation:none !important; } .conc-bar-fill{ transition:none !important; } }
        </style></head>
        <body>
          <div class="signal-card">
            <div class="signal-card-top">
              <div class="signal-card-identity">
                <span class="signal-card-source" data-src></span>
                <div class="signal-card-location" data-loc></div>
                <div class="signal-card-tags"><span class="badge" data-tag></span><span class="pattern-label" data-pat></span></div>
              </div>
              <div class="signal-card-metrics">
                <span class="metric-label" title="Composite signal strength">Signal</span>
                <span class="metric-value" data-mv="signal"></span>
                <span class="metric-viz"><span class="signal-sparkbars" data-spark></span></span>
                <span class="metric-label" title="Concentration ratio — how overrepresented vs study average">Concentration</span>
                <span class="metric-value" data-mv="conc"></span>
                <span class="metric-viz"><span class="conc-bar-track"><span class="conc-bar-fill" data-cbar></span></span></span>
                <span class="metric-label" title="Agreement — effective number of voices (Simpson's diversity)">Agreement</span>
                <span class="metric-value" data-mv="agree"></span>
                <span class="metric-viz"><span class="conc-bar-track"><span class="conc-bar-fill" data-abar></span></span></span>
                <span class="metric-label" title="Mean emotional intensity (0–3)">Intensity</span>
                <span class="metric-value" data-mv="intensity"></span>
                <span class="metric-viz" data-dots></span>
              </div>
            </div>
          </div>
        <script>
          var R = document.documentElement.getAttribute("data-reduce")==="1" || matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind));
          function flapWord(host, word){
            host.innerHTML="";
            String(word).split("").forEach(function(ch,i){
              var f=document.createElement("span"); f.className="flap";
              var r=document.createElement("span"); r.className="roll";
              r.textContent = ch===" " ? " " : ch;
              f.appendChild(r); host.appendChild(f);
              if(!R) setTimeout(function(){ f.classList.add("flip"); setTimeout(function(){ f.classList.remove("flip"); },300); }, Math.round(i*40*PACE));
            });
          }
          var SIGNALS=[
            { src:"SECTION", loc:"Onboarding",     tag:["badge-confusion","confusion"],     accent:"var(--bn-sentiment-confusion)",   pat:["pattern-gap","GAP"],           signal:"2.41", conc:"3.2×", concPct:64, agree:"4.1", agreePct:68, intensity:2.5 },
            { src:"THEME",   loc:"Search results", tag:["badge-delight","delight"],         accent:"var(--bn-sentiment-delight)",     pat:["pattern-success","SUCCESS"],   signal:"1.98", conc:"2.6×", concPct:52, agree:"5.3", agreePct:88, intensity:2.1 },
            { src:"THEME",   loc:"Checkout",       tag:["badge-frustration","frustration"], accent:"var(--bn-sentiment-frustration)", pat:["pattern-tension","TENSION"],   signal:"3.12", conc:"4.3×", concPct:86, agree:"3.4", agreePct:57, intensity:2.8 },
            { src:"SECTION", loc:"Settings",       tag:["badge-doubt","doubt"],             accent:"var(--bn-sentiment-doubt)",       pat:["pattern-recovery","RECOVERY"], signal:"1.74", conc:"1.9×", concPct:38, agree:"2.2", agreePct:37, intensity:1.6 }
          ];
          var VALS=SIGNALS.map(function(s){ return parseFloat(s.signal); });
          function sparkbars(idx, accent){
            var max=Math.max.apply(null,VALS), maxH=28, n=VALS.length, barW=Math.floor((96-(n-1)*2)/n);
            return VALS.map(function(v,i){
              var h=Math.max(2,(v/max)*maxH), op=i===idx?1:Math.max(0.09,(v/max)*0.45), bg=i===idx?accent:"var(--ink)";
              return '<div class="signal-sparkbar" style="height:'+h+'px;width:'+barW+'px;background:'+bg+';opacity:'+op+'"></div>';
            }).join("");
          }
          function dotsSVG(value){
            var r=5,cx0=7,gap=16,w=cx0+gap*2+r+2,h=r*2+2,y=r+1,col="var(--ink)",rd=Math.round(value*2)/2,out="";
            for(var i=0;i<3;i++){ var th=i+1,x=cx0+i*gap;
              if(rd>=th) out+='<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+col+'" opacity="0.7"/>';
              else if(rd>=th-0.5) out+='<clipPath id="c'+i+'"><rect x="'+(x-r)+'" y="'+(y-r)+'" width="'+r+'" height="'+(r*2)+'"/></clipPath><circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="'+col+'" opacity="0.7" clip-path="url(#c'+i+')"/><circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="none" stroke="'+col+'" stroke-width="1.2" opacity="0.35"/>';
              else out+='<circle cx="'+x+'" cy="'+y+'" r="'+r+'" fill="none" stroke="'+col+'" stroke-width="1.2" opacity="0.35"/>';
            }
            return '<svg class="intensity-dots-svg" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'">'+out+'</svg>';
          }
          function q(sel){ return document.querySelector(sel); }
          var idx=0;
          function set(){
            var s=SIGNALS[idx];
            q("[data-src]").textContent=s.src;
            q("[data-tag]").className="badge "+s.tag[0]; q("[data-tag]").textContent=s.tag[1];
            q("[data-pat]").className="pattern-label "+s.pat[0];
            q("[data-spark]").innerHTML=sparkbars(idx,s.accent);
            q("[data-cbar]").style.width=s.concPct+"%"; q("[data-abar]").style.width=s.agreePct+"%";
            q("[data-dots]").innerHTML=dotsSVG(s.intensity);
            if(R){
              q("[data-loc]").textContent=s.loc; q("[data-pat]").textContent=s.pat[1];
              q('[data-mv="signal"]').textContent=s.signal; q('[data-mv="conc"]').textContent=s.conc;
              q('[data-mv="agree"]').textContent=s.agree;  q('[data-mv="intensity"]').textContent=s.intensity.toFixed(1);
              return;
            }
            flapWord(q("[data-loc]"), s.loc);
            flapWord(q("[data-pat]"), s.pat[1]);
            flapWord(q('[data-mv="signal"]'), s.signal);
            flapWord(q('[data-mv="conc"]'), s.conc);
            flapWord(q('[data-mv="agree"]'), s.agree);
            flapWord(q('[data-mv="intensity"]'), s.intensity.toFixed(1));
          }
          // Scale the whole card to fit the cell — aspect preserved, max 90% (like the
          // tools-cell images), shrinking further when narrower. Never wraps (internal
          // layout is a fixed 440px), never scrolls (body overflow hidden).
          function fit(){
            var c=document.querySelector('.signal-card');
            var s=Math.min(0.9,(window.innerWidth-8)/c.offsetWidth,(window.innerHeight-8)/c.offsetHeight);
            if(isFinite(s) && s>0) c.style.transform='translate(-50%,-50%) scale('+s+')';
          }
          set();
          requestAnimationFrame(fit);
          window.addEventListener('resize', fit);
          if(!R) setInterval(function(){ idx=(idx+1)%SIGNALS.length; set(); }, Math.round(2800*PACE));
        </script>
        </body></html>
        """
    }

    static func emergentThemes(dark: Bool, reduce: Bool) -> String {
        let kind = WelcomeIllustration.emergentThemes
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{ --ink:#1a1a1a; --faint:#6b7280; }
          html[data-appearance="dark"]{ --ink:#e5e7eb; --faint:#9ca3af; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ font-family:-apple-system,"SF Pro Text",system-ui,sans-serif; }
          .fish{ position:absolute; left:0; top:0; font-size:11px; font-weight:420; color:var(--ink); white-space:nowrap; transform:translate(-50%,-50%); }
          .tl{ position:absolute; left:0; top:0; transform:translate(-50%,-50%); text-align:center; opacity:0; transition:opacity .6s ease; pointer-events:none; }
          .tl .n{ font-size:12px; font-weight:600; color:var(--ink); white-space:nowrap; }
          .tl.on{ opacity:1; }
        </style></head>
        <body>
        <script>
          var R = document.documentElement.getAttribute("data-reduce")==="1" || matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          var SH={ A:{ name:"How to begin unclear", words:["“where do I start?”","confusing","too many steps","I gave up"] },
                   B:{ name:"Intuitive",            words:["“found it fast”","really clear","one tap","obvious"] } };
          var host=document.body, fishes=[], labels={};
          ["A","B"].forEach(function(key){ SH[key].words.forEach(function(txt){
            var el=document.createElement("span"); el.className="fish"; el.textContent=txt; host.appendChild(el);
            fishes.push({ el:el, key:key, phase:Math.random()*6.28, freq:(0.6+Math.random()*0.6)/PACE, amp:8+Math.random()*6 });
          }); });
          ["A","B"].forEach(function(key){ var l=document.createElement("div"); l.className="tl"; l.innerHTML='<div class="n">'+SH[key].name+'</div>'; host.appendChild(l); labels[key]=l; });
          function homes(W,H){ var cx=W/2, cy=H/2;
            var flock=fishes.map(function(f,i){ return { x:cx+Math.cos(i*1.7)*44, y:cy+Math.sin(i*2.3)*28 }; });
            var split=fishes.map(function(f){ var g=SH[f.key].words, idx=g.indexOf(f.el.textContent), n=g.length;
              var colX=f.key==="A"?W*0.30:W*0.70; var y0=cy-(n-1)/2*20+idx*20+8; return { x:colX, y:y0 }; });
            return { flock:flock, split:split };
          }
          function posLabels(){ var W=host.clientWidth||300; labels.A.style.left=(W*0.30)+"px"; labels.A.style.top="14px"; labels.B.style.left=(W*0.70)+"px"; labels.B.style.top="14px"; }
          if(R){
            var W0=host.clientWidth||300, H0=host.clientHeight||140, h0=homes(W0,H0);
            fishes.forEach(function(f,i){ f.el.style.transform="translate(-50%,-50%) translate("+h0.split[i].x+"px,"+h0.split[i].y+"px)"; });
            posLabels(); labels.A.classList.add("on"); labels.B.classList.add("on");
          } else {
            var CYCLE=Math.round(8200*PACE), SWOOP=Math.round(1600*PACE), t0=performance.now()+LEAD;   // LEAD rests on the gathered flock
            function ease(x){ return x<0.5 ? 2*x*x : 1-Math.pow(-2*x+2,2)/2; }
            function tick(now){ var W=host.clientWidth||300, H=host.clientHeight||140, hm=homes(W,H); posLabels();
              var el=now-t0; if(el<0) el=0;   // pre-LEAD: hold the opening flock
              var p=(el%CYCLE)/CYCLE, blend, show;
              if(p<SWOOP/CYCLE){ blend=ease(p/(SWOOP/CYCLE)); show=false; }
              else if(p<0.5){ blend=1; show=true; }
              else if(p<0.5+SWOOP/CYCLE){ blend=1-ease((p-0.5)/(SWOOP/CYCLE)); show=false; }
              else { blend=0; show=false; }
              labels.A.classList.toggle("on",show); labels.B.classList.toggle("on",show);
              var ts=now/1000;
              fishes.forEach(function(f,i){
                var hx=hm.flock[i].x+(hm.split[i].x-hm.flock[i].x)*blend;
                var hy=hm.flock[i].y+(hm.split[i].y-hm.flock[i].y)*blend;
                var j=f.amp*(1-blend*0.7);
                var x=hx+Math.cos(ts*f.freq+f.phase)*j, y=hy+Math.sin(ts*f.freq*1.3+f.phase)*j*0.8;
                f.el.style.transform="translate(-50%,-50%) translate("+x+"px,"+y+"px)";
              });
              requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
          }
        </script>
        </body></html>
        """
    }

    /// AutoCode (study tools #1) — quote streams in, the AI code arrives proposed,
    /// is accepted, goes solid, then a 3-play burst rests. Tag + quote CSS copied
    /// from badge.css / blockquote.css (dark-mode selector adapted to data-appearance).
    static func autocode(dark: Bool, palette: String, reduce: Bool) -> String {
        let kind = WelcomeIllustration.autocode
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-palette="\(palette)" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{
            --bn-colour-quote-bg:#f9fafb; --bn-colour-border:#e5e7eb; --bn-colour-muted:#6b7280; --bn-colour-accent:#007aff;
            --bn-colour-text:#1a1a1a; --bn-colour-bg:#ffffff; --bn-colour-badge-bg:#f3f4f6; --bn-colour-badge-text:#374151;
            --bn-colour-user-tag-bg:#f3f4f6; --bn-colour-success:#16a34a; --bn-colour-danger:#dc2626;
            --bn-sentiment-satisfaction:#16a34a; --bn-sentiment-satisfaction-bg:#f0fdf4;
            --code-blue-bg:#dbeafe; --code-violet-bg:#ede9fe;
            --bn-font-mono:"SF Mono",ui-monospace,Menlo,monospace;
            --bn-font-body:-apple-system,"SF Pro Text",system-ui,sans-serif;
            --bn-radius-sm:3px; --bn-radius-md:6px;
            --bn-space-xs:0.15rem; --bn-space-sm:0.35rem; --bn-space-md:0.75rem;
            --bn-text-body:0.9375rem; --bn-text-body-lh:1.5; --bn-text-label:0.8125rem; --bn-text-badge:0.72rem; --bn-text-micro:0.6rem;
            --bn-weight-normal:420; --bn-weight-emphasis:490; --bn-weight-strong:700;
          }
          html[data-appearance="dark"]{
            --bn-colour-quote-bg:#1a1a1a; --bn-colour-border:#2d2d2d; --bn-colour-muted:#9ca3af; --bn-colour-accent:#0a84ff;
            --bn-colour-text:#e5e7eb; --bn-colour-bg:#111111; --bn-colour-badge-bg:#252525; --bn-colour-badge-text:#d1d5db;
            --bn-colour-user-tag-bg:#252525; --bn-colour-success:#4ade80; --bn-colour-danger:#f87171;
            --bn-sentiment-satisfaction:#4ade80; --bn-sentiment-satisfaction-bg:#0f2918;
            --code-blue-bg:#1e3a5f; --code-violet-bg:#3b2f5c;
          }
          html[data-palette="edo"]{
            --bn-colour-quote-bg:#f0e9d8; --bn-colour-border:#d4c9a8; --bn-colour-muted:#4a698a; --bn-colour-accent:#0f5c9e;
            --bn-colour-text:#1b2230; --bn-colour-bg:#fdfbf7; --bn-colour-badge-bg:#e8dfc9; --bn-colour-badge-text:#2d3654;
            --bn-colour-user-tag-bg:#e8dfc9;
          }
          html[data-palette="edo"][data-appearance="dark"]{
            --bn-colour-quote-bg:#211e18; --bn-colour-border:#2d2820; --bn-colour-muted:#7ba8a0; --bn-colour-accent:#4d9fe0;
            --bn-colour-text:#e8e3d6; --bn-colour-bg:#1a1816; --bn-colour-badge-bg:#2d2820; --bn-colour-badge-text:#c4b898;
            --bn-colour-user-tag-bg:#2d2820;
          }
          *{ box-sizing:border-box; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ display:flex; align-items:center; padding:2px 12px; font-family:var(--bn-font-body); color:var(--bn-colour-text); }
          #ac{ width:100%; }
          blockquote.quote-card{ font-family:var(--bn-font-body); color:var(--bn-colour-text); background:var(--bn-colour-quote-bg); border-left:1px solid var(--bn-colour-border); margin:0; padding:var(--bn-space-md) 1rem; border-radius:0 var(--bn-radius-md) var(--bn-radius-md) 0; width:100%; }
          blockquote .quote-row{ display:flex; gap:0.5rem; align-items:baseline; }
          blockquote .quote-row .timecode{ flex-shrink:0; }
          blockquote .quote-body{ flex:1; min-width:0; font-size:var(--bn-text-body); line-height:var(--bn-text-body-lh); }
          blockquote .timecode{ color:var(--bn-colour-accent); font-family:var(--bn-font-mono); font-size:var(--bn-text-label); }
          .timecode-bracket{ color:var(--bn-colour-muted); }
          blockquote .speaker{ color:var(--bn-colour-muted); font-size:var(--bn-text-label); white-space:nowrap; }
          .smart-quote{ color:var(--bn-colour-muted); }
          .speaker .badge{ margin-left:4px; }
          .quote-card .badges{ display:flex; gap:var(--bn-space-sm); margin-top:0.45rem; flex-wrap:wrap; align-items:center; }
          .badge{ display:inline-block; font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); padding:var(--bn-space-xs) 0.45rem; border-radius:var(--bn-radius-sm); background:var(--bn-colour-badge-bg); color:var(--bn-colour-badge-text); }
          .badge-satisfaction{ background:var(--bn-sentiment-satisfaction-bg); color:var(--bn-sentiment-satisfaction); }
          .badge-ai{ position:relative; }
          .badge-user{ background:var(--bn-colour-user-tag-bg); color:var(--bn-colour-text); font-weight:var(--bn-weight-normal); position:relative; }
          html[data-appearance="dark"] .badge-user{ color:#ffffff; font-weight:var(--bn-weight-emphasis); }
          .badge.code-blue{ background:var(--code-blue-bg); }
          .badge.code-violet{ background:var(--code-violet-bg); }
          .badge-add{ border:1px dashed var(--bn-colour-border); background:transparent; color:var(--bn-colour-muted); }
          @keyframes bn-proposed-pulse{ 0%{opacity:.5} 50%{opacity:.78} 100%{opacity:.5} }
          .badge-proposed{ animation:bn-proposed-pulse 3.9s ease-in-out infinite; border:1px dashed currentColor; position:relative; }
          .badge-action-pill{ position:absolute; top:calc(-0.3rem - 1px); right:calc(-0.3rem - 1px - 1rem); display:flex; gap:0; background:var(--bn-colour-bg); border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.16),0 0 1px rgba(0,0,0,.06); opacity:0; pointer-events:none; overflow:hidden; z-index:1; }
          .badge-proposed.show-pill .badge-action-pill{ animation:pill-blink .72s ease-out; opacity:1; }
          .badge-action-deny,.badge-action-accept{ display:flex; align-items:center; justify-content:center; width:1rem; height:1rem; font-size:var(--bn-text-micro); font-weight:var(--bn-weight-strong); }
          .badge-action-deny{ color:var(--bn-colour-danger); }
          .badge-action-accept{ color:var(--bn-colour-success); border-left:1px solid var(--bn-colour-border); }
          .badge-action-accept.pressing{ background:#dcfce7; }
          html[data-appearance="dark"] .badge-action-accept.pressing{ background:rgba(22,163,74,.25); color:#4ade80; }
          @keyframes badge-accept-flash{ 0%{filter:brightness(1.35)} 100%{filter:brightness(1)} }
          .badge-accept-flash{ animation:badge-accept-flash .52s ease-out; }
          @keyframes badge-fade-in{ from{opacity:0; transform:scale(.8)} to{opacity:1; transform:scale(1)} }
          .badge-appearing{ animation:badge-fade-in .2s ease-out; }
          @keyframes chip-arrive{ 0%{opacity:0; transform:scale(.55); filter:brightness(1.7)} 55%{opacity:1; transform:scale(1.18); filter:brightness(1.5)} 78%{transform:scale(.95); filter:brightness(1.15)} 100%{transform:scale(1); filter:brightness(1)} }
          .chip-arrive{ transform-origin:center; animation:chip-arrive .8s cubic-bezier(.34,1.56,.64,1); }
          @keyframes pill-blink{ 0%{opacity:0} 22%{opacity:1} 42%{opacity:.12} 66%{opacity:1} 100%{opacity:1} }
          @keyframes pill-vanish{ from{opacity:1; transform:scale(1)} to{opacity:0; transform:scale(.5)} }
          .badge-action-pill.vanishing{ animation:pill-vanish .31s ease forwards; }
          .caret{ display:inline-block; width:2px; height:1em; background:var(--bn-colour-accent); margin-left:1px; vertical-align:text-bottom; }
          .caret.blink{ animation:caret-blink 1s step-end infinite; }
          @keyframes caret-blink{ 50%{opacity:0} }
          .quote-card.card-hidden{ opacity:0; transition:opacity .45s ease; }
          .quote-card.card-shown{ opacity:1; transition:opacity .45s ease; }
          @media (prefers-reduced-motion:reduce){ *{ animation:none !important; transition:none !important; } }
        </style></head>
        <body><div id="ac"></div>
        <script>
          var host=document.getElementById("ac");
          var REDUCED=document.documentElement.getAttribute("data-reduce")==="1"||matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          function sleep(ms){ return new Promise(function(r){ setTimeout(r, Math.round(ms*PACE)); }); }
          function nap(ms){ return sleep(ms); }   // PACE lives in sleep now; nap kept as the beat verb
          var QUOTES=[
            { time:"11:30", speaker:"p1", role:"Participant", sentiment:"Satisfaction", q:"In the end, browsing rather than searching works. Yeah, it did.", code:"visible options", codeClass:"code-blue" },
            { time:"13:08", speaker:"p1", role:"Participant", sentiment:"Satisfaction", q:"Is it normal it’s called a shopping bag? On another site it’d feel weird — you’re used to a cart.", code:"platform convention", codeClass:"code-violet" }
          ];
          function cardHTML(d){
            return '<blockquote class="quote-card card-hidden"><div class="quote-row">'
              +'<span class="timecode"><span class="timecode-bracket">[</span>'+d.time+'<span class="timecode-bracket">]</span></span>'
              +'<div class="quote-body"><span class="quote-text-wrapper"><span class="smart-quote">“</span><span class="quote-text"></span><span class="smart-quote closing" style="visibility:hidden">”</span></span>'
              +'<span class="speaker" style="visibility:hidden"><span class="badge">'+d.speaker+'</span><span class="badge">'+d.role+'</span></span>'
              +'<div class="badges"></div></div></div></blockquote>';
          }
          async function runCard(d, fadeOut){
            host.innerHTML=cardHTML(d);
            var card=host.querySelector(".quote-card"), qtext=host.querySelector(".quote-text"),
                qclose=host.querySelector(".smart-quote.closing"), speaker=host.querySelector(".speaker"), badges=host.querySelector(".badges");
            if(REDUCED){
              qtext.textContent=d.q; qclose.style.visibility=""; speaker.style.visibility="";
              badges.innerHTML='<span class="badge badge-ai badge-satisfaction">'+d.sentiment+'</span><span class="badge badge-user '+d.codeClass+'">'+d.code+'</span><span class="badge badge-add">+</span>';
              card.classList.remove("card-hidden"); card.classList.add("card-shown"); return;
            }
            await sleep(60);
            card.classList.remove("card-hidden"); card.classList.add("card-shown");
            var caret=document.createElement("span"); caret.className="caret blink"; qtext.after(caret);
            var words=d.q.split(" ");
            for(var i=0;i<words.length;i++){ qtext.textContent+=(i?" ":"")+words[i]; await sleep(46); }
            caret.classList.remove("blink"); await nap(260); caret.remove(); qclose.style.visibility="";
            speaker.style.visibility=""; speaker.classList.add("badge-appearing"); await nap(720);
            var sent=document.createElement("span"); sent.className="badge badge-ai badge-satisfaction badge-appearing"; sent.textContent=d.sentiment; badges.appendChild(sent);
            var add=document.createElement("span"); add.className="badge badge-add"; add.textContent="+"; badges.appendChild(add);
            await nap(1200);
            var chip=document.createElement("span"); chip.className="badge badge-proposed "+d.codeClass+" chip-arrive";
            chip.innerHTML=d.code+'<span class="badge-action-pill"><span class="badge-action-deny">✕</span><span class="badge-action-accept">✓</span></span>';
            badges.insertBefore(chip, add);
            await nap(760);
            chip.classList.add("show-pill"); await nap(1300);
            var acc=chip.querySelector(".badge-action-accept"); acc.classList.add("pressing"); await nap(260);
            var pill=chip.querySelector(".badge-action-pill"); if(pill) pill.classList.add("vanishing");
            chip.classList.remove("badge-proposed","show-pill","chip-arrive"); chip.classList.add("badge-user");
            void chip.offsetWidth; chip.classList.add("badge-accept-flash");
            await nap(300); if(pill) pill.remove();
            await nap(2600);
            if(fadeOut){ card.classList.remove("card-shown"); card.classList.add("card-hidden"); await nap(560); }
          }
          async function run(){   // the native baton owns the rhythm: play once per turn, then hold
            var d = REDUCED ? QUOTES[0] : QUOTES[Math.floor(Math.random()*QUOTES.length)];
            await runCard(d, false);
          }
          if(REDUCED){ run(); } else { setTimeout(run, LEAD); }   // rest on the empty opening frame first
        </script>
        </body></html>
        """
    }

    /// Manual tags (Codebooks) — the researcher hand-builds a codebook group:
    /// title + description + codes typed via the real + → type → commit flow, in the
    /// real codebook OKLCH colours (ux 250 / opp 75). The human counterpart to
    /// AutoCode; one group per turn (the baton owns the rhythm).
    static func manualTags(dark: Bool, palette: String, reduce: Bool) -> String {
        let kind = WelcomeIllustration.manualTags
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-palette="\(palette)" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{
            --bn-colour-quote-bg:#f9fafb; --bn-colour-border:#e5e7eb; --bn-colour-muted:#6b7280; --bn-colour-accent:#007aff;
            --bn-colour-text:#1a1a1a; --bn-colour-bg:#ffffff; --bn-colour-badge-bg:#f3f4f6; --bn-colour-badge-text:#374151;
            --bn-colour-user-tag-bg:#f3f4f6;
            --bn-font-mono:"SF Mono",ui-monospace,Menlo,monospace;
            --bn-font-body:-apple-system,"SF Pro Text",system-ui,sans-serif;
            --bn-radius-sm:3px; --bn-space-xs:0.15rem;
            --bn-text-label:0.8125rem; --bn-text-badge:0.72rem;
            --bn-weight-normal:420; --bn-weight-emphasis:490;
          }
          html[data-appearance="dark"]{
            --bn-colour-border:#2d2d2d; --bn-colour-muted:#9ca3af; --bn-colour-accent:#0a84ff;
            --bn-colour-text:#e5e7eb; --bn-colour-badge-bg:#252525; --bn-colour-badge-text:#d1d5db; --bn-colour-user-tag-bg:#252525;
          }
          html[data-palette="edo"]{
            --bn-colour-border:#d4c9a8; --bn-colour-muted:#4a698a; --bn-colour-accent:#0f5c9e; --bn-colour-text:#1b2230;
          }
          html[data-palette="edo"][data-appearance="dark"]{
            --bn-colour-border:#2d2820; --bn-colour-muted:#7ba8a0; --bn-colour-accent:#4d9fe0; --bn-colour-text:#e8e3d6;
          }
          *{ box-sizing:border-box; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ display:flex; align-items:center; padding:2px 12px; font-family:var(--bn-font-body); color:var(--bn-colour-text); }
          #mt{ width:100%; }
          .badge{ display:inline-block; font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); padding:var(--bn-space-xs) 0.45rem; border-radius:var(--bn-radius-sm); background:var(--bn-colour-badge-bg); color:var(--bn-colour-badge-text); }
          .badge-user{ background:var(--bn-colour-user-tag-bg); color:var(--bn-colour-text); font-weight:var(--bn-weight-normal); }
          html[data-appearance="dark"] .badge-user{ color:#ffffff; font-weight:var(--bn-weight-emphasis); }
          @keyframes badge-fade-in{ from{opacity:0; transform:scale(.8)} to{opacity:1; transform:scale(1)} }
          .badge-appearing{ animation:badge-fade-in .2s ease-out; }
          .caret{ display:inline-block; width:2px; height:1em; background:var(--bn-colour-accent); margin-left:1px; vertical-align:text-bottom; }
          .caret.blink{ animation:caret-blink 1s step-end infinite; }
          @keyframes caret-blink{ 50%{opacity:0} }
          .cb-group{ width:100%; border-radius:8px; padding:10px 12px; background:var(--grp-bg);
                     border:1px solid color-mix(in oklch, var(--grp-bg), var(--bn-colour-border) 55%);
                     opacity:0; transform:translateX(16px); transition:opacity .4s ease, transform .4s ease; }
          .cb-group.slide-in{ opacity:1; transform:none; }
          .group-title{ font-size:var(--bn-text-label); font-weight:var(--bn-weight-emphasis); color:var(--bn-colour-text); line-height:1.45; min-height:1.2em; }
          .group-subtitle{ font-size:11px; color:var(--bn-colour-muted); line-height:1.35; margin-top:1px; min-height:1em; }
          .tag-list{ display:flex; flex-direction:column; gap:3px; margin-top:7px; }
          .tag-row{ display:flex; align-items:center; min-height:1.4em; }
          .cb-tag{ background:var(--tag-bg); }
          .cb-input{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); color:var(--bn-colour-text); }
          .grp-ux{ --grp-bg:oklch(97% 0.015 250); } .grp-opp{ --grp-bg:oklch(97% 0.015 75); }
          html[data-appearance="dark"] .grp-ux{ --grp-bg:oklch(24% 0.03 250); } html[data-appearance="dark"] .grp-opp{ --grp-bg:oklch(24% 0.028 75); }
          .grp-ux .s0{ --tag-bg:oklch(93% 0.045 250); } .grp-ux .s1{ --tag-bg:oklch(89% 0.06 250); } .grp-ux .s2{ --tag-bg:oklch(85% 0.075 250); } .grp-ux .s3{ --tag-bg:oklch(82% 0.09 250); } .grp-ux .s4{ --tag-bg:oklch(78% 0.10 250); }
          .grp-opp .s0{ --tag-bg:oklch(93% 0.05 75); } .grp-opp .s1{ --tag-bg:oklch(89% 0.065 75); } .grp-opp .s2{ --tag-bg:oklch(85% 0.08 75); } .grp-opp .s3{ --tag-bg:oklch(82% 0.095 75); } .grp-opp .s4{ --tag-bg:oklch(78% 0.105 75); }
          html[data-appearance="dark"] .grp-ux .s0{ --tag-bg:oklch(40% 0.07 250); } html[data-appearance="dark"] .grp-ux .s1{ --tag-bg:oklch(44% 0.08 250); } html[data-appearance="dark"] .grp-ux .s2{ --tag-bg:oklch(48% 0.09 250); } html[data-appearance="dark"] .grp-ux .s3{ --tag-bg:oklch(52% 0.10 250); } html[data-appearance="dark"] .grp-ux .s4{ --tag-bg:oklch(56% 0.11 250); }
          html[data-appearance="dark"] .grp-opp .s0{ --tag-bg:oklch(40% 0.07 75); } html[data-appearance="dark"] .grp-opp .s1{ --tag-bg:oklch(44% 0.08 75); } html[data-appearance="dark"] .grp-opp .s2{ --tag-bg:oklch(48% 0.09 75); } html[data-appearance="dark"] .grp-opp .s3{ --tag-bg:oklch(52% 0.10 75); } html[data-appearance="dark"] .grp-opp .s4{ --tag-bg:oklch(56% 0.11 75); }
          @media (prefers-reduced-motion:reduce){ *{ animation:none !important; transition:none !important; } }
        </style></head>
        <body><div id="mt"></div>
        <script>
          var host=document.getElementById("mt");
          var REDUCED=document.documentElement.getAttribute("data-reduce")==="1"||matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          function sleep(ms){ return new Promise(function(r){ setTimeout(r, Math.round(ms*PACE)); }); }
          function nap(ms){ return sleep(ms); }   // PACE lives in sleep now; nap kept as the beat verb
          var GROUPS=[
            { cls:"grp-ux",  title:"A/B homepage trial",
              subtitle:"Reactions to the two homepage variants we tested.",
              tags:["A +ve","A -ve","B +ve","B -ve","AB choice"] },
            { cls:"grp-opp", title:"Switching costs",
              subtitle:"Barriers for a participant already using a rival tool.",
              tags:["data migration","learning curve","institutional inertia","better-but-not-better-enough"] }
          ];
          async function typeInto(el, text, msPerChar){ for(var i=0;i<text.length;i++){ el.textContent += text[i]; await sleep(msPerChar); } }
          async function buildGroup(g){
            host.innerHTML='<div class="cb-group '+g.cls+'"><div class="group-title"></div><div class="group-subtitle"></div><div class="tag-list"></div></div>';
            var grp=host.querySelector(".cb-group"), titleEl=host.querySelector(".group-title"),
                subEl=host.querySelector(".group-subtitle"), list=host.querySelector(".tag-list");
            void grp.offsetWidth; grp.classList.add("slide-in");
            if(REDUCED){
              titleEl.textContent=g.title; subEl.textContent=g.subtitle;
              for(var k=0;k<g.tags.length;k++){ var r=document.createElement("div"); r.className="tag-row";
                var c=document.createElement("span"); c.className="badge badge-user cb-tag s"+k; c.textContent=g.tags[k]; r.appendChild(c); list.appendChild(r); }
              return;
            }
            await nap(140);
            await typeInto(titleEl, g.title, 46);      // title, by hand
            await nap(240);
            await typeInto(subEl, g.subtitle, 26);     // description
            await nap(340);
            for(var i=0;i<g.tags.length;i++){          // each code via + -> type -> commit -> chip
              var ed=document.createElement("div"); ed.className="tag-row editor";
              var inp=document.createElement("span"); inp.className="cb-input";
              var caret=document.createElement("span"); caret.className="caret blink";
              ed.appendChild(inp); ed.appendChild(caret); list.appendChild(ed);
              await typeInto(inp, g.tags[i], 44);
              caret.classList.remove("blink"); await nap(230);
              ed.remove();
              var row=document.createElement("div"); row.className="tag-row";
              var chip=document.createElement("span"); chip.className="badge badge-user cb-tag badge-appearing s"+i;
              chip.textContent=g.tags[i]; row.appendChild(chip); list.appendChild(row);
              await nap(380);
            }
            await nap(1700);                           // hold on the finished group
          }
          async function run(){   // one group per turn (random); the baton alternates across turns
            var g = REDUCED ? GROUPS[0] : GROUPS[Math.floor(Math.random()*GROUPS.length)];
            await buildGroup(g);
          }
          if(REDUCED){ run(); } else { setTimeout(run, LEAD); }   // rest on the empty opening frame first
        </script>
        </body></html>
        """
    }

    /// Tag (study-tools #3) — pointer arcs onto the card's left rule (chrome, NOT the
    /// words — clicking the text opens trim/edit), a plain click focuses + single-selects
    /// (real .bn-focused.bn-selected), the `t` keycap presses under the cursor, and a code
    /// types itself in as a real .badge-user chip. Real selection colours; plays once/turn.
    static func tag(dark: Bool, palette: String, reduce: Bool) -> String {
        let kind = WelcomeIllustration.tag
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-palette="\(palette)" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{
            --bn-colour-quote-bg:#f9fafb; --bn-colour-border:#e5e7eb; --bn-colour-muted:#6b7280; --bn-colour-accent:#007aff;
            --bn-colour-text:#1a1a1a; --bn-colour-bg:#ffffff; --bn-colour-badge-bg:#f3f4f6; --bn-colour-badge-text:#374151;
            --bn-colour-user-tag-bg:#f3f4f6;
            --bn-sentiment-satisfaction:#16a34a; --bn-sentiment-satisfaction-bg:#f0fdf4; --code-blue-bg:#dbeafe;
            --bn-selection-bg:#eef4fc; --bn-selection-border:var(--bn-colour-accent);
            --bn-focus-shadow:0 3px 12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05);
            --bn-colour-border-hover:#d1d5db;
            --bn-cap-face:#fbfbfc; --bn-cap-face-lo:#f0f1f3; --bn-cap-highlight:rgba(255,255,255,.9); --bn-cap-edge:#cfd2d7;
            --bn-font-mono:"SF Mono",ui-monospace,Menlo,monospace;
            --bn-font-body:-apple-system,"SF Pro Text",system-ui,sans-serif;
            --bn-radius-sm:3px; --bn-radius-md:6px;
            --bn-space-xs:0.15rem; --bn-space-sm:0.35rem;
            --bn-text-body:0.9375rem; --bn-text-body-lh:1.5; --bn-text-label:0.8125rem; --bn-text-badge:0.72rem;
            --bn-weight-normal:420; --bn-weight-emphasis:490;
          }
          html[data-appearance="dark"]{
            --bn-colour-quote-bg:#1a1a1a; --bn-colour-border:#2d2d2d; --bn-colour-muted:#9ca3af; --bn-colour-accent:#0a84ff;
            --bn-colour-text:#e5e7eb; --bn-colour-bg:#111111; --bn-colour-badge-bg:#252525; --bn-colour-badge-text:#d1d5db;
            --bn-colour-user-tag-bg:#252525;
            --bn-sentiment-satisfaction:#4ade80; --bn-sentiment-satisfaction-bg:#0f2918; --code-blue-bg:#1e3a5f;
            --bn-selection-bg:#1a2838; --bn-colour-border-hover:#3a3a3a;
            --bn-cap-face:#2c2c2e; --bn-cap-face-lo:#232325; --bn-cap-highlight:rgba(255,255,255,.06); --bn-cap-edge:#000;
          }
          html[data-palette="edo"]{
            --bn-colour-quote-bg:#f0e9d8; --bn-colour-border:#d4c9a8; --bn-colour-muted:#4a698a; --bn-colour-accent:#0f5c9e;
            --bn-colour-text:#1b2230; --bn-colour-bg:#fdfbf7; --bn-colour-badge-bg:#e8dfc9; --bn-colour-badge-text:#2d3654;
            --bn-colour-user-tag-bg:#e8dfc9;
            --bn-selection-bg:#e0e8f0; --bn-colour-border-hover:#c4b896;
            --bn-focus-shadow:0 3px 12px rgba(30,20,10,0.12), 0 0 0 1px rgba(30,20,10,0.06);
            --bn-cap-face:#fdfbf7; --bn-cap-face-lo:#f3ecdb; --bn-cap-highlight:rgba(255,255,255,.85); --bn-cap-edge:#d4c9a8;
          }
          html[data-palette="edo"][data-appearance="dark"]{
            --bn-colour-quote-bg:#211e18; --bn-colour-border:#2d2820; --bn-colour-muted:#7ba8a0; --bn-colour-accent:#4d9fe0;
            --bn-colour-text:#e8e3d6; --bn-colour-bg:#1a1816; --bn-colour-badge-bg:#2d2820; --bn-colour-badge-text:#c4b898;
            --bn-colour-user-tag-bg:#2d2820;
            --bn-selection-bg:#1e2830; --bn-colour-border-hover:#3a3428;
            --bn-cap-face:#211e18; --bn-cap-face-lo:#1a1816; --bn-cap-highlight:rgba(255,255,255,.05); --bn-cap-edge:#000;
          }
          *{ box-sizing:border-box; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ display:flex; align-items:center; padding:10px 14px; font-family:var(--bn-font-body); color:var(--bn-colour-text); }
          #stage{ position:relative; width:100%; }
          .sh-stage{ display:flex; flex-direction:column; gap:7px; }
          blockquote.quote-card{ position:relative; font-family:var(--bn-font-body); color:var(--bn-colour-text); background:var(--bn-colour-quote-bg); border-left:1px solid var(--bn-colour-border); margin:0; padding:0.55rem 0.85rem; border-radius:0 var(--bn-radius-md) var(--bn-radius-md) 0; width:100%; }
          blockquote .quote-row{ display:flex; gap:0.5rem; align-items:baseline; }
          blockquote .timecode{ color:var(--bn-colour-accent); font-family:var(--bn-font-mono); font-size:var(--bn-text-label); flex-shrink:0; }
          .timecode-bracket{ color:var(--bn-colour-muted); }
          blockquote .quote-body{ flex:1; min-width:0; font-size:var(--bn-text-body); line-height:var(--bn-text-body-lh); }
          blockquote .speaker{ color:var(--bn-colour-muted); font-size:var(--bn-text-label); white-space:nowrap; }
          .speaker .badge{ margin-left:4px; }
          .smart-quote{ color:var(--bn-colour-muted); }
          .quote-card .badges{ display:flex; gap:var(--bn-space-sm); margin-top:0.45rem; flex-wrap:wrap; align-items:center; }
          .badge{ display:inline-block; font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); padding:var(--bn-space-xs) 0.45rem; border-radius:var(--bn-radius-sm); background:var(--bn-colour-badge-bg); color:var(--bn-colour-badge-text); }
          .badge-satisfaction{ background:var(--bn-sentiment-satisfaction-bg); color:var(--bn-sentiment-satisfaction); }
          .badge-user{ background:var(--bn-colour-user-tag-bg); color:var(--bn-colour-text); font-weight:var(--bn-weight-normal); }
          html[data-appearance="dark"] .badge-user{ color:#ffffff; font-weight:var(--bn-weight-emphasis); }
          .badge.code-blue{ background:var(--code-blue-bg); }
          .badge-add{ border:1px dashed var(--bn-colour-border); background:transparent; color:var(--bn-colour-muted); }
          .cb-input{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); color:var(--bn-colour-text); }
          .caret{ display:inline-block; width:2px; height:1em; background:var(--bn-colour-accent); margin-left:1px; vertical-align:text-bottom; }
          .caret.blink{ animation:caret-blink 1s step-end infinite; }
          @keyframes caret-blink{ 50%{opacity:0} }
          @keyframes badge-fade-in{ from{opacity:0; transform:scale(.8)} to{opacity:1; transform:scale(1)} }
          .badge-appearing{ animation:badge-fade-in .2s ease-out; }
          blockquote.quote-card.bn-focused{ background:var(--bn-colour-bg); box-shadow:var(--bn-focus-shadow); z-index:2; }
          blockquote.quote-card.bn-selected{ background:var(--bn-selection-bg); border-left-color:var(--bn-selection-border); }
          .cap{ position:absolute; z-index:8; display:inline-flex; align-items:center; justify-content:center; min-width:1.7em; height:1.7em; padding:0 .42em; font-family:var(--bn-font-mono); font-size:var(--bn-text-label); font-weight:500; line-height:1; color:var(--bn-colour-text); border-radius:5px; pointer-events:none; }
          .cap--raised{ background:linear-gradient(var(--bn-cap-face),var(--bn-cap-face-lo)); border:1px solid var(--bn-colour-border-hover); box-shadow:0 1.5px 0 0 var(--bn-cap-edge), inset 0 1px 0 0 var(--bn-cap-highlight); }
          @keyframes cap-enter{ from{opacity:0; transform:translateY(7px) scale(.9)} to{opacity:1; transform:translateY(0) scale(1)} }
          .cap-enter{ animation:cap-enter .2s ease-out; }
          @keyframes cap-leave{ to{opacity:0; transform:translateY(-5px) scale(.92)} }
          .cap-leave{ animation:cap-leave .22s ease forwards; }
          .cap.cap-press{ transform:translateY(1.5px); box-shadow:inset 0 1px 2px rgba(0,0,0,.2), 0 0 0 3px var(--bn-selection-border); filter:brightness(.97); }
          .ptr{ position:absolute; left:0; top:0; z-index:9; pointer-events:none; filter:drop-shadow(0 1px 1.5px rgba(0,0,0,.35)); }
          .ptr-ico{ display:block; transform-origin:4px 3px; }
          @keyframes ptr-click{ 0%{transform:scale(1)} 45%{transform:scale(.8)} 100%{transform:scale(1)} }
          .ptr.ptr-click .ptr-ico{ animation:ptr-click .24s ease; }
          @media (prefers-reduced-motion:reduce){ *{ animation:none !important; transition:none !important; } }
        </style></head>
        <body><div id="stage"></div>
        <script>
          var host=document.getElementById("stage");
          var REDUCED=document.documentElement.getAttribute("data-reduce")==="1"||matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          function sleep(ms){ return new Promise(function(r){ setTimeout(r, Math.round(ms*PACE)); }); }
          function nap(ms){ return sleep(ms); }   // PACE lives in sleep now; nap kept as the beat verb
          function settle(){ return new Promise(function(r){ requestAnimationFrame(function(){ requestAnimationFrame(r); }); }); }
          var PTR_SVG='<svg width="21" height="21" viewBox="0 0 12 19"><path d="M1.2 1.2 L1.2 14.6 L4.8 11.3 L7.1 16.8 L9.3 15.8 L7.0 10.4 L11.4 10.4 Z" fill="#ffffff" stroke="#111111" stroke-width="1.1" stroke-linejoin="round"/></svg>';
          function mkPointer(){ var p=document.createElement("div"); p.className="ptr"; p.innerHTML='<span class="ptr-ico">'+PTR_SVG+'</span>'; host.appendChild(p); return p; }
          function relXY(el, dx, dy){ var hr=host.getBoundingClientRect(), r=el.getBoundingClientRect(); return [r.left-hr.left+(dx||0), r.top-hr.top+(dy||0)]; }
          function setPtr(p,x,y){ p.style.transition="none"; p.style.transform="translate("+x+"px,"+y+"px)"; p._x=x; p._y=y; }
          function bez(a,c,b,t){ var u=1-t; return u*u*a+2*u*t*c+t*t*b; }
          function glideCurve(p, el, dx, dy){
            var e=relXY(el,dx,dy), ex=e[0], ey=e[1];
            var sx=(p._x!=null?p._x:ex), sy=(p._y!=null?p._y:ey);
            var vx=ex-sx, vy=ey-sy, dist=Math.hypot(vx,vy)||1, bow=Math.min(48,dist*0.22);
            var cx=(sx+ex)/2+(-vy/dist)*bow, cy=(sy+ey)/2+(vx/dist)*bow, N=18, frames=[];
            for(var i=0;i<=N;i++){ var t=i/N; frames.push({transform:"translate("+bez(sx,cx,ex,t)+"px,"+bez(sy,cy,ey,t)+"px)"}); }
            p.style.transition="none"; p.animate(frames,{duration:Math.round(640*PACE), easing:"ease-in-out", fill:"forwards"});
            p._x=ex; p._y=ey; return nap(640);
          }
          async function clickPulse(p){ p.classList.remove("ptr-click"); void p.offsetWidth; p.classList.add("ptr-click"); await nap(260); }
          function fadePtr(p){ p.style.transition="opacity .35s ease"; p.style.opacity="0"; }
          function mkCap(x,y,letter){ var c=document.createElement("span"); c.className="cap cap--raised cap-enter"; c.textContent=letter; c.style.left=x+"px"; c.style.top=y+"px"; host.appendChild(c); return c; }
          async function pressCap(c){ await nap(140); c.classList.add("cap-press"); await nap(150); c.classList.remove("cap-press"); await nap(150); }
          async function leaveCap(c){ c.classList.remove("cap-enter"); void c.offsetWidth; c.classList.add("cap-leave"); await nap(240); c.remove(); }
          async function typeInto(el, text, ms){ for(var i=0;i<text.length;i++){ el.textContent+=text[i]; await sleep(ms); } }
          var TAGQ={ time:"09:14", speaker:"p3", role:"Participant", sentiment:"Satisfaction", q:"I knew straight away where to click — it matched what I expected.", tag:"mental model", tagClass:"code-blue" };
          function tagCard(d){
            return '<blockquote class="quote-card sh-card"><div class="quote-row">'
              +'<span class="timecode"><span class="timecode-bracket">[</span>'+d.time+'<span class="timecode-bracket">]</span></span>'
              +'<div class="quote-body"><span class="smart-quote">“</span>'+d.q+'<span class="smart-quote">”</span> '
              +'<span class="speaker"><span class="badge">'+d.speaker+'</span><span class="badge">'+d.role+'</span></span>'
              +'<div class="badges"><span class="badge badge-ai badge-satisfaction">'+d.sentiment+'</span><span class="badge badge-add">+</span></div>'
              +'</div></div></blockquote>';
          }
          async function runTag(){
            host.innerHTML='<div class="sh-stage">'+tagCard(TAGQ)+'</div>';
            var card=host.querySelector(".quote-card"), badges=host.querySelector(".badges"), add=host.querySelector(".badge-add");
            if(REDUCED){ var rc=document.createElement("span"); rc.className="badge badge-user "+TAGQ.tagClass; rc.textContent=TAGQ.tag; badges.insertBefore(rc, add); return; }
            await settle();
            var p=mkPointer();
            var s=relXY(card, card.offsetWidth-6, card.offsetHeight+20); setPtr(p,s[0],s[1]);
            await nap(360);
            await glideCurve(p, card, 12, card.offsetHeight*0.5);      // arc onto the LEFT RULE (chrome, not the words)
            await clickPulse(p); card.classList.add("bn-focused","bn-selected");
            await nap(360);
            var cap=mkCap(p._x-2, p._y+14, "t");                       // key under the cursor, over empty gutter
            await pressCap(cap);
            var ed=document.createElement("span"); ed.className="cb-input";
            var caret=document.createElement("span"); caret.className="caret blink";
            badges.insertBefore(ed, add); badges.insertBefore(caret, add);
            await typeInto(ed, TAGQ.tag, 60);
            caret.classList.remove("blink"); await nap(220);
            ed.remove(); caret.remove();
            var chip=document.createElement("span"); chip.className="badge badge-user "+TAGQ.tagClass+" badge-appearing"; chip.textContent=TAGQ.tag;
            badges.insertBefore(chip, add);
            await leaveCap(cap);
            card.classList.remove("bn-focused","bn-selected"); fadePtr(p);
          }
          if(REDUCED){ runTag(); } else { setTimeout(runTag, LEAD); }   // rest on the opening frame first
        </script>
        </body></html>
        """
    }

    /// Star & hide (study-tools #4) — pointer arcs onto card A's rule, clicks (focus+select),
    /// `s` stars it (real #999/#ccc tint differential + weight bump + star-pop); then card B,
    /// `h` collapses it away (real .bn-hiding) and the "N hidden" count ticks up. Plays once/turn.
    static func starHide(dark: Bool, palette: String, reduce: Bool) -> String {
        let kind = WelcomeIllustration.starHide
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-palette="\(palette)" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          :root{
            --bn-colour-quote-bg:#f9fafb; --bn-colour-border:#e5e7eb; --bn-colour-muted:#6b7280; --bn-colour-accent:#007aff;
            --bn-colour-text:#1a1a1a; --bn-colour-bg:#ffffff; --bn-colour-badge-bg:#f3f4f6; --bn-colour-badge-text:#374151;
            --bn-sentiment-satisfaction:#16a34a; --bn-sentiment-satisfaction-bg:#f0fdf4;
            --bn-selection-bg:#eef4fc; --bn-selection-border:var(--bn-colour-accent);
            --bn-focus-shadow:0 3px 12px rgba(0,0,0,0.12), 0 0 0 1px rgba(0,0,0,0.05);
            --bn-colour-starred:#999; --bn-colour-icon-idle:#c9ccd1; --bn-colour-border-hover:#d1d5db;
            --bn-cap-face:#fbfbfc; --bn-cap-face-lo:#f0f1f3; --bn-cap-highlight:rgba(255,255,255,.9); --bn-cap-edge:#cfd2d7;
            --bn-font-mono:"SF Mono",ui-monospace,Menlo,monospace;
            --bn-font-body:-apple-system,"SF Pro Text",system-ui,sans-serif;
            --bn-radius-sm:3px; --bn-radius-md:6px;
            --bn-space-xs:0.15rem; --bn-space-sm:0.35rem;
            --bn-text-body:0.9375rem; --bn-text-body-lh:1.5; --bn-text-label:0.8125rem; --bn-text-badge:0.72rem;
            --bn-weight-normal:420; --bn-weight-emphasis:490; --bn-weight-starred:520;
          }
          html[data-appearance="dark"]{
            --bn-colour-quote-bg:#1a1a1a; --bn-colour-border:#2d2d2d; --bn-colour-muted:#9ca3af; --bn-colour-accent:#0a84ff;
            --bn-colour-text:#e5e7eb; --bn-colour-bg:#111111; --bn-colour-badge-bg:#252525; --bn-colour-badge-text:#d1d5db;
            --bn-sentiment-satisfaction:#4ade80; --bn-sentiment-satisfaction-bg:#0f2918;
            --bn-selection-bg:#1a2838; --bn-colour-starred:#ccc; --bn-colour-icon-idle:#595959; --bn-colour-border-hover:#3a3a3a;
            --bn-cap-face:#2c2c2e; --bn-cap-face-lo:#232325; --bn-cap-highlight:rgba(255,255,255,.06); --bn-cap-edge:#000;
          }
          html[data-palette="edo"]{
            --bn-colour-quote-bg:#f0e9d8; --bn-colour-border:#d4c9a8; --bn-colour-muted:#4a698a; --bn-colour-accent:#0f5c9e;
            --bn-colour-text:#1b2230; --bn-colour-bg:#fdfbf7; --bn-colour-badge-bg:#e8dfc9; --bn-colour-badge-text:#2d3654;
            --bn-selection-bg:#e0e8f0; --bn-colour-starred:#9e8b6e; --bn-colour-icon-idle:#b8ad91; --bn-colour-border-hover:#c4b896;
            --bn-focus-shadow:0 3px 12px rgba(30,20,10,0.12), 0 0 0 1px rgba(30,20,10,0.06);
            --bn-cap-face:#fdfbf7; --bn-cap-face-lo:#f3ecdb; --bn-cap-highlight:rgba(255,255,255,.85); --bn-cap-edge:#d4c9a8;
          }
          html[data-palette="edo"][data-appearance="dark"]{
            --bn-colour-quote-bg:#211e18; --bn-colour-border:#2d2820; --bn-colour-muted:#7ba8a0; --bn-colour-accent:#4d9fe0;
            --bn-colour-text:#e8e3d6; --bn-colour-bg:#1a1816; --bn-colour-badge-bg:#2d2820; --bn-colour-badge-text:#c4b898;
            --bn-selection-bg:#1e2830; --bn-colour-starred:#b8a880; --bn-colour-icon-idle:#4a4030; --bn-colour-border-hover:#3a3428;
            --bn-cap-face:#211e18; --bn-cap-face-lo:#1a1816; --bn-cap-highlight:rgba(255,255,255,.05); --bn-cap-edge:#000;
          }
          *{ box-sizing:border-box; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ display:flex; align-items:center; padding:9px 14px; font-family:var(--bn-font-body); color:var(--bn-colour-text); }
          #stage{ position:relative; width:100%; }
          .sh-toolbar{ display:flex; justify-content:flex-end; align-items:center; min-height:18px; margin-bottom:3px; }
          .bn-hidden-toggle{ background:none; border:none; font-size:var(--bn-text-label); color:var(--bn-colour-accent); font-family:var(--bn-font-body); padding:2px 4px; display:inline-block; }
          .bn-hidden-chevron{ font-size:.7em; margin-left:.15em; }
          @keyframes hidden-bump{ 0%{transform:scale(1)} 38%{transform:scale(1.18); filter:brightness(1.35)} 100%{transform:scale(1)} }
          .bn-hidden-toggle.bump{ animation:hidden-bump .5s ease; }
          .sh-stage{ display:flex; flex-direction:column; gap:7px; }
          blockquote.quote-card{ position:relative; font-family:var(--bn-font-body); color:var(--bn-colour-text); background:var(--bn-colour-quote-bg); border-left:1px solid var(--bn-colour-border); margin:0; padding:0.55rem 0.85rem; border-radius:0 var(--bn-radius-md) var(--bn-radius-md) 0; width:100%; }
          blockquote .quote-row{ display:flex; gap:0.5rem; align-items:baseline; }
          blockquote .timecode{ color:var(--bn-colour-accent); font-family:var(--bn-font-mono); font-size:var(--bn-text-label); flex-shrink:0; }
          .timecode-bracket{ color:var(--bn-colour-muted); }
          blockquote .quote-body{ flex:1; min-width:0; font-size:var(--bn-text-body); line-height:var(--bn-text-body-lh); }
          blockquote .speaker{ color:var(--bn-colour-muted); font-size:var(--bn-text-label); white-space:nowrap; }
          .speaker .badge{ margin-left:4px; }
          .smart-quote{ color:var(--bn-colour-muted); }
          .quote-card .badges{ display:flex; gap:var(--bn-space-sm); margin-top:0.45rem; flex-wrap:wrap; align-items:center; }
          .badge{ display:inline-block; font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); padding:var(--bn-space-xs) 0.45rem; border-radius:var(--bn-radius-sm); background:var(--bn-colour-badge-bg); color:var(--bn-colour-badge-text); }
          .badge-satisfaction{ background:var(--bn-sentiment-satisfaction-bg); color:var(--bn-sentiment-satisfaction); }
          .badge-add{ border:1px dashed var(--bn-colour-border); background:transparent; color:var(--bn-colour-muted); }
          .star-btn,.hide-btn{ position:absolute; top:.5rem; background:none; border:none; font-size:var(--bn-text-label); color:var(--bn-colour-icon-idle); padding:2px; line-height:1; display:inline-block; }
          .star-btn{ right:.55rem; }
          .hide-btn{ right:1.9rem; opacity:0; }
          blockquote.quote-card.bn-focused .hide-btn{ opacity:1; }
          .hide-btn svg{ display:block; }
          blockquote.quote-card.starred{ font-weight:var(--bn-weight-starred); border-left-color:var(--bn-colour-starred); }
          blockquote.quote-card.starred .star-btn{ color:var(--bn-colour-starred); }
          @keyframes star-pop{ 0%{transform:scale(1)} 40%{transform:scale(1.55)} 100%{transform:scale(1)} }
          .star-btn.pop{ animation:star-pop .42s cubic-bezier(.34,1.56,.64,1); }
          blockquote.quote-card.bn-hiding{ max-height:0 !important; opacity:0; overflow:hidden; margin:0 !important; padding-top:0 !important; padding-bottom:0 !important; border-width:0 !important; transition:all 300ms ease; }
          blockquote.quote-card.bn-hidden{ display:none !important; }
          blockquote.quote-card.bn-focused{ background:var(--bn-colour-bg); box-shadow:var(--bn-focus-shadow); z-index:2; }
          blockquote.quote-card.bn-selected{ background:var(--bn-selection-bg); border-left-color:var(--bn-selection-border); }
          .cap{ position:absolute; z-index:8; display:inline-flex; align-items:center; justify-content:center; min-width:1.7em; height:1.7em; padding:0 .42em; font-family:var(--bn-font-mono); font-size:var(--bn-text-label); font-weight:500; line-height:1; color:var(--bn-colour-text); border-radius:5px; pointer-events:none; }
          .cap--raised{ background:linear-gradient(var(--bn-cap-face),var(--bn-cap-face-lo)); border:1px solid var(--bn-colour-border-hover); box-shadow:0 1.5px 0 0 var(--bn-cap-edge), inset 0 1px 0 0 var(--bn-cap-highlight); }
          @keyframes cap-enter{ from{opacity:0; transform:translateY(7px) scale(.9)} to{opacity:1; transform:translateY(0) scale(1)} }
          .cap-enter{ animation:cap-enter .2s ease-out; }
          @keyframes cap-leave{ to{opacity:0; transform:translateY(-5px) scale(.92)} }
          .cap-leave{ animation:cap-leave .22s ease forwards; }
          .cap.cap-press{ transform:translateY(1.5px); box-shadow:inset 0 1px 2px rgba(0,0,0,.2), 0 0 0 3px var(--bn-selection-border); filter:brightness(.97); }
          .ptr{ position:absolute; left:0; top:0; z-index:9; pointer-events:none; filter:drop-shadow(0 1px 1.5px rgba(0,0,0,.35)); }
          .ptr-ico{ display:block; transform-origin:4px 3px; }
          @keyframes ptr-click{ 0%{transform:scale(1)} 45%{transform:scale(.8)} 100%{transform:scale(1)} }
          .ptr.ptr-click .ptr-ico{ animation:ptr-click .24s ease; }
          @media (prefers-reduced-motion:reduce){ *{ animation:none !important; transition:none !important; } }
        </style></head>
        <body><div id="stage"></div>
        <script>
          var host=document.getElementById("stage");
          var REDUCED=document.documentElement.getAttribute("data-reduce")==="1"||matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          function sleep(ms){ return new Promise(function(r){ setTimeout(r, Math.round(ms*PACE)); }); }
          function nap(ms){ return sleep(ms); }   // PACE lives in sleep now; nap kept as the beat verb
          function settle(){ return new Promise(function(r){ requestAnimationFrame(function(){ requestAnimationFrame(r); }); }); }
          var PTR_SVG='<svg width="21" height="21" viewBox="0 0 12 19"><path d="M1.2 1.2 L1.2 14.6 L4.8 11.3 L7.1 16.8 L9.3 15.8 L7.0 10.4 L11.4 10.4 Z" fill="#ffffff" stroke="#111111" stroke-width="1.1" stroke-linejoin="round"/></svg>';
          var HIDE_SVG='<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"><path d="M2 8s2.3-4 6-4 6 4 6 4-2.3 4-6 4-6-4-6-4Z"/><circle cx="8" cy="8" r="1.7"/><line x1="3.2" y1="12.8" x2="12.8" y2="3.2"/></svg>';
          function mkPointer(){ var p=document.createElement("div"); p.className="ptr"; p.innerHTML='<span class="ptr-ico">'+PTR_SVG+'</span>'; host.appendChild(p); return p; }
          function relXY(el, dx, dy){ var hr=host.getBoundingClientRect(), r=el.getBoundingClientRect(); return [r.left-hr.left+(dx||0), r.top-hr.top+(dy||0)]; }
          function setPtr(p,x,y){ p.style.transition="none"; p.style.transform="translate("+x+"px,"+y+"px)"; p._x=x; p._y=y; }
          function bez(a,c,b,t){ var u=1-t; return u*u*a+2*u*t*c+t*t*b; }
          function glideCurve(p, el, dx, dy){
            var e=relXY(el,dx,dy), ex=e[0], ey=e[1];
            var sx=(p._x!=null?p._x:ex), sy=(p._y!=null?p._y:ey);
            var vx=ex-sx, vy=ey-sy, dist=Math.hypot(vx,vy)||1, bow=Math.min(48,dist*0.22);
            var cx=(sx+ex)/2+(-vy/dist)*bow, cy=(sy+ey)/2+(vx/dist)*bow, N=18, frames=[];
            for(var i=0;i<=N;i++){ var t=i/N; frames.push({transform:"translate("+bez(sx,cx,ex,t)+"px,"+bez(sy,cy,ey,t)+"px)"}); }
            p.style.transition="none"; p.animate(frames,{duration:Math.round(640*PACE), easing:"ease-in-out", fill:"forwards"});
            p._x=ex; p._y=ey; return nap(640);
          }
          async function clickPulse(p){ p.classList.remove("ptr-click"); void p.offsetWidth; p.classList.add("ptr-click"); await nap(260); }
          function fadePtr(p){ p.style.transition="opacity .35s ease"; p.style.opacity="0"; }
          function mkCap(x,y,letter){ var c=document.createElement("span"); c.className="cap cap--raised cap-enter"; c.textContent=letter; c.style.left=x+"px"; c.style.top=y+"px"; host.appendChild(c); return c; }
          async function pressCap(c){ await nap(140); c.classList.add("cap-press"); await nap(150); c.classList.remove("cap-press"); await nap(150); }
          async function leaveCap(c){ c.classList.remove("cap-enter"); void c.offsetWidth; c.classList.add("cap-leave"); await nap(240); c.remove(); }
          var SHQ=[
            { time:"11:30", speaker:"p1", role:"Participant", sentiment:"Satisfaction", q:"Browsing beat searching — it just worked." },
            { time:"04:52", speaker:"p2", role:"Participant", sentiment:"Satisfaction", q:"Honestly, I skimmed straight past this bit." }
          ];
          function fullCard(d){
            return '<blockquote class="quote-card sh-card"><button class="hide-btn" tabindex="-1">'+HIDE_SVG+'</button><button class="star-btn" tabindex="-1">★</button><div class="quote-row">'
              +'<span class="timecode"><span class="timecode-bracket">[</span>'+d.time+'<span class="timecode-bracket">]</span></span>'
              +'<div class="quote-body"><span class="smart-quote">“</span>'+d.q+'<span class="smart-quote">”</span> '
              +'<span class="speaker"><span class="badge">'+d.speaker+'</span><span class="badge">'+d.role+'</span></span>'
              +'<div class="badges"><span class="badge badge-ai badge-satisfaction">'+d.sentiment+'</span><span class="badge badge-add">+</span></div>'
              +'</div></div></blockquote>';
          }
          function shToolbar(n){ return '<div class="sh-toolbar"><button class="bn-hidden-toggle" tabindex="-1">'+n+' hidden <span class="bn-hidden-chevron">⌄</span></button></div>'; }
          async function runStarHide(){
            host.innerHTML=shToolbar(2)+'<div class="sh-stage">'+fullCard(SHQ[0])+fullCard(SHQ[1])+'</div>';
            var cards=host.querySelectorAll(".quote-card"), A=cards[0], B=cards[1], toggle=host.querySelector(".bn-hidden-toggle");
            if(REDUCED){ A.classList.add("starred"); B.classList.add("bn-hidden"); toggle.firstChild.textContent="3 hidden "; return; }
            await settle();
            var p=mkPointer(); setPtr(p, host.clientWidth-24, host.clientHeight-14);
            await nap(340);
            // s : star card A (arc onto the rule → focus+select, key under pointer)
            await glideCurve(p, A, 12, A.offsetHeight*0.5);
            await clickPulse(p); A.classList.add("bn-focused","bn-selected");
            await nap(320);
            var capS=mkCap(p._x-2, p._y+14, "s");
            await pressCap(capS);
            A.classList.remove("bn-focused","bn-selected"); A.classList.add("starred"); A.querySelector(".star-btn").classList.add("pop");
            await leaveCap(capS);
            await nap(1100);
            // h : hide card B, the hidden count ticks up
            await glideCurve(p, B, 12, B.offsetHeight*0.5);
            await clickPulse(p); B.classList.add("bn-focused","bn-selected");
            await nap(320);
            var capH=mkCap(p._x-2, p._y+14, "h");
            await pressCap(capH);
            B.classList.add("bn-hiding"); toggle.firstChild.textContent="3 hidden "; toggle.classList.add("bump");
            await nap(300); B.classList.add("bn-hidden");
            toggle.classList.remove("bump");
            await leaveCap(capH);
            fadePtr(p);
          }
          if(REDUCED){ runStarHide(); } else { setTimeout(runStarHide, LEAD); }   // rest on the opening frame first
        </script>
        </body></html>
        """
    }

    /// Connect an AI agent (study-tools #5) — a faked-up Claude Code session. The
    /// question types in at the terminal prompt, a thinking shimmer runs, the agent
    /// calls the REAL MCP tool (`search_quotes` — the name /mcp/ actually exposes),
    /// the result line lands, and a cited answer streams back. Plays once per turn.
    /// Terminal panel is drawn (no window chrome, no screenshot), theme + palette
    /// aware like the other webview illustrations.
    static func agentChat(dark: Bool, palette: String, reduce: Bool) -> String {
        let kind = WelcomeIllustration.agentChat
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-palette="\(palette)" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          /* Claude Code's own scheme, following the welcome screen's appearance:
             light = ink on terminal white, dark = warm near-black (#262624) with warm
             white text; coral spinner + green tool dot in both. Only the citation uses
             the BN accent — it points back into the report. */
          :root{
            --term-bg:#ffffff; --term-border:#e0ddd4; --term-ink:#1a1a1a; --term-muted:#767676;
            --term-accent:#007aff; --term-tool:#2c7a39; --term-spin:#c96442;
            --bn-font-mono:"SF Mono",ui-monospace,Menlo,monospace;
          }
          html[data-appearance="dark"]{
            --term-bg:#262624; --term-border:#3e3e38; --term-ink:#e8e6e3; --term-muted:#98978f;
            --term-accent:#0a84ff; --term-tool:#4eba65; --term-spin:#d97757;
          }
          html[data-palette="edo"]{
            --term-bg:#fdfbf7; --term-border:#d4c9a8; --term-ink:#1b2230; --term-muted:#4a698a;
            --term-accent:#0f5c9e;
          }
          html[data-palette="edo"][data-appearance="dark"]{
            --term-bg:#1a1816; --term-border:#2d2820; --term-ink:#e8e3d6; --term-muted:#7ba8a0;
            --term-accent:#4d9fe0;
          }
          *{ box-sizing:border-box; }
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ display:flex; align-items:center; }
          /* Full width of the cell, normal flow, left origin (design-welcome-screen §2 —
             no centring, no scale): rows wrap to the width they're given; if the slot
             runs short the panel clips its own bottom (the reserved answer air first). */
          .term{ width:100%; max-height:100%; overflow:hidden;
                 border:1px solid var(--term-border); border-radius:8px; background:var(--term-bg);
                 padding:12px 14px; font-family:var(--bn-font-mono); font-size:12.5px; line-height:1.55;
                 color:var(--term-ink); }
          .row{ white-space:pre-wrap; margin:0 0 4px; min-height:1.55em; }
          .row:last-child{ margin-bottom:0; }
          .ln{ opacity:0; transition:opacity .3s ease; }
          .ln.on{ opacity:1; }
          .pg{ color:var(--term-muted); }
          .done{ color:var(--term-muted); }   /* committed input dims, Claude Code transcript style */
          .spin{ color:var(--term-spin); }
          .tooldot{ color:var(--term-tool); }
          .ansdot{ color:var(--term-ink); }
          .toolname{ color:var(--term-ink); }
          .toolargs{ color:var(--term-muted); }
          .res{ color:var(--term-muted); }
          .ans{ min-height:4.65em; }   /* reserve 3 lines so the streamed answer never grows the panel */
          .cite{ color:var(--term-accent); opacity:0; transition:opacity .35s ease; }
          .cite.on{ opacity:1; }
          .tcaret{ display:inline-block; width:7px; height:1.15em; background:var(--term-ink);
                   margin-left:1px; vertical-align:text-bottom; }
          .tcaret.blink{ animation:tcaret-blink 1s step-end infinite; }
          @keyframes tcaret-blink{ 50%{opacity:0} }
          @media (prefers-reduced-motion:reduce){ *{ animation:none !important; transition:none !important; } }
        </style></head>
        <body>
          <div class="term" id="term">
            <div class="row" id="qrow"><span class="pg">&gt; </span><span id="q"></span><span class="tcaret blink" id="qc"></span></div>
            <div class="row ln" id="tool"></div>
            <div class="row ln res" id="res">  ⎿  Found 6 quotes</div>
            <div class="row ln ans" id="ans"><span class="ansdot">⏺ </span><span id="anstext"></span><span class="cite" id="cite"> [11:30 · p2]</span></div>
          </div>
        <script>
          var REDUCED=document.documentElement.getAttribute("data-reduce")==="1"||matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          function sleep(ms){ return new Promise(function(r){ setTimeout(r, Math.round(ms*PACE)); }); }
          function nap(ms){ return sleep(ms); }   // PACE lives in sleep now; nap kept as the beat verb
          function settle(){ return new Promise(function(r){ requestAnimationFrame(function(){ requestAnimationFrame(r); }); }); }
          function q(id){ return document.getElementById(id); }
          var QUESTION="where did participants struggle in checkout?";
          var TOOLCALL='<span class="tooldot">⏺ </span><span class="toolname">bristlenose · search_quotes</span><span class="toolargs"> (MCP)(query: "checkout")</span>';
          var ANSWER="Checkout is the clearest friction point — six quotes, nearly all frustration: “I couldn’t figure out where to pay.”";
          function fillStill(){
            q("q").textContent=QUESTION; q("qc").remove(); q("qrow").classList.add("done");
            q("tool").innerHTML=TOOLCALL; q("tool").classList.add("on");
            q("res").classList.add("on");
            q("anstext").textContent=ANSWER;
            q("ans").classList.add("on"); q("cite").classList.add("on");
          }
          async function typeQuestion(){
            var el=q("q");
            for(var i=0;i<QUESTION.length;i++){ el.textContent+=QUESTION[i]; await sleep(34); }
            await nap(280);
            q("qc").remove(); q("qrow").classList.add("done");   // enter — the input commits and dims
          }
          async function think(){
            var t=q("tool"), glyphs=["✻","✽","✳","✻"];
            t.innerHTML='<span class="spin" id="sg">✻</span><span class="toolargs"> Thinking…</span>';
            t.classList.add("on");
            for(var i=0;i<glyphs.length;i++){ q("sg").textContent=glyphs[i]; await nap(230); }
          }
          async function streamAnswer(){
            q("ans").classList.add("on");
            var el=q("anstext"), words=ANSWER.split(" ");
            for(var i=0;i<words.length;i++){ el.textContent+=(i?" ":"")+words[i]; await sleep(78); }
            await nap(240);
            q("cite").classList.add("on");
          }
          async function runAgentChat(){
            await settle();
            await typeQuestion();
            await think();
            q("tool").innerHTML=TOOLCALL;      // the shimmer resolves into the real tool call
            await nap(550);
            q("res").classList.add("on");
            await nap(650);
            await streamAnswer();
          }
          if(REDUCED){ fillStill(); } else { setTimeout(runAgentChat, LEAD); }   // rest on the empty prompt first
        </script>
        </body></html>
        """
    }

    static func miro(dark: Bool, reduce: Bool) -> String {
        let kind = WelcomeIllustration.miro
        return """
        <!doctype html><html data-appearance="\(dark ? "dark" : "light")" data-reduce="\(reduce ? "1" : "0")">
        <head><meta charset="utf-8"><style>
          /* Just the stickies — no Miro chrome, no dotted board grid (too distracting;
             the famous colours carry the recognition). Colours sampled from a real
             board capture: the pink and the two yellows. Miro's own face isn't freely
             licensable, so Inter (the report face) leads the stack; the line wrapping
             is hand-set with <br> so the ragged edges stay EXACTLY the board's at any
             font fallback — that sameness is what tricks the eye. Sticky ink stays
             dark in both appearances (paper is paper); only the shadow deepens. */
          html,body{ margin:0; height:100%; overflow:hidden; background:transparent; }
          body{ position:relative; }
          .board{ position:absolute; left:0; top:50%; transform:translateY(-50%); transform-origin:left center;
                  display:flex; align-items:center; gap:6px; }
          .sticky{ display:flex; flex-direction:column; align-items:center; justify-content:center;
                   font-family:"Inter","Open Sans","Helvetica Neue",Arial,sans-serif; color:#1f1f1f;
                   text-align:center; box-shadow:0 3px 7px rgba(0,0,0,.16);
                   opacity:0; transform:translateY(8px) scale(.9);
                   transition:opacity .32s ease, transform .38s cubic-bezier(.2,.85,.3,1.15); }
          html[data-appearance="dark"] .sticky{ box-shadow:0 4px 9px rgba(0,0,0,.4); }
          .sticky.on{ opacity:1; transform:translateY(0) scale(1); }
          .pink{ background:#f3cbe6; width:150px; height:140px; }
          .y1{ background:#fbf5a5; width:142px; height:140px; font-size:12px; line-height:1.32; }
          .y2{ background:#f8efa0; width:138px; height:120px; font-size:12px; line-height:1.32; }
          .pink .t1{ font-size:17px; font-weight:700; }
          .pink .t2{ font-size:14px; margin-top:2px; }
          .attr{ font-style:italic; margin-top:3px; }
          @media (prefers-reduced-motion:reduce){ *{ transition:none !important; } }
        </style></head>
        <body>
          <div class="board" id="board">
            <div class="sticky pink"><div class="t1">Homepage</div><div class="t2">2 quote(s)</div></div>
            <div class="sticky y1">“I’ve got these…<br>categorizations<br>that I can go to<br>but… that’s<br>probably…<br>quite busy.<br><span class="attr">— P1 · 8:27</span></div>
            <div class="sticky y2">“The obvious<br>thing to pick<br>here is<br>kitchenware<br>and tableware.”<br><span class="attr">— P1 · 9:10</span></div>
          </div>
        <script>
          var R=document.documentElement.getAttribute("data-reduce")==="1"||matchMedia("(prefers-reduced-motion:reduce)").matches;
          var PACE=\(WelcomeTempo.jsStretch(for: kind)), LEAD=\(WelcomeTempo.jsLeadMs);
          var S=[].slice.call(document.querySelectorAll(".sticky"));
          function fit(){
            var b=document.getElementById("board");
            var s=Math.min((window.innerWidth-2)/b.offsetWidth,(window.innerHeight-4)/b.offsetHeight);
            if(isFinite(s)&&s>0) b.style.transform="translateY(-50%) scale("+s+")";
          }
          requestAnimationFrame(fit);
          window.addEventListener("resize",fit);
          if(R){ S.forEach(function(el){ el.classList.add("on"); }); }
          else{ S.forEach(function(el,i){ setTimeout(function(){ el.classList.add("on"); }, LEAD+Math.round(i*480*PACE)); }); }
        </script>
        </body></html>
        """
    }
}
