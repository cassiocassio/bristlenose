import Foundation

// Model layer for Google Meet import. Pure values — no networking, no UI.
//
// Design: docs/design-cloud-import.md — §3 gates (and the 15 Aug scope
// findings that reordered §5), §6 the staircase, §9 mechanics.
// Mockup: docs/mockups/cloud-import-states.html — the Teams window this one
// follows.
//
// Sibling: CloudImportModel.swift (Teams). The two deliberately do NOT share a
// protocol yet — see docs/design-cloud-import.md §7 "No CallSource protocol".
// What they DO share is `ImportRowState`, because that type is about *local*
// files and has nothing platform-specific in it.

// MARK: - API outcomes

/// What a Google API response actually means, as distinct from what its status
/// code says.
///
/// The same reasoning as `TeamsAPIOutcome`, one platform over: a status code is
/// not a remedy. Google's collisions are different from Microsoft's, and each
/// one here is a case where the naive reading sends the researcher somewhere
/// useless.
///
/// The three that matter:
///
/// - **403 is overloaded three ways.** `ACCESS_TOKEN_SCOPE_INSUFFICIENT` wants a
///   consent prompt; `PERMISSION_DENIED` on a Meet conference record wants "you
///   weren't the organiser"; a Workspace-edition refusal wants "your plan
///   doesn't do this" and will never clear no matter how many times you consent.
/// - **A 200 with an empty list is the most dangerous response of all**, and it
///   is not modelled here as an error precisely because it isn't one — see
///   `ListOutcome`.
/// - **401 means one thing on Google**, unlike Microsoft, where it also carries
///   "no licence". Google puts the licence-shaped refusals in 403. That
///   asymmetry is why this is a separate type rather than a shared enum with
///   a platform tag.
enum GoogleAPIOutcome: Equatable {
    /// The request succeeded.
    case ok

    /// The token is absent, malformed or expired. Refresh and retry — **once**.
    case needsReauthentication(reason: String)

    /// Authenticated, but this scope was never granted. Google's consent screen
    /// lets the user tick scopes individually, so this is a *routine* state,
    /// not an exceptional one: the researcher may have allowed Calendar and
    /// declined Drive on the same screen. The fix is a re-consent naming the
    /// one missing thing.
    case scopeNotGranted(scope: String?)

    /// Authenticated and in scope, but this account's Workspace edition does not
    /// include the capability (recording, transcripts). No amount of consent
    /// fixes it, and it is the single most common false lead on Google because
    /// personal `@gmail.com` accounts hit it for recordings while every calendar
    /// call succeeds.
    case notAvailableOnThisPlan(detail: String?)

    /// Authenticated, in scope, permitted — but not for *this* resource. On Meet
    /// conference records this is the organiser wall.
    case notPermittedForThisResource(detail: String?)

    /// The resource genuinely is not there.
    case notFound

    /// Throttled or over quota. Google returns 429 *and* 403 for quota
    /// depending on the API, which is exactly why quota is its own case rather
    /// than a status-code branch.
    case rateLimited(retryAfter: TimeInterval?)

    /// Server-side and plausibly temporary.
    case transient(status: Int)

    /// Unrecognised. Deliberately not folded into anything else: a response we
    /// cannot classify must not be quietly treated as retryable or as fatal.
    case unexpected(status: Int, reason: String?)
}

extension GoogleAPIOutcome {
    /// How a caller may retry. Encoded here rather than left to each call site,
    /// because the wrong retry decision is invisible when it happens.
    enum RetryPolicy: Equatable {
        case never
        case onceAfterReauthentication
        /// Re-run consent, then retry. Distinct from `onceAfterReauthentication`
        /// because refreshing a token that was never granted the scope produces
        /// a valid token that fails identically, forever.
        case afterConsent
        case backoff(after: TimeInterval?)
    }

    var retryPolicy: RetryPolicy {
        switch self {
        case .ok, .notFound, .notAvailableOnThisPlan, .notPermittedForThisResource:
            return .never
        case .needsReauthentication:
            return .onceAfterReauthentication
        case .scopeNotGranted:
            return .afterConsent
        case .rateLimited(let after):
            return .backoff(after: after)
        case .transient:
            return .backoff(after: nil)
        case .unexpected:
            // Unknown responses do not get a free retry. Failing closed here is
            // the whole point of the type.
            return .never
        }
    }

    /// True when the researcher can do something about it. Drives whether the UI
    /// offers an action or simply states the condition.
    var isUserActionable: Bool {
        switch self {
        case .scopeNotGranted, .notAvailableOnThisPlan:
            return true
        default:
            return false
        }
    }
}

