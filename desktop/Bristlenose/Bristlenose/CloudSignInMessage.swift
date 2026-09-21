import Foundation

/// A failure sentence that may be **ours** or **theirs**.
///
/// Sign-in errors are a mix. Some are our words about our own state — "Bristlenose
/// hasn't been set up with a Zoom client ID yet" — and those want a key. Others
/// carry the provider's own `error_description`, and Microsoft's "User declined to
/// consent" is already more precise than anything we would write; `TeamsOAuth`
/// says so at the site. Replacing a provider's specific reason with our generic
/// translated one is the loss this codebase paid back once already, in the
/// cloud-import download verdicts.
///
/// So: `key` when the sentence is ours, `nil` when it is a passthrough. `english`
/// is always populated, because `LocalizedError.errorDescription` reaches logs and
/// bug reports and stays English there by decision
/// (`docs/design-i18n.md` §"Which surfaces are targets").
///
/// The three OAuth enums have no `I18n` and cannot get one — they are not views.
/// `CloudImportWindow` resolves this, which is the same shape as
/// `CloudFetchFailure`, `CopyError.localeKey` and `MiroAPI.APIError.localeKey`.
struct CloudSignInMessage: Equatable, Sendable {
    /// `desktop.cloudImport.*`, or nil for a passthrough of the provider's words.
    let key: String?
    let vars: [String: String]
    /// What the log gets, and what the UI falls back to if a key ever goes missing.
    let english: String

    init(key: String? = nil, vars: [String: String] = [:], english: String) {
        self.key = key
        self.vars = vars
        self.english = english
    }

    /// The provider's own sentence, passed through untouched.
    static func passthrough(_ text: String) -> CloudSignInMessage {
        CloudSignInMessage(english: text)
    }
}
