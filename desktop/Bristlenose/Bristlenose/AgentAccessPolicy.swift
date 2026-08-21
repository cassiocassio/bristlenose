import Foundation

/// When can a project's Agent Access be offered at all?
/// (design-mcp-extension §3.6a — the table's two knowable "hide" rows.)
///
/// `canShowInFinder` was the wrong predicate: it is file-presence, so a
/// never-analysed folder passes it with no quotes to read. This one requires
/// locatable AND analysed.
///
/// **"Analysed" means sessions exist, not that a run happened** — corrected 19
/// Aug 2026, when the context menu offered Turn On Agent Access on a project
/// showing `0` sessions and `+57 unanalysed`. Both arms of the old test were
/// satisfied by a project with nothing to serve: `sessionCount != nil` is true
/// whenever the DB is merely *readable*, and zero is a perfectly readable
/// count; `lastPipelineRunAt != nil` is stamped by a run that **failed**, which
/// is exactly how that project got its eleven hours of nothing.
///
/// So the count decides when it is known, and the run stamp is consulted only
/// when it is not — which is the window the second signal existed for (freshly
/// analysed, watcher hasn't ticked yet), rather than a second way to say yes.
/// A known zero is an answer, not a missing one.
///
/// One home for the rule — the context menu (via the ContentView-injected
/// closure), the menu-bar twin, and the Settings register's Access checkbox
/// all call it, so they cannot drift.
///
/// **All three consult it before OFFERING, never inside the mutator.** The
/// register briefly did the other thing: it called `setAgentAccess` directly,
/// which made this comment false for a day (21 Aug 2026, caught in review).
/// The fix was not to move the guard into `ProjectIndex` — `canShare` reads
/// `unanalysed[id]?.sessionCount`, which is nil until the folder watcher's
/// async scan lands, so a guard there would make one call succeed or fail on
/// scan timing and would refuse a legitimate grant on a CLI-analysed project
/// in the seconds after launch. Refusing a real grant is worse than the drift.
/// So: the menus hide or dim the command, the checkbox disables itself, and
/// the mutator stays a mutator.
///
/// Deliberately NOT here: "is an agent installed" — unknowable (we can
/// offer; we cannot observe), and turning access on with no agent is a
/// permission, not an error.
enum AgentAccessPolicy {
    static func canShare(_ project: Project, sessionCount: Int?) -> Bool {
        guard project.availability.isReady else { return false }
        if let sessionCount { return sessionCount > 0 }
        return project.lastPipelineRunAt != nil
    }
}
