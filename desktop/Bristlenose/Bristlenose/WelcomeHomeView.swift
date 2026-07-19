import SwiftUI
import AppKit

// MARK: - Welcome home (first-run / .noSelection / ⌘⇧1)
//
// The layout is a FIXED golden (Fibonacci) spiral — architecture, not a
// suggestion. It grows as wide as the content area and keeps its φ proportions
// (height = width / 1.618), pinned to the TOP; the space below is left for
// later. Fonts stay at fixed semantic sizes (no scaling); cell content aligns
// top-leading. It never reflows and cells never resize to their content —
// copy is cut to fit editorially (overflow handling comes later).
//
// Provisional layers (iterate): cell pigments (Edo), copy pools, the delight
// fish, the AI-icon morph, Drop-a-folder .onDrop wiring, aiConfigured binding.
// Type follows the macOS ladder (design-welcome-screen.md §6).

// MARK: Content model

private struct SlotItem: Identifiable {
    let id = UUID()
    let title: String?     // nil for tips
    let text: String       // may contain markdown (**bold**)
    let linkLabel: String
    let href: String
    var image: String? = nil   // imageset name; nil = text-only slot (Science/Tips, art-pending tools)
}

private enum WelcomeContent {
    static let docs = "https://bristlenose.app/docs/"

    // Draft PNG screenshots (light-mode captures) while the set is tuned — see design-welcome-screen.md §Cell 1.
    // image = nil → text-only slot (Ingest + Redact PII art pending). CTA labels are per-tool (doc §Cell 1 pool).
    static let studyTools: [SlotItem] = [
        .init(title: "AutoCode", text: "Let AutoCode propose tags across every quote — you Accept or Deny.", linkLabel: "AI helps tag →", href: docs + "use-codebooks.html", image: "welcome-autocoding"),
        .init(title: "Codebooks", text: "Build a codebook, or start from a ready-made framework.", linkLabel: "Research frameworks →", href: docs + "use-codebooks.html", image: "welcome-codes"),
        .init(title: "Tag", text: "Select one or more quotes, and press `t` to tag them with a code from your codebook.", linkLabel: "Manual tagging →", href: docs + "tag-for-meaning.html", image: "welcome-tag"),
        .init(title: "Star & hide", text: "Press `s` to keep the quotes that matter, `h` to hide the rest.", linkLabel: "Keyboard shortcuts →", href: docs + "keyboard-shortcuts.html", image: "welcome-star"),
        .init(title: "Video clips", text: "Turn selected quotes into video clips.", linkLabel: "Export options →", href: docs + "export-clips.html", image: "welcome-clips"),
        .init(title: "Send to Miro", text: "Send quotes to a Miro board.", linkLabel: "Connect to Miro →", href: docs + "send-to-miro.html", image: "welcome-miro"),
        .init(title: "Ingest", text: "Drop a folder of recordings or transcripts — Bristlenose transcribes, analyses and reports back.", linkLabel: "Import options →", href: docs + "first-analysis.html", image: "welcome-ingest"),
        .init(title: "Redact PII", text: "Remove personal details automatically, before analysis.", linkLabel: "Strip names and more →", href: docs + "redact-pii.html"),
    ]

    static let science: [SlotItem] = [
        .init(title: "Emergent themes", text: "Themes emerge from participants’ own words, not a fixed taxonomy (Braun & Clarke, 2006).", linkLabel: "Learn more →", href: docs + "research-foundations.html"),
        .init(title: "Don Norman", text: "The codebook frameworks draw on Don Norman’s principles of human-centred design.", linkLabel: "Learn more →", href: docs + "codebook-frameworks.html"),
        .init(title: "Jakob Nielsen", text: "The UX codebooks build on Nielsen’s usability heuristics.", linkLabel: "Learn more →", href: docs + "codebook-frameworks.html"),
        .init(title: "Seven sentiments", text: "Seven sentiments, grounded in appraisal theory (Scherer) and core affect (Russell).", linkLabel: "Learn more →", href: docs + "signals.html"),
        .init(title: "Signals", text: "A signal marks where sentiment or tags concentrate more than you’d expect — a measure we coined.", linkLabel: "Learn more →", href: docs + "signals.html"),
        .init(title: "Dignity without distortion", text: "Quotes are tidied but never twisted; the participant’s voice is honoured.", linkLabel: "Learn more →", href: docs + "research-foundations.html"),
    ]

