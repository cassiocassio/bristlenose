import SwiftUI

// MARK: - Menu bar

/// Native menu bar — every command reachable, keyboard shortcuts discoverable.
///
/// Uses the `View`-inside-`Commands` pattern: `@ObservedObject` is unreliable
/// directly in `Commands.body`, so each menu section is a small `View` struct
/// that owns `@ObservedObject var bridgeHandler`. Views inside `CommandMenu` /
/// `CommandGroup` follow normal SwiftUI view lifecycle and observe correctly.
///
/// All actions dispatch through `bridgeHandler.menuAction(_:payload:)` which
/// calls `callAsyncJavaScript` with structured arguments (security rule 3).
///
/// Menu order: Bristlenose · File · Edit · View · Project · Codes · Quotes · Video · Window · Help
struct MenuCommands: Commands {
    let bridgeHandler: BridgeHandler

    var body: some Commands {
        // App menu (Bristlenose)
        CommandGroup(replacing: .appInfo) {
            AppMenuContent(bridgeHandler: bridgeHandler)
        }

        // File menu
        CommandGroup(replacing: .newItem) {
            FileMenuContent(bridgeHandler: bridgeHandler)
        }
        CommandGroup(replacing: .printItem) {
            PrintMenuContent(bridgeHandler: bridgeHandler)
        }

        // Edit > Undo/Redo — gated on isEditing.
        // When isEditing, these items are hidden so Cmd+Z falls through to
        // WKWebView's responder chain for character-level undo.
        // Do NOT touch .pasteboard — Cut/Copy/Paste/Select All handled by
        // WKWebView's responder chain automatically.
        CommandGroup(replacing: .undoRedo) {
            UndoRedoMenuContent(bridgeHandler: bridgeHandler)
        }

        // Edit > Find (after text editing group)
        CommandGroup(after: .textEditing) {
            FindMenuContent(bridgeHandler: bridgeHandler)
        }

        // View menu — tabs, sidebar/panel toggles, filters, zoom, dark mode
        CommandGroup(replacing: .toolbar) {
            ViewMenuContent(bridgeHandler: bridgeHandler)
        }

        // App-specific menus between View and Window
        CommandMenu("Project") {
            ProjectMenuContent(bridgeHandler: bridgeHandler)
        }
        CommandMenu("Codes") {
            CodesMenuContent(bridgeHandler: bridgeHandler)
        }
        CommandMenu("Quotes") {
            QuotesMenuContent(bridgeHandler: bridgeHandler)
        }
        CommandMenu("Video") {
            VideoMenuContent(bridgeHandler: bridgeHandler)
        }

        // Help menu
        CommandGroup(replacing: .help) {
            HelpMenuContent(bridgeHandler: bridgeHandler)
        }
    }
}

// MARK: - App menu (Bristlenose)

/// About, Check System Health.
/// Settings (Cmd+,) is NOT here — provided automatically by the Settings {} scene.
private struct AppMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Button("About Bristlenose") {
            NSApp.orderFrontStandardAboutPanel()
        }

        Divider()

        Button("Check System Health...") {
            bridgeHandler.menuAction("checkSystemHealth")
        }
    }
}

// MARK: - File menu

private struct FileMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Button("New Project...") {
            bridgeHandler.menuAction("newProject")
        }
        .keyboardShortcut("n", modifiers: .command)

        Button("Open in New Window") {
            bridgeHandler.menuAction("openInNewWindow")
        }
        .keyboardShortcut("o", modifiers: [.command, .shift])

        Divider()

        Button("Export Report...") {
            bridgeHandler.menuAction("exportReport")
        }
        .keyboardShortcut("e", modifiers: [.command, .shift])

        Button("Export Anonymised...") {
            bridgeHandler.menuAction("exportAnonymised")
        }
    }
}

private struct PrintMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Button("Page Setup...") {
            bridgeHandler.menuAction("pageSetup")
        }

        Button("Print...") {
            bridgeHandler.menuAction("print")
        }
        .keyboardShortcut("p", modifiers: .command)
    }
}

// MARK: - Edit > Undo/Redo

/// When isEditing is true, Undo/Redo are hidden so Cmd+Z falls through to
/// WKWebView's text-editing responder chain for character-level undo.
/// When !isEditing, they route to the app-level undo stack via bridge.
private struct UndoRedoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        if !bridgeHandler.isEditing {
            Button(bridgeHandler.undoLabel ?? "Undo") {
                bridgeHandler.menuAction("undo")
            }
            .keyboardShortcut("z", modifiers: .command)
            .disabled(!bridgeHandler.canUndo)

            Button("Redo") {
                bridgeHandler.menuAction("redo")
            }
            .keyboardShortcut("z", modifiers: [.command, .shift])
            .disabled(!bridgeHandler.canRedo)
        }
    }
}

// MARK: - Edit > Find

