import Foundation
import OSLog
import SwiftUI

/// The import window's state machine.
///
/// Everything the window decides lives here rather than in the view, per
/// `desktop/CLAUDE.md` § Testing: "if a SwiftUI view is making a decision, the
/// decision belongs in a testable helper". The view below it is a renderer.
///
/// Holds a `CloudImportSource` and never asks which kind it is.
@MainActor
final class CloudImportStore: ObservableObject {

    /// What the window is showing. One enum rather than a handful of booleans,
    /// because the states are mutually exclusive and a boolean soup makes
    /// "loading and also showing a stale list" representable.
    enum Phase: Equatable {
        case signedOut
        case signingIn
        case loading
        case loaded
        /// A sign-in that ended in a real error, and whether trying again could
        /// plausibly work.
        ///
        /// **It is not a listing failure**, whatever this comment used to say —
        /// and the old wording is worth recording, because the window built its
        /// Try-again button on it and had that button re-run `load()`. There is
        /// exactly one construction site and it is the sign-in catch below, so
        /// the listing has never been the thing that failed, and retrying it
        /// with no token was never going to help. A partly-succeeded listing is
        /// `.loaded` with a non-exhausted outcome; a listing that fails outright
        /// does not reach here.
        ///
        /// `worthRetrying` is false for the two Entra walls — the admin one and
        /// Conditional Access — where the same click yields the same refusal
        /// forever. Anything we cannot classify is presumed retryable: offering
        /// a button that turns out not to help is the recoverable way to be
        /// wrong, and withholding one from someone a retry would have rescued is
        /// not.
        case failed(String, worthRetrying: Bool)

        /// The consent flow ended and we hold no credentials.
        ///
        /// Deliberately NOT folded into `.failed`, and not called "cancelled":
        /// on Zoom and Teams the commonest cause is an admin approval the
        /// researcher cannot grant themselves, enforced on the vendor's own
        /// consent screen before any redirect — so no error ever reaches this
        /// app. From here, "you cancelled" and "your organisation has to
        /// approve this first" are indistinguishable, and telling someone they
        /// cancelled when they were blocked sends them to try again, forever.
        case signInIncomplete
    }

    /// Phase transitions, because the window's whole visible state is this
    /// enum and a stuck spinner is indistinguishable from a slow one.
    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import")

    @Published private(set) var phase: Phase = .signedOut {
        didSet {
            guard phase != oldValue else { return }
            Self.log.notice("""
                import_phase \(String(describing: oldValue), privacy: .public) \
                -> \(String(describing: self.phase), privacy: .public)
                """)
        }
    }
    @Published private(set) var listing: MeetingListing? { didSet { rebuild() } }
    @Published private(set) var accountEmail: String?

    /// The listing's rows **with the destination scan applied** — the one
    /// place the list is read from.
    ///
    /// Nothing outside `rebuild()` may read `listing.rows`, and that is the
    /// whole point of it being stored. `fetchOrder` used to read the listing
    /// directly while the outline read a marked copy, which is a split that
    /// costs nothing until the two disagree: the window would draw a row as
    /// already held while the batch quietly fetched it anyway.
    @Published private(set) var rows: [CloudImportRow] = []

    /// Recordings measured in the destination folder, or empty when there is
    /// no destination yet. An input to `rebuild()` alongside the listing and
    /// the filter — it arrives on its own schedule and must not depend on
    /// which of the two landed first.
    @Published private(set) var destinationRecordings: [LocalRecording] = [] {
        didSet { rebuild() }
    }

    /// The list as the grid draws it: days, meetings, recordings, plus the three
    /// counts the footer is allowed to state.
    ///
    /// Stored rather than computed, because it is read once per render and the
    /// renders are frequent — a fetch publishes progress several times a second
    /// and rebuilding the tree on each would be work nobody asked for. It is
    /// recomputed exactly when its inputs move: a new listing, or a new filter.
    @Published private(set) var outline: CloudImportOutline.Result = .empty

    /// Meetings the researcher has collapsed, this session.
    ///
    /// Expanded is the default and the point: nesting exists to *show* that one
    /// call produced two files. A collapse is a deliberate act and survives
    /// filtering, which is the state a rebuild would otherwise throw away on
    /// every keystroke. Not yet persisted across launches — the mockup lists
    /// that as owed.
    @Published var collapsedMeetings: Set<String> = []