    static let tips: [SlotItem] = [
        .init(title: nil, text: "Already have transcripts? Drop **.vtt**, **.srt** or **.docx** — transcription is skipped.", linkLabel: "More →", href: docs + "supported-files.html"),
        .init(title: nil, text: "No API key? Run **Ollama** locally — free, no account, nothing uploaded.", linkLabel: "More →", href: docs + "set-up-ollama.html"),
        .init(title: nil, text: "Name **p1.srt** next to **p1.mp4** and they merge into one session.", linkLabel: "More →", href: docs + "supported-files.html"),
        .init(title: nil, text: "Press `s` to star, `h` to hide — then filter to what matters.", linkLabel: "More →", href: docs + "keyboard-shortcuts.html"),
        .init(title: nil, text: "Click any transcript timecode to jump the video to that moment.", linkLabel: "More →", href: docs + "run-an-analysis.html"),
    ]

    static let aiConfigured: [SlotItem] = [
        .init(title: "About local models", text: "Ollama runs entirely on your Mac — no account, nothing uploaded.", linkLabel: "More →", href: docs + "set-up-ollama.html"),
        .init(title: "Switch anytime", text: "Change provider or model whenever you like, in Settings.", linkLabel: "More →", href: docs + "configuration.html"),
        .init(title: "Local or cloud", text: "Local models are free; cloud models are faster and sharper.", linkLabel: "More →", href: docs + "cloud-or-local.html"),
    ]

    static let placeholder = SlotItem(title: nil, text: "", linkLabel: "", href: docs)
    static func pick(_ items: [SlotItem]) -> SlotItem { items.randomElement() ?? placeholder }
}

// MARK: - View

struct WelcomeHomeView: View {
    /// TODO: bind to real provider-configured state.
    var aiConfigured: Bool = false
    /// Folders/files dropped on the Drop-a-folder card → create a project.
    var onDropURLs: ([URL]) -> Void = { _ in }

    // Configured-AI card still shows a single per-construction pick (not yet a rotator).
    @State private var aiItem = WelcomeContent.pick(WelcomeContent.aiConfigured)
    @State private var dropTargeted = false