// MARK: - Classification

enum GoogleResponseClassifier {
    /// Google's error envelope. Only the fields that carry meaning.
    ///
    /// Two API families, two shapes: the older Google-API JSON error
    /// (`error.errors[].reason`) used by Calendar and Drive v3, and the newer
    /// gRPC-transcoded shape (`error.status`) used by the Meet REST API. Both
    /// are decoded because the adapter talks to both, and reading only one is
    /// how a real refusal becomes `.unexpected`.
    private struct Envelope: Decodable {
        struct Detail: Decodable {
            let reason: String?
            let message: String?
        }
        struct GoogleError: Decodable {
            let code: Int?
            let message: String?
            /// gRPC status name — `PERMISSION_DENIED`, `RESOURCE_EXHAUSTED`, …
            let status: String?
            let errors: [Detail]?
        }
        let error: GoogleError
    }

    /// Reasons Google returns in `error.errors[].reason` (or `error.status`)
    /// that this classifier acts on. Kept as a named set so the strings appear
    /// once and the tests can enumerate them.
    enum Reason {
        static let insufficientScope = "ACCESS_TOKEN_SCOPE_INSUFFICIENT"
        static let insufficientPermissions = "insufficientPermissions"
        static let permissionDenied = "PERMISSION_DENIED"
        static let rateLimitExceeded = "rateLimitExceeded"
        static let userRateLimitExceeded = "userRateLimitExceeded"
        static let quotaExceeded = "quotaExceeded"
        static let resourceExhausted = "RESOURCE_EXHAUSTED"
        static let authError = "authError"
        static let unauthorized = "UNAUTHENTICATED"
        static let forbidden = "forbidden"
    }

    /// Classify a Google API response by **status, reason and message
    /// together** — never by status alone.
    ///
    /// `retryAfter` is the parsed `Retry-After` header when present; passing it
    /// separately keeps this function free of any HTTP type.
    static func classify(
        status: Int,
        body: Data?,
        retryAfter: TimeInterval? = nil
    ) -> GoogleAPIOutcome {
        let envelope = body.flatMap { try? JSONDecoder().decode(Envelope.self, from: $0) }
        let error = envelope?.error
        let message = error?.message ?? ""
        // The first reason string is the specific one; `status` is the generic
        // gRPC bucket. Prefer the specific, fall back to the bucket.
        let reason = error?.errors?.compactMap(\.reason).first ?? error?.status

        switch status {
        case 200...299:
            return .ok

        case 401:
            return .needsReauthentication(reason: reason ?? "unauthenticated")

        case 403:
            // The three-way split. Order matters: scope is the most specific and
            // the most actionable, plan is next, and bare permission-denied is
            // the fallback — reversing them would swallow a fixable consent
            // problem inside an unfixable-sounding one.
            if reason == Reason.insufficientScope || reason == Reason.insufficientPermissions {
                return .scopeNotGranted(scope: scopeHint(in: message))
            }
            if reason == Reason.rateLimitExceeded
                || reason == Reason.userRateLimitExceeded
                || reason == Reason.quotaExceeded {
                // Google returns quota exhaustion as 403 on several APIs. Reading
                // this as a permission problem sends the researcher to their IT
                // department over a rate limit that clears by itself.
                return .rateLimited(retryAfter: retryAfter)
            }
            if mentionsEdition(message) {
                return .notAvailableOnThisPlan(detail: message.isEmpty ? nil : message)
            }
            return .notPermittedForThisResource(detail: message.isEmpty ? nil : message)

        case 404:
            return .notFound

        case 429:
            return .rateLimited(retryAfter: retryAfter)

        case 500...599:
            return .transient(status: status)

        default:
            return .unexpected(status: status, reason: reason)
        }
    }

    /// Google names the missing scope inside the human message rather than in a
    /// field. Lifting it out is what lets the UI say which permission to grant
    /// instead of "permission denied".
    ///
    /// Returns nil rather than guessing — a wrong scope name in a consent
    /// prompt is worse than no scope name.
    static func scopeHint(in message: String) -> String? {
        guard let range = message.range(of: "https://www.googleapis.com/auth/") else { return nil }
        let tail = message[range.lowerBound...]
        let scope = tail.prefix { !$0.isWhitespace && $0 != "\"" && $0 != "'" && $0 != "," }
        return scope.isEmpty ? nil : String(scope)
    }

