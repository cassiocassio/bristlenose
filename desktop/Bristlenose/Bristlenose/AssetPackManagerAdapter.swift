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
    private func currentProgress() -> Progress? { lock.lock(); defer { lock.unlock() }; return progress }

    func ensure(report: @escaping @Sendable (Int64, Int64) -> Void) async throws {
        let manager = AssetPackManager.shared
        let pack = try await manager.assetPack(withID: manifest.assetPackID)
        // A new subscription for each ensure: one does not carry on past a failure.
        let updates = manager.statusUpdates(forAssetPackWithID: manifest.assetPackID)
        let watcher = Task { [weak self] in
            for await update in updates {
                switch update {
                case .downloading(_, let p):
                    self?.setProgress(p)
                    let total = p.totalUnitCount > 0 ? p.totalUnitCount : Int64(pack.downloadSize)
                    report(p.completedUnitCount, total)
                default:
                    break
                }
            }
        }
        defer { watcher.cancel(); setProgress(nil) }
        // Task cancellation reaches the system call's Progress when there is one; before the first
        // byte there is none, and the acquirer then does not wait for this call (it asks for the
        // pack to be removed instead, see `BackgroundAssetsAcquirer.ensureWithWatchdog`).
        try await withTaskCancellationHandler {
            try await manager.ensureLocalAvailability(of: pack)
        } onCancel: { [weak self] in
            self?.cancelEnsure()
        }
    }

    func cancelEnsure() { currentProgress()?.cancel() }

    func directory() throws -> URL {
        try AssetPackManager.shared.url(for: FilePath(manifest.directory))
    }

    func remove() async throws {
        try await AssetPackManager.shared.remove(assetPackWithID: manifest.assetPackID)
    }
}
#endif
