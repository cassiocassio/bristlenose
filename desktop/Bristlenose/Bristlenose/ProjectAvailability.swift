import Foundation

// MARK: - Availability state

/// Whether a project's on-disk home is reachable, and if not, why.
///
/// Collapses six internal sub-reasons (volume / network / cloud / moved /
/// missing-bookmark / bookmark-stale) down to **three** user-visible buckets
/// per HANDOFF §8+9. Researchers can't tell unmounted from moved at a glance,
/// and the earlier UI tried to make them.
///
/// Each case carries its own copy / icon / primary action so adding a new
/// availability state forces a corresponding UI change at the type level.
enum ProjectAvailability: Equatable {
    /// Path resolves; sidebar shows the regular icon + name.
    case ready
    /// Path doesn't resolve. Reason hints why (for telemetry / copy) but the
    /// UI affordance is the same: a single "Locate…" action.
    case cantFind(reason: CantFindReason)
    /// File lives in iCloud / cloud storage and is currently evicted. Optional
    /// Progress is the active download, if one's in flight.
    case inCloud(downloading: Progress?)
}

/// Why a project can't be found. Internal sub-reasons; collapse to "Can't find
/// this project" in user-facing surfaces. The hint *is* surfaced in the
/// subtitle ("Samsung T7 · missing", "server.local · unreachable") but the
/// primary action is always Locate.
enum CantFindReason: Equatable {
    case unmountedVolume(name: String)
    case networkUnreachable(host: String)
    case moved
    /// Schema-defensive: a v1 record persisted without a bookmark. Same UX as
    /// `.moved` — researcher locates the folder, we capture a fresh bookmark.
    case missingBookmark
}

// MARK: - Primary action

/// The single affordance offered for a given availability state. Selection
/// row / hover surfaces this; menu items map onto it.
enum ProjectAction: Equatable {
    case none
    /// Re-anchor the project to a new folder via Spotlight one-shot or
    /// NSOpenPanel. See HANDOFF §8+9 for the flow.
    case locate
    /// Trigger an iCloud download for an evicted file/folder.
    case downloadFromCloud
}

// MARK: - UI mapping

extension ProjectAvailability {
    /// SF Symbol name to render in the row's leading icon slot. `nil` means
    /// "use the project's normal icon" (the `.ready` case).
    var sfSymbolName: String? {
        switch self {
        case .ready:
            return nil
        case .cantFind(let reason):
            switch reason {
            case .unmountedVolume:
                return "externaldrive.badge.xmark"
            case .networkUnreachable:
                return "network.slash"
            case .moved, .missingBookmark:
                // Same glyph by design — both lead to the Locate flow.
                // `.missingBookmark` is the schema-defensive v1 case; treat
                // identically to `.moved`.
                return "questionmark.folder"
            }
        case .inCloud:
            return "icloud.and.arrow.down"
        }
    }

    /// The single action to offer for this state.
    var primaryAction: ProjectAction {
        switch self {
        case .ready:
            return .none
        case .cantFind:
            return .locate
        case .inCloud:
            return .downloadFromCloud
        }
    }

    /// Factual one-line subtitle for the sidebar row. Returns nil for `.ready`
    /// (no subtitle row — pipeline state owns that line).
    ///
    /// Copy matches HANDOFF §8+9: tight, factual, not imperative. We don't
    /// know where the moved folder went, so we don't pretend to.
    @MainActor
    func subtitle(using i18n: I18n) -> String? {
        switch self {
        case .ready:
            return nil
        case .cantFind(let reason):
            switch reason {
            case .unmountedVolume(let name):
                return i18n.t("desktop.availability.unmountedVolume",
                              ["name": name])
            case .networkUnreachable(let host):
                return i18n.t("desktop.availability.networkUnreachable",
                              ["host": host])
            case .moved, .missingBookmark:
                return i18n.t("desktop.availability.missing")
            }
        case .inCloud:
            return i18n.t("desktop.availability.inCloud")
        }
    }

    /// Whether the project is currently usable (`.ready`). Convenience for
    /// places that don't care about the reason, only the outcome.
    var isReady: Bool {
        if case .ready = self { return true }
        return false
    }
}

// MARK: - Project → ProjectAvailability

extension Project {
    /// Derive availability from the current on-disk + bookmark state.
    /// Pure inspection — no side effects, safe to call from view code.
    ///
    /// Order of checks (location info is more specific than bookmark
    /// presence, so it wins when both apply):
    /// 1. Empty path (new/unsaved project) → `.ready`
    /// 2. File exists at `path` → `.ready`
    /// 3. Location says volume + volume not mounted → `.unmountedVolume`
    /// 4. Location says network + share not mounted → `.networkUnreachable`
    /// 5. Location says cloud → `.inCloud(downloading: nil)`
    /// 6. v1 record with no bookmark and no location verdict →
    ///    `.cantFind(.missingBookmark)`
    /// 7. Otherwise → `.cantFind(.moved)`
    var availability: ProjectAvailability {
        guard !path.isEmpty else { return .ready }
        if FileManager.default.fileExists(atPath: path) { return .ready }

        if let location {
            switch location.type {
            case .volume:
                // We're here because the project's own path didn't exist
                // (checked at line 131). For volume projects, that means the
                // volume isn't usable from our perspective — either it's
                // unmounted, or it's freshly mounted and DiskArbitration
                // hasn't surfaced contents yet. Report `.unmountedVolume`
                // either way; falling through to `.moved` would lose the
                // volume-name context and flicker the subtitle on remount.
                let volumeName = location.volumeName ?? ""
                if volumeName.isEmpty {
                    // Malformed migration: `.volume` location with no name.
                    // Fall through to `.moved` so Locate still works.
                    assertionFailure(".volume location without volumeName")
                    break
                }
                // Trailing slash is load-bearing: it stops "T7" matching a
                // path under "/Volumes/T7 Pro/" when the project actually
                // lives on a sibling volume whose name is a prefix.
                let wasOnThisVolume = lastSeenPath
                    .hasPrefix("/Volumes/\(volumeName)/")
                if wasOnThisVolume || !FileManager.default.fileExists(
                    atPath: "/Volumes/\(volumeName)"
                ) {
                    return .cantFind(reason: .unmountedVolume(
                        name: location.volumeName ?? location.displayHint
                    ))
                }
            case .network:
                let volumePath = "/Volumes/\(location.volumeName ?? "")"
                if !FileManager.default.fileExists(atPath: volumePath) {
                    return .cantFind(reason: .networkUnreachable(
                        host: location.volumeName ?? location.displayHint
                    ))
                }
            case .cloud:
                return .inCloud(downloading: nil)
            case .local:
                break
            }
        }

        if schemaVersion >= 1, bookmarkData == nil {
            return .cantFind(reason: .missingBookmark)
        }

        return .cantFind(reason: .moved)
    }
}