    /// Whether a 403's message is about the account's Workspace edition rather
    /// than about permission. Deliberately conservative: a false positive here
    /// tells a researcher to upgrade their plan when they only needed to
    /// re-consent, which is an expensive thing to be wrong about.
    private static func mentionsEdition(_ message: String) -> Bool {
        let m = message.lowercased()
        return m.contains("workspace edition")
            || m.contains("not supported for this edition")
            || m.contains("not available for your")
            || m.contains("requires a google workspace")
    }
}

// MARK: - Account tier

/// Which kind of Google account is signed in.
///
/// Worth having as a first-class concept for the same reason `DriveTier` is on
/// the Teams side, and the failure is even quieter here: a personal
/// `@gmail.com` account has a **real, populated calendar**, so the meeting list
/// fills up convincingly and then every single row is unfetchable, because
/// personal accounts cannot record a Meet call at all. The Teams equivalent at
/// least fails early — `/Recordings` simply isn't there.
///
/// So this is the difference between "the list looks right but nothing works"
/// and one sentence up front.
enum GoogleAccountTier: Equatable {
    /// A Workspace account, or at least one whose domain isn't a consumer one.
    /// Recording *may* be available; the edition still decides.
    case workspace(domain: String)
    /// A consumer account. Calendar works; Meet recording does not exist.
    case personal
    case unknown

    /// Consumer domains Google operates. `googlemail.com` is the historical
    /// German alias for gmail and still resolves to consumer accounts.
    private static let consumerDomains: Set<String> = ["gmail.com", "googlemail.com"]

    init(email: String?) {
        guard let email, let at = email.lastIndex(of: "@") else {
            self = .unknown
            return
        }
        let domain = String(email[email.index(after: at)...]).lowercased()
        guard !domain.isEmpty else {
            self = .unknown
            return
        }
        self = Self.consumerDomains.contains(domain) ? .personal : .workspace(domain: domain)
    }

    /// Meet recording is a Workspace feature. A personal account can hold a
    /// meeting, invite participants and produce a perfectly good calendar
    /// event — and can never produce a recording to fetch.
    var canHoldMeetRecordings: Bool {
        if case .workspace = self { return true }
        return false
    }

    /// The domain "external" is measured against when ordering the attendee
    /// line (§9's externality rule). Nil for a personal account, where every
    /// other participant is external by construction and the ordering hint
    /// carries no information.
    var organisationDomain: String? {
        if case .workspace(let domain) = self { return domain }
        return nil
    }
}

// MARK: - Listing outcome

/// The terminal state of a paginated listing.
///
/// This exists because of the single worst property of this whole feature: its
/// **success output and its failure output are both a shorter list**. An
/// unfollowed `nextPageToken` returns HTTP 200 with a partial page, and every
/// classifier above says `.ok`. Nothing is wrong; there is simply less.
///
/// So the paginator's terminal state is carried explicitly and rendered, rather
/// than inferred from "no error was thrown".
enum ListOutcome: Equatable {
    /// The paginator ran to the end. The list is complete.
    case exhausted
    /// The paginator stopped at a self-imposed page cap. The list is a prefix,
    /// and the UI must say so — this is the state that otherwise reads as
    /// "that's all there was".
    case pageCapHit(pagesFetched: Int)
    /// The paginator stopped on an error after some pages. Partial, and the
    /// reason is known.
    case failed(after: Int, outcome: GoogleAPIOutcome)

    /// Whether the researcher is looking at everything there is.
    var isComplete: Bool { self == .exhausted }
}

// MARK: - Artifact availability

