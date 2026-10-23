import Foundation
import JavaScriptCore
import Testing
@testable import Bristlenose

/// The report's per-viewer preferences must outlive the web view (R89).
///
/// The SPA keeps zoom, panel open state and panel widths in localStorage, and
/// on the Mac that storage is `.nonPersistent()` per serve session — so without
/// a saved copy they were forgotten on every relaunch, serve restart and last
/// window closed. The subtitle-prefs mirror made generic: these pin the
/// allowlist against the shared contract, the save, and the seed.
@MainActor
struct ReportPrefsMirrorTests {

    nonisolated private static let contractURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("tests/fixtures/report-prefs-contract.json")

    private func contract() throws -> [String: Any] {
        let data = try Data(contentsOf: Self.contractURL)
        return try #require(try JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func isolatedDefaults() throws -> (UserDefaults, String) {
        let suite = "ReportPrefsMirrorTests.\(UUID().uuidString)"
        return (try #require(UserDefaults(suiteName: suite)), suite)
    }

    /// Runs a seed script against a stub localStorage holding `existing`, and
    /// returns what the stub holds afterwards.
    private func runSeed(_ script: String, existing: [String: String] = [:]) throws -> [String: String] {
        let ctx = try #require(JSContext())
        var store = existing
        let get: @convention(block) (String) -> Any = { key in store[key] ?? NSNull() }
        let set: @convention(block) (String, String) -> Void = { key, value in store[key] = value }
        let storage = try #require(JSValue(newObjectIn: ctx))
        storage.setObject(get, forKeyedSubscript: "getItem" as NSString)
        storage.setObject(set, forKeyedSubscript: "setItem" as NSString)
        ctx.setObject(storage, forKeyedSubscript: "localStorage" as NSString)
        ctx.evaluateScript("var sideEffect = false;")
        ctx.evaluateScript(script)
        #expect(ctx.exception == nil)
        #expect(ctx.objectForKeyedSubscript("sideEffect").toBool() == false)
        // The page gets no globals from the seed.
        #expect(ctx.objectForKeyedSubscript("p").isUndefined)
        #expect(ctx.objectForKeyedSubscript("k").isUndefined)
        return store
    }

    @Test func allowlistMatchesTheContract() throws {
        let keys = try #require(try contract()["keys"] as? [String])
        #expect(BridgeHandler.reportPrefKeys == Set(keys))
        #expect(try contract()["message_type"] as? String == "report-pref")
        #expect(try contract()["max_value_length"] as? Int == BridgeHandler.reportPrefMaxLength)
        #expect(try contract()["key_prefixes"] as? [String] == BridgeHandler.reportPrefKeyPrefixes)
        #expect(try contract()["max_key_length"] as? Int == BridgeHandler.reportPrefMaxKeyLength)
    }

    @Test func aListedKeyIsSavedAndNullRemovesIt() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }

        BridgeHandler.storeReportPref(key: "bn-toc-width", value: "300", defaults: defaults)
        BridgeHandler.storeReportPref(key: "bristlenose-zoom", value: "1.2", defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults)
                == ["bn-toc-width": "300", "bristlenose-zoom": "1.2"])

        BridgeHandler.storeReportPref(key: "bristlenose-zoom", value: NSNull(), defaults: defaults)
        BridgeHandler.storeReportPref(key: "bn-toc-width", value: nil, defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults).isEmpty)
    }

    @Test func anUnlistedKeyAnOverlongValueOrANonStringIsRefused() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }

        BridgeHandler.storeReportPref(key: "bn-inspector-source", value: "cb-1", defaults: defaults)
        BridgeHandler.storeReportPref(
            key: "bn-toc-width",
            value: String(repeating: "9", count: BridgeHandler.reportPrefMaxLength + 1),
            defaults: defaults)
        BridgeHandler.storeReportPref(key: "bn-tags-width", value: 300, defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults).isEmpty)
        // Refused at the door, not only filtered on the way out.
        #expect(defaults.object(forKey: BridgeHandler.reportPrefsDefaultsKey) == nil)

        // A refused value leaves the saved one standing.
        BridgeHandler.storeReportPref(key: "bn-toc-width", value: "300", defaults: defaults)
        BridgeHandler.storeReportPref(key: "bn-toc-width", value: 310, defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults) == ["bn-toc-width": "300"])
    }

    @Test func theSeedFillsAFreshWebViewAndKeepsALiveOne() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }
        BridgeHandler.storeReportPref(key: "bristlenose-zoom", value: "1.2", defaults: defaults)
        BridgeHandler.storeReportPref(key: "bn-toc-open", value: "true", defaults: defaults)
        let script = BridgeHandler.reportPrefsSeedScript(defaults: defaults)

        // A new serve session's partition is empty: everything saved comes back.
        #expect(try runSeed(script) == ["bristlenose-zoom": "1.2", "bn-toc-open": "true"])

        // A second window on a partition already in use keeps what is live.
        #expect(try runSeed(script, existing: ["bn-toc-open": "false"])
                == ["bristlenose-zoom": "1.2", "bn-toc-open": "false"])
    }

    @Test func aHostileValueIsCarriedAsDataNotCode() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }
        let hostile = "'); sideEffect = true; //\u{2028}</"
        BridgeHandler.storeReportPref(key: "bn-inspector-dimension", value: hostile, defaults: defaults)
        let script = BridgeHandler.reportPrefsSeedScript(defaults: defaults)
        #expect(try runSeed(script) == ["bn-inspector-dimension": hostile])
    }

    @Test func aKeyDroppedFromTheAllowlistIsNotSeeded() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }
        // As an older build might have saved it.
        defaults.set(["bn-retired": "x", "bn-tags-open": "true"], forKey: BridgeHandler.reportPrefsDefaultsKey)
        let script = BridgeHandler.reportPrefsSeedScript(defaults: defaults)
        #expect(try runSeed(script) == ["bn-tags-open": "true"])
    }

    @Test func theQuoteGroupingIsTakenByPrefix() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }
        BridgeHandler.storeReportPref(key: "bristlenose-quote-grouping-1", value: "session", defaults: defaults)
        BridgeHandler.storeReportPref(
            key: "bristlenose-quote-grouping-" + String(repeating: "x", count: BridgeHandler.reportPrefMaxKeyLength),
            value: "session", defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults) == ["bristlenose-quote-grouping-1": "session"])
    }

    /// Through a throwaway suite: the test host is the real app, so
    /// `UserDefaults.standard` is the researcher's own preferences.
    @Test func theBridgeMessageReachesTheStore() throws {
        let (defaults, suite) = try isolatedDefaults()
        defer { defaults.removePersistentDomain(forName: suite) }

        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "report-pref", "key": "bn-tags-width", "value": "320"], defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults) == ["bn-tags-width": "320"])
        bridge.handleMessage(["type": "report-pref", "key": "bn-tags-width", "value": NSNull()], defaults: defaults)
        #expect(BridgeHandler.savedReportPrefs(defaults: defaults).isEmpty)
    }
}
