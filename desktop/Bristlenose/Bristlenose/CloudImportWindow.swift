import SwiftUI

// The import window. Renders `CloudImportStore`; decides nothing itself.
//
// Shape comes from docs/mockups/cloud-import-states.html — the Teams window —
// with the Google deviations marked `DEVIATION` inline and argued in
// docs/design-cloud-import.md §3.
//
// Native primitives, per desktop/CLAUDE.md § Native primitives first:
//   • `NSOutlineView`          — via `CloudImportOutlineView`. HIG: "use an
//                                outline view instead of a table view to
//                                present hierarchical data". A meeting can
//                                hold more than one recording, and only an
//                                outline says so. It also brings the floating
//                                day header, which SwiftUI has no equivalent
//                                for at all.
//   • `ContentUnavailableView` — the system empty state; `.search` quotes the
//                                term back on its own.
//   • `Window` scene           — not a sheet. A sheet is window-modal, so it
//                                would hide the sidebar-row progress behind
//                                itself and destroy the per-row outcomes that
//                                recovery depends on (§9). Image Capture is the
//                                system analogue and it is a window.
//
// The one place selection semantics needed a decision: the mockup says "ticks
// are intent, highlight is keyboard focus". The outline's single selection IS a
// focus model — it draws the row, moves on arrows, supports type-select — so it
// is taken as-is rather than hand-rolled. Ticks stay a separate `Set`.

struct CloudImportWindow: View {
    @ObservedObject var store: CloudImportStore
    @EnvironmentObject var projectIndex: ProjectIndex
    /// Read for one thing only: which project the researcher was looking at
    /// when they invoked Import.
    @EnvironmentObject private var coordinator: CloudImportCoordinator
    @EnvironmentObject private var i18n: I18n
    /// Supplies every vendor-specific string. A `switch` on platform inside a
    /// view body is the smell this replaces.
    let platform: CloudPlatform

    /// Where the recordings go. Pre-selected by how the window was opened (§9),
    /// never silently defaulted to a project — a wrong default here writes
    /// gigabytes into the wrong study.
    ///
    /// `.newProject` when the window was opened with nothing selected, which is
    /// a route rather than a dead end: the researcher on the welcome screen can
    /// name and place a study from inside this popup.
    @State private var destination: CloudImportDestinations.Choice = .newProject

    var body: some View {
        VStack(spacing: 0) {
            content
            Divider()
            footer
        }
        .frame(minWidth: 760, minHeight: 420)
        .navigationTitle(platform.windowTitle(i18n))
        .navigationSubtitle(subtitle)
        .searchable(text: $store.filterText, placement: .toolbar, prompt: i18n.t("desktop.cloudImport.filter"))
        .toolbar { windowScopePicker }
        // Keyed on the **store instance**, not on appear. There is one import
        // window globally (§9), and re-opening it builds a fresh store behind
        // a view SwiftUI is free to reuse — in which case a plain `.task`
        // never fires again and the new store is left un-scanned and, on the
        // same path, un-listed. The identity of the store is the thing that
        // actually changed, so it is what this watches.
        .task(id: ObjectIdentifier(store)) {
            // Re-scanned here as well as on a destination change, because
            // re-opening on the *same* project moves nothing the `.onChange`
            // below would notice — while the folder itself may well have
            // gained files in the days between visits, which is exactly the
            // routine this serves.
            store.setDestination(destinationFolder(for: destination))
            if store.accountEmail != nil, store.listing == nil { await store.load() }
        }
        // Follows how the window was opened, including a re-open from a
        // different project while it is already on screen — one window globally
        // (§9), so the destination has to keep up with the invocation rather
        // than be fixed at first mount. Fires on appear and on change; a nil
        // preselection resolves to `.newProject`, which is the same value the
        // state starts at, so opening from the welcome screen never triggers
        // the panel by itself.
        .task(id: coordinator.preselectedProjectID) {
            destination = CloudImportDestinations.initialChoice(
                preselected: coordinator.preselectedProjectID, in: destinationGroups)
        }
        // Choosing "New Project…" opens its panel there and then, the way
        // "Other…" behaves in a native popup — not silently at Import, where a
        // save sheet would arrive after the researcher thought they were done
        // deciding.
        .onChange(of: destination) { previous, next in
            // Ask the new folder what it already holds, before anything else —
            // the answer decides which rows can still be ticked, and a wrong
            // one withholds a recording rather than merely wasting a fetch.
            store.setDestination(destinationFolder(for: next))
            guard next == .newProject, previous != .newProject else { return }
            makeNewProject(revertingTo: previous)
        }
        .onChange(of: store.windowDays) { _, _ in
            // A menu selection is a deliberate act, so one re-list per change
            // needs no debounce. Guarded on being signed in because the picker
            // is reachable before the first sign-in completes.
            guard store.accountEmail != nil else { return }
            Task { await store.load() }
        }
    }

