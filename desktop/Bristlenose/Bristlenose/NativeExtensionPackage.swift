import Foundation

/// Claude Desktop's `.mcpb` for the native helper, built at install time
/// (design-mcp-native-proxy §6.9 P4).
///
/// Built now rather than at build time because the helper inside it must be the
/// one the app actually ships: the App Store re-signs `Contents/Helpers`, and
/// the `.dmg` export re-signs it Developer ID, but nothing re-signs a binary
/// sealed inside a zip. So the package is assembled from the signed copy in
/// `Contents/Helpers` whenever the researcher clicks Install.
///
/// The server is `type: binary`. Claude Desktop launches binary servers
/// through its own `Helpers/disclaimer`, so the helper runs as its own
/// responsible process; it is sandboxed and carries the team group either way,
/// which is what lets it read the handshake (§6.2). It names its host, so the
/// Claude tab compares against its own proxy (D8).
enum NativeExtensionPackage {

    static let helperName = "bristlenose-mcp"

    /// Pure: the manifest. `version` is the app's release, as the Node
    /// extension's is: Claude replaces an installed extension only for a
    /// HIGHER version (measured 29 Sep 2026), and semver sorts a
    /// `0.31.5-3906` pre-release below `0.31.5`, so appending the build would
    /// read as a downgrade of the Node extension it replaces.
    static func manifest(version: String) -> Data {
        let object: [String: Any] = [
            "manifest_version": "0.3",
            "name": "bristlenose",
            "display_name": "Bristlenose",
            "version": version,
            "description": "Ask your Bristlenose study — quotes, themes, signals, frameworks — from your agent. Read-only.",
            "author": ["name": "Bristlenose"],
            "icon": "icon.png",
            "server": [
                "type": "binary",
                "entry_point": "server/\(helperName)",
                "mcp_config": [
                    "command": "${__dirname}/server/\(helperName)",
                    "args": [String](),
                    "env": ["BRISTLENOSE_MCP_HOST": "Claude"],
                ] as [String: Any],
            ] as [String: Any],
            "tools_generated": true,
            "compatibility": [
                "claude_desktop": ">=1.13576.0",
                "platforms": ["darwin"],
            ] as [String: Any],
        ]
        return try! JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
    }

    /// Assemble the package. The helper is stored with mode 0755, so the
    /// executable bit survives Claude's extraction without a chmod of ours.
    static func build(helper: URL, iconPNG: Data?, version: String) throws -> Data {
        var entries: [ZipWriter.Entry] = [
            .init(path: "manifest.json", data: manifest(version: version), mode: 0o644),
            .init(path: "server/", data: Data(), mode: 0o755, isDirectory: true),
            .init(path: "server/\(helperName)", data: try Data(contentsOf: helper), mode: 0o755),
        ]
        if let iconPNG {
            entries.append(.init(path: "icon.png", data: iconPNG, mode: 0o644))
        }
        return ZipWriter.archive(entries)
    }
}

/// A minimal ZIP writer: stored (uncompressed) entries with Unix modes.
///
/// A sandboxed app cannot run `/usr/bin/zip` or `ditto`, and the one in-process
/// route Foundation offers (a coordinated read with `.forUploading`) decides
/// the entries' permissions itself. The package's whole contract is one
/// executable bit, so it is written here, where the bit is ours.
enum ZipWriter {

    struct Entry {
        let path: String
        let data: Data
        let mode: UInt16
        var isDirectory: Bool = false
    }

    static func archive(_ entries: [Entry]) -> Data {
        var out = Data()
        var central = Data()
        for entry in entries {
            let name = Data(entry.path.utf8)
            let crc = crc32(entry.data)
            let size = UInt32(entry.data.count)
            let offset = UInt32(out.count)
            // Local file header.
            out.append(le32: 0x04034b50)
            out.append(le16: 20)          // version needed
            out.append(le16: 0x0800)      // flags: UTF-8 names
            out.append(le16: 0)           // method: stored
            out.append(le16: 0)           // time: 00:00
            out.append(le16: 0x0021)      // date: 1980-01-01
            out.append(le32: crc)
            out.append(le32: size)
            out.append(le32: size)
            out.append(le16: UInt16(name.count))
            out.append(le16: 0)
            out.append(name)
            out.append(entry.data)
            // Central directory record.
            let type: UInt32 = entry.isDirectory ? 0o040000 : 0o100000
            central.append(le32: 0x02014b50)
            central.append(le16: 0x031E)  // made by: Unix, spec 3.0
            central.append(le16: 20)
            central.append(le16: 0x0800)
            central.append(le16: 0)
            central.append(le16: 0)
            central.append(le16: 0x0021)
            central.append(le32: crc)
            central.append(le32: size)
            central.append(le32: size)
            central.append(le16: UInt16(name.count))
            central.append(le16: 0)       // extra
            central.append(le16: 0)       // comment
            central.append(le16: 0)       // disk
            central.append(le16: 0)       // internal attributes
            central.append(le32: (type | UInt32(entry.mode)) << 16 | (entry.isDirectory ? 0x10 : 0))
            central.append(le32: offset)
            central.append(name)
        }
        let centralOffset = UInt32(out.count)
        out.append(central)
        // End of central directory.
        out.append(le32: 0x06054b50)
        out.append(le16: 0)
        out.append(le16: 0)
        out.append(le16: UInt16(entries.count))
        out.append(le16: UInt16(entries.count))
        out.append(le32: UInt32(central.count))
        out.append(le32: centralOffset)
        out.append(le16: 0)
        return out
    }

    private static let table: [UInt32] = (0..<256).map { i in
        var c = UInt32(i)
        for _ in 0..<8 { c = (c & 1) != 0 ? 0xEDB88320 ^ (c >> 1) : c >> 1 }
        return c
    }

    static func crc32(_ data: Data) -> UInt32 {
        var c: UInt32 = 0xFFFFFFFF
        for byte in data { c = table[Int((c ^ UInt32(byte)) & 0xFF)] ^ (c >> 8) }
        return c ^ 0xFFFFFFFF
    }
}

private extension Data {
    mutating func append(le16 value: UInt16) {
        Swift.withUnsafeBytes(of: value.littleEndian) { append(contentsOf: $0) }
    }
    mutating func append(le32 value: UInt32) {
        Swift.withUnsafeBytes(of: value.littleEndian) { append(contentsOf: $0) }
    }
}
