#if DEBUG
import AppKit
import SwiftUI

// MARK: - Types

/// One changed surface, in the states that show the change. Diagnostics ▸
/// Review Gallery lists these; `docs/mockups/review-gallery.html` §1–§2 is the
/// design.
///
/// **Every specimen is the real view, fed fake inputs.** Nothing here redraws a
/// surface — a state that needs data the view cannot be given has a seam in the
/// view's own type (`ServeManager.debugMarkStartedByRetry`,
/// `PipelineRunner._debugSetState`), never a copy of the view.
///
/// **The commits are the review key.** `ReviewGalleryReviewed` stores the list
/// it was reviewed at, so a change that grows the list un-reviews the entry.
/// `tests/test_review_gallery_registry.py` resolves every hash in git, and
/// `ReviewGalleryRegistryTests` builds and hosts every state, so an entry that
/// names a gone commit or a view that no longer builds fails a test rather than
/// rotting quietly.
struct ReviewGalleryEntry: Identifiable {
    enum Section: String, CaseIterable, Identifiable {
        case panesAndSheets, sidebarRows, popovers, settings, inTheApp
        var id: String { rawValue }

        /// Chrome is English by decision (the Diagnostics exception in
        /// `docs/design-i18n.md`); only the specimens go through i18n.
        var title: String {
            switch self {
            case .panesAndSheets: "Panes and sheets"
            case .sidebarRows: "Sidebar rows"
            case .popovers: "Popovers"
            case .settings: "Settings"
            case .inTheApp: "In the app (opens the real thing)"
            }
        }
    }

    let id: String
    let title: String
    let what: String
    /// Short hashes, at least one.
    let commits: [String]
    /// Source files under `desktop/Bristlenose/Bristlenose/` (or the repo path
    /// for anything else) — the chips under the title.
    let files: [String]
    let section: Section
    /// Latest author date of `commits`, `yyyy-MM-dd` — what "Changed since"
    /// filters on.
    let landed: String
    let states: [ReviewGalleryState]
}

struct ReviewGalleryState {
    let name: String
    /// Pins the specimen's language for a state that is *about* a language
    /// (a plural in French, say). Nil follows the toolbar's Language picker.
    var locale: String? = nil
    let make: @MainActor (ReviewGalleryContext) -> ReviewGallerySpecimen
}

enum ReviewGallerySpecimen {
    /// One real view, with the monospaced line that says what it was fed.
    case view(AnyView, label: String)
    /// A family of small states, laid side by side.
    case views([(label: String, AnyView)])
    /// A change the gallery cannot fake honestly: how to reach it in the app,
    /// and a door straight to it where the app has one.
    case navigation(recipe: String, open: (@MainActor () -> Void)?)
}

struct ReviewGalleryContext {
    /// The gallery's own `I18n` (the toolbar's Language), so a specimen can
    /// resolve a string or hand it to an AppKit controller.
    let i18n: I18n
    /// The toolbar's Appearance; nil follows the app.
    let appearance: ColorScheme?
    /// Writes the footer readout line. Specimen buttons call this instead of
    /// opening real sheets.
    let log: (String) -> Void
}

// MARK: - Reviewed

/// Which entries have been reviewed on this Mac, keyed by entry id and stamped
/// with the commit list they were reviewed at. Reviewed iff the stamp equals
/// the entry's current list, so an entry whose list grows (a fix landed on a
/// surface already looked at) comes back unreviewed.
@MainActor
final class ReviewGalleryReviewed: ObservableObject {
    static let defaultsKey = "reviewGallery.reviewed"

    private let defaults: UserDefaults
    @Published private(set) var stamps: [String: String]

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        stamps = defaults.dictionary(forKey: Self.defaultsKey) as? [String: String] ?? [:]
    }

    static func stamp(_ commits: [String]) -> String { commits.joined(separator: "+") }

    func isReviewed(id: String, commits: [String]) -> Bool {
        stamps[id] == Self.stamp(commits)
    }

    func isReviewed(_ entry: ReviewGalleryEntry) -> Bool {
        isReviewed(id: entry.id, commits: entry.commits)
    }

    func setReviewed(_ reviewed: Bool, id: String, commits: [String]) {
        stamps[id] = reviewed ? Self.stamp(commits) : nil
        defaults.set(stamps, forKey: Self.defaultsKey)
    }
}