    @Environment(\.openURL) private var openURL

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width - 40                     // 20pt margin each side
            spiral
                .frame(width: w, height: w / 1.618)         // full width, φ proportions
                .padding(20)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)  // pin top; space below
        }
    }

    // Golden spiral: major square first, alternating axis, curling inward.
    private var spiral: some View {
        GoldenSplit(.horizontal) { studyToolsCell } minor: {
            GoldenSplit(.vertical) { scienceCell } minor: {
                GoldenSplit(.horizontal) { tipCell } minor: {
                    GoldenSplit(.vertical) { aiCell } minor: { delightCell }
                }
            }
        }
    }

    // MARK: cells (tints: big → small = 0.03 → 0.26 of the palette accent)

    // Info cells — calm, ignorable; NOT whole-clickable (D3).
    private var studyToolsCell: some View {
        VStack(alignment: .leading, spacing: 8) {
            tag("Study tools")
            SlotRotator(items: WelcomeContent.studyTools, storageKey: "welcome.rotator.tools")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            dropCard
        }
        .welcomeCell(tint: 0.03, large: true)
    }

    private var scienceCell: some View {
        VStack(alignment: .leading, spacing: 8) {
            tag("Scientific background")
            SlotRotator(items: WelcomeContent.science, storageKey: "welcome.rotator.science")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(tint: 0.07, large: true)
    }

    private var tipCell: some View {
        VStack(alignment: .leading, spacing: 6) {
            tag("Tip")
            SlotRotator(items: WelcomeContent.tips, storageKey: "welcome.rotator.tip")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(tint: 0.12)
    }

    // The card is inert; the Setup link is the only target (design-welcome-screen.md §2).
    @ViewBuilder private var aiCell: some View {
        if aiConfigured {
            VStack(alignment: .leading, spacing: 6) { tag("AI"); slotBody(aiItem) }
                .welcomeCell(tint: 0.18)
        } else {
            VStack(alignment: .leading, spacing: 6) {
                tag("AI")
                MorphingAIIcon()
                SettingsLink {
                    Text("Setup →").font(.callout).foregroundStyle(Color.accentColor)
                }
                .buttonStyle(.plain)
                // Deep-link to the LLM tab: set the shared tab key on tap (reactive @AppStorage
                // binding in SettingsView switches even if the window opened on another tab first).
                .simultaneousGesture(TapGesture().onEnded {
                    UserDefaults.standard.set("llm", forKey: "settingsSelectedTab")
                })
            }
            .welcomeCell(tint: 0.18)
        }
    }

    // Action cell — whole card clickable (D3). Placeholder until the swimming fish.
    private var delightCell: some View {
        CardButton(tint: 0.26, action: { openURL(url(WelcomeContent.docs + "privacy.html")) }) {
            Text("Review AI & privacy settings…")
                .font(.body).foregroundStyle(.secondary)
        }
    }

    // MARK: building blocks

    private func tag(_ s: String) -> some View {
        Text(s)
            .font(.subheadline).fontWeight(.medium)
            .textCase(.uppercase).kerning(0.4)
            .foregroundStyle(.secondary)
    }

    private func slotBody(_ item: SlotItem) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if let title = item.title {
                Text(title).font(.title3).fontWeight(.semibold)
            }
            Text(markdown(item.text)).font(.body).foregroundStyle(.secondary)
            if !item.href.isEmpty {
                Link(item.linkLabel, destination: url(item.href))   // discrete control, not inline
                    .font(.callout).padding(.vertical, 2)
            }
        }
    }

    private var dropCard: some View {
        VStack(alignment: .leading, spacing: 3) {
            Image(systemName: dropTargeted ? "tray.and.arrow.down.fill" : "tray.and.arrow.down")
                .font(.system(size: 24, weight: .light))
                .foregroundStyle(dropTargeted ? Color.accentColor : .secondary)
            Text("Drop a folder").font(.title3).fontWeight(.semibold)
            Text("Drag a folder of recordings or transcripts here to add it as a project.")
                .font(.body).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 10)
            .fill(Color(nsColor: .textBackgroundColor))
            .opacity(dropTargeted ? 0.6 : 1))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(dropTargeted ? Color.accentColor : Color(nsColor: .separatorColor),
                              style: StrokeStyle(lineWidth: dropTargeted ? 2 : 1.5, lineCap: .round,
                                                 dash: dropTargeted ? [] : [1, 3]))
        )
        .dropDestination(for: URL.self) { urls, _ in
            onDropURLs(urls)
            return true
        } isTargeted: { dropTargeted = $0 }
    }

    private func markdown(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s)) ?? AttributedString(s)
    }
    private func url(_ s: String) -> URL { URL(string: s) ?? URL(string: "https://bristlenose.app")! }
}

// MARK: - Golden split (major 0.618 first, minor takes the rest)

private struct GoldenSplit<Major: View, Minor: View>: View {
    enum Axis { case horizontal, vertical }
    private let axis: Axis
    private let major: Major
    private let minor: Minor
    private let phi: CGFloat = 0.618
    private let gutter: CGFloat = 8

