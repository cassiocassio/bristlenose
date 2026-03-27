import SwiftUI

/// App-wide toast notification overlay.
///
/// Shows a brief message at the bottom of the window, auto-dismisses after 3 seconds.
/// One toast at a time — new messages replace the current one.
///
/// Usage: inject `ToastStore` as `@EnvironmentObject` and call `toast.show("message")`.
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

    var body: some View {
        VStack {
            Spacer()
            if let message = toast.message {
                Text(message)
                    .font(.callout)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8))
                    .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .padding(.bottom, 16)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: toast.message)
    }
}