// MARK: - Registry

@MainActor
enum ReviewGalleryRegistry {

    static let entries: [ReviewGalleryEntry] = gallery + inTheApp

    // MARK: Gallery entries

    private static let gallery: [ReviewGalleryEntry] = [
        ReviewGalleryEntry(
            id: "M14",
            title: "Couldn’t start Bristlenose",
            what: "The start-timeout failure reads \"Bristlenose didn't finish starting within 90 seconds.\", and after a Retry that fails too the primary button becomes \"Send Feedback…\".",
            commits: ["f7048124", "4d8053c9"],
            files: ["BootView.swift", "ServeManager.swift", "ServeStartPolicy.swift"],
            section: .panesAndSheets,
            landed: "2026-10-22",
            states: bootStates.map { row in
                ReviewGalleryState(name: row.name) { ctx in boot(row, ctx) }
            }
        ),
        ReviewGalleryEntry(
            id: "M17",
            title: "Re-analyse can’t count your edits",
            what: "When the study's database can't be read, Re-analyse… shows its sheet with \"Bristlenose couldn't count your stars, tags and edits — re-analysing may discard them.\" instead of running unasked.",
            commits: ["2de22925"],
            files: ["ReAnalyseConfirmSheet.swift", "CurationCountsReader.swift"],
            section: .panesAndSheets,
            landed: "2026-10-21",
            states: [
                ReviewGalleryState(name: "Unreadable") { ctx in
                    reAnalyse(counts: nil, label: "counts = nil", ctx)
                },
                ReviewGalleryState(name: "Counted") { ctx in
                    reAnalyse(counts: CurationCounts(editedQuotes: 12, tags: 34, starredQuotes: 7,
                                                     renamedSpeakers: 3, namedThemes: 2),
                              label: "counts = 12 edited · 34 tags · 7 stars · 3 speakers · 2 themes", ctx)
                },
            ]
        ),
        ReviewGalleryEntry(
            id: "M18-B08-B06",
            title: "Diagnostic popover: set aside, no provider, report crash",
            what: "A second download of the same transcript is listed \"A second copy of this session's transcript — the other one was used.\"; with no AI provider the popover says \"No AI provider is set up yet.\" with Set Up Provider… in Show Log's place; a whole-report crash says your analysis is safe, with an error · route caption.",
            commits: ["66e94555", "848a83cb", "bf7ee8c6"],
            files: ["ProjectDiagnosticPopover.swift", "PipelineSummary.swift", "ReportCrash.swift"],
            section: .popovers,
            landed: "2026-10-21",
            states: [
                ReviewGalleryState(name: "Duplicate transcript set aside") { _ in
                    popover(state: .completedPartial(summary: duplicateTranscriptSummary),
                            label: ".completedPartial · ingest: duplicate_transcript")
                },
                ReviewGalleryState(name: "Provider not set up") { _ in
                    popover(state: .failed(.keyed("desktop.pipeline.failure.providerNotSetUpGeneric"),
                                           category: .providerNotSetUp),
                            label: ".failed · .providerNotSetUp")
                },
                ReviewGalleryState(name: "Report couldn’t be shown") { _ in
                    popover(state: .idle, crash: sampleCrash,
                            label: ".idle + ReportCrash · /report/quotes")
                },
            ]
        ),
        ReviewGalleryEntry(
            id: "sidebar-row-states",
            title: "Row states (new since 20 Oct)",
            what: "The real sidebar cells (SidebarOutlineController), each fed a fake study: provider not set up, project file damaged, Exporting…, the speech-model download and the spinner after it with no timing history, a report that couldn't be shown, nothing analysable, and a missing folder. Click a glyph to open its popover.",
            commits: ["66e94555", "7645dd6e", "7d048c3c", "7e43a5d0", "848a83cb", "bbf75243", "c06adea0", "ce125ffc", "d7f549dd"],
            files: ["ProjectSidebarOutline.swift", "ProjectSubtitle.swift", "SidebarSubtitleText.swift", "RunProgressMath.swift"],
            section: .sidebarRows,
            landed: "2026-10-22",
            states: [
                ReviewGalleryState(name: "Eight studies") { ctx in
                    let fixture = ReviewGallerySidebarFixture()
                    let host = LabOutlineHost(
                        index: fixture.index, i18n: ctx.i18n, roots: fixture.roots,
                        selection: .constant([]), activeTab: nil,
                        floats: false, scrolls: false,
                        onActivateLens: { _ in }, onContentHeight: nil,
                        onController: { _ in },
                        configure: { fixture.configure($0) }
                    )
                    return .view(AnyView(host.frame(width: 280, height: fixture.height)),
                                 label: "SidebarOutlineController · \(fixture.rows.count) fixture studies")
                },
            ]
        ),
    ]

