import SwiftUI

/// Menu-bar commands that act on **one window**, routed to the front one.
///
/// ## Why this exists
///
/// `SidebarVisibilityFocus` fixed View ▸ Hide/Show Projects the same way and
/// left a note: sixteen other menu commands still went out over
/// `NotificationCenter.default`, so every open window received every one. That
/// count had grown to nineteen by 15 Aug 2026 — which is the finding, not a
/// footnote. New commands kept being written as broadcasts because it is the
/// path of least resistance and nothing fails when you take it. This type is
/// the obvious idiom to copy instead, and `check-menu-routing.sh` is what stops
/// a twentieth broadcast being added.
///
/// The bugs are live rather than hypothetical: a second window is reachable
/// today from the Window menu, and with two open, New Project creates two
/// projects and Rename opens an editor in both.
///
/// ## One sink, not seventeen focused values
///
/// Read against the code the sites fall into four groups (see
/// `docs/design-workspace.md` §"P1's taxonomy"), and two of them —
/// window-targeted (present a sheet here) and selection-targeted (act on this
/// window's sidebar selection) — share one routing rule: *the key window*. They
/// differ only in what the window then does. So they get one focused value
/// carrying a command sink rather than one focused value each.
///
/// **Scene-scoped, not view-scoped**, for the reason `SidebarVisibilityFocus`
/// documents: a view-scoped value drops out the moment focus moves into the
/// WKWebView, which is most of the time.
enum WindowCommand: Equatable {

    // MARK: Group 1 — app-global, with a window follow-through

    /// File ▸ New Project (⌘N).
    case newProject
    /// File ▸ New Folder (⇧⌘N).
    case newFolder

    // MARK: Group 2 — window-targeted (this window's own UI)

    /// Bristlenose ▸ AI & Privacy…
    case showAIConsent
    /// Quotes ▸ Send to Miro…
    case showMiro
    /// Help ▸ Welcome to Bristlenose — deselect, revealing the welcome pane.
    case showWelcome
    /// View ▸ Switch Session (⌘⌥L on the Sessions lens).
    case showSessionsSwitcher
    /// Diagnostics ▸ Diagnostic fixtures — inject a named scenario into this
    /// window's selected project.
    case applyDebugFixture(scenario: String)

    // MARK: Group 3 — selection-targeted (this window's sidebar selection)

    /// File ▸ Add Files… (⇧⌘A).
    case addFiles
    /// Project ▸ Rename (project selected).
    case renameProject
    /// Project ▸ Rename (folder selected).
    case renameFolder
    /// Project ▸ Delete (folder selected).
    case deleteFolder
    /// Project ▸ Move to ▸ … — `nil` is the "No Folder" row (move to root).
    case moveProject(toFolder: UUID?)
    /// Project ▸ Show Transcripts in Finder.
    case revealTranscripts
    /// Project ▸ Locate…
    case locateProject
    /// Project ▸ Stop Analysis (⌘.).
    case stopProject
    /// Project ▸ Remove from Sidebar (⌘⌫).
    case removeFromSidebar
}

extension WindowCommand {

    /// Whether this command still does something with **no project window
    /// frontmost** — group 1 only.
    ///
    /// New Project is two halves: `projectIndex.addProject(…)`, which is
    /// app-global and needs no window, and *select it and begin inline rename*,
    /// which is window state. So the command survives having no window: the
    /// model half runs at app level and the follow-through is handed to a window
    /// that opens to receive it.
    ///
    /// Everything else genuinely needs a window — there is no meaningful
    /// "rename the selection" when no window is showing a selection — so those
    /// dim, which is what every Mac app does with a utility window frontmost.
    var hasAppLevelFallback: Bool {
        switch self {
        case .newProject, .newFolder: return true
        default: return false
        }
    }

    /// Commands that act on **which study** — the axis a child window does not
    /// have.
    ///
    /// A child holds a lens, not a project (`design-workspace.md` §"What a child
    /// window is"). It has no selection and no project list, so every one of
    /// these would either act on nothing or act on a study the window has no
    /// claim to. Dimming them says the same thing the missing project list says,
    /// in the place a Mac user looks when a click does nothing.
    ///
    /// The lens commands are deliberately absent from this list: switching view
    /// is the axis a child owns, and is the entire reason it exists.
    ///
    /// `removeFromSidebar`, `renameProject`, `renameFolder`, `deleteFolder`,
    /// `moveProject` and `locateProject` are not listed because they already
    /// require a sidebar selection, which a child never has — they dim through
    /// `hasKeyWindow` and their own guards without needing to be named here.
    /// Listing them anyway would be a second rule saying the same thing.
    var actsOnTheStudyAxis: Bool {
        switch self {
        case .newProject, .newFolder, .addFiles: return true
        default: return false
        }
    }

