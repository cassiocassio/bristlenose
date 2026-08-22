import SwiftUI
import AppKit

// MARK: - Welcome home (first-run / .noSelection / ⌘⇧1)
//
// The layout is a FIXED golden (Fibonacci) spiral — architecture, not a
// suggestion. It grows as wide as the content area and keeps its φ proportions
// (height = width / 1.618), pinned to the TOP; the space below is left for
// later. Fonts stay at fixed semantic sizes (no scaling); cell content aligns
// top-leading. It never reflows and cells never resize to their content —
// copy is cut to fit editorially, the looping illustrations self-scale to the
// slot they're handed, and the cell clips as the final backstop.
//
// Provisional layers (iterate): cell pigments (Edo), copy pools, the delight
// fish, the AI-icon morph, Drop-a-folder .onDrop wiring, aiConfigured binding.
// Type follows the macOS ladder (design-welcome-screen.md §6).

// MARK: Content model

private struct SlotItem: Identifiable {
    let id = UUID()
    let title: String?     // nil for tips
    let text: String       // may contain markdown (**bold**); the core sentence, sized to fit even the small cell
    var more: String? = nil    // optional follow-up sentence, shown ONLY when the whole tip fits un-truncated (larger cells)
    let linkLabel: String
    let href: String
    var linkLabel2: String? = nil   // optional second CTA — e.g. Codebooks offers both paths (manual vs framework)
    var href2: String? = nil
    var illustration: WelcomeIllustration = .none   // looping illustration for this slot (WelcomeIllustrations.swift)
    // Where the PRIMARY CTA goes when it should stay in the app — set instead of `href`,
    // which the slot then leaves empty. For a tool whose first step is *setup*, sending the
    // reader to the browser to read about it is a detour; the link should land them on the
    // control. The docs move to the second CTA ("Learn more →") so both routes stay offered.
    var primaryDestination: SlotDestination? = nil
}

/// An in-app destination for a slot's primary CTA.
///
/// Deliberately a plain tag rather than a stored closure: `SettingsWindow` is `@MainActor`,
/// and `WelcomeContent`'s pools are non-isolated `static let`s — so the *call* belongs in the
/// view (same construct as the AI cell's `Setup →`), and the model stays pure data.
private enum SlotDestination {
    case mcpAgentsSettings
}

private enum WelcomeContent {
    static let docs = "https://bristlenose.app/docs/"

    // Every tool slot carries a drawn looping illustration (WelcomeIllustrations.swift);
    // the draft PNG screenshots are gone — the last three (clips, Miro, ingest) converted
    // 14 Aug 2026, completing the "no screenshots long-term" decision recorded in
    // design-welcome-screen.md §Cell 1. CTA labels are per-tool (doc §Cell 1 pool).
    static let studyTools: [SlotItem] = [
        .init(title: "AutoCode", text: "Let AutoCode propose tags across every quote — you Accept or Deny.", linkLabel: "AI helps tag →", href: docs + "use-codebooks.html", illustration: .autocode),
        .init(title: "Codebooks", text: "Build a codebook, or start from a ready-made framework.", linkLabel: "Code by hand →", href: docs + "tag-for-meaning.html", linkLabel2: "Research frameworks →", href2: docs + "codebook-frameworks.html", illustration: .manualTags),
        .init(title: "Tag", text: "Select one or more quotes, and press `t` to tag them with a code from your codebook.", linkLabel: "Manual tagging →", href: docs + "tag-for-meaning.html", illustration: .tag),
        .init(title: "Star & hide", text: "Press `s` to keep the quotes that matter, `h` to hide the rest.", linkLabel: "Keyboard shortcuts →", href: docs + "keyboard-shortcuts.html", illustration: .starHide),
        .init(title: "Video clips", text: "Turn selected quotes into video clips.", linkLabel: "Export options →", href: docs + "export-clips.html", illustration: .clips),
        .init(title: "Send to Miro", text: "Send quotes to a Miro board.", linkLabel: "Connect to Miro →", href: docs + "send-to-miro.html", illustration: .miro),
        // The only slot whose first step is setup, so the primary CTA opens the control
        // (Settings ▸ MCP Agents) rather than a docs page — same destination as the
        // Bristlenose ▸ Connect an Agent… menu item, and the same "…" that says it opens
        // something here. The docs keep their route as the second link.
        .init(title: "Connect an AI agent", text: "Chat to your data from Claude Code, Claude Desktop, or any MCP agent.",
              linkLabel: "Connect an agent…", href: "",
              linkLabel2: "Learn more →", href2: docs + "connect-an-agent.html",
              illustration: .agentChat, primaryDestination: .mcpAgentsSettings),
        .init(title: "Ingest", text: "Drop a folder of recordings or transcripts — Bristlenose transcribes, analyses and reports back.", linkLabel: "Import options →", href: docs + "first-analysis.html", illustration: .ingest),
        // WITHHELD from the desktop pool (2 Aug 2026) — this slot taught a tool the .app cannot run.
        // Presidio + spaCy are in the sidecar spec's `excludes=[]` (desktop/bristlenose-sidecar.spec),
        // `pii_enabled` defaults false and is only settable by the CLI's `--redact-pii`, and no desktop
        // control exists — so the capability is absent from the bundle AND unreachable from the UI.
        // (The Tip cell already skips /docs/redact-pii.html for being CLI-only; this contradicted it.)
        // Kept verbatim as the reference copy: restore this line when PII redaction ships on the Mac.
        // .init(title: "Redact PII", text: "Remove personal details automatically, before analysis.", linkLabel: "Strip names and more →", href: docs + "redact-pii.html"),
    ]