    // MARK: In the app

    /// The changes from the 20–22 Oct review list that are seen in the real
    /// app rather than faked here (`look` and `seed`): the recipe, and a door
    /// where the app has one. CLI-only changes are left out — nothing in the
    /// app shows them.
    private static let inTheApp: [ReviewGalleryEntry] = [
        navigation(id: "B02", title: "Show in folder opens Finder (Mac)",
                   what: "Show in folder on a finished clips or screens chip now opens Finder at the export in the Mac app.",
                   commits: ["a398994e"],
                   landed: "2026-10-20",
                   recipe: "Mac app, project-ikea: Quotes ▸ Extract Clips (or File ▸ Export Screens), press Show in folder on the finished chip.",
                   open: nil),
        navigation(id: "M01", title: "View ▸ Reload Report (⌘R)",
                   what: "New View ▸ Reload Report (⌘R, arrow.clockwise), dimmed while text is being edited, plus Reload Report on the report's right-click menu.",
                   commits: ["576f7287"],
                   landed: "2026-10-21",
                   recipe: "Open project-ikea; View menu; right-click in the report; click into a quote edit and check it dims.",
                   open: nil),
        navigation(id: "M02", title: "Send Feedback sheet",
                   what: "Send Feedback opens exactly one sheet in the window that asked, with Cancel/Send drawn while it loads (Send dimmed, Esc works), no \"Opened by:\" caption, and a Cancel mid-send leaves no later toast.",
                   commits: ["15a80c71", "178b7dce", "02a57cc8", "25b9d249"],
                   landed: "2026-10-21",
                   recipe: "Help ▸ Send Feedback on project-ikea and on a failed-run status page; Esc while it loads. Cancel-mid-send needs a slow network (skip).",
                   open: nil),
        navigation(id: "M03", title: "Export Report: Exporting…, one panel, Anonymise once",
                   what: "The row reads \"Exporting…\" from the press until the save panel; a second press neither opens a second panel nor leaves \"Exporting…\" stuck; ticking Anonymise saves once; a server error shows \"The export could not be saved.\" instead of saving the error.",
                   commits: ["bec02487", "18a1c3f4", "ce125ffc", "c06adea0"],
                   landed: "2026-10-22",
                   recipe: "project-ikea: ⇧⌘E, watch the sidebar subtitle; press ⇧⌘E twice fast; tick Anonymise and Save. (Server-error alert: hands — Ctrl-C an External Server serve, then export.)",
                   open: nil),
        navigation(id: "M04", title: "LLM settings restart only on a real change",
                   what: "Dragging the concurrency slider or typing Azure fields restarts the report once on release/Return/leave, not per step; the show/hide eye no longer commits a half-typed key.",
                   commits: ["8f3648e7", "b9be38e3"],
                   landed: "2026-10-20",
                   recipe: "With project-ikea open: Settings ▸ LLM Provider, drag concurrency and watch the report not reload until release; type in an Azure field; click the eye mid-typing (don't save a real key).",
                   open: { SettingsWindow.shared.show(pane: .llm) }),
        navigation(id: "M05", title: "Settings ▸ Transcription: Transcribe with + Whisper row",
                   what: "On macOS 26 Settings ▸ Transcription shows \"Transcribe with\" and an always-present Whisper status row with Download Now / Stop; backend/model pickers move behind Diagnostics.",
                   commits: ["fc2fea73", "2859bbaa"],
                   landed: "2026-10-22",
                   recipe: "Settings ▸ Transcription (toggle Diagnostics menu pref to see the pickers move).",
                   open: { SettingsWindow.shared.show(pane: .transcription) }),
        navigation(id: "M06", title: "Sidebar drop and Add Files affordances",
                   what: "A drag of files a study can't take is refused (no +), Add Files offers only accepted types and greys .md, a drop on an already-listed study flashes its row and scrolls it into view, the empty Drop-a-folder pane selects the existing study, and a new study's icon stays while its name is typed.",
                   commits: ["5fdafdd2", "2bb7328e", "f00bfd0b"],
                   landed: "2026-10-20",
                   recipe: "Drag a .pdf onto a study; File ▸ Add Files…; drop trial-runs/project-ikea again on the sidebar and on the empty pane; ⌘N and type a name.",
                   open: nil),
        navigation(id: "M07", title: "Menus: Archive gone, Re-analyse lit, Miro dims with no server",
                   what: "Project ▸ Archive and Folder ▸ Archive are gone; Project ▸ Re-analyse lights after a first analysis; Send to Miro / Send to FigJam dim when the window's study has no running report server.",
                   commits: ["22ca42ed", "417e1645"],
                   landed: "2026-10-21",
                   recipe: "Project and Folder menus + right-click a folder; deselect every study (Welcome) and open the Quotes menu.",
                   open: nil),
        navigation(id: "M08", title: "Stopped/failed study offers Analyse",
                   what: "A study whose run stopped or failed offers Analyse (resume) as well as Re-analyse….",
                   commits: ["8c06f7f3"],
                   landed: "2026-10-20",
                   recipe: "Select project-ikea ▸ Diagnostics ▸ Diagnostic fixtures ▸ selected project ▸ stopped (then run_failed_abandoned); check context menu, Project menu, toolbar.",
                   open: nil),
        navigation(id: "M09", title: "Failed/unreachable study refuses files",
                   what: "A failed or unreachable study no longer highlights or accepts a Finder drop, and File ▸ Add Files… is dimmed for it.",
                   commits: ["da351490", "dd0bd498"],
                   landed: "2026-10-21",
                   recipe: "Select a study ▸ Diagnostics ▸ Diagnostic fixtures ▸ selected project ▸ run_failed_abandoned; drag a recording over its row; open File menu. (Unreachable: unplug a drive-backed study — hands.)",
                   open: nil),
        navigation(id: "M10", title: "Accounts: parked platform still-stored sentence",
                   what: "A parked platform's row in Settings ▸ Accounts uses the fuller \"still stored\" sentence whenever a sign-in key is stored, even with no readable address.",
                   commits: ["8a072d88"],
                   landed: "2026-10-21",
                   recipe: "`defaults write app.bristlenose BristlenoseCloudImportZoom -bool NO`, Diagnostics ▸ Cloud Import ▸ Store a Test Zoom Sign-In, open Settings ▸ Accounts; Forget afterwards. (Fixture has an address, so the no-address variant isn't reached.)",
                   open: { SettingsWindow.shared.show(pane: .accounts) }),
        navigation(id: "B01", title: "Activity chips survive a reload",
                   what: "Reloading mid-AutoCode or mid clips/screens export puts the chip back (still polling, or with its Done/failed outcome and View Report/Reveal); a dismissed chip stays gone; a restored chip's View Report opens the Codebook review; Cancel on an older export just removes that chip.",
                   commits: ["0a73df39", "9a8fbe0d", "96357736", "e6e64199"],
                   landed: "2026-10-22",
                   recipe: "Start Export clips (or AutoCode) on project-ikea, press ⌘R (Mac: View ▸ Reload Report) mid-job and again after it finishes; dismiss one and reload. View Report: reload before visiting Codebook.",
                   open: nil),
        navigation(id: "B03", title: "Unmeasured session length reads —",
                   what: "A session whose length was never measured shows an em dash (—) instead of \"0m\" in the Mac sessions popover, cloud import list and dashboard session rows.",
                   commits: ["6b419ad5"],
                   landed: "2026-10-21",
                   recipe: "Diagnostics ▸ Cloud Import ▸ Google Meet ▸ Organised by Someone Else (rows with nil duration). Popover/dashboard halves need a study with an unmeasured session — analyse a copy of trial-runs/folder-of-horrors or use a sidebar/dashboard gallery.",
                   open: nil),
        navigation(id: "W01", title: "Project tab: whole session row opens transcript",
                   what: "On the Project tab, a click anywhere on a session row (not only the #N link) opens its transcript.",
                   commits: ["237d4dd1"],
                   landed: "2026-10-20",
                   recipe: "Report ▸ Project tab on project-ikea; click a session row away from #N.",
                   open: nil),
        navigation(id: "W02", title: "Quote edit kept after bracket drag-and-return",
                   what: "A typed quote edit whose crop bracket is dragged away and back is kept instead of silently discarded.",
                   commits: ["14405307"],
                   landed: "2026-10-20",
                   recipe: "Quotes lens: edit a quote's text, drag a crop bracket out and back, click away; the edit stays.",
                   open: nil),
        navigation(id: "W03", title: "Tag group eye stays hidden",
                   what: "Clicking a tag group's eye to hide it no longer flips back when the sidebar remounts or a slow read lands.",
                   commits: ["e9d4ecdf"],
                   landed: "2026-10-20",
                   recipe: "Quotes ▸ tag sidebar: hide a group with its eye right after opening the report / switching lens; it stays hidden.",
                   open: nil),
        navigation(id: "W04", title: "Tag sidebar: no wall of zeros",
                   what: "Tag rows show the accepted count in full ink, the pending-proposal count in muted ink, or nothing; a group's total row is hidden at zero.",
                   commits: ["a9b4a976"],
                   landed: "2026-10-20",
                   recipe: "Quotes ▸ tag sidebar on a study with a framework codebook after AutoCode (project-ikea if already coded; else Codebook ▸ install a framework).",
                   open: nil),
        navigation(id: "W05", title: "AutoCode proposals appear without reload",
                   what: "When an AutoCode run finishes its proposals appear on quotes (Quotes, tag sidebar, Discussion, Screens) with no reload.",
                   commits: ["de6b774b"],
                   landed: "2026-10-20",
                   recipe: "Codebook ▸ install a framework (small LLM cost), stay on Quotes until the chip says Coded.",
                   open: nil),
        navigation(id: "W06", title: "Reinstalled codebook gets its own chip",
                   what: "Reinstalling a codebook shows a fresh AutoCode chip instead of reusing the previous run's Done chip.",
                   commits: ["5aec70b9"],
                   landed: "2026-10-20",
                   recipe: "Codebook: uninstall then reinstall a framework while its last chip still reads Done.",
                   open: nil),
        navigation(id: "W07", title: "Exported report: no delete in transcript margin",
                   what: "An exported HTML report's transcript margin no longer offers delete.",
                   commits: ["8bce5ffe"],
                   landed: "2026-10-20",
                   recipe: "Export HTML (toolbar / File ▸ Export Report…), open the file, open a transcript, hover the margin.",
                   open: nil),
        navigation(id: "W08", title: "Undo only records real changes",
                   what: "Clicking into a quote and leaving untouched adds no Undo entry; a spacing-only quote or heading edit is not an edit; an undone removal of an accepted AutoCode tag comes back styled as AutoCode; a failed save leaves no dead Undo.",
                   commits: ["a77f8ee9", "07a42179", "128964db"],
                   landed: "2026-10-22",
                   recipe: "Quotes: click into a quote, switch lens, check Edit ▸ Undo; add only spaces to a section heading + Return; remove an accepted AutoCode tag then ⌘Z. (Failed-save half: see W17 recipe.)",
                   open: nil),
        navigation(id: "W09", title: "Transcript for a session that's gone",
                   what: "A transcript URL for a session the report no longer has reads \"This session is no longer in the report.\" with an All sessions link and no Retry; a missing project instead shows the ordinary lens sentence with Retry.",
                   commits: ["833c246d", "0ba1acd7"],
                   landed: "2026-10-22",
                   recipe: "In a browser on serve: open /report/sessions/s999 (bogus id → 404). The missing-project variant has no cheap route; skip or use the request-fault gallery.",
                   open: nil),
    ]