    init(_ axis: Axis, @ViewBuilder major: () -> Major, @ViewBuilder minor: () -> Minor) {
        self.axis = axis; self.major = major(); self.minor = minor()
    }
    var body: some View {
        GeometryReader { geo in
            switch axis {
            case .horizontal:
                HStack(spacing: gutter) {
                    major.frame(width: (geo.size.width - gutter) * phi); minor
                }
            case .vertical:
                VStack(spacing: gutter) {
                    major.frame(height: (geo.size.height - gutter) * phi); minor
                }
            }
        }
    }
}

// MARK: - Clickable card (whole-cell action, hover highlight)

private struct CardButton<Content: View>: View {
    let tint: Double
    var large: Bool = false
    var alignment: Alignment = .topLeading
    let action: () -> Void
    @ViewBuilder var content: Content
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            content
                .welcomeCell(tint: tint, large: large, alignment: alignment)
                .overlay(
                    RoundedRectangle(cornerRadius: large ? 10 : 8)
                        .fill(Color.primary.opacity(hover ? 0.06 : 0))
                        .allowsHitTesting(false)
                )
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
    }
}

// MARK: - Morphing AI glyph (provisional; guarded for Reduce Motion)

private struct MorphingAIIcon: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let symbols = ["sparkles", "brain", "cpu", "bolt", "cloud"]
    var body: some View {
        Group {
            if reduceMotion {
                Image(systemName: symbols[0])
                    .font(.system(size: 22, weight: .light)).foregroundStyle(.secondary)
            } else {
                TimelineView(.periodic(from: .now, by: 4)) { ctx in
                    let idx = Int(ctx.date.timeIntervalSinceReferenceDate / 4) % symbols.count
                    Image(systemName: symbols[idx])
                        .font(.system(size: 22, weight: .light)).foregroundStyle(.secondary)
                        .transition(.opacity).id(idx)
                        .animation(.easeInOut(duration: 0.8), value: idx)
                }
            }
        }
        .frame(width: 26, height: 26, alignment: .leading)
    }
}

// Markdown → AttributedString, forcing `code` spans (key references, written as
// `t` / `s` / `h`) to a same-size monospaced run so a bare key reads unambiguously
// as a key — the text-only path of docs/design-keycaps.md (lowercase bare keys,
// glyph-safe font, no drawn cap). Drawn caps can't flow mid-sentence in `Text`.
private func welcomeKeyMarkdown(_ s: String) -> AttributedString {
    var attr = (try? AttributedString(markdown: s)) ?? AttributedString(s)
    let codeRanges = attr.runs
        .filter { $0.inlinePresentationIntent?.contains(.code) == true }
        .map(\.range)
    for r in codeRanges { attr[r].font = .system(.body, design: .monospaced).weight(.medium) }
    return attr
}

// MARK: - Slot rotator (manual content carousel, in place)
//
// Content cross-fades in the SAME frame (no card slide, so no edge-peek problem).
// Driven four ways: two-finger swipe, hover-revealed edge chevrons, muted
// page dots (indicator first, hit-slopped fallback target), and arrow keys.
// Next-per-visit: opens one step past where you last left off (persisted).
// No auto-advance. VoiceOver via an adjustable action; reduce-motion → instant.
private struct SlotRotator: View {
    let items: [SlotItem]
    @AppStorage private var lastIndex: Int
    @State private var index = 0
    @State private var started = false
    @State private var hovering = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(items: [SlotItem], storageKey: String) {
        self.items = items
        self._lastIndex = AppStorage(wrappedValue: -1, storageKey)
    }

    private var count: Int { items.count }
    private var revealed: Bool { hovering }   // mouse affordance only; keyboard uses arrow keys

    // Chevron disk size AND dots-row height. Equal by construction — that's what puts the
    // disk and dot centres on one line. Changing one without the other breaks the alignment.
    private static let controlRow: CGFloat = 26

