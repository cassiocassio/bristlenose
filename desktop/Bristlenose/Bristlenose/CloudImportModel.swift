import Foundation

// Model layer for cloud import (Teams). Pure values — no networking, no UI.
//
// Design: docs/design-cloud-import.md. Mockup: docs/mockups/cloud-import-states.html.
//
// This exists before any adapter because the *classification* is where the
// feature's worst failure modes live, and it can be built and proven against
// real recorded responses without an account, a tenant, or a licence.

// MARK: - API outcomes

/// What a Graph response actually means, as distinct from what its status code says.
///
/// The reason this is a type rather than a switch on `Int`: **two different 401s
/// carry opposite remedies.** An expired token wants refresh-and-retry; an
/// unlicensed account wants a sentence to the user and no retry, ever. An adapter
/// that reads only the status code will re-authenticate forever against an account
/// that can never work, silently, with the researcher watching a spinner.
///
/// Observed 15 Aug 2026 against a live personal account — the fixtures in
/// `CloudImportModelTests` are those exact bodies.
enum TeamsAPIOutcome: Equatable {
    /// The request succeeded.
    case ok

    /// The token is absent, malformed or expired. Refresh and retry — **once**.
    /// See `retryPolicy`: the bound is part of the contract, not the caller's taste.
    case needsReauthentication(code: String)

    /// The account has no licence for the surface being called. Retrying is futile
    /// at any interval and with any token. Tell the user what to do instead.
    case accountNotLicensed

    /// Authenticated, but the scope was never granted. Distinct from the above:
    /// the fix is a consent prompt, not a refresh.
    case scopeNotGranted

    /// The resource genuinely is not there. For `/Recordings` this usually means
    /// the wrong account *tier* rather than a missing folder — see `DriveTier`.
    case notFound

    /// Throttled. `retryAfter` is the server's own advice when it gives any.
    case rateLimited(retryAfter: TimeInterval?)

    /// Server-side and plausibly temporary. Back off and retry.
    case transient(status: Int)

    /// Unrecognised. Deliberately not folded into any of the above — a response we
    /// cannot classify must not be quietly treated as retryable or as fatal.
    case unexpected(status: Int, code: String?)
}

extension TeamsAPIOutcome {
    /// How a caller may retry. Encoded here rather than left to each call site,
    /// because the whole point of this type is that the wrong retry decision is
    /// invisible when it happens.
    enum RetryPolicy: Equatable {
        /// Do not retry. The condition will not clear by itself.
        case never
        /// Retry at most once, after refreshing credentials.
        case onceAfterReauthentication
        /// Retry with backoff; `after` is the server's hint when it supplied one.
        case backoff(after: TimeInterval?)
    }

    var retryPolicy: RetryPolicy {
        switch self {
        case .ok, .accountNotLicensed, .scopeNotGranted, .notFound:
            return .never
        case .needsReauthentication:
            return .onceAfterReauthentication
        case .rateLimited(let after):
            return .backoff(after: after)
        case .transient:
            return .backoff(after: nil)
        case .unexpected:
            // Unknown responses do not get a free retry. A retry loop is the
            // failure this type exists to prevent, so the unknown case fails
            // closed and surfaces rather than spinning.
            return .never
        }
    }

    /// True when the researcher can do something about it. Drives whether the UI
    /// offers an action or simply states the condition.
    var isUserActionable: Bool {
        switch self {
        case .accountNotLicensed, .scopeNotGranted:
            return true
        default:
            return false
        }
    }
}

// MARK: - Classification

enum TeamsResponseClassifier {
    /// Graph's error envelope. Only the two fields that carry meaning.
    private struct Envelope: Decodable {
        struct GraphError: Decodable {
            let code: String
            let message: String
        }
        let error: GraphError
    }

    /// Classify a Graph response by **status and body together**.
    ///
    /// `retryAfter` is the parsed `Retry-After` header when present; passing it
    /// separately keeps this function free of any HTTP type.
    static func classify(
        status: Int,
        body: Data?,
        retryAfter: TimeInterval? = nil
    ) -> TeamsAPIOutcome {
        let envelope = body.flatMap { try? JSONDecoder().decode(Envelope.self, from: $0) }
        let code = envelope?.error.code
        let message = envelope?.error.message ?? ""

        switch status {
        case 200...299:
            return .ok

        case 401:
            // The distinction that matters. Microsoft returns 401 both for "your
            // token is no good" and for "this account has no licence for this
            // API" — same status, opposite remedies. Match the licence case on
            // the message, because its `code` is the unhelpfully generic
            // "Unauthorized" while the message is specific.
            if message.localizedCaseInsensitiveContains("valid license") {
                return .accountNotLicensed
            }
            return .needsReauthentication(code: code ?? "unknown")

        case 403:
            return .scopeNotGranted

        case 404:
            return .notFound

        case 429:
            return .rateLimited(retryAfter: retryAfter)

        case 500...599:
            return .transient(status: status)

        default:
            return .unexpected(status: status, code: code)
        }
    }
}

// MARK: - Drive tier

/// Which kind of drive we are looking at, read from `parentReference.driveType`.
///
/// Worth having as a first-class concept because the failure it prevents is
/// otherwise baffling: a personal account has no `/Recordings` folder at all, so
/// the naive implementation reports an empty list and the researcher concludes
/// they have no recordings. Naming the tier turns that into a sentence.
enum DriveTier: Equatable {
    case business
    case personal
    case unknown(String)

