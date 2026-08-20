import Darwin
import Foundation
import OSLog

/// The MCP handshake file — how an agent-side proxy finds the running serve.
///
/// `ServeManager` writes this whenever a project with Agent Access on reaches
/// `.running`, and deletes it on stop/park/unshare. The `.mcpb` proxy
/// (`desktop/mcpb/server/index.js`) re-reads it on every tool call, probes
/// `/api/health` unauthenticated, compares `instance_id`, and only then opens
/// the authenticated transport. Design: `docs/design-mcp-extension.md` §3.1.
///
/// **Write it the way this codebase writes credentials** — not
/// `Data.write(to:options:.atomic)`, which lands at the umask default
/// (`projects.json` beside it is 0644) and follows symlinks. `open(2)` with
/// `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600` on a uniquely-named temp, then
/// `rename(2)` — mirroring `run_lifecycle.py:_write_pid_file` and
/// `bristlenose/llm/telemetry.py`. `O_NOFOLLOW` is load-bearing: the
/// containing directory is same-user writable, so a pre-planted
/// `mcp-handshake.json → ~/Library/Mobile Documents/…` symlink would
/// otherwise replicate a live bearer to iCloud. (`O_EXCL` fires first when
/// the planted symlink is the temp's name; `O_NOFOLLOW` covers the rest —
/// keep both. Spike-verified 31 Jul 2026, design §5c.)
///
/// Scope caveat: both flags guard the FINAL path component only — a
/// symlinked *parent* (`…/Application Support/Bristlenose → synced dir`)
/// is not detected. Unreachable in the sandboxed shipping build (the
/// container chain is 0700, minted by secinitd); on an unsandboxed dev
/// build the same-user attacker this would stop can already read the
/// study (design §3.1's leading argument). Revisit with O_NOFOLLOW_ANY
/// if a CLI handshake writer ever ships.
///
/// **No path, ever — and `name` is the deliberate exception.** Schema 2 carries
/// the folder basename so a proxy can label a project for the agent; a bare
/// digest is useless in a chooser. That is a narrowing of the original rule,
/// not an accident: the *path* still never appears. `MCPTokenStore.accountKey` hashes the project
/// path precisely so client folder names never become readable metadata;
/// a cleartext path here would undo that for no gain — the proxy doesn't
/// need it, and tool payloads carry the project.
enum MCPHandshake {

    static let filename = "mcp-handshake.json"
    private static let log = Logger(subsystem: "app.bristlenose", category: "mcp")

    /// `…/Application Support/Bristlenose` — the same directory that holds
    /// `projects.json`. Under App Sandbox this resolves inside the container
    /// (the proxy's path 2); on an unsandboxed dev build it resolves to the
    /// real `~/Library/Application Support` (the proxy's path 3). One
    /// expression, both layouts.
    static func defaultDirectory() -> URL? {
        guard let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first else { return nil }
        return appSupport.appendingPathComponent("Bristlenose", isDirectory: true)
    }

    /// Serialize the handshake payload. Pure — unit-testable without touching
    /// the filesystem. Schema 1: `{schema, port, token, instance_id,
    /// updated_at}`. Keyed so a project *set* can arrive in phase 2 without a
    /// schema break (design §3.3a: don't bake "the project" into the shape).
    /// Schema 2: the same file, carrying a project **set**.
    ///
    /// Scope became plural when it stopped being a designated slot and started
    /// being derived from the window roster — several projects can be open with
    /// Agent Access on, and all of them are reachable.
    ///
    /// **The schema-1 keys are still written**, pointing at the first entry.
    /// A `.mcpb` extension installed weeks ago has no upgrade path (design §6
    /// risk 3, "live and unmitigated"), so a v2-only file would silently break
    /// every proxy already in the field. With the fallback, an old proxy keeps
    /// working and simply sees one project — degraded, never broken. An empty
    /// set writes no schema-1 keys at all, which an old proxy reads as "not
    /// open": the correct answer.
    static func payload(entries: [HandshakeExposure.Entry], now: Date = Date()) -> Data {
        let formatter = ISO8601DateFormatter()
        var object: [String: Any] = [
            "schema": 2,
            "updated_at": formatter.string(from: now),
            "projects": entries.map {
                [
                    "key": $0.key,
                    "name": $0.name,
                    "port": $0.port,
                    "token": $0.token,
                    "instance_id": $0.instanceID,
                ]
            },
        ]
        if let first = entries.first {
            object["port"] = first.port
            object["token"] = first.token
            object["instance_id"] = first.instanceID
        }
        return try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    }

    /// Write (atomically, 0600, symlink-refusing) into `directory`.
    /// Returns false — with a log line, never a dialog — when the write path
    /// refuses; a missing handshake degrades to the proxy's "isn't open"
    /// sentence, which is the designed failure surface.
    /// Writes the whole exposed set — see `payload(entries:)`.
    @discardableResult
    static func write(entries: [HandshakeExposure.Entry], directory: URL? = nil) -> Bool {
        guard let dir = directory ?? defaultDirectory() else { return false }
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        } catch {
            log.error("handshake dir create failed: \(error.localizedDescription, privacy: .public)")
            return false
        }

        let data = payload(entries: entries)
        let finalURL = dir.appendingPathComponent(filename)
        var tempURL = dir.appendingPathComponent(".\(filename).tmp-\(UUID().uuidString)")

        let fd = open(tempURL.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o600)
        guard fd >= 0 else {
            log.error("handshake temp open refused: errno=\(errno, privacy: .public)")
            return false
        }
        var writeErrno: Int32 = 0
        var ok = data.withUnsafeBytes { (raw: UnsafeRawBufferPointer) -> Bool in
            var written = 0
            while written < raw.count {
                let n = Darwin.write(fd, raw.baseAddress!.advanced(by: written), raw.count - written)
                if n <= 0 {
                    writeErrno = errno
                    return false
                }
                written += n
            }
            return true
        }
        if close(fd) != 0 {
            if ok { writeErrno = errno }
            ok = false
        }

        // Runtime artefact with no restore value — keep it out of Time
        // Machine. Set on the temp; the xattr travels through the rename.
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try? tempURL.setResourceValues(values)

        guard ok else {
            unlink(tempURL.path)
            log.error("handshake write failed: errno=\(writeErrno, privacy: .public)")
            return false
        }
        guard rename(tempURL.path, finalURL.path) == 0 else {
            // Capture BEFORE the unlink — its errno would clobber rename's
            // and the log would diagnose the wrong failure.
            let renameErrno = errno
            unlink(tempURL.path)
            log.error("handshake rename failed: errno=\(renameErrno, privacy: .public)")
            return false
        }
        log.info("handshake written projects=\(entries.count, privacy: .public)")
        return true
    }

    /// Delete the handshake if present. Idempotent, silent on absence.
    static func remove(directory: URL? = nil) {
        guard let dir = directory ?? defaultDirectory() else { return }
        let url = dir.appendingPathComponent(filename)
        if unlink(url.path) != 0 && errno != ENOENT {
            log.error("handshake remove failed: errno=\(errno, privacy: .public)")
        }
    }
}