/// Whether one artifact is obtainable for one row, resolved at list time.
///
/// §7: "Model artifact availability per item, not per platform." Availability is
/// the conjunction of what the platform can serve, what the granted scopes
/// allow, and whether *this* item is reachable. Resolving it at list time is
/// what lets a row say "roster — needs calendar access" instead of silently
/// having none, and what stops twenty ticked rows returning 403 at fetch time.
enum ArtifactAvailability: Hashable {
    case available
    /// The platform could serve it, but a scope we don't hold is required.
    case needsScope(String)
    /// This account's plan doesn't produce it.
    case notOnThisPlan
    /// We were allowed to look, we looked, and nobody recorded this meeting.
    ///
    /// **Distinct from `.notOnThisPlan`, and the distinction is the whole
    /// reason this case exists.** Both produce an unfetchable row, so the
    /// temptation is to reuse the plan case — which is what Google's adapter
    /// did until 16 Aug 2026, before a single real list had ever run. The
    /// consequence only shows when *every* row is refused, which is an
    /// ordinary month for a researcher who took notes instead of recording:
    /// the window's blanket state then told a paying Workspace customer that
    /// "this account can't record Meet calls", and the fix it implied was to
    /// go and argue with their admin about an edition upgrade they already
    /// have.
    ///
    /// An un-recorded meeting is not a capability failure and must not be
    /// reported as one. Only `GoogleAccountTier.personal` earns
    /// `.notOnThisPlan`, where the claim is literally true.
    case notRecorded
    /// Someone else organised the meeting.
    case notOrganiser(organiser: String?)
    /// Recordings exist on this meeting's link around this time, and none of
    /// them can be told apart well enough to say which is this meeting's.
    ///
    /// **A refusal that costs the researcher a row, chosen over a guess that
    /// costs them a wrong one.** A Meet link is a room, not a meeting, and a
    /// personal room is reused all day — so two sessions can produce two
    /// records that a start time cannot separate. Guessing yields the *other*
    /// session's video filed under this participant's name, which analyses
    /// cleanly and reads as complete. This says so instead, and the recording
    /// is still one Drive visit away.
    case notResolved
    /// The platform doesn't offer it at all.
    case unsupported

    var isAvailable: Bool { self == .available }
}

// MARK: - Row state

// NOTE: The per-row *local file* state (`ImportRowState`) lives in
// CloudImportModel.swift and is shared. It is about files on this Mac —
// present, dataless, wrong size, on an unmounted volume — and none of that is
// platform-specific. Its one platform-flavoured member is the label for a row
// that has vanished from the remote listing; see `CloudImportRow.statusLabel`,
// which overrides it rather than editing the Teams file.

/// One row of the Google Meet import list, after the calendar↔recording join.
///
/// Value type, `Identifiable`, no references to any API client: the whole point
/// is that the list can be built from a live adapter or from fixtures and the
/// UI cannot tell the difference.
struct CloudImportRow: Identifiable, Equatable {
    /// Stable across refreshes. The calendar event id when we have one, else the
    /// Drive file id — never an array index, because the list re-sorts.
    let id: String

    /// The meeting title. From the calendar event's `summary` when the join
    /// matched; otherwise parsed from the recording's filename. Remote data, and
    /// therefore untrusted — §9: `safe_filename()` before it becomes a path
    /// component, `wrap_untrusted()` before it reaches a prompt.
    let title: String

    /// The row's anchor on the clock: when the record button was pressed if we
    /// know, otherwise when the meeting was booked. Sorting, day grouping and
    /// fetch ordering all read this, so it is never nil.
    ///
    /// It is deliberately *not* rendered on its own — the grid draws
    /// `scheduledAt` and `recordedAt` in separate columns, because a researcher
    /// looking at "09:30 / 09:34" learns something a single merged time cannot
    /// tell them.
    let startsAt: Date

    /// When the meeting was **booked** to start, from the calendar.
    ///
    /// Nil for a recording with no calendar event behind it — an instant
    /// meeting, a call started from the Meet home screen. That is not a gap to
    /// be filled: the Scheduled column shows a dash and the row is marked ad
    /// hoc, which is the true state of affairs.
    let scheduledAt: Date?

    /// How long the meeting was booked for — `end − start` on the event.
    /// Rendered under `scheduledAt`, and never confused with `duration`, which
    /// is the recording's own length. The two routinely disagree by an hour.
    let scheduledDuration: TimeInterval?

    /// When the record button was actually pressed. Nil when there is no
    /// recording — which is the honest answer for a meeting nobody recorded,
    /// and the reason this is separate from `startsAt` rather than folded into
    /// it. A row whose Recorded column is a dash has no file behind it.
    let recordedAt: Date?

    /// The meeting this row belongs to. Rows sharing one are recordings of the
    /// **same call**, and the outline nests them under a single meeting row.
    ///
    /// Nil means "this recording has no calendar event" — the ad-hoc case,
    /// which stands alone at meeting level rather than being invented a parent.
    ///
    /// **On Zoom this will need a second thought and the compiler will not ask
    /// for it.** Two Meet children are two interviews; two Zoom children would
    /// be one interview rendered twice (speaker view, gallery view), and
    /// ticking both yields the same 45 minutes analysed as two participants.
    /// The grouping is identical; the meaning is opposite. See
    /// `CloudPlatform.yieldsMultipleMediaFiles`, and `CloudImportOutline.Kind`,
    /// where a `.rendition` case is what would make the compiler ask.
    let meetingID: String?

