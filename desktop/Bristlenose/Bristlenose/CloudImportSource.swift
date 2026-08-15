import Foundation

// The seam between the import window and where its rows come from.
//
// Two implementations from the outset, both real:
//   • `GoogleMeetSource`   — live Google Calendar + Drive/Meet APIs.
//   • `FixtureCloudSource`  — recorded/derived shapes, no network, no account.
//
// This is NOT the `CallSource` abstraction docs/design-cloud-import.md §7 warns
// against ("at n=1 that is Speculative Generality"). That warning is about
// abstracting over *platforms* before a second platform exists. This protocol
// abstracts over *transports* for one platform, and it has two implementations
// on the day it is written — one of which is the only way the window's nine
// states can be driven at all without a paid Workspace tenant and a recorded
// meeting.
//
// The discipline that keeps it honest: the fixture source must be reachable
// only from the Diagnostics menu, and the window must not know which one it
// holds. If a view ever needs to ask "am I on fixtures?", the seam has leaked.

// MARK: - What a listing is

/// One complete answer to "what could I import right now".
struct MeetingListing: Equatable {
    var rows: [CloudImportRow]
    var arithmetic: JoinArithmetic
    /// The window that was asked for, so the UI can say "last 30 days" without
    /// re-deriving it and drifting from what was actually queried.
    var window: DateInterval
}

/// Progress for one file in flight.
struct FetchProgress: Equatable {
    let rowID: String
    /// 0…1, or nil while the total size is unknown.
    let fraction: Double?
    let bytesWritten: Int64
    let bytesExpected: Int64?
}

/// The outcome of one row's fetch. Per-row, never per-batch: §6's "the unit of
/// recovery is the file, not the batch".
enum FetchOutcome: Equatable {
    case imported(bytes: Int64)
    /// Carries a *sentence*, not a code — this string is rendered in the row.
    case failed(reason: String, isRetryable: Bool)
    case cancelled
}

// MARK: - The protocol

protocol CloudImportSource: AnyObject {
    /// The signed-in account, or nil when signed out. Rendered read-only in the
    /// window's subtitle; sign-out lives in Settings ▸ Accounts, per §9's "one
    /// place to disconnect, not two".
    var accountEmail: String? { get }

    /// The account's tier, which decides whether recordings can exist at all.
    var accountTier: GoogleAccountTier { get }

    /// Present the provider's own consent UI. Throws on user cancellation.
    func signIn() async throws

    /// List everything in the window. Never throws: a listing that partly
    /// failed is still a listing, and the failure rides in
    /// `arithmetic.outcome` where the UI can render it. Throwing would discard
    /// the rows that *did* arrive — which is the shorter-list failure this
    /// design exists to make visible.
    func list(window: DateInterval) async -> MeetingListing

    /// Fetch one row's media into `destination`.
    ///
    /// One row at a time, by design: the caller owns concurrency (bounded at
    /// 3–4 per §9) and the ordering (soonest-expiring first, regardless of
    /// display sort).
    func fetch(
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome
}

// MARK: - Fixtures

/// The nine states of docs/mockups/cloud-import-states.html, plus the ones
/// Google adds, drivable without an account.
///
/// This is not a toy. It is how the window's failure states get exercised at
/// all: every one of them — a capped paginator, a declined scope, a personal
/// account with a full calendar and no recordings, a partial batch — is
/// unreachable from a happy-path live account, and several are unreachable
/// without a paid Workspace tenant that does not exist yet.
enum CloudImportScenario: String, CaseIterable, Identifiable {
    case signedOut
    case loading
    case populated
    case personalAccountNoRecordings
    case emptyWindow
    case allAlreadyImported
    case someoneElsesMeetings
    case scopeDeclined
    case paginatorCapped
    case partialFailure

    var id: String { rawValue }