    /// Ticked rows. Intent, and durable across filter changes — which is the
    /// whole argument for checkboxes over selection: ticking three under
    /// "Interview", clearing the filter and adding two more has to survive.
    @Published var ticked: Set<String> = []

    /// Keyboard focus. Exactly one row, and deliberately not the same thing as
    /// a tick — one model for intent, one for navigation.
    @Published var focusedRowID: String?

    @Published var filterText: String = "" { didSet { rebuild() } }

    /// Per-row fetch state, keyed by row id.
    @Published private(set) var progress: [String: FetchProgress] = [:]
    @Published private(set) var outcomes: [String: FetchOutcome] = [:]
    @Published private(set) var isFetching = false

    /// Rolling window. 30 days per §9 — "~95% of what you want is recent";
    /// going further back is a different intent, not a longer scroll.
    @Published var windowDays: Int = 30

    private let source: CloudImportSource
    /// Only for `durationTolerance` — the store still never asks its source
    /// which kind it is. The tolerance is a property of where the *duration*
    /// came from, so it cannot be a constant here.
    private let platform: CloudPlatform
    private var listTask: Task<Void, Never>?
    private var fetchTask: Task<Void, Never>?
    private var scanTask: Task<Void, Never>?

    /// Bounded concurrency. §9: the benefit is resilience — one stalled file
    /// doesn't block the batch — not throughput, since a single 1.3 GB transfer
    /// already saturates a modest uplink.
    private let maxConcurrentFetches = 3

    init(source: CloudImportSource, platform: CloudPlatform = .meet) {
        self.source = source
        self.platform = platform
        self.accountEmail = source.accountEmail
        self.phase = source.accountEmail == nil ? .signedOut : .loading
    }

    // MARK: - Derived

    /// Bumped whenever `outline` is replaced, and never otherwise.
    ///
    /// The view compares it to decide whether a *structural* pass is needed at
    /// all. Without it, every progress tick — several a second per in-flight
    /// file — walked the whole tree twice, once to build a fingerprint it then
    /// threw away and once to resolve the focused row, in order to conclude
    /// that nothing had changed.
    @Published private(set) var outlineGeneration: Int = 0

    /// Recompute `rows` and `outline` from the three things they depend on:
    /// the listing, the destination scan, and the filter.
    ///
    /// The scan is applied **before** the filter, not after, so a row hidden by
    /// a filter keystroke is still marked when the filter clears — and, more
    /// importantly, so `fetchOrder` sees the same marks the window drew.
    private func rebuild() {
        let listed = listing?.rows ?? []
        let held = CloudImportLocalMatch.alreadyPresent(
            rows: listed,
            local: destinationRecordings,
            platform: platform)
        rows = listed.map { held.contains($0.id) ? $0.markedAsAlreadyInProject() : $0 }

        // The predicate lives on the row — titles *and* people, diacritic-
        // insensitive, covering names behind the `+N` overflow. See
        // `CloudImportRow.matches(filter:)` for why each of those is deliberate.
        let filtered = rows.filter { $0.matches(filter: filterText) }
        outline = CloudImportOutline.build(rows: filtered)
        outlineGeneration &+= 1
    }

    /// Point the check at the chosen project's folder, or at nothing.
    ///
    /// Called on every destination change, because the answer is a fact about
    /// *that* folder: the same listing against two projects has two different
    /// sets of already-held rows, and a stale answer is the one that withholds
    /// a recording the researcher does not have.
    ///
    /// A nil folder — the popup still reading "New Project…" — clears the
    /// marks rather than leaving the previous project's. There is nothing in
    /// an unnamed project yet, so every row is fetchable, which is true.
    func setDestination(_ folder: URL?) {
        scanTask?.cancel()
        guard let folder else {
            destinationRecordings = []
            return
        }
        scanTask = Task { [weak self] in
            let found = await CloudImportLocalMatch.scan(folder: folder)
            // A destination changed while the scan ran. Publishing now would
            // mark rows against a folder the researcher has already left.
            guard !Task.isCancelled else { return }
            self?.applyDestinationScan(found)
        }
    }

