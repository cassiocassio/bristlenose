import Foundation
import Testing
@testable import Bristlenose

/// Claude's runtime `.mcpb` for the native helper (design-mcp-native-proxy §6.9
/// P4). The contract is small and every clause of it is load-bearing: a binary
/// server, launched from the extracted folder, naming its host, at a version
/// Claude will accept as an update — and one executable bit.
@Suite("Native extension package")
struct NativeExtensionPackageTests {

    private func manifest(_ version: String = "0.32.0") throws -> [String: Any] {
        try #require(JSONSerialization.jsonObject(
            with: NativeExtensionPackage.manifest(version: version)) as? [String: Any])
    }

    @Test func manifest_declaresABinaryServer_thatNamesItsHost() throws {
        let m = try manifest()
        let server = try #require(m["server"] as? [String: Any])
        #expect(server["type"] as? String == "binary")
        #expect(server["entry_point"] as? String == "server/bristlenose-mcp")
        let config = try #require(server["mcp_config"] as? [String: Any])
        #expect(config["command"] as? String == "${__dirname}/server/bristlenose-mcp")
        #expect((config["env"] as? [String: String])?["BRISTLENOSE_MCP_HOST"] == "Claude")
    }

    @Test func manifest_keepsTheNodeExtensionsName_soItReplacesIt() throws {
        // Same `name` → same Claude extension id (local.mcpb.bristlenose.bristlenose),
        // so installing the native package updates the Node one in place.
        #expect(try manifest()["name"] as? String == "bristlenose")
    }

    @Test func manifest_versionIsThePlainRelease() throws {
        // A "-<build>" suffix is a semver pre-release and sorts BELOW the
        // release, which would read as a downgrade of the Node extension.
        #expect(try manifest("0.32.0")["version"] as? String == "0.32.0")
    }

    @Test func archive_storesTheHelperExecutable_andTheRestNot() throws {
        let helper = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("helper-\(UUID())")
        try Data("#!/bin/sh\n".utf8).write(to: helper)
        defer { try? FileManager.default.removeItem(at: helper) }
        let zip = try NativeExtensionPackage.build(helper: helper, iconPNG: Data([1, 2, 3]), version: "0.32.0")
        let modes = Self.centralDirectoryModes(zip)
        #expect(modes["server/bristlenose-mcp"] == 0o100755)
        #expect(modes["manifest.json"] == 0o100644)
        #expect(modes["icon.png"] == 0o100644)
        #expect(modes["server/"] == 0o040755)
    }

    @Test func crc32_matchesTheStandardCheckValue() {
        #expect(ZipWriter.crc32(Data("123456789".utf8)) == 0xCBF43926)
    }

    /// Read each central-directory record's name and Unix mode.
    private static func centralDirectoryModes(_ zip: Data) -> [String: UInt32] {
        let bytes = [UInt8](zip)
        func u16(_ i: Int) -> Int { Int(bytes[i]) | Int(bytes[i + 1]) << 8 }
        func u32(_ i: Int) -> UInt32 { UInt32(u16(i)) | UInt32(u16(i + 2)) << 16 }
        var out: [String: UInt32] = [:]
        var i = 0
        while i + 46 <= bytes.count {
            if u32(i) == 0x02014b50 {
                let nameLen = u16(i + 28), extra = u16(i + 30), comment = u16(i + 32)
                let name = String(decoding: bytes[(i + 46)..<(i + 46 + nameLen)], as: UTF8.self)
                out[name] = u32(i + 38) >> 16
                i += 46 + nameLen + extra + comment
            } else {
                i += 1
            }
        }
        return out
    }
}