    /// Menu titles. English-only on purpose: this is a Diagnostics surface, and
    /// the project's rule is that debug harnesses do not consume translator
    /// budget.
    var menuTitle: String {
        switch self {
        case .signedOut:                   return "Signed Out"
        case .loading:                     return "Loading"
        case .populated:                   return "Populated List"
        case .personalAccountNoRecordings: return "Personal Account (no recordings)"
        case .emptyWindow:                 return "No Recordings in Window"
        case .allAlreadyImported:          return "All Already Imported"
        case .someoneElsesMeetings:        return "Organised by Someone Else"
        case .scopeDeclined:               return "Drive Scope Declined"
        case .paginatorCapped:             return "Paginator Capped (partial list)"
        case .partialFailure:              return "Partial Failure After Fetch"
        }
    }
}

/// A `CloudImportSource` backed by generated shapes rather than a network.
///
/// Dates are computed relative to a fixed `now` passed in, so the same scenario
/// renders identically on any day — a fixture whose rows drift with the wall
/// clock stops being a fixture.
final class FixtureCloudSource: CloudImportSource {
    private let scenario: CloudImportScenario
    private let platform: CloudPlatform
    private let now: Date
    private var signedIn: Bool

    init(scenario: CloudImportScenario, platform: CloudPlatform = .meet, now: Date = Date()) {
        self.scenario = scenario
        self.platform = platform
        self.now = now
        self.signedIn = (scenario != .signedOut)
    }

    /// The address shape differs per platform, and it is not cosmetic: the
    /// tier that yields a full calendar and zero recordings is a consumer
    /// account on Google and a Basic-plan work address on Zoom, so a fixture
    /// that always showed a consumer address would exercise the wrong sentence.
    var accountEmail: String? {
        guard signedIn else { return nil }
        guard scenario == .personalAccountNoRecordings else {
            return "martin@stmarystrust.example"
        }
        switch platform {
        case .meet:  return "m.storey@gmail.com"
        case .teams: return "m.storey@outlook.example"
        case .zoom:  return "martin@stmarystrust.example"
        }
    }

    var accountTier: GoogleAccountTier { GoogleAccountTier(email: accountEmail) }

    func signIn() async throws {
        // A beat, so the sign-in state is actually observable in the UI rather
        // than flashing past.
        try? await Task.sleep(for: .milliseconds(400))
        signedIn = true
    }

    func list(window: DateInterval) async -> MeetingListing {
        if scenario == .loading {
            // Long enough to see the loading state and read it. Cancellable.
            try? await Task.sleep(for: .seconds(600))
        } else {
            try? await Task.sleep(for: .milliseconds(350))
        }
        return MeetingListing(
            rows: rows(),
            arithmetic: arithmetic(),
            window: window
        )
    }

    func fetch(
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        let total = row.sizeBytes ?? 800_000_000
        var written: Int64 = 0
        let steps = 24
        for step in 1...steps {
            if Task.isCancelled { return .cancelled }
            try? await Task.sleep(for: .milliseconds(90))
            written = Int64(Double(total) * Double(step) / Double(steps))
            progress(FetchProgress(
                rowID: row.id,
                fraction: Double(step) / Double(steps),
                bytesWritten: written,
                bytesExpected: total
            ))
            // The partial-failure scenario fails two named rows mid-transfer,
            // so the retry path and the "2 imported · 2 failed" terminus are
            // reachable without unplugging a network cable.
            if scenario == .partialFailure, step == 17 {
                if row.id == "evt-p06" {
                    return .failed(reason: "Lost connection at 71%", isRetryable: true)
                }
                if row.id == "evt-p07" {
                    return .failed(reason: "Not enough disk space", isRetryable: false)
                }
            }
        }
        return .imported(bytes: total)
    }

    // MARK: Shapes

    private func day(_ daysAgo: Int, hour: Int, minute: Int = 0) -> Date {
        let cal = Calendar.current
        let base = cal.date(byAdding: .day, value: -daysAgo, to: now) ?? now
        return cal.date(bySettingHour: hour, minute: minute, second: 0, of: base) ?? base
    }

