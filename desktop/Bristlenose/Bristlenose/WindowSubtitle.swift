import SwiftUI

// MARK: - Composition rules

/// Pure composition of the main window's `NSWindow.subtitle` — the parenthesised
/// half of the Window-menu entry (`IKEA Study (163 Quotes)`) and the second line
/// of the titlebar.
///
/// These live outside `ContentView` because each is a *decision*, and a decision
/// a view makes is a decision nobody can test (`desktop/CLAUDE.md` § Testing).
/// The options weighed and the cases rejected are drawn in
/// `docs/mockups/window-menu-naming.html`.
enum WindowSubtitle {

    /// Interpunct — the separator the sessions subtitle, the sidebar row and
    /// Mail's own viewer titles all use. Named once here so the folder, the run
    /// state and the count can't drift onto different separators.
    static let separator = " · "

    /// The project's folder name, but **only** when another project in the index
    /// carries the same name (mockup E5).
    ///
    /// Keyed off the *index*, deliberately not off which windows are open: a
    /// project's subtitle must not change shape because the researcher opened a
    /// window somewhere else. That would make the rule unlearnable — the same
    /// project would be titled two different ways at two moments, for reasons
    /// invisible from the window itself.
    ///
    /// The comparison is case-insensitive because the failure being solved is
    /// visual: "Pilot" and "pilot" are as ambiguous in a menu as two exact
    /// matches.
    ///
    /// Returns nil for a project sitting at the sidebar root — there is no
    /// folder to name, so that row stays ambiguous. Honest, and better than
    /// inventing a label for "no folder" that would read as a real one.
    static func folderDisambiguator(for project: Project,
                                    projects: [Project],
                                    folders: [Folder]) -> String? {
        guard let folderID = project.folderId else { return nil }
        let sharingName = projects.filter {
            $0.name.compare(project.name, options: .caseInsensitive) == .orderedSame
        }
        guard sharingName.count > 1 else { return nil }
        guard let name = folders.first(where: { $0.id == folderID })?.name,
              !name.trimmingCharacters(in: .whitespaces).isEmpty
        else { return nil }
        return name
    }

    /// Joins the optional folder onto the body (the count, or the live run
    /// state). Either half may be absent: a project with no analysis and no
    /// name clash yields `""`, which AppKit renders as a bare title rather than
    /// as empty parentheses.
    static func compose(folder: String?, body: String) -> String {
        [folder, body]
            .compactMap { $0 }
            .filter { !$0.isEmpty }
            .joined(separator: separator)
    }
}

// MARK: - Application

/// Applies `.navigationSubtitle`, observing the live run data itself.
///
/// `PipelineLiveData` is a nested `ObservableObject` hanging off
/// `PipelineRunner` ([PipelineRunner.swift](PipelineRunner.swift) `let liveData`).
/// A change to `progress` republishes *it*, not the runner — so `ContentView`'s
/// `@EnvironmentObject pipelineRunner` never sees the per-second tick, and a
/// titlebar composed up there would freeze on whichever stage happened to be
/// current at the last unrelated redraw. The observation has to live at the
/// point of use, which is what this modifier is for. (`ProjectRow` solves the
/// same problem the same way, with its own `@ObservedObject liveData`.)
struct WindowSubtitleModifier: ViewModifier {
    @ObservedObject var liveData: PipelineLiveData

    /// The selected project, or nil on the welcome screen.
    let projectID: UUID?
    /// `pipelineRunner.state[id] == .running`. Read by the caller because
    /// `state` is low-frequency and `ContentView` already observes the runner;
    /// only the churn belongs to `liveData`.
    let isRunning: Bool
    /// Result of `WindowSubtitle.folderDisambiguator`, nil in the normal case.
    let folder: String?
    /// The resting body — the lens count, when no run is in flight.
    let countSubtitle: String
    let i18n: I18n

    func body(content: Content) -> some View {
        content.navigationSubtitle(WindowSubtitle.compose(folder: folder, body: bodyText))
    }

    /// A run in flight outranks the count (mockup E7).
    ///
    /// Scoped to the two *live* states — stopping and running. A run narrates
    /// itself while it is happening and then stops, which is what earns it a
    /// place in chrome the researcher can't dismiss. Terminal conditions
    /// (stopped, failed, partial) deliberately stay on the sidebar row, where
    /// status lives with its subject: a titlebar reading "(Stopped)" would sit
    /// there indefinitely, and that is a different decision from this one.
    private var bodyText: String {
        guard let projectID else { return countSubtitle }
        let progress = liveData.progress[projectID]
        // Stopping outranks progress — the same immediate-ack contract the pill
        // and the sidebar row honour, so all three flip together on the click.
        if progress?.isStopping == true {
            return i18n.t("desktop.chrome.pipeline.stopping")
        }
        guard isRunning else { return countSubtitle }
        return RunProgressSubtitle.compose(
            stage: progress?.stage,
            sessionsComplete: progress?.sessionsComplete,
            sessionsTotal: progress?.sessionsTotal,
            etaRemainingSeconds: progress?.etaRemainingSeconds,
            resuming: progress?.attachedFromOrphan ?? false,
            separator: WindowSubtitle.separator,
            localize: { i18n.t($0, $1) }
        )
    }
}
