import Foundation

/// What the MCP Agents pane can honestly say about the extension, given what
/// it actually knows.
///
/// Two versions are in play and they legitimately differ: the `.mcpb` this app
/// **ships**, and the proxy build **running** inside Claude Desktop. A `.mcpb`
/// has no auto-update — reinstall is the only delivery — so an older copy in
/// the field is the normal resting state, not a fault.
///
/// The whole point of this type is that every case is *derived*, never assumed.
/// It is deliberately not a compatibility gate: `MCP_CONTRACT` decides whether
/// a proxy can still be understood (see `routes/health.py`), and nothing here
/// may ever refuse to serve. This reports; it does not judge.
enum MCPExtensionState: Equatable {

    /// No proxy has identified itself, so nothing about an installed copy is
    /// knowable. NOT "up to date" and not "missing" — Bristlenose cannot see
    /// into Claude Desktop, and this is the case where it says so by saying
    /// nothing.
    case unknown

    /// The running proxy reports exactly what we ship.
    case matching

    /// Same release, different content hash. Two packs of one release — the
    /// developer-loop case, and the one that cost six reinstall cycles on
    /// 20 Aug 2026 because nothing surfaced it.
    ///
    /// Deliberately NOT "older": content hashes have no ordering, so which of
    /// the two came first is not derivable. Claiming it would be the app
    /// guessing, in the pane built to stop it guessing.
    case differentBuild(installed: String)

    /// The installed copy's release is genuinely behind ours. Semver orders,
    /// so "older" here is derived rather than assumed.
    case olderRelease(installed: String)

    /// The release halves differ and the installed one is *ahead* — a
    /// downgraded app, or a dev machine that packed, installed, then checked
    /// out an older branch. Rare, but real, and it must not be reported as
    /// "older" just because that is the common direction.
    case newerRelease(installed: String)

    /// Compare what we ship against what called us.
    ///
    /// - Parameters:
    ///   - bundled: the packed stamp, `<release>+<hash>` — or a bare release
    ///     when the sibling stamp file is absent, in which case the hash half
    ///     simply isn't compared.
    ///   - running: the proxy's self-reported stamp, or nil if nothing has
    ///     called through the extension yet.
    static func compare(bundled: String?, running: String?) -> MCPExtensionState {
        guard let bundled, let running, !bundled.isEmpty, !running.isEmpty else {
            return .unknown
        }
        if bundled == running { return .matching }

        let ours = release(of: bundled)
        let theirs = release(of: running)

        if ours == theirs {
            // Same release. If either side lacks a hash we cannot tell these
            // apart at all — treat that as unknown rather than inventing a
            // difference, since a missing stamp file must degrade to silence,
            // not to a false alarm.
            guard hash(of: bundled) != nil, hash(of: running) != nil else {
                return .unknown
            }
            return .differentBuild(installed: display(running))
        }

        switch compareReleases(theirs, ours) {
        case .orderedAscending:  return .olderRelease(installed: display(running))
        case .orderedDescending: return .newerRelease(installed: display(running))
        case .orderedSame:       return .differentBuild(installed: display(running))
        }
    }

    /// The version to show as our own identity, rendered for humans.
    static func identity(bundled: String?) -> String? {
        guard let bundled, !bundled.isEmpty else { return nil }
        return display(bundled)
    }

    // MARK: - Rendering

    /// `0.26.0+854270a` → `0.26.0 (854270a)`.
    ///
    /// Apple's convention for a human version beside an opaque build token,
    /// used in every first-party About panel (`Version 26.3 (17C52)`). The
    /// wire form is semver-build syntax, which reads as a package manifest.
    /// A stamp with no `+` renders unchanged rather than being forced into
    /// parentheses it doesn't have.
    static func display(_ stamp: String) -> String {
        guard let h = hash(of: stamp) else { return stamp }
        return "\(release(of: stamp)) (\(h))"
    }

    static func release(of stamp: String) -> String {
        String(stamp.split(separator: "+", maxSplits: 1).first ?? "")
    }

    static func hash(of stamp: String) -> String? {
        let parts = stamp.split(separator: "+", maxSplits: 1)
        guard parts.count == 2, !parts[1].isEmpty else { return nil }
        return String(parts[1])
    }

    // MARK: - Ordering

    /// Numeric, component-wise — never lexicographic, which puts 0.9.0 above
    /// 0.26.0 and would invert the one claim this type is allowed to make.
    /// A non-numeric component makes the pair incomparable (`.orderedSame`),
    /// which callers render as "different" rather than as a direction.
    static func compareReleases(_ a: String, _ b: String) -> ComparisonResult {
        let lhs = a.split(separator: ".").map { Int($0) }
        let rhs = b.split(separator: ".").map { Int($0) }
        if lhs.contains(where: { $0 == nil }) || rhs.contains(where: { $0 == nil }) {
            return .orderedSame
        }
        for i in 0..<max(lhs.count, rhs.count) {
            let l = i < lhs.count ? (lhs[i] ?? 0) : 0
            let r = i < rhs.count ? (rhs[i] ?? 0) : 0
            if l != r { return l < r ? .orderedAscending : .orderedDescending }
        }
        return .orderedSame
    }
}

extension MCPExtensionState {

    /// The install button's verb. An offer, never a verdict — we can propose
    /// an action on our own file; we cannot pronounce on Claude Desktop's
    /// state. Reinstall/Update differ because the researcher's intent differs:
    /// one replaces a build, the other advances a version.
    var buttonKey: String {
        switch self {
        case .unknown, .matching:            return "desktop.mcpAgents.install"
        case .differentBuild, .newerRelease: return "desktop.mcpAgents.reinstall"
        case .olderRelease:                  return "desktop.mcpAgents.update"
        }
    }

    /// The comparison line, or nil when there is nothing to compare. Absence
    /// is the in-sync signal: a second line appears only when it means
    /// something, and the remedy is the button directly above it.
    var footnoteKey: String? {
        switch self {
        case .unknown, .matching:  return nil
        case .differentBuild:      return "desktop.mcpAgents.installedDifferentBuild"
        case .olderRelease:        return "desktop.mcpAgents.installedOlder"
        case .newerRelease:        return "desktop.mcpAgents.installedNewer"
        }
    }

    /// The version named in that line.
    var installedDisplay: String? {
        switch self {
        case .unknown, .matching:
            return nil
        case let .differentBuild(v), let .olderRelease(v), let .newerRelease(v):
            return v
        }
    }
}
