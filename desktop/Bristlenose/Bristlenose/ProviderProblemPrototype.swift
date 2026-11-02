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

    /// Where the hover-revealed × lives. Space is reserved either way, so the
    /// pill never changes size under the pointer (it would shift the glyph and
    /// its neighbours in the centred `.status` zone).
    enum SlotStyle: String, CaseIterable, Identifiable {
        case trailing, symmetric
        var id: String { rawValue }
        var menuLabel: String {
            switch self {
            case .trailing: "× slot on the right only"
            case .symmetric: "× slot, balanced on both sides"
            }
        }
    }

    @Published var condition: Condition?
    @Published var stage: Stage = .first
    @Published var slot: SlotStyle = .trailing

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
    /// Width kept free for the × (a `.mini` bordered circle is about 18 pt).
    private static let dismissSlot: CGFloat = 20

    var body: some View {
        if let condition = model.condition {
            let kind = condition.kind
            let loud = model.stage == .first
            // Collapsed: the bare glyph, no capsule ("less is more"; the HIG says a
            // toolbar symbol needs no border of its own). Nothing is drawn round it,
            // so the target is padded instead (22 × 20), never left at glyph size.
            let collapsed = model.stage == .collapsed
            HStack(spacing: 6) {
                if !collapsed && model.slot == .symmetric {
                    Color.clear.frame(width: Self.dismissSlot, height: 1)
                }
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
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(pillText(condition))
                .accessibilityAction(named: "Hide") { model.hide() }
                .popover(isPresented: $showingDetail, arrowEdge: .bottom) {
                    detail(condition)
                }
                if !collapsed {
                    // Safari's tab ×: there on any mouseover into the pill, and on
                    // keyboard focus (never hover-only). The slot is always there.
                    let shown = hovering || dismissFocused
                    dismissButton
                        .focused($dismissFocused)
                        .opacity(shown ? 1 : 0)
                        .allowsHitTesting(shown)
                        .frame(width: Self.dismissSlot, height: Self.dismissSlot)
                        .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: shown)
                }
            }
            .padding(.horizontal, collapsed ? 0 : 10)
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
            .animation(reduceMotion ? nil : .smooth(duration: 0.25), value: model.stage)
            .onHover { hovering = $0 }
            .help(pillText(condition))
        }
    }

    // MARK: - Dismiss
    // Mail's "This message is from a mailing list." banner is the first-party
    // precedent: a grey circular × beside the action, a separate target. Stock
    // SwiftUI draws that (`.bordered` + `.circle` border shape, macOS 14+); on 26
    // the button also takes the system's close role. Whether it looks right
    // inside the capsule is exactly what this is here to show.

    @ViewBuilder
    private var dismissButton: some View {
        if #available(macOS 26.0, *) {
            Button(role: .close) { model.hide() } label: { Image(systemName: "xmark") }
                .providerDismissStyle(provider.displayName)
        } else {
            Button { model.hide() } label: { Image(systemName: "xmark") }
                .providerDismissStyle(provider.displayName)
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
