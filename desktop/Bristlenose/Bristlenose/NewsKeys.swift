import Foundation

/// The Ed25519 public keys the news check trusts (spec §9).
///
/// # ⚠️ The production keys are EMPTY placeholders
///
/// Until the owner runs `scripts/sign-news.py keygen` (twice: the active `k1`
/// and the cold backup `k0`, generated offline) and pastes the two printed
/// base64 public keys below, **a Release build accepts no news file at all**:
/// an empty key is dropped by `NewsCheck.Keyring`, so every file fails with
/// `unknownKey` and the welcome screen simply shows no news. That is the safe
/// state, and it is deliberate. **No request goes out either**: while the
/// keyring is empty, `NewsCheck.mayRequest(with:)` stops the check before it
/// asks, because a request whose file can never be accepted is collection for
/// nothing (counts included).
///
/// When the keys are set, also set `PUBLIC_KEYS` in `scripts/sign-news.py`:
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

    /// Base64 of the raw 32-byte public key. **EMPTY: no file is accepted.**
    static let productionK1 = ""
    /// Base64 of the raw 32-byte public key. **EMPTY: no revocation possible.**
    static let productionK0 = ""

    static var productionKeyring: NewsCheck.Keyring {
        NewsCheck.Keyring(base64Keys: [activeKID: productionK1, backupKID: productionK0],
                          backupKID: backupKID)
    }

    /// Whether this build can ever accept a news file. While it can't (today:
    /// the production keys are empty), the app also shows NO news or counts
    /// controls: no first-run checkbox, no Settings rows. A switch for
    /// something that never happens is an offer the build can't keep, and
    /// the store build's declarations ("Data Not Collected") stay true.
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
