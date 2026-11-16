import SwiftUI
import AppKit

// MARK: - Welcome home (its own window — WelcomeWindow.swift)
//
// The layout is a FIXED golden (Fibonacci) spiral — architecture, not a
// suggestion. It draws at its natural size (`WelcomeSpiralLayout.naturalWidth`)
// and keeps its φ proportions (height = width / 1.618), pinned to the TOP.
// Narrower than that, it reflows in exactly ONE step (see the layout) rather
// than shrinking. Since Model 2 (design-welcome-screen.md, 3 Oct 2026) it lives
// in its own window and the Drop-a-folder card lives in the main window. Fonts stay at fixed semantic sizes (no scaling); cell content aligns
// top-leading. It never reflows and cells never resize to their content —
// copy is cut to fit editorially, the looping illustrations self-scale to the
// slot they're handed, and the cell clips as the final backstop.
//
// Provisional layers (iterate): cell pigments (Edo), copy pools, the delight
// fish, the AI-icon morph, Drop-a-folder .onDrop wiring, aiConfigured binding.
// Type follows the macOS ladder (design-welcome-screen.md §6).

// MARK: Content model
//
// Slots carry a KEY, never a string. The pools are non-isolated `static let`s
// built before any environment exists, so the text cannot be resolved here —
// `resolve(_:_:)` reads it from `I18n` at render time, which also means a slot
// re-reads itself when the interface language changes mid-session rather than
// freezing whatever was current when the pool was first touched.
//
// The key is a path under `desktop.welcome.home.`; its leaves are `title`,
// `text`, `more`, `link` and `link2`, every one of them optional — an absent
// leaf is how a tip says "no title" or a tool says "no second route". The
// arrow on a CTA stays in code (`cta(_:)`), so translators get a clean word
// and a glyph cannot go missing from one of 21 files.

/// What a slot's words come from.
private enum SlotContent {
    /// A path under `desktop.welcome.home.`, resolved from `I18n` at render time.
    case keyed(String)
    /// A verified item from the news file. Its words are the file's, drawn with
    /// `Text(verbatim:)` only, never through the Markdown path keyed slots use.
    case remote(NewsItem)
    /// No words of its own: the illustration owns its prose (the book shelf).
    case unkeyed
}

private struct SlotItem: Identifiable {
    let content: SlotContent
    let href: String
    var href2: String? = nil
    var illustration: WelcomeIllustration = .none   // looping illustration for this slot (WelcomeIllustrations.swift)
    // Where the PRIMARY CTA goes when it should stay in the app — set instead of `href`,
    // which the slot then leaves empty. For a tool whose first step is *setup*, sending the
    // reader to the browser to read about it is a detour; the link should land them on the
    // control. The docs move to the second CTA ("Learn more →") so both routes stay offered.
    var primaryDestination: SlotDestination? = nil

    /// The pools' shape: a key (or none) plus where its links go.
    init(key: String?, href: String, href2: String? = nil,
         illustration: WelcomeIllustration = .none,
         primaryDestination: SlotDestination? = nil) {
        self.content = key.map(SlotContent.keyed) ?? .unkeyed
        self.href = href
        self.href2 = href2
        self.illustration = illustration
        self.primaryDestination = primaryDestination
    }

    /// A news item as a slide: its own words, its own (allowlisted) link.
    init(news item: NewsItem) {
        self.content = .remote(item)
        self.href = item.href.absoluteString
    }

    /// The path under `desktop.welcome.home.`, for a keyed slot.
    var key: String? {
        if case .keyed(let key) = content { return key }
        return nil
    }

    var news: NewsItem? {
        if case .remote(let item) = content { return item }
        return nil
    }

    /// **Stable across launches**, never `UUID()`: the rotator persists its
    /// place by this id (`SlotRotation`), so a news item arriving at the front
    /// of the list cannot make the reader's place jump. Keyed slots use their
    /// key, a news item its file id, the book shelf its illustration.
    var id: String {
        switch content {
        case .keyed(let key): return "keyed:" + key
        case .remote(let item): return "news:" + item.id
        case .unkeyed: return "illustration:" + String(describing: illustration)
        }
    }
}

/// An in-app destination for a slot's primary CTA.
///
/// Deliberately a plain tag rather than a stored closure: `SettingsWindow` is `@MainActor`,
/// and `WelcomeContent`'s pools are non-isolated `static let`s — so the *call* belongs in the
/// view (same construct as the AI cell's `Setup →`), and the model stays pure data.
private enum SlotDestination {
    case mcpAgentsSettings
}

/// One slot's resolved prose. Every field may be absent; `text` collapses to
/// empty so a caller can test it the way it always could.
private struct ResolvedSlot {
    let title: String?
    let text: String
    let more: String?
    let linkLabel: String
    let linkLabel2: String?
    /// True for a news item: its words are drawn verbatim (`WelcomeSlotProse`).
    var remote = false
}

/// How a slot's sentence is drawn. The decision is here, not in the view, so
/// a test can pin it: **a news item's words are never parsed**, so
/// `[x](https://elsewhere)` in a field shows as typed and cannot become a link
/// (spec §4, field rules). Keyed slots keep the Markdown path, which is how
/// they draw bold and keycaps.
enum WelcomeSlotProse: Equatable {
    case markdown(String)
    case verbatim(String)

    static func of(_ text: String, remote: Bool) -> WelcomeSlotProse {
        remote ? .verbatim(text) : .markdown(text)
    }
}

private extension I18n {
    /// The value for `key`, or nil when the key is absent. `t` returns the key
    /// itself on a miss, which is the signal this turns into an Optional —
    /// so a missing `title` reads as "this slot has no title", not as a
    /// dotted path rendered at `.title3` on the welcome pane.
    @MainActor func optional(_ key: String) -> String? {
        let value = t(key)
        return value == key ? nil : value
    }
}

/// A CTA label plus its arrow. A label that already ends in an ellipsis is
/// opening something *here* (macOS convention) and takes no arrow.
///
/// **Both ellipsis characters count.** Traditional Chinese spells it `\u{22EF}`
/// (midline) where every other language we ship spells it `\u{2026}` — Apple’s own
/// `zh_TW` tables are 982 U+22EF to 5 U+2026, and `zh_HK` 984 to 5, against zero
/// U+22EF in `zh_CN`, `ja` and `ko`. This used to test U+2026 alone, which meant
/// the moment `zh-Hant` was given its correct ellipsis the sniff stopped matching
/// and an in-app control grew a `→` — in one locale, invisibly, since the two
/// characters are indistinguishable in a terminal and a diff. Pinned from the
/// Python side by `tests/test_welcome_locale_keys.py`, which also asserts each
/// locale uses the *right* one of the two.
private func cta(_ label: String) -> String {
    let ellipses: Set<Character> = ["\u{2026}", "\u{22EF}"]
    guard let last = label.last, ellipses.contains(last) else { return label + " \u{2192}" }
    return label
}

