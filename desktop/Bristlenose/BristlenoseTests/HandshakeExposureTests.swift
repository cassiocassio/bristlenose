import Foundation
import Testing
@testable import Bristlenose

/// The antenna's solid tier and the handshake file are now one decision.
///
/// The first two tests are the regression: both describe a serve that is up
/// and fronted with Agent Access on, which is what the badge used to read —
/// and both must produce *no* handshake, because the instance id or the
/// token is missing. On the pre-19-Aug code the badge went solid in exactly
/// these states while no file existed.
@Suite("HandshakeExposure")
struct HandshakeExposureTests {

    private static let path = "/Users/x/Studies/ikea"
    private static func on(_: String) -> Bool { true }
    private static func off(_: String) -> Bool { false }

    @Test func runningAndFrontedIsNotEnough_whenInstanceIDHasNotLanded() {
        // The window between `.running` (port parsed from stdout) and the
        // first successful /api/health read. Reachable on every start and
        // every warm re-point, and permanent when health never answers.
        #expect(HandshakeExposure.write(
            state: .running(port: 51234), currentProjectPath: Self.path,
            instanceID: nil, token: "tok", agentAccess: Self.on) == nil)
    }

    @Test func runningAndFrontedIsNotEnough_withoutAScopedToken() {
        #expect(HandshakeExposure.write(
            state: .running(port: 51234), currentProjectPath: Self.path,
            instanceID: "iid", token: nil, agentAccess: Self.on) == nil)
    }

    @Test func allFiveConjunctsProduceAPlanNamingTheProject() {
        let plan = HandshakeExposure.write(
            state: .running(port: 51234), currentProjectPath: Self.path,
            instanceID: "iid", token: "tok", agentAccess: Self.on)
        #expect(plan == HandshakeExposure.Plan(
            path: Self.path, port: 51234, token: "tok", instanceID: "iid"))
    }

    @Test func agentAccessOffExposesNothing() {
        #expect(HandshakeExposure.write(
            state: .running(port: 51234), currentProjectPath: Self.path,
            instanceID: "iid", token: "tok", agentAccess: Self.off) == nil)
    }

    @Test func aServeThatIsNotRunningExposesNothing() {
        for state: ServeState in [.idle, .starting, .failed(error: "boom")] {
            #expect(HandshakeExposure.write(
                state: state, currentProjectPath: Self.path,
                instanceID: "iid", token: "tok", agentAccess: Self.on) == nil)
        }
    }

    @Test func noFrontedProjectExposesNothing() {
        #expect(HandshakeExposure.write(
            state: .running(port: 51234), currentProjectPath: nil,
            instanceID: "iid", token: "tok", agentAccess: Self.on) == nil)
    }

    /// Nothing in the decision assumes a single serve — the same inputs from a
    /// second sidecar answer for that sidecar. Pinned so the independent-windows
    /// stage does not have to rediscover it.
    @Test func twoServesEachAnswerForTheirOwnProject() {
        let a = HandshakeExposure.write(
            state: .running(port: 51234), currentProjectPath: "/a",
            instanceID: "iid-a", token: "tok-a", agentAccess: Self.on)
        let b = HandshakeExposure.write(
            state: .running(port: 51235), currentProjectPath: "/b",
            instanceID: "iid-b", token: "tok-b", agentAccess: Self.on)
        #expect(a?.path == "/a")
        #expect(b?.path == "/b")
        #expect(a?.port != b?.port)
    }
}
