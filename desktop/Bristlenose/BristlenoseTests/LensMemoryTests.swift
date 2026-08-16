import Foundation
import Testing

@testable import Bristlenose

/// "Open where you left it, not the dashboard" — the project-level twin of
/// `SessionsRouteMemory`.
///
/// The rules worth pinning are the two the code would get *plausibly* wrong: a
/// never-opened project must land on the dashboard rather than somewhere
/// arbitrary, and a lens name that no longer exists must degrade to the
/// dashboard rather than crash or be honoured blindly.
@Suite("Lens memory")
struct LensMemoryTests {

    @Test("a remembered lens is restored")
    func remembersALens() {
        #expect(LensMemory.restore("quotes") == .quotes)
        #expect(LensMemory.restore("codebook") == .codebook)
        #expect(LensMemory.restore("sessions") == .sessions)
    }

    @Test("a never-opened project lands on the dashboard")
    func noMemoryMeansDashboard() {
        // nil is "let the report load where it loads", which is the Project
        // dashboard — and that is exactly the case the dashboard is right for,
        // so it needs no special rule.
        #expect(LensMemory.restore(nil) == nil)
    }

    @Test("a lens that no longer exists degrades to the dashboard")
    func unknownLensDegrades() {
        // A `Tab` case renamed or removed between versions. Landing on the
        // dashboard beats both crashing and honouring a string nothing can
        // interpret.
        #expect(LensMemory.restore("moodboard") == nil)
        #expect(LensMemory.restore("") == nil)
    }

    @Test("round-trips every lens")
    func roundTrip() {
        // Guards the pairing rather than either half: if `remember` ever stops
        // writing what `restore` reads, every project silently reverts to the
        // dashboard and nothing else fails.
        for tab in Tab.allCases {
            #expect(LensMemory.restore(LensMemory.remember(tab)) == tab)
        }
    }

    @Test("no lens yet means don't write")
    func noTabMeansNoWrite() {
        // The SPA can report a route before it reports a lens. Writing "nothing"
        // there would erase the memory the window is about to restore from.
        #expect(LensMemory.remember(nil) == nil)
    }
}

/// The persistence half — `lastLens` survives a `projects.json` round trip, and
/// its absence is not an error.
@MainActor
@Suite("Lens memory persistence")
struct LensMemoryPersistenceTests {

    private static func makeTempIndex() -> (ProjectIndex, URL) {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: tempDir.appendingPathComponent("projects.json"))
        return (index, tempDir)
    }

    @Test("the lens is written and read back")
    func persists() {
        let (index, dir) = Self.makeTempIndex()
        defer { try? FileManager.default.removeItem(at: dir) }

        let project = index.addProject(name: "IKEA Study", path: "/tmp/ikea")
        #expect(project.lastLens == nil, "a new project has nowhere it was left")

        index.setLastLens(id: project.id, lens: "quotes")

        let reloaded = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        #expect(reloaded.projects.first?.lastLens == "quotes")
    }

    @Test("a projects.json written before lens memory still loads")
    func absentKeyIsNotAnError() throws {
        let (index, dir) = Self.makeTempIndex()
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent("projects.json")

        let project = index.addProject(name: "Old", path: "/tmp/old")
        index.setLastLens(id: project.id, lens: "quotes")

        // Strip the key back out rather than hand-writing a legacy file: the
        // fixture is then produced by the real encoder and can't drift from the
        // actual schema. Twice bitten writing this test — a hand-written
        // literal missed the envelope's `version` field, and a text substitution
        // missed that the encoder is `.prettyPrinted` + `.sortedKeys`. Parsing
        // is the only version that doesn't encode a guess about the format.
        var file = try JSONSerialization.jsonObject(
            with: Data(contentsOf: url)) as! [String: Any]
        var projects = file["projects"] as! [[String: Any]]
        projects[0].removeValue(forKey: "last_lens")
        file["projects"] = projects
        let stripped = try JSONSerialization.data(withJSONObject: file)
        #expect(!String(decoding: stripped, as: UTF8.self).contains("last_lens"),
                "fixture must actually lack the key")
        try stripped.write(to: url, options: .atomic)

        let reloaded = ProjectIndex(fileURL: url)
        #expect(reloaded.projects.count == 1, "an older file must still parse")
        #expect(reloaded.projects.first?.lastLens == nil)
    }
}