/// Find routes to the web search bar (richer than native WKWebView find).
private struct FindMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Divider()

        Button("Find...") {
            bridgeHandler.menuAction("find")
        }
        .keyboardShortcut("f", modifiers: .command)

        Button("Find Next") {
            bridgeHandler.menuAction("findNext")
        }
        .keyboardShortcut("g", modifiers: .command)

        Button("Find Previous") {
            bridgeHandler.menuAction("findPrevious")
        }
        .keyboardShortcut("g", modifiers: [.command, .shift])

        Button("Use Selection for Find") {
            bridgeHandler.menuAction("useSelectionForFind")
        }
        .keyboardShortcut("e", modifiers: .command)

        Button("Jump to Selection") {
            bridgeHandler.menuAction("jumpToSelection")
        }
        .keyboardShortcut("j", modifiers: .command)
    }
}

// MARK: - View menu

private struct ViewMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        // Tab shortcuts Cmd+1 through Cmd+5
        ForEach(Array(Tab.allCases.enumerated()), id: \.element.id) { index, tab in
            Button(tab.label) {
                bridgeHandler.switchToTab(tab)
            }
            .keyboardShortcut(
                KeyEquivalent(Character("\(index + 1)")),
                modifiers: .command
            )
        }

        Divider()

        // Sidebar and panel toggles
        Button("Toggle Sidebar") {
            NSApp.keyWindow?.firstResponder?.tryToPerform(
                #selector(NSSplitViewController.toggleSidebar(_:)),
                with: nil
            )
        }
        .keyboardShortcut("s", modifiers: [.command, .option])

        Button("Toggle Left Panel") {
            bridgeHandler.menuAction("toggleLeftPanel")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Button("Toggle Right Panel") {
            bridgeHandler.menuAction("toggleRightPanel")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Button("Toggle Inspector Panel") {
            bridgeHandler.menuAction("toggleInspectorPanel")
        }
        .disabled(bridgeHandler.activeTab != .analysis)

        Divider()

        // Quote filters (Quotes tab only)
        Button("All Quotes") {
            bridgeHandler.menuAction("allQuotes")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Button("Starred Quotes Only") {
            bridgeHandler.menuAction("starredQuotesOnly")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Button("Filter by Tag...") {
            bridgeHandler.menuAction("filterByTag")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Divider()

        // Zoom — Cmd+0 reserved for Window > Projects
        Button("Zoom In") {
            bridgeHandler.menuAction("zoomIn")
        }
        .keyboardShortcut("=", modifiers: .command)

        Button("Zoom Out") {
            bridgeHandler.menuAction("zoomOut")
        }
        .keyboardShortcut("-", modifiers: .command)

        Button("Actual Size") {
            bridgeHandler.menuAction("actualSize")
        }

        Divider()

        // Dark mode toggle — label swaps based on current state
        Button(bridgeHandler.isDarkMode ? "Switch to Light Mode" : "Switch to Dark Mode") {
            bridgeHandler.menuAction("toggleDarkMode")
        }
    }
}

// MARK: - Project menu

private struct ProjectMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Button("Show in Finder") {
            bridgeHandler.menuAction("revealInFinder")
        }
        .keyboardShortcut("r", modifiers: [.command, .shift])

        Button("Rename...") {
            bridgeHandler.menuAction("renameProject")
        }

        Button("Re-analyse...") {
            bridgeHandler.menuAction("reAnalyse")
        }

        Button("Archive...") {
            bridgeHandler.menuAction("archive")
        }

        Divider()

        Button("Delete...") {
            bridgeHandler.menuAction("deleteProject")
        }
    }
}

// MARK: - Codes menu

private struct CodesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    private var isCodeTab: Bool {
        bridgeHandler.activeTab == .codebook || bridgeHandler.activeTab == .quotes
    }

    var body: some View {
        // Always enabled
        Button("Create Code Group") {
            bridgeHandler.menuAction("createCodeGroup")
        }

        // Dimmed unless on codebook or quotes tab
        Button("Rename Code Group...") {
            bridgeHandler.menuAction("renameCodeGroup")
        }
        .disabled(!isCodeTab)

        Button("Delete Code Group") {
            bridgeHandler.menuAction("deleteCodeGroup")
        }
        .disabled(!isCodeTab)

        Button("Show/Hide Code Group") {
            bridgeHandler.menuAction("toggleCodeGroup")
        }
        .disabled(!isCodeTab)

        Divider()

        Button("Create Code") {
            bridgeHandler.menuAction("createCode")
        }

        Button("Rename Code...") {
            bridgeHandler.menuAction("renameCode")
        }
        .disabled(!isCodeTab)

        Button("Delete Code") {
            bridgeHandler.menuAction("deleteCode")
        }
        .disabled(!isCodeTab)

        Button("Merge Codes...") {
            bridgeHandler.menuAction("mergeCode")
        }
        .disabled(!isCodeTab)

        Divider()

        // Always enabled
        Button("Browse Codebooks...") {
            bridgeHandler.menuAction("browseCodebooks")
        }

        Button("Import Framework...") {
            bridgeHandler.menuAction("importFramework")
        }

        Button("Remove Framework") {
            bridgeHandler.menuAction("removeFramework")
        }
        .disabled(!isCodeTab)
    }
}