    private static func navigation(id: String, title: String, what: String, commits: [String],
                                   landed: String, recipe: String,
                                   open: (@MainActor () -> Void)?) -> ReviewGalleryEntry {
        ReviewGalleryEntry(
            id: id, title: title, what: what, commits: commits, files: [],
            section: .inTheApp, landed: landed,
            states: [ReviewGalleryState(name: "In the app") { _ in
                .navigation(recipe: recipe, open: open)
            }]
        )
    }

    // MARK: Builders

    /// The tail `handleTermination` would put in `details`: the last five lines.
    private static let bootLines = [
        "[bristlenose] serve starting (desktop-hosted)",
        "Traceback (most recent call last):",
        "  File \"bristlenose/server/app.py\", line 212, in create_app",
        "ModuleNotFoundError: No module named 'sqladmin'",
        "sidecar_exit reason=uncaught_exception uptime_sec=0.2 exc=ModuleNotFoundError",
    ]
    private static var bootDetails: String { bootLines.suffix(5).joined(separator: "\n") }

    /// The boot pane's states: the sentence `ServeManager` would build, and
    /// whether a Retry has already failed (which turns Retry into Send
    /// Feedback…). A table so `ReviewGalleryRegistryTests` can check each
    /// state's primary button against the manager the pane reads.
    struct BootState {
        let name: String
        let message: FailureMessage
        let retried: Bool
        let label: String
    }