    /// Which recording of its call this is, 1-based — and **nil when the call
    /// produced only one**, which is the overwhelmingly common case.
    ///
    /// Set by the adapter, which is the only place that knows, rather than
    /// derived from position in a sorted array. That matters for three separate
    /// reasons, and the third is a data-losing bug:
    ///
    /// 1. Swift's sort is not documented as stable, and siblings sort on
    ///    `startsAt` — which is *identical* for both when Google omits the
    ///    recording's `startTime`. Positional ordinals could then swap between
    ///    two renders of the same list.
    /// 2. The outline labels children "Recording 1" / "Recording 2" from it, so
    ///    the label is a fact about the call rather than about the array.
    /// 3. **It disambiguates the filename.** Both siblings carry the same title
    ///    and, on that same nil-`startTime` path, the same `startsAt` — so they
    ///    produced byte-identical destination names, and `publish` deliberately
    ///    overwrites. One file survived, both rows reported "Imported", and the
    ///    terminus said two. That is the segmented-recording loss this feature
    ///    just fixed, reappearing one layer down at the filesystem.
    let siblingOrdinal: Int?

    /// Duration of the *recording* where known, else of the meeting. Nil when
    /// the row is someone else's meeting — we know the event, not the file.
    let duration: TimeInterval?

    /// Bytes, from the Drive listing. Nil for the same reason as `duration`.
    /// Load-bearing for the free-space precheck (§9), which is why it is on the
    /// row rather than fetched later.
    let sizeBytes: Int64?

    /// When the recording disappears. **Nil is the expected value on Google**,
    /// where retention is an admin policy rather than a per-file attribute — so
    /// the Expires column renders "—" rather than a countdown, and that is a
    /// platform difference the UI states rather than hides.
    let expiresAt: Date?

    /// Attendees, already ordered by the §9 degradation ladder. Display only:
    /// only the ones the researcher promotes to participants ever reach disk.
    let attendees: [Attendee]

    /// Local file state — shared with the Teams side.
    let localState: ImportRowState

    /// Per-artifact availability, resolved at list time.
    let video: ArtifactAvailability
    let roster: ArtifactAvailability
    let transcript: ArtifactAvailability

    /// Who organised it, when it wasn't the signed-in user. Present means "not
    /// yours" — and naming them is the point: the fix is to ping them, and a
    /// count is dead weight where a name is a workflow.
    let organiser: Attendee?

    struct Attendee: Equatable, Identifiable {
        /// Stable for the lifetime of the row. Deliberately NOT computed with a
        /// `UUID()` fallback: a computed identity that changes on every read
        /// makes SwiftUI rebuild the row on every redraw, and the symptom
        /// (attendee names flickering during a fetch) reads as a rendering bug
        /// rather than as an identity one.
        let id: String
        /// May be nil: Google returns bare addresses for people outside the
        /// organiser's domain who aren't in any shared directory, which is
        /// exactly the population UR participants belong to.
        let displayName: String?
        /// Held in memory only. §9: emails are a re-identification key and are
        /// never rendered in the list — they earn their place at the "who is
        /// p1?" promotion step.
        let email: String?
        let isSelf: Bool
        let isOrganiser: Bool
        let didDecline: Bool
        /// True when the address's domain differs from the signed-in account's.
        /// An ordering hint, not a claim.
        let isExternal: Bool

        init(
            id: String? = nil,
            displayName: String?,
            email: String?,
            isSelf: Bool = false,
            isOrganiser: Bool = false,
            didDecline: Bool = false,
            isExternal: Bool = false
        ) {
            // Prefer the address (unique within an event by construction), then
            // the name, then a caller-supplied key. All three absent is a
            // malformed attendee, and an empty id is a visible bug rather than
            // a silent one.
            self.id = id ?? email ?? displayName ?? ""
            self.displayName = displayName
            self.email = email
            self.isSelf = isSelf
            self.isOrganiser = isOrganiser
            self.didDecline = didDecline
            self.isExternal = isExternal
        }

        /// What the list shows. Falls back to the local part of the address
        /// rather than the whole address — recognisable, and not a
        /// copy-pasteable identifier sitting in a screenshot.
        var listLabel: String {
            if let displayName, !displayName.isEmpty { return displayName }
            guard let email, let at = email.firstIndex(of: "@") else { return "—" }
            return String(email[..<at])
        }
    }

