import CryptoKit
import Foundation

// Shared OAuth spine — used by every platform adapter, owned by none.
//
// PKCE is RFC 7636, not a vendor concern: the Microsoft and Google adapters need
// byte-identical behaviour from it. It lived in GoogleOAuth.swift only because
// that adapter was written first; two parallel sessions then independently
// reached for the same type, which is the spine/adapter split in
// docs/design-cloud-import.md §7 asserting itself rather than either session
// duplicating by accident. Extracted here 15 Aug 2026 so the next adapter
// inherits it instead of writing a third copy.


// MARK: - PKCE

/// RFC 7636 verifier/challenge pair.
///
/// Pulled out as a value type with no I/O so it is unit-testable — the whole
/// mechanism is unobservable at runtime, and a subtly wrong challenge fails as
/// `invalid_grant` at the token exchange, several steps from the cause.
struct PKCEPair: Equatable {
    let verifier: String
    let challenge: String
    let method = "S256"

    /// Google: 43–128 characters from the unreserved set. 32 random bytes
    /// base64url-encode to 43 characters — the documented minimum, and the
    /// conventional choice.
    init(verifier: String? = nil) {
        let v = verifier ?? Self.randomVerifier()
        self.verifier = v
        let digest = SHA256.hash(data: Data(v.utf8))
        self.challenge = Data(digest).base64URLEncodedString()
    }

    static func randomVerifier(byteCount: Int = 32) -> String {
        var bytes = [UInt8](repeating: 0, count: byteCount)
        // SecRandomCopyBytes, not `Int.random`: this value is the entire
        // credential substitute for a client that holds no secret.
        if SecRandomCopyBytes(kSecRandomDefault, byteCount, &bytes) != errSecSuccess {
            bytes = (0..<byteCount).map { _ in UInt8.random(in: 0...255) }
        }
        return Data(bytes).base64URLEncodedString()
    }
}

extension Data {
    /// base64url, unpadded — RFC 4648 §5. The padding matters: Google rejects a
    /// challenge with `=` in it.
    func base64URLEncodedString() -> String {
        base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