    /// How far back to look.
    ///
    /// **In the toolbar, because it is scope** — the Mail-filter and
    /// Finder-arrangement slot — and not in the subtitle, which is where it
    /// used to be stated and could not be changed. The control replaces a
    /// "Look back 60 days" button that lived *inside the empty state*, so the
    /// only way to widen the window was to find nothing first: a researcher who
    /// got two results and wanted a third from six weeks ago had no affordance
    /// at all. That button also doubled unboundedly — 30, 60, 120, 240 — which
    /// on Meet is a calendar walk of two calls per event.
    ///
    /// **Hidden at one choice**, which is not a nicety: Meet's conference
    /// records expire around thirty days while the Drive file lives on, so a
    /// longer window there would list weeks of meetings whose recordings are
    /// real, downloadable, and reported "Not recorded". If `expireTime` on a
    /// live tenant confirms that ceiling, `.meet` shrinks to `[30]` in
    /// `CloudPlatform` and this control disappears by itself.
    @ToolbarContentBuilder
    private var windowScopePicker: some ToolbarContent {
        if platform.windowChoices.count > 1 {
            ToolbarItem(placement: .primaryAction) {
                Picker(i18n.t("desktop.cloudImport.scopeLabel"), selection: $store.windowDays) {
                    ForEach(platform.windowChoices, id: \.self) { days in
                        Text(i18n.plural("desktop.cloudImport.scopeChoice", count: days)).tag(days)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .help(i18n.t("desktop.cloudImport.scopeHelp"))
            }
        }
    }

    // MARK: - Body states

    @ViewBuilder
    private var content: some View {
        switch store.phase {
        case .signedOut:
            signedOutView

        case .signingIn:
            ProgressView().controlSize(.small)
                .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .loading:
            VStack(spacing: 10) {
                ProgressView().controlSize(.small)
                Text(i18n.plural("desktop.cloudImport.loading", count: store.windowDays))
                    .font(.callout).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .signInIncomplete:
            ContentUnavailableView {
                Label(i18n.t("desktop.cloudImport.signInIncompleteTitle"), systemImage: "person.crop.circle.badge.questionmark")
            } description: {
                Text(incompleteSignInDetail)
            } actions: {
                Button(i18n.t("desktop.cloudImport.tryAgain"), action: store.signIn)
            }

        case .failed(let message):
            ContentUnavailableView {
                Label(i18n.t("desktop.cloudImport.loadFailedTitle"), systemImage: "exclamationmark.triangle")
            } description: {
                Text(message)
            } actions: {
                Button(i18n.t("desktop.cloudImport.tryAgain")) { Task { await store.load() } }
            }

        case .loaded:
            loadedView
        }
    }

    /// State 1 — the resting state, and what most launches see. One line of what
    /// it does, one button, no billboard.
    private var signedOutView: some View {
        ContentUnavailableView {
            Label(i18n.t("desktop.cloudImport.signedOutTitle"), systemImage: "arrow.down.circle")
        } description: {
            // DEVIATION from the Teams copy. Microsoft mandates the noun "work
            // or school account"; Google has no equivalent requirement, and
            // saying "Google Account" would be wrong in the way that matters —
            // a personal Google Account signs in perfectly and can never hold a
            // recording. So the sentence names the capability, not the account
            // type, and the tier refusal is stated once the list is known
            // rather than guessed at up front.
            Text(signedOutDetail)
        } actions: {
            // The button string is Google's, not ours: their branding
            // guidelines specify "Sign in with Google" together with the
            // unaltered G mark, which ships as an official asset to drop in
            // rather than redraw. `googleMark` is a stand-in until it is.
            Button(action: store.signIn) {
                HStack(spacing: 8) {
                    VendorMark(platform: platform)
                    Text(platform.signInTitle)
                }
            }
            .controlSize(.large)
        }
    }

    /// Names both possibilities, because from here they are indistinguishable.
    ///
    /// The order is deliberate: the researcher's own action first (they know
    /// whether they closed the window), then the one they cannot see. Leading
    /// with the admin theory would read as blame-shifting to someone who simply
    /// changed their mind.
    private var incompleteSignInDetail: String {
        let key = platform.signInMayAwaitAdminApproval
            ? "desktop.cloudImport.signInIncompleteDetailAdmin"
            : "desktop.cloudImport.signInIncompleteDetail"
        return i18n.t(key, ["platform": platform.displayName])
    }

    /// One sentence naming the capability, not the account type.
    ///
    /// Microsoft's guidelines *require* the account noun beside the button —
    /// "work or school account", never "business" or "corporate" — because
    /// users need to recognise whether it applies to them. Google has no such
    /// requirement, and naming the account type there would actively mislead: a
    /// personal Google Account signs in perfectly and can never hold a
    /// recording, so the tier refusal belongs after the list, not before it.
    private var signedOutDetail: String {
        guard let noun = platform.accountNoun(i18n) else {
            return i18n.t("desktop.cloudImport.signedOutDetail")
        }
        return i18n.t("desktop.cloudImport.signedOutDetailWithAccount", ["noun": noun])
    }

    @ViewBuilder
    private var loadedView: some View {
        // `store.outline.isEmpty` rather than `store.visibleRows.isEmpty`: the
        // latter flattens the whole tree into a fresh array, and this body is
        // re-evaluated several times a second while a batch downloads.
        let isEmpty = store.outline.isEmpty

        if let refusal = store.blanketRefusal {
            // DEVIATION, and the most important one on this platform. Every row
            // is unfetchable for the same reason, so the window says it once
            // instead of drawing eleven dead ticks. The Teams design never
            // needed this: its equivalent failure (a personal account with no
            // /Recordings folder) returns an empty list, which is at least
            // legibly empty. Google returns a full, convincing calendar and no
            // media — a list that looks like it works.
            blanketRefusalView(refusal)
        } else if isEmpty && !store.filterText.isEmpty {
            // State 6. `.search` quotes the term back automatically.
            ContentUnavailableView.search(text: store.filterText)
        } else if isEmpty {
            // State 5.
            ContentUnavailableView {
                Label(i18n.plural("desktop.cloudImport.emptyTitle", count: store.windowDays),
                      systemImage: "calendar")
            } description: {
                Text(emptyWindowDetail)
            } actions: {
                // The next choice up, not a doubling — and absent when there
                // isn't one, so the empty state stops offering a window the
                // platform cannot serve. The re-list rides `onChange`, so this
                // only sets the value.
                if let wider = platform.windowChoices.first(where: { $0 > store.windowDays }) {
                    Button(i18n.plural("desktop.cloudImport.lookBack", count: wider)) {
                        store.windowDays = wider
                    }
                }
            }
        } else {
            CloudImportOutlineView(store: store, platform: platform, i18n: i18n)
        }
    }

    private func blanketRefusalView(_ refusal: ArtifactAvailability) -> some View {
        ContentUnavailableView {
            Label(blanketTitle(refusal), systemImage: blanketIcon(refusal))
        } description: {
            Text(blanketDetail(refusal))
        } actions: {
            if case .needsScope = refusal {
                // "Sign In Again", not "Grant Access": the button has to name
                // what actually happens, which is the full consent screen a
                // second time.
                Button(i18n.t("desktop.cloudImport.signInAgain")) { store.signIn() }
            }
        }
    }

    private func blanketTitle(_ refusal: ArtifactAvailability) -> String {
        switch refusal {
        case .notOnThisPlan:  return i18n.t("desktop.cloudImport.blanketNotOnThisPlanTitle")
        case .notRecorded:    return i18n.t("desktop.cloudImport.blanketNotRecordedTitle")
        case .needsScope:     return i18n.t("desktop.cloudImport.blanketNeedsScopeTitle")
        case .notOrganiser:   return i18n.t("desktop.cloudImport.blanketNotOrganiserTitle")
        case .notResolved:    return i18n.t("desktop.cloudImport.blanketNotResolvedTitle")
        case .unsupported:    return i18n.t("desktop.cloudImport.blanketUnsupportedTitle")
        case .available:      return ""
        }
    }

    private func blanketIcon(_ refusal: ArtifactAvailability) -> String {
        switch refusal {
        case .notOnThisPlan: return "person.crop.circle.badge.exclamationmark"
        case .needsScope:    return "lock"
        // Not an error glyph: nothing failed. A month with no recordings in it
        // is an ordinary month, and this state should read as an observation.
        case .notRecorded:   return "video.slash"
        // Also not an error: the recordings exist and are reachable, we just
        // can't say which is which. A puzzle, not a fault.
        case .notResolved:   return "questionmark.square.dashed"
        default:             return "questionmark.circle"
        }
    }

    private func blanketDetail(_ refusal: ArtifactAvailability) -> String {
        switch refusal {
        case .notOnThisPlan:
            // Names the meetings we CAN see, so the sentence reads as an
            // explanation rather than as a failure to find anything.
            let n = store.listing?.rows.count ?? 0
            return i18n.plural("desktop.cloudImport.blanketNotOnThisPlanDetail", count: n)
        case .notRecorded:
            // States the fact and stops. No remedy is offered because there
            // isn't one — the meetings are over, and a recording that was
            // never started cannot be recovered by anything the researcher
            // does here. Naming the count keeps it an observation about this
            // window rather than a verdict about the account.
            let count = store.listing?.rows.count ?? 0
            return i18n.plural("desktop.cloudImport.blanketNotRecordedDetail", count: count)
        case .needsScope:
            // The wording is careful, and the care is a research finding rather
            // than taste. Google does NOT support incremental authorisation for
            // installed apps — stated twice on its own native-app page — so
            // there is no way to ask for just the missing permission. Signing in
            // again re-presents the whole consent screen. Promising "only that
            // one permission" would be a small lie that the very next screen
            // contradicts, which is how a consent prompt teaches people to stop
            // reading consent prompts.
            return i18n.t("desktop.cloudImport.blanketNeedsScopeDetail")
        case .notOrganiser(let organiser):
            return organiser.map {
                i18n.t("desktop.cloudImport.blanketNotOrganiserDetail", ["organiser": $0])
            } ?? i18n.t("desktop.cloudImport.blanketNotOrganiserDetailUnnamed")
        case .notResolved:
            // Names the cause, because it is the one thing that makes the
            // remedy obvious: the room is reused, so the link alone can't say
            // which call this was. The recordings are still in Drive.
            return i18n.t("desktop.cloudImport.blanketNotResolvedDetail")
        case .unsupported, .available:
            return ""
        }
    }

    private var emptyWindowDetail: String {
        guard let a = store.listing?.arithmetic else { return "" }
        return i18n.plural("desktop.cloudImport.emptyDetail", count: a.eventsInWindow)
    }

    // MARK: - Footer

    private var footer: some View {
        HStack(spacing: 12) {
            arithmeticLine
            Spacer(minLength: 12)
            if store.phase == .loaded, store.blanketRefusal == nil, !(store.listing?.rows.isEmpty ?? true) {
                Text(i18n.t("desktop.cloudImport.destinationLabel")).font(.caption).foregroundStyle(.secondary)
                destinationPicker
                primaryButton
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
    }

    /// §6's first honest-batch requirement, and the only place in the design
    /// where a data-losing failure becomes visible. Permanently visible, never
    /// a disclosure.
    @ViewBuilder
    private var arithmeticLine: some View {
        if let terminus = store.terminus, !store.isFetching {
            HStack(spacing: 5) {
                Text(i18n.t("desktop.cloudImport.footerImported", ["count": String(terminus.imported)])).fontWeight(.semibold)
                if terminus.failed > 0 {
                    Text("·").foregroundStyle(.secondary)
                    Text(i18n.t("desktop.cloudImport.footerFailed", ["count": String(terminus.failed)])).foregroundStyle(.red).fontWeight(.semibold)
                }
            }
            .font(.callout)
        } else if let a = store.listing?.arithmetic {
            let counts = store.outline
            HStack(spacing: 5) {
                // Not "in window" — the window is already named in the toolbar
                // picker, and saying it twice on one screen is the same
                // redundancy §7 rules out for the timezone: state it once,
                // never on every row.
                //
                // The meetings count is what is **on screen**, so the sentence
                // is checkable by looking. It used to be `eventsInWindow` — the
                // researcher's whole diary, including every meeting with no
                // video call attached — which read as a join loss that wasn't
                // one. Real incompleteness has its own signal, below.
                Text(a.isExact
                     ? i18n.plural("desktop.cloudImport.footerMeetings", count: counts.meetings)
                     : i18n.plural("desktop.cloudImport.footerMeetingsAtLeast", count: counts.meetings))
                // Only when the two numbers differ. In the 90% case one meeting
                // made one recording, and a second noun saying the same number
                // twice is a sentence the reader has to check before
                // discarding.
                if counts.recordings != counts.meetings {
                    Text("·").foregroundStyle(.secondary)
                    Text(i18n.plural("desktop.cloudImport.footerRecordings", count: counts.recordings))
                }
                Text("·").foregroundStyle(.secondary)
                Text(i18n.t("desktop.cloudImport.footerFetchable", ["count": String(counts.fetchable)])).fontWeight(.semibold)
                // Suppressed while a filter is on. Every other number in this
                // sentence is measured over the filtered list; this one is
                // measured over the whole window, so filtering to "P05" read
                // "1 meeting · 1 you can fetch · 4 organised by someone else"
                // — one sentence quietly counting two different sets, on the
                // surface whose entire claim is that its arithmetic is
                // checkable by looking.
                if a.organisedByOthers > 0, store.filterText.isEmpty {
                    Text("·").foregroundStyle(.secondary)
                    Text(i18n.t("desktop.cloudImport.footerOrganisedByOthers",
                                ["count": String(a.organisedByOthers)]))
                        .foregroundStyle(.secondary)
                }
                // Shown only when a recording the researcher can *see* is one
                // they cannot fetch. Fetch 8 of 8 and there is no link — that
                // absence is the reassurance, and a permanent "learn about
                // permissions" would train people to ignore it by the third
                // visit.
                if counts.withholding {
                    Link(i18n.t("desktop.cloudImport.footerPermissionsLink"), destination: platform.permissionsDocURL)
                        .font(.caption)
                }
                // A capped paginator returns HTTP 200 with a partial page, and
                // every error check says fine. Saying so is the whole point.
                if case .pageCapHit = a.outcome {
                    Label(i18n.t("desktop.cloudImport.footerPartial"), systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                        .help(i18n.plural("desktop.cloudImport.footerPartialHelp", count: store.windowDays))
                }
            }
            .font(.callout)
            .foregroundStyle(.secondary)
        }
    }

    /// Projects that can actually receive a file.
    ///
    /// A project whose `path` is empty is an unlocated placeholder — the
    /// "Drag Interviews Here" state — and has no folder behind it. Offering one
    /// The popup's contents, in sidebar order, with folders as headings.
    /// Every judgement in here is `CloudImportDestinations`'; this is the read.
    private var destinationGroups: [CloudImportDestinations.Group] {
        CloudImportDestinations.groups(
            sidebar: projectIndex.sidebarItems,
            projectsInFolder: { projectIndex.projectsInFolder($0) })
    }

    /// The chosen project, when the choice is one. Nil while the popup still
    /// reads "New Project…" — which is a pending decision, not a destination.
    private var chosenProjectID: UUID? {
        if case .project(let id) = destination { return id }
        return nil
    }

    private var destinationPicker: some View {
        Picker("", selection: $destination) {
            // First, and separated: the one entry that isn't a place that
            // already exists. Choosing it opens the panel that makes one.
            Text(i18n.t("desktop.cloudImport.destinationNewProject"))
                .tag(CloudImportDestinations.Choice.newProject)
            Divider()
            ForEach(destinationGroups) { group in
                destinationGroup(group)
            }
        }
        .labelsHidden()
        .frame(maxWidth: 220)
    }

    /// A folder becomes a real menu **section header** — unselectable by
    /// construction, which is the point. A folder is not a place a recording
    /// can land, so it must not be clickable; `Section` is how AppKit says that
    /// and it needs no disabled-row of our own.
    @ViewBuilder
    private func destinationGroup(_ group: CloudImportDestinations.Group) -> some View {
        if let folderName = group.folderName {
            Section(folderName) { destinationRows(group.projects) }
        } else {
            // Root-level projects sit under no heading, exactly as in the
            // sidebar.
            destinationRows(group.projects)
        }
    }

    @ViewBuilder
    private func destinationRows(_ projects: [Project]) -> some View {
        ForEach(projects) { project in
            Text(project.name).tag(CloudImportDestinations.Choice.project(project.id))
        }
    }

    /// Name and place a new study, then select it.
    ///
    /// Cancelling must leave the previous selection alone — `present` returns
    /// nil for that, and `previous` is what we go back to. Without it the popup
    /// would sit on "New Project…" after a cancel, which reads as though the
    /// cancel had been ignored.
    private func makeNewProject(revertingTo previous: CloudImportDestinations.Choice,
                                then continuation: ((UUID) -> Void)? = nil) {
        NewProjectDestination.present(
            index: projectIndex,
            i18n: i18n,
            suggestedName: i18n.t("desktop.chrome.newProject"),
            message: i18n.t("desktop.cloudImport.newProjectSaveMessage")
        ) { created in
            guard let created else {
                destination = previous
                return
            }
            destination = .project(created)
            continuation?(created)
        }
    }

    @ViewBuilder
    private var primaryButton: some View {
        if store.isFetching {
            // Not prominent: HIG says not to give the primary role to a
            // destructive action.
            Button(i18n.t("desktop.cloudImport.stop")) { store.stopFetch() }
        } else if let terminus = store.terminus, terminus.failed > 0 {
            Button(i18n.t("desktop.cloudImport.retryFailed", ["count": String(terminus.failed)])) { start() }
                .buttonStyle(.borderedProminent)
        } else {
            // A specific verb carrying the count, never "OK" — HIG: "a specific
            // button title… helps people understand the action they're taking."
            Button(i18n.plural("desktop.cloudImport.importButton", count: store.tickedCount)) { start() }
                .buttonStyle(.borderedProminent)
                // No longer gated on a destination existing. "New Project…" is
                // a destination the researcher can commit to — the panel that
                // resolves it opens on the way through, which is the ordinary
                // Save-panel shape rather than a disabled button with no way to
                // find out why.
                .disabled(store.tickedCount == 0)
                .keyboardShortcut(.defaultAction)
        }
    }

    private func start() {
        guard store.tickedCount > 0 else { return }
        guard let projectID = chosenProjectID else {
            // The popup still reads "New Project…" — opened from the welcome
            // screen, where the researcher has said nothing about where this
            // belongs. Ask at the commit, then carry straight on.
            makeNewProject(revertingTo: destination) { created in
                startFetch(into: created)
            }
            return
        }
        startFetch(into: projectID)
    }

    private func startFetch(into projectID: UUID) {
        guard let folder = destinationFolder(for: .project(projectID)) else { return }
        store.startFetch(destination: folder)
    }

    /// The folder behind a choice, or nil when there isn't one to point at.
    ///
    /// One resolution for both readers — the fetch that writes into it and the
    /// scan that reads what it already holds. Two copies would be two chances
    /// to drop the security scope, and the one that dropped it would fail
    /// differently: the fetch loudly at the publish move, the scan silently as
    /// an empty folder, which reads as "nothing here" rather than as a refusal
    /// and would quietly turn the already-imported check off.
    ///
    /// Borrows the project's security-scoped lease rather than rebuilding a
    /// raw path. Under App Sandbox a `URL(fileURLWithPath:)` into a
    /// user-chosen folder has no grant behind it, so the whole multi-gigabyte
    /// transfer would run and then fail at the publish move — surfacing as
    /// "The download failed", which reads as a network fault. Debug builds
    /// are unsandboxed, so a green run there proves nothing about TestFlight.
    ///
    /// `leaseURL` returns a URL with scope already open and owned by
    /// `ProjectIndex`; per its contract we must not call
    /// start/stopAccessingSecurityScopedResource ourselves.
    ///
    /// Still owed, and deliberately not done here because it changes the
    /// surface: the picker offers projects whose lease is unavailable
    /// (`.cantFind`, `.inCloud`, past the watcher cap, or no bookmark data).
    /// Falling back to the raw path keeps today's behaviour for those rather
    /// than introducing a refusal state this pass has no design for.
    ///
    /// No empty-path fallback. `URL(fileURLWithPath: "")` is the cwd, not a
    /// refusal, and it published a real recording into the sandbox container
    /// while the window said "Imported" (16 Aug 2026). The picker no longer
    /// offers unlocated projects, so that guard should be unreachable — it is
    /// here because "should be unreachable" is what the last one said.
    private func destinationFolder(for choice: CloudImportDestinations.Choice) -> URL? {
        guard case .project(let id) = choice,
              let project = projectIndex.projects.first(where: { $0.id == id }),
              !project.path.isEmpty
        else { return nil }
        return projectIndex.leaseURL(projectID: id) ?? URL(fileURLWithPath: project.path)
    }

    private var subtitle: String {
        var parts: [String] = []
        if let email = store.accountEmail { parts.append(email) }
        // The window is named by the toolbar picker now. Repeating it here is
        // the redundancy already removed from the footer's "in window".
        // Restored only when the picker is hidden, so a single-choice platform
        // still states its scope somewhere.
        if store.phase == .loaded, platform.windowChoices.count == 1 {
            parts.append(i18n.plural("desktop.cloudImport.subtitleWindow", count: store.windowDays))
        }
        return parts.joined(separator: " · ")
    }
}

// MARK: - Cells

/// Stand-in for each vendor's official mark.
///
/// All three require the unaltered asset and permit no redrawn approximation,
/// so these are explicitly placeholders to be replaced with the downloaded SVGs
/// before this ships. Drawn as neutral glyphs rather than almost-right
/// imitations, because an approximation that looks correct is harder to notice
/// and remove than one that obviously isn't.
private struct VendorMark: View {
    let platform: CloudPlatform

    var body: some View {
        Image(systemName: symbol)
            .imageScale(.medium)
            .accessibilityHidden(true)
    }

    private var symbol: String {
        switch platform {
        case .teams: return "m.square"
        case .meet:  return "g.circle"
        case .zoom:  return "z.square"
        }
    }
}