    /// Explicit rather than memberwise, so the four grid fields can default to
    /// "we don't know" and every adapter that hasn't learned them yet keeps
    /// compiling — and, more usefully, keeps *rendering*: a source that sets
    /// none of them produces exactly the flat one-clock list this type drew
    /// before the grid existed.
    init(
        id: String,
        title: String,
        startsAt: Date,
        duration: TimeInterval?,
        sizeBytes: Int64?,
        expiresAt: Date?,
        attendees: [Attendee],
        localState: ImportRowState,
        video: ArtifactAvailability,
        roster: ArtifactAvailability,
        transcript: ArtifactAvailability,
        organiser: Attendee?,
        scheduledAt: Date? = nil,
        scheduledDuration: TimeInterval? = nil,
        recordedAt: Date? = nil,
        meetingID: String? = nil,
        siblingOrdinal: Int? = nil
    ) {
        self.siblingOrdinal = siblingOrdinal
        self.id = id
        self.title = title
        self.startsAt = startsAt
        self.scheduledAt = scheduledAt
        self.scheduledDuration = scheduledDuration
        self.recordedAt = recordedAt
        self.meetingID = meetingID
        self.duration = duration
        self.sizeBytes = sizeBytes
        self.expiresAt = expiresAt
        self.attendees = attendees
        self.localState = localState
        self.video = video
        self.roster = roster
        self.transcript = transcript
        self.organiser = organiser
    }

    /// Whether this row has a file behind it at all.
    ///
    /// Not the same question as `isSelectable`, which also asks whether we
    /// already hold it. A row can have a recording and be untickable (already
    /// imported); a row can be untickable and have no recording (nobody pressed
    /// record). The footer counts recordings, so it needs this one.
    var hasRecording: Bool { recordedAt != nil || video.isAvailable }

    /// Whether a recording is being **kept from** the researcher — the one
    /// condition that earns the "About recordings permissions" link.
    ///
    /// This asks the remote question directly, and it must, because the
    /// arithmetic that looks equivalent is not. `fetchable < recordings` counts
    /// three purely *local* states as withholding: a file already imported, an
    /// iCloud placeholder in the destination project, and an unmounted external
    /// drive all report `isSelectable == false` while plainly having a
    /// recording. So a returning researcher — the commonest case there is —
    /// would be shown a link about *remote permissions* because they succeeded
    /// last week. The link's argued value is its **absence**; one that appears
    /// after a success is the "trains people to ignore it by the third visit"
    /// failure the design warns about, arriving by the third visit.
    ///
    /// Switched exhaustively rather than defaulted, so a new availability case
    /// has to state which side of this line it falls on.
    var isWithheld: Bool {
        switch video {
        case .available:
            return false
        case .notRecorded:
            // Nothing was withheld, because nothing existed. An ordinary month
            // of un-recorded standups must never raise a permissions question.
            return false
        case .notResolved:
            // Also not a permissions question — the recording is reachable and
            // the failure is ours. Sending the researcher to a page about
            // scopes and plans would be a wrong turn.
            return false
        case .needsScope, .notOnThisPlan, .notOrganiser, .unsupported:
            // Each of these is a decision made at the other end: a scope we
            // don't hold, a plan that doesn't include it, someone else's
            // meeting, a tenant that blocks download. `.needsScope` belongs
            // here even though we cannot see whether a recording exists —
            // being unable to look *is* the permission problem, and it is the
            // most permission-shaped state in the feature.
            return true
        }
    }

    /// Whether this row can be ticked. Local state decides first (an already-held
    /// file is not re-fetchable), then remote availability.
    var isSelectable: Bool {
        guard localState.isSelectable else { return false }
        return video.isAvailable
    }

    /// Whether this row's checkbox draws as ticked.
    ///
    /// **Two ways to be ticked, and they mean different things.** Either the
    /// researcher chose it, or we already hold the file — the second draws
    /// ticked *and disabled*, because it is here and re-fetching would spend an
    /// expiry-limited remote read on a purely local problem.
    ///
    /// One definition, because a meeting header's tri-state checkbox has to
    /// summarise exactly what its children draw. Two copies of this predicate
    /// is a parent reading "mixed" over three boxes that all look ticked.
    func drawsTicked(in ticked: Set<String>) -> Bool {
        ticked.contains(id) || !localState.isSelectable
    }

