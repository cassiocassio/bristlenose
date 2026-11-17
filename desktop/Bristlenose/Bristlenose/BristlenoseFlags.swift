import Foundation

/// In-progress feature flags, read from `UserDefaults` so they can be flipped
/// without a rebuild: `defaults write app.bristlenose <key> -bool YES`.
enum BristlenoseFlags {
    /// Render the native AppKit `NSOutlineView` source-list sidebar instead of the
    /// SwiftUI `List`. **Default off** (SwiftUI is the shipping sidebar). The AppKit
    /// sidebar is the in-progress framework migration — see
    /// `docs/design-desktop-sidebar-appkit.md`. Flip with:
    /// `defaults write app.bristlenose BristlenoseAppKitSidebar -bool YES`
    static var appKitSidebar: Bool {
        UserDefaults.standard.bool(forKey: "BristlenoseAppKitSidebar")
    }

    /// Welcome-screen cell-tint working candidate (open decision #3,
    /// `docs/design-welcome-screen.md` §2): Whisper reversed — accent 11→2 %,
    /// colour on the stage, quiet eye — over a radial pane glow, with glassy
    /// cells that pick the glow up. Tuned in
    /// `docs/mockups/welcome-gradient-playground.html` (its defaults are these
    /// values). **Default off** — v1's 3→26 % ramp ships. The welcome views
    /// read this key via `@AppStorage`, so a flip re-renders live. Flip with:
    /// `defaults write app.bristlenose BristlenoseWelcomeTintCandidate -bool YES`
    /// or per-run in Xcode: Edit Scheme ▸ Run ▸ Arguments Passed On Launch →
    /// `-BristlenoseWelcomeTintCandidate YES`.
    static let welcomeTintCandidateKey = "BristlenoseWelcomeTintCandidate"
    static var welcomeTintCandidate: Bool {
        UserDefaults.standard.bool(forKey: welcomeTintCandidateKey)
    }

    /// Offer **Zoom** in `File ▸ Import` regardless of the Diagnostics menu.
    /// Parked 16 Aug 2026 so Teams and Meet could reach releasable quality
    /// first; since 17 Oct 2026 Zoom is a Diagnostics beta, shown whenever the
    /// Diagnostics menu is on (`CloudPlatform.zoomOffered`), and this is the
    /// override.
    ///
    /// This parks the *menu item only*. The Zoom adapter, its OAuth client, its
    /// transfer policy and its tests all still build and run, and Zoom keeps
    /// its row in the Diagnostics ▸ Cloud Import fixture menu (which reads
    /// `allCases`, deliberately) so its states stay inspectable while parked.
    /// Nothing about ingesting Zoom *files* is affected — that is Python-side
    /// filename and folder-pattern recognition in `s01_ingest.py`, reached by
    /// drag-and-drop, and it never touches this flag.
    ///
    /// Registration, the `webcredentials` entitlement (store and Debug), the
    /// deployed `apple-app-site-association` file and token persistence are
    /// all done, and a first live sign-in worked on 17 Oct 2026. What remains
    /// is Zoom's Marketplace review, after which a Production client ID ships
    /// in the bundle and this flag can go — see
    /// `docs/design-cloud-import-transcripts.md` §1b.
    ///
    /// Flip with: `defaults write app.bristlenose BristlenoseCloudImportZoom -bool YES`
    static let cloudImportZoomKey = "BristlenoseCloudImportZoom"
    static var cloudImportZoom: Bool {
        UserDefaults.standard.bool(forKey: cloudImportZoomKey)
    }

    /// Offer **Send to FigJam…** in the Quotes menu and the export popover.
    /// **Default off** — parked 17 Oct 2026 until the Bristlenose plugin
    /// is published in Figma Community: a row whose last step is "run a plugin
    /// you can't install" is a dead affordance. The sheet (`FigJamSheet`) and
    /// the download route it calls build and run regardless; this hides the
    /// entry points only. The SPA's twin is `featureFlags.figjamExport`.
    ///
    /// Flip with: `defaults write app.bristlenose BristlenoseFigJamExport -bool YES`
    static let figjamExportKey = "BristlenoseFigJamExport"
    static var figjamExport: Bool {
        UserDefaults.standard.bool(forKey: figjamExportKey)
    }

    /// Offer **Link quotes to clips** in both board sheets (Miro and FigJam).
    /// **Default off** — parked 19 Oct 2026: every link was dead. The board guesses
    /// a clip's file name and the clip exporter writes another, and matching the
    /// real one would put the participant's name on a shared board
    /// (`docs/design-miro-bridge.md` § Enhancement: clip links in stickies). The
    /// sheets send no clip folder while it is off; the route and its tests stay.
    /// The SPA's twin is `featureFlags.boardClipLinks`.
    ///
    /// Flip with: `defaults write app.bristlenose BristlenoseBoardClipLinks -bool YES`
    static let boardClipLinksKey = "BristlenoseBoardClipLinks"
    static var boardClipLinks: Bool {
        UserDefaults.standard.bool(forKey: boardClipLinksKey)
    }