/// Resolve a slot. `fallbackLink` is the label for a pool whose slots carry no
/// `link` of their own. The science slots have carried their own since 11 Oct 2026
/// (a link reads on from its headline rather than saying "Learn more"; research in
/// docs/research/link-text.md), so today only the configured-AI cell falls back,
/// to "More →". It is a parameter rather than one global
/// default because a single default silently demotes one of the two pools —
/// which is exactly what happened when this shipped: every science slot quietly
/// went from "Learn more →" to "More →" in all 21 locales.
@MainActor private func resolve(_ item: SlotItem, _ i18n: I18n,
                                fallbackLink: String = "learnMore") -> ResolvedSlot {
    let key: String
    switch item.content {
    case .unkeyed:
        return ResolvedSlot(title: nil, text: "", more: nil, linkLabel: "", linkLabel2: nil)
    case .remote(let news):
        return ResolvedSlot(title: news.title, text: news.text, more: news.more,
                            linkLabel: news.link, linkLabel2: nil, remote: true)
    case .keyed(let k):
        key = k
    }
    let base = "desktop.welcome.home." + key
    return ResolvedSlot(
        title: i18n.optional(base + ".title"),
        text: i18n.optional(base + ".text") ?? "",
        more: i18n.optional(base + ".more"),
        linkLabel: i18n.optional(base + ".link")
            ?? i18n.t("desktop.welcome.home." + fallbackLink),
        linkLabel2: i18n.optional(base + ".link2")
    )
}

private enum WelcomeContent {
    static let docs = "https://bristlenose.app/docs/"

    // Every tool slot carries a drawn looping illustration (WelcomeIllustrations.swift);
    // the draft PNG screenshots are gone — the last three (clips, Miro, ingest) converted
    // 14 Aug 2026, completing the "no screenshots long-term" decision recorded in
    // design-welcome-screen.md §Cell 1. CTA labels are per-tool (doc §Cell 1 pool).
    static let studyTools: [SlotItem] = [
        .init(key: "tools.autocode", href: docs + "use-codebooks.html", illustration: .autocode),
        .init(key: "tools.codebooks", href: docs + "tag-for-meaning.html", href2: docs + "codebook-frameworks.html", illustration: .manualTags),
        .init(key: "tools.tag", href: docs + "tag-for-meaning.html", illustration: .tag),
        .init(key: "tools.starHide", href: docs + "keyboard-shortcuts.html", illustration: .starHide),
        .init(key: "tools.clips", href: docs + "export-clips.html", illustration: .clips),
        // Beside Video clips: the timeline's clip colours are what was on screen.
        // Links to the transcripts page until docs/session-timeline.html publishes (it is
        // written and parked, waiting for its screenshots) — then point it there.
        .init(key: "tools.timeline", href: docs + "read-transcripts.html", illustration: .timeline),
        .init(key: "tools.miro", href: docs + "send-to-miro.html", illustration: .miro),
        // The only slot whose first step is setup, so the primary CTA opens the control
        // (Settings ▸ MCP Agents) rather than a docs page — same destination as the
        // Bristlenose ▸ Connect an Agent… menu item, and the same "…" that says it opens
        // something here. The docs keep their route as the second link.
        .init(key: "tools.agent", href: "", href2: docs + "connect-an-agent.html",
              illustration: .agentChat, primaryDestination: .mcpAgentsSettings),
        .init(key: "tools.ingest", href: docs + "first-analysis.html", illustration: .ingest),
        // WITHHELD from the desktop pool (2 Aug 2026) — this slot taught a tool the .app cannot run.
        // Still withheld, but for ONE of the original two reasons: as of 12 Sep 2026 presidio and
        // spaCy are BUNDLED, not excluded (bristlenose-sidecar.spec's `excludes=[]` says so in its
        // own comment), so the capability is no longer absent from the binary. What is still true is
        // that it is unreachable from the UI: `piiEnabled` is read by PIIModelPack and handed to the
        // sidecar by BristlenoseShared.childEnvironment, but NOTHING WRITES IT — there is no Privacy
        // control — so it is false on every Mac and redaction remains CLI-only (`--redact-pii`).
        // (The Tip cell likewise skips /docs/redact-pii.html for being CLI-only.)
        // Restore this line when a control ships. Verify with `grep -rn 'piiEnabled' Bristlenose/`:
        // a second, WRITING call site is the signal — this comment cannot tell you, it only rots.
        // Its strings are translated and waiting under `tools.redactPii` in all 21 locales.
        // .init(key: "tools.redactPii", href: docs + "redact-pii.html"),
    ]

    // Each link lands on the section that answers it (the docs build's heading ids),
    // so its label can promise that section rather than the whole page. A renamed
    // heading on the website degrades to the top of the page, not a dead link.
    static let science: [SlotItem] = [
        .init(key: "science.emergentThemes", href: docs + "research-foundations.html#the-analysis-method", illustration: .emergentThemes),
        // One "tip the hat" shelf for all the source books — BookShelfView owns its own author + line + link, synced to the front cover (no key here).
        .init(key: nil, href: "", illustration: .books),
        .init(key: "science.sentiments", href: docs + "signals.html#sentiment", illustration: .sentimentFan),
        .init(key: "science.signals", href: docs + "signals.html#how-a-signal-is-measured", illustration: .signal),
        .init(key: "science.dignity", href: docs + "research-foundations.html#the-analysis-method", illustration: .quote),
    ]

    // An ambient map of the docs. ORDER mirrors the website's sidebar curriculum
    // (bristlenose-website `build.py` NAV → getting-started → obscure), so a first-run
    // user walks the whole help surface one topic per launch, then it goes random
    // (SlotRotator `curriculum`). Each tip: a core sentence that fits the small cell, an
    // optional `more` follow-up shown only when a larger cell fits it whole, and a 1–3
    // word link naming the destination page (label ← page title, follow-up ← page lead).
    // Keep this list in NAV order and update it when the docs nav changes — the keys are
    // slugs, not indices, so reordering this list costs no translation.
    static let tips: [SlotItem] = [
        .init(key: "tips.firstAnalysis", href: docs + "first-analysis.html"),
        .init(key: "tips.setUpClaude", href: docs + "set-up-claude.html"),
        .init(key: "tips.setUpOllama", href: docs + "set-up-ollama.html"),
        .init(key: "tips.runAnalysis", href: docs + "run-an-analysis.html"),
        .init(key: "tips.exportQuotes", href: docs + "export-quotes.html"),
        .init(key: "tips.videoClips", href: docs + "export-clips.html"),
        .init(key: "tips.shareReport", href: docs + "share-report.html"),
        .init(key: "tips.sendToMiro", href: docs + "send-to-miro.html"),
        .init(key: "tips.connectAgent", href: docs + "connect-an-agent.html"),
        .init(key: "tips.useCodebooks", href: docs + "use-codebooks.html"),
        .init(key: "tips.tagForMeaning", href: docs + "tag-for-meaning.html"),
        .init(key: "tips.howItWorks", href: docs + "how-it-works.html"),
        .init(key: "tips.signals", href: docs + "signals.html"),
        .init(key: "tips.frameworks", href: docs + "codebook-frameworks.html"),
        .init(key: "tips.researchFoundations", href: docs + "research-foundations.html"),
        .init(key: "tips.thePipeline", href: docs + "the-pipeline.html"),
        .init(key: "tips.cloudOrLocal", href: docs + "cloud-or-local.html"),
        .init(key: "tips.privacy", href: docs + "privacy.html"),
        .init(key: "tips.configuration", href: docs + "configuration.html"),
        .init(key: "tips.keyboardShortcuts", href: docs + "keyboard-shortcuts.html"),
        .init(key: "tips.supportedFiles", href: docs + "supported-files.html"),
        .init(key: "tips.matchingFiles", href: docs + "supported-files.html"),
        .init(key: "tips.outputFiles", href: docs + "output-files.html"),
        .init(key: "tips.appearance", href: docs + "appearance.html"),
        .init(key: "tips.languages", href: docs + "languages.html"),
    ]

