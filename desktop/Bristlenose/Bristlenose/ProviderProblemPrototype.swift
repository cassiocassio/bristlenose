#if DEBUG
import SwiftUI

/// DEBUG-only prototype: one title-bar pill for provider problems (key
/// rejected, can't reach, out of credit), in the `.status` toolbar zone beside
/// the shipped pills. Driven from Diagnostics ▸ Provider problem pill — it
/// reads nothing real. `docs/mockups/provider-problem-surface.html` is the
/// design argument; this exists because toolbar placement, resizing and the
/// Liquid Glass opt-out can only be judged native.
///
/// Throwaway on purpose: English strings where no shipped key exists (the
/// Diagnostics menu is English-only), no tests, no persistence. The shipped
/// `OutOfCreditPill` is untouched and can sit beside it for comparison.
///
/// Singleton, like `WhisperDownloadModel.shared`, so the app's
/// environment-object wiring (a launch crash when one scene misses it) stays
/// as it is.
@MainActor
final class ProviderProblemPrototype: ObservableObject {
    static let shared = ProviderProblemPrototype()

    enum Condition: String, CaseIterable, Identifiable {
        case keyRejected, networkBlocks, providerOutage, outOfCredit
        var id: String { rawValue }

        /// The existing five-kind vocabulary (`MessageKind`): the glyph says
        /// how bad, the words say what. Nothing invented per condition.
        var kind: MessageKind { self == .keyRejected ? .error : .warning }

        var menuLabel: String {
            switch self {
            case .keyRejected: "Key rejected (error)"
            case .networkBlocks: "Network blocks the provider (warning)"
            case .providerOutage: "Provider outage (warning)"
            case .outOfCredit: "Out of credit (warning)"
            }
        }
    }

    /// First sight → settled (✕ offered) → a day later, glyph only.
    enum Stage: String, CaseIterable, Identifiable {
        case first, settled, collapsed
        var id: String { rawValue }

        var menuLabel: String {
            switch self {
            case .first: "1 · First refusal (loud)"
            case .settled: "2 · Settled (✕)"
            case .collapsed: "3 · A day later (glyph only)"
            }
        }
    }

    /// How much room the pill keeps for the hover-revealed ×. The × overlays the
    /// pill's trailing end and the end of the text fades out beneath it, so the
    /// pill never changes size under the pointer (it would shift the glyph and
    /// its neighbours in the centred `.status` zone). Less room = a neater pill
    /// at rest and more of the text faded when the × shows.
    enum SlotStyle: String, CaseIterable, Identifiable {
        case none, half, full
        var id: String { rawValue }
        var points: CGFloat {
            switch self {
            case .none: 0
            case .half: 6
            case .full: 14
            }
        }
        var menuLabel: String {
            switch self {
            case .none: "Reserve no room for ×"
            case .half: "Reserve half the room for ×"
            case .full: "Reserve the full room for ×"
            }
        }
    }

    /// Two looks for the ×, to compare natively.
    enum DismissStyle: String, CaseIterable, Identifiable {
        case plain, disc
        var id: String { rawValue }
        var menuLabel: String {
            switch self {
            case .plain: "× like Safari’s tabs (small, bare)"
            case .disc: "× like Mail’s banner (grey disc)"
            }
        }
    }

    @Published var condition: Condition?
    @Published var stage: Stage = .first
    @Published var slot: SlotStyle = .half
    @Published var dismissStyle: DismissStyle = .plain

    /// `BRISTLENOSE_DEBUG_PROVIDER_PILL=outOfCredit` or `keyRejected:collapsed`.
    private init() {
        guard let raw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEBUG_PROVIDER_PILL"],
              !raw.isEmpty else { return }
        let parts = raw.split(separator: ":").map(String.init)
        condition = Condition(rawValue: parts[0])
        if parts.count > 1, let s = Stage(rawValue: parts[1]) { stage = s }
    }

    func hide() { condition = nil }
}

/// The pill. Same envelope as `StatusPill` (secondary 0.08 fill, 0.25 hairline,
/// 10 × 4 padding, caption-medium text) but built here, because `StatusPill`
/// is one `Button` and the ✕ has to be its own hit target.
struct ProviderProblemPill: View {
    @ObservedObject var model: ProviderProblemPrototype
    @EnvironmentObject var i18n: I18n
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var showingDetail = false
    @State private var hovering = false
    @FocusState private var dismissFocused: Bool

