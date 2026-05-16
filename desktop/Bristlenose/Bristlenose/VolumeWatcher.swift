import AppKit
import Foundation
import os.log

/// Observes volume mount/unmount events and triggers project availability refresh.
///
/// Separate from ContentView — a plain observable class that listens to
/// `NSWorkspace` notifications. Owned at the App level alongside ProjectIndex.
@MainActor
final class VolumeWatcher: ObservableObject {

    /// Backoff ladder for `runRemountLadder`. First rung at 500ms — rung 0
    /// would fire inside the DiskArbitration settling window the ladder
    /// exists to dodge. Cap at 3s; slower volumes (USB hubs, encrypted
    /// disks) surface in the `settled at rung …` log line if it recurs.
    private static let remountLadderMs: [UInt64] = [500, 1_500, 3_000]

    private static let log = Logger(subsystem: "app.bristlenose", category: "volume-watcher")

    private var mountObserver: NSObjectProtocol?
    private var unmountObserver: NSObjectProtocol?

    /// The ProjectIndex to refresh on mount/unmount. Set after init.
    weak var projectIndex: ProjectIndex?

    init() {
        let center = NSWorkspace.shared.notificationCenter

        mountObserver = center.addObserver(
            forName: NSWorkspace.didMountNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor in
                guard let self else { return }
                let volumeName = (notification.userInfo?[NSWorkspace.volumeURLUserInfoKey] as? URL)?
                    .lastPathComponent
                print("[VolumeWatcher] Volume mounted: \(volumeName ?? "unknown")")
                self.runRemountLadder(volumeName: volumeName)
            }
        }

        unmountObserver = center.addObserver(
            forName: NSWorkspace.didUnmountNotification,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            Task { @MainActor in
                guard let self else { return }
                let volumeName = (notification.userInfo?[NSWorkspace.volumeURLUserInfoKey] as? URL)?
                    .lastPathComponent
                print("[VolumeWatcher] Volume unmounted: \(volumeName ?? "unknown")")
                self.projectIndex?.refreshAvailability()
            }
        }
    }

    /// `NSWorkspace.didMountNotification` fires when a volume is mounted, but
    /// DiskArbitration may not have surfaced contents yet — a synchronous
    /// `refreshAvailability()` at that instant sees the mount-point but
    /// `fileExists(atPath: <project path>)` race-fails, so `resolveBookmark`
    /// returns nil and the project's reason regresses from `.unmountedVolume`
    /// to `.moved`. Schedule a small ladder of retries; stop as soon as no
    /// project still claims this volume name.
    private func runRemountLadder(volumeName: String?) {
        Task { @MainActor [weak self] in
            for (index, delayMs) in Self.remountLadderMs.enumerated() {
                try? await Task.sleep(nanoseconds: delayMs * 1_000_000)
                guard let self, let projectIndex = self.projectIndex else { return }
                projectIndex.refreshAvailability()
                guard let name = volumeName else { continue }
                let stillWaiting = projectIndex.projects.contains { project in
                    if case .cantFind(let reason) = project.availability,
                       case .unmountedVolume(let n) = reason,
                       n == name {
                        return true
                    }
                    return false
                }
                if !stillWaiting {
                    Self.log.info(
                        "settled at rung \(index, privacy: .public) (\(delayMs, privacy: .public)ms)"
                    )
                    return
                }
            }
        }
    }

    deinit {
        if let mountObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(mountObserver)
        }
        if let unmountObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(unmountObserver)
        }
    }
}