    init(driveType: String?) {
        switch driveType {
        case "business", "documentLibrary":
            self = .business
        case "personal":
            self = .personal
        case let other?:
            self = .unknown(other)
        case nil:
            self = .unknown("")
        }
    }

    /// Teams recordings only land in OneDrive on work/school tiers. On a personal
    /// account they are attached to the meeting chat instead and never reach the
    /// drive — verified 15 Aug 2026.
    var canHoldTeamsRecordings: Bool { self == .business }
}

// MARK: - Row state

/// The state of one row in the import list, resolved at list time.
///
/// Seven states, not a boolean, because "did we import this" and "can we read it
/// now" are different questions and the obvious check answers the wrong one:
/// `fileExists()` returns true for a cloud placeholder. Resolve from `stat` alone
/// — existence, logical size and the dataless flag are all available without
/// faulting a placeholder in, and size against the byte count recorded at import
/// *is* the truncation check.
///
/// See docs/design-cloud-import.md §6 for the table this mirrors.
enum ImportRowState: Equatable {
    /// No local file. Fetchable.
    case notImported

    /// Present, resident, size matches. Nothing to say and nothing to do.
    case imported

    /// Present but a cloud placeholder. **Not an error** — a healthy file that
    /// needs fetching from the *destination* provider, which is a different cloud
    /// from the one the import comes from. Colouring this as a failure repeats the
    /// "ffprobe timed out, so my video is broken" defect.
    case notDownloaded(provider: String)

    /// Present on a volume that is not mounted. Naming the volume makes it
    /// actionable; "missing" does not.
    case driveNotConnected(volume: String)

    /// Present but the wrong size. This one genuinely should re-fetch.
    case damaged

    /// The tenant blocks download of meeting recordings. No remedy, and no manual
    /// fallback either — the researcher cannot download it by hand.
    case viewOnly

    /// Gone from the listing. Unrecoverable if it was never imported.
    case noLongerAvailable

    /// Whether the row offers a tick. Two states deliberately offer none: there is
    /// nothing to fetch, and offering a checkbox would be a lie.
    var isSelectable: Bool {
        switch self {
        case .notImported, .damaged:
            return true
        case .imported, .notDownloaded, .driveNotConnected:
            // Already held. Re-fetching would spend an expiry-limited remote read
            // on a purely local problem — the expensive confusion.
            return false
        case .viewOnly, .noLongerAvailable:
            return false
        }
    }

    /// Whether the checkbox renders as ticked-and-disabled (we hold it) versus
    /// absent entirely (there is nothing to hold).
    var showsCheckbox: Bool {
        switch self {
        case .viewOnly, .noLongerAvailable:
            return false
        default:
            return true
        }
    }

    /// Text for the Status column. `nil` means the column stays empty — the common
    /// case, and deliberate: the checkbox already says imported or not, so this
    /// carries only what the checkbox cannot.
    var statusLabel: String? {
        switch self {
        case .notImported, .imported:
            return nil
        case .notDownloaded(let provider):
            return "On \(provider)"
        case .driveNotConnected(let volume):
            return "On “\(volume)”"
        case .damaged:
            return "Damaged"
        case .viewOnly:
            return "View only"
        case .noLongerAvailable:
            // Platform-neutral since 15 Aug 2026: this enum was Teams-only when
            // written and is now shared by all three adapters, so naming one
            // vendor rendered "No longer in Teams" on Zoom and Meet rows.
            return "No longer available"
        }
    }

    /// Only conditions the researcher should act on are warning-coloured. A
    /// countdown or a pill on every row is a wall of noise, and then none of them
    /// mean anything.
    var isWarning: Bool {
        switch self {
        case .damaged, .viewOnly, .noLongerAvailable:
            return true
        default:
            return false
        }
    }
}

// MARK: - Counting things in a sentence

/// English count + noun, in one place.
///
/// Five sites in the import window interpolate a count into a sentence, and
/// every one of them said **"1 meetings"** — which is what the first live
/// Google list drew on its opening screen, twice, in a window whose whole job
/// is to be believed about quantities. Hardcoding the `s` looks fine at each
/// site and is wrong across all of them.
///
/// Deliberately **not** a general pluraliser. The CLI already has one
/// (`count_noun`, wrapping inflect) and the React SPA uses i18next's CLDR
/// plurals; this window is hardcoded English only because cloud import is not
/// localised yet. When it is, these become `t(key, count:)` — and routing them
/// through one function now means there is a single shape to convert rather
/// than five interpolations to hunt down.
///
/// Verb agreement is **not** handled here, on purpose: "1 meeting is here" and
/// "3 meetings are here" are different sentences, not a pluralised token, and a
/// helper that tried to conjugate would be inventing a grammar engine to avoid
/// writing two strings. Sites that need a verb write both forms.
enum CloudCount {
    /// `1 meeting` / `3 meetings`. Pass `plural` for anything English doesn't
    /// form with a bare `s`.
    static func noun(_ n: Int, _ singular: String, plural: String? = nil) -> String {
        "\(n) \(n == 1 ? singular : (plural ?? singular + "s"))"
    }
}
