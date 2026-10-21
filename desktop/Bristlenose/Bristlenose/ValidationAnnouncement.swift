import AppKit

/// What VoiceOver should hear when a key check the researcher asked for lands.
///
/// The verdict only changes the status label under the key field, and focus
/// stays where it was, so VoiceOver says nothing unless the app announces it.
/// Only a check the researcher started (a pasted key, a changed Azure endpoint)
/// is spoken; the checks Settings runs by itself on open or on a row change
/// stay quiet, since nobody asked for them.
struct ValidationAnnouncement: Equatable {
    let text: String
    let priority: NSAccessibilityPriorityLevel

    /// `nil` when nothing should be said: a check nobody asked for, or a
    /// verdict that is not one (still checking, no key).
    @MainActor
    static func make(
        provider: LLMProvider, status: ProviderStatus, error: String?,
        requested: Bool, i18n: I18n
    ) -> ValidationAnnouncement? {
        if !requested { return nil }
        switch status {
        case .checking, .notSetUp:
            return nil
        case .online:
            // The label alone, as the pane shows it: an error under a green
            // status is not drawn, so it is not spoken either.
            return ValidationAnnouncement(
                text: provider.statusLabel(for: status, i18n: i18n), priority: .medium)
        case .invalid, .unavailable, .outOfCredit:
            // As for a key that failed to save: an error that did not move focus.
            return ValidationAnnouncement(
                text: spoken(provider.statusLabel(for: status, i18n: i18n), error), priority: .high)
        }
    }

    private static func spoken(_ label: String, _ error: String?) -> String {
        guard let error, !error.isEmpty else { return label }
        return "\(label). \(error)"
    }

    func post() {
        NSAccessibility.post(
            element: NSApp as Any, notification: .announcementRequested,
            userInfo: [.announcement: text, .priority: priority.rawValue])
    }
}