    private let provider = LLMProvider.claude
    /// The × target is 20 pt with an 18 pt hover circle. Inset 1 pt, the circle's
    /// centre is 11 pt from the edge: concentric with the capsule's rounded end
    /// (a 22 pt-high pill has an 11 pt cap radius), so the circle sits neatly in it.
    private static let dismissSize: CGFloat = 20
    private static let dismissInset: CGFloat = 1
    /// While the × is showing, the last `clear` points of the label are fully
    /// clear and the `fade` points before them fade out, so the type never touches
    /// the ×. The disc is 18 pt and lands on the end of the text, so it needs more
    /// (tuned from a screenshot, 2 Nov 2026). The bare × is a thin ~9 pt glyph that
    /// starts about where the text ends: a short soft edge is enough, and the word
    /// stays legible ("Claude", not "Claud").
    private var fadeShape: (fade: CGFloat, clear: CGFloat) {
        model.dismissStyle == .disc ? (14, 6) : (8, 0)
    }

    var body: some View {
        if let condition = model.condition {
            let kind = condition.kind
            let loud = model.stage == .first
            // Collapsed: the bare glyph, no capsule ("less is more"; the HIG says a
            // toolbar symbol needs no border of its own). Nothing is drawn round it,
            // so the target is padded instead (22 × 20), never left at glyph size.
            let collapsed = model.stage == .collapsed
            // Safari's tab ×: there on any mouseover into the pill, and on keyboard
            // focus (never hover-only).
            let shown = !collapsed && (hovering || dismissFocused)
            HStack(spacing: 6) {
                Button {
                    showingDetail.toggle()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: kind.symbolName)
                            .imageScale(.small)
                            .foregroundStyle(kind.tint)
                        if model.stage != .collapsed {
                            Text(pillText(condition))
                                .font(.system(.caption).weight(.medium))
                                .fixedSize(horizontal: true, vertical: false)
                                .transition(.opacity)
                        }
                    }
                    .frame(minWidth: collapsed ? 22 : nil, minHeight: collapsed ? 20 : nil)
                    .mask { fadeMask(fading: shown && model.slot != .full) }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(pillText(condition))
                .accessibilityAction(named: "Hide") { model.hide() }
                .popover(isPresented: $showingDetail, arrowEdge: .bottom) {
                    detail(condition)
                }
            }
            .padding(.leading, collapsed ? 0 : 10)
            .padding(.trailing, collapsed ? 0 : 10 + model.slot.points)
            .padding(.vertical, collapsed ? 0 : 4)
            .background {
                if !collapsed {
                    Capsule().fill(loud ? kind.tint.opacity(0.14) : Color.secondary.opacity(0.08))
                }
            }
            .overlay {
                if !collapsed {
                    Capsule().stroke(loud ? kind.tint.opacity(0.7) : Color.secondary.opacity(0.25),
                                     lineWidth: loud ? 1 : 0.5)
                }
            }
            .overlay(alignment: .trailing) {
                if !collapsed {
                    dismissButton
                        .focused($dismissFocused)
                        .opacity(shown ? 1 : 0)
                        .allowsHitTesting(shown)
                        .frame(width: Self.dismissSize, height: Self.dismissSize)
                        .padding(.trailing, Self.dismissInset)
                }
            }
            .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: shown)
            .animation(reduceMotion ? nil : .smooth(duration: 0.25), value: model.stage)
            .onHover { hovering = $0 }
            .help(pillText(condition))
        }
    }

    // MARK: - Dismiss

    /// Opaque, except the end of the label fades to clear while
    /// the × is showing, so the × appears to sit over a softened end of the text.
    private func fadeMask(fading: Bool) -> some View {
        HStack(spacing: 0) {
            Rectangle()
            LinearGradient(colors: [.black, fading ? .clear : .black],
                           startPoint: .leading, endPoint: .trailing)
                .frame(width: fadeShape.fade)
            Rectangle()
                .fill(fading ? Color.clear : Color.black)
                .frame(width: fadeShape.clear)
        }
    }
    // Mail's "This message is from a mailing list." banner is the first-party
    // precedent: a grey circular × beside the action, a separate target. Stock
    // SwiftUI draws that (`.bordered` + `.circle` border shape, macOS 14+); on 26
    // the button also takes the system's close role. Whether it looks right
    // inside the capsule is exactly what this is here to show.

    @ViewBuilder
    private var dismissButton: some View {
        switch model.dismissStyle {
        case .plain:
            PlainDismissButton(label: "Hide \(provider.displayName) notice") { model.hide() }
        case .disc:
            if #available(macOS 26.0, *) {
                Button(role: .close) { model.hide() } label: { Image(systemName: "xmark") }
                    .providerDismissStyle(provider.displayName)
            } else {
                Button { model.hide() } label: { Image(systemName: "xmark") }
                    .providerDismissStyle(provider.displayName)
            }
        }
    }

    // MARK: - Words
    // Shipped keys where they exist; the rest are English, because this is the
    // Diagnostics harness. The mockup's string-plan table lists which is which.

    private func pillText(_ condition: ProviderProblemPrototype.Condition) -> String {
        let name = provider.displayName
        switch condition {
        case .outOfCredit:
            return String(format: i18n.t("desktop.outOfCredit.pill"), name)
        case .keyRejected:
            return "\(name) · \(i18n.t("desktop.llmSettings.status.invalid"))"
        case .networkBlocks:
            // The subject is the network, not the provider: we know the internet
            // answers and this provider doesn't (a diagnosis the build must earn
            // with a control probe; here it is forced from the menu).
            return "Network · can’t reach \(name)"
        case .providerOutage:
            return "\(name) · \(i18n.t("desktop.llmSettings.status.unavailable"))"
        }
    }

    private func detail(_ condition: ProviderProblemPrototype.Condition) -> some View {
        let name = provider.displayName
        return VStack(alignment: .leading, spacing: 8) {
            switch condition {
            case .outOfCredit:
                Text(String(format: i18n.t("desktop.outOfCredit.title"), name))
                    .font(.system(.callout).weight(.semibold))
                Text(i18n.t("desktop.outOfCredit.body"))
                    .font(.callout).foregroundStyle(.secondary)
            case .keyRejected:
                // Line 1 the state (shipped), line 2 the remedy (proposed English:
                // the shipped sentences are one key each, so a real build needs
                // title/body pairs like `outOfCredit.title` / `.body`).
                Text(i18n.t("desktop.pipeline.failure.auth", ["provider": name]))
                    .font(.system(.callout).weight(.semibold))
                Text("Add a new key in Settings.")
                    .font(.callout).foregroundStyle(.secondary)
            case .networkBlocks:
                Text("This network can’t reach \(name).")
                    .font(.system(.callout).weight(.semibold))
                Text("Try a different network.")
                    .font(.callout).foregroundStyle(.secondary)
            case .providerOutage:
                // The shipped `pipeline.failure.apiServer` is
                // "{{provider}} is unavailable. Try again shortly." as one line.
                Text("\(name) is unavailable.")
                    .font(.system(.callout).weight(.semibold))
                Text("Try again shortly.")
                    .font(.callout).foregroundStyle(.secondary)
            }
            // One row when the labels fit, a stack when a longer locale does not:
            // buttons never truncate (HIG Typography: "keep text truncation to a
            // minimum"; Layout: adjacent views may need to stack vertically).
            // Measured with ImageRenderer: the three English labels need 317 pt.
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) {
                    Spacer(minLength: 0)
                    actions(condition)
                }
                VStack(alignment: .trailing, spacing: 8) {
                    actions(condition)
                }
            }
            .padding(.top, 6)
        }
        .fixedSize(horizontal: false, vertical: true)
        .padding(16)
        .frame(width: 300)
    }

    /// The popover's buttons, each at its full width. No Hide here: the ✕ in the
    /// pill is the dismiss (a well-known affordance beats a third button). "Switch provider…" is
    /// offered only where it is a different act from the primary one (out of
    /// credit); for a rejected key both would open the same Settings pane.
    @ViewBuilder
    private func actions(_ condition: ProviderProblemPrototype.Condition) -> some View {
        switch condition {
        case .outOfCredit:
            Button(i18n.t("desktop.outOfCredit.switchProvider")) {
                showingDetail = false
                SettingsWindow.shared.show(pane: .llm)
            }
            .fixedSize(horizontal: true, vertical: false)
            Button(i18n.t("desktop.outOfCredit.addFunds")) {
                showingDetail = false
                let links = provider.links
                if let url = links.billing ?? links.console { NSWorkspace.shared.open(url) }
            }
            .keyboardShortcut(.defaultAction)
            .fixedSize(horizontal: true, vertical: false)
        case .keyRejected:
            Button("Open Settings…") {
                showingDetail = false
                SettingsWindow.shared.show(pane: .llm)
            }
            .keyboardShortcut(.defaultAction)
            .fixedSize(horizontal: true, vertical: false)
        case .networkBlocks, .providerOutage:
            EmptyView()
        }
    }
}

/// Safari's tab ×, as seen: a thin grey cross about 9 pt, no disc; a soft circle
/// only under the pointer, and a 20 pt target round a glyph that small.
private struct PlainDismissButton: View {
    let label: String
    let action: () -> Void
    @State private var over = false

    var body: some View {
        Button(action: action) {
            Image(systemName: "xmark")
                .font(.system(size: 9, weight: .semibold))
                .foregroundStyle(over ? Color.primary : Color.secondary)
                .frame(width: 18, height: 18)
                .background(Circle().fill(Color.secondary.opacity(over ? 0.18 : 0)))
                .frame(width: 20, height: 20)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { over = $0 }
        .help("Hide")
        .accessibilityLabel(label)
    }
}

private extension View {
    func providerDismissStyle(_ providerName: String) -> some View {
        self.buttonStyle(.bordered)
            .buttonBorderShape(.circle)
            .controlSize(.mini)
            .help("Hide")
            .accessibilityLabel("Hide \(providerName) notice")
    }
}
#endif
