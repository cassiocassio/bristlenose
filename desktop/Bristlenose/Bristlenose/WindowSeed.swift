import Foundation

/// What a window is opened onto — and, deliberately, how much it deduplicates.
///
/// `WindowGroup(for:)` keys window identity on the **whole value**: presenting a
/// value that is already on screen brings that window forward instead of opening
/// another. That is useful for one command and fatal for the other, and both
/// were measured on 20 Aug 2026 rather than reasoned:
///
/// - `File ▸ New Window` (⌥⌘N) passed the front window's project, and on a study
///   that already had a window it re-activated it. Its whole job is *another view
///   of what I'm looking at*, so deduping made it — and the `WindowRoster`
///   ordinals that exist to number those windows — unreachable.
/// - Passing **no** value did not help: `nil` is itself a unique value, so exactly
///   one no-value window can exist. With `nil` plus one project that is a hard
///   ceiling of two windows, and which two depends on the order you opened them.
///
/// So the value carries its own identity. `fresh` mints a `token` nobody else
/// holds, so the window always opens; `revealing` uses the project as the token,
/// so a second request for the same study reveals the window that already has it.
/// One type, both behaviours, and the difference is named at the call site rather
/// than emerging from SwiftUI.
struct WindowSeed: Codable, Hashable {

    /// Window identity. Distinct from `project` precisely so two windows can show
    /// one study.
    let token: UUID

    /// The study to open on, or nil for "no particular study".
    let project: UUID?

    /// The lens to land on, as `LensMemory`'s remembered spelling. nil falls back
    /// to the study's own last lens — which is what makes *Open in New Window* on
    /// a lens row a single gesture rather than open-then-navigate.
    let lens: String?

    /// Always opens a new window.
    static func fresh(project: UUID? = nil, lens: String? = nil) -> WindowSeed {
        WindowSeed(token: UUID(), project: project, lens: lens)
    }

    /// Opens this study, or reveals the window that already has it.
    ///
    /// The token IS the project, so the value is stable per study and SwiftUI's
    /// dedup does the revealing for free. Deliberate: for *open THIS study*,
    /// surfacing the existing window is the right answer, and it is what a
    /// reveal-or-open command should do.
    static func revealing(project: UUID) -> WindowSeed {
        WindowSeed(token: project, project: project, lens: nil)
    }
}
