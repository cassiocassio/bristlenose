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
///
/// Menu item labels are translated via `I18n` (reads from shared JSON locale files).
/// `CommandMenu` titles stay in English — SwiftUI resolves `LocalizedStringKey`
/// from `.lproj` bundles, not runtime JSON. Matches ATLAS.ti/MAXQDA precedent.
struct MenuCommands: Commands {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var i18n: I18n

    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            AppMenuContent(bridgeHandler: bridgeHandler, serveManager: serveManager, i18n: i18n)
        }

        CommandGroup(replacing: .newItem) {
            FileMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(replacing: .undoRedo) {
            UndoRedoMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(after: .textEditing) {
            FindMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(replacing: .toolbar) {
            ViewMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        // CommandMenu titles stay in English (see doc comment above).
        CommandMenu("Project") {
            ProjectMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Codes") {
            CodesMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Quotes") {
            QuotesMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Video") {
            VideoMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(replacing: .help) {
            HelpMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
    }
}

// MARK: - App menu (Bristlenose)

private struct AppMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var i18n: I18n

    var body: some View {
        Button(i18n.t("desktop.menu.app.about")) {
            let buildNumber = Bundle.main.infoDictionary?["CFBundleVersion"] as? String
            var options: [NSApplication.AboutPanelOptionKey: Any] = [:]

            if let version = serveManager.serverVersion {
                var versionString = version
                if let build = buildNumber {
                    versionString += " (\(build))"
                }
                options[.applicationVersion] = versionString
            }

            options[.version] = ""
            NSApp.orderFrontStandardAboutPanel(options: options)
        }

        Divider()

        Button(i18n.t("desktop.menu.app.checkHealth")) {
            bridgeHandler.menuAction("checkSystemHealth")
        }
    }
}

// MARK: - File menu

private struct FileMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Button(i18n.t("desktop.menu.file.newProject")) {
            bridgeHandler.menuAction("newProject")
        }
        .keyboardShortcut("n", modifiers: .command)

        Button(i18n.t("desktop.menu.file.openInNewWindow")) {
            bridgeHandler.menuAction("openInNewWindow")
        }
        .keyboardShortcut("o", modifiers: [.command, .shift])

        Divider()

        Button(i18n.t("desktop.menu.file.exportReport")) {
            bridgeHandler.menuAction("exportReport")
        }
        .keyboardShortcut("e", modifiers: [.command, .shift])

        Button(i18n.t("desktop.menu.file.exportAnonymised")) {
            bridgeHandler.menuAction("exportAnonymised")
        }

        Divider()

        Button(i18n.t("desktop.menu.file.pageSetup")) {
            bridgeHandler.menuAction("pageSetup")
        }

        Button(i18n.t("desktop.menu.file.print")) {
            bridgeHandler.menuAction("print")
        }
        .keyboardShortcut("p", modifiers: .command)
    }
}

// MARK: - Edit > Undo/Redo

private struct UndoRedoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        if !bridgeHandler.isEditing {
            Button(bridgeHandler.undoLabel ?? i18n.t("desktop.menu.edit.undo")) {
                bridgeHandler.menuAction("undo")
            }
            .keyboardShortcut("z", modifiers: .command)
            .disabled(!bridgeHandler.canUndo)

            Button(i18n.t("desktop.menu.edit.redo")) {
                bridgeHandler.menuAction("redo")
            }
            .keyboardShortcut("z", modifiers: [.command, .shift])
            .disabled(!bridgeHandler.canRedo)
        }
    }
}

// MARK: - Edit > Find

private struct FindMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Divider()

        Button(i18n.t("desktop.menu.edit.find")) {
            bridgeHandler.menuAction("find")
        }
        .keyboardShortcut("f", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.findNext")) {
            let text = NSPasteboard(name: .find).string(forType: .string) ?? ""
            bridgeHandler.menuAction("findNext", payload: ["text": text])
        }
        .keyboardShortcut("g", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.findPrevious")) {
            let text = NSPasteboard(name: .find).string(forType: .string) ?? ""
            bridgeHandler.menuAction("findPrevious", payload: ["text": text])
        }
        .keyboardShortcut("g", modifiers: [.command, .shift])

        Button(i18n.t("desktop.menu.edit.useSelectionForFind")) {
            bridgeHandler.menuAction("useSelectionForFind")
        }
        .keyboardShortcut("e", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.jumpToSelection")) {
            bridgeHandler.menuAction("jumpToSelection")
        }
        .keyboardShortcut("j", modifiers: .command)
    }
}