    /// Publish what a scan measured.
    ///
    /// Split out from `setDestination` because the measurement and its
    /// consequences are worth exercising apart: a folder of real 50-minute
    /// recordings is not something a test can conjure, while "a held row
    /// leaves the batch" is exactly what has to be pinned.
    func applyDestinationScan(_ found: [LocalRecording]) {
        destinationRecordings = found
    }

    /// Rows after the filter, **in the order they appear on screen**.
    ///
    /// Derived from the outline rather than sorted independently, because the
    /// two would drift and only one of them is what the researcher's eye used.
    /// Range selection is the case that would break first: shift-clicking from
    /// Monday to Wednesday has to tick what lies between them *as drawn* —
    /// days newest-first, rows within a day oldest-first — and a second sort
    /// order here would silently tick a different set.
    var visibleRows: [CloudImportRow] {
        outline.days.flatMap { day in
            day.children.flatMap { node -> [CloudImportRow] in
                if node.children.isEmpty { return node.row.map { [$0] } ?? [] }
                return node.children.compactMap(\.row)
            }
        }
    }

    /// Ticked rows that are still tickable, in the order they will actually be
    /// fetched.
    ///
    /// **Display order is the user's; fetch order is expiry's** (§9). An
    /// interrupted batch must not lose exactly the files closest to deletion,
    /// so this sorts soonest-expiring first regardless of how the table is
    /// sorted. Rows with no expiry — which on Google is all of them, since
    /// retention is an admin policy — fall back to oldest-first, on the same
    /// reasoning one level down: the oldest recording is the one nearest
    /// whatever policy eventually removes it.
    /// Reads `rows`, never `listing`. A row the destination already holds is
    /// not selectable, so it drops out here — which is what keeps a stale tick
    /// from fetching a file the window has just drawn as held. That also means
    /// the Import button's count falls as the scan lands, which is the honest
    /// reading of "you already have two of these".
    var fetchOrder: [CloudImportRow] {
        rows
            .filter { ticked.contains($0.id) && $0.isSelectable }
            .sorted { lhs, rhs in
                switch (lhs.expiresAt, rhs.expiresAt) {
                case let (l?, r?): return l < r
                case (nil, _?):    return false
                case (_?, nil):    return true
                case (nil, nil):   return lhs.startsAt < rhs.startsAt
                }
            }
    }

    var tickedCount: Int { fetchOrder.count }

    /// Total bytes the current tick set will pull. Feeds the free-space
    /// precheck, which §9 requires *before a byte moves* — both platforms carry
    /// size in the listing, so it costs nothing and a mid-batch ENOSPC has
    /// already burned real transfer time.
    var tickedBytes: Int64 {
        fetchOrder.reduce(0) { $0 + ($1.sizeBytes ?? 0) }
    }

    /// Whether every row in the list is unfetchable for the *same* reason. When
    /// true the window says it once, at the top, instead of repeating it on
    /// every row — the difference between one sentence and eleven dead ticks.
    var blanketRefusal: ArtifactAvailability? {
        guard !rows.isEmpty else { return nil }
        let reasons = Set(rows.map(\.video))
        guard reasons.count == 1, let only = reasons.first, !only.isAvailable else { return nil }
        return only
    }

    /// The terminus (§6's fourth honest-batch requirement):
    /// `20 requested · 18 imported · 2 failed`. Nil until a batch has run.
    var terminus: (requested: Int, imported: Int, failed: Int)? {
        guard !outcomes.isEmpty else { return nil }
        var imported = 0, failed = 0
        for outcome in outcomes.values {
            switch outcome {
            case .imported: imported += 1
            case .failed:   failed += 1
            case .cancelled: break
            }
        }
        return (outcomes.count, imported, failed)
    }

    // MARK: - Actions

    private var signInTask: Task<Void, Never>?

    /// Bumped on every start and every cancel, so a sign-in the researcher has
    /// walked away from cannot come back later and overwrite the phase they
    /// are now looking at.
    private var signInGeneration = 0

