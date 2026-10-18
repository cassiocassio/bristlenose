import AppKit
import Foundation
import SwiftUI
import Testing

@testable import Bristlenose

/// The Send-to-Miro sheet against a live serve and a real Miro board — the sheet's own model,
/// doing what its buttons do, with the creating step rendered at the states the build passed
/// through. Off unless a serve is named, because it makes real boards in a real Miro account:
///
///     TEST_RUNNER_BN_LIVE_MIRO_PORT=8176 TEST_RUNNER_BN_LIVE_MIRO_TOKEN=<serve's auth token> \
///       xcodebuild test-without-building … -only-testing:BristlenoseTests/MiroSheetLiveTests
///
/// Each step's line, bar and time left are attached as `live-steps.tsv`, and a picture of the
/// sheet per phase as PNG (`xcrun xcresulttool export attachments`).
@MainActor
@Suite(.serialized, .enabled(if: ProcessInfo.processInfo.environment["BN_LIVE_MIRO_PORT"] != nil))
struct MiroSheetLiveTests {
    private let env = ProcessInfo.processInfo.environment
    private var port: Int { Int(env["BN_LIVE_MIRO_PORT"] ?? "") ?? 0 }
    private var token: String? { env["BN_LIVE_MIRO_TOKEN"] }

    private func i18n() throws -> I18n {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        return i18n
    }

    private func model(_ i18n: I18n, name: String) -> MiroSheetModel {
        let m = MiroSheetModel(port: port, token: token, projectName: "Rockclimbing", i18n: i18n)
        m.boardName = name
        return m
    }

    /// The sheet as it looks now, as a PNG.
    private func picture(_ m: MiroSheetModel) throws -> Data {
        let host = NSHostingView(rootView: MiroSheet(model: m))
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 400),
                              styleMask: [.borderless], backing: .buffered, defer: false)
        window.appearance = NSAppearance(named: .aqua)
        window.contentView = host
        host.layoutSubtreeIfNeeded()
        let size = host.fittingSize
        window.setContentSize(size)
        host.frame = NSRect(origin: .zero, size: size)
        host.layoutSubtreeIfNeeded()
        let rep = try #require(host.bitmapImageRepForCachingDisplay(in: host.bounds))
        host.cacheDisplay(in: host.bounds, to: rep)
        return try #require(rep.representation(using: .png, properties: [:]))
    }

    private func serverStatus() async throws -> String {
        var req = URLRequest(url: try #require(URL(string: "http://127.0.0.1:\(port)/api/projects/1/miro/board/status")))
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (data, _) = try await URLSession.shared.data(for: req)
        let json = try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
        return json["status"] as? String ?? "?"
    }

    /// Wait, sampling the sheet every half-second, until `done` says so or the deadline passes.
    private func follow(_ m: MiroSheetModel, label: String, log: inout [String], seen: inout Set<String>,
                        until done: () -> Bool, deadline: TimeInterval = 300) async throws {
        let start = Date()
        var last = ""
        while !done(), Date().timeIntervalSince(start) < deadline {
            let fraction = m.buildFraction().map { String(format: "%.2f", $0) } ?? "indeterminate"
            let row = "\(m.step)\t\(m.buildLine())\t\(fraction)\t\(m.buildETA() ?? "-")"
            if row != last {
                log.append(String(format: "%@\t%.1f\t%@", label, Date().timeIntervalSince(start), row))
                last = row
            }
            // One picture per kind of line (and once more when a time left first appears).
            let key = label + m.buildLine().replacingOccurrences(of: "[0-9]+", with: "#",
                                                                 options: .regularExpression)
                + (m.buildETA() == nil ? "" : "+eta")
            if m.step == .creating, seen.insert(key).inserted {
                Attachment.record(try picture(m), named: "\(label)-\(seen.count).png")
            }
            try await Task.sleep(nanoseconds: 500_000_000)
        }
    }

    @Test func aBoardBuildsWithProgressAndFinishes() async throws {
        let i18n = try i18n()
        let m = model(i18n, name: "Bristlenose Mac sheet test — delete me")
        await m.load()
        #expect(m.step == .configure)
        var log = ["run\tseconds\tstep\tline\tbar\ttime left"]
        var seen = Set<String>()
        m.createBoard()  // what Create Board does
        try await follow(m, label: "build", log: &log, seen: &seen, until: { m.step != .creating })
        Attachment.record(log.joined(separator: "\n"), named: "live-steps-build.tsv")
        Attachment.record(try picture(m), named: "build-done.png")
        #expect(m.step == .done)
        #expect(try await serverStatus() == "completed")
        // It said what it was counting, and the bar had a value once there was one.
        #expect(log.contains { $0.contains("Placing quotes") })
        #expect(log.contains { !$0.hasSuffix("indeterminate\t-") && $0.contains("\t0.") })
    }

    @Test func reopeningFollowsTheBuildAndStopStopsIt() async throws {
        let i18n = try i18n()
        let first = model(i18n, name: "Bristlenose Mac stop test — delete me")
        await first.load()
        var log = ["run\tseconds\tstep\tline\tbar\ttime left"]
        var seen = Set<String>()
        first.createBoard()
        try await follow(first, label: "first", log: &log, seen: &seen,
                         until: { first.buildLine().contains("Placing quotes") || first.step != .creating })
        #expect(first.step == .creating)

        // The sheet opened again while the board builds: it follows the build, not the form.
        let again = model(i18n, name: "")
        await again.load()
        #expect(again.step == .creating)
        try await follow(again, label: "reopened", log: &log, seen: &seen, until: { again.build != nil },
                         deadline: 10)

        // Stop on the reopened sheet (what its Cancel does): the server stops the build...
        again.cancelExport()
        var status = "running"
        for _ in 0..<120 where status == "running" {
            try await Task.sleep(nanoseconds: 500_000_000)
            status = try await serverStatus()
        }
        #expect(status == "cancelled")
        // ...and the first sheet, which did not ask, hands its form back rather than freezing.
        try await follow(first, label: "first-after-stop", log: &log, seen: &seen,
                         until: { first.step != .creating }, deadline: 10)
        Attachment.record(log.joined(separator: "\n"), named: "live-steps-stop.tsv")
        #expect(first.step == .configure)
    }
}
