import AppKit
import SwiftUI
import Testing
import WebKit
@testable import Bristlenose

// The app's OWN window, measured. App-hosted tests run inside Bristlenose.app,
// which opens its real ContentView window (Welcome pane, no project) before
// any test runs — so the real NavigationSplitView, the real
// ProjectSidebarOutline column and the real toolbar are available to read
// without a harness stand-in. Diagnosis only; no production code is touched.
//
// Why: the live trace (pid 91553, 25 Sep 2026) shows the app's column resting
// at 180 (its minimum) from the first geometry pass at launch, and returning
// to 180 after every show — while every harness variant (List, outline-shaped
// stand-in, real SPA) rests at the 220 ideal and returns to the pre-hide
// width. This reads what AppKit was told for the REAL column, what the column's
// content offers as a fitting width, and whether a divider position survives
// SwiftUI updates (a window nudge drives ContentView's geometry readers, whose
// @State writes re-run body and update the split view).

@MainActor
private enum Probe {
    static func findSplit(_ v: NSView?) -> NSSplitView? {
        guard let v else { return nil }
        if let s = v as? NSSplitView { return s }
        for sub in v.subviews { if let s = findSplit(sub) { return s } }
        return nil
    }

    static func describe(_ v: NSView, depth: Int, max: Int, into out: inout String) {
        let pad = String(repeating: "  ", count: depth)
        let cls = String(describing: type(of: v))
        let f = v.frame
        let ic = v.intrinsicContentSize
        out += "\(pad)\(cls) frame=(\(Int(f.minX)),\(Int(f.minY)) \(Int(f.width))x\(Int(f.height))) intrinsic=(\(Int(ic.width)),\(Int(ic.height))) fitting=\(Int(v.fittingSize.width)) hidden=\(v.isHidden) hugging=\(Int(v.contentHuggingPriority(for: .horizontal).rawValue)) compress=\(Int(v.contentCompressionResistancePriority(for: .horizontal).rawValue))\n"
        guard depth < max else { return }
        for sub in v.subviews { describe(sub, depth: depth + 1, max: max, into: &out) }
    }

    static func report(_ label: String, window: NSWindow, split: NSSplitView, depth: Int = 3) -> String {
        var out = "=== \(label)\n"
        out += "window frameW=\(Int(window.frame.width)) contentW=\(Int(window.contentView?.frame.width ?? -1)) toolbar=\(window.toolbar != nil)\n"
        out += "split frame=\(Int(split.frame.width)) dividerThickness=\(split.dividerThickness) vertical=\(split.isVertical) arranged=\(split.arrangedSubviews.count)\n"
        if let c = split.delegate as? NSSplitViewController {
            for (i, item) in c.splitViewItems.enumerated() {
                out += "item[\(i)] behavior=\(item.behavior.rawValue) collapsed=\(item.isCollapsed) min=\(Int(item.minimumThickness)) max=\(Int(item.maximumThickness)) preferredFraction=\(item.preferredThicknessFraction) holding=\(Int(item.holdingPriority.rawValue)) canCollapse=\(item.canCollapse) canCollapseFromResize=\(item.canCollapseFromWindowResize) autoMax=\(Int(item.automaticMaximumThickness)) allowsFullHeight=\(item.allowsFullHeightLayout)\n"
            }
        } else {
            out += "delegate is not NSSplitViewController: \(String(describing: split.delegate))\n"
        }
        for (i, v) in split.arrangedSubviews.enumerated() {
            out += "arranged[\(i)] x=\(Int(v.frame.minX)) w=\(Int(v.frame.width)) collapsed=\(split.isSubviewCollapsed(v))\n"
        }
        if let column = split.arrangedSubviews.first {
            out += "-- sidebar column subtree (depth \(depth)):\n"
            describe(column, depth: 0, max: depth, into: &out)
        }
        return out
    }
}

