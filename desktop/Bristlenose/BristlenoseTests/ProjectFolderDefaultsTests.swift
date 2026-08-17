import Foundation
import Testing

@testable import Bristlenose

// Where the next New Project panel opens.
//
// Four doors reach this decision — loose-file drops on the sidebar and on the
// welcome screen, the import window, and `+ New Project` (which deliberately
// proposes nothing and must stay that way; see the type's doc comment). Three of
// them used to hardcode `~/Documents`, so a researcher who keeps every study in
// `~/Work/Studies` was sent to Documents every single time, by every door. The
// duplication is the reason this type exists; the three-rung ladder is what
// makes it worth existing.
//
// Uses an isolated `UserDefaults` suite throughout: these tests must never
// read or write the real preference, or running the suite would move where the
// developer's own next project lands.

@Suite("Where new projects are proposed")
struct ProjectFolderDefaultsTests {

    private func scratchDefaults() -> UserDefaults {
        // A unique suite per test, so ordering cannot leak state between them.
        UserDefaults(suiteName: "bn-test-\(UUID().uuidString)")!
    }

    private func scratchDirectory() throws -> URL {
        let url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-folder-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    /// The **real** home's Documents, which is what the implementation falls
    /// back to — deliberately not `FileManager.urls(for: .documentDirectory)`,
    /// which under App Sandbox returns the *container's* Documents. That path
    /// is invisible to the researcher in Finder, so proposing it would send
    /// every new project somewhere they cannot find.
    private var documents: URL { UserHome.folder("Documents") }

    // MARK: - Rung 3: the floor

    @Test("With nothing remembered, the first proposal is Documents")
    func fallsBackToDocuments() {
        let defaults = scratchDefaults()
        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults) == documents)
    }

    // The test above reads naturally and is worth keeping, but on its own it
    // cannot fail on the bug it looks like it covers: the test target is
    // unsandboxed, so `UserHome.folder("Documents")` and
    // `FileManager.urls(for: .documentDirectory, in: .userDomainMask)` resolve to
    // the *same* path here. Revert the implementation to the FileManager lookup
    // and it still passes, while the shipping sandboxed app proposes a folder
    // inside its own container. That is exactly how the container bug survived
    // review — the assertion was computed from the same call it was checking.
    //
    // Injecting a fixture home makes the *derivation* the thing under test. The
    // two lookups disagree the moment the home is not the process's own, so a
    // revert fails here even though the target is unsandboxed.

    @Test("The floor is Documents inside the given home, not the process's own")
    func floorIsDerivedFromTheInjectedHome() throws {
        let defaults = scratchDefaults()
        let home = try scratchDirectory()
        defer { try? FileManager.default.removeItem(at: home) }
        let fixtureDocuments = home.appendingPathComponent("Documents", isDirectory: true)
        try FileManager.default.createDirectory(
            at: fixtureDocuments, withIntermediateDirectories: true)

        let suggested = try #require(
            ProjectFolderDefaults.suggestedDirectory(defaults: defaults, home: home))
        #expect(suggested.standardizedFileURL == fixtureDocuments.standardizedFileURL)
        #expect(suggested.standardizedFileURL != documents.standardizedFileURL)
    }

    @Test("The real home is never the sandbox container")
    func realHomeIsNotTheContainer() {
        // `UserHome` reads the passwd entry, which the sandbox does not rewrite.
        // Checked against an independent read of that entry rather than against
        // `NSHomeDirectory()`, which agrees in this unsandboxed target and would
        // therefore prove nothing.
        let passwd = String(cString: getpwuid(getuid())!.pointee.pw_dir)
        #expect(UserHome.path == passwd)
        #expect(!UserHome.path.contains("/Library/Containers/"))
    }

    @Test("A home with no Documents folder yields no opinion, not a bad path")
    func floorDeclinesWhenDocumentsIsAbsent() throws {
        // Handing a panel a directoryURL that does not exist is worse than
        // handing it nil — nil lets AppKit fall back to its own per-app memory.
        let defaults = scratchDefaults()
        let home = try scratchDirectory()
        defer { try? FileManager.default.removeItem(at: home) }

        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults, home: home) == nil)
    }

    // MARK: - Rung 2: remembered

    @Test("It proposes the parent of the last project, not the project itself")
    func remembersTheParent() throws {
        // The researcher chose a place to put a study. Starting the next panel
        // *inside* last week's project is the more annoying of the two
        // mistakes, so the parent is what gets kept.
        let defaults = scratchDefaults()
        let root = try scratchDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        let project = root.appendingPathComponent("Ikea study", isDirectory: true)
        try FileManager.default.createDirectory(at: project, withIntermediateDirectories: true)

        ProjectFolderDefaults.remember(projectFolder: project, defaults: defaults)

        let suggested = try #require(ProjectFolderDefaults.suggestedDirectory(defaults: defaults))
        #expect(suggested.standardizedFileURL == root.standardizedFileURL)
        #expect(suggested.lastPathComponent != "Ikea study")
    }

    @Test("A remembered folder that has gone away does not strand the panel")
    func fallsBackWhenTheFolderVanished() {
        // An external drive unplugged, a folder renamed, a study archived.
        // Opening a panel at a path that no longer exists reads as the app
        // being broken rather than as a disk being absent.
        let defaults = scratchDefaults()
        let gone = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-absent-\(UUID().uuidString)/inner", isDirectory: true)
        ProjectFolderDefaults.remember(projectFolder: gone, defaults: defaults)

        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults) == documents)
    }

    @Test("A file where a folder was remembered is refused too")
    func fallsBackWhenThePathIsNotADirectory() throws {
        // `fileExists` alone would accept this and hand a panel a file to open
        // *at*, which AppKit does not do anything sensible with.
        let defaults = scratchDefaults()
        let root = try scratchDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("notafolder.txt")
        try Data("x".utf8).write(to: file)

        // Remembering `<root>/notafolder.txt/child` stores `notafolder.txt`.
        ProjectFolderDefaults.remember(
            projectFolder: file.appendingPathComponent("child"), defaults: defaults)

        #expect(ProjectFolderDefaults.suggestedDirectory(defaults: defaults) == documents)
    }

    @Test("The root directory is never remembered")
    func refusesRoot() {
        // A project created at `/Something` would otherwise store `/`, and
        // every future panel would open at the volume root — technically a
        // directory, and a hostile place to start.
        let defaults = scratchDefaults()
        ProjectFolderDefaults.remember(
            projectFolder: URL(fileURLWithPath: "/Something", isDirectory: true),
            defaults: defaults)
        #expect(ProjectFolderDefaults.remembered(defaults: defaults) == nil)
    }

    @Test("The volume list is never remembered either")
    func refusesVolumesList() {
        // A project at `/Volumes/Study` stores `/Volumes`, and every future
        // panel opens on the mounted-volume list. Same class as `/`, one level
        // down, and just as hostile a place to start.
        let defaults = scratchDefaults()
        ProjectFolderDefaults.remember(
            projectFolder: URL(fileURLWithPath: "/Volumes/Study", isDirectory: true),
            defaults: defaults)
        #expect(ProjectFolderDefaults.remembered(defaults: defaults) == nil)
    }

    // MARK: - Rung 1: configured (Settings ▸ General)

    @Test("A configured folder outranks a remembered one")
    func configuredBeatsRemembered() throws {
        // A preference the researcher set explicitly, then overridden by
        // wherever they last saved something, is not a setting but a suggestion
        // — and that drift is the very thing they set it to stop.
        let defaults = scratchDefaults()
        let remembered = try scratchDirectory()
        let chosen = try scratchDirectory()
        defer {
            try? FileManager.default.removeItem(at: remembered)
            try? FileManager.default.removeItem(at: chosen)
        }

        ProjectFolderDefaults.remember(
            projectFolder: remembered.appendingPathComponent("Old study", isDirectory: true),
            defaults: defaults)
        #expect(ProjectFolderDefaults.setConfigured(chosen, defaults: defaults))

        let suggested = try #require(ProjectFolderDefaults.suggestedDirectory(defaults: defaults))
        #expect(suggested.standardizedFileURL == chosen.standardizedFileURL)
    }

    @Test("An unreachable configured folder falls through to remembered, not to Documents")
    func unreachableConfiguredFallsThroughToRemembered() throws {
        // The whole point of keeping `remember()` writing underneath: losing the
        // configured folder should cost the researcher their preference, not the
        // learned behaviour as well.
        let defaults = scratchDefaults()
        let remembered = try scratchDirectory()
        let chosen = try scratchDirectory()
        defer { try? FileManager.default.removeItem(at: remembered) }

        ProjectFolderDefaults.remember(
            projectFolder: remembered.appendingPathComponent("Old study", isDirectory: true),
            defaults: defaults)
        #expect(ProjectFolderDefaults.setConfigured(chosen, defaults: defaults))
        try FileManager.default.removeItem(at: chosen)

        let suggested = try #require(ProjectFolderDefaults.suggestedDirectory(defaults: defaults))
        #expect(suggested.standardizedFileURL == remembered.standardizedFileURL)
        #expect(suggested.standardizedFileURL != documents.standardizedFileURL)
    }

    @Test("An unreachable configured folder still names itself to the settings row")
    func unreachableConfiguredStaysVisible() throws {
        // An unplugged drive is not a decision to change where studies go, so
        // the row keeps saying what was set and why it cannot be used.
        // Collapsing to `.notSet` would read as the app having quietly
        // discarded the preference.
        let defaults = scratchDefaults()
        let chosen = try scratchDirectory()
        #expect(ProjectFolderDefaults.setConfigured(chosen, defaults: defaults))
        try FileManager.default.removeItem(at: chosen)

        let state = ProjectFolderDefaults.configured(defaults: defaults)
        #expect(state != .notSet)
        if case .unavailable(let name, let reason) = state {
            #expect(name == chosen.lastPathComponent)
            // A temp dir is on the boot volume, so this is a deletion rather
            // than an absent volume.
            #expect(reason == .missing)
        } else {
            Issue.record("expected .unavailable, got \(state)")
        }
    }

    @Test("Nothing configured is a distinct state, not a stand-in for Documents")
    func notSetIsDistinct() {
        let defaults = scratchDefaults()
        #expect(ProjectFolderDefaults.configured(defaults: defaults) == .notSet)
    }

    @Test("Use Last Location clears the preference and restores the remembered folder")
    func clearingRestoresRemembered() throws {
        let defaults = scratchDefaults()
        let remembered = try scratchDirectory()
        let chosen = try scratchDirectory()
        defer {
            try? FileManager.default.removeItem(at: remembered)
            try? FileManager.default.removeItem(at: chosen)
        }

        ProjectFolderDefaults.remember(
            projectFolder: remembered.appendingPathComponent("Old study", isDirectory: true),
            defaults: defaults)
        #expect(ProjectFolderDefaults.setConfigured(chosen, defaults: defaults))
        ProjectFolderDefaults.clearConfigured(defaults: defaults)

        #expect(ProjectFolderDefaults.configured(defaults: defaults) == .notSet)
        let suggested = try #require(ProjectFolderDefaults.suggestedDirectory(defaults: defaults))
        #expect(suggested.standardizedFileURL == remembered.standardizedFileURL)
    }

    @Test("Configuring a file, the root, or the volume list is refused outright")
    func setConfiguredRefusesHostileTargets() throws {
        let defaults = scratchDefaults()
        let root = try scratchDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("notafolder.txt")
        try Data("x".utf8).write(to: file)

        #expect(!ProjectFolderDefaults.setConfigured(file, defaults: defaults))
        #expect(!ProjectFolderDefaults.setConfigured(
            URL(fileURLWithPath: "/", isDirectory: true), defaults: defaults))
        #expect(!ProjectFolderDefaults.setConfigured(
            URL(fileURLWithPath: "/Volumes", isDirectory: true), defaults: defaults))
        // Refused means unchanged, not half-written.
        #expect(ProjectFolderDefaults.configured(defaults: defaults) == .notSet)
    }
}