    func signIn() {
        signInTask?.cancel()
        signInGeneration &+= 1
        let mine = signInGeneration
        phase = .signingIn
        signInTask = Task { @MainActor [weak self] in
            guard let self else { return }
            do {
                try await self.source.signIn()
                guard self.signInGeneration == mine else { return }
                guard self.source.accountEmail != nil else {
                    // Signed in, apparently, but no account came back. On the
                    // admin-gated platforms this is the pre-approval wall.
                    self.phase = .signInIncomplete
                    return
                }
                self.accountEmail = self.source.accountEmail
                await self.load()
            } catch let error as ZoomOAuthError where error == .cancelled {
                guard self.signInGeneration == mine else { return }
                self.phase = .signInIncomplete
            } catch let error as GoogleOAuthError where error == .cancelled {
                guard self.signInGeneration == mine else { return }
                self.phase = .signInIncomplete
            } catch let error as MicrosoftOAuthError where error == .cancelled {
                // Third of three, and it was missing — so closing the Teams
                // sign-in window landed on the error screen while doing the same
                // thing on Meet or Zoom landed on the calm one. Abandoning a
                // sign-in is not a fault on any platform.
                guard self.signInGeneration == mine else { return }
                self.phase = .signInIncomplete
            } catch {
                guard self.signInGeneration == mine else { return }
                // The refusal itself knows whether a second attempt could
                // differ; nothing else in this app does.
                let refusal = (error as? MicrosoftOAuthError)?.refusal
                self.phase = .failed(error.localizedDescription,
                                     worthRetrying: refusal?.isWorthRetrying ?? true)
            }
        }
    }

    /// Give up on a sign-in that is not coming back.
    ///
    /// **On macOS `ASWebAuthenticationSession` opens the researcher's real
    /// default browser, not an embedded view** — so when they abandon the tab,
    /// close it, or simply lose it behind another window, nothing reports a
    /// cancellation and the `await` never returns. Measured 17 Aug 2026:
    /// `import_phase signedOut -> signingIn` and then silence, with the window
    /// spinning indefinitely and no way out but quitting the app.
    ///
    /// Deliberately **not** a timeout. A real sign-in can legitimately take
    /// minutes — a password, then 2FA, then an account chooser — so any
    /// deadline long enough to be safe is far too long to be useful, and any
    /// deadline short enough to be useful cancels people mid-password. The
    /// honest mechanism is to say what we are waiting for and let them stop.
    ///
    /// The in-flight session is not itself cancellable; bumping the generation
    /// is what makes its eventual return inert.
    func cancelSignIn() {
        signInTask?.cancel()
        signInTask = nil
        signInGeneration &+= 1
        phase = .signedOut
    }

    func load() async {
        listTask?.cancel()
        phase = .loading
        // **The trailing edge is now + 3h, not now, and it is the same fact as
        // the Meet lookup's 3h lookback seen from the other side.**
        //
        // A recording exists on the clock the *call* ran on; the listing is
        // filtered on the clock the *event* was scheduled for. Google's
        // `timeMax` bounds an event's START (an overlap query, not a
        // containment one), so ending the window at this instant excludes any
        // meeting whose scheduled start is still in the future — including one
        // that has already been recorded, which is the routine case for anyone
        // who opens the room early. Observed 16 Aug 2026: a call joined at
        // 2:12pm against a 3:00pm event would have listed as nothing at all
        // until 3pm, with no error to say why.
        //
        // Three hours because that is the tolerance the recording lookup
        // already allows in the other direction; a narrower one here would make
        // that tolerance unreachable for the most recent meetings, which are
        // exactly the ones a researcher opens this window to find. Harmless for
        // Teams and Zoom, which filter on the recording's own timestamp and
        // simply have nothing in the future to return.
        let now = Date()
        let interval = DateInterval(
            start: Calendar.current.date(byAdding: .day, value: -windowDays, to: now) ?? now,
            end: now.addingTimeInterval(3 * 3600)
        )
        let task = Task { @MainActor in
            let result = await source.list(window: interval)
            guard !Task.isCancelled else {
                // The one path that leaves the window on its spinner forever:
                // a superseded listing returns, its result is dropped, and
                // `phase` is never moved off `.loading`. Correct when a newer
                // `load()` is going to finish — and indistinguishable from a
                // hang when there isn't one, which is why it now says so.
                Self.log.notice("import_list superseded, result discarded")
                return
            }
            Self.log.notice("import_list returned, applying")
            listing = result
            accountEmail = source.accountEmail
            phase = .loaded
            // Pre-tick nothing. §9 declines to promote Select All for the same
            // reason: the list is *recordings you organised*, mixing research
            // calls with workshops and readouts, so a default of "all" is close
            // to always wrong.
            //
            // And **pre-select nothing either.** Setting focus to row 1 here
            // drew a highlighted row above a button reading "Import 0
            // Recordings" — at rest, the only thing on screen that looked
            // chosen, and it wasn't. Worse, the outline is not the first
            // responder when the window opens (the toolbar's filter field is
            // in the running), so it rendered in the inactive grey that reads
            // as disabled. An empty selection is the honest opening state; the
            // first arrow key selects row 1, which is what a Mac list does.
            //
            // A row that has gone (a filter keystroke, a collapsed parent) must
            // not keep the focus either: `toggleFocused` would tick something
            // invisible straight into the fetch queue.
            if let focused = focusedRowID,
               !visibleRows.contains(where: { $0.id == focused }) {
                focusedRowID = nil
            }
        }
        listTask = task
        await task.value
    }

