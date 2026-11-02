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
        case keyRejected, unreachable, outOfCredit
        var id: String { rawValue }

        /// The existing five-kind vocabulary (`MessageKind`): the glyph says
        /// how bad, the words say what. Nothing invented per condition.
        var kind: MessageKind { self == .keyRejected ? .error : .warning }

        var menuLabel: String {
            switch self {
            case .keyRejected: "Key rejected (error)"
            case .unreachable: "Can't reach (warning)"
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

    @Published var condition: Condition?
    @Published var stage: Stage = .first

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

    private let provider = LLMProvider.claude

    var body: some View {
        if let condition = model.condition {
            let kind = condition.kind
            let loud = model.stage == .first
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
                                .lineLimit(1)
                                .transition(.opacity)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(pillText(condition))
                .popover(isPresented: $showingDetail, arrowEdge: .bottom) {
                    detail(condition)
                }
                if model.stage == .settled {
                    Button {
                        model.hide()
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 8, weight: .bold))
                            .foregroundStyle(.secondary)
                            .frame(width: 14, height: 14)
                            .contentShape(Circle())
                    }
                    .buttonStyle(.plain)
                    .help("Hide")
                    .accessibilityLabel("Hide")
                    .transition(.opacity)
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(Capsule().fill(loud ? kind.tint.opacity(0.14) : Color.secondary.opacity(0.08)))
            .overlay(Capsule().stroke(loud ? kind.tint.opacity(0.7) : Color.secondary.opacity(0.25),
                                      lineWidth: loud ? 1 : 0.5))
            .animation(reduceMotion ? nil : .smooth(duration: 0.25), value: model.stage)
            .help(pillText(condition))
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
        case .unreachable:
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
                Text(i18n.t("desktop.pipeline.failure.auth", ["provider": name]))
                    .font(.system(.callout).weight(.semibold))
            case .unreachable:
                Text(i18n.t("desktop.pipeline.failure.network", ["provider": name]))
                    .font(.system(.callout).weight(.semibold))
            }
            HStack {
                Spacer()
                Button("Hide") {
                    showingDetail = false
                    model.hide()
                }
                if condition != .unreachable {
                    Button(i18n.t("desktop.outOfCredit.switchProvider")) {
                        showingDetail = false
                        SettingsWindow.shared.show(pane: .llm)
                    }
                }
                switch condition {
                case .outOfCredit:
                    Button(i18n.t("desktop.outOfCredit.addFunds")) {
                        showingDetail = false
                        let links = provider.links
                        if let url = links.billing ?? links.console { NSWorkspace.shared.open(url) }
                    }
                    .keyboardShortcut(.defaultAction)
                case .keyRejected:
                    Button("Open Settings…") {
                        showingDetail = false
                        SettingsWindow.shared.show(pane: .llm)
                    }
                    .keyboardShortcut(.defaultAction)
                case .unreachable:
                    EmptyView()
                }
            }
            .padding(.top, 6)
        }
        .fixedSize(horizontal: false, vertical: true)
        .padding(16)
        .frame(width: 300)
    }
}
#endif