    /// Offer **View ▸ Show / Hide Quote Edits**. **Default off** — parked 6 Nov
    /// 2026: step 1 is the menu item and its state only, and nothing in the
    /// transcript draws the view yet (it needs a per-word used/cut record the
    /// server does not send), so a shipped row would be live but inert. The SPA's
    /// store (`QuoteEditsStore`) and the bridge state build and run regardless;
    /// this hides the entry point only. `docs/design-quote-edits-view.md`.
    ///
    /// Flip with: `defaults write app.bristlenose BristlenoseQuoteEdits -bool YES`
    static let quoteEditsKey = "BristlenoseQuoteEdits"
    static var quoteEdits: Bool {
        UserDefaults.standard.bool(forKey: quoteEditsKey)
    }

    /// Transcribe a first run with **Apple's on-device speech model** while
    /// Whisper downloads behind it (`docs/design-apple-first-transcription.md`).
    /// **On by default since 22 Oct 2026** (owner: unpark now). This is the
    /// kill switch, kept for a tester who hits trouble: off, no helper is
    /// offered to the sidecar and Settings ▸ Transcription keeps its old
    /// layout. Mirrors Python's `experimental_apple_speech` (default on too).
    ///
    /// Turn off with: `defaults write app.bristlenose BristlenoseAppleSpeech -bool NO`
    static let appleSpeechKey = "BristlenoseAppleSpeech"
    static var appleSpeech: Bool { appleSpeech(in: .standard) }

    /// On unless written off: a missing key is the graduated default.
    static func appleSpeech(in defaults: UserDefaults) -> Bool {
        defaults.object(forKey: appleSpeechKey) as? Bool ?? true
    }

    /// Deliver the Whisper model by **Apple Background Assets** in the store build on macOS 26+
    /// (the Background Assets plan). On unless written off: the
    /// kill switch for a tester who hits trouble, and a guard on `AssetPackManager.shared`,
    /// which is never touched when this is off. Only means something in a build compiled with
    /// `BA_WHISPER`; the Developer-ID `.dmg` never has it.
    ///
    /// Turn off with the app QUIT, writing the container's plist by path (the sandboxed app reads
    /// `~/Library/Containers/app.bristlenose/Data/Library/Preferences/app.bristlenose.plist`):
    /// `defaults write ~/Library/Containers/app.bristlenose/Data/Library/Preferences/app.bristlenose BristlenoseBackgroundAssets -bool NO`.
    /// The by-name form `defaults write app.bristlenose …` fails on a TestFlight build ("Could not
    /// write domain"), and on macOS 27 the container itself may refuse Terminal until Terminal has
    /// Full Disk Access or App Management. UNTESTED on a signed build (17 Nov 2026).
    static let backgroundAssetsKey = "BristlenoseBackgroundAssets"
    static var backgroundAssets: Bool { backgroundAssets(in: .standard) }

    static func backgroundAssets(in defaults: UserDefaults) -> Bool {
        defaults.object(forKey: backgroundAssetsKey) as? Bool ?? true
    }

    /// The switch **and** the helper in this bundle: CI stubs the sidecar and a
    /// Dev Sidecar build may lack it, so nothing offers a choice that does
    /// nothing. Every Swift caller asks this, not `appleSpeech`.
    static var appleSpeechAvailable: Bool {
        appleSpeech && FileManager.default.isExecutableFile(
            atPath: Bundle.main.bundleURL
                .appendingPathComponent("Contents/Helpers/bristlenose-speech").path)
    }
}

/// Settings ▸ Transcription ▸ Transcription engine (plan §4.5). Stored as the
/// raw value; each maps to Python's `apple_speech` setting.
///
/// There was a third, *Whisper only* (never Apple's model). It was removed on
/// 12 Nov 2026: with it, a Whisper that failed to download meant no
/// transcription at all when Apple's model was a viable stand-in. A stored
/// `whisperOnly` from an older build reads as the default (`current`), and the
/// pane's selection binding does the same, so nothing renders blank.
enum TranscriptionEngineChoice: String, CaseIterable {
    /// Apple's model until Whisper is on disk, then Whisper. The default. The
    /// pop-up calls it just "Whisper".
    case whisperWhenReady
    /// Apple's model in its languages, Whisper for the rest.
    case apple

    static let key = "transcriptionEngine"

    static func current(_ defaults: UserDefaults = .standard) -> TranscriptionEngineChoice {
        defaults.string(forKey: key).flatMap(Self.init(rawValue:)) ?? .whisperWhenReady
    }

    /// `BRISTLENOSE_APPLE_SPEECH`'s value.
    var pythonMode: String {
        switch self {
        case .whisperWhenReady: return "until-whisper"
        case .apple: return "prefer"
        }
    }
}

// MARK: - News and anonymous counts (Swift-only preferences)