    /// Whether the row draws a checkbox at all — live, or dead-and-disabled.
    ///
    /// **A dead checkbox and no checkbox say different things**, and collapsing
    /// them was a real loss of information. Nothing at all means *there is no
    /// recording here*. A disabled box means *there is a recording here and you
    /// cannot have it* — which is the state a researcher can act on, by asking
    /// the organiser, re-consenting, or upgrading a plan.
    ///
    /// The settled mockup drew an empty cell for both, including on a row
    /// showing 58 MB of video under "Needs access", and this faithfully
    /// reproduced that. A mockup is where the collapse is easy to miss: the
    /// Status column carried the difference, so the missing checkbox read as
    /// tidy rather than as silence about a file that exists.
    ///
    /// `isWithheld` already drew this line for the permissions link. It draws
    /// the same line here, which is what it should have done from the start.
    var showsCheckbox: Bool {
        guard video.isAvailable || isWithheld else { return false }
        return localState.showsCheckbox
    }

    /// Status-column text. Empty is the common and correct case — the checkbox
    /// already says imported or not, so this carries only what the checkbox
    /// cannot.
    @MainActor
    func statusLabel(_ i18n: I18n) -> String? {
        switch video {
        case .notOrganiser(let organiser):
            return organiser ?? i18n.t("desktop.cloudImport.statusSomeoneElse")
        case .notRecorded:
            return i18n.t("desktop.cloudImport.statusNotRecorded")
        case .notResolved:
            return i18n.t("desktop.cloudImport.statusNotResolved")
        case .notOnThisPlan:
            // Not "Not recorded" — on this branch the meeting's recording
            // status is unknown and unknowable, because the account could
            // never have produced one.
            return i18n.t("desktop.cloudImport.statusNeedsPaidPlan")
        case .needsScope:
            return i18n.t("desktop.cloudImport.statusNeedsAccess")
        case .unsupported:
            return i18n.t("desktop.cloudImport.statusUnavailable")
        case .available:
            break
        }
        // Deliberately platform-neutral. This type is shared by all three
        // adapters, so naming one vendor here renders "No longer in Meet" on a
        // Zoom row. The platform name belongs to `CloudPlatform`, which the
        // window holds; the row does not know which platform it came from.
        if case .noLongerAvailable = localState {
            return i18n.t("desktop.cloudImport.statusNoLongerAvailable")
        }
        return localState.statusLabel(i18n)
    }

    /// Whether this row survives the filter field.
    ///
    /// **Titles and people, not titles alone.** The filter used to test the
    /// title only, which is backwards for a surface whose most identifying
    /// content is the attendee line: a researcher looking for the session with
    /// Simon in it types "Simon", and "P05 Interview" tells them nothing about
    /// whether they found it.
    ///
    /// Three decisions inside this:
    ///
    /// **Diacritic-insensitive, so "Bjorn" finds "Björn".** The old predicate
    /// was `localizedCaseInsensitiveContains`, which is not — while
    /// `TeamsRecordingName.matches(filter:)` next door *is*, and has a test
    /// saying so, and was never called from the window. Two implementations,
    /// different semantics, and the weaker one was the live one.
    ///
    /// **Searches the whole ranked set, not the visible three.** The line shows
    /// the first few names; the filter covers everyone behind the `+N` too.
    /// Same rules, different depth — otherwise a name is findable only when it
    /// happens to fit.
    ///
    /// **Self and decliners are excluded, because `rank` excludes them.** Your
    /// own name would match every row and identify nothing. A decliner is
    /// stronger: "was Simon in that one?" should answer *no* for a meeting
    /// Simon declined, and matching it would be a false positive in exactly the
    /// question the filter exists to answer.
    func matches(filter: String) -> Bool {
        let term = filter.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !term.isEmpty else { return true }
        let options: String.CompareOptions = [.caseInsensitive, .diacriticInsensitive]

        if title.range(of: term, options: options) != nil { return true }
        // The organiser of someone else's meeting is a legitimate search term
        // ("who ran that one?") and is not always present in `attendees`.
        if let organiser, organiser.listLabel.range(of: term, options: options) != nil {
            return true
        }
        return AttendeeLine.rank(attendees).contains {
            $0.listLabel.range(of: term, options: options) != nil
        }
    }
}

// MARK: - The attendee line

/// Composes the one-line attendee summary, degrading in the fixed order §9
/// specifies.
///
/// The order follows from what the line is *for* — identifying which call this
/// is, which means the participant, never the moderator (always the researcher)
/// and rarely the observers (often the same client faces weekly).
enum AttendeeLine {