    /// Attendee sets deliberately include the hard cases: a name too long for
    /// the column, an external participant with no display name at all (the
    /// shape Google returns for someone outside the directory), and a decliner
    /// who must be dropped from the line.
    private func participants(_ n: Int) -> [CloudImportRow.Attendee] {
        let pool: [(String?, String)] = [
            ("Sarah Chen", "s.chen@nhs.example"),
            ("Margarethe Okafor-Whitcombe", "m.okafor-whitcombe@nhs.example"),
            (nil, "j.whitfield@outlook.example"),
            ("A. Bianchi", "a.bianchi@nhs.example"),
            ("D. Achebe", "d.achebe@stmarystrust.example"),
            ("L. Fitzgerald", "l.fitzgerald@stmarystrust.example"),
            ("R. Nakamura", "r.nakamura@nhs.example"),
        ]
        let domain = accountTier.organisationDomain
        var out: [CloudImportRow.Attendee] = [
            CloudImportRow.Attendee(
                displayName: "Martin Storey",
                email: accountEmail,
                isSelf: true,
                isOrganiser: true,
                isExternal: false
            )
        ]
        for (name, email) in pool.prefix(n) {
            let external = domain.map { !email.hasSuffix("@\($0)") } ?? true
            out.append(CloudImportRow.Attendee(
                displayName: name,
                email: email,
                isExternal: external
            ))
        }
        // One decliner, to prove the line drops them.
        out.append(CloudImportRow.Attendee(
            displayName: "K. Lindqvist",
            email: "k.lindqvist@stmarystrust.example",
            didDecline: true,
            isExternal: false
        ))
        return out
    }

    private func row(
        id: String,
        title: String,
        daysAgo: Int,
        hour: Int,
        minute: Int = 0,
        minutes: Int,
        gigabytes: Double,
        people: Int = 3,
        local: ImportRowState = .notImported,
        video: ArtifactAvailability = .available,
        organiser: CloudImportRow.Attendee? = nil
    ) -> CloudImportRow {
        CloudImportRow(
            id: id,
            title: title,
            startsAt: day(daysAgo, hour: hour, minute: minute),
            duration: organiser == nil ? TimeInterval(minutes * 60) : nil,
            sizeBytes: organiser == nil ? Int64(gigabytes * 1_073_741_824) : nil,
            // Nil on Google, and that is a finding rather than an omission:
            // Drive has no per-file retention attribute, so there is nothing to
            // count down and the column is absent entirely. Platforms that DO
            // expose one get a real date, so the "earn the red" rule — only
            // rows inside the danger window are warning-coloured — is actually
            // exercised by the fixture rather than asserted in a comment.
            expiresAt: platform.hasPerFileExpiry
                ? Calendar.current.date(byAdding: .day, value: max(2, 60 - daysAgo), to: now)
                : nil,
            attendees: participants(people),
            localState: local,
            video: video,
            roster: .available,
            transcript: .available,
            organiser: organiser
        )
    }

