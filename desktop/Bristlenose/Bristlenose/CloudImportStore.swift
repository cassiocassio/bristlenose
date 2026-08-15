import Foundation
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
        /// Listing failed outright — distinct from a listing that partly
        /// succeeded, which is `.loaded` with a non-exhausted outcome.
        case failed(String)
    }

    @Published private(set) var phase: Phase = .signedOut
    @Published private(set) var listing: MeetingListing?
    @Published private(set) var accountEmail: String?

    /// Ticked rows. Intent, and durable across filter changes — which is the
    /// whole argument for checkboxes over selection: ticking three under
    /// "Interview", clearing the filter and adding two more has to survive.
    @Published var ticked: Set<String> = []

    /// Keyboard focus. Exactly one row, and deliberately not the same thing as
    /// a tick — one model for intent, one for navigation.
    @Published var focusedRowID: String?

    @Published var filterText: String = ""

    /// Per-row fetch state, keyed by row id.
    @Published private(set) var progress: [String: FetchProgress] = [:]
    @Published private(set) var outcomes: [String: FetchOutcome] = [:]
    @Published private(set) var isFetching = false

    /// Rolling window. 30 days per §9 — "~95% of what you want is recent";
    /// going further back is a different intent, not a longer scroll.
    @Published var windowDays: Int = 30

    private let source: CloudImportSource
    private var listTask: Task<Void, Never>?
    private var fetchTask: Task<Void, Never>?

    /// Bounded concurrency. §9: the benefit is resilience — one stalled file
    /// doesn't block the batch — not throughput, since a single 1.3 GB transfer
    /// already saturates a modest uplink.
    private let maxConcurrentFetches = 3

    init(source: CloudImportSource) {
        self.source = source
        self.accountEmail = source.accountEmail
        self.phase = source.accountEmail == nil ? .signedOut : .loading
    }

    // MARK: - Derived

    /// Rows after the filter, in display order: most-recent-first, because the
    /// researcher opened this to find last week. Fetch order is a different
    /// question — see `fetchOrder`.
    var visibleRows: [CloudImportRow] {
        let all = listing?.rows ?? []
        let term = filterText.trimmingCharacters(in: .whitespacesAndNewlines)
        let filtered = term.isEmpty
            ? all
            : all.filter { $0.title.localizedCaseInsensitiveContains(term) }
        return filtered.sorted { $0.startsAt > $1.startsAt }
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
    var fetchOrder: [CloudImportRow] {
        (listing?.rows ?? [])
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
        let rows = listing?.rows ?? []
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

    func signIn() {
        phase = .signingIn
        Task { @MainActor in
            do {
                try await source.signIn()
                accountEmail = source.accountEmail
                await load()
            } catch {
                phase = .failed(error.localizedDescription)
            }
        }
    }

    func load() async {
        listTask?.cancel()
        phase = .loading
        let interval = DateInterval(
            start: Calendar.current.date(byAdding: .day, value: -windowDays, to: Date()) ?? Date(),
            end: Date()
        )
        let task = Task { @MainActor in
            let result = await source.list(window: interval)
            guard !Task.isCancelled else { return }
            listing = result
            accountEmail = source.accountEmail
            phase = .loaded
            // Pre-tick nothing. §9 declines to promote Select All for the same
            // reason: the list is *recordings you organised*, mixing research
            // calls with workshops and readouts, so a default of "all" is close
            // to always wrong.
            if focusedRowID == nil { focusedRowID = visibleRows.first?.id }
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
    func toggle(_ rowID: String) {
        guard let row = listing?.rows.first(where: { $0.id == rowID }), row.isSelectable else { return }
        if ticked.contains(rowID) { ticked.remove(rowID) } else { ticked.insert(rowID) }
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

    func clearSelection() { ticked.removeAll() }

    func moveFocus(by delta: Int) {
        let visible = visibleRows
        guard !visible.isEmpty else { return }
        guard let current = focusedRowID,
              let idx = visible.firstIndex(where: { $0.id == current })
        else {
            focusedRowID = visible.first?.id
            return
        }
        let next = min(max(0, idx + delta), visible.count - 1)
        focusedRowID = visible[next].id
    }

    func toggleFocused() {
        guard let focusedRowID else { return }
        toggle(focusedRowID)
    }

    // MARK: - Fetching

    func startFetch(destination: URL) {
        guard !isFetching, !fetchOrder.isEmpty else { return }
        isFetching = true
        outcomes.removeAll()
        progress.removeAll()

        let queue = fetchOrder
        fetchTask = Task { @MainActor in
            await withTaskGroup(of: Void.self) { group in
                var iterator = queue.makeIterator()
                var running = 0

                func startNext() {
                    guard let row = iterator.next() else { return }
                    running += 1
                    group.addTask { @MainActor [weak self] in
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
                        // A row that landed stops being tickable; one that
                        // failed stays ticked so Retry has something to act on.
                        if case .imported = outcome { self.ticked.remove(row.id) }
                    }
                }

                for _ in 0..<min(maxConcurrentFetches, queue.count) { startNext() }
                while running > 0 {
                    await group.next()
                    running -= 1
                    startNext()
                }
            }
            isFetching = false
        }
    }

    func stopFetch() {
        fetchTask?.cancel()
        fetchTask = nil
        isFetching = false
    }
}