    /// - Parameter limit: how many names fit. The caller measures; this type
    ///   does not guess at pixels.
    ///
    ///   **The default is three, and it is a claim about research sessions
    ///   rather than about pixels.** A session is the researcher — dropped as
    ///   self — one or two participants, and at most one observer, so three
    ///   surviving names covers the large majority of them without an overflow
    ///   badge appearing on the ordinary case. Two was the original default and
    ///   was too tight for a window whose *minimum* width is 760pt: it put "+1"
    ///   on a routine three-person interview.
    ///
    ///   It remains a floor rather than the answer. The caller is still meant
    ///   to measure and pass a real limit — no call site does yet, which is why
    ///   this default was doing all the work.
    /// - Returns: the names to render and the count of everyone omitted. A
    ///   count, never an ellipsis: "Sarah Chen · J. Whitfield +4" says there are
    ///   six; "Sarah Chen, J. Whit…" says nothing.
    static func compose(
        _ attendees: [CloudImportRow.Attendee],
        limit: Int = 3
    ) -> (names: [String], overflow: Int) {
        let ranked = rank(attendees)
        guard limit > 0 else { return ([], ranked.count) }
        let shown = Array(ranked.prefix(limit))
        return (shown.map(\.listLabel), max(0, ranked.count - shown.count))
    }

    /// The whole subtitle, ready to render: `Sarah Chen · J. Whitfield  +4`, or
    /// the organiser's name on someone else's meeting, or nothing.
    ///
    /// Here rather than private to the outline's coordinator, where it was, so
    /// it can be reached by a test — `desktop/CLAUDE.md` § Testing: "if a
    /// SwiftUI view is making a decision, the decision belongs in a testable
    /// helper". Three decisions live in these eight lines, and each is one the
    /// review log has already had to argue once.
    ///
    /// - Returns: nil when there is nothing to say. **Nothing, not "0
    ///   attendees"** — a meeting with no invitees is an ordinary meeting, and
    ///   announcing the zero is chrome for a non-event.
    static func summary(
        _ attendees: [CloudImportRow.Attendee],
        organiser: CloudImportRow.Attendee?,
        limit: Int = 3
    ) -> String? {
        let (names, overflow) = compose(attendees, limit: limit)
        guard !names.isEmpty else {
            // Someone else's meeting: their name is the workflow — the fix is
            // to ping them — where a count would be dead weight.
            if let organiser { return organiser.listLabel }
            // Names existed and were all shed: you, decliners, resources. The
            // count is the honest residue and worth saying.
            return attendees.isEmpty ? nil : CloudCount.noun(attendees.count, "attendee")
        }
        let joined = names.joined(separator: " · ")
        // A count, not an ellipsis: "+4" says there are six.
        return overflow > 0 ? "\(joined)  +\(overflow)" : joined
    }

    /// Drop yourself, drop decliners, order by externality.
    ///
    /// `isExternal` is an ordering hint, not a claim: when it is wrong the only
    /// cost is seeing a different name first. Sorting is stable within each
    /// group so the platform's own ordering survives where we have no opinion.
    static func rank(_ attendees: [CloudImportRow.Attendee]) -> [CloudImportRow.Attendee] {
        attendees
            .filter { !$0.isSelf && !$0.didDecline }
            .enumerated()
            .sorted { lhs, rhs in
                if lhs.element.isExternal != rhs.element.isExternal {
                    return lhs.element.isExternal
                }
                return lhs.offset < rhs.offset
            }
            .map(\.element)
    }
}

// MARK: - The join's arithmetic

/// The permanently-visible footer line: `N in window · M you can fetch ·
/// N−M unmatched`.
///
/// §6's first "thing that makes a batch honest". The calendar↔recording join is
/// an inner join over two independently-paginated, independently-windowed
/// lists, and its intended output is "shorter than your calendar" — which is
/// also what every failure mode produces. Stating the arithmetic is the only
/// place in the design where a data-losing failure becomes visible.
struct JoinArithmetic: Equatable {
    /// Calendar events in the window, before the join.
    let eventsInWindow: Int
    /// Rows the researcher can actually fetch.
    let fetchable: Int
    /// Rows present but organised by someone else.
    let organisedByOthers: Int
    /// How the listing terminated. A capped or failed paginator makes every
    /// count above a lower bound rather than a total, and the UI must not print
    /// a confident number over an incomplete read.
    let outcome: ListOutcome

    /// Events in the window with no fetchable recording and no named organiser
    /// — the genuinely unexplained remainder. Never negative: a negative here
    /// would mean the join produced more rows than the window held, which is a
    /// bug, and clamping keeps a bug from rendering as a nonsense sentence.
    var unmatched: Int {
        max(0, eventsInWindow - fetchable - organisedByOthers)
    }

    /// Whether the numbers can be presented as totals rather than as a floor.
    var isExact: Bool { outcome.isComplete }
}