    /// Whether the menu item is enabled, given whether a project window is
    /// frontmost and what kind of window it is. The one decision every converted
    /// site shares, in one place so the sites cannot drift apart on it.
    ///
    /// The role is checked **first and unconditionally**: a study-axis command
    /// in a child stays dim even though `newProject` and `newFolder` carry an
    /// app-level fallback. That fallback exists for "no window is frontmost, so
    /// make one" — a genuinely different situation from "the frontmost window is
    /// one that deliberately cannot do this".
    func isEnabled(hasKeyWindow: Bool, role: WindowRoster.Role = .master) -> Bool {
        if role == .child, actsOnTheStudyAxis { return false }
        return hasKeyWindow || hasAppLevelFallback
    }
}

/// The key window's command target.
///
/// `Equatable` on the window's identity alone: the closure captures per-window
/// `@State`, so a fresh one is built on every body pass and comparing closures
/// isn't possible anyway. Identity is the thing that actually changes when the
/// front window changes, which is the only change the menu needs to notice.
struct WindowCommandSink: Equatable {
    let windowID: UUID
    /// Master or child. Carried on the sink because it is a property of the
    /// window the menu is currently targeting, and the menu has no other way to
    /// ask — `focusedSceneValue` gives it this sink and nothing else.
    let role: WindowRoster.Role
    let perform: (WindowCommand) -> Void

    /// Identity **and** role. The role is fixed for a window's life, so this
    /// adds no churn — but leaving it out would mean a menu built against a
    /// master staying enabled when focus moved to a child with the same body
    /// pass, which is the one moment the enablement has to change.
    static func == (lhs: WindowCommandSink, rhs: WindowCommandSink) -> Bool {
        lhs.windowID == rhs.windowID && lhs.role == rhs.role
    }
}

struct WindowCommandKey: FocusedValueKey {
    typealias Value = WindowCommandSink
}

/// The key window's `BridgeHandler` — the *state* half of the same seam.
///
/// Routing a command to the front window is only half the job: the menu also
/// reads that window's state to decide its labels and its dimming (`activeTab`
/// picks the left-panel row's name, `canUndo` gates Undo, `isReady` gates
/// Print). While one `BridgeHandler` was shared app-wide, every window
/// necessarily showed the same lens — routing the *command* correctly wouldn't
/// have helped, because the *state* it acts on was global. Stage 3a splits the
/// object per window and this is how the menu bar finds the right one.
struct BridgeHandlerKey: FocusedValueKey {
    typealias Value = BridgeHandler
}

extension FocusedValues {
    /// The key window's menu-command sink. `nil` when no project window is
    /// frontmost — e.g. Settings, the Import window, or a diagnostics window —
    /// which the menus render as dimmed items, except for the two commands that
    /// declare `hasAppLevelFallback`.
    var windowCommands: WindowCommandSink? {
        get { self[WindowCommandKey.self] }
        set { self[WindowCommandKey.self] = newValue }
    }

    /// The key window's `BridgeHandler`. `nil` in the same cases as
    /// `windowCommands`; `MenuCommands` substitutes `BridgeHandler.unattached`,
    /// whose all-default state dims every item that depends on a report.
    var bridge: BridgeHandler? {
        get { self[BridgeHandlerKey.self] }
        set { self[BridgeHandlerKey.self] = newValue }
    }
}

/// The app-level half of group 1 — what New Project / New Folder do when no
/// project window is frontmost.
///
/// Both write the one-shot batons `ProjectIndex` already uses to hand work to a
/// sidebar that doesn't exist yet (`pendingIconReveal` established the idiom,
/// `pendingRename` followed it). The caller then opens a window, which drains
/// them on appear.
///
/// **Known papercut, deliberately not fixed here.** With a project window open
/// but Settings frontmost, this opens a *second* project window instead of
/// bringing the first forward — SwiftUI's `openWindow(id:)` on a `WindowGroup`
/// always spawns. Fixing it wants a roster of live project windows, which is
/// also what `applicationShouldHandleReopen` needs, so it lands with that in P2
/// rather than growing a second mechanism here. Today's behaviour in the same
/// situation is worse (a project created in *every* open window), so this is
/// strictly forward.
@MainActor
enum NewItemFallback {

    /// Create a project at app level and stage the window follow-through.
    static func createProject(in index: ProjectIndex, named name: String) {
        let project = index.addProject(name: name, path: "")
        index.pendingSelection = .project(project.id)
        index.pendingRename = project.id
    }

    /// Create a folder at app level and stage the window follow-through.
    static func createFolder(in index: ProjectIndex, named name: String) {
        let folder = index.addFolder(name: name)
        index.pendingSelection = .folder(folder.id)
        index.pendingRename = folder.id
    }
}