/// The two switches (spec §7), in the style of `BristlenoseFlags`. Both can be
/// forced **off** by a managed preference (an MDM configuration profile for
/// `app.bristlenose`); a forced value never turns anything *on*.
///
/// - `news.enabled` (Bool, default **on**): "Check bristlenose.app for news".
///   Off: no request of any kind, and the cached file is deleted.
///   Managed: `<key>news.enabled</key><false/>`.
/// - `news.counts` (Bool, **absent = not answered**): "Send anonymous daily
///   counts", chosen explicitly on first run. Counts ride along only on an
///   explicit `true` that the person set; absent or `false` sends the bare
///   request. Managed: `<key>news.counts</key><false/>`. A managed `true` is
///   not the person's yes, so it sends nothing either.
///
/// Neither posts `.bristlenosePrefsChanged`: the serve never reads them.
enum NewsPreferences {
    static let enabledKey = "news.enabled"
    static let countsKey = "news.counts"

    /// On unless written off. A managed value is what `UserDefaults` returns
    /// (the forced domain wins the search), so a profile's `false` is read
    /// here as off and cannot be switched back on.
    ///
    /// A profile's `true` is not a lock: a forced value never turns anything
    /// on, so the switch stays the person's. `UserDefaults` would answer the
    /// forced `true` whatever they chose, so their own choice is read from
    /// their own domain (`ownValue`, default `ownStoredValue`).
    static func newsEnabled(in defaults: UserDefaults, isForced: (String) -> Bool,
                            ownValue: (String) -> Any? = ownStoredValue) -> Bool {
        if isForcedOff(enabledKey, in: defaults, isForced: isForced) { return false }
        if isForced(enabledKey) { return ownValue(enabledKey) as? Bool ?? true }
        return defaults.object(forKey: enabledKey) as? Bool ?? true
    }

    /// Forced, and to anything but `true`: the only managed state that locks.
    static func isForcedOff(_ key: String, in defaults: UserDefaults,
                            isForced: (String) -> Bool) -> Bool {
        isForced(key) && (defaults.object(forKey: key) as? Bool) != true
    }

    /// The person's own value for `key` in this app's user domain, which a
    /// configuration profile's managed domain does not touch.
    static func ownStoredValue(_ key: String) -> Any? {
        CFPreferencesCopyValue(key as CFString, kCFPreferencesCurrentApplication,
                               kCFPreferencesCurrentUser, kCFPreferencesAnyHost)
    }

    static func countsConsent(in defaults: UserDefaults,
                              isForced: (String) -> Bool) -> NewsCheck.CountsConsent {
        if isForced(countsKey) { return .no }
        switch defaults.object(forKey: countsKey) as? Bool {
        case true?: return .yes
        case false?: return .no
        case nil: return .unanswered
        }
    }

    /// The first-run answer (the counts checkbox on the AI disclosure), and the
    /// Settings switch. An explicit `true` or `false` is written either way,
    /// so "answered no" is told apart from "never asked". Nothing is written
    /// while a profile manages the key.
    static func recordCountsAnswer(_ yes: Bool, in defaults: UserDefaults,
                                   isForced: (String) -> Bool) {
        guard !isForced(countsKey) else { return }
        defaults.set(yes, forKey: countsKey)
    }

    /// What the first-run checkbox starts at: **off**, unless this person
    /// already said yes (in Settings, or on an earlier showing).
    static func countsChoiceStartsOn(in defaults: UserDefaults,
                                     isForced: (String) -> Bool) -> Bool {
        countsConsent(in: defaults, isForced: isForced) == .yes
    }

    /// One Settings row: what the switch shows, and whether a profile locks it
    /// ("Managed by your organisation"). A locked row shows the value that is
    /// in force, which for counts is never on: a managed yes is not a yes.
    struct Row: Equatable {
        var isOn: Bool
        var isLocked: Bool
        /// The counts row only: news is off, so no request is made and the
        /// counts switch has nothing to act on. Shown dimmed, keeping the
        /// person's own answer for when news comes back on.
        var waitsForNews: Bool = false
    }

    static func newsRow(in defaults: UserDefaults, isForced: (String) -> Bool,
                        ownValue: (String) -> Any? = ownStoredValue) -> Row {
        Row(isOn: newsEnabled(in: defaults, isForced: isForced, ownValue: ownValue),
            isLocked: isForcedOff(enabledKey, in: defaults, isForced: isForced))
    }

    static func countsRow(in defaults: UserDefaults, isForced: (String) -> Bool,
                          newsOn: Bool = true) -> Row {
        Row(isOn: countsConsent(in: defaults, isForced: isForced) == .yes,
            isLocked: isForced(countsKey),
            waitsForNews: !newsOn)
    }

    /// Where both rows and the first-run line send someone who wants the detail.
    static let privacyURL = URL(string: "https://bristlenose.app/privacy.html")!

    /// `CFPreferencesAppValueIsForced`: true when a configuration profile
    /// manages the key, whatever value it set.
    static func isManaged(_ key: String) -> Bool {
        CFPreferencesAppValueIsForced(key as CFString, kCFPreferencesCurrentApplication)
    }
}