@Suite("Abbreviating paths the way Finder does")
struct UserHomeTests {

    @Test("A path inside the home abbreviates to a tilde")
    func abbreviatesHomePaths() {
        #expect(UserHome.abbreviate(UserHome.path + "/Work/Studies") == "~/Work/Studies")
        #expect(UserHome.abbreviate(UserHome.path) == "~")
    }

    @Test("A path outside the home is left alone")
    func leavesForeignPathsAlone() {
        #expect(UserHome.abbreviate("/Volumes/Iona/Studies") == "/Volumes/Iona/Studies")
        // A sibling directory that merely shares the home's string prefix must
        // not be mangled — the component boundary is what matters.
        #expect(UserHome.abbreviate(UserHome.path + "extra/Studies")
            == UserHome.path + "extra/Studies")
    }

    @Test("Segments carry the tilde as its own component for VoiceOver")
    func segmentsSpeakTheTilde() {
        // The breadcrumb joins these with ›, and VoiceOver reads them
        // comma-separated — so `~` must be its own component rather than a
        // character glued to the first folder name.
        #expect(UserHome.abbreviatedSegments(UserHome.path + "/Work/Studies")
            == ["~", "Work", "Studies"])
        #expect(UserHome.abbreviatedSegments("/Volumes/Iona/Studies")
            == ["Volumes", "Iona", "Studies"])
    }
}