    static let aiConfigured: [SlotItem] = [
        .init(key: "aiConfigured.localModels", href: docs + "set-up-ollama.html"),
        .init(key: "aiConfigured.switchAnytime", href: docs + "configuration.html"),
        .init(key: "aiConfigured.localOrCloud", href: docs + "cloud-or-local.html"),
    ]

    static let placeholder = SlotItem(key: nil, href: docs)
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

    /// The Scientific background card's slides: the news items first, then the
    /// drawn science slides. Built ONCE per window from the fetcher's snapshot
    /// (`WelcomeWindowContent`), so a fetch that lands while the window is
    /// open never changes slides under a reader; the new item shows next time.
    @State private var scienceItems: [SlotItem]
    /// The slide the card opens on while a news item is in the file.
    private let scienceLeadID: String?
    /// A news item's link was clicked (`NewsFetcher.recordClick(on:)`).
    private let onNewsLink: (NewsItem) -> Void

    /// The footer checkbox and Settings ▸ Appearance are two views of this one
    /// key. Unticking never closes the window — it governs the next launch.
    @AppStorage(WelcomeWindow.showOnLaunchKey) private var showOnLaunch = true

    // Configured-AI card still shows a single per-construction pick (not yet a rotator).
    @State private var aiItem = WelcomeContent.pick(WelcomeContent.aiConfigured)

