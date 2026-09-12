import Testing
import Foundation
@testable import Bristlenose

/// The Swift half of the PII model handoff.
///
/// The asymmetry between the two environment variables is the whole point of
/// this suite, and it is a privacy decision rather than a plumbing detail: the
/// enabled flag travels even with no pack, so a run the researcher asked to be
/// redacted fails loudly instead of proceeding unredacted.
@Suite("PII model pack handoff")
struct PIIModelPackTests {

    private static func makeDirectory(_ files: [String]) throws -> URL {
        let dir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("pii-pack-\(UUID().uuidString)")
            .appendingPathComponent("en_core_web_lg-3.8.0")
        try FileManager.default.createDirectory(
            at: dir, withIntermediateDirectories: true
        )
        for name in files {
            try "x".write(
                to: dir.appendingPathComponent(name), atomically: true, encoding: .utf8
            )
        }
        return dir
    }

    @Test("off yields no environment at all")
    func offIsSilent() throws {
        let dir = try Self.makeDirectory(PIIModelPack.requiredFiles)
        let env = PIIModelPack.packEnvironment(enabled: false, packDirectory: dir)
        #expect(env.isEmpty, "redaction is off; the sidecar environment must be untouched")
    }

    @Test("enabled with no pack still sets the flag, so the run fails loudly")
    func enabledWithoutPackStillFlags() {
        let env = PIIModelPack.packEnvironment(enabled: true, packDirectory: nil)

        #expect(env["BRISTLENOSE_PII_ENABLED"] == "1")
        #expect(env["BRISTLENOSE_PII_MODEL_DIR"] == nil)
        // Withholding the flag would be the worse bug: the researcher asked for
        // redaction, the run would proceed without it, and nothing would say
        // so. Stage 7 abandons with MISSING_DEP instead.
    }

    @Test("a loadable pack is handed over by path")
    func loadablePackIsPassed() throws {
        let dir = try Self.makeDirectory(PIIModelPack.requiredFiles)
        let env = PIIModelPack.packEnvironment(enabled: true, packDirectory: dir)

        #expect(env["BRISTLENOSE_PII_ENABLED"] == "1")
        #expect(env["BRISTLENOSE_PII_MODEL_DIR"] == dir.path)
    }

    @Test("a half-unpacked pack is not handed over", arguments: [
        ["config.cfg"],   // meta.json missing — spaCy reads it FIRST
        ["meta.json"],    // config.cfg missing
        [],               // nothing arrived
    ])
    func halfUnpackedPackIsRefused(files: [String]) throws {
        let dir = try Self.makeDirectory(files)
        let env = PIIModelPack.packEnvironment(enabled: true, packDirectory: dir)

        #expect(env["BRISTLENOSE_PII_ENABLED"] == "1")
        #expect(
            env["BRISTLENOSE_PII_MODEL_DIR"] == nil,
            """
            an incomplete pack must not be handed over: Python's resolver raises \
            on it by design rather than falling back to the package name, and \
            that fallback makes Presidio shell out to pip install from GitHub — \
            a §2.5.2 violation inside a sandboxed App Store binary
            """
        )
    }

    @Test("the liveness check needs BOTH files, in spaCy's own order")
    func livenessNeedsBothFiles() throws {
        #expect(PIIModelPack.requiredFiles == ["meta.json", "config.cfg"])

        let complete = try Self.makeDirectory(["meta.json", "config.cfg"])
        #expect(PIIModelPack.isLoadableModelDirectory(complete))

        let configOnly = try Self.makeDirectory(["config.cfg"])
        #expect(
            !PIIModelPack.isLoadableModelDirectory(configOnly),
            """
            checking config.cfg alone lets a directory through that then dies \
            inside spaCy with an opaque E053 — the failure this check replaces
            """
        )
    }

    // MARK: - the storage seam both acquirers write into

    private static func scratchDefaults() -> UserDefaults {
        let suite = "pii-pack-tests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        d.removePersistentDomain(forName: suite)
        return d
    }

    @Test("nothing stored means no pack, and the flag still travels")
    func nothingStoredIsNoPack() {
        let d = Self.scratchDefaults()
        d.set(true, forKey: PIIModelPack.enabledDefaultsKey)

        #expect(PIIModelPack.acquiredPackDirectory(defaults: d) == nil)
        let env = PIIModelPack.currentEnvironment(defaults: d)
        #expect(env["BRISTLENOSE_PII_ENABLED"] == "1")
        #expect(env["BRISTLENOSE_PII_MODEL_DIR"] == nil)
    }

    @Test("a stored, loadable pack reaches the sidecar by path")
    func storedLoadablePackIsHandedOver() throws {
        let dir = try Self.makeDirectory(PIIModelPack.requiredFiles)
        let d = Self.scratchDefaults()
        d.set(true, forKey: PIIModelPack.enabledDefaultsKey)
        d.set(dir.path, forKey: PIIModelPack.packDirectoryDefaultsKey)

        let env = PIIModelPack.currentEnvironment(defaults: d)
        #expect(env["BRISTLENOSE_PII_MODEL_DIR"] == dir.path)
    }

    @Test("a stored path whose pack has gone yields the flag alone — fail loudly, not silently")
    func storedButReclaimedPackIsNotHandedOver() throws {
        // The system may reclaim a Background Assets pack under storage
        // pressure; the stored path then points at nothing. The run must
        // fail with MISSING_DEP, not proceed unredacted.
        let gone = try Self.makeDirectory(PIIModelPack.requiredFiles)
        try FileManager.default.removeItem(at: gone)
        let d = Self.scratchDefaults()
        d.set(true, forKey: PIIModelPack.enabledDefaultsKey)
        d.set(gone.path, forKey: PIIModelPack.packDirectoryDefaultsKey)

        let env = PIIModelPack.currentEnvironment(defaults: d)
        #expect(env["BRISTLENOSE_PII_ENABLED"] == "1")
        #expect(env["BRISTLENOSE_PII_MODEL_DIR"] == nil)
    }

    @Test("an empty stored path is 'nothing stored', not a path to cwd")
    func emptyStoredPathIsNil() {
        let d = Self.scratchDefaults()
        d.set("", forKey: PIIModelPack.packDirectoryDefaultsKey)
        #expect(PIIModelPack.acquiredPackDirectory(defaults: d) == nil)
    }
}