    static let science: [SlotItem] = [
        .init(title: "Emergent themes", text: "Themes emerge from participants’ own words, not a fixed taxonomy (Braun & Clarke, 2006).", linkLabel: "Learn more →", href: docs + "research-foundations.html", illustration: .emergentThemes),
        // One "tip the hat" shelf for all the source books — BookShelfView owns its own author + line + link, synced to the front cover (title/text/href left empty here).
        .init(title: nil, text: "", linkLabel: "", href: "", illustration: .books),
        .init(title: "Seven sentiments", text: "Seven sentiments, grounded in appraisal theory (Scherer) and core affect (Russell).", linkLabel: "Learn more →", href: docs + "signals.html", illustration: .sentimentFan),
        .init(title: "Signals", text: "A signal is a score that combines the strength of participants’ opinions or feelings, their level of focus on an area or theme, and a measure of their agreement.", linkLabel: "Learn more →", href: docs + "signals.html", illustration: .signal),
        .init(title: "Dignity without distortion", text: "Quotes are tidied but never twisted; the participant’s voice is honoured.", linkLabel: "Learn more →", href: docs + "research-foundations.html", illustration: .quote),
    ]

    // An ambient map of the docs. ORDER mirrors the website's sidebar curriculum
    // (bristlenose-website `build.py` NAV → getting-started → obscure), so a first-run
    // user walks the whole help surface one topic per launch, then it goes random
    // (SlotRotator `curriculum`). Each tip: a core sentence that fits the small cell, an
    // optional `more` follow-up shown only when a larger cell fits it whole, and a 1–3
    // word link naming the destination page (label ← page title, follow-up ← page lead).
    // Keep this list in NAV order and update it when the docs nav changes.
    static let tips: [SlotItem] = [
        // Get started
        .init(title: nil, text: "From a folder of recordings to a readable report in minutes.",
              more: "It walks a single run end to end, so you see what each step does.",
              linkLabel: "First analysis →", href: docs + "first-analysis.html"),
        // How-to guides
        .init(title: nil, text: "Connect an AI provider to run the analysis.",
              more: "Claude is the recommended default; ChatGPT, Gemini and Azure work too.",
              linkLabel: "Set up Claude →", href: docs + "set-up-claude.html"),
        .init(title: nil, text: "No API key? Run **Ollama** locally — free, no account, nothing uploaded.",
              more: "The whole analysis runs on your own machine, with no cloud and no key.",
              linkLabel: "Set up Ollama →", href: docs + "set-up-ollama.html"),
        .init(title: nil, text: "Click any transcript timecode to play from that moment.",
              more: "The transcript scrolls in step with the video, so you never lose your place.",
              linkLabel: "Run an analysis →", href: docs + "run-an-analysis.html"),
        .init(title: nil, text: "Send your quotes to a spreadsheet in one step.",
              more: "Copy them to the clipboard, or download as CSV or Excel.",
              linkLabel: "Export quotes →", href: docs + "export-quotes.html"),
        .init(title: nil, text: "Turn your best quotes into shareable video clips.",
              more: "Bristlenose cuts a short clip for each starred or featured quote.",
              linkLabel: "Video clips →", href: docs + "export-clips.html"),
        .init(title: nil, text: "Share one self-contained HTML file — no install needed.",
              more: "Anyone can open it in a browser; anonymise names and places first if you like.",
              linkLabel: "Share a report →", href: docs + "share-report.html"),
        .init(title: nil, text: "Send quotes straight to a **Miro** board.",
              more: "They land as sticky notes, ready to cluster and affinity-map (experimental).",
              linkLabel: "Send to Miro →", href: docs + "send-to-miro.html"),
        .init(title: nil, text: "Ask questions about a project from **Claude Desktop**, or any MCP agent.",
              more: "Turn on agent access, install the extension once, and ask in your own words.",
              linkLabel: "Connect an agent →", href: docs + "connect-an-agent.html"),
        .init(title: nil, text: "Let **AutoCode** propose tags across every quote.",
              more: "Tag by hand, or start from a codebook and accept the model's suggestions.",
              linkLabel: "Codebooks →", href: docs + "use-codebooks.html"),
        .init(title: nil, text: "Tagging is analysis — turn quotes into themes.",
              more: "Group a set of quotes under a code and the findings start to surface.",
              linkLabel: "Tag for meaning →", href: docs + "tag-for-meaning.html"),
        // Understand
        .init(title: nil, text: "Bristlenose reads interviews as sessions and quotes.",
              more: "Sessions, participants, quotes, sections and themes — that's the whole model.",
              linkLabel: "How it works →", href: docs + "how-it-works.html"),
        .init(title: nil, text: "The **Analysis** tab shows where sentiment concentrates.",
              more: "A signal marks a theme running hotter or cooler than you'd expect.",
              linkLabel: "Signals →", href: docs + "signals.html"),
        .init(title: nil, text: "Tag with a ready-made UX research framework.",
              more: "Each framework — Norman, Nielsen and more — brings its own lens.",
              linkLabel: "Frameworks →", href: docs + "codebook-frameworks.html"),
        .init(title: nil, text: "The method rests on published, peer-reviewed research.",
              more: "The sentiment taxonomy, the analysis and the codebooks all cite their sources.",
              linkLabel: "Research foundations →", href: docs + "research-foundations.html"),
        .init(title: nil, text: "Every analysis runs the same twelve stages.",
              more: "Caching means a re-run only redoes what actually changed, keeping the cost down.",
              linkLabel: "The pipeline →", href: docs + "the-pipeline.html"),
        .init(title: nil, text: "Choose what the AI sees: cloud or local.",
              more: "Cloud models are faster and sharper; local ones never leave your Mac.",
              linkLabel: "Cloud or local →", href: docs + "cloud-or-local.html"),
        .init(title: nil, text: "See exactly what the AI sees, and what never leaves your Mac.",
              more: "Recordings and files stay local; only transcript text goes to your provider.",
              linkLabel: "Privacy →", href: docs + "privacy.html"),
        // Reference
        .init(title: nil, text: "Every setting has a sensible default you can change.",
              more: "One reference page lists them all, with what each one does.",
              linkLabel: "Configuration →", href: docs + "configuration.html"),
        .init(title: nil, text: "Press `s` to star, `h` to hide — then filter to what matters.",
              more: "There's a key for nearly everything, in the app and the browser report.",
              linkLabel: "Keyboard shortcuts →", href: docs + "keyboard-shortcuts.html"),
        .init(title: nil, text: "Drop **.srt**, **.vtt** or **.docx** and skip transcription.",
              more: "Bristlenose reads the text you already have and goes straight to analysis.",
              linkLabel: "Supported files →", href: docs + "supported-files.html"),
        .init(title: nil, text: "Name **p1.srt** next to **p1.mp4** to merge them.",
              more: "Matching names pair each transcript with its audio or video automatically.",
              linkLabel: "Matching files →", href: docs + "supported-files.html"),
        .init(title: nil, text: "Everything Bristlenose makes lands in one folder.",
              more: "The report, transcripts and data sit beside your recordings — yours to keep.",
              linkLabel: "Output files →", href: docs + "output-files.html"),
        .init(title: nil, text: "Make it yours: light, dark, palette and type.",
              more: "Switch the colour palette and typography to taste in Settings.",
              linkLabel: "Appearance →", href: docs + "appearance.html"),
        .init(title: nil, text: "Not in English? Switch the interface language.",
              more: "Bristlenose ships in more than twenty languages — set yours in Settings.",
              linkLabel: "Languages →", href: docs + "languages.html"),
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
    // Restored 21 Aug 2026. The bento rewrite (`a310bca6`) replaced three
    // `i18n.t("desktop.welcome.…")` call sites with the same English verbatim,
    // so the keys stayed translated in all 21 locales while the view stopped
    // reading them. Nothing could report it: `check-locales.py` diffs key sets,
    // and the keys were never missing.
    @EnvironmentObject var i18n: I18n

    /// TODO: bind to real provider-configured state.
    var aiConfigured: Bool = false
    /// Folders/files dropped on the Drop-a-folder card → create a project.
    var onDropURLs: ([URL]) -> Void = { _ in }

    // Configured-AI card still shows a single per-construction pick (not yet a rotator).
    @State private var aiItem = WelcomeContent.pick(WelcomeContent.aiConfigured)
    @State private var dropTargeted = false

    // Only one cell animates at a time; the baton travels the golden spiral.
    @StateObject private var baton = WelcomeBaton()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.openURL) private var openURL

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width - 40                     // 20pt margin each side
            spiral
                .frame(width: w, height: w / 1.618)         // full width, φ proportions
                .padding(20)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)  // pin top; space below
                .task { baton.setReduceMotion(reduceMotion) }               // start the baton (off under reduce-motion)
                .onChange(of: reduceMotion) { _, new in baton.setReduceMotion(new) }
                .onDisappear { baton.stop() }
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

    // MARK: cells (tints resolve per cell via WelcomeCellTint — v1 ramp by default,
    // the flagged Whisper-reversed candidate under BristlenoseWelcomeTintCandidate)

    // Info cells — calm, ignorable; NOT whole-clickable (D3).
    private var studyToolsCell: some View {
        VStack(alignment: .leading, spacing: 8) {
            tag("Study tools")
            SlotRotator(items: WelcomeContent.studyTools, storageKey: "welcome.rotator.tools",
                        onCurrent: { item in
                            baton.report(.studyTools, wants: item.illustration != .none, turn: item.illustration.welcomeTurn)
                        })
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            dropCard
        }
        .welcomeCell(.studyTools, large: true)
        .environment(\.welcomeAnimationActive, baton.isActive(.studyTools))
    }

    private var scienceCell: some View {
        VStack(alignment: .leading, spacing: 8) {
            tag("Scientific background")
            SlotRotator(items: WelcomeContent.science, storageKey: "welcome.rotator.science",
                        onCurrent: { item in
                            baton.report(.science, wants: item.illustration != .none, turn: item.illustration.welcomeTurn)
                        })
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(.science, large: true)
        .environment(\.welcomeAnimationActive, baton.isActive(.science))
    }

    private var tipCell: some View {
        VStack(alignment: .leading, spacing: 6) {
            tag("Tip")
            SlotRotator(items: WelcomeContent.tips, storageKey: "welcome.rotator.tip", curriculum: true)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(.tip)
    }

    // The card is inert; the Setup link is the only target (design-welcome-screen.md §2).
    @ViewBuilder private var aiCell: some View {
        if aiConfigured {
            VStack(alignment: .leading, spacing: 6) { tag("AI"); slotBody(aiItem) }
                .welcomeCell(.ai)
        } else {
            VStack(alignment: .leading, spacing: 6) {
                tag("AI")
                MorphingAIIcon()
                // Deep-link straight to the LLM pane. The AppKit Settings
                // window (`SettingsWindow`) opens on the requested pane; no
                // SettingsLink (that's tied to the removed SwiftUI Settings
                // scene) and no shared-tab-key hack.
                Button {
                    SettingsWindow.shared.show(pane: .llm)
                } label: {
                    // The fourth call site `a310bca6` replaced with English
                    // verbatim; the 21 Aug restoration caught the other three.
                    // English stays the noun "Setup" — deliberate, don't
                    // "correct" it to the verb. The other 20 are Apple's own
                    // per-locale verb (`CCS_Localizable.loctable`), which is not
                    // a mismatch: those languages take a verb for a link that
                    // performs the action, and Apple's noun forms there
                    // (ca `Configuració`, fi `Käyttöönotto`) read as section
                    // titles, not as something you click. Part of speech follows
                    // each language's UI convention, not English's.
                    // The arrow stays in code: translators get a clean word, and
                    // a glyph in 21 files is a glyph that goes missing from one.
                    Text(i18n.t("desktop.welcome.aiSetup") + " →")
                        .font(.callout).foregroundStyle(Color.accentColor)
                }
                .buttonStyle(.plain)
            }
            .welcomeCell(.ai)
            .environment(\.welcomeAnimationActive, baton.isActive(.ai))
            .onAppear { baton.report(.ai, wants: true, turn: 8) }
        }
    }

    // Action cell — whole card clickable (D3). Placeholder until the swimming fish.
    private var delightCell: some View {
        CardButton(tint: .delight, action: { openURL(url(WelcomeContent.docs + "privacy.html")) }) {
            Text(i18n.t("desktop.welcome.aiPrivacyLink"))
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
            if let href2 = item.href2, !href2.isEmpty, let label2 = item.linkLabel2 {
                Link(label2, destination: url(href2))   // second path — both routes offered (e.g. manual vs framework)
                    .font(.callout).padding(.vertical, 2)
            }
        }
    }

    private var dropCard: some View {
        VStack(alignment: .leading, spacing: 3) {
            Image(systemName: dropTargeted ? "tray.and.arrow.down.fill" : "tray.and.arrow.down")
                .font(.system(size: 24, weight: .light))
                .foregroundStyle(dropTargeted ? Color.accentColor : .secondary)
            Text(i18n.t("desktop.welcome.dropFolderTitle")).font(.title3).fontWeight(.semibold)
            Text(i18n.t("desktop.welcome.dropFolderHint"))
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
    let tint: WelcomeCellTint
    var large: Bool = false
    var alignment: Alignment = .topLeading
    let action: () -> Void
    @ViewBuilder var content: Content
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            content
                .welcomeCell(tint, large: large, alignment: alignment)
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
    @Environment(\.welcomeAnimationActive) private var active
    private let symbols = ["sparkles", "brain", "cpu", "bolt", "cloud"]
    var body: some View {
        Group {
            if reduceMotion || !active {
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

// Markdown → `Text`, rendering `code` spans (key references, written as `t` /
// `s` / `h`) as a real drawn keycap — Skin A · Flat, the inline-prose default in
// docs/design-keycaps.md §2. This used to emit a bare monospaced run, because a
// cap is a `View` and a `View` cannot flow inside wrapping `Text`; `KeycapInline`
// rasterises the cap once and interpolates it as an image, which flows and wraps
// natively, so the sentence stays a single `Text` and keeps its truncation and
// `ViewThatFits` behaviour. Bold and the rest of the markdown survive because the
// parse still happens first and only the `code` runs are substituted.
@MainActor
private func welcomeKeyText(_ s: String, dark: Bool) -> Text {
    let attr = (try? AttributedString(markdown: s)) ?? AttributedString(s)
    var out = Text(verbatim: "")
    for run in attr.runs {
        let slice = AttributedString(attr[run.range])
        if run.inlinePresentationIntent?.contains(.code) == true,
           let cap = KeycapInline.run(String(slice.characters), dark: dark) {
            out = out + cap
        } else {
            out = out + Text(slice)
        }
    }
    return out
}

// MARK: - Slot rotator (manual content carousel, in place)
//
// Content cross-fades in the SAME frame (no card slide, so no edge-peek problem).
// Driven four ways: two-finger swipe, hover-revealed edge chevrons, muted
// page dots (indicator first, hit-slopped fallback target), and arrow keys.
// Next-per-visit: opens one step past where you last left off (persisted).
// Curriculum mode (Tip cell): the first `count` launches walk the list in order
// (getting-started → obscure), then it goes random — an ambient tour that turns into
// reinforcement once you've seen the whole map. No auto-advance. VoiceOver via an
// adjustable action; reduce-motion → instant.
private struct SlotRotator: View {
    let items: [SlotItem]
    let curriculum: Bool
    let onCurrent: ((SlotItem) -> Void)?   // baton: report the current slot so the cell can want/skip
    @AppStorage private var lastIndex: Int
    @AppStorage private var visits: Int
    @State private var index = 0
    @State private var started = false
    @State private var hovering = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// Caps are rasterised per appearance, so the rotator has to know it.
    @Environment(\.colorScheme) private var scheme

    init(items: [SlotItem], storageKey: String, curriculum: Bool = false, onCurrent: ((SlotItem) -> Void)? = nil) {
        self.items = items
        self.curriculum = curriculum
        self.onCurrent = onCurrent
        self._lastIndex = AppStorage(wrappedValue: -1, storageKey)
        self._visits = AppStorage(wrappedValue: 0, storageKey + ".visits")
    }

    private var count: Int { items.count }
    private var currentItem: SlotItem { items[min(index, max(0, count - 1))] }
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
            index = startIndex()
            visits += 1
            lastIndex = index
            onCurrent?(currentItem)
        }
    }

    // Which slot to open on this visit.
    // • Curriculum, still touring (visits < count): walk the list in order, one per launch.
    // • Curriculum, tour done: random, avoiding an immediate repeat of the last shown.
    // • Non-curriculum (Science/Study cells): unchanged next-per-visit.
    private func startIndex() -> Int {
        guard count > 0 else { return 0 }
        if curriculum {
            if visits < count { return visits }
            if count == 1 { return 0 }
            var pick = Int.random(in: 0..<count)
            if pick == lastIndex { pick = (pick + 1) % count }   // no back-to-back repeat
            return pick
        }
        return (lastIndex + 1) % count   // next-per-visit
    }

    private func go(_ n: Int) {
        guard count > 1 else { return }
        let wrapped = ((n % count) + count) % count   // wrap-around; seamless because content cross-fades (no slide to teleport)
        guard wrapped != index else { return }
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { index = wrapped }
        lastIndex = wrapped
        onCurrent?(items[wrapped])
    }

    @ViewBuilder private func slotView(_ item: SlotItem) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if let title = item.title {
                Text(title).font(.title3).fontWeight(.semibold)
            }
            if let more = item.more {
                // Progressive disclosure inside the fixed cell (never a trim): show
                // the core sentence alone in a small cell, and the whole follow-up
                // sentence ONLY when a larger cell can display all of it un-truncated.
                // ViewThatFits picks the first (richest) candidate that fits vertically.
                ViewThatFits(in: .vertical) {
                    tipBody("\(item.text) \(more)")
                    tipBody(item.text)
                }
            } else if !item.text.isEmpty {
                welcomeKeyText(item.text, dark: scheme == .dark)
                    .font(.body).foregroundStyle(.secondary)
            }
            if item.illustration != .none {
                illustrationView(item.illustration)
                    // Flexible, capped at its natural height: the illustration absorbs the
                    // leftover space in the fixed golden slot and shrinks (self-scaling) when
                    // the cell is short, so the CONTENT bends to the geometry instead of
                    // overflowing it (design-welcome-screen.md — geometry is fixed).
                    // topLeading, not leading: `.leading` centres VERTICALLY, which
                    // was invisible while every illustration filled its box. The book
                    // shelf now sizes to its content, so a centring frame would split
                    // the leftover above and below it and read as a gap under the
                    // caption. Cell content aligns top-leading (§2).
                    .frame(maxWidth: .infinity, maxHeight: illustrationNaturalHeight(item.illustration),
                           alignment: .topLeading)
                    .padding(.vertical, 8)
                    // The books shelf renders real author + line + link → keep it accessible;
                    // the other illustrations are decorative (the title/text carry the meaning).
                    .accessibilityHidden(item.illustration != .books)
            }
            // PRIMARY CTA — an in-app destination when the slot declares one, else a docs URL.
            // Styled to read as the same accent link a `Link` produces (matching the AI cell's
            // `Setup →`); the AppKit Settings window opens on the requested pane directly, so
            // no SettingsLink (tied to the removed SwiftUI Settings scene) and no tab-key hack.
            if let destination = item.primaryDestination {
                Button {
                    switch destination {
                    case .mcpAgentsSettings: SettingsWindow.shared.show(pane: .mcpAgents)
                    }
                } label: {
                    Text(item.linkLabel).font(.callout).foregroundStyle(Color.accentColor)
                }
                .buttonStyle(.plain)
                .padding(.vertical, 2)
            } else if !item.href.isEmpty, let url = URL(string: item.href) {
                Link(item.linkLabel, destination: url).font(.callout).padding(.vertical, 2)
            }
            if let href2 = item.href2, !href2.isEmpty, let label2 = item.linkLabel2,
               let url2 = URL(string: href2) {
                Link(label2, destination: url2).font(.callout).padding(.vertical, 2)
            }
        }
    }

    // One tip-body candidate for `ViewThatFits`. NO `.fixedSize` — that would force the
    // text to demand its full height and ignore the cell bounds, breaking the grid AND
    // ViewThatFits's fit test. Plain Text lets ViewThatFits measure the true wrapped
    // height against the cell's real height and pick the candidate that fits.
    private func tipBody(_ s: String) -> some View {
        welcomeKeyText(s, dark: scheme == .dark)
            .font(.body).foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    // Natural (maximum) height of a science-cell looping illustration. The illustration
    // renders AT this height when the golden slot has room and SHRINKS BELOW it when the
    // slot is short — every illustration self-scales to the frame it's handed (the four
    // webviews fit() themselves, the fan is a GeometryReader, and the book shelf scales
    // ONLY its cover fan (its caption holds fixed type and sheds words instead) via
    // its own GeometryReader), so a smaller frame simply makes them smaller. The height
    // is thus a cap, not a pin — the cell geometry stays fixed and the content bends.
    private func illustrationNaturalHeight(_ kind: WelcomeIllustration) -> CGFloat {
        switch kind {
        case .none:           return 0
        case .quote:          return 112
        case .sentimentFan:   return 128
        case .emergentThemes: return 140
        case .signal:         return 152
        case .autocode:       return 160
        case .manualTags:     return 176
        case .tag:            return 160
        case .starHide:       return 190   // toolbar + two compact cards
        case .agentChat:      return 160   // full-width terminal panel (~155 natural at 12.5px type; clips its reserved answer air first when short)
        case .ingest:         return 196   // five surtitled rows (5×32 + 4×8)
        case .clips:          return 100   // three thumbnail rows; the menu + pointer play out in the same region
        case .miro:           return 148   // sticky row (140) + shadow room
        case .books:          return 252   // caption + covers + link (see BookShelfView.naturalHeight)
        }
    }

    // Science-cell looping illustration (WelcomeIllustrations.swift). NO hard height here
    // — the caller frames it flexibly (maxHeight: illustrationNaturalHeight) so it bends
    // to the fixed slot. Only the current slot is alive (the rotator renders one item),
    // so a webview / shoal exists only while shown.
    @ViewBuilder private func illustrationView(_ kind: WelcomeIllustration) -> some View {
        switch kind {
        case .none:           EmptyView()
        case .sentimentFan:   SentimentFanView()
        case .books:          BookShelfView()   // renders its own author + line + link (synced); self-scales to fit
        case .emergentThemes: EmergentThemesView()
        case .quote:          QuoteIllustrationView()
        case .signal:         SignalIllustrationView()
        case .autocode:       AutoCodeIllustrationView()
        case .manualTags:     ManualTagsIllustrationView()
        case .tag:            TagIllustrationView()
        case .starHide:       StarHideIllustrationView()
        case .agentChat:      AgentChatIllustrationView()
        case .ingest:         IngestIllustrationView()
        case .clips:          ClipsIllustrationView()
        case .miro:           MiroIllustrationView()
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

    // Windowed page indicator. Prior art: iOS "scrolling dots" / UIPageControl with many
    // pages, and the Instagram-style ScrollingPageControl — show at most a window of dots,
    // keep the active one central, slide the window as you move, and SHRINK the outermost
    // dot on any side that still has hidden tips (the shrink is the "there's more that way"
    // cue). The window size is what fits the row, capped for legibility (Apple HIG: more
    // than ~10 dots are hard to count at a glance). The whole list stays reachable via the
    // arrows / swipe / chevrons, and the a11y value announces "n of total".
    // Active ~2× width, muted accent; row is `controlRow` tall so dots share a centre line
    // with the chevron disks.
    private static let dotPitch: CGFloat = 16
    private static let maxDotsCap = 9

    private var dots: some View {
        GeometryReader { geo in
            let fits = max(5, Int((geo.size.width / Self.dotPitch).rounded(.down)))
            let n = min(count, fits, Self.maxDotsCap)
            let windowed = count > n
            // Slide the window so the active dot stays central; clamp at the two ends.
            let start = windowed ? min(max(index - n / 2, 0), count - n) : 0
            HStack(spacing: 0) {
                ForEach(Array(0..<n), id: \.self) { slot in
                    let idx = start + slot
                    let isActive = idx == index
                    let moreBefore = slot == 0 && start > 0
                    let moreAfter = slot == n - 1 && start + n < count
                    let scale: CGFloat = (moreBefore || moreAfter) ? 0.55 : 1
                    Capsule()
                        .fill(isActive ? Color.accentColor.opacity(0.6) : Color(nsColor: .separatorColor))
                        .frame(width: isActive ? 10 : 5, height: 5)
                        .scaleEffect(isActive ? 1 : scale)
                        .frame(width: Self.dotPitch, height: Self.controlRow)
                        .contentShape(Rectangle())
                        .onTapGesture { go(idx) }
                }
            }
            .frame(width: geo.size.width, height: Self.controlRow)   // centre the strip in the row
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: index)
        }
        .frame(height: Self.controlRow)
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

// MARK: - Cell tints (v1 + the flagged candidate)

/// Per-cell accent tint, big → small down the spiral. Carries BOTH colour sets:
/// v1 (the shipping default — 3→26 %, the eye carries the colour) and the
/// working candidate from `docs/mockups/welcome-gradient-playground.html`
/// (Whisper reversed — 11→2 %, colour on the stage, quiet eye; open decision #3
/// in `docs/design-welcome-screen.md` §2). Resolution is the one place the two
/// sets meet; flip via `BristlenoseFlags.welcomeTintCandidate`.
enum WelcomeCellTint {
    case studyTools, science, tip, ai, delight

    /// v1 ramp, shipped since the first fibonacci build.
    var v1: Double {
        switch self {
        case .studyTools: return 0.03
        case .science: return 0.07
        case .tip: return 0.12
        case .ai: return 0.18
        case .delight: return 0.26
        }
    }

    /// Whisper reversed — the playground pick (14 Aug 2026).
    var candidate: Double {
        switch self {
        case .studyTools: return 0.11
        case .science: return 0.08
        case .tip: return 0.06
        case .ai: return 0.04
        case .delight: return 0.02
        }
    }

    func value(candidate on: Bool) -> Double { on ? candidate : v1 }
}

/// Palette accent shared by the cell fills and the candidate pane glow.
private enum WelcomePalette {
    static func accent(edo: Bool) -> Color {
        Color(edo ? "PaletteEdoAccent" : "PaletteDefaultAccent")
    }
}

// MARK: - Cell surface (accent-tint over the control background)

private extension View {
    func welcomeCell(_ tint: WelcomeCellTint, large: Bool = false, alignment: Alignment = .topLeading) -> some View {
        modifier(WelcomeCellStyle(tint: tint, large: large, alignment: alignment))
    }
}

/// Cell surface, opaque, sourced from the active palette so a Default↔Edo swap updates
/// the grid live. Colours come from the asset-catalog palette tokens (no
/// hardcoded hex): Default = system control surface + blue accent (measured);
/// Edo = warm washi paper + Prussian accent (demonstrative). Two colour sets —
/// v1 by default, the Whisper-reversed candidate under
/// `BristlenoseFlags.welcomeTintCandidate` (see `WelcomeCellTint`).
private struct WelcomeCellStyle: ViewModifier {
    let tint: WelcomeCellTint
    var large: Bool = false
    var alignment: Alignment = .topLeading
    @AppStorage("palette") private var palette: String = "default"
    @AppStorage(BristlenoseFlags.welcomeTintCandidateKey) private var candidate = false

    private var isEdo: Bool { palette == "edo" }
    private var accent: Color { WelcomePalette.accent(edo: isEdo) }
    private var surface: Color { isEdo ? Color("PaletteEdoPaper") : Color(nsColor: .controlBackgroundColor) }

    func body(content: Content) -> some View {
        let r: CGFloat = large ? 10 : 8
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: alignment)
            .padding(large ? 16 : 10)
            .background(
                RoundedRectangle(cornerRadius: r)
                    .fill(surface)
                    .overlay(RoundedRectangle(cornerRadius: r)
                        .fill(accent.opacity(tint.value(candidate: candidate))))
            )
            // Backstop for the fixed geometry: content is meant to bend to the slot, but if
            // any ever exceeds it, clip to the cell rather than letting it break the spiral.
            .clipShape(RoundedRectangle(cornerRadius: r))
            .overlay(RoundedRectangle(cornerRadius: r).strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
    }
}

// MARK: - Previews

/// Previews need the same `I18n` the app injects, or SwiftUI traps on the
/// missing environment object. Configure it from disk so the canvas shows real
/// strings rather than raw keys.
@MainActor
private func previewI18n() -> I18n {
    let i18n = I18n()
    if let dir = I18n.findLocalesDirectory() { i18n.configure(localesDirectory: dir) }
    return i18n
}

#Preview("Home · light") {
    WelcomeHomeView().frame(width: 940, height: 600).environmentObject(previewI18n())
}
#Preview("Home · dark") {
    WelcomeHomeView().frame(width: 940, height: 600).preferredColorScheme(.dark)
        .environmentObject(previewI18n())
}
#Preview("Home · wide (fills width, top-pinned)") {
    WelcomeHomeView().frame(width: 1200, height: 760).environmentObject(previewI18n())
}
#Preview("Home · narrow") {
    WelcomeHomeView().frame(width: 560, height: 520).environmentObject(previewI18n())
}
#Preview("Home · AI configured") {
    WelcomeHomeView(aiConfigured: true).frame(width: 940, height: 600)
        .environmentObject(previewI18n())
}
