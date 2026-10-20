import Foundation

/// The studies waiting behind the run in flight, in order, each with whether
/// it asked for `--clean`.
///
/// The queue held bare ids until 20 Oct 2026, so a Re-analyse that had to wait
/// for another study ran without `--clean`: the CLI resumed and the row ended
/// "ready" on the old report (R18). A value type so its rules have tests.
struct RunQueue: Equatable {
    struct Entry: Equatable {
        let id: UUID
        var clean: Bool
    }

    private(set) var entries: [Entry] = []

    var isEmpty: Bool { entries.isEmpty }
    var count: Int { entries.count }
    var ids: [UUID] { entries.map(\.id) }

    func contains(_ id: UUID) -> Bool {
        entries.contains { $0.id == id }
    }

    /// Adds `id` at the back. A study already waiting keeps its place, and a
    /// Re-analyse makes it clean; a later plain Analyse never undoes that,
    /// because the researcher confirmed the Re-analyse and nothing since has
    /// taken it back.
    mutating func enqueue(_ id: UUID, clean: Bool) {
        if let i = entries.firstIndex(where: { $0.id == id }) {
            entries[i].clean = entries[i].clean || clean
        } else {
            entries.append(Entry(id: id, clean: clean))
        }
    }

    /// Takes `id` out of the queue. False when it was not waiting.
    @discardableResult
    mutating func remove(_ id: UUID) -> Bool {
        guard let i = entries.firstIndex(where: { $0.id == id }) else { return false }
        entries.remove(at: i)
        return true
    }

    mutating func popFirst() -> Entry? {
        entries.isEmpty ? nil : entries.removeFirst()
    }

    /// Puts an entry back at the head, as it was, when it could not start.
    mutating func pushFront(_ entry: Entry) {
        entries.insert(entry, at: 0)
    }
}
