import Foundation
import Testing

@testable import Bristlenose

// The one line that made the whole grant store inert.
//
// `KeychainHelper.serviceNames` is an ALLOWLIST, not a naming convention:
// `get` and `set` each open with `guard let service = serviceNames[provider]`
// and bail. An unregistered key therefore reads nil and writes false —
// silently, with no error and no crash. `CloudGrantStore` shipped against an
// unregistered key and was a complete no-op: every save discarded, every
// restore empty, and the only visible symptom "why am I signing in again?",
// weeks later, on a feature whose entire purpose was to stop that.
//
// This asserts registration rather than round-tripping through the Keychain,
// because tests here never touch the real one — a SIGKILL bypasses teardown,
// so cleanup is not crash-safe and a stray test could overwrite a real
// credential.

@Suite("Cloud grant keys are registered with the Keychain helper")
struct CloudGrantKeychainRegistrationTests {

    @Test("The Google grant key resolves to a service name")
    func googleGrantKeyIsRegistered() {
        // If this fails, `CloudGrantStore` is silently storing nothing.
        #expect(KeychainHelper.serviceNames["cloud-google-meet"] != nil)
    }

    @Test("An unregistered key really does fail closed — the trap this pins")
    func unregisteredKeysReadNil() {
        // Proves the mechanism rather than trusting the comment: without this,
        // the test above looks like bookkeeping instead of a guard against a
        // silent no-op.
        #expect(KeychainHelper.serviceNames["cloud-not-a-real-provider"] == nil)
        #expect(KeychainHelper.get(provider: "cloud-not-a-real-provider") == nil)
        #expect(KeychainHelper.set(provider: "cloud-not-a-real-provider", value: "x") == false)
    }

    @Test("Its service name is distinct from every other stored secret")
    func serviceNameDoesNotCollide() {
        // One Keychain account is shared across providers, so the SERVICE name
        // is the only thing separating a sign-in from an API key. A duplicate
        // would have one silently overwrite the other.
        let names = KeychainHelper.serviceNames.values
        #expect(Set(names).count == names.count)
    }
}