    static let bootStates: [BootState] = [
        BootState(name: "First failure",
                  message: .keyed("desktop.boot.failure.exitedBeforeReady",
                                  vars: ["status": "1", "details": bootDetails]),
                  retried: false, label: "exitedBeforeReady · code 1"),
        BootState(name: "After a failed retry",
                  message: .keyed("desktop.boot.failure.exitedBeforeReady",
                                  vars: ["status": "1", "details": bootDetails]),
                  retried: true, label: "exitedBeforeReady · code 1"),
        BootState(name: "90 s timeout",
                  message: .keyed("desktop.boot.failure.startTimeout"),
                  retried: false, label: "startTimeout"),
        BootState(name: "Sidecar missing",
                  message: SidecarResolveError.bundledSidecarMissing(
                      expectedPath: "/Applications/Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar"
                  ).failureMessage,
                  retried: false, label: "sidecarMissing"),
    ]

    /// A fleet of one manager that can touch nothing of the app's: external
    /// mode, so it can never spawn a sidecar; its own `NotificationCenter`, so
    /// the app's Agent Access flips and Quit never reach it; and no handshake
    /// hook, so nothing it does reconciles the real MCP handshake file. (With
    /// `.default` and the fleet's hook, a flip anywhere in the app ran this
    /// fleet's `syncHandshake`, whose only manager has no path, and removed
    /// the live handshake.)
    static func bootFixture(_ row: BootState) -> (fleet: ServeFleet, manager: ServeManager, project: UUID) {
        let project = UUID()
        let fleet = ServeFleet(makeManager: {
            ServeManager(resolvedMode: .success(.external(port: 1)),
                         notificationCenter: NotificationCenter())
        })
        let manager = fleet.manager(for: project)
        manager.onHandshakeDirty = nil
        manager.debugAppendOutput(bootLines)
        if row.retried { manager.debugMarkStartedByRetry() }
        return (fleet, manager, project)
    }

