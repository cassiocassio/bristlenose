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
    /// Supplies every vendor-specific string. A `switch` on platform inside a
    /// view body is the smell this replaces.
    let platform: CloudPlatform

    /// Destination project. Pre-selected by how the window was opened (§9), not
    /// defaulted — a wrong default here writes gigabytes into the wrong study.
    @State private var destinationID: UUID?

    var body: some View {
        VStack(spacing: 0) {
            content
            Divider()
            footer
        }
        .frame(minWidth: 760, minHeight: 420)
        .navigationTitle(platform.windowTitle)
        .navigationSubtitle(subtitle)
        .searchable(text: $store.filterText, placement: .toolbar, prompt: "Filter")
        .toolbar { windowScopePicker }
        .task {
            if store.accountEmail != nil, store.listing == nil { await store.load() }
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
                Picker("Window", selection: $store.windowDays) {
                    ForEach(platform.windowChoices, id: \.self) { days in
                        Text("Last \(CloudCount.noun(days, "day"))").tag(days)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .help("How far back to look for recordings")
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
                Text("Looking at the last \(store.windowDays) days…")
                    .font(.callout).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .signInIncomplete:
            ContentUnavailableView {
                Label("Sign-in didn't finish", systemImage: "person.crop.circle.badge.questionmark")
            } description: {
                Text(incompleteSignInDetail)
            } actions: {
                Button("Try Again", action: store.signIn)
            }

        case .failed(let message):
            ContentUnavailableView {
                Label("Couldn't load your meetings", systemImage: "exclamationmark.triangle")
            } description: {
                Text(message)
            } actions: {
                Button("Try Again") { Task { await store.load() } }
            }

        case .loaded:
            loadedView
        }
    }

    /// State 1 — the resting state, and what most launches see. One line of what
    /// it does, one button, no billboard.
    private var signedOutView: some View {
        ContentUnavailableView {
            Label("Not signed in", systemImage: "arrow.down.circle")
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
        let base = "Bristlenose didn't receive an account from \(platform.displayName)."
        guard platform.signInMayAwaitAdminApproval else {
            return base + " If you closed the sign-in window, try again."
        }
        return base
            + " If you closed the sign-in window, try again — and if \(platform.displayName) "
            + "asked for your administrator's approval, sign-in won't complete until they grant it."
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
        let base = "Sign in to see the meetings you recorded, and bring them into a project."
        guard let noun = platform.accountNoun else { return base }
        return "Use your \(noun) to see the meetings you recorded, and bring them into a project."
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
                Label("No recordings in the last \(store.windowDays) days",
                      systemImage: "calendar")
            } description: {
                Text(emptyWindowDetail)
            } actions: {
                // The next choice up, not a doubling — and absent when there
                // isn't one, so the empty state stops offering a window the
                // platform cannot serve. The re-list rides `onChange`, so this
                // only sets the value.
                if let wider = platform.windowChoices.first(where: { $0 > store.windowDays }) {
                    Button("Look back \(CloudCount.noun(wider, "day"))") {
                        store.windowDays = wider
                    }
                }
            }
        } else {
            CloudImportOutlineView(store: store, platform: platform)
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
                Button("Sign In Again") { store.signIn() }
            }
        }
    }

    private func blanketTitle(_ refusal: ArtifactAvailability) -> String {
        switch refusal {
        case .notOnThisPlan:  return "This account can't record Meet calls"
        case .notRecorded:    return "None of these were recorded"
        case .needsScope:     return "Bristlenose can't see your recordings"
        case .notOrganiser:   return "None of these are yours to fetch"
        case .notResolved:    return "Bristlenose couldn't match these up"
        case .unsupported:    return "Recordings aren't available"
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
            return (n == 1
                    ? "One meeting is here, but Meet recording needs a Google Workspace plan. "
                    : "\(n) meetings are here, but Meet recording needs a Google Workspace plan. ")
                + "Recordings made on a work account can still be dragged in from Finder."
        case .notRecorded:
            // States the fact and stops. No remedy is offered because there
            // isn't one — the meetings are over, and a recording that was
            // never started cannot be recovered by anything the researcher
            // does here. Naming the count keeps it an observation about this
            // window rather than a verdict about the account.
            let count = store.listing?.rows.count ?? 0
            return (count == 1
                    ? "One meeting is here, and it wasn't recorded. "
                    : "\(count) meetings are here, and none of them were recorded. ")
                + "Meet only keeps a recording when someone starts one during the call."
        case .needsScope:
            // The wording is careful, and the care is a research finding rather
            // than taste. Google does NOT support incremental authorisation for
            // installed apps — stated twice on its own native-app page — so
            // there is no way to ask for just the missing permission. Signing in
            // again re-presents the whole consent screen. Promising "only that
            // one permission" would be a small lie that the very next screen
            // contradicts, which is how a consent prompt teaches people to stop
            // reading consent prompts.
            return "Your meetings loaded, but access to the recordings themselves was declined. "
                + "Signing in again will ask for both permissions together — Google can't request one on its own."
        case .notOrganiser(let organiser):
            return organiser.map {
                "\($0) organised these. Bristlenose can't see whether they were recorded — ask them."
            } ?? "Someone else organised these. Ask them to share the recordings."
        case .notResolved:
            // Names the cause, because it is the one thing that makes the
            // remedy obvious: the room is reused, so the link alone can't say
            // which call this was. The recordings are still in Drive.
            return "These meetings share a Meet link, and more than one call was recorded "
                + "around the same time — so Bristlenose can't tell which recording belongs "
                + "to which. Open Google Drive and drag the ones you want in from Finder."
        case .unsupported, .available:
            return ""
        }
    }

    private var emptyWindowDetail: String {
        guard let a = store.listing?.arithmetic else { return "" }
        return "\(CloudCount.noun(a.eventsInWindow, "meeting")), none with a recording you organised."
    }

    // MARK: - Footer

    private var footer: some View {
        HStack(spacing: 12) {
            arithmeticLine
            Spacer(minLength: 12)
            if store.phase == .loaded, store.blanketRefusal == nil, !(store.listing?.rows.isEmpty ?? true) {
                Text("Project:").font(.caption).foregroundStyle(.secondary)
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
                Text("\(terminus.imported) imported").fontWeight(.semibold)
                if terminus.failed > 0 {
                    Text("·").foregroundStyle(.secondary)
                    Text("\(terminus.failed) failed").foregroundStyle(.red).fontWeight(.semibold)
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
                     ? CloudCount.noun(counts.meetings, "meeting")
                     : "at least \(CloudCount.noun(counts.meetings, "meeting"))")
                // Only when the two numbers differ. In the 90% case one meeting
                // made one recording, and a second noun saying the same number
                // twice is a sentence the reader has to check before
                // discarding.
                if counts.recordings != counts.meetings {
                    Text("·").foregroundStyle(.secondary)
                    Text(CloudCount.noun(counts.recordings, "recording"))
                }
                Text("·").foregroundStyle(.secondary)
                Text("\(counts.fetchable) you can fetch").fontWeight(.semibold)
                // Suppressed while a filter is on. Every other number in this
                // sentence is measured over the filtered list; this one is
                // measured over the whole window, so filtering to "P05" read
                // "1 meeting · 1 you can fetch · 4 organised by someone else"
                // — one sentence quietly counting two different sets, on the
                // surface whose entire claim is that its arithmetic is
                // checkable by looking.
                if a.organisedByOthers > 0, store.filterText.isEmpty {
                    Text("·").foregroundStyle(.secondary)
                    Text("\(a.organisedByOthers) organised by someone else")
                        .foregroundStyle(.secondary)
                }
                // Shown only when a recording the researcher can *see* is one
                // they cannot fetch. Fetch 8 of 8 and there is no link — that
                // absence is the reassurance, and a permanent "learn about
                // permissions" would train people to ignore it by the third
                // visit.
                if counts.withholding {
                    Link("About recordings permissions", destination: platform.permissionsDocURL)
                        .font(.caption)
                }
                // A capped paginator returns HTTP 200 with a partial page, and
                // every error check says fine. Saying so is the whole point.
                if case .pageCapHit = a.outcome {
                    Label("Partial list", systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                        .help("Bristlenose stopped after \(store.windowDays) days' worth of pages. There may be more.")
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
    /// as a destination is offering a choice that cannot work: on 16 Aug 2026 a
    /// real recording was fetched, verified byte-for-byte, and published into
    /// `URL(fileURLWithPath: "")`, which resolves to the **process's current
    /// working directory** — the sandbox container root. The window reported
    /// "✓ Imported" and the researcher had no way to find their file.
    ///
    /// Filtering here rather than refusing at `start()` keeps this a correctness
    /// fix rather than a new UI state: the primary button's existing disabled
    /// condition (`destinationID == nil`) already covers "nothing selectable".
    private var deliverableProjects: [Project] {
        projectIndex.projects.filter { !$0.path.isEmpty }
    }

    private var destinationPicker: some View {
        Picker("", selection: $destinationID) {
            ForEach(deliverableProjects) { project in
                Text(project.name).tag(Optional(project.id))
            }
        }
        .labelsHidden()
        .frame(maxWidth: 200)
    }

    @ViewBuilder
    private var primaryButton: some View {
        if store.isFetching {
            // Not prominent: HIG says not to give the primary role to a
            // destructive action.
            Button("Stop") { store.stopFetch() }
        } else if let terminus = store.terminus, terminus.failed > 0 {
            Button("Retry \(terminus.failed)") { start() }
                .buttonStyle(.borderedProminent)
        } else {
            // A specific verb carrying the count, never "OK" — HIG: "a specific
            // button title… helps people understand the action they're taking."
            Button(store.tickedCount == 1
                   ? "Import 1 Recording"
                   : "Import \(store.tickedCount) Recordings") { start() }
                .buttonStyle(.borderedProminent)
                .disabled(store.tickedCount == 0 || destinationID == nil)
                .keyboardShortcut(.defaultAction)
        }
    }

    private func start() {
        guard let destinationID,
              let project = projectIndex.projects.first(where: { $0.id == destinationID })
        else { return }

        // Borrow the project's security-scoped lease rather than rebuilding a
        // raw path. Under App Sandbox a `URL(fileURLWithPath:)` into a
        // user-chosen folder has no grant behind it, so the whole multi-gigabyte
        // transfer would run and then fail at the publish move — surfacing as
        // "The download failed", which reads as a network fault. Debug builds
        // are unsandboxed, so a green run there proves nothing about TestFlight.
        //
        // `leaseURL` returns a URL with scope already open and owned by
        // `ProjectIndex`; per its contract we must not call
        // start/stopAccessingSecurityScopedResource ourselves.
        //
        // Still owed, and deliberately not done here because it changes the
        // surface: the picker offers projects whose lease is unavailable
        // (`.cantFind`, `.inCloud`, past the watcher cap, or no bookmark data).
        // Falling back to the raw path keeps today's behaviour for those rather
        // than introducing a refusal state this pass has no design for.
        // No empty-path fallback. `URL(fileURLWithPath: "")` is the cwd, not a
        // refusal, and it published a real recording into the sandbox container
        // while the window said "Imported" (16 Aug 2026). The picker no longer
        // offers unlocated projects, so this guard should be unreachable — it
        // is here because "should be unreachable" is what the last one said.
        guard !project.path.isEmpty else { return }
        let destination = projectIndex.leaseURL(projectID: destinationID)
            ?? URL(fileURLWithPath: project.path)
        store.startFetch(destination: destination)
    }

    private var subtitle: String {
        var parts: [String] = []
        if let email = store.accountEmail { parts.append(email) }
        // The window is named by the toolbar picker now. Repeating it here is
        // the redundancy already removed from the footer's "in window".
        // Restored only when the picker is hidden, so a single-choice platform
        // still states its scope somewhere.
        if store.phase == .loaded, platform.windowChoices.count == 1 {
            parts.append("last \(CloudCount.noun(store.windowDays, "day"))")
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
