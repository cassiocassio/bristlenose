import SwiftUI

/// Shared chrome for app-global toolbar status pills (`placement: .status`).
///
/// Owns ONLY the envelope + interaction: a plain Capsule button that opens a
/// bottom-anchored light-dismiss popover. Everything inside — the icon, label
/// text, any progress accessory, and the whole popover body — is supplied by
/// the caller via `@ViewBuilder`s, because those diverge completely between
/// pills (Ollama's phase machine + progress bar vs. the out-of-credit dot +
/// add-funds popover). Sharing the envelope means the two pills can't drift on
/// padding, stroke, corner, or popover anchoring.
///
/// Extracted from `OllamaDownloadPill`'s `pillBody`; the envelope constants
/// (0.08 fill / 0.25 stroke, 10×4 padding, caption-medium text is the caller's)
/// are the canonical values. `OllamaDownloadPill` should adopt this shell as a
/// fast-follow so there's a single source; until it does, keep the two in sync.
///
/// Gate visibility at the call site (`if model.isActive { StatusPill { … } }`) —
/// the shell always renders; it doesn't self-hide.
struct StatusPill<Label: View, Detail: View>: View {
    /// Two-way so the caller can also drive presentation (e.g. auto-present).
    @Binding var isPresented: Bool
    /// VoiceOver label for the pill button (the visible text may be truncated).
    let accessibilityLabel: String
    /// Pill contents: icon + text (+ optional accessory), laid out in an HStack.
    @ViewBuilder var label: () -> Label
    /// The popover body shown when the pill is tapped.
    @ViewBuilder var detail: () -> Detail

    var body: some View {
        Button {
            isPresented.toggle()
        } label: {
            HStack(spacing: 6) {
                label()
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(Capsule().fill(Color.secondary.opacity(0.08)))
            .overlay(Capsule().stroke(Color.secondary.opacity(0.25), lineWidth: 0.5))
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(accessibilityLabel)
        .popover(isPresented: $isPresented, arrowEdge: .bottom) {
            detail()
        }
    }
}