    func cancelLoad() {
        listTask?.cancel()
        listTask = nil
        if phase == .loading { phase = .loaded }
    }

    /// Toggle one row. Rows that cannot be fetched cannot be ticked — the guard
    /// lives here rather than in the view so that keyboard, mouse and Select
    /// All all obey it.
    /// - Returns: whether the tick actually moved. False means the row refused
    ///   — already held, someone else's meeting, nothing to fetch — which the
    ///   keyboard path turns into a beep rather than a silent no-op.
    @discardableResult
    func toggle(_ rowID: String) -> Bool {
        // Looked up in the **visible** rows, not the whole listing. A row the
        // filter has hidden is not a row the researcher is acting on, and
        // ticking one puts a file they cannot see into the fetch queue.
        guard let row = visibleRows.first(where: { $0.id == rowID }), row.isSelectable else {
            return false
        }
        if ticked.contains(rowID) { ticked.remove(rowID) } else { ticked.insert(rowID) }
        return true
    }

    /// The meeting header's tri-state checkbox.
    ///
    /// **Mixed completes the set; full clears it.** Clicking a partly-ticked
    /// meeting ticks the rest rather than emptying it — the researcher clicked
    /// the parent to mean "all of this call", and reading a half-made selection
    /// as an instruction to discard it would throw away the choice they had
    /// already expressed. Only a fully-ticked meeting unticks. Finder and Mail
    /// both behave this way.
    ///
    /// Operates on the tickable children only. A recording already on disk is
    /// untouched in either direction: it draws ticked because it is here, not
    /// because it was chosen, and unticking it would mean nothing.
    ///
    /// - Returns: whether anything moved, so the keyboard path can beep.
    @discardableResult
    func toggleMeeting(rowIDs: [String]) -> Bool {
        let wanted = Set(rowIDs)
        let actionable = visibleRows.filter { wanted.contains($0.id) && $0.isSelectable }
        guard !actionable.isEmpty else { return false }
        if actionable.allSatisfy({ ticked.contains($0.id) }) {
            for row in actionable { ticked.remove(row.id) }
        } else {
            for row in actionable { ticked.insert(row.id) }
        }
        return true
    }

    /// Shift-click a checkbox to tick a range — §9's "the gesture that actually
    /// pays". Sorted by date, a study's sessions are adjacent: tick Monday's,
    /// shift-click Wednesday's.
    ///
    /// Operates over the *visible* (filtered, sorted) order, because that is the
    /// order the researcher's eye used to pick the two ends.
    func extendSelection(to rowID: String) {
        let visible = visibleRows
        guard let anchorID = lastTickedID ?? focusedRowID,
              let from = visible.firstIndex(where: { $0.id == anchorID }),
              let to = visible.firstIndex(where: { $0.id == rowID })
        else {
            toggle(rowID)
            return
        }
        for row in visible[min(from, to)...max(from, to)] where row.isSelectable {
            ticked.insert(row.id)
        }
        lastTickedID = rowID
    }

    private var lastTickedID: String?

    /// Edit ▸ Select All. Operates on the **filtered** set, never the window
    /// (§9) — ticking everything in a 30-day window is close to always wrong,
    /// but post-filter it is coherent, which is what earns it a menu item
    /// rather than a button.
    func selectAllVisible() {
        for row in visibleRows where row.isSelectable { ticked.insert(row.id) }
    }

