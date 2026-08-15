import SwiftUI

// The import window. Renders `CloudImportStore`; decides nothing itself.
//
// Shape comes from docs/mockups/cloud-import-states.html — the Teams window —
// with the Google deviations marked `DEVIATION` inline and argued in
// docs/design-cloud-import.md §3.
//
// Native primitives, per desktop/CLAUDE.md § Native primitives first:
//   • `Table`                  — NSTableView. Sortable columns, type-select,
//                                arrow-key navigation and VoiceOver for free.
//   • `ContentUnavailableView` — the system empty state; `.search` quotes the
//                                term back on its own.
//   • `Window` scene           — not a sheet. A sheet is window-modal, so it
//                                would hide the sidebar-row progress behind
//                                itself and destroy the per-row outcomes that
//                                recovery depends on (§9). Image Capture is the
//                                system analogue and it is a window.
//
// The one place selection semantics needed a decision: the mockup says "ticks
// are intent, highlight is keyboard focus". `Table`'s single selection IS a
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
    @State private var sortOrder: [KeyPathComparator<CloudImportRow>] = [
        .init(\.startsAt, order: .reverse)
    ]

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
        .task {
            if store.accountEmail != nil, store.listing == nil { await store.load() }
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
        let rows = store.visibleRows

        if let refusal = store.blanketRefusal {
            // DEVIATION, and the most important one on this platform. Every row
            // is unfetchable for the same reason, so the window says it once
            // instead of drawing eleven dead ticks. The Teams design never
            // needed this: its equivalent failure (a personal account with no
            // /Recordings folder) returns an empty list, which is at least
            // legibly empty. Google returns a full, convincing calendar and no
            // media — a list that looks like it works.
            blanketRefusalView(refusal)
        } else if rows.isEmpty && !store.filterText.isEmpty {
            // State 6. `.search` quotes the term back automatically.
            ContentUnavailableView.search(text: store.filterText)
        } else if rows.isEmpty {
            // State 5.
            ContentUnavailableView {
                Label("No recordings in the last \(store.windowDays) days",
                      systemImage: "calendar")
            } description: {
                Text(emptyWindowDetail)
            } actions: {
                Button("Look back \(store.windowDays * 2) days") {
                    store.windowDays *= 2
                    Task { await store.load() }
                }
            }
        } else {
            table(rows)
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
        case .needsScope:     return "Bristlenose can't see your recordings"
        case .notOrganiser:   return "None of these are yours to fetch"
        case .unsupported:    return "Recordings aren't available"
        case .available:      return ""
        }
    }

    private func blanketIcon(_ refusal: ArtifactAvailability) -> String {
        switch refusal {
        case .notOnThisPlan: return "person.crop.circle.badge.exclamationmark"
        case .needsScope:    return "lock"
        default:             return "questionmark.circle"
        }
    }

    private func blanketDetail(_ refusal: ArtifactAvailability) -> String {
        switch refusal {
        case .notOnThisPlan:
            // Names the meetings we CAN see, so the sentence reads as an
            // explanation rather than as a failure to find anything.
            return "\(store.listing?.rows.count ?? 0) meetings are here, but Meet recording needs a Google Workspace plan. "
                + "Recordings made on a work account can still be dragged in from Finder."
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
        case .unsupported, .available:
            return ""
        }
    }

    private var emptyWindowDetail: String {
        guard let a = store.listing?.arithmetic else { return "" }
        return "\(a.eventsInWindow) meetings, none with a recording you organised."
    }

    // MARK: - The table

    private func table(_ rows: [CloudImportRow]) -> some View {
        Table(rows, selection: $store.focusedRowID, sortOrder: $sortOrder) {
            // Tick column. Header is deliberately blank — a titled checkbox
            // column reads as a filter control.
            TableColumn("") { row in
                TickBox(row: row, store: store)
            }
            .width(28)

            TableColumn("Meeting") { row in
                VStack(alignment: .leading, spacing: 1) {
                    Text(row.title).lineLimit(1)
                    AttendeeLineView(row: row)
                }
            }
            .width(min: 220, ideal: 320)

            TableColumn("Date", value: \.startsAt) { row in
                VStack(alignment: .leading, spacing: 1) {
                    Text(row.startsAt, format: dateFormat(for: row.startsAt))
                        .monospacedDigit()
                    Text(row.startsAt, style: .time)
                        .font(.caption).foregroundStyle(.secondary).monospacedDigit()
                }
            }
            .width(min: 96, ideal: 120)

            TableColumn("Length") { row in
                Text(row.duration.map(DurationFormat.human) ?? "—")
                    .monospacedDigit()
                    .foregroundStyle(row.duration == nil ? .secondary : .primary)
            }
            .width(min: 60, ideal: 76)

            // Expiry is a COLUMN on platforms that expose a per-file clock,
            // and absent on those that do not. Teams' own product renders
            // exactly this affordance on exactly this data; Drive has no
            // expiration field at all, so drawing the column there would be a
            // row of em-dashes pretending to be data. Absence is information.
            if platform.hasPerFileExpiry {
                TableColumn("Expires") { row in
                    ExpiryCell(row: row)
                }
                .width(min: 78, ideal: 96)
            }

            TableColumn("Status") { row in
                StatusCell(row: row, store: store)
            }
            .width(min: 110, ideal: 170)
        }
        .tableStyle(.inset)
        .alternatingRowBackgrounds(.disabled)
    }

    /// Year appears only when it differs from the current one — Finder and
    /// Mail's rule. Eleven months of the year it is noise; across the New Year
    /// it is essential. Through the system formatter, never a hand-rolled
    /// pattern: day-name and month ordering differ by locale.
    private func dateFormat(for date: Date) -> Date.FormatStyle {
        let cal = Calendar.current
        let sameYear = cal.component(.year, from: date) == cal.component(.year, from: Date())
        var style = Date.FormatStyle.dateTime.weekday(.abbreviated).day().month(.abbreviated)
        if !sameYear { style = style.year() }
        return style
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
            HStack(spacing: 5) {
                Text(a.isExact
                     ? "\(a.eventsInWindow) meetings in window"
                     : "at least \(a.eventsInWindow) meetings in window")
                Text("·").foregroundStyle(.secondary)
                Text("\(a.fetchable) you can fetch").fontWeight(.semibold)
                if a.organisedByOthers > 0 {
                    Text("·").foregroundStyle(.secondary)
                    Text("\(a.organisedByOthers) organised by someone else")
                        .foregroundStyle(.secondary)
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

    private var destinationPicker: some View {
        Picker("", selection: $destinationID) {
            ForEach(projectIndex.projects) { project in
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
        let destination = projectIndex.leaseURL(projectID: destinationID)
            ?? URL(fileURLWithPath: project.path)
        store.startFetch(destination: destination)
    }

    private var subtitle: String {
        var parts: [String] = []
        if let email = store.accountEmail { parts.append(email) }
        if store.phase == .loaded { parts.append("last \(store.windowDays) days") }
        return parts.joined(separator: " · ")
    }
}

// MARK: - Cells

private struct TickBox: View {
    let row: CloudImportRow
    @ObservedObject var store: CloudImportStore

    var body: some View {
        if row.showsCheckbox {
            Toggle("", isOn: Binding(
                get: { store.ticked.contains(row.id) || !row.localState.isSelectable },
                set: { _ in store.toggle(row.id) }
            ))
            .labelsHidden()
            .disabled(!row.isSelectable)
            .help(row.isSelectable ? "" : heldReason)
        } else {
            // No checkbox at all. There is nothing to tick, and offering one
            // would be a lie.
            Color.clear.frame(width: 1, height: 1)
        }
    }

    /// Why a held row is disabled. The distinction that matters: a placeholder
    /// or an unplugged volume is a *local* problem, and re-fetching from Meet
    /// would spend an expiry-limited remote read on it.
    private var heldReason: String {
        switch row.localState {
        case .imported:                        return "Already in this project."
        case .notDownloaded(let provider):     return "Already imported — the file is on \(provider) and needs downloading there."
        case .driveNotConnected(let volume):   return "Already imported — “\(volume)” isn't connected."
        default:                               return ""
        }
    }
}

private struct AttendeeLineView: View {
    let row: CloudImportRow

    var body: some View {
        let (names, overflow) = AttendeeLine.compose(row.attendees)
        HStack(spacing: 4) {
            if names.isEmpty {
                Text("\(row.attendees.count) attendees")
            } else {
                Text(names.joined(separator: " · ")).lineLimit(1)
                if overflow > 0 {
                    // A count, not an ellipsis: "+4" says there are six.
                    Text("+\(overflow)")
                        .padding(.horizontal, 4).padding(.vertical, 1)
                        .background(.quaternary, in: Capsule())
                }
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        // Names in the list, emails never — they are a re-identification key
        // and are also unscannable. They earn their place at the "who is p1?"
        // promotion step.
    }
}

private struct StatusCell: View {
    let row: CloudImportRow
    @ObservedObject var store: CloudImportStore

    var body: some View {
        if let progress = store.progress[row.id] {
            HStack(spacing: 6) {
                ProgressView(value: progress.fraction ?? 0).frame(width: 60)
                Text(progress.fraction.map { "\(Int($0 * 100))%" } ?? "")
                    .font(.caption).monospacedDigit().foregroundStyle(.secondary)
            }
        } else if let outcome = store.outcomes[row.id] {
            switch outcome {
            case .imported:
                Label("Imported", systemImage: "checkmark").font(.caption).foregroundStyle(.green)
            case .failed(let reason, _):
                Text(reason).font(.caption).foregroundStyle(.red).lineLimit(1).help(reason)
            case .cancelled:
                Text("Stopped").font(.caption).foregroundStyle(.secondary)
            }
        } else if store.isFetching && store.ticked.contains(row.id) {
            Text("Queued").font(.caption).foregroundStyle(.secondary)
        } else if let label = row.statusLabel {
            Text(label)
                .font(.caption)
                .foregroundStyle(row.localState.isWarning ? .orange : .secondary)
                .lineLimit(1)
        }
    }
}

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

/// The countdown, rendered only where the platform supplies one.
private struct ExpiryCell: View {
    let row: CloudImportRow

    var body: some View {
        if let expires = row.expiresAt {
            Text(expires, format: .relative(presentation: .named))
                .font(.callout)
                // Earn the red: a countdown on every row is a wall of
                // countdowns, and then none of them mean anything. Only rows
                // inside the danger window get warning colour.
                .foregroundStyle(isUrgent(expires) ? AnyShapeStyle(.orange)
                                                   : AnyShapeStyle(.secondary))
        } else {
            Text("—").foregroundStyle(.tertiary)
        }
    }

    private func isUrgent(_ date: Date) -> Bool {
        date.timeIntervalSinceNow < 7 * 24 * 3600
    }
}