// MARK: - Quotes menu

/// All items dimmed when not on Quotes tab. Quote-specific actions additionally
/// require a focused quote. No bare-key shortcuts shown in menu — those are
/// web-only (s, h, arrows etc.).
private struct QuotesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    private var onQuotesTab: Bool {
        bridgeHandler.activeTab == .quotes
    }

    private var hasFocus: Bool {
        onQuotesTab && bridgeHandler.focusedQuoteId != nil
    }

    private var hasSelection: Bool {
        onQuotesTab && bridgeHandler.selectedQuoteCount > 0
    }

    var body: some View {
        Button("Star") {
            bridgeHandler.menuAction("star")
        }
        .disabled(!hasFocus)

        Button("Hide") {
            bridgeHandler.menuAction("hide")
        }
        .disabled(!hasFocus)

        Button("Add Tag...") {
            bridgeHandler.menuAction("addTag")
        }
        .disabled(!hasFocus)

        Button("Apply Last Tag") {
            bridgeHandler.menuAction("applyLastTag")
        }
        .disabled(!hasFocus)

        Button("Reveal in Transcript") {
            bridgeHandler.menuAction("revealInTranscript")
        }
        .disabled(!hasFocus)

        Button("Play/Pause") {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button("Next Quote") {
            bridgeHandler.menuAction("nextQuote")
        }
        .disabled(!onQuotesTab)

        Button("Previous Quote") {
            bridgeHandler.menuAction("previousQuote")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button("Extend Selection Down") {
            bridgeHandler.menuAction("extendSelectionDown")
        }
        .disabled(!onQuotesTab)

        Button("Extend Selection Up") {
            bridgeHandler.menuAction("extendSelectionUp")
        }
        .disabled(!onQuotesTab)

        Button("Toggle Selection") {
            bridgeHandler.menuAction("toggleSelection")
        }
        .disabled(!onQuotesTab)

        Button("Clear Selection") {
            bridgeHandler.menuAction("clearSelection")
        }
        .disabled(!hasSelection)

        Divider()

        Button("Copy as CSV") {
            bridgeHandler.menuAction("copyAsCSV")
        }
        .disabled(!hasSelection)
    }
}

// MARK: - Video menu

/// All items dimmed when no player is open. Play/Pause label swaps based on
/// player state. No bare-key shortcuts shown — arrows, space are web-only.
private struct VideoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    private var active: Bool { bridgeHandler.hasPlayer }

    var body: some View {
        Button(bridgeHandler.playerPlaying ? "Pause" : "Play") {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!active)

        Divider()

        Button("Skip Forward 5 Seconds") {
            bridgeHandler.menuAction("skipForward5")
        }
        .disabled(!active)

        Button("Skip Back 5 Seconds") {
            bridgeHandler.menuAction("skipBack5")
        }
        .disabled(!active)

        Button("Skip Forward 30 Seconds") {
            bridgeHandler.menuAction("skipForward30")
        }
        .disabled(!active)

        Button("Skip Back 30 Seconds") {
            bridgeHandler.menuAction("skipBack30")
        }
        .disabled(!active)

        Divider()

        Button("Speed Up") {
            bridgeHandler.menuAction("speedUp")
        }
        .disabled(!active)

        Button("Slow Down") {
            bridgeHandler.menuAction("slowDown")
        }
        .disabled(!active)

        Button("Normal Speed") {
            bridgeHandler.menuAction("normalSpeed")
        }
        .disabled(!active)

        Divider()

        Button("Volume Up") {
            bridgeHandler.menuAction("volumeUp")
        }
        .disabled(!active)

        Button("Volume Down") {
            bridgeHandler.menuAction("volumeDown")
        }
        .disabled(!active)

        Button("Mute") {
            bridgeHandler.menuAction("mute")
        }
        .disabled(!active)

        Divider()

        Button("Picture in Picture") {
            bridgeHandler.menuAction("pictureInPicture")
        }
        .disabled(!active)

        Button("Fullscreen") {
            bridgeHandler.menuAction("fullscreen")
        }
        .disabled(!active)
    }
}

// MARK: - Help menu

private struct HelpMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Button("Bristlenose Help") {
            bridgeHandler.menuAction("showHelp")
        }
        .keyboardShortcut("?", modifiers: .command)

        Button("Keyboard Shortcuts") {
            bridgeHandler.menuAction("showKeyboardShortcuts")
        }

        Divider()

        Button("Release Notes") {
            bridgeHandler.menuAction("showReleaseNotes")
        }

        Button("Send Feedback") {
            bridgeHandler.menuAction("sendFeedback")
        }
    }
}
