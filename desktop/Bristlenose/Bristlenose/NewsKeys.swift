import Foundation

/// The Ed25519 public keys the news check trusts (spec §9).
///
/// # The production keys are set (25 Nov 2026)
///
/// Both public keys below are the real ones (`k1` active, `k0` cold backup;
/// the private halves live in `~/.private_keys/`). A Release build therefore
/// accepts a signed news file and makes the daily check. A keyring with no
/// usable key does neither: an empty key is dropped by `NewsCheck.Keyring`,
/// `NewsCheck.mayRequest(with:)` stops the check before it asks (a request whose
/// file can never be accepted is collection for nothing), and the app shows no
/// news or counts controls (`isLive`).
///
/// The same keys are in `PUBLIC_KEYS` in `scripts/sign-news.py`;
/// `tests/test_sign_news.py` fails if the two disagree (the repo's Seams rule).
///
/// - `k1` signs every ordinary file.
/// - `k0` is the backup. A file it signs may carry `"revoke": ["k1"]`, which
///   the app records permanently (spec §9, "Revocation without an update").
///
/// One key, one job: these sign news and nothing else.
enum NewsKeys {
    static let activeKID = "k1"
    static let backupKID = "k0"

    /// Base64 of the raw 32-byte public key: the active signing key.
    static let productionK1 = "+jCA1SYBnaID8ArXG6iyndpvlSMM4cy7OCYYiE53hzA="
    /// Base64 of the raw 32-byte public key: the cold backup, which can revoke `k1`.
    static let productionK0 = "lJxaisxLyyGCH/bHKY59I21nm5VdecrkrbwfQ3KHKj4="

    static var productionKeyring: NewsCheck.Keyring {
        NewsCheck.Keyring(base64Keys: [activeKID: productionK1, backupKID: productionK0],
                          backupKID: backupKID)
    }

    /// Whether this build can ever accept a news file. While it can't (a
    /// keyring with no usable key), the app also shows NO news or counts
    /// controls: no first-run checkbox, no Settings rows. A switch for
    /// something that never happens is an offer the build can't keep. The
    /// privacy manifest declares Product Interaction and Purchase History
    /// (linked, analytics, not tracking); the App Store privacy label is set to
    /// match at the first submission of a build that carries keys.
    static var isLive: Bool {
        #if DEBUG
        NewsCheck.mayRequest(with: stagingKeyring)
        #else
        NewsCheck.mayRequest(with: productionKeyring)
        #endif
    }

    #if DEBUG
    /// The staging key, accepted **only** by Debug builds, and only for files
    /// whose `env` is `staging`, fetched from `BRISTLENOSE_DEBUG_NEWS_URL`.
    /// Release builds do not contain it. Also an empty placeholder: generate
    /// with `sign-news.py keygen --kid staging` and paste the public half.
    static let stagingKID = "staging"
    static let stagingKey = ""

    static var stagingKeyring: NewsCheck.Keyring {
        NewsCheck.Keyring(base64Keys: [stagingKID: stagingKey], backupKID: nil)
    }
    #endif
}
