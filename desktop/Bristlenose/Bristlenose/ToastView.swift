import SwiftUI

/// Shared bottom-of-window toast surface. Two consumers today:
///   - `ToastStore` + `ToastOverlay` — informational toasts (3s auto-dismiss).
///   - `UndoableRemovalStore` + `RemoveToast` — undoable removal toasts
///     (8s window with an action button).
///
/// Visual surface lives in `ToastSurface` so the two consumers stay
/// pixel-aligned without ad-hoc copies.

@MainActor
final class ToastStore: ObservableObject {
    @Published var message: String?
    private var dismissTask: Task<Void, Never>?

    /// Show a toast message. Replaces any currently visible toast.
    func show(_ message: String, duration: TimeInterval = 3) {
        dismissTask?.cancel()
        self.message = message
        dismissTask = Task {
            try? await Task.sleep(for: .seconds(duration))
            guard !Task.isCancelled else { return }
            self.message = nil
        }
    }
}

/// Overlay view that renders the toast at the bottom of its parent.
/// Attach to the root content view via `.overlay { ToastOverlay() }`.
struct ToastOverlay: View {
    @EnvironmentObject var toast: ToastStore
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack {
            Spacer()
            if let message = toast.message {
                ToastSurface(message: message, action: nil, tooltip: nil)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .padding(.bottom, 16)
            }
        }
        .animation(
            reduceMotion ? nil : .easeInOut(duration: 0.25),
            value: toast.message
        )
    }
}

/// Shared visual surface for toasts. Composable: optional action button
/// (rendered to the right of the message), optional hover tooltip.
struct ToastSurface: View {

    /// Trailing action — button label + handler.
    struct Action {
        let label: String
        let handler: () -> Void
    }

    let message: String
    let action: Action?
    let tooltip: String?

    var body: some View {
        HStack(spacing: 12) {
            Text(message)
                .font(.callout)

            if let action {
                Button(action.label, action: action.handler)
                    .buttonStyle(.borderless)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
        .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
        .help(tooltip ?? "")
    }
}
