import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

/// The Review Gallery cannot quietly rot: every entry is well-formed, every
/// state builds and draws at a real size, the sidebar fixture's rows say what
/// they claim to, and "reviewed" follows the commit list.
/// (`tests/test_review_gallery_registry.py` resolves the hashes in git.)
@MainActor
@Suite struct ReviewGalleryRegistryTests {

    private func i18n(_ locale: String = "en") throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale(locale)   // never the developer's own app language
        return i18n
    }

    // MARK: - The registry

    @Test func idsAreUnique() {
        let ids = ReviewGalleryRegistry.entries.map(\.id)
        #expect(Set(ids).count == ids.count, "duplicate ids: \(ids)")
    }

    @Test func everyEntryNamesItsCommitsAsShortHashes() throws {
        let hash = try Regex("^[0-9a-f]{7,40}$")
        for entry in ReviewGalleryRegistry.entries {
            #expect(!entry.commits.isEmpty, "\(entry.id) names no commit")
            #expect(!entry.states.isEmpty, "\(entry.id) has no state")
            for commit in entry.commits {
                #expect(commit.wholeMatch(of: hash) != nil, "\(entry.id): \(commit) is not a hash")
            }
        }
    }

    /// The test that catches a view whose initialiser changed, a fixture that
    /// no longer builds, or a state that draws nothing.
    @Test func everyStateBuildsAndDrawsAtARealSize() throws {
        let i18n = try i18n()
        let context = ReviewGalleryContext(i18n: i18n, appearance: nil, log: { _ in })
        for entry in ReviewGalleryRegistry.entries {
            for state in entry.states {
                let what = "\(entry.id) · \(state.name)"
                let specimen = state.make(context)
                // The view itself, not the canvas: the canvas's label line has
                // a height of its own and would pass for an empty specimen.
                var drawn: [AnyView] = []
                switch specimen {
                case .view(let view, let label):
                    #expect(!label.isEmpty, "\(what) has no label")
                    drawn = [view]
                case .views(let views):
                    #expect(!views.isEmpty, "\(what) has no views")
                    for item in views { #expect(!item.label.isEmpty, "\(what) has an unlabelled view") }
                    drawn = views.map(\.1)
                case .navigation(let recipe, _):
                    #expect(!recipe.isEmpty, "\(what) has no recipe")
                }
                // An empty view hosts at 10 × 10 (NSHostingView's floor, measured),
                // so "drew something" means more than that; every real surface
                // here is far larger than 40 pt either way.
                for view in drawn {
                    let size = host(view.environmentObject(i18n))
                    #expect(size.height > 40 && size.width > 40, "\(what) drew nothing (\(size))")
                }
                // And the canvas the window shows draws, whatever the kind.
                let canvas = host(ReviewGalleryCanvas(specimen: specimen, log: { _ in })
                    .environmentObject(i18n))
                #expect(canvas.height > 0, "\(what): the canvas drew nothing")
            }
        }
    }

    private func host(_ view: some View) -> NSSize {
        let hosting = NSHostingView(rootView: view)
        let window = NSWindow(contentRect: NSRect(x: -20_000, y: -20_000, width: 900, height: 700),
                              styleMask: [.borderless], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentView = hosting
        defer { window.close() }
        hosting.layoutSubtreeIfNeeded()
        return hosting.fittingSize
    }

    // MARK: - The sidebar rows say what they claim

    @Test(arguments: ["en", "de"])
    func theSidebarFixtureRowsReadTheirSubtitles(locale: String) throws {
        let i18n = try i18n(locale)
        let fixture = ReviewGallerySidebarFixture()
        let controller = SidebarOutlineController()
        controller.projectIndex = fixture.index
        controller.i18n = i18n                    // weak: `i18n` is held above
        fixture.configure(controller)
        _ = controller.view
        controller.update(roots: fixture.roots, selection: [], activeTab: nil, lensesEnabled: true)

        #expect(fixture.rows.count == 8)
        for row in fixture.rows {
            let expected = i18n.t(row.subtitleKey)
            #expect(expected != row.subtitleKey, "\(row.subtitleKey) does not resolve in \(locale)")
            let shown = try #require(texts(ofRowFor: row.id, in: controller), "no row for \(row.name)")
            #expect(shown.contains(row.name), "\(row.name)'s row does not show its name: \(shown)")
            #expect(shown.contains { $0.contains(expected) },
                    "\(row.name) (\(row.what)) should read “\(expected)” in \(locale), shows \(shown)")
        }
    }

    private func texts(ofRowFor id: UUID, in controller: SidebarOutlineController) -> [String]? {
        let outline = controller.outlineView
        for row in 0..<outline.numberOfRows {
            guard let node = outline.item(atRow: row) as? OutlineNode, node.kind == .project(id),
                  let cell = outline.view(atColumn: 0, row: row, makeIfNecessary: true)
            else { continue }
            return texts(in: cell)
        }
        return nil
    }

    /// The row's words wherever the cell put them: a label, the subtitle
    /// button that opens the popover, or the shimmering host of a running row.
    private func texts(in view: NSView) -> [String] {
        var out: [String] = []
        if let field = view as? NSTextField { out.append(field.stringValue) }
        if let button = view as? NSButton { out.append(button.title) }
        if let shimmer = view as? NSHostingView<ShimmerText> { out.append(shimmer.rootView.text) }
        for sub in view.subviews { out += texts(in: sub) }
        return out
    }

    /// A fixture's rows are not runs: no Stop on them, no idle-sleep
    /// assertion held through `ProcessInfo`, no folder watchers.
    @Test func theSidebarFixtureTouchesNothingOfTheApps() async throws {
        let fixture = ReviewGallerySidebarFixture()
        for row in fixture.rows {
            #expect(!fixture.runner.canStop(row.id), "\(row.name) offers Stop")
        }
        // The two `.running` rows drive the injected assertion, which asserts
        // nothing — so the runner is not holding a real one.
        #expect(fixture.sleepAssertionsHeld == 1)
        // Asked directly: no row has a folder watcher (watcherCap: 0).
        for row in fixture.rows {
            #expect(!fixture.index.hasWatcher(projectID: row.id), "\(row.name) has a folder watcher")
        }
    }

    @Test func theSidebarFixtureRemovesItsTempTree() throws {
        var root: URL?
        do {
            let fixture = ReviewGallerySidebarFixture()
            root = fixture.root
            try #require(FileManager.default.fileExists(atPath: fixture.root.path))
        }
        let gone = try #require(root)
        #expect(!FileManager.default.fileExists(atPath: gone.path), "the fixture left \(gone.path)")
    }

    // MARK: - The boot pane

    /// The 520 × 360 frame means a size check cannot see this pane's change, so
    /// check the change itself: the primary button is Retry until a Retry has
    /// failed. Asked of the decision `BootView` makes, on the manager the pane
    /// reads (`fleet.manager(for: project)`) — a SwiftUI button in a hosting
    /// view has no AppKit subview or offscreen accessibility element to read.
    @Test func theBootPaneOffersRetryUntilARetryHasFailed() throws {
        let i18n = try i18n()
        let expected = [
            "First failure": "desktop.boot.retry",
            "After a failed retry": "desktop.menu.help.sendFeedback",
            "90 s timeout": "desktop.boot.retry",
            "Sidecar missing": "desktop.boot.retry",
        ]
        let entry = try #require(ReviewGalleryRegistry.entries.first { $0.id == "M14" })
        #expect(entry.states.map(\.name) == ReviewGalleryRegistry.bootStates.map(\.name))
        #expect(Set(expected.keys) == Set(ReviewGalleryRegistry.bootStates.map(\.name)))
        for row in ReviewGalleryRegistry.bootStates {
            let fixture = ReviewGalleryRegistry.bootFixture(row)
            #expect(fixture.fleet.manager(for: fixture.project) === fixture.manager)
            // The button that tells this state apart: Retry (the default) on a
            // first failure, Send Feedback… (no default) once a retry failed.
            let set = BootView.failureButtons(startedByRetry: fixture.manager.startedByRetry)
            let key = set.buttons.contains(.retry)
                ? "desktop.boot.retry" : "desktop.menu.help.sendFeedback"
            #expect(key == expected[row.name], "\(row.name): offers \(key)")
            #expect((set.defaultButton == .retry) == set.buttons.contains(.retry),
                    "\(row.name): Return presses Retry or nothing")
            #expect(i18n.t(key) != key)
            #expect(!fixture.manager.outputLines.isEmpty, "\(row.name): Show details has nothing")
        }
    }

    // MARK: - The gallery's managers hear nothing of the app's

    /// A gallery manager on `.default` with the fleet's handshake hook ran the
    /// gallery fleet's `syncHandshake` on every Agent Access flip in the app,
    /// and that fleet's only manager has no path, so it removed the live MCP
    /// handshake file. Posting the flip on `.default` here would reach the
    /// test host's own fleet, so this pins the wiring instead.
    @Test func theBootFixtureIsOffTheAppsNotificationCentre() {
        for row in ReviewGalleryRegistry.bootStates {
            let fixture = ReviewGalleryRegistry.bootFixture(row)
            #expect(fixture.manager.notificationCenter !== NotificationCenter.default)
            #expect(fixture.manager.onHandshakeDirty == nil)
        }
    }

    /// And the centre a manager is given is the one it listens on.
    @Test func aServeManagerListensOnTheCentreItIsGiven() async throws {
        let centre = NotificationCenter()
        let manager = ServeManager(resolvedMode: .success(.external(port: 1)),
                                   notificationCenter: centre)
        var syncs = 0
        manager.onHandshakeDirty = { syncs += 1 }
        centre.post(name: .bristlenoseAgentAccessChanged, object: nil)
        // The observer hops to the main queue and then a main-actor Task, so
        // poll with a deadline rather than trusting one fixed sleep.
        let deadline = Date().addingTimeInterval(5)
        while syncs < 1, Date() < deadline {
            try await Task.sleep(for: .milliseconds(20))
        }
        #expect(syncs >= 1, "an Agent Access flip on the manager's own centre did not reach it")
    }

    // MARK: - Reviewed follows the commits

    @Test func reviewedFollowsTheCommitList() throws {
        let suite = "ReviewGalleryRegistryTests-\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }

        let reviewed = ReviewGalleryReviewed(defaults: defaults)
        #expect(!reviewed.isReviewed(id: "M99", commits: ["aaaaaaa"]))
        reviewed.setReviewed(true, id: "M99", commits: ["aaaaaaa"])
        #expect(reviewed.isReviewed(id: "M99", commits: ["aaaaaaa"]))

        // A fix landed on the same surface: the list grew, so it is unreviewed.
        #expect(!reviewed.isReviewed(id: "M99", commits: ["aaaaaaa", "bbbbbbb"]))
        // Another entry is untouched.
        #expect(!reviewed.isReviewed(id: "M98", commits: ["aaaaaaa"]))

        // It is kept on this Mac, not in memory.
        let again = ReviewGalleryReviewed(defaults: defaults)
        #expect(again.isReviewed(id: "M99", commits: ["aaaaaaa"]))

        again.setReviewed(false, id: "M99", commits: ["aaaaaaa"])
        #expect(!ReviewGalleryReviewed(defaults: defaults).isReviewed(id: "M99", commits: ["aaaaaaa"]))
    }
}