@Suite(.serialized, .enabled(if: sidebarDiagnosisEnabled)) @MainActor struct SidebarRealWindowProbeTests {

    /// The app's real window: what the column was told, what its content
    /// offers, and whether a divider position survives SwiftUI updates.
    @Test func p01_theAppsOwnColumn() async {
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        guard let window = NSApp.windows.first(where: { $0.isVisible && Probe.findSplit($0.contentView) != nil }),
              let split = Probe.findSplit(window.contentView) else {
            Attachment.record("no visible window with an NSSplitView — app window not up", named: "p01-no-window.txt")
            return
        }
        var text = ""
        text += Probe.report("launch (as found)", window: window, split: split)
        // The split view AUTOSAVES the column (`main-AppWindow-1,
        // SidebarNavigationSplitView`, measured by p03) into the container
        // this test host shares with the real app, so every move below is
        // put back before the test ends — or the next real launch restores
        // whatever this test left.
        let launchWidth = split.arrangedSubviews.first?.frame.width ?? SidebarAutoCollapse.columnIdeal

        // A divider position, then SwiftUI churn: nudging the window width
        // drives ContentView's two geometry readers, whose @State writes
        // re-run body and update the NavigationSplitView. If SwiftUI
        // re-applies a column width on update, the divider will not hold.
        split.setPosition(260, ofDividerAt: 0)
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        text += Probe.report("after setPosition(260)", window: window, split: split, depth: 0)

        let base = window.frame
        for _ in 0..<3 {
            var f = base; f.size.width += 1; window.setFrame(f, display: true, animate: false)
            try? await Task.sleep(nanoseconds: 120_000_000)
            window.setFrame(base, display: true, animate: false)
            try? await Task.sleep(nanoseconds: 120_000_000)
        }
        try? await Task.sleep(nanoseconds: 2_000_000_000)
        text += Probe.report("after 3 window nudges (+1/−1) and 2 s", window: window, split: split, depth: 0)

        let controller = split.delegate as? NSSplitViewController
        _ = NSApp.sendAction(#selector(NSSplitViewController.toggleSidebar(_:)), to: controller, from: nil)
        try? await Task.sleep(nanoseconds: 1_200_000_000)
        text += Probe.report("after toolbar hide", window: window, split: split, depth: 0)
        _ = NSApp.sendAction(#selector(NSSplitViewController.toggleSidebar(_:)), to: controller, from: nil)
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        text += Probe.report("after toolbar show", window: window, split: split, depth: 0)

        // A bigger jump, as a zoom or full-screen exit lands.
        var wide = base; wide.size.width = base.width + 300
        window.setFrame(wide, display: true, animate: false)
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        text += Probe.report("after window +300", window: window, split: split, depth: 0)
        window.setFrame(base, display: true, animate: false)
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        text += Probe.report("after window back", window: window, split: split, depth: 0)

        split.setPosition(launchWidth, ofDividerAt: 0)
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        text += Probe.report("restored to launch width \(Int(launchWidth))", window: window, split: split, depth: 0)
        #expect(abs((split.arrangedSubviews.first?.frame.width ?? -1) - launchWidth) <= 1,
                "column not restored to its launch width; the shared autosave now carries this test's value")

        Attachment.record(text, named: "p01-real-window.txt")
    }

    /// What the app's own defaults hold about split views and window frames.
    /// The container plist is TCC-blocked from outside (desktop/CLAUDE.md), so
    /// `defaults read app.bristlenose` from a shell reports the domain absent
    /// whatever it holds; only the app itself can read it. If AppKit or
    /// SwiftUI persists column frames, the key is here or nowhere.
    @Test func p03_theAppsOwnDefaults() async {
        var text = "=== UserDefaults keys mentioning split / frame / column / sidebar / Navigation\n"
        let all = UserDefaults.standard.dictionaryRepresentation()
        let hits = all.keys.filter { k in
            let l = k.lowercased()
            return l.contains("split") || l.contains("frame") || l.contains("column") || l.contains("sidebar") || l.contains("navigation")
        }.sorted()
        for k in hits { text += "\(k) = \(String(describing: all[k]).prefix(300))\n" }
        text += "(\(hits.count) of \(all.count) keys)\n"
        if let window = NSApp.windows.first(where: { $0.isVisible && Probe.findSplit($0.contentView) != nil }),
           let split = Probe.findSplit(window.contentView) {
            text += "split.autosaveName=\(split.autosaveName.map { "'\($0)'" } ?? "nil") window.frameAutosaveName='\(window.frameAutosaveName)' identifier=\(window.identifier?.rawValue ?? "nil")\n"
            text += "column now w=\(Int(split.arrangedSubviews.first?.frame.width ?? -1))\n"
            // Read-only. On 25 Sep 2026 this step also moved the divider and
            // read the key again 1.5 s later: the entry had been rewritten
            // to the new position — the write-back that makes the column's
            // width a restored value on every launch after the first.
        }
        Attachment.record(text, named: "p03-defaults.txt")
    }

    // MARK: Does the migration run before the window restores? (two launches)
    //
    // Run p04 alone, then p05 alone, as two xcodebuild invocations: the
    // question is about what happens at LAUNCH, so it takes a launch between
    // them. p04 seeds a width below the minimum into this window's own
    // autosave key and records the original; p05, in the next process, reads
    // where the column opened — the ideal if `SidebarAutosaveMigration` ran
    // in `applicationWillFinishLaunching` before the split view restored, the
    // minimum (clamped) if it ran too late or not at all — and then drags the
    // divider back to the recorded width, so AppKit itself rewrites the key.
    // The container is shared with any running copy of the app; if that copy
    // lays out its first window in between, p05 reads its width instead and
    // says so.

    static let seedRecord = "BristlenoseDiagnosisAutosaveSeed"

    @Test func p04_seedABelowMinimumWidth() async throws {
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        let window = try #require(NSApp.windows.first(where: { $0.isVisible && Probe.findSplit($0.contentView) != nil }))
        let split = try #require(Probe.findSplit(window.contentView))
        let name = try #require(split.autosaveName, "the app's split view has no autosave name")
        let key = SidebarAutosaveMigration.keyPrefix + name
        let original = UserDefaults.standard.stringArray(forKey: key)
        let originalWidth = Double(split.arrangedSubviews.first?.frame.width ?? SidebarAutoCollapse.columnIdeal)
        // Move off the ideal first, so the three outcomes differ in p05:
        // 220 = migrated before restore, 200 = restored and clamped,
        // 240 = this process rewrote the key on its way out (seed lost).
        split.setPosition(240, ofDividerAt: 0)
        try? await Task.sleep(nanoseconds: 1_000_000_000)
        let seeded = ["0.000000, 0.000000, 150.000000, 827.000000, NO, NO",
                      "150.000000, 0.000000, 1005.000000, 827.000000, NO, NO"]
        UserDefaults.standard.set([
            "key": key,
            "pid": Int(ProcessInfo.processInfo.processIdentifier),
            "originalWidth": originalWidth,
            "original": original ?? [],
        ] as [String: Any], forKey: Self.seedRecord)
        UserDefaults.standard.set(seeded, forKey: key)
        UserDefaults.standard.synchronize()
        Attachment.record("seeded \(key)\n  was: \(original ?? [])\n  now: \(seeded)\n  pid \(ProcessInfo.processInfo.processIdentifier)",
                          named: "p04-seed.txt")
    }

    @Test func p05_nextLaunchOpensAtTheIdeal() async throws {
        guard let record = UserDefaults.standard.dictionary(forKey: Self.seedRecord),
              let key = record["key"] as? String,
              let seedPid = record["pid"] as? Int,
              let originalWidth = record["originalWidth"] as? Double else {
            Attachment.record("no seed record — run p04 in a previous launch first", named: "p05-skipped.txt")
            return
        }
        guard seedPid != Int(ProcessInfo.processInfo.processIdentifier) else {
            Attachment.record("seeded in THIS process; the question needs a launch in between", named: "p05-skipped.txt")
            return
        }
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        let window = try #require(NSApp.windows.first(where: { $0.isVisible && Probe.findSplit($0.contentView) != nil }))
        let split = try #require(Probe.findSplit(window.contentView))
        let opened = split.arrangedSubviews.first?.frame.width ?? -1
        let keyNow = UserDefaults.standard.stringArray(forKey: key) ?? []

        // Put the researcher's width back through AppKit, which rewrites the key.
        split.setPosition(CGFloat(originalWidth), ofDividerAt: 0)
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        let restored = split.arrangedSubviews.first?.frame.width ?? -1
        UserDefaults.standard.removeObject(forKey: Self.seedRecord)

        Attachment.record("""
            key \(key)
            seeded in pid \(seedPid); this launch pid \(ProcessInfo.processInfo.processIdentifier)
            column opened at \(Int(opened)) (ideal \(Int(SidebarAutoCollapse.columnIdeal)), clamped would be \(Int(SidebarAutoCollapse.columnMin)))
            key at test start: \(keyNow)
            restored to the recorded \(Int(originalWidth)): column now \(Int(restored)); key \(UserDefaults.standard.stringArray(forKey: key) ?? [])
            """, named: "p05-verify.txt")
        #expect(abs(opened - SidebarAutoCollapse.columnIdeal) <= 1,
                "column opened at \(opened): the migration did not run before the restore (or another copy of the app rewrote \(key))")
        #expect(abs(restored - CGFloat(originalWidth)) <= 1, "could not put the recorded width \(originalWidth) back")
    }

    /// Control: the harness's List sidebar under the same divider + churn.
    @Test func p02_harnessListUnderChurn() async {
        let rig = await SidebarFitRig(width: 1200, minWidth: 0)
        defer { rig.close() }
        guard let split = rig.splitController?.splitView else { return }
        var text = ""
        text += Probe.report("harness launch 1200", window: rig.window, split: split)
        split.setPosition(260, ofDividerAt: 0)
        await rig.settle(1.0)
        text += Probe.report("harness after setPosition(260)", window: rig.window, split: split, depth: 0)
        for _ in 0..<3 { await rig.resize(to: 1201, settleFor: 0.12); await rig.resize(to: 1200, settleFor: 0.12) }
        await rig.settle(2.0)
        text += Probe.report("harness after nudges", window: rig.window, split: split, depth: 0)
        await rig.appKitToggle(); await rig.appKitToggle()
        await rig.settle(0.8)
        text += Probe.report("harness after hide/show", window: rig.window, split: split, depth: 0)
        Attachment.record(text, named: "p02-harness-list.txt")
    }
}