    /// Clears the **ticks**, not the keyboard focus.
    ///
    /// Named `clearSelection` until 16 Aug 2026, beside a `focusedRowID` that
    /// the outline also calls "selection" — two different things under one
    /// word, in a file where the whole design rests on keeping intent and
    /// navigation apart. The next person to wire Escape would have reached for
    /// the wrong one.
    func clearTicks() { ticked.removeAll() }

    // `moveFocus(by:)` lived here and is gone. `NSOutlineView` does arrow
    // navigation natively, so it was a second, divergent focus model with no
    // caller — superseded by replacement rather than merely unfinished, which
    // is the distinction between deleting it and parking it.

    /// Space, from the outline.
    ///
    /// - Returns: whether the tick moved. False covers both "nothing is
    ///   focused" and "that row refuses" — the caller beeps either way, because
    ///   silence after a key that was understood reads as the app having missed
    ///   the keystroke.
    @discardableResult
    func toggleFocused() -> Bool {
        guard let focusedRowID else { return false }
        return toggle(focusedRowID)
    }

    // MARK: - Fetching

    /// True while the batch is blocked on the researcher granting access in
    /// their browser — **not** while anything is transferring.
    ///
    /// The rows used to say "Queued" here, which is a lie of exactly the wrong
    /// kind: nothing is queued, nothing is waiting its turn, and no amount of
    /// patience will move it. We are waiting on a person, in a window that on
    /// macOS opens in their *real* browser and is therefore routinely hidden
    /// behind it. Measured 17 Aug 2026: a stack of consent windows sitting
    /// unseen behind Chrome while the app appeared to be working.
    @Published private(set) var isAwaitingGrant = false

    /// Bumped on every start and every stop, so a grant the researcher walked
    /// away from cannot come back later and start transferring files.
    private var fetchGeneration = 0

    /// Which project this batch is landing in, and how far along it is.
    ///
    /// Published so the **sidebar row** can show the batch after the window is
    /// closed — the only thing that can answer "is it still going?" once the
    /// window that started it is gone. `total` is fixed at the moment Import is
    /// pressed rather than recomputed, so the denominator cannot move under a
    /// count the researcher is watching.
    struct BatchProgress: Equatable {
        let projectID: UUID
        let done: Int
        let total: Int
    }

    @Published private(set) var batch: BatchProgress?