    private static func boot(_ row: BootState, _ ctx: ReviewGalleryContext) -> ReviewGallerySpecimen {
        let fixture = bootFixture(row)
        let view = BootView(
            phase: .failed(message: row.message,
                           retry: { ctx.log("Retry pressed") },
                           sendFeedback: { ctx.log("Send Feedback… pressed (the real sheet is not opened)") }),
            project: fixture.project
        )
        .environmentObject(fixture.fleet)
        .frame(width: 520, height: 360)
        return .view(AnyView(view),
                     label: "BootView · .failed · \(row.label) · startedByRetry = \(row.retried) · 520 × 360")
    }

    private static func reAnalyse(counts: CurationCounts?, label: String,
                                  _ ctx: ReviewGalleryContext) -> ReviewGallerySpecimen {
        let sheet = ReAnalyseConfirmSheet(
            projectName: "Checkout v2", sessionCount: 8, counts: counts,
            onCancel: { ctx.log("Cancel pressed") },
            onConfirm: { ctx.log("Re-analyse pressed (nothing runs)") }
        )
        return .view(AnyView(sheet), label: "ReAnalyseConfirmSheet · \(label)")
    }

    private static func popover(state: PipelineState, crash: ReportCrash? = nil,
                                label: String) -> ReviewGallerySpecimen {
        // A path with no log file, so the header shows no Show Log button that
        // would open nothing.
        let project = Project(id: UUID(), name: "Checkout v2",
                              path: "/private/tmp/bn-review-gallery-no-such-study")
        let view = ProjectDiagnosticPopover(project: project, state: state,
                                            liveData: PipelineLiveData(), reportCrash: crash)
        return .view(AnyView(view), label: "ProjectDiagnosticPopover · \(label)")
    }

