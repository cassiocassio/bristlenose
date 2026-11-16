import CryptoKit
import Foundation

// What the app trusts about a Whisper pack the system delivered
// (docs/private/background-assets-whisper-plan-2026-11.md §4, "Integrity").
//
// Apple hosts and delivers the pack; the app still checks what it is about to hand to the
// sidecar, because the sidecar loads these bytes as tensors and runs with
// disable-library-validation. The manifest is pinned here, from `build-whisper-pack.sh`'s
// `pack-manifest.json`. Pure, so it is tested with small fixtures and a different manifest.

struct WhisperPackManifest: Equatable, Sendable {
    struct File: Equatable, Sendable {
        let name: String
        let bytes: Int64
        let sha256: String
    }

    let assetPackID: String
    /// The directory inside the pack, and the name Python expects under the model-dir variable.
    let directory: String
    let files: [File]

    /// The one model the store build ships: mlx-community/whisper-large-v3-turbo at revision
    /// a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb, packaged 16 Nov 2026. Re-pin from the real
    /// build's `pack-manifest.json` before any upload; a different model is a different manifest.
    static let largeV3Turbo = WhisperPackManifest(
        assetPackID: "whisper-large-v3-turbo",
        directory: "large-v3-turbo",
        files: [
            File(name: "config.json", bytes: 268,
                 sha256: "b34fc29e4e11e0a25e812775dd67f4dd16fc2c8eb43d28ae25ff7d660ecb6379"),
            File(name: "weights.safetensors", bytes: 1_613_977_612,
                 sha256: "951ed3fc1203e6a62467abb2144a96ce7eafca8fa77e3704fdb8635ff3e7f8a6"),
        ])
}

enum WhisperPackVerdict: Equatable {
    case ok
    case missing(String)
    case wrongSize(String)
    /// A file the allowlist does not name (a second copy of the weights, a script).
    case unexpected(String)
    case wrongHash(String)
}

enum WhisperPackVerifier {

    /// Names and sizes only: cheap enough to ask before every run. A pack that passed `verify`
    /// when it arrived and still has the right names and sizes is taken as intact.
    static func quickCheck(directory: URL, manifest: WhisperPackManifest) -> WhisperPackVerdict {
        let fm = FileManager.default
        guard let listed = try? fm.contentsOfDirectory(atPath: directory.path) else {
            return .missing(manifest.directory)
        }
        let allowed = Set(manifest.files.map(\.name))
        // Dot files are the file system's, not the pack's.
        if let extra = listed.filter({ !$0.hasPrefix(".") }).sorted().first(where: { !allowed.contains($0) }) {
            return .unexpected(extra)
        }
        for file in manifest.files {
            let path = directory.appendingPathComponent(file.name).path
            guard let attrs = try? fm.attributesOfItem(atPath: path),
                  (attrs[.type] as? FileAttributeType) == .typeRegular else {
                return .missing(file.name)
            }
            guard (attrs[.size] as? NSNumber)?.int64Value == file.bytes else { return .wrongSize(file.name) }
        }
        return .ok
    }

    /// Names, sizes and SHA-256 of every file. Blocking (a few seconds for 1.6 GB): call it off
    /// the main thread.
    static func verify(directory: URL, manifest: WhisperPackManifest) -> WhisperPackVerdict {
        let quick = quickCheck(directory: directory, manifest: manifest)
        guard quick == .ok else { return quick }
        for file in manifest.files {
            guard let digest = sha256(of: directory.appendingPathComponent(file.name)) else {
                return .missing(file.name)
            }
            if digest != file.sha256 { return .wrongHash(file.name) }
        }
        return .ok
    }

    static func sha256(of url: URL) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            // `read(upToCount:)` returns nil at the end of the file and throws on a real error.
            do {
                guard let chunk = try handle.read(upToCount: 1 << 20), !chunk.isEmpty else { break }
                hasher.update(data: chunk)
            } catch {
                return nil
            }
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}
