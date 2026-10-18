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
    /// **Default off** — parked 17 Oct 2026 until the Bristlenose board plugin
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

    /// Transcribe a first run with **Apple's on-device speech model** while
    /// Whisper downloads behind it (`docs/design-apple-first-transcription.md`).
    /// **Default off** — parked until the language gate is measured on more than
    /// five files. Off, nothing on this path runs: no helper is offered to the
    /// sidecar, no download job starts, and Settings ▸ Transcription keeps its
    /// shipped layout. Mirrors Python's `experimental_apple_speech`.
    ///
    /// Flip with: `defaults write app.bristlenose BristlenoseAppleSpeech -bool YES`
    static let appleSpeechKey = "BristlenoseAppleSpeech"
    static var appleSpeech: Bool {
        UserDefaults.standard.bool(forKey: appleSpeechKey)
    }

    /// The flag **and** the helper in this bundle. While parked the helper is
    /// embedded in Debug builds only, so a `defaults write` on a TestFlight or
    /// `.dmg` build must not offer a choice that does nothing, nor start the
    /// download job for it. Every Swift caller asks this, not `appleSpeech`.
    static var appleSpeechAvailable: Bool {
        appleSpeech && FileManager.default.isExecutableFile(
            atPath: Bundle.main.bundleURL
                .appendingPathComponent("Contents/Helpers/bristlenose-speech").path)
    }
}

/// Settings ▸ Transcription ▸ Transcribe with (plan §4.5). Stored as the raw
/// value; each maps to Python's `apple_speech` setting.
enum TranscriptionEngineChoice: String, CaseIterable {
    /// Apple's model until Whisper is on disk, then Whisper. The default.
    case whisperWhenReady
    /// Never Apple's model.
    case whisperOnly
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
        case .whisperOnly: return "never"
        case .apple: return "prefer"
        }
    }
}