// MARK: - View menu

private struct ViewMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    /// Locale key suffix for the left-panel label, per tab.
    private var leftPanelKey: String? {
        switch bridgeHandler.activeTab {
        case .quotes:   return "Contents"
        case .codebook: return "Codes"
        case .analysis: return "Signals"
        default:        return nil
        }
    }

    private var hasLeftPanel: Bool {
        leftPanelKey != nil
    }

    var body: some View {
        // Tab shortcuts Cmd+1 through Cmd+5
        ForEach(Array(Tab.allCases.enumerated()), id: \.element.id) { index, tab in
            Button(tab.localizedLabel(i18n)) {
                bridgeHandler.switchToTab(tab)
            }
            .keyboardShortcut(
                KeyEquivalent(Character("\(index + 1)")),
                modifiers: .command
            )
        }

        Divider()

        Button(i18n.t("desktop.menu.view.toggleSidebar")) {
            NSApp.keyWindow?.firstResponder?.tryToPerform(
                #selector(NSSplitViewController.toggleSidebar(_:)),
                with: nil
            )
        }
        .keyboardShortcut("s", modifiers: [.command, .option])

        Button(i18n.t("desktop.menu.view.show\(leftPanelKey ?? "Contents")")) {
            bridgeHandler.menuAction("toggleLeftPanel")
        }
        .keyboardShortcut("l", modifiers: [.command, .option])
        .disabled(!hasLeftPanel)

        Button(i18n.t("desktop.menu.view.showTags")) {
            bridgeHandler.menuAction("toggleRightPanel")
        }
        .keyboardShortcut("t", modifiers: [.command, .option])
        .disabled(bridgeHandler.activeTab != .quotes)

        Button(i18n.t("desktop.menu.view.showHeatmap")) {
            bridgeHandler.menuAction("toggleInspectorPanel")
        }
        .disabled(bridgeHandler.activeTab != .analysis)

        Divider()

        Button(i18n.t("desktop.menu.view.allQuotes")) {
            bridgeHandler.menuAction("allQuotes")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Button(i18n.t("desktop.menu.view.starredQuotesOnly")) {
            bridgeHandler.menuAction("starredQuotesOnly")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Button(i18n.t("desktop.menu.view.filterByTag")) {
            bridgeHandler.menuAction("filterByTag")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Divider()

        Button(i18n.t("desktop.menu.view.zoomIn")) {
            bridgeHandler.menuAction("zoomIn")
        }
        .keyboardShortcut("=", modifiers: .command)

        Button(i18n.t("desktop.menu.view.zoomOut")) {
            bridgeHandler.menuAction("zoomOut")
        }
        .keyboardShortcut("-", modifiers: .command)

        Button(i18n.t("desktop.menu.view.actualSize")) {
            bridgeHandler.menuAction("actualSize")
        }

        Divider()

        Button(bridgeHandler.isDarkMode
               ? i18n.t("desktop.menu.view.switchToLightMode")
               : i18n.t("desktop.menu.view.switchToDarkMode")) {
            bridgeHandler.menuAction("toggleDarkMode")
        }
    }
}

// MARK: - Project menu

private struct ProjectMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Button(i18n.t("desktop.menu.project.showInFinder")) {
            bridgeHandler.menuAction("revealInFinder")
        }
        .keyboardShortcut("r", modifiers: [.command, .shift])

        Button(i18n.t("desktop.menu.project.rename")) {
            bridgeHandler.menuAction("renameProject")
        }

        Button(i18n.t("desktop.menu.project.reAnalyse")) {
            bridgeHandler.menuAction("reAnalyse")
        }

        Button(i18n.t("desktop.menu.project.archive")) {
            bridgeHandler.menuAction("archive")
        }

        Divider()

        Button(i18n.t("desktop.menu.project.delete")) {
            bridgeHandler.menuAction("deleteProject")
        }
    }
}

// MARK: - Codes menu