    var body: some View {
        VStack(spacing: 6) {
            slotView(items[min(index, max(0, count - 1))])
                .id(index)
                .transition(.opacity)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            if count > 1 { dots }
        }
        .overlay(alignment: .leading)  { chevron("chevron.left")  { go(index - 1) } }
        .overlay(alignment: .trailing) { chevron("chevron.right") { go(index + 1) } }
        .background(SwipeCatcher { dir in go(index + dir) })
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .focusable()
        .focusEffectDisabled()   // keep keyboard focus (arrow keys), drop the intrusive focus ring
        .onKeyPress(.leftArrow)  { go(index - 1); return .handled }
        .onKeyPress(.rightArrow) { go(index + 1); return .handled }
        .accessibilityElement(children: .contain)
        .accessibilityValue("\(index + 1) of \(count)")
        .accessibilityAdjustableAction { dir in
            switch dir {
            case .increment: go(index + 1)
            case .decrement: go(index - 1)
            @unknown default: break
            }
        }
        .onAppear {
            guard !started else { return }
            started = true
            index = count > 0 ? (lastIndex + 1) % count : 0   // next-per-visit
            lastIndex = index
        }
    }

    private func go(_ n: Int) {
        guard count > 1 else { return }
        let wrapped = ((n % count) + count) % count   // wrap-around; seamless because content cross-fades (no slide to teleport)
        guard wrapped != index else { return }
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { index = wrapped }
        lastIndex = wrapped
    }

    @ViewBuilder private func slotView(_ item: SlotItem) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if let title = item.title {
                Text(title).font(.title3).fontWeight(.semibold)
            }
            Text(welcomeKeyMarkdown(item.text))
                .font(.body).foregroundStyle(.secondary)
            if let name = item.image, let ns = NSImage(named: name) {   // nil-guard = graceful before the PNG lands
                Image(nsImage: ns)
                    .resizable().scaledToFit()
                    // 85% of native size at its own aspect ratio (starting guess); shrinks if the
                    // cell is narrower, never upscales past 85%. ns.size is points (@2x asset → px/2).
                    .frame(maxWidth: ns.size.width * 0.85, maxHeight: ns.size.height * 0.85, alignment: .leading)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))   // faint keyline = illustration, not live UX
                    .accessibilityLabel(Text("\(item.title ?? "") example"))
                    .padding(.vertical, 8)   // one macOS grid square top & bottom
            }
            if !item.href.isEmpty, let url = URL(string: item.href) {
                Link(item.linkLabel, destination: url).font(.callout).padding(.vertical, 2)
            }
        }
    }

    // Tall strip, but the disk sits LOW — bottom-aligned so its centre lands on the dots'
    // centre line (both are `controlRow` tall), keeping the glyph off the body text.
    // The TAP TARGET is the disk only (with slop), NOT the full strip — a full-height
    // leading strip would sit on top of the leading-aligned `Learn →` link and steal its
    // clicks. And the strip is inert unless revealed (pointer over the cell), so an
    // invisible edge column never shadows content.
    private func chevron(_ symbol: String, _ action: @escaping () -> Void) -> some View {
        VStack(spacing: 0) {
            Spacer(minLength: 0)
            // Frosted glass disk so the glyph survives any content underneath with dignity.
            Image(systemName: symbol)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.primary)
                .frame(width: Self.controlRow, height: Self.controlRow)
                .background(.regularMaterial, in: Circle())
                .overlay(Circle().strokeBorder(.primary.opacity(0.08)))      // hairline definition
                .shadow(color: .black.opacity(0.15), radius: 1, y: 0.5)
                .opacity(revealed ? 1 : 0)                                    // disk + glyph fade together
                .frame(width: 30, height: Self.controlRow)                   // hit area = disk band only (dots row level, clear of the link above)
                .contentShape(Rectangle())
                .onTapGesture { action() }
        }
        .frame(width: 30)                                                     // fixed strip width
        .frame(maxHeight: .infinity)                                          // spans height so the disk bottom-aligns
        .allowsHitTesting(revealed)                                          // inert unless revealed → never shadows the link
    }

    // Visible dot 5pt; active ~2× width, muted accent; 17pt hit-slop; indicator-first.
    // Row is `controlRow` tall (not 17) so the dots share a centre line with the chevron disks.
    private var dots: some View {
        HStack(spacing: 0) {
            ForEach(items.indices, id: \.self) { n in
                Capsule()
                    .fill(n == index ? Color.accentColor.opacity(0.6) : Color(nsColor: .separatorColor))
                    .frame(width: n == index ? 10 : 5, height: 5)
                    .frame(width: 17, height: 17)
                    .contentShape(Rectangle())
                    .onTapGesture { go(n) }
            }
        }
        .frame(height: Self.controlRow)
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: index)
    }
}