    private func rows() -> [CloudImportRow] {
        switch scenario {
        case .signedOut, .loading, .emptyWindow:
            return []

        case .personalAccountNoRecordings:
            // The trap this scenario exists for: a full, convincing calendar
            // where every single row is unfetchable. Google's personal tier
            // cannot record a Meet call, so the list must say so once rather
            // than letting the researcher tick ten rows and fail ten times.
            return [
                row(id: "evt-p07", title: "P07 Interview — ward handover",
                    daysAgo: 3, hour: 16, minutes: 58, gigabytes: 1.3,
                    video: .notOnThisPlan),
                row(id: "evt-p06", title: "P06 Interview — ward handover",
                    daysAgo: 3, hour: 14, minute: 30, minutes: 64, gigabytes: 1.4,
                    video: .notOnThisPlan),
                row(id: "evt-sync", title: "Weekly sync — design",
                    daysAgo: 3, hour: 9, minute: 30, minutes: 27, gigabytes: 0.6,
                    people: 5, video: .notOnThisPlan),
            ]

        case .allAlreadyImported:
            return [
                row(id: "evt-p07", title: "P07 Interview — ward handover",
                    daysAgo: 3, hour: 16, minutes: 58, gigabytes: 1.3,
                    local: .imported),
                row(id: "evt-p06", title: "P06 Interview — ward handover",
                    daysAgo: 3, hour: 14, minute: 30, minutes: 64, gigabytes: 1.4,
                    local: .imported),
                // On an unplugged volume: still ticked and disabled, because
                // re-fetching from Meet is the wrong fix for a drive that needs
                // plugging in.
                row(id: "evt-p05", title: "P05 Interview — ward handover",
                    daysAgo: 4, hour: 11, minutes: 51, gigabytes: 1.1,
                    local: .driveNotConnected(volume: "T7")),
                // Wrong size: unticked and enabled, because this one genuinely
                // does need re-fetching. Same past fact, opposite remedy.
                row(id: "evt-p03", title: "P03 Interview — triage",
                    daysAgo: 11, hour: 10, minutes: 55, gigabytes: 1.2,
                    local: .damaged),
            ]

        case .someoneElsesMeetings:
            let bianchi = CloudImportRow.Attendee(
                displayName: "A. Bianchi", email: "a.bianchi@nhs.example",
                isOrganiser: true, isExternal: true
            )
            return [
                row(id: "evt-p07", title: "P07 Interview — ward handover",
                    daysAgo: 3, hour: 16, minutes: 58, gigabytes: 1.3),
                // Length and expiry are "—" here, deliberately: those come from
                // the recording, and we cannot see it. We know the meeting and
                // the organiser from the calendar; whether it was recorded at
                // all would need a scope this design refuses.
                row(id: "evt-dis2", title: "Discharge pathway — session 2",
                    daysAgo: 4, hour: 10, minutes: 0, gigabytes: 0,
                    video: .notOrganiser(organiser: "A. Bianchi"),
                    organiser: bianchi),
                row(id: "evt-p05b", title: "P05b Interview — ward handover",
                    daysAgo: 4, hour: 16, minute: 30, minutes: 69, gigabytes: 1.5,
                    video: .notOrganiser(organiser: "A. Bianchi"),
                    organiser: bianchi),
            ]

        case .scopeDeclined:
            // Granular consent: the researcher allowed Calendar and declined
            // Drive on the same screen. The meetings are all there and none of
            // the media is — which must read as one fixable sentence, not as
            // eleven broken rows.
            return (0..<4).map { i in
                row(id: "evt-s\(i)", title: "P0\(7 - i) Interview — ward handover",
                    daysAgo: 3 + i, hour: 16 - i, minutes: 58, gigabytes: 1.3,
                    video: .needsScope("drive.readonly"))
            }

        default:
            var list = [
                row(id: "evt-p07", title: "P07 Interview — ward handover",
                    daysAgo: 3, hour: 16, minutes: 58, gigabytes: 1.3),
                row(id: "evt-p06", title: "P06 Interview — ward handover",
                    daysAgo: 3, hour: 14, minute: 30, minutes: 64, gigabytes: 1.4),
                row(id: "evt-sync", title: "Weekly sync — design",
                    daysAgo: 3, hour: 9, minute: 30, minutes: 27, gigabytes: 0.6,
                    people: 5),
                row(id: "evt-p05", title: "P05 Interview — ward handover",
                    daysAgo: 4, hour: 11, minutes: 51, gigabytes: 1.1),
                row(id: "evt-p04", title: "P04 Interview — triage",
                    daysAgo: 9, hour: 15, minute: 15, minutes: 71, gigabytes: 1.6,
                    local: .imported),
                row(id: "evt-p03", title: "P03 Interview — triage",
                    daysAgo: 11, hour: 10, minutes: 55, gigabytes: 1.2,
                    local: .damaged),
                row(id: "evt-p02", title: "P02 Interview — triage",
                    daysAgo: 19, hour: 13, minutes: 62, gigabytes: 1.3,
                    local: .notDownloaded(provider: "Dropbox")),
                row(id: "evt-p01", title: "P01 Interview — triage",
                    daysAgo: 26, hour: 9, minutes: 49, gigabytes: 1.0),
            ]
            if scenario == .paginatorCapped {
                list = Array(list.prefix(5))
            }
            return list
        }
    }

    private func arithmetic() -> JoinArithmetic {
        let rs = rows()
        let fetchable = rs.filter(\.isSelectable).count
        let others = rs.filter { $0.organiser != nil }.count
        switch scenario {
        case .emptyWindow:
            return JoinArithmetic(eventsInWindow: 11, fetchable: 0,
                                  organisedByOthers: 0, outcome: .exhausted)
        case .paginatorCapped:
            return JoinArithmetic(eventsInWindow: 14, fetchable: fetchable,
                                  organisedByOthers: others,
                                  outcome: .pageCapHit(pagesFetched: 5))
        case .personalAccountNoRecordings:
            return JoinArithmetic(eventsInWindow: rs.count, fetchable: 0,
                                  organisedByOthers: 0, outcome: .exhausted)
        default:
            return JoinArithmetic(eventsInWindow: max(11, rs.count),
                                  fetchable: fetchable,
                                  organisedByOthers: others,
                                  outcome: .exhausted)
        }
    }
}