    func startFetch(destination: URL, projectID: UUID) {
        guard !isFetching, !fetchOrder.isEmpty else { return }
        isFetching = true
        batch = BatchProgress(projectID: projectID, done: 0, total: fetchOrder.count)
        fetchGeneration &+= 1
        let mine = fetchGeneration
        outcomes.removeAll()
        progress.removeAll()

        let queue = fetchOrder
        fetchTask = Task { @MainActor in
            // One grant for the whole batch, before any transfer starts. A
            // failure here is the batch's failure — every row would 403 — so it
            // is reported once rather than N times.
            isAwaitingGrant = true
            do {
                try await source.prepareBatch(rowIDs: queue.map(\.id))
                isAwaitingGrant = false
            } catch {
                isAwaitingGrant = false
                guard self.fetchGeneration == mine else { return }
                for row in queue {
                    outcomes[row.id] = .failed(
                        reason: "Access wasn't granted.", isRetryable: true)
                }
                isFetching = false
                return
            }

            // **Stop cannot cancel a browser round trip.** `Task.cancel()` does
            // not reach into an `ASWebAuthenticationSession` continuation, so a
            // researcher who presses Stop while the consent window is open gets
            // their UI back — and, without this guard, the grant would land
            // minutes later and quietly start transferring the batch they had
            // just abandoned. The generation is what makes a late return inert.
            guard self.fetchGeneration == mine else { return }

            // `@MainActor` on the group body, so the per-row task registry can
            // be written from `startNext`. Without it the closure is
            // nonisolated and the bookkeeping cannot touch `rowTasks` — and the
            // alternative, hopping per registration, would let a cancel arrive
            // between a task starting and the handle that stops it being
            // recorded.
            await withTaskGroup(of: Void.self) { @MainActor group in
                var iterator = queue.makeIterator()
                var running = 0

                // `@MainActor` on the nested function too: a local `func` does
                // **not** inherit its enclosing closure's isolation, so the
                // annotation on the group body above does not reach in here.
                @MainActor func startNext() {
                    guard let row = iterator.next() else { return }
                    running += 1
                    // A per-row `Task` we keep a handle on, rather than an
                    // anonymous group child. `withTaskGroup` hands back no
                    // per-child handle, so with `addTask` alone the only
                    // available cancellation is all-or-nothing — and one
                    // stalled 465 MB transfer then forces abandoning the four
                    // beside it that were fine.
                    let task = Task { @MainActor [weak self] in
                        guard let self else { return }
                        let outcome = await self.source.fetch(
                            row: row,
                            destination: destination,
                            progress: { [weak self] p in
                                Task { @MainActor in self?.progress[p.rowID] = p }
                            }
                        )
                        self.outcomes[row.id] = outcome
                        self.progress[row.id] = nil
                        self.rowTasks[row.id] = nil
                        // Counted on *settling*, not on succeeding: the row
                        // question behind "3 of 4" is how many are still to
                        // wait for, and a failed or cancelled one is no longer
                        // being waited for. A ring that stalls at 3 because the
                        // fourth failed is the ring saying nothing at all.
                        if let current = self.batch {
                            self.batch = BatchProgress(projectID: current.projectID,
                                                       done: current.done + 1,
                                                       total: current.total)
                        }
                        // A row that landed stops being tickable; one that
                        // failed stays ticked so Retry has something to act on.
                        if case .imported = outcome { self.ticked.remove(row.id) }
                    }
                    rowTasks[row.id] = task
                    // The group waits on it, but does not own its cancellation
                    // — which is the whole point, and also the trap: an
                    // unstructured `Task` does NOT inherit the group's
                    // cancellation, so `stopFetch` has to cancel these itself.
                    group.addTask { await task.value }
                }

                for _ in 0..<min(maxConcurrentFetches, queue.count) { startNext() }
                while running > 0 {
                    await group.next()
                    running -= 1
                    startNext()
                }
            }
            isFetching = false
            // The row's ring is driven off this, so clearing it is what makes
            // the sidebar go quiet. Guarded on the generation: a superseded
            // batch must not blank the indicator of the one that replaced it.
            if self.fetchGeneration == mine { self.batch = nil }
        }
    }

    /// In-flight transfers, one per row, so a single stuck one can be dropped
    /// without taking the batch with it.
    private var rowTasks: [String: Task<Void, Never>] = [:]

    /// Stop one transfer. The rest of the batch carries on.
    ///
    /// Genuinely stops it rather than merely un-drawing it: the download is a
    /// `URLSession.download(for:delegate:)`, which bridges Swift task
    /// cancellation to the session task, and `CloudDownloader` checks
    /// `Task.isCancelled` again before anything reaches the project folder.
    /// The outcome is left to the natural completion path — the adapter
    /// already maps both `CloudDownloadError.cancelled` and the
    /// `URLError(.cancelled)` the transport actually throws onto
    /// `FetchOutcome.cancelled` — because setting it here would race a
    /// transfer that finished in the same instant and could report a landed
    /// file as stopped.
    ///
    /// The row stays ticked on purpose: you stopped it, so Retry should still
    /// find it.
    func cancelRow(_ rowID: String) {
        rowTasks[rowID]?.cancel()
        rowTasks[rowID] = nil
    }

    func stopFetch() {
        fetchTask?.cancel()
        fetchTask = nil
        // **Cancel the row tasks explicitly.** They are unstructured `Task`s,
        // created so they can be cancelled one at a time, and the price of that
        // is that they do NOT inherit cancellation from `fetchTask` or from the
        // group. Without this line Stop would tear down the coordinator and
        // leave every download running.
        for task in rowTasks.values { task.cancel() }
        rowTasks.removeAll()
        batch = nil
        // Bumped so an in-flight grant that returns after this — which it will,
        // since cancelling the Task does not close the browser window — cannot
        // resume the batch behind the researcher's back.
        fetchGeneration &+= 1
        isAwaitingGrant = false
        isFetching = false
    }
}