    static let sampleCrash = ReportCrash(
        route: "/report/quotes",
        message: "TypeError: Cannot read properties of undefined (reading 'quotes')",
        frames: ["QuotesLens@http://127.0.0.1/assets/index.js:1:4821",
                 "renderWithHooks@http://127.0.0.1/assets/index.js:1:90112"]
    )

    /// What a run writes when `transcript (1).vtt` is the same transcript as
    /// `transcript.vtt` (bf7ee8c6): the copy is set aside at ingest.
    static let duplicateTranscriptSummary = PipelineSummary(
        ingest: StageOutcome(
            attempted: 9, succeeded: 8, durationMs: 140,
            failed: [SessionFailure(
                sourceFile: "transcript (1).vtt",
                cause: Cause(category: .unusableInput,
                             message: "A second copy of this session's transcript — the other one was used.",
                             reason: "duplicate_transcript")
            )]
        )
    )
}

// MARK: - Sidebar fixture

/// Eight studies on a temp `ProjectIndex`, each in one of the row states the
/// 20–22 Oct changes added, driven through the runner and live data the
/// controller reads. Shared with `ReviewGalleryRegistryTests`, which reads the
/// cells this produces.
///
/// The runner is a throwaway: its own `NotificationCenter` (so Quit,
/// activation and Whisper-ready never reach it), a launcher that refuses (so
/// nothing can spawn), a sleep assertion that asserts nothing (two rows are
/// `.running`, and a fixture must not keep the Mac awake), and states set with
/// `_debugSetState`. The index has no folder watchers, and the temp tree goes
/// with the fixture.
///
/// **No Stop.** A `.running` row offers its hover × only when the runner owns
/// the run (`canStop`); these were never spawned, so the ring shows and the ×
/// does not. The glyph popovers are the real ones and do open.
@MainActor
final class ReviewGallerySidebarFixture {
    struct Row {
        let id: UUID
        let name: String
        /// What the row demonstrates, and the subtitle it should read.
        let what: String
        let subtitleKey: String
    }

    let index: ProjectIndex
    let runner: PipelineRunner
    let liveData = PipelineLiveData()
    /// Removed when the fixture goes, with everything the index wrote.
    let root: URL
    private let assertions = AssertionCount()
    private(set) var rows: [Row] = []
    private(set) var crash: (projectID: UUID, crash: ReportCrash)?
    private(set) var exportingID: UUID?

    private struct GalleryRefusesToLaunch: Error {}

    /// Counts the runner's sleep assertions, which assert nothing: a fixture's
    /// `.running` rows are not runs, so they must not hold idle sleep off.
    private final class AssertionCount { var held = 0 }

    /// How many idle-sleep assertions the runner holds — through the fixture's
    /// no-op, never `ProcessInfo`. One while any row is `.running`.
    var sleepAssertionsHeld: Int { assertions.held }

