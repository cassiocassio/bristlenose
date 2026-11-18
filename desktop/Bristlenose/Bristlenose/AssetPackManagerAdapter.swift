#if BA_WHISPER && !DEVELOPER_ID_BETA
import BackgroundAssets
import Foundation
import System

// The only file that touches `AssetPackManager`. Compiled into the store build with
// `BA_WHISPER` set, never into the Developer-ID `.dmg` (which passes DEVELOPER_ID_BETA).
//
// API surface is macOS 26.0's, on purpose: CI builds with an Xcode whose SDK lacks the 26.4
// names (`status(relativeTo:)`, `ensureLocalAvailability(of:requireLatestVersion:)`), and the
// 26.0 calls still work on later systems (deprecated in 26.4 and 27, not removed). Moving to
// the new names is a later, separate change that needs the CI Xcode first.

@available(macOS 26, *)
final class AssetPackManagerAdapter: WhisperPackAdapter, @unchecked Sendable {
    private let manifest: WhisperPackManifest
    private let lock = NSLock()
    private var progress: Progress?

    init(manifest: WhisperPackManifest) { self.manifest = manifest }

    private func setProgress(_ p: Progress?) { lock.lock(); progress = p; lock.unlock() }

    /// One per `ensure` call: set when that call is cancelled, from either the task or `cancelEnsure()`.
    private final class CancelToken: @unchecked Sendable {
        private let lock = NSLock()
        private var flag = false
        var isCancelled: Bool { lock.lock(); defer { lock.unlock() }; return flag }
        func cancel() { lock.lock(); flag = true; lock.unlock() }
    }
    private var token = CancelToken()

    func ensure(report: @escaping @Sendable (Int64, Int64) -> Void) async throws {
        let manager = AssetPackManager.shared
        let mine = CancelToken()
        lock.lock(); token = mine; lock.unlock()
        try Task.checkCancellation()
        // A cancel can arrive at any stage, and the system call may never notice one before its
        // first byte, so every stage checks, and a Progress that shows up after a cancel is
        // cancelled on arrival: otherwise the lookup finishing late would start the fetch after
        // the app has moved on to the Hugging Face fallback.
        try await withTaskCancellationHandler {
            let pack = try await manager.assetPack(withID: manifest.assetPackID)
            try Task.checkCancellation()
            if mine.isCancelled { throw CancellationError() }
            // A new subscription for each ensure: one does not carry on past a failure.
            let updates = manager.statusUpdates(forAssetPackWithID: manifest.assetPackID)
            let watcher = Task { [weak self] in
                for await update in updates {
                    switch update {
                    case .downloading(_, let p):
                        self?.setProgress(p)
                        if mine.isCancelled { p.cancel() }
                        let total = p.totalUnitCount > 0 ? p.totalUnitCount : Int64(pack.downloadSize)
                        report(p.completedUnitCount, total)
                    default:
                        break
                    }
                }
            }
            defer { watcher.cancel(); setProgress(nil) }
            try await manager.ensureLocalAvailability(of: pack)
        } onCancel: { [weak self] in
            mine.cancel()
            self?.cancelEnsure()
        }
    }

    func cancelEnsure() {
        lock.lock(); let current = token; let p = progress; lock.unlock()
        current.cancel()
        p?.cancel()
    }

    func directory() throws -> URL {
        try AssetPackManager.shared.url(for: FilePath(manifest.directory))
    }

    func remove() async throws {
        try await AssetPackManager.shared.remove(assetPackWithID: manifest.assetPackID)
    }
}
#endif
