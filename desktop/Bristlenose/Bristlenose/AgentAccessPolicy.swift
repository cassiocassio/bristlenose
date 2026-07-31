import Foundation

/// When can a project's Agent Access be offered at all?
/// (design-mcp-extension §3.6a — the table's two knowable "hide" rows.)
///
/// `canShowInFinder` was the wrong predicate: it is file-presence, so a
/// never-analysed folder passes it with no quotes to read. This one requires
/// locatable AND analysed. "Analysed" is either signal the host has:
/// - the watcher read a session count from the project DB (works for
///   projects analysed before `lastPipelineRunAt` existed), or
/// - a pipeline run completed this install (`lastPipelineRunAt`), which
///   covers the freshly-analysed window before the watcher's next tick.
///
/// One home for the rule — the context menu (via the ContentView-injected
/// closure), the menu-bar twin, and the Settings agent-access list all call
/// it, so they cannot drift.
///
/// Deliberately NOT here: "is an agent installed" — unknowable (we can
/// offer; we cannot observe), and turning access on with no agent is a
/// permission, not an error.
enum AgentAccessPolicy {
    static func canShare(_ project: Project, sessionCount: Int?) -> Bool {
        project.availability.isReady
            && (sessionCount != nil || project.lastPipelineRunAt != nil)
    }
}