    init() {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("ReviewGallery-\(UUID().uuidString)")
        self.root = root
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        // No folder watchers: each would register an NSFilePresenter on a
        // temp folder, and none is released until the index is.
        index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"), watcherCap: 0)
        let assertions = self.assertions
        runner = PipelineRunner(
            notificationCenter: NotificationCenter(),
            sendSignal: { _, _ in 0 },
            hasConsent: { false },
            keyReadiness: { .missing(provider: "anthropic") },
            launcher: { _, _, _ in throw GalleryRefusesToLaunch() },
            manifestRead: { _ in .idle },
            sleepAssertion: RunSleepAssertion(
                begin: { _, _ in assertions.held += 1; return NSObject() },
                end: { _ in assertions.held -= 1 }
            )
        )

        enum Kind { case provider, damaged, exporting, downloading, afterDownload, crash, nothing, missing }
        let plan: [(String, Kind, String, String)] = [
            ("Acme onboarding", .provider, "Provider not set up — the row says the run failed; the popover names the cause",
             "desktop.pipeline.diagnostic.header.failed"),
            ("Checkout v2", .damaged, "Project file damaged (.unreachable(.damaged))",
             UnreachableReason.damaged.localeKey),
            ("Pricing interviews", .exporting, "Exporting… (exportingReportProjectID)",
             "common.export.exporting"),
            ("Diabetes diary", .downloading, "Downloading speech model, ring at 412 MB of 1.6 GB",
             "desktop.chrome.pipeline.stage.download"),
            ("Field visits", .afterDownload, "After the download, no timing history: a spinner, not a frozen ring",
             "desktop.chrome.pipeline.stage.transcribe"),
            ("Kitchen study", .crash, "This report couldn’t be shown (reportCrash)",
             "desktop.pipeline.diagnostic.header.reportError"),
            ("Empty folder", .nothing, "No analysable interviews — the row says the run failed; the popover names the cause",
             "desktop.pipeline.diagnostic.header.failed"),
            ("Old shoot", .missing, "Missing (a folder that was never there)",
             "desktop.availability.missing"),
        ]

        // `addProject` puts each new study first, so add in reverse.
        var made: [Row] = []
        for (name, kind, what, key) in plan.reversed() {
            let folder = root.appendingPathComponent(name)
            if kind != .missing {
                try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            }
            let project = index.addProject(name: name, path: folder.path)
            index.consumeIconReveal(project.id)
            let id = project.id
            switch kind {
            case .provider:
                runner._debugSetState(.failed(.keyed("desktop.pipeline.failure.providerNotSetUpGeneric"),
                                              category: .providerNotSetUp), for: id)
            case .damaged:
                runner._debugSetState(.unreachable(reason: .damaged), for: id)
            case .exporting:
                runner._debugSetState(.ready(Date().addingTimeInterval(-3_600)), for: id)
                exportingID = id
            case .downloading:
                runner._debugSetState(.running, for: id)
                liveData.setProgress(Self.download(fraction: 412.0 / 1_614.0), for: id)
            case .afterDownload:
                runner._debugSetState(.running, for: id)
                liveData.setProgress(Self.afterDownloadWithNoHistory(), for: id)
            case .crash:
                runner._debugSetState(.ready(Date().addingTimeInterval(-7_200)), for: id)
                crash = (projectID: id, crash: ReviewGalleryRegistry.sampleCrash)
            case .nothing:
                runner._debugSetState(.failed(FailureMessage.failure(for: .missingInput),
                                              category: .missingInput), for: id)
            case .missing:
                break
            }
            made.append(Row(id: id, name: name, what: what, subtitleKey: key))
        }
        rows = made.reversed()
    }

    deinit {
        try? FileManager.default.removeItem(at: root)
    }

    var roots: [OutlineNode] {
        OutlineTree.build(lenses: [], projects: index.projects, folders: index.folders)
    }

    /// Every row is two lines, plus the group heading.
    var height: CGFloat {
        CGFloat(rows.count) * ProjectCellSpec.rowHeight(twoLine: true) + 40
    }

    /// Hands the controller what it reads. It holds these weakly; the fixture
    /// (captured by the host's `configure`) keeps them alive.
    func configure(_ controller: SidebarOutlineController) {
        controller.pipelineRunner = runner
        controller.liveData = liveData
        controller.reportCrash = crash
        controller.exportingReportProjectID = exportingID
    }

    /// A first run part-way through the speech-model download, as
    /// `RunProgressMath.apply` leaves it: the ring is the bytes received.
    private static func download(fraction: Double) -> PipelineProgress {
        let start = Date().addingTimeInterval(-300)
        return RunProgressMath.apply(
            stage: RunProgressMath.downloadStage, sessionsComplete: nil, sessionsTotal: nil,
            stageFraction: fraction, etaRemainingSeconds: nil, predictedTotalSeconds: nil,
            to: PipelineProgress(startedAt: start), startedAt: start, now: Date()
        )
    }

    /// The download finished and transcription began on a Mac with no timing
    /// history: no estimate, no measured fraction, so the spinner.
    private static func afterDownloadWithNoHistory() -> PipelineProgress {
        let start = Date().addingTimeInterval(-900)
        var p = PipelineProgress(startedAt: start)
        p = RunProgressMath.apply(
            stage: RunProgressMath.downloadStage, sessionsComplete: nil, sessionsTotal: nil,
            stageFraction: 1, etaRemainingSeconds: nil, predictedTotalSeconds: nil,
            to: p, startedAt: start, now: start.addingTimeInterval(800)
        )
        return RunProgressMath.apply(
            stage: "transcribe", sessionsComplete: nil, sessionsTotal: nil,
            stageFraction: nil, etaRemainingSeconds: nil, predictedTotalSeconds: nil,
            to: p, startedAt: start, now: start.addingTimeInterval(801)
        )
    }
}
#endif
