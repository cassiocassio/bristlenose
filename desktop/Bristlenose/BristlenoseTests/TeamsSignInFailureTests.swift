import Foundation
import Testing

@testable import Bristlenose

// What the import window does when a Microsoft sign-in does not end in a token.
//
// Three outcomes reach this path and they are not the same: the researcher
// closed the window, Entra refused them at a wall only their IT can lift, and
// Entra refused a consent screen they could simply accept next time. The window
// used to render all three as "Couldn't load your meetings" with a Try Again
// button that re-ran the *listing* — a button that could not work, over a
// sentence explaining why, on a screen naming the wrong failure.
//
// Scope: the store's phase, because that is the whole of the window's visible
// state. What the researcher notices is "an error screen for closing a window"
// and "a button that does nothing, forever" — both decided here.

@MainActor
@Suite("Microsoft sign-in refusals")
struct TeamsSignInFailureTests {

    /// Fails `signIn()` with a chosen error, so a refusal can be tested without
    /// an OAuth round trip. Everything else is the inert minimum the protocol
    /// needs — no listing ever happens on these paths.
    private final class RefusingSource: CloudImportSource {
        let error: Error
        init(_ error: Error) { self.error = error }

        var accountEmail: String? { nil }
        var accountTier: GoogleAccountTier { .unknown }

        func signIn() async throws { throw error }

        func list(window: DateInterval) async -> MeetingListing {
            MeetingListing(
                rows: [],
                arithmetic: JoinArithmetic(eventsInWindow: 0, fetchable: 0,
                                           organisedByOthers: 0, outcome: .exhausted),
                window: window)
        }

        func fetch(
            row: CloudImportRow,
            destination: URL,
            progress: @escaping @Sendable (FetchProgress) -> Void
        ) async -> FetchOutcome {
            .failed(reason: "not reached", isRetryable: false)
        }
    }

    /// `signIn()` returns before its work does — it publishes `.signingIn` and
    /// hands off to a task. Bounded rather than open-ended so a genuine hang
    /// fails as `.signingIn` instead of never returning.
    private func settledPhase(after store: CloudImportStore) async -> CloudImportStore.Phase {
        store.signIn()
        for _ in 0..<500 where store.phase == .signingIn {
            await Task.yield()
        }
        return store.phase
    }

    private func phase(refusing error: Error) async -> CloudImportStore.Phase {
        await settledPhase(after: CloudImportStore(source: RefusingSource(error), platform: .teams))
    }

    // MARK: - Closing the window is not a fault

    /// The parity bug. Meet and Zoom each had a `cancelled` catch and Microsoft
    /// did not, so abandoning a Teams sign-in — the ordinary thing to do when
    /// you change your mind — fell through to the error screen while the same
    /// act on the other two platforms landed on the calm one.
    @Test("Cancelling a Teams sign-in is incomplete, not failed")
    func cancellingIsNotAFailure() async {
        #expect(await phase(refusing: MicrosoftOAuthError.cancelled) == .signInIncomplete)
    }

    // MARK: - The two walls offer nothing, because there is nothing to offer

    /// `AADSTS90094`. The researcher cannot grant this themselves and neither
    /// can we; the message names the only move there is, which is to send the
    /// approval link to their IT team. A Try Again button here produces the
    /// same refusal for as long as they are willing to keep clicking.
    @Test("An admin-consent wall is not worth retrying")
    func adminWallOffersNoRetry() async {
        let phase = await phase(refusing: MicrosoftOAuthError.consentRefused(
            code: "AADSTS90094",
            description: "The grant requires an administrator's permission."))
        guard case .failed(_, let worthRetrying) = phase else {
            Issue.record("expected a failure, got \(phase)"); return
        }
        #expect(!worthRetrying)
    }

    /// Conditional Access refuses at the *token* leg, after the authorize leg
    /// has already succeeded — which is why it reads as "sign-in worked and
    /// then nothing did", and why a retry is the most tempting wrong move.
    @Test("A Conditional Access refusal is not worth retrying")
    func conditionalAccessOffersNoRetry() async {
        let phase = await phase(refusing: MicrosoftOAuthError.tokenExchangeFailed(
            status: 400,
            body: "AADSTS53003: Access has been blocked by Conditional Access policies."))
        guard case .failed(_, let worthRetrying) = phase else {
            Issue.record("expected a failure, got \(phase)"); return
        }
        #expect(!worthRetrying)
    }

    // MARK: - The refusal that a second attempt genuinely fixes

    /// `AADSTS65004`. They read the consent screen and said no. This is the one
    /// case where the button is exactly right, so suppressing it everywhere
    /// would trade one wrong affordance for another.
    @Test("A declined consent screen keeps its Try Again")
    func declinedConsentKeepsRetry() async {
        let phase = await phase(refusing: MicrosoftOAuthError.consentRefused(
            code: "AADSTS65004",
            description: "User declined to consent to access the app."))
        guard case .failed(_, let worthRetrying) = phase else {
            Issue.record("expected a failure, got \(phase)"); return
        }
        #expect(worthRetrying)
    }

    /// Presuming retryable is the recoverable way to be wrong: an unnecessary
    /// button wastes a click, a withheld one strands someone a retry would have
    /// rescued. Applies to every non-Microsoft error reaching this path too.
    @Test("An unclassifiable error is presumed worth retrying")
    func unknownErrorKeepsRetry() async {
        let phase = await phase(refusing: MicrosoftOAuthError.noAuthorizationCode)
        guard case .failed(_, let worthRetrying) = phase else {
            Issue.record("expected a failure, got \(phase)"); return
        }
        #expect(worthRetrying)
    }
}
