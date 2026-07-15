import Foundation
import OSLog

/// Time-boxes the Developer-ID `.dmg` "alpha sampler" builds (lifecycle stage
/// 2.5). These are a deliberately-disposable, low-friction preview handed out
/// via a public download link (a Substack / LinkedIn post) for people who bounce
/// off TestFlight — NOT a real distribution channel and NOT auto-updating. They
/// stop working `validityDays` after the build date so no build lingers as a
/// support liability. The funnel past expiry is the App Store (the commercial
/// channel, with its own trial) or Homebrew (for CLI users).
///
/// **Anchored on the build date, not first launch.** `GeneratedBuildInfo.buildDate`
/// is already baked and code-signed into the binary — editing it breaks the
/// signature — so the expiry is tamper-resistant, predictable (every alpha dies
/// 30 days after it's cut), and self-limiting. Refresh the public download by
/// re-cutting a build. Deliberately NOT hardened against clock-rollback: this is
/// a courtesy funnel, not DRM.
///
/// **Scoped to `.developerID` only.** Debug, App Store, and TestFlight builds
/// never expire (`expiryDate == nil`), so the guards below can be called
/// unconditionally from shared code paths.
enum AlphaBuild {
    /// Days a Developer-ID alpha build stays usable after its build date.
    static let validityDays = 30

    /// Where an expired build sends the user.
    static let landingURL = URL(string: "https://bristlenose.app/")!

    // MARK: Pure core (unit-tested — takes its inputs, reads no globals)

    /// The instant a build cut on `built` stops working.
    static func expiry(forBuildDate built: Date, validityDays: Int = validityDays) -> Date {
        Calendar.current.date(byAdding: .day, value: validityDays, to: built) ?? built
    }

    /// Whether a build cut on `built` is expired as of `now`.
    static func isExpired(buildDate built: Date, asOf now: Date,
                          validityDays: Int = validityDays) -> Bool {
        now >= expiry(forBuildDate: built, validityDays: validityDays)
    }

    /// Whole days from `now` until a `built` build expires (negative once past).
    static func daysRemaining(buildDate built: Date, asOf now: Date,
                              validityDays: Int = validityDays) -> Int {
        Calendar.current.dateComponents(
            [.day], from: now, to: expiry(forBuildDate: built, validityDays: validityDays)
        ).day ?? 0
    }

    // MARK: Channel-aware wrappers (read the signed-in build facts)

    /// True only for the Developer-ID `.dmg` sampler channel.
    static var isAlphaChannel: Bool {
        switch DistributionChannel.current {
        case .developerID: return true
        case .debug, .appStoreOrTestFlight: return false
        }
    }

    /// Build date parsed from the code-signed constant, or nil if unreadable.
    static var buildDate: Date? {
        ISO8601DateFormatter().date(from: GeneratedBuildInfo.buildDate)
    }

    #if DEBUG
    /// DEBUG-only preview override — the alpha UI is otherwise invisible in a
    /// normal Cmd+R build (wrong channel). Set `BRISTLENOSE_DEBUG_ALPHA_DAYS` in
    /// the Run scheme's environment to force it visible:
    ///   `5` (0…7)  → pretend N days remain → the `.status` pill shows "Alpha · Nd"
    ///   `0`        → "Alpha · today" (amber)
    ///   `10`       → outside the final week → pill stays hidden (silent state)
    ///   `-1`       → pretend expired → the expiry flow's alert presents, then quit
    /// Unset → normal behaviour. Keep the scheme row `isEnabled = "NO"` if committed.
    static var debugDaysOverride: Int? {
        guard let raw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEBUG_ALPHA_DAYS"],
              let n = Int(raw) else { return nil }
        return n
    }
    #endif

    /// When this build stops working — nil on every non-alpha channel (they
    /// never expire) and nil if the build date can't be parsed.
    static var expiryDate: Date? {
        #if DEBUG
        if let o = debugDaysOverride, o >= 0 {
            return Calendar.current.date(byAdding: .day, value: o, to: Date())
        }
        #endif
        guard isAlphaChannel, let built = buildDate else { return nil }
        return expiry(forBuildDate: built)
    }

    /// Whole days until this build expires, or nil when it never will.
    static func daysRemaining(asOf now: Date = Date()) -> Int? {
        #if DEBUG
        if let o = debugDaysOverride { return o >= 0 ? o : nil }
        #endif
        guard let built = buildDate, isAlphaChannel else { return nil }
        return daysRemaining(buildDate: built, asOf: now)
    }

    /// True once an alpha build is past its expiry. Always false off the alpha
    /// channel, so it's safe to call unconditionally at any startup seam.
    static func isExpired(asOf now: Date = Date()) -> Bool {
        #if DEBUG
        if let o = debugDaysOverride { return o < 0 }
        #endif
        guard let built = buildDate, isAlphaChannel else { return false }
        return isExpired(buildDate: built, asOf: now)
    }
}
