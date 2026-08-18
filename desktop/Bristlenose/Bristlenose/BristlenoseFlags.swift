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

    /// Offer **Zoom** in `File ▸ Import`. **Default off** — parked 16 Aug 2026
    /// so Teams and Meet can reach releasable quality first.
    ///
    /// This parks the *menu item only*. The Zoom adapter, its OAuth client, its
    /// transfer policy and its tests all still build and run, and Zoom keeps
    /// its row in the Diagnostics ▸ Cloud Import fixture menu (which reads
    /// `allCases`, deliberately) so its states stay inspectable while parked.
    /// Nothing about ingesting Zoom *files* is affected — that is Python-side
    /// filename and folder-pattern recognition in `s01_ingest.py`, reached by
    /// drag-and-drop, and it never touches this flag.
    ///
    /// Two out-of-tree prerequisites are already done and will keep: the
    /// `associated-domains` entitlement, and the `apple-app-site-association`
    /// file staged in the website repo. What remains is a Zoom Marketplace
    /// client ID and token persistence — see `docs/design-cloud-import.md`,
    /// and the `cloud-import-zoom-parked` brief in the maintainer's private
    /// handoffs, kept outside the public tree.
    ///
    /// Flip with: `defaults write app.bristlenose BristlenoseCloudImportZoom -bool YES`
    static let cloudImportZoomKey = "BristlenoseCloudImportZoom"
    static var cloudImportZoom: Bool {
        UserDefaults.standard.bool(forKey: cloudImportZoomKey)
    }
}