private struct CodesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var isCodeTab: Bool {
        bridgeHandler.activeTab == .codebook || bridgeHandler.activeTab == .quotes
    }

    var body: some View {
        Button(i18n.t("desktop.menu.codes.createCodeGroup")) {
            bridgeHandler.menuAction("createCodeGroup")
        }

        Button(i18n.t("desktop.menu.codes.renameCodeGroup")) {
            bridgeHandler.menuAction("renameCodeGroup")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.deleteCodeGroup")) {
            bridgeHandler.menuAction("deleteCodeGroup")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.showHideCodeGroup")) {
            bridgeHandler.menuAction("toggleCodeGroup")
        }
        .disabled(!isCodeTab)

        Divider()

        Button(i18n.t("desktop.menu.codes.createCode")) {
            bridgeHandler.menuAction("createCode")
        }

        Button(i18n.t("desktop.menu.codes.renameCode")) {
            bridgeHandler.menuAction("renameCode")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.deleteCode")) {
            bridgeHandler.menuAction("deleteCode")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.mergeCodes")) {
            bridgeHandler.menuAction("mergeCode")
        }
        .disabled(!isCodeTab)

        Divider()

        Button(i18n.t("desktop.menu.codes.browseCodebooks")) {
            bridgeHandler.menuAction("browseCodebooks")
        }

        Button(i18n.t("desktop.menu.codes.importFramework")) {
            bridgeHandler.menuAction("importFramework")
        }

        Button(i18n.t("desktop.menu.codes.removeFramework")) {
            bridgeHandler.menuAction("removeFramework")
        }
        .disabled(!isCodeTab)
    }
}

// MARK: - Quotes menu

private struct QuotesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

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
        Button(i18n.t("desktop.menu.quotes.star")) {
            bridgeHandler.menuAction("star")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.hide")) {
            bridgeHandler.menuAction("hide")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.addTag")) {
            bridgeHandler.menuAction("addTag")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.applyLastTag")) {
            bridgeHandler.menuAction("applyLastTag")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.revealInTranscript")) {
            bridgeHandler.menuAction("revealInTranscript")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.playPause")) {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button(i18n.t("desktop.menu.quotes.nextQuote")) {
            bridgeHandler.menuAction("nextQuote")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.previousQuote")) {
            bridgeHandler.menuAction("previousQuote")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button(i18n.t("desktop.menu.quotes.extendSelectionDown")) {
            bridgeHandler.menuAction("extendSelectionDown")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.extendSelectionUp")) {
            bridgeHandler.menuAction("extendSelectionUp")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.toggleSelection")) {
            bridgeHandler.menuAction("toggleSelection")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.clearSelection")) {
            bridgeHandler.menuAction("clearSelection")
        }
        .disabled(!hasSelection)

        Divider()

        Button(i18n.t("desktop.menu.quotes.copyAsCSV")) {
            bridgeHandler.menuAction("copyAsCSV")
        }
        .disabled(!hasSelection)
    }
}

// MARK: - Video menu

private struct VideoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var active: Bool { bridgeHandler.hasPlayer }

    var body: some View {
        Button(bridgeHandler.playerPlaying
               ? i18n.t("desktop.menu.video.pause")
               : i18n.t("desktop.menu.video.play")) {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.skipForward5")) {
            bridgeHandler.menuAction("skipForward5")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipBack5")) {
            bridgeHandler.menuAction("skipBack5")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipForward30")) {
            bridgeHandler.menuAction("skipForward30")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipBack30")) {
            bridgeHandler.menuAction("skipBack30")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.speedUp")) {
            bridgeHandler.menuAction("speedUp")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.slowDown")) {
            bridgeHandler.menuAction("slowDown")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.normalSpeed")) {
            bridgeHandler.menuAction("normalSpeed")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.volumeUp")) {
            bridgeHandler.menuAction("volumeUp")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.volumeDown")) {
            bridgeHandler.menuAction("volumeDown")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.mute")) {
            bridgeHandler.menuAction("mute")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.pictureInPicture")) {
            bridgeHandler.menuAction("pictureInPicture")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.fullscreen")) {
            bridgeHandler.menuAction("fullscreen")
        }
        .disabled(!active)
    }
}

// MARK: - Help menu

private struct HelpMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Button(i18n.t("desktop.menu.help.bristlenoseHelp")) {
            bridgeHandler.menuAction("showHelp")
        }
        .keyboardShortcut("?", modifiers: .command)

        Button(i18n.t("desktop.menu.help.keyboardShortcuts")) {
            bridgeHandler.menuAction("showKeyboardShortcuts")
        }

        Divider()

        Button(i18n.t("desktop.menu.help.releaseNotes")) {
            bridgeHandler.menuAction("showReleaseNotes")
        }

        Button(i18n.t("desktop.menu.help.sendFeedback")) {
            bridgeHandler.menuAction("sendFeedback")
        }
    }
}
