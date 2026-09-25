import Foundation
import Testing
@testable import Bristlenose

/// The rule behind `SidebarAutosaveMigration`: remove a stored projects-column
/// width only when AppKit would clamp it (below the minimum), keep everything
/// else, and never touch what it cannot parse.
struct SidebarAutosaveMigrationTests {
    typealias M = SidebarAutosaveMigration

    /// Exactly the shape AppKit wrote on 25 Sep 2026 (read from the container).
    static func frames(sidebar: Double, collapsed: Bool = false) -> [String] {
        [
            "0.000000, 0.000000, \(String(format: "%.6f", sidebar)), 827.000000, \(collapsed ? "YES" : "NO"), NO",
            "\(String(format: "%.6f", sidebar)), 0.000000, 946.000000, 827.000000, NO, NO",
        ]
    }

    static func key(_ window: String) -> String { M.keyPrefix + window + M.keySuffix }

    // MARK: Parsing

    @Test func readsTheSidebarWidthFromAppKitsShape() {
        #expect(M.sidebarWidth(from: Self.frames(sidebar: 148)) == 148)
        #expect(M.sidebarWidth(from: Self.frames(sidebar: 209)) == 209)
        #expect(M.sidebarWidth(from: Self.frames(sidebar: 148, collapsed: true)) == 148)
    }

    @Test func refusesWhatItCannotParse() {
        #expect(M.sidebarWidth(from: "0, 0, 148, 827, NO, NO") == nil)           // not an array
        #expect(M.sidebarWidth(from: [String]()) == nil)                          // empty
        #expect(M.sidebarWidth(from: ["0, 0, wide, 827, NO, NO"]) == nil)         // width not a number
        #expect(M.sidebarWidth(from: ["0, 0"]) == nil)                            // too few fields
        #expect(M.sidebarWidth(from: [148, 827]) == nil)                          // not strings
        #expect(M.sidebarWidth(from: ["0, 0, -5, 827, NO, NO"]) == nil)           // negative
        #expect(M.sidebarWidth(from: ["0, 0, nan, 827, NO, NO"]) == nil)          // non-finite
    }

    // MARK: The rule

    @Test func removesOnlyWidthsBelowTheMinimum() {
        let stored: [String: Any] = [
            Self.key("main-AppWindow-5"): Self.frames(sidebar: 148),                    // pre-fix resting width
            Self.key("main-AppWindow-6"): Self.frames(sidebar: 148, collapsed: true),   // same, stored collapsed
            Self.key("main-AppWindow-7"): Self.frames(sidebar: 180),                    // the old minimum
            Self.key("main-AppWindow-1"): Self.frames(sidebar: 209),                    // a researcher's drag
            Self.key("main-AppWindow-2"): Self.frames(sidebar: 200),                    // exactly the minimum
            Self.key("main-AppWindow-3"): Self.frames(sidebar: 300),                    // the maximum
            Self.key("main-AppWindow-9"): ["garbage"],                                  // unparseable
        ]
        #expect(M.keysToRemove(in: stored, below: 200) == [
            Self.key("main-AppWindow-5"), Self.key("main-AppWindow-6"), Self.key("main-AppWindow-7"),
        ])
    }

    @Test func leavesOtherSplitViewsAndOtherKeysAlone() {
        let stored: [String: Any] = [
            M.keyPrefix + "main-AppWindow-1, SomeOtherSplitView": Self.frames(sidebar: 100),
            "NSWindow Frame main-AppWindow-1": "40 40 1155 827 0 0 1728 1079",
            "BristlenoseSidebarTintAlpha": 0.22,
        ]
        #expect(M.keysToRemove(in: stored, below: 200).isEmpty)
    }

    // MARK: Against a real defaults domain

    @Test func runRemovesTheClampedEntriesAndIsIdempotent() throws {
        let suite = "SidebarAutosaveMigrationTests.\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set(Self.frames(sidebar: 148), forKey: Self.key("main-AppWindow-5"))
        defaults.set(Self.frames(sidebar: 209), forKey: Self.key("main-AppWindow-1"))
        defaults.set("not frames", forKey: Self.key("main-AppWindow-9"))

        let first = M.run(defaults: defaults, minimum: 200)
        #expect(first == [Self.key("main-AppWindow-5")])
        #expect(defaults.object(forKey: Self.key("main-AppWindow-5")) == nil)
        #expect(defaults.stringArray(forKey: Self.key("main-AppWindow-1")) == Self.frames(sidebar: 209))
        #expect(defaults.string(forKey: Self.key("main-AppWindow-9")) == "not frames")

        // No marker needed: the rule is a function of the stored width, so a
        // second launch finds nothing to do.
        #expect(M.run(defaults: defaults, minimum: 200).isEmpty)
    }

    @Test func theAppRunsItAtTheCurrentMinimum() {
        // The default argument is the live constant, so raising the minimum
        // again carries the migration with it.
        let stored: [String: Any] = [Self.key("w"): Self.frames(sidebar: SidebarAutoCollapse.columnMin - 1)]
        #expect(M.keysToRemove(in: stored, below: SidebarAutoCollapse.columnMin).count == 1)
    }
}