// Two-finger trackpad / Magic Mouse horizontal swipe → discrete step (one per gesture).
private struct SwipeCatcher: NSViewRepresentable {
    var onSwipe: (Int) -> Void
    func makeNSView(context: Context) -> NSView { CatchView(onSwipe: onSwipe) }
    func updateNSView(_ nsView: NSView, context: Context) { (nsView as? CatchView)?.onSwipe = onSwipe }

    final class CatchView: NSView {
        var onSwipe: (Int) -> Void
        private var lock = false
        init(onSwipe: @escaping (Int) -> Void) { self.onSwipe = onSwipe; super.init(frame: .zero) }
        required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
        override func scrollWheel(with e: NSEvent) {
            guard abs(e.scrollingDeltaX) > abs(e.scrollingDeltaY), abs(e.scrollingDeltaX) > 6 else {
                super.scrollWheel(with: e); return
            }
            guard !lock else { return }
            lock = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { self.lock = false }
            onSwipe(e.scrollingDeltaX < 0 ? 1 : -1)   // swipe content left → next
        }
    }
}

// MARK: - Cell surface (accent-tint over the control background)

private extension View {
    func welcomeCell(tint: Double, large: Bool = false, alignment: Alignment = .topLeading) -> some View {
        modifier(WelcomeCellStyle(tint: tint, large: large, alignment: alignment))
    }
}

/// Cell surface, sourced from the active palette so a Default↔Edo swap updates
/// the grid live. Colours come from the asset-catalog palette tokens (no
/// hardcoded hex): Default = system control surface + blue accent (measured);
/// Edo = warm washi paper + Prussian accent (demonstrative). Colours still to
/// be tuned (per docs/design-welcome-screen.md open decisions).
private struct WelcomeCellStyle: ViewModifier {
    let tint: Double
    var large: Bool = false
    var alignment: Alignment = .topLeading
    @AppStorage("palette") private var palette: String = "default"

    private var isEdo: Bool { palette == "edo" }
    private var accent: Color { Color(isEdo ? "PaletteEdoAccent" : "PaletteDefaultAccent") }
    private var surface: Color { isEdo ? Color("PaletteEdoPaper") : Color(nsColor: .controlBackgroundColor) }

    func body(content: Content) -> some View {
        let r: CGFloat = large ? 10 : 8
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: alignment)
            .padding(large ? 16 : 10)
            .background(
                RoundedRectangle(cornerRadius: r)
                    .fill(surface)
                    .overlay(RoundedRectangle(cornerRadius: r).fill(accent.opacity(tint)))
            )
            .overlay(RoundedRectangle(cornerRadius: r).strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
    }
}

// MARK: - Previews

#Preview("Home · light") {
    WelcomeHomeView().frame(width: 940, height: 600)
}
#Preview("Home · dark") {
    WelcomeHomeView().frame(width: 940, height: 600).preferredColorScheme(.dark)
}
#Preview("Home · wide (fills width, top-pinned)") {
    WelcomeHomeView().frame(width: 1200, height: 760)
}
#Preview("Home · narrow") {
    WelcomeHomeView().frame(width: 560, height: 520)
}
#Preview("Home · AI configured") {
    WelcomeHomeView(aiConfigured: true).frame(width: 940, height: 600)
}
