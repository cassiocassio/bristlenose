import Foundation
import Testing
@testable import Bristlenose

/// The serve-free path is load-bearing for the expired-alpha `.dmg` flow: with
/// no sidecar there's nothing to answer `/api/health`, so `load()` MUST honour
/// the `preresolved` guard and keep the supplied `FeedbackConfig` rather than
/// probing port 0 (which resolves to `.unavailable` → silent clipboard-only
/// degradation). Pure, no network. Suite is `@MainActor` — the model is.
@MainActor
@Suite struct FeedbackSheetModelTests {

    @Test func serverlessLoadSkipsHealthProbeAndKeepsConfig() async {
        let model = FeedbackSheetModel(config: .serverless, i18n: I18n())
        await model.load()

        // Ready without a probe, and the config is the serverless one we passed
        // — NOT overwritten by a failed port-0 health probe (which would be
        // `.unavailable`, url == nil → clipboard-only).
        #expect(model.phase == .ready)
        #expect(model.config.url == FeedbackEndpoint.defaultURL)
        #expect(model.config.enabled)
    }

    // MARK: - Cancel during a send

    /// A send that the server holds: `hold()` parks until `open()`, and does not
    /// answer cancellation, as a request the server already has will not. Records
    /// whether the task carrying it was cancelled by the time it returns.
    @MainActor
    final class HeldSend {
        private(set) var entered = false
        private(set) var cancelledInside = false
        /// Every caller parked, so a bug that sends twice fails the test
        /// rather than hanging it on a continuation nobody resumes.
        private var parked: [CheckedContinuation<Void, Never>] = []

        func hold() async {
            entered = true
            await withCheckedContinuation { parked.append($0) }
            cancelledInside = Task.isCancelled
        }

        func open() {
            parked.forEach { $0.resume() }
            parked.removeAll()
        }

        func untilEntered() async throws {
            for _ in 0..<10_000 where !entered { await Task.yield() }
            try #require(entered, "the sender was never reached")
        }
    }

    /// A model whose send waits on `held` and then answers `result`, and whose
    /// clipboard writes land in `copied` instead of the real pasteboard.
    private func model(
        answering result: SubmissionResult, held: HeldSend, copied: @escaping (String) -> Void
    ) -> FeedbackSheetModel {
        let model = FeedbackSheetModel(
            config: .serverless,
            i18n: I18n(),
            sender: { _, _ in
                await held.hold()
                return result
            },
            copy: { copied($0); return true }
        )
        model.rating = .like
        return model
    }

    @Test(arguments: [SubmissionResult.failed, .sent])
    func aSendThatEndsAfterCancelShowsNothing(_ result: SubmissionResult) async throws {
        let held = HeldSend()
        var copied: [String] = []
        var outcomes: [(dismiss: Bool, toast: String?)] = []
        let model = model(answering: result, held: held, copied: { copied.append($0) })
        await model.load()

        let send = Task { await model.send() }
        try await held.untilEntered()
        send.cancel()
        held.open()
        outcomes.append(await send.value)

        #expect(copied.isEmpty, "a cancelled send wrote the clipboard")
        #expect(outcomes.first?.toast == nil, "a cancelled send asked for a toast")
        #expect(outcomes.first?.dismiss == false, "a cancelled send reported a confirmed send")
    }

    /// What the sheet does: Cancel (and Esc, its shortcut) calls `cancelSend`,
    /// which must reach the request itself and leave the sheet nothing to show.
    @Test(arguments: [SubmissionResult.failed, .sent])
    func cancelStopsTheSendAndDeliversNothing(_ result: SubmissionResult) async throws {
        let held = HeldSend()
        var copied: [String] = []
        var delivered: [(dismiss: Bool, toast: String?)] = []
        let model = model(answering: result, held: held, copied: { copied.append($0) })
        await model.load()

        model.startSend { delivered.append($0) }
        try await held.untilEntered()
        model.cancelSend()
        held.open()
        await model.sendTask?.value

        #expect(held.cancelledInside, "Cancel did not reach the request")
        #expect(copied.isEmpty, "a cancelled send wrote the clipboard")
        #expect(delivered.count == 1)
        #expect(delivered.first?.toast == nil, "a cancelled send asked for a toast")
        #expect(delivered.first?.dismiss == false, "a cancelled send confirmed (the alpha flow's Thanks)")
    }

    /// The control: the same held send, not cancelled, shows its outcome, so
    /// the tests above can see a write or a toast when there is one.
    @Test func anUncancelledSendStillShowsItsOutcome() async throws {
        let held = HeldSend()
        var copied: [String] = []
        var delivered: [(dismiss: Bool, toast: String?)] = []
        let model = model(answering: .failed, held: held, copied: { copied.append($0) })
        await model.load()

        model.startSend { delivered.append($0) }
        try await held.untilEntered()
        held.open()
        await model.sendTask?.value

        #expect(!held.cancelledInside)
        #expect(copied.count == 1, "a failed send falls back to the clipboard")
        #expect(model.failure != nil)
        #expect(delivered.first?.dismiss == false)
    }

    // MARK: - A send that fails says so (R80)

    /// While the request is out the sheet is in `.sending`, which is what
    /// draws the spinner and "Sending…" and disables Send.
    @Test func aSendInFlightIsVisible() async throws {
        let held = HeldSend()
        let model = model(answering: .sent, held: held, copied: { _ in })
        await model.load()

        model.startSend { _ in }
        try await held.untilEntered()
        #expect(model.phase == .sending, "nothing shows that a send is out")
        #expect(!model.canSend, "Send stayed live while a send was out")
        held.open()
        await model.sendTask?.value
        #expect(model.phase == .ready)
    }

