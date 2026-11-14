import Foundation

/// Azure failure states for Settings ▸ LLM Provider, on demand.
///
/// **Why this exists.** The Settings window never scrolls: it grows to fit the
/// pane (`SettingsWindow.refitToContent`) and nothing limits it to the screen.
/// So the height of an Azure failure is a budget against the smallest screen we
/// support, the M1 MacBook Air at default scaling (1440×900 points, about
/// 800–820pt visible), and the Azure pane is already the tallest at about 792pt
/// of window. Those states are hard to reach from a healthy account, which is
/// the argument `Diagnostics ▸ Cloud Import` makes one level up: a state that can
/// be written but never *seen* is how a layout is wrong for two releases.
/// Design: `docs/design-azure-connection.md` §13.
///
/// **What it overlays.** The pane reads Azure's status and failure sentence
/// through `LLMSettingsView.statusFor` / `failure(for:)`; a fixture replaces both
/// at read time. It never *writes* the real validation state, so a background
/// check landing during the visit cannot clobber it. It still lets the normal
/// path run underneath: choosing a fixture selects the Azure row, which reads the
/// Keychain and, with a stored key and a stale verdict, sends the same one-token
/// check as clicking the row, and an edit to an Azure field announces the REAL
/// verdict to VoiceOver while the pane draws the fake one. Leaving Azure, or
/// reopening the pane (every appear drops the previous visit's fixture), clears it.
/// While one is active the window refits exactly, so a height read does not
/// depend on the order fixtures were picked.
///
/// **What it is not.** It does not ship a design. The sentences are the
/// *proposed* wording, passed through as English (this menu is tester-facing and
/// English by decision, like the rest of Diagnostics). The status label still
/// reads the shipped "Invalid key", because "Not connected" is not built, and the
/// proposed Details button is not built either: the raw record lives in a
/// popover (`ProjectDiagnosticPopover`), which costs the pane no height, so the
/// pane's collapsed failure is the whole budget. Gated by
/// `DistributionChannel.exposesDebugTools`, so no App Store or TestFlight build
/// can reach it.
enum AzureSettingsFixture: String, CaseIterable, Identifiable {
    case keyNotAccepted
    case noSuchDeployment
    case hostNotFound
    case longestSentence

    var id: String { rawValue }

    var menuTitle: String {
        switch self {
        case .keyNotAccepted: "Key Not Accepted"
        case .noSuchDeployment: "No Such Deployment"
        case .hostNotFound: "Host Not Found"
        case .longestSentence: "Longest Sentence: Long Deployment Name"
        }
    }

    /// The proposed sentences S1, S2 and S6 (`docs/design-azure-connection.md`
    /// §9), with the provider named "Azure" (D10). Passed through as given:
    /// nothing here is a locale key. `longestSentence` is S2 with a 66-character
    /// deployment name, which wraps to four lines.
    var sentence: String {
        switch self {
        case .keyNotAccepted:
            "Azure didn’t accept this key (401). Check it and the endpoint in Keys and Endpoint."
        case .noSuchDeployment:
            "No deployment named “research-mni” on this resource. Key and endpoint are fine; check the name."
        case .hostNotFound:
            "Couldn’t find that endpoint. Check the address."
        case .longestSentence:
            "No deployment named “research-interviews-structured-outputs-gpt-4-1-mini-eu-west-2026” on this resource. Key and endpoint are fine; check the name."
        }
    }

    var failure: FailureMessage { .passthrough(sentence) }

    // MARK: - Presenting

    /// A fixture asked for a moment ago, waiting for a pane that is not on
    /// screen yet. Settings re-adds the pane on every tab switch, so a pane that
    /// does not exist when the menu item is chosen reads this in `onAppear`. It
    /// expires: a request nobody collected must not surface on a later visit.
    @MainActor private static var pending: (fixture: AzureSettingsFixture, at: Date)?
    static let pendingLifetime: TimeInterval = 3

    @MainActor static func stage(_ fixture: AzureSettingsFixture, at now: Date = Date()) {
        pending = (fixture, now)
    }

    @MainActor static func present(_ fixture: AzureSettingsFixture) {
        stage(fixture)
        // A pane that is already on screen takes it from the notification; one
        // that is not takes it from `takePending()` once `show(pane:)` has built it.
        NotificationCenter.default.post(name: .azureSettingsFixture, object: fixture)
        SettingsWindow.shared.show(pane: .llm)
    }

    @MainActor static func takePending(now: Date = Date()) -> AzureSettingsFixture? {
        defer { pending = nil }
        guard let pending, now.timeIntervalSince(pending.at) <= pendingLifetime else { return nil }
        return pending.fixture
    }
}

extension Notification.Name {
    /// Posted by Diagnostics ▸ Azure Settings; `object` is an `AzureSettingsFixture`.
    static let azureSettingsFixture = Notification.Name("bristlenoseAzureSettingsFixture")
}
