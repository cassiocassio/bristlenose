import AppKit
import SwiftUI

/// App-global toolbar pill: the active provider is refusing us (key rejected, or
/// out of credit). Sibling to the other `.status` pills, but built here and not
/// on `StatusPill`, because `StatusPill` is one `Button` and this one has a ✕ of
/// its own. The envelope matches (secondary 0.08 fill, 0.25 hairline, 10 × 4
/// padding, caption-medium text), and the item opts out of Liquid Glass's shared
/// background the same way (`withoutSharedBackground()` at the call site).
///
/// **Stages** (`ProviderProblemRules`): a tinted capsule for the first minutes,
/// the plain capsule, then — a day on — the bare glyph with no capsule (a
/// toolbar symbol needs no border of its own). The glyph is the same
/// `MessageKind` glyph at every stage and for every condition of the same kind,
/// so a collapsed pill is recognisably yesterday's: only the words drop away.
///
/// **The ✕** is Safari's tab close: a small bare ×, there on any mouseover into
/// the pill and on keyboard focus (never hover-only), its space half reserved so
/// the pill does not resize under the pointer; the end of the text fades out
/// beneath it while it shows. It hides the notice entirely. VoiceOver has a
/// "Hide" action on the pill itself, so nobody has to find the ✕.
///
/// Measured against the real toolbar in the DEBUG prototype this was ported from
/// (geometry approved 2 Nov 2026): the ✕'s circle is concentric with the
/// capsule's rounded end, and the fade is per-look.
struct ProviderProblemPill: View {
    @ObservedObject var model: ProviderProblemModel
    @EnvironmentObject var i18n: I18n
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorSchemeContrast) private var contrast
    @State private var showingDetail = false
    @State private var hovering = false
    @FocusState private var dismissFocused: Bool

    /// Room kept for the ✕ beyond the capsule's own padding.
    private static let reserve: CGFloat = 6
    private static let dismissSize: CGFloat = 20
    /// Inset 1 pt puts the 18 pt hover circle's centre 11 pt from the edge:
    /// concentric with a 22 pt-high pill's rounded end.
    private static let dismissInset: CGFloat = 1
    /// While the ✕ shows, the end of the label softens (the bare ✕ starts about
    /// where the text ends, so a short edge keeps the whole word legible).
    private static let fadeWidth: CGFloat = 8

    var body: some View {
        if let shown = model.shown {
            let presentation = ProviderProblemPresentation(condition: shown.condition)
            let kind = presentation.kind
            let collapsed = shown.stage == .collapsed
            let loud = shown.stage == .loud
            let showDismiss = !collapsed && (hovering || dismissFocused)
            let providerName = shown.provider.displayName
            ZStack(alignment: .trailing) {
                Button { showingDetail.toggle() } label: {
                    label(kind: kind, presentation: presentation, provider: providerName,
                          collapsed: collapsed, loud: loud, fading: showDismiss)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(title(presentation, provider: providerName))
                .accessibilityValue(i18n.t(presentation.kindWordKey))
                .accessibilityHint(i18n.t("desktop.providerProblem.hint"))
                .accessibilityAction(named: Text(i18n.t("desktop.providerProblem.hideTooltip"))) {
                    model.dismiss()
                }
                .popover(isPresented: $showingDetail, arrowEdge: .bottom) {
                    detail(presentation, provider: shown.provider)
                }
                if !collapsed {
                    PlainDismissButton(
                        label: i18n.t("desktop.providerProblem.hide", ["provider": providerName]),
                        tooltip: i18n.t("desktop.providerProblem.hideTooltip")
                    ) { model.dismiss() }
                        .focused($dismissFocused)
                        .opacity(showDismiss ? 1 : 0)
                        .allowsHitTesting(showDismiss)
                        .frame(width: Self.dismissSize, height: Self.dismissSize)
                        .padding(.trailing, Self.dismissInset)
                }
            }
            .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: showDismiss)
            .animation(reduceMotion ? nil : .smooth(duration: 0.25), value: shown.stage)
            .onHover { hovering = $0 }
            .help(pillText(presentation, provider: providerName))
            // Said once when it appears or changes condition: the "loud once"
            // moment must not be visual only. Not on stage changes, which are
            // cosmetic, and not on clearing.
            .onChange(of: shown.condition) { _, _ in announce(presentation, provider: providerName) }
            .onAppear { announce(presentation, provider: providerName) }
        }
    }

    // MARK: - The capsule

    @ViewBuilder
    private func label(
        kind: MessageKind, presentation: ProviderProblemPresentation, provider: String,
        collapsed: Bool, loud: Bool, fading: Bool
    ) -> some View {
        let increased = contrast == .increased
        HStack(spacing: 6) {
            Image(systemName: kind.symbolName)
                .imageScale(.small)
                .foregroundStyle(kind.tint)
            if !collapsed {
                Text(pillText(presentation, provider: provider))
                    .font(.system(.caption).weight(.medium))
                    .fixedSize(horizontal: true, vertical: false)
                    .transition(.opacity)
            }
        }
        .mask {
            HStack(spacing: 0) {
                Rectangle()
                LinearGradient(colors: [.black, fading ? .clear : .black],
                               startPoint: .leading, endPoint: .trailing)
                    .frame(width: Self.fadeWidth)
            }
        }
        // The padding is inside the button, so the whole capsule is the target;
        // collapsed, nothing is drawn round the glyph, so the target is padded.
        .frame(minWidth: collapsed ? 22 : nil, minHeight: collapsed ? 20 : nil)
        .padding(.leading, collapsed ? 0 : 10)
        .padding(.trailing, collapsed ? 0 : 10 + Self.reserve)
        .padding(.vertical, collapsed ? 0 : 4)
        .background {
            if !collapsed {
                Capsule().fill(loud ? kind.tint.opacity(0.14) : Color.secondary.opacity(0.08))
            }
        }
        .overlay {
            if !collapsed {
                Capsule().stroke(
                    loud ? kind.tint.opacity(increased ? 0.95 : 0.7)
                         : Color.secondary.opacity(increased ? 0.6 : 0.25),
                    lineWidth: (loud || increased) ? 1 : 0.5)
            }
        }
        .contentShape(collapsed ? AnyShape(Rectangle()) : AnyShape(Capsule()))
    }

    // MARK: - Words

    private func pillText(_ p: ProviderProblemPresentation, provider: String) -> String {
        p.usesPrintfProviderFormat
            ? String(format: i18n.t(p.pillKey), provider)
            : i18n.t(p.pillKey, ["provider": provider])
    }

    /// Line 1 of the popover: the state.
    private func title(_ p: ProviderProblemPresentation, provider: String) -> String {
        p.usesPrintfProviderFormat
            ? String(format: i18n.t(p.titleKey), provider)
            : i18n.t(p.titleKey, ["provider": provider])
    }

    private func announce(_ p: ProviderProblemPresentation, provider: String) {
        NSAccessibility.post(
            element: NSApp as Any, notification: .announcementRequested,
            userInfo: [
                .announcement: title(p, provider: provider),
                .priority: NSAccessibilityPriorityLevel.medium.rawValue,
            ])
    }

    // MARK: - The popover

    private func detail(_ p: ProviderProblemPresentation, provider: LLMProvider) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title(p, provider: provider.displayName))
                .font(.system(.callout).weight(.semibold))
            Text(i18n.t(p.bodyKey))
                .font(.callout)
                .foregroundStyle(.secondary)
            // One row when the labels fit, a stack when a longer language does not:
            // buttons never truncate (HIG Typography). The stacked form reads
            // the default first, as a stacked NSAlert does.
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 8) {
                    Spacer(minLength: 0)
                    buttons(p.actions, provider: provider)
                }
                VStack(alignment: .trailing, spacing: 8) {
                    buttons(Array(p.actions.reversed()), provider: provider, defaultIs: p.actions.last)
                }
            }
            .padding(.top, 6)
        }
        .fixedSize(horizontal: false, vertical: true)
        .padding(16)
        .frame(width: 300)
    }

    @ViewBuilder
    private func buttons(
        _ actions: [ProviderProblemAction], provider: LLMProvider,
        defaultIs defaultAction: ProviderProblemAction? = nil
    ) -> some View {
        let primary = defaultAction ?? actions.last
        ForEach(actions, id: \.self) { action in
            let button = Button(buttonTitle(action)) { perform(action, provider: provider) }
                .fixedSize(horizontal: true, vertical: false)
            if action == primary {
                button.keyboardShortcut(.defaultAction)
            } else {
                button
            }
        }
    }

    private func buttonTitle(_ action: ProviderProblemAction) -> String {
        switch action {
        case .switchProvider: return i18n.t("desktop.outOfCredit.switchProvider")
        case .addFunds: return i18n.t("desktop.outOfCredit.addFunds")
        case .openSettings: return i18n.t("desktop.providerProblem.openSettings")
        }
    }

    private func perform(_ action: ProviderProblemAction, provider: LLMProvider) {
        showingDetail = false
        switch action {
        case .switchProvider, .openSettings:
            // Deep-link to the pane that answers the question, not the window's
            // last-used pane.
            SettingsWindow.shared.show(pane: .llm)
        case .addFunds:
            let links = provider.links
            if let url = links.billing ?? links.console { NSWorkspace.shared.open(url) }
        }
    }
}

/// Safari's tab ×, as seen: a thin grey cross about 9 pt, no disc; a soft circle
/// only under the pointer, and a 20 pt target round a glyph that small.
private struct PlainDismissButton: View {
    let label: String
    let tooltip: String
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
        .help(tooltip)
        .accessibilityLabel(label)
    }
}
