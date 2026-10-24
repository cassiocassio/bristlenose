import Foundation
import Testing
@testable import Bristlenose

/// The page's door to this window's feedback sheet (`open-feedback`). The status
/// page's footer link sends no data and opens feedback; the whole-report crash
/// pane, once its Retry has crashed too, sends `kind: "problem"` and the
/// sentence to start from, and opens a problem report
/// (`docs/design-feedback-native.md` § Feedback and problem reports).
@MainActor
@Suite struct FeedbackDoorTests {

    private func ask(_ data: [String: Any]?) -> BridgeHandler {
        let bridge = BridgeHandler()
        var body: [String: Any] = ["type": "project-action", "action": "open-feedback"]
        if let data { body["data"] = data }
        bridge.handleMessage(body)
        return bridge
    }

    @Test func noDataAsksForFeedback() {
        let bridge = ask(nil)
        #expect(bridge.feedbackRequests == 1)
        #expect(bridge.requestedFeedbackMode == .feedback)
    }

    @Test func theCrashPaneAsksForAProblemReportWithItsSentence() {
        let message = "This report couldn’t be shown.\nTypeError: x · /report/quotes/"
        let bridge = ask(["kind": "problem", "message": message])
        #expect(bridge.feedbackRequests == 1)
        #expect(bridge.requestedFeedbackMode == .problem(initialMessage: message))
    }

    /// Cut, never refused, at the same limit the page cuts at.
    @Test func aLongMessageIsCut() {
        let bridge = ask(["kind": "problem", "message": String(repeating: "a", count: 2000)])
        guard case .problem(let message) = bridge.requestedFeedbackMode else {
            Issue.record("not a problem report"); return
        }
        #expect(message.count == FeedbackSheetMode.problemMessageLimit)
    }

    /// Only exactly `"problem"` with a message that says something.
    @Test(arguments: [
        ["kind": "Problem", "message": "m"],
        ["kind": "problem ", "message": "m"],
        ["kind": "problem", "message": ""],
        ["kind": "problem", "message": "  \n "],
        ["kind": "problem", "message": 3],
        ["message": "m"],
    ] as [[String: Any]])
    func anythingElseIsFeedback(data: [String: Any]) {
        let bridge = ask(data)
        #expect(bridge.feedbackRequests == 1)
        #expect(bridge.requestedFeedbackMode == .feedback)
    }

    /// A feedback request after a problem report is feedback again: the mode
    /// is what this request asked for, not what the last one did.
    @Test func theNextPlainRequestIsFeedbackAgain() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "project-action", "action": "open-feedback",
                              "data": ["kind": "problem", "message": "m"]])
        bridge.handleMessage(["type": "project-action", "action": "open-feedback"])
        #expect(bridge.feedbackRequests == 2)
        #expect(bridge.requestedFeedbackMode == .feedback)
    }
}