    // Only one cell animates at a time; the baton travels the golden spiral.
    @StateObject private var baton = WelcomeBaton()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.openURL) private var openURL

    init(aiConfigured: Bool = false, newsItems: [NewsItem] = [],
         onNewsLink: @escaping (NewsItem) -> Void = { _ in }) {
        self.aiConfigured = aiConfigured
        let news = newsItems.map(SlotItem.init(news:))
        self._scienceItems = State(initialValue: news + WelcomeContent.science)
        self.scienceLeadID = news.first?.id
        self.onNewsLink = onNewsLink
    }

    var body: some View {
        // The arrangement is decided by the WINDOW's width, read outside the scroll
        // view: inside it, a legacy (always-shown) scroller or a window shorter than
        // the spiral takes ~15 pt of width and would flip a full-width window to the
        // stacked arrangement. Width alone decides; height only decides scrolling.
        GeometryReader { geo in
            ScrollView(.vertical) {
                spiral(stacked: WelcomeWindow.stacks(atContentWidth: geo.size.width))
                    .padding(20)
                    .frame(maxWidth: .infinity, alignment: .topLeading)   // pin top
            }
            // At the natural size nothing scrolls and nothing should bounce; only the
            // one-step stack below it is taller than the window.
            .scrollBounceBehavior(.basedOnSize)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) { footer }
        .task { baton.setReduceMotion(reduceMotion) }               // start the baton (off under reduce-motion)
        .onChange(of: reduceMotion) { _, new in baton.setReduceMotion(new) }
        .onDisappear { baton.stop() }
    }

    // Golden spiral: major square first, alternating axis, curling inward. The five
    // cells are FLAT children of one Layout, never nested views, so switching between
    // the spiral and the stacked reflow moves them without rebuilding them — a rebuilt
    // `SlotRotator` would count a fresh visit on every window resize.
    // VoiceOver reads by position unless told otherwise, and the spiral's positions
    // don't run in curriculum order. Higher priority reads first; the footer takes 0.
    private func spiral(stacked: Bool) -> some View {
        WelcomeSpiralLayout(stacked: stacked) {
            studyToolsCell.welcomeReadingOrder(5)
            scienceCell.welcomeReadingOrder(4)
            tipCell.welcomeReadingOrder(3)
            aiCell.welcomeReadingOrder(2)
            delightCell.accessibilitySortPriority(1)   // a Button: stays an element, not a container
        }
        .environment(\.welcomeStacked, stacked)
        .accessibilityElement(children: .contain)   // the cells are siblings here, so the priorities compare
    }

    /// "Show Welcome when Bristlenose opens" — bottom-leading, the Xcode / Pixelmator
    /// Pro place for it. Pinned, so it stays put while the stacked reflow scrolls.
    private var footer: some View {
        Toggle(i18n.t("settings.appearance.welcomeLegend"), isOn: $showOnLaunch)
            .toggleStyle(.checkbox)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 20)
            .padding(.top, 8)
            .padding(.bottom, 16)
            .background(Color(nsColor: .windowBackgroundColor))
            .accessibilitySortPriority(0)
    }

    // MARK: cells (tints resolve per cell via WelcomeCellTint — v1 ramp by default,
    // the flagged Whisper-reversed candidate under BristlenoseWelcomeTintCandidate)

    // Info cells — calm, ignorable; NOT whole-clickable (D3).
    private var studyToolsCell: some View {
        VStack(alignment: .leading, spacing: 8) {
            tag(i18n.t("desktop.welcome.home.tags.studyTools"))
            SlotRotator(items: WelcomeContent.studyTools, storageKey: "welcome.rotator.tools",
                        sizesToTallestWhenStacked: true,
                        onCurrent: { item, userPicked in report(.studyTools, item, userPicked) })
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(.studyTools, large: true)
        .batonCell(.studyTools, baton)
    }

    private var scienceCell: some View {
        ScienceCell(items: scienceItems, leadID: scienceLeadID,
                    storageKey: "welcome.rotator.science", baton: baton,
                    onNewsLink: onNewsLink,
                    onCurrent: { item, userPicked in report(.science, item, userPicked) })
    }

    private var tipCell: some View {
        VStack(alignment: .leading, spacing: 6) {
            tag(i18n.t("desktop.welcome.home.tags.tip"))
            SlotRotator(items: WelcomeContent.tips, storageKey: "welcome.rotator.tip", curriculum: true,
                        onCurrent: { item, userPicked in report(.tip, item, userPicked) })
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(.tip)
        // No tip carries an illustration today, so this cell reports `wants: false` and
        // never takes the baton. It is wired anyway because the environment default is
        // TRUE: an illustration dropped into a cell that sets nothing would free-run
        // forever, ignoring the baton, with nothing to report it.
        .batonCell(.tip, baton)
    }

    /// One place where a rotator's current slot becomes baton state.
    ///
    /// `userPicked` is the researcher having moved the carousel themselves — paging to
    /// a slide IS "show me this one", so the playhead follows them rather than leaving
    /// the new illustration frozen on its still until the spiral comes round.
    private func report(_ slot: WelcomeSlot, _ item: SlotItem, _ userPicked: Bool) {
        baton.report(slot, wants: item.illustration != .none, turn: item.illustration.welcomeTurn)
        if userPicked { baton.claim(slot) }
    }

    // The card is inert; the Setup link is the only target (design-welcome-screen.md §2).
    @ViewBuilder private var aiCell: some View {
        if aiConfigured {
            VStack(alignment: .leading, spacing: 6) { tag(i18n.t("desktop.welcome.home.tags.ai")); slotBody(aiItem) }
                .welcomeCell(.ai)
        } else {
            VStack(alignment: .leading, spacing: 6) {
                tag(i18n.t("desktop.welcome.home.tags.ai"))
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
            .batonCell(.ai, baton)
            .onAppear { baton.report(.ai, wants: true, turn: 8) }
        }
    }

    // Action cell — whole card clickable (D3). Placeholder until the swimming fish.
    private var delightCell: some View {
        CardButton(tint: .delight, action: { openURL(url(WelcomeContent.docs + "privacy.html")) }) {
            Text(i18n.t("desktop.welcome.aiPrivacyLink"))
                .font(.body).foregroundStyle(.secondary)
        }
        // Nothing animates here yet; wired for the same reason as the Tip cell.
        .batonCell(.delight, baton)
    }

    // MARK: building blocks

    private func tag(_ s: String) -> some View { welcomeTag(s) }

    private func slotBody(_ item: SlotItem) -> some View {
        let slot = resolve(item, i18n, fallbackLink: "more")
        return VStack(alignment: .leading, spacing: 3) {
            if let title = slot.title {
                Text(title).font(.title3).fontWeight(.semibold)
            }
            Text(markdown(slot.text)).font(.body).foregroundStyle(.secondary)
            if !item.href.isEmpty {
                Link(cta(slot.linkLabel), destination: url(item.href))   // discrete control, not inline
                    .font(.callout).padding(.vertical, 2)
            }
            if let href2 = item.href2, !href2.isEmpty, let label2 = slot.linkLabel2 {
                Link(cta(label2), destination: url(href2))   // second path — both routes offered (e.g. manual vs framework)
                    .font(.callout).padding(.vertical, 2)
            }
        }
    }

    private func markdown(_ s: String) -> AttributedString {
        (try? AttributedString(markdown: s)) ?? AttributedString(s)
    }
    private func url(_ s: String) -> URL { URL(string: s) ?? URL(string: "https://bristlenose.app")! }
}

/// A cell's eyebrow: small caps, secondary.
private func welcomeTag(_ s: String) -> some View {
    Text(s)
        .font(.subheadline).fontWeight(.medium)
        .textCase(.uppercase).kerning(0.4)
        .foregroundStyle(.secondary)
}

// MARK: - Scientific background cell (and the news slide it can carry)

/// The Scientific background card. Its own view because it holds the one
/// piece of state no other cell has: which kind of slide is showing. The card's
/// tag and tint follow the current slide (owner, 16 Nov 2026): SCIENTIFIC
/// BACKGROUND and the science tint on the drawn slides, the item's tone
/// ("Community", "News") and the tone's colour set on a news slide. Both
/// cross-fade with the slide, instantly under Reduce Motion.
private struct ScienceCell: View {
    @EnvironmentObject var i18n: I18n
    let items: [SlotItem]
    let leadID: String?
    let storageKey: String
    @ObservedObject var baton: WelcomeBaton
    let onNewsLink: (NewsItem) -> Void
    let onCurrent: (SlotItem, Bool) -> Void

    @State private var tone: NewsCheck.Tone?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let eyebrow = WelcomeNewsTone.eyebrowKey(for: tone)
        VStack(alignment: .leading, spacing: 8) {
            welcomeTag(i18n.t(eyebrow))
                .id(eyebrow)
                .transition(.opacity)
                // The rotator's value names the kind ("Community, Office hours,
                // 1 of 6"), so VoiceOver hears the swap; the tag would say it twice.
                .accessibilityHidden(true)
            SlotRotator(items: items, storageKey: storageKey,
                        sizesToTallestWhenStacked: true,
                        leadID: leadID,
                        kind: { item in i18n.t(WelcomeNewsTone.eyebrowKey(for: item.news?.tone)) },
                        onRemoteLink: onNewsLink,
                        onCurrent: { item, userPicked in
                            withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) {
                                tone = item.news?.tone
                            }
                            onCurrent(item, userPicked)
                        })
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .welcomeCell(.science, large: true, tone: tone)
        .batonCell(.science, baton)
    }
}

/// The app-owned look of a news item, by its `tone` (spec §4): the eyebrow's
/// key and the colour set per palette. The file names the tone, never a word
/// or a colour, so an old app can never show a later tone dressed as something
/// else (unknown tones and `alert` never reach the card; `NewsCheck` drops them).
enum WelcomeNewsTone {
    /// The card's tag for a slide: the science tag on a drawn slide (nil tone),
    /// the tone's own eyebrow on a news slide.
    static func eyebrowKey(for tone: NewsCheck.Tone?) -> String {
        switch tone {
        case nil: return "desktop.welcome.home.tags.science"
        case .community?: return "desktop.welcome.home.tags.community"
        // `alert` is reserved and never shown in v1; were it ever to reach
        // here it reads as News, never as something cheerful.
        case .news?, .alert?: return "desktop.welcome.home.tags.news"
        }
    }

    /// The tint colour set, alpha baked in per appearance and with an Increase
    /// Contrast variant (5 %). Contrast (WCAG ratio, AA needs 4.5) of the link
    /// and the secondary body text on the tinted card:
    /// - Default community, light (11 %): link 4.51, body 3.83.
    /// - Default community, dark (18 %): link 4.85, body 5.21.
    /// - Edo community, light (12 %): Prussian link (`PaletteEdoNewsLink`) 5.90.
    /// - Edo, dark (20 %) on `PaletteEdoPaper` dark #3A2E1C, link #A6D1F5 and
    ///   body white at 70 % (`PaletteEdoNewsSecondary`): community (#EB8BA5)
    ///   link 5.75, body 5.50; news (#B9AEDD) link 5.51, body 5.33.
    /// Recompute these when a tint, the paper or a text colour changes.
    static func tintAsset(for tone: NewsCheck.Tone, edo: Bool) -> String {
        let palette = edo ? "PaletteEdo" : "PaletteDefault"
        switch tone {
        case .community: return palette + "Community"
        case .news, .alert: return palette + "News"
        }
    }

    /// The link on a news slide. Default: the system link colour, as every
    /// other slide's `Link` draws. Edo: its own set, because on Edo's dark
    /// paper the system link colour falls below 4.5:1 under a tone tint.
    static func linkColor(edo: Bool) -> Color {
        edo ? Color("PaletteEdoNewsLink") : Color(nsColor: .linkColor)
    }

    /// Secondary text on a news slide: the system's, except Edo dark, which
    /// needs a stronger one to clear 4.5:1 under the tint (`PaletteEdoNewsSecondary`).
    static func secondary(edo: Bool) -> Color {
        edo ? Color("PaletteEdoNewsSecondary") : Color(nsColor: .secondaryLabelColor)
    }
}

// MARK: - Spiral layout (natural size, or one reflow step below it)

/// Lays the five cells out as the golden spiral — Study tools, Scientific
/// background, Tip, AI, Delight; major 0.618 first, alternating axis, curling
/// inward — at its **natural size**, which is also the widest it ever draws.
///
/// Between the natural size and `WelcomeWindow.stackBelowContentWidth` it stays a
/// spiral and narrows with the window. Narrower than that it reflows in exactly
/// **one** step: the outermost split turns
/// from side-by-side to stacked, so Study tools goes on top at the full width and
/// the rest of the spiral sits underneath at its natural height. Nothing inside
/// that block ever moves — the window's minimum width (`minimumWidth`) is the
/// Scientific background cell's natural width, so AI never wraps under Tip — and
/// nothing scales. Reading order (and the baton's) is comic-strip: left to right,
/// then top to bottom, which the cell order already is in both arrangements.
///
/// A `Layout` rather than nested stacks so the cells keep their identity when the
/// arrangement changes (see `WelcomeHomeView.spiral`).
struct WelcomeSpiralLayout: Layout {
    /// The one reflow step, decided by the caller from the window's width (see
    /// `WelcomeHomeView.body` for why not from the proposal).
    var stacked: Bool

    /// The spiral's natural width: 760 pt is where the Scientific background cell is
    /// wide enough for the shelf's 208 pt cover fan to draw at scale 1 with its
    /// caption and link. Derived, not yet measured — the Degradation Lab is the
    /// place to confirm it.
    static let naturalWidth: CGFloat = 760
    static let naturalHeight: CGFloat = naturalWidth / 1.618
    /// The Scientific background cell's natural width — the narrowest the stacked
    /// arrangement may be drawn without the minor block having to move.
    static let minimumWidth: CGFloat = (naturalWidth - gutter) * (1 - phi)

    private static let phi: CGFloat = 0.618
    private static let gutter: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let w = Self.clampedWidth(proposal.width)
        let bottom = arrangement(width: w, subviews: subviews).map(\.maxY).max() ?? 0
        return CGSize(width: w, height: bottom)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let frames = arrangement(width: Self.clampedWidth(bounds.width), subviews: subviews)
        for (subview, frame) in zip(subviews, frames) {
            subview.place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY),
                          anchor: .topLeading, proposal: ProposedViewSize(frame.size))
        }
    }

    private static func clampedWidth(_ proposed: CGFloat?) -> CGFloat {
        min(max(proposed ?? naturalWidth, minimumWidth), naturalWidth)
    }

    /// The frames for this pass. Stacked, Study tools and Scientific background are
    /// as deep as their content asks — their rotators report the tallest slot of their
    /// pool as an ideal height — clamped so a mis-measure can neither collapse a cell
    /// nor run the stack away.
    private func arrangement(width w: CGFloat, subviews: Subviews) -> [CGRect] {
        guard stacked, subviews.count >= 2 else { return Self.frames(width: w, stacked: stacked) }
        func ideal(_ i: Int) -> CGFloat {
            let h = subviews[i].sizeThatFits(ProposedViewSize(width: w, height: nil)).height
            return min(max(h, Self.minimumMeasuredHeight), Self.naturalHeight * 1.5)
        }
        return Self.frames(width: w, stacked: true, studyHeight: ideal(0), scienceHeight: ideal(1))
    }

    /// Floor for a measured cell height — below it the measurement is not believed.
    static let minimumMeasuredHeight: CGFloat = 160

    /// Height of the stacked arrangement at a given width, for given (or estimated)
    /// Study tools and Scientific background heights.
    static func stackedHeight(width w: CGFloat, studyHeight: CGFloat? = nil,
                              scienceHeight: CGFloat? = nil) -> CGFloat {
        frames(width: w, stacked: true, studyHeight: studyHeight, scienceHeight: scienceHeight)
            .map(\.maxY).max() ?? 0
    }

    /// Frames in cell order: Study tools, Scientific background, Tip, AI, Delight.
    /// Stacked, `studyHeight` / `scienceHeight` are the measured content heights;
    /// without them the layout falls back to an estimate (a test, or a cell that has
    /// not reported).
    static func frames(width w: CGFloat, stacked: Bool,
                       studyHeight: CGFloat? = nil, scienceHeight: CGFloat? = nil) -> [CGRect] {
        if !stacked {
            // The spiral keeps φ at any width it is drawn at.
            let h = w / 1.618
            let studyWidth = (w - gutter) * phi
            return [CGRect(x: 0, y: 0, width: studyWidth, height: h)]
                + minorBlock(in: CGRect(x: studyWidth + gutter, y: 0,
                                        width: w - studyWidth - gutter, height: h))
        }
        // Stacked: Study tools on top, then Scientific background, each as deep as
        // its tallest slot (owner decision, 3 Oct 2026); then Tip beside (AI over
        // Delight) at their natural height. The estimate below is only a fallback.
        let study = studyHeight ?? min(naturalHeight, max(minimumWidth, w / 1.618))
        let science = scienceHeight ?? naturalScienceHeight
        let scienceFrame = CGRect(x: 0, y: study + gutter, width: w, height: science)
        return [CGRect(x: 0, y: 0, width: w, height: study), scienceFrame]
            + innerBlock(in: CGRect(x: 0, y: scienceFrame.maxY + gutter,
                                    width: w, height: naturalInnerHeight))
    }

    /// Scientific background's height in the natural spiral.
    static let naturalScienceHeight: CGFloat = (naturalHeight - gutter) * phi
    /// Tip / AI / Delight block's height in the natural spiral.
    static let naturalInnerHeight: CGFloat = naturalHeight - naturalScienceHeight - gutter

    /// Science over (Tip beside (AI over Delight)) — the spiral's inner three splits.
    private static func minorBlock(in r: CGRect) -> [CGRect] {
        let science = CGRect(x: r.minX, y: r.minY, width: r.width, height: (r.height - gutter) * phi)
        let restY = science.maxY + gutter
        return [science] + innerBlock(in: CGRect(x: r.minX, y: restY, width: r.width, height: r.maxY - restY))
    }

    /// Tip beside (AI over Delight).
    private static func innerBlock(in r: CGRect) -> [CGRect] {
        let tip = CGRect(x: r.minX, y: r.minY, width: (r.width - gutter) * phi, height: r.height)
        let x2 = tip.maxX + gutter
        let ai = CGRect(x: x2, y: r.minY, width: r.maxX - x2, height: (r.height - gutter) * phi)
        let delight = CGRect(x: x2, y: ai.maxY + gutter, width: r.maxX - x2, height: r.maxY - ai.maxY - gutter)
        return [tip, ai, delight]
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

/// Join a tip's two sentences.
///
/// A fullwidth stop (`。！？．`) carries about half an em of built-in trailing
/// space, so Japanese and Chinese do not put a space after it — an interpolated
/// `"\(a) \(b)"` leaves a visible gap those scripts never write. The test is the
/// PUNCTUATION, not the script: Korean is head-final too but ends a sentence
/// with an ASCII period and does space normally, so a script check would get it
/// wrong in the other direction.
private func joinSentences(_ head: String, _ tail: String) -> String {
    let fullwidthStops: Set<Character> = ["\u{3002}", "\u{FF01}", "\u{FF1F}", "\u{FF0E}"]
    guard let last = head.last, fullwidthStops.contains(last) else { return head + " " + tail }
    return head + tail
}

// MARK: - Baton wiring for a cell

private extension View {
    /// One cell = one VoiceOver group, placed in the curriculum order by `rank`.
    func welcomeReadingOrder(_ rank: Double) -> some View {
        accessibilityElement(children: .contain).accessibilitySortPriority(rank)
    }

    /// Everything a welcome cell owes the baton: whether it may animate, and how its
    /// illustration says it has played out. One modifier so a new cell cannot wire half
    /// of it — the environment default for `welcomeAnimationActive` is TRUE, so a cell
    /// that sets neither animates forever and reports nothing.
    func batonCell(_ slot: WelcomeSlot, _ baton: WelcomeBaton) -> some View {
        environment(\.welcomeAnimationActive, baton.isActive(slot))
            .environment(\.welcomeTurnDone, WelcomeTurnDone { baton.finish(slot) })
    }
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
/// Which slide a rotator opens on, by **slide id**, never by index alone: a
/// news item inserted at the front of the science card must not move the
/// reader's place in the drawn slides (spec §5, UX review 16 Nov 2026).
enum SlotRotation {
    struct Start: Equatable {
        var index: Int
        /// True when the lead slide won. The caller then leaves the stored
        /// place alone, so the drawn slides carry on where they were.
        var isLead: Bool
    }

    /// - A `leadID` that is present always wins (a news item leads).
    /// - Curriculum (the Tip cell): the first `count` visits walk the list in
    ///   order, one per launch; then random, never the last one shown twice.
    /// - Otherwise next-per-visit: one past the stored slide. An id that is no
    ///   longer in the list (an item that ended) restarts at the first slide.
    ///   With no id stored yet, `legacyIndex` (what the rotator stored before
    ///   ids) stands in, so an upgrade keeps the reader's place.
    /// `random(n)` returns a value in `0..<n`.
    static func start(ids: [String], lastID: String, legacyIndex: Int, visits: Int,
                      curriculum: Bool, leadID: String?, random: (Int) -> Int) -> Start {
        let count = ids.count
        guard count > 0 else { return Start(index: 0, isLead: false) }
        if let leadID, let lead = ids.firstIndex(of: leadID) {
            return Start(index: lead, isLead: true)
        }
        let last: Int = lastID.isEmpty ? legacyIndex : (ids.firstIndex(of: lastID) ?? -1)
        if curriculum {
            if visits < count { return Start(index: visits, isLead: false) }
            if count == 1 { return Start(index: 0, isLead: false) }
            var pick = random(count)
            if pick == last { pick = (pick + 1) % count }   // no back-to-back repeat
            return Start(index: pick, isLead: false)
        }
        let next = (last + 1) % count
        return Start(index: next < 0 ? 0 : next, isLead: false)
    }
}

private struct SlotRotator: View {
    @EnvironmentObject var i18n: I18n
    let items: [SlotItem]
    let curriculum: Bool
    /// In the stacked arrangement, report the TALLEST slot of the pool as this
    /// rotator's height, so the cell is as deep as its content wants and keeps one
    /// height as it pages (see `tallestSlotGhost`). In the spiral the geometry sets
    /// the depth and this does nothing.
    let sizesToTallestWhenStacked: Bool
    @Environment(\.welcomeStacked) private var stacked
    /// Baton: report the current slot, and whether the RESEARCHER put it there.
    /// A first appearance is registration; a chevron, swipe, dot or arrow key is intent.
    let onCurrent: ((SlotItem, Bool) -> Void)?
    /// A slide to open on whenever it is present (a news item), overriding
    /// next-per-visit. See `SlotRotation.start`.
    let leadID: String?
    /// The card's kind for a slide, when the rotator speaks it (the science
    /// card, whose visible tag swaps and is hidden from VoiceOver).
    let kind: ((SlotItem) -> String)?
    /// A news slide's link was clicked.
    let onRemoteLink: ((NewsItem) -> Void)?
    /// Where the reader last was, BY SLIDE ID (`SlotItem.id`), so a slide
    /// inserted at the front never moves them.
    @AppStorage private var lastID: String
    /// The index this rotator stored before it stored ids. Read once, when no
    /// id has been stored yet, so an upgrade keeps the reader's place.
    @AppStorage private var legacyIndex: Int
    @AppStorage private var visits: Int
    @State private var index = 0
    @State private var started = false
    @State private var hovering = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// Caps are rasterised per appearance, so the rotator has to know it.
    @Environment(\.colorScheme) private var scheme
    @Environment(\.openURL) private var openURL
    @AppStorage("palette") private var palette: String = "default"

    init(items: [SlotItem], storageKey: String, curriculum: Bool = false,
         sizesToTallestWhenStacked: Bool = false,
         leadID: String? = nil,
         kind: ((SlotItem) -> String)? = nil,
         onRemoteLink: ((NewsItem) -> Void)? = nil,
         onCurrent: ((SlotItem, Bool) -> Void)? = nil) {
        self.items = items
        self.curriculum = curriculum
        self.sizesToTallestWhenStacked = sizesToTallestWhenStacked
        self.leadID = leadID
        self.kind = kind
        self.onRemoteLink = onRemoteLink
        self.onCurrent = onCurrent
        self._lastID = AppStorage(wrappedValue: "", storageKey + ".id")
        self._legacyIndex = AppStorage(wrappedValue: -1, storageKey)
        self._visits = AppStorage(wrappedValue: 0, storageKey + ".visits")
    }

    private var ids: [String] { items.map(\.id) }

    private var count: Int { items.count }
    private var currentItem: SlotItem { items[min(index, max(0, count - 1))] }
    private var revealed: Bool { hovering }   // mouse affordance only; keyboard uses arrow keys

    // Chevron disk size AND dots-row height. Equal by construction — that's what puts the
    // disk and dot centres on one line. Changing one without the other breaks the alignment.
    private static let controlRow: CGFloat = 26

    var body: some View {
        VStack(spacing: 6) {
            ZStack(alignment: .topLeading) {
                if stacked && sizesToTallestWhenStacked { tallestSlotGhost }
                slotView(items[min(index, max(0, count - 1))])
                    .id(index)
                    .transition(.opacity)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            if count > 1 { dots }
        }
        .overlay(alignment: .leading)  { chevron("chevron.left")  { go(index - 1) } }
        .overlay(alignment: .trailing) { chevron("chevron.right") { go(index + 1) } }
        .background(SwipeCatcher { dir in go(index + dir) })
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        // Focusable the way a BUTTON is (`.activate`), with the system focus ring.
        // Plain `.focusable()` made the rotator a text-field-like focus target, so
        // the Welcome window, opening key, handed it focus at once and a ring sat
        // round Study tools for every mouse user (owner QA, 3 Oct 2026). With
        // `.activate` it is reached by keyboard navigation (Tab under Keyboard
        // navigation / Full Keyboard Access) and shows the ring then — WCAG 2.4.7
        // still holds — and never takes focus on its own. Don't go back to
        // `.focusEffectDisabled()`: that hides the ring from the people who need it.
        .focusable(interactions: .activate)
        .onKeyPress(.leftArrow)  { go(index - 1); return .handled }
        .onKeyPress(.rightArrow) { go(index + 1); return .handled }
        .accessibilityElement(children: .contain)
        .accessibilityValue(accessibilityValue)
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
            let start = SlotRotation.start(ids: ids, lastID: lastID, legacyIndex: legacyIndex,
                                           visits: visits, curriculum: curriculum, leadID: leadID,
                                           random: { Int.random(in: 0..<$0) })
            index = start.index
            visits += 1
            // A lead slide is the file's choice, not the reader's place: keep
            // where they were, so the drawn slides carry on once the item ends.
            if !start.isLead, ids.indices.contains(index) { lastID = ids[index] }
            onCurrent?(currentItem, false)   // registration, not a choice
        }
    }

    /// "Community, Office hours, 1 of 6" where the rotator speaks its kind (the
    /// science card), else the plain "1 of 6".
    private var accessibilityValue: String {
        let n = "\(index + 1)", total = "\(count)"
        guard let kind, count > 0 else {
            return i18n.t("desktop.welcome.home.rotatorPosition", ["n": n, "total": total])
        }
        let kindText = kind(currentItem)
        guard let title = resolve(currentItem, i18n).title else {
            return i18n.t("desktop.welcome.home.rotatorKindPosition",
                          ["kind": kindText, "n": n, "total": total])
        }
        return i18n.t("desktop.welcome.home.rotatorItem",
                      ["kind": kindText, "title": title, "n": n, "total": total])
    }

    private func go(_ n: Int) {
        guard count > 1 else { return }
        let wrapped = ((n % count) + count) % count   // wrap-around; seamless because content cross-fades (no slide to teleport)
        guard wrapped != index else { return }
        withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.22)) { index = wrapped }
        lastID = ids[wrapped]
        onCurrent?(items[wrapped], true)   // every caller of `go` is the researcher
    }

    private var isEdo: Bool { palette == "edo" }

    /// A slot's sentence, drawn as `WelcomeSlotProse` decides.
    private func prose(_ text: String, remote: Bool) -> Text {
        switch WelcomeSlotProse.of(text, remote: remote) {
        case .verbatim(let s): return Text(verbatim: s)
        case .markdown(let s): return welcomeKeyText(s, dark: scheme == .dark)
        }
    }

    /// A news slide's secondary colour (Edo dark needs its own; see `WelcomeNewsTone`).
    private func secondaryStyle(remote: Bool) -> AnyShapeStyle {
        remote ? AnyShapeStyle(WelcomeNewsTone.secondary(edo: isEdo)) : AnyShapeStyle(.secondary)
    }

    @ViewBuilder private func slotView(_ item: SlotItem) -> some View {
        let slot = resolve(item, i18n)
        VStack(alignment: .leading, spacing: 3) {
            if let title = slot.title {
                Text(verbatim: title).font(.title3).fontWeight(.semibold)
            }
            if let more = slot.more {
                // Progressive disclosure inside the fixed cell (never a trim): show
                // the core sentence alone in a small cell, and the whole follow-up
                // sentence ONLY when a larger cell can display all of it un-truncated.
                // ViewThatFits picks the first (richest) candidate that fits vertically.
                ViewThatFits(in: .vertical) {
                    tipBody(joinSentences(slot.text, more), remote: slot.remote)
                    // A news item's core sentence is shown whole, never cut
                    // mid-word (spec §5, "Fitting words"): it takes its own
                    // height, and the cell's clip stays the last backstop.
                    // Measured: German at the smallest cell otherwise ended
                    // in "…" with two lines of room left under the link.
                    tipBody(slot.text, remote: slot.remote)
                        .fixedSize(horizontal: false, vertical: slot.remote)
                }
            } else if !slot.text.isEmpty {
                prose(slot.text, remote: slot.remote)
                    .font(.body).foregroundStyle(secondaryStyle(remote: slot.remote))
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
            if let news = item.news {
                // v1 news has no graphic, so nothing fills the slot's middle: push
                // the link down to where the drawn slides put theirs (under the
                // illustration, just above the dots), as the approved mockup does,
                // rather than leaving it floating under the text with a gap below.
                if item.illustration == .none { Spacer(minLength: 8) }
                // A Button rather than a `Link` so the click is recorded before
                // the browser opens; drawn as a link. The href passed the app's
                // allowlist in `NewsCheck.validateLink`. Words verbatim; the
                // arrow is ours and VoiceOver does not read it.
                Button {
                    onRemoteLink?(news)
                    openURL(news.href)
                } label: {
                    Text(verbatim: cta(news.link)).font(.callout)
                        .foregroundStyle(WelcomeNewsTone.linkColor(edo: isEdo))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text(verbatim: news.link))
                .accessibilityAddTraits(.isLink)
                .accessibilityRemoveTraits(.isButton)
                .padding(.vertical, 2)
            } else if let destination = item.primaryDestination {
                Button {
                    switch destination {
                    case .mcpAgentsSettings: SettingsWindow.shared.show(pane: .mcpAgents)
                    }
                } label: {
                    Text(cta(slot.linkLabel)).font(.callout).foregroundStyle(Color.accentColor)
                }
                .buttonStyle(.plain)
                .padding(.vertical, 2)
            } else if !item.href.isEmpty, let url = URL(string: item.href) {
                Link(cta(slot.linkLabel), destination: url).font(.callout).padding(.vertical, 2)
            }
            if let href2 = item.href2, !href2.isEmpty, let label2 = slot.linkLabel2,
               let url2 = URL(string: href2) {
                Link(cta(label2), destination: url2).font(.callout).padding(.vertical, 2)
            }
        }
    }

    // Every slot of the pool, laid out invisibly at the real width with each
    // illustration as a spacer of its natural height. The ZStack is as tall as the
    // TALLEST slot, which is what the cell reports as its ideal height in the stacked
    // arrangement — so no slot clips, and paging never changes the cell's height
    // (owner decision, 3 Oct 2026: tallest slot, not the current one, which would
    // make the whole stack breathe on every page turn). Text is measured, not
    // counted: wrapping varies by slot, width and locale.
    private var tallestSlotGhost: some View {
        ZStack(alignment: .topLeading) {
            ForEach(items) { item in ghostSlot(item) }
        }
        .hidden()
        .accessibilityHidden(true)
    }

    private func ghostSlot(_ item: SlotItem) -> some View {
        let slot = resolve(item, i18n)
        return VStack(alignment: .leading, spacing: 3) {
            if let title = slot.title {
                Text(verbatim: title).font(.title3).fontWeight(.semibold)
            }
            if let more = slot.more {
                tipBody(joinSentences(slot.text, more), remote: slot.remote)
            } else if !slot.text.isEmpty {
                prose(slot.text, remote: slot.remote).font(.body)
            }
            if item.illustration != .none {
                Color.clear
                    .frame(height: illustrationNaturalHeight(item.illustration))
                    .padding(.vertical, 8)
            }
            if item.primaryDestination != nil || !item.href.isEmpty {
                Text(verbatim: cta(slot.linkLabel)).font(.callout).padding(.vertical, 2)
            }
            if let href2 = item.href2, !href2.isEmpty, let label2 = slot.linkLabel2 {
                Text(cta(label2)).font(.callout).padding(.vertical, 2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .fixedSize(horizontal: false, vertical: true)
    }

    // One tip-body candidate for `ViewThatFits`. NO `.fixedSize` — that would force the
    // text to demand its full height and ignore the cell bounds, breaking the grid AND
    // ViewThatFits's fit test. Plain Text lets ViewThatFits measure the true wrapped
    // height against the cell's real height and pick the candidate that fits.
    private func tipBody(_ s: String, remote: Bool) -> some View {
        prose(s, remote: remote)
            .font(.body).foregroundStyle(secondaryStyle(remote: remote))
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
        case .timeline:       return 240   // row + slice + the open quote (~236 natural); shrinks to the slot
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
        case .timeline:       TimelineIllustrationView()
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
    func welcomeCell(_ tint: WelcomeCellTint, large: Bool = false, alignment: Alignment = .topLeading,
                     tone: NewsCheck.Tone? = nil) -> some View {
        modifier(WelcomeCellStyle(tint: tint, large: large, alignment: alignment, tone: tone))
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
    /// A news slide's tone: its colour set replaces the cell's tint for that
    /// slide only. The set carries its own alpha per appearance and Increase
    /// Contrast (`WelcomeNewsTone.tintAsset`), so no opacity is applied here.
    var tone: NewsCheck.Tone? = nil
    @AppStorage("palette") private var palette: String = "default"
    @AppStorage(BristlenoseFlags.welcomeTintCandidateKey) private var candidate = false

    private var fill: Color {
        if let tone { return Color(WelcomeNewsTone.tintAsset(for: tone, edo: isEdo)) }
        return accent.opacity(tint.value(candidate: candidate))
    }

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
                    .overlay(RoundedRectangle(cornerRadius: r).fill(fill))
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

#if DEBUG
/// The Scientific background card on its own, opening on a news item, at a
/// given size: the real `ScienceCell`, not a copy. For the Degradation Lab's
/// news row and for render probes. Its rotator stores its place under a key of
/// its own, so a preview never moves the real card.
struct WelcomeNewsCardPreview: View {
    let item: NewsItem
    let size: CGSize
    @StateObject private var baton = WelcomeBaton()

    var body: some View {
        let news = SlotItem(news: item)
        ScienceCell(items: [news] + WelcomeContent.science, leadID: news.id,
                    storageKey: "welcome.rotator.newsPreview", baton: baton,
                    onNewsLink: { _ in }, onCurrent: { _, _ in })
            .frame(width: size.width, height: size.height)
    }

    /// The smallest Scientific background cell the spiral draws: the window at
    /// the width below which it stacks (`WelcomeWindow.stackBelowContentWidth`).
    static var smallestCell: CGSize {
        let w = WelcomeWindow.stackBelowContentWidth - 40
        return WelcomeSpiralLayout.frames(width: w, stacked: false)[1].size
    }

    /// Office hours, as the spec's sample file carries it (`en`), and a German
    /// draft for the fit test (a fixture, not a translation to ship).
    static func officeHours(german: Bool = false) -> NewsItem {
        NewsItem(
            id: "office-hours-2026-12-15", tone: .community, locale: german ? "de" : "en",
            title: german ? "Sprechstunde" : "Office hours",
            text: german
                ? "Sprechen Sie mit Martin Storey, dem Autor von Bristlenose, am Dienstag, 15. Dezember, 17.30 bis 18.30 Uhr britischer Zeit."
                : "Drop in with Martin Storey, author of Bristlenose, on Tuesday 15 December, 5.30 to 6.30pm UK time.",
            more: german
                ? "Bringen Sie eine Frage mit, oder etwas, das repariert, verbessert oder ergänzt werden soll."
                : "Bring a question, or something that needs fixing, improving or adding.",
            link: german ? "Zur Sprechstunde" : "Office hours details",
            href: URL(string: "https://bristlenose.app/community/?ref=app-news&id=office-hours-2026-12-15#office-hours")!,
            from: Date(timeIntervalSince1970: 1_765_411_200),
            until: Date(timeIntervalSince1970: 1_765_823_400))
    }
}

#Preview("News card · community · light") {
    WelcomeNewsCardPreview(item: WelcomeNewsCardPreview.officeHours(), size: CGSize(width: 287, height: 285))
        .padding().environmentObject(previewI18n())
}
#Preview("News card · community · dark") {
    WelcomeNewsCardPreview(item: WelcomeNewsCardPreview.officeHours(), size: CGSize(width: 287, height: 285))
        .padding().preferredColorScheme(.dark).environmentObject(previewI18n())
}
#endif

// MARK: - Stacked arrangement flag

private struct WelcomeStackedKey: EnvironmentKey { static let defaultValue = false }

extension EnvironmentValues {
    /// Whether the Welcome spiral is in its stacked arrangement (`WelcomeSpiralLayout`).
    var welcomeStacked: Bool {
        get { self[WelcomeStackedKey.self] }
        set { self[WelcomeStackedKey.self] = newValue }
    }
}