    /// The failure is said in the sheet, not by a toast behind it: what
    /// failed, that the text is on the clipboard, and where to paste it. The
    /// sheet stays open with the text. A bare `I18n()` answers the key, so
    /// this asserts which sentence was chosen.
    @Test func aFailedSendSaysSoInTheSheet() async throws {
        let held = HeldSend()
        var copied: [String] = []
        var delivered: [(dismiss: Bool, toast: String?)] = []
        let model = model(answering: .failed, held: held, copied: { copied.append($0) })
        model.message = "Long careful feedback."
        await model.load()

        model.startSend { delivered.append($0) }
        try await held.untilEntered()
        held.open()
        await model.sendTask?.value

        #expect(model.failure == "common.feedback.sendFailed")
        #expect(delivered.first?.toast == nil, "the failure went to a toast behind the sheet")
        #expect(delivered.first?.dismiss == false)
        #expect(model.message == "Long careful feedback.", "the text was not kept")
        #expect(copied.first?.contains("Long careful feedback.") == true)
    }

    /// Neither the send nor the copy took: the sentence must not claim the
    /// clipboard has it.
    @Test func aFailedSendAndCopySaysTheTextIsNotOnTheClipboard() async throws {
        let model = FeedbackSheetModel(
            config: .serverless, i18n: I18n(),
            sender: { _, _ in .failed },
            copy: { _ in false }
        )
        model.rating = .like
        await model.load()

        let outcome = await model.send()

        #expect(model.failure == "common.feedback.sendFailedNotCopied")
        #expect(outcome.toast == nil)
        #expect(outcome.dismiss == false)
    }

    /// No endpoint (health unreachable, feedback disabled): nothing is
    /// posted, so no spinner, but the same sentence says where the text went.
    @Test func noEndpointSaysSoInTheSheet() async {
        var copied: [String] = []
        let model = FeedbackSheetModel(
            config: .unavailable, i18n: I18n(),
            sender: { _, _ in Issue.record("no endpoint, so nothing is posted"); return .failed },
            copy: { copied.append($0); return true }
        )
        model.rating = .like
        await model.load()

        let outcome = await model.send()

        #expect(model.failure == "common.feedback.sendFailed")
        #expect(outcome.toast == nil)
        #expect(copied.count == 1)
    }

    /// Send again after a failure: the old sentence goes as the new send
    /// starts, and a confirmed send leaves none behind.
    @Test func aNewSendClearsTheFailure() async throws {
        var answer = SubmissionResult.failed
        let model = FeedbackSheetModel(
            config: .serverless, i18n: I18n(),
            sender: { _, _ in answer },
            copy: { _ in true }
        )
        model.rating = .like
        await model.load()
        _ = await model.send()
        try #require(model.failure != nil)

        answer = .sent
        let outcome = await model.send()

        #expect(model.failure == nil, "a confirmed send kept the old failure")
        #expect(outcome.dismiss == true)
        #expect(outcome.toast == "common.feedback.sent")
    }

    /// An edit after a failure takes the line away: "it's copied to the
    /// clipboard" describes the text as it was sent.
    @Test func anEditAfterAFailureClearsTheLine() async {
        let model = FeedbackSheetModel(
            config: .serverless, i18n: I18n(),
            sender: { _, _ in .failed },
            copy: { _ in true }
        )
        model.rating = .like
        await model.load()
        _ = await model.send()
        #expect(model.failure != nil)
        model.message = "More."
        #expect(model.failure == nil, "editing the message kept the line")

        _ = await model.send()
        #expect(model.failure != nil)
        model.rating = .love
        #expect(model.failure == nil, "changing the rating kept the line")
    }

    /// Cancelled while out: the person has gone, so no sentence either.
    @Test func aCancelledSendLeavesNoFailure() async throws {
        let held = HeldSend()
        let model = model(answering: .failed, held: held, copied: { _ in })
        await model.load()

        model.startSend { _ in }
        try await held.untilEntered()
        model.cancelSend()
        held.open()
        await model.sendTask?.value

        #expect(model.failure == nil)
    }

    /// No endpoint (disabled or unreachable serve): the send is the clipboard.
    /// Cancelled before its task begins, it must not write that either.
    @Test func aClipboardSendCancelledBeforeItBeginsWritesNothing() async {
        var copied: [String] = []
        var delivered: [(dismiss: Bool, toast: String?)] = []
        let model = FeedbackSheetModel(
            config: .unavailable, i18n: I18n(),
            sender: { _, _ in Issue.record("no endpoint, so nothing is posted"); return .failed },
            copy: { copied.append($0); return true }
        )
        model.rating = .like
        await model.load()

        model.startSend { delivered.append($0) }
        let send = model.sendTask
        model.cancelSend()
        await send?.value

        #expect(copied.isEmpty, "a cancelled clipboard send wrote the clipboard")
        #expect(delivered.first?.toast == nil)
    }

    /// A second Send before the first has finished is ignored, not a second
    /// request whose task nothing can cancel.
    @Test func aSecondSendWhileOneIsOutIsIgnored() async throws {
        let held = HeldSend()
        var delivered: [(dismiss: Bool, toast: String?)] = []
        let model = model(answering: .sent, held: held, copied: { _ in })
        await model.load()

        model.startSend { delivered.append($0) }
        let first = model.sendTask
        model.startSend { delivered.append($0) }
        #expect(model.sendTask == first, "the second press replaced the send in flight")
        try await held.untilEntered()
        held.open()
        await first?.value

        #expect(delivered.count == 1)
        #expect(model.sendTask == nil, "a finished send still blocks the next")
    }
}
