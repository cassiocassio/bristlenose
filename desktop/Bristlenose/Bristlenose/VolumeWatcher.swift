import AppKit
import Foundation

/// Observes volume mount/unmount events and triggers project availability refresh.
///
/// Separate from ContentView — a plain observable class that listens to
/// `NSWorkspace` notifications. Owned at the App level alongside ProjectIndex.
@MainActor
final class VolumeWatcher: ObservableObject {

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
                self.projectIndex?.refreshAvailability()
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

    deinit {
        if let mountObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(mountObserver)
        }
        if let unmountObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(unmountObserver)
        }
    }
}
