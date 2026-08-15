#if DEBUG
import SwiftUI

// DEBUG-only harness for the cloud-import window. Debug ▸ Cloud Import Harness.
//
// Sample data only — no Graph, no auth, no network. It exists so the planned UX
// can be seen and exercised before any adapter exists, and while the real data
// path is blocked behind a work tenant (see the probe brief in the maintainer's
// private handoff notes, kept outside the public tree).
//
// Design: docs/design-cloud-import.md §6/§9. Mockup: docs/mockups/cloud-import-states.html.
//
// Native-primitives note: this is a `Table`, which is NSTableView underneath —
// column headers, sorting and row selection come from the system rather than
// being drawn. And it is a *window*, not a sheet, because a sheet is
// window-modal and could not show per-row outcomes while the project's sidebar
// row reports aggregate progress. Image Capture is the system analogue.

// MARK: - Sample data

struct SampleMeeting: Identifiable {
    let id = UUID()
    var title: String
    /// Already ordered by externality — participant first, observers shed.
    var attendees: [String]
    var hiddenAttendees: Int
    var start: Date
    var durationMinutes: Int?
    var expiresInDays: Int?
    var state: ImportRowState
    var isTicked: Bool
    /// Set only when the researcher did not organise it — this is who to ask.
    var organiser: String?
    /// Per-row progress, 0...1, only during a fetch.
    var progress: Double?
    /// Terminal per-row outcome after a batch.
    var failure: String?

    var attendeeLine: String {
        var line = attendees.joined(separator: " · ")
        if hiddenAttendees > 0 { line += "  +\(hiddenAttendees)" }
        return line
    }
}

/// The scenarios the mockup draws. Switching these is the whole point of the harness.
enum HarnessScenario: String, CaseIterable, Identifiable {
    case notSignedIn = "Not signed in"
    case loading = "Loading"
    case populated = "The list"
    case filtered = "Filtered"
    case noRecordings = "No recordings"
    case filterEmpty = "Filter empty"
    case allImported = "All imported"
    case unreachable = "Unreachable"
    case fetching = "Fetching"
    case partialFailure = "Partial failure"

    var id: String { rawValue }
}

// MARK: - Date formatting

enum ImportDateFormat {
    /// Year appears only when it differs from the current one — Finder and Mail's
    /// rule. Eleven months of the year it is noise; across the New Year it is
    /// essential. Formatted through the system formatter, never a hand-rolled
    /// pattern, because day-name and month ordering differ by locale.
    static func dayLabel(_ date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        let sameYear = calendar.component(.year, from: date) == calendar.component(.year, from: now)
        let format: Date.FormatStyle = sameYear
            ? .dateTime.weekday(.abbreviated).day().month(.abbreviated)
            : .dateTime.weekday(.abbreviated).day().month(.abbreviated).year()
        return date.formatted(format)
    }

    static func timeLabel(_ date: Date) -> String {
        date.formatted(.dateTime.hour().minute())
    }

    static func duration(_ minutes: Int?) -> String {
        guard let minutes else { return "—" }
        if minutes < 60 { return "\(minutes) min" }
        return "\(minutes / 60) h \(String(format: "%02d", minutes % 60))"
    }
}

// MARK: - Window

struct CloudImportHarnessView: View {
    @State private var scenario: HarnessScenario = .populated
    @State private var meetings: [SampleMeeting] = []
    @State private var filterText: String = ""
    @State private var destination: String = "Ward Handover Study"
    @State private var focusedID: SampleMeeting.ID?

    private let projects = ["Ward Handover Study", "Triage Pilot", "Discharge Study 2025"]

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            content
            Divider()
            footer
        }
        .frame(minWidth: 760, minHeight: 420)
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Picker("Scenario", selection: $scenario) {
                    ForEach(HarnessScenario.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.menu)
                .frame(width: 160)
            }
        }
        .navigationTitle("Import from Teams")
        .navigationSubtitle(subtitle)
        .onAppear { load() }
        .onChange(of: scenario) { _, _ in load() }
    }

    // MARK: Header

    private var header: some View {
        HStack {
            Spacer()
            if scenario != .notSignedIn && scenario != .loading {
                TextField("Filter", text: $filterText)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 200)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    private var subtitle: String {
        switch scenario {
        case .notSignedIn: return ""
        case .fetching: return "Fetching 2 of 4 · about 6 min left"
        case .partialFailure: return "4 requested · 2 imported · 2 failed"
        default: return "St Mary's Trust · martin@144a.org · last 30 days"
        }
    }

    // MARK: Content

    @ViewBuilder
    private var content: some View {
        switch scenario {
        case .notSignedIn:
            ContentUnavailableView {
                Label("Not signed in", systemImage: "square.and.arrow.down")
            } description: {
                Text("Use your work or school account to see meetings you recorded in Teams, and bring them into a project.")
            } actions: {
                // The real button is Microsoft's own asset and string
                // ("Sign in with Microsoft", their logo, unaltered). Plain here
                // because this is a harness, not the shipping surface.
                Button("Sign in with Microsoft") {}.buttonStyle(.borderedProminent)
            }

        case .loading:
            VStack(spacing: 8) {
                ProgressView()
                Text("Looking at the last 30 days…").foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .noRecordings:
            ContentUnavailableView {
                Label("No recordings in the last 30 days", systemImage: "calendar")
            } description: {
                Text("11 meetings, none with a recording you organised.")
            } actions: {
                Button("Look back 60 days") {}
            }

        case .filterEmpty:
            ContentUnavailableView.search(text: "Diary study")

        default:
            table
        }
    }

    private var table: some View {
        Table(visibleMeetings, selection: $focusedID) {
            TableColumn("") { meeting in
                if meeting.state.showsCheckbox {
                    Toggle("", isOn: binding(for: meeting))
                        .labelsHidden()
                        .disabled(!meeting.state.isSelectable)
                }
            }
            .width(28)

            TableColumn("Meeting") { meeting in
                VStack(alignment: .leading, spacing: 1) {
                    Text(meeting.title)
                    Text(meeting.attendeeLine)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                .padding(.vertical, 2)
            }

            TableColumn("Date · \(TimeZone.current.abbreviation() ?? "")") { meeting in
                VStack(alignment: .leading, spacing: 1) {
                    Text(ImportDateFormat.dayLabel(meeting.start))
                    Text(ImportDateFormat.timeLabel(meeting.start))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .width(110)

            TableColumn("Length") { meeting in
                Text(ImportDateFormat.duration(meeting.durationMinutes))
                    .monospacedDigit()
            }
            .width(70)

            TableColumn("Expires") { meeting in
                if let days = meeting.expiresInDays {
                    // Earn the red: only rows inside the danger window are
                    // warning-coloured. A countdown on every row is a wall of
                    // countdowns, and then none of them mean anything.
                    Text("in \(days) days")
                        .monospacedDigit()
                        .foregroundStyle(days <= 7 ? .orange : .secondary)
                        .fontWeight(days <= 7 ? .semibold : .regular)
                } else {
                    Text("—").foregroundStyle(.tertiary)
                }
            }
            .width(90)

            TableColumn("Status") { meeting in
                statusCell(meeting)
            }
            .width(150)
        }
        .tableStyle(.inset)
    }

    @ViewBuilder
    private func statusCell(_ meeting: SampleMeeting) -> some View {
        if let progress = meeting.progress {
            HStack(spacing: 6) {
                ProgressView(value: progress).frame(width: 70)
                Text("\(Int(progress * 100))%")
                    .font(.caption).monospacedDigit().foregroundStyle(.secondary)
            }
        } else if let failure = meeting.failure {
            pill(failure, tint: .red)
        } else if let organiser = meeting.organiser {
            pill(organiser, tint: nil, symbol: "person.crop.circle")
        } else if let label = meeting.state.statusLabel {
            pill(label, tint: meeting.state.isWarning ? .orange : nil)
        } else if meeting.state == .imported && scenario == .partialFailure {
            pill("Imported", tint: .green)
        }
    }

    private func pill(_ text: String, tint: Color?, symbol: String? = nil) -> some View {
        HStack(spacing: 3) {
            if let symbol { Image(systemName: symbol).font(.caption2) }
            Text(text).font(.caption)
        }
        .padding(.horizontal, 7).padding(.vertical, 1)
        .background((tint ?? .secondary).opacity(0.15), in: Capsule())
        .foregroundStyle(tint ?? .secondary)
    }

    // MARK: Footer

    private var footer: some View {
        HStack(spacing: 12) {
            arithmetic
            Spacer()
            if scenario != .notSignedIn && scenario != .loading {
                Text("Project:").font(.callout).foregroundStyle(.secondary)
                Picker("", selection: $destination) {
                    ForEach(projects, id: \.self) { Text($0).tag($0) }
                    Divider()
                    Text("New Project…").tag("__new__")
                }
                .labelsHidden()
                .frame(width: 190)

                Button(primaryButtonTitle) {}
                    .buttonStyle(.borderedProminent)
                    .disabled(tickedCount == 0 && scenario != .fetching)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
    }

    /// The most important element in the window. This feature's success output
    /// and its failure output are both "a shorter list" — an unfollowed
    /// pagination link, a shifted window, a fuzzy join key all produce one, and
    /// the researcher reads it as "it didn't record" while an expiry clock runs.
    /// Stating the arithmetic is the only place a data-losing failure becomes
    /// visible.
    @ViewBuilder
    private var arithmetic: some View {
        switch scenario {
        case .unreachable:
            HStack(spacing: 4) {
                Image(systemName: "person.crop.circle")
                Text("**A. Bianchi** organised this. Bristlenose can't see whether it was recorded — ask them.")
                    .font(.callout)
            }
        case .fetching:
            Text("Fetching soonest-expiring first · 2.4 GB of 4.7 GB")
                .font(.callout).foregroundStyle(.secondary)
        case .partialFailure:
            Text("**2 imported** · 2 failed — 8.1 GB free, 2.6 GB needed")
                .font(.callout)
        case .allImported:
            Text("3 already in **\(destination)** · 1 needs re-fetching")
                .font(.callout).foregroundStyle(.secondary)
        case .filtered:
            Text("7 of 9 shown · filtered on “Interview”")
                .font(.callout).foregroundStyle(.secondary)
        case .notSignedIn, .loading, .noRecordings, .filterEmpty:
            EmptyView()
        case .populated:
            Text("11 meetings in window · **8 you can fetch** · 3 organised by someone else")
                .font(.callout).foregroundStyle(.secondary)
        }
    }

    private var primaryButtonTitle: String {
        switch scenario {
        case .fetching: return "Stop"
        case .partialFailure: return "Retry 2"
        default:
            // Verb plus count, never "OK" — HIG: a specific title helps people
            // understand the action they're taking.
            return tickedCount == 1 ? "Import 1 Recording" : "Import \(tickedCount) Recordings"
        }
    }

    // MARK: Plumbing

    private var visibleMeetings: [SampleMeeting] {
        guard !filterText.isEmpty else { return meetings }
        return meetings.filter { $0.title.localizedCaseInsensitiveContains(filterText) }
    }

    private var tickedCount: Int { meetings.filter(\.isTicked).count }

    private func binding(for meeting: SampleMeeting) -> Binding<Bool> {
        Binding(
            get: { meetings.first(where: { $0.id == meeting.id })?.isTicked ?? false },
            set: { newValue in
                guard let i = meetings.firstIndex(where: { $0.id == meeting.id }) else { return }
                meetings[i].isTicked = newValue
            }
        )
    }

    private func load() {
        filterText = (scenario == .filtered) ? "Interview" : ""
        meetings = CloudImportSampleData.meetings(for: scenario)
    }
}

// MARK: - Sample data

enum CloudImportSampleData {
    private static func date(_ daysAgo: Int, _ hour: Int, _ minute: Int) -> Date {
        let cal = Calendar.current
        let day = cal.date(byAdding: .day, value: -daysAgo, to: Date()) ?? Date()
        return cal.date(bySettingHour: hour, minute: minute, second: 0, of: day) ?? day
    }

    static func meetings(for scenario: HarnessScenario) -> [SampleMeeting] {
        switch scenario {
        case .notSignedIn, .loading, .noRecordings, .filterEmpty:
            return []

        case .populated, .filtered:
            return [
                SampleMeeting(title: "P07 Interview — ward handover",
                              attendees: ["Sarah Chen", "J. Whitfield"], hiddenAttendees: 4,
                              start: date(3, 16, 0), durationMinutes: 58, expiresInDays: 58,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P06 Interview — ward handover",
                              attendees: ["Margarethe Okafor-Whitcombe", "A. Bianchi"], hiddenAttendees: 3,
                              start: date(3, 14, 30), durationMinutes: 64, expiresInDays: 57,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "Weekly sync — design",
                              attendees: ["6 attendees"], hiddenAttendees: 0,
                              start: date(3, 9, 30), durationMinutes: 27, expiresInDays: 57,
                              state: .notImported, isTicked: false, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P05 Interview — ward handover",
                              attendees: ["J. Whitfield"], hiddenAttendees: 0,
                              start: date(4, 11, 0), durationMinutes: 51, expiresInDays: 56,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P04 Interview — triage",
                              attendees: ["D. Achebe"], hiddenAttendees: 0,
                              start: date(9, 15, 15), durationMinutes: 71, expiresInDays: 52,
                              state: .imported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P03 Interview — triage",
                              attendees: ["L. Fitzgerald"], hiddenAttendees: 0,
                              start: date(11, 10, 0), durationMinutes: 55, expiresInDays: 50,
                              state: .damaged, isTicked: false, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P02 Interview — triage",
                              attendees: ["K. Lindqvist"], hiddenAttendees: 0,
                              start: date(49, 13, 0), durationMinutes: 62, expiresInDays: 12,
                              state: .notDownloaded(provider: "Dropbox"), isTicked: true,
                              organiser: nil, progress: nil, failure: nil),
                SampleMeeting(title: "P01 Interview — triage",
                              attendees: ["R. Nakamura"], hiddenAttendees: 0,
                              start: date(56, 9, 0), durationMinutes: 49, expiresInDays: 5,
                              state: .notImported, isTicked: false, organiser: nil,
                              progress: nil, failure: nil),
            ]

        case .allImported:
            return [
                SampleMeeting(title: "P07 Interview — ward handover",
                              attendees: ["Sarah Chen"], hiddenAttendees: 4,
                              start: date(3, 16, 0), durationMinutes: 58, expiresInDays: 58,
                              state: .imported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P05 Interview — ward handover",
                              attendees: ["J. Whitfield"], hiddenAttendees: 0,
                              start: date(4, 11, 0), durationMinutes: 51, expiresInDays: 56,
                              state: .driveNotConnected(volume: "T7"), isTicked: true,
                              organiser: nil, progress: nil, failure: nil),
                SampleMeeting(title: "P03 Interview — triage",
                              attendees: ["L. Fitzgerald"], hiddenAttendees: 0,
                              start: date(11, 10, 0), durationMinutes: 55, expiresInDays: 50,
                              state: .damaged, isTicked: false, organiser: nil,
                              progress: nil, failure: nil),
            ]

        case .unreachable:
            return [
                SampleMeeting(title: "P07 Interview — ward handover",
                              attendees: ["Sarah Chen"], hiddenAttendees: 4,
                              start: date(3, 16, 0), durationMinutes: 58, expiresInDays: 58,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                // Length and expiry are unknown on purpose: both come from the
                // recording, and we cannot see it. We know the meeting and the
                // organiser from the calendar — hence "ask them", never "they have it".
                SampleMeeting(title: "Discharge pathway — session 2",
                              attendees: ["A. Bianchi", "D. Achebe"], hiddenAttendees: 3,
                              start: date(4, 10, 0), durationMinutes: nil, expiresInDays: nil,
                              state: .noLongerAvailable, isTicked: false,
                              organiser: "A. Bianchi", progress: nil, failure: nil),
                SampleMeeting(title: "P05b Interview — ward handover",
                              attendees: ["D. Achebe", "S. Chen"], hiddenAttendees: 2,
                              start: date(4, 16, 30), durationMinutes: 69, expiresInDays: 56,
                              state: .viewOnly, isTicked: false, organiser: nil,
                              progress: nil, failure: nil),
            ]

        case .fetching:
            return [
                SampleMeeting(title: "P01 Interview — triage",
                              attendees: ["R. Nakamura"], hiddenAttendees: 0,
                              start: date(56, 9, 0), durationMinutes: 49, expiresInDays: 5,
                              state: .imported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P05 Interview — ward handover",
                              attendees: ["J. Whitfield"], hiddenAttendees: 0,
                              start: date(4, 11, 0), durationMinutes: 51, expiresInDays: 56,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: 0.64, failure: nil),
                SampleMeeting(title: "P06 Interview — ward handover",
                              attendees: ["M. Okafor", "A. Bianchi"], hiddenAttendees: 3,
                              start: date(3, 14, 30), durationMinutes: 64, expiresInDays: 57,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: "Queued"),
                SampleMeeting(title: "P07 Interview — ward handover",
                              attendees: ["Sarah Chen"], hiddenAttendees: 4,
                              start: date(3, 16, 0), durationMinutes: 58, expiresInDays: 58,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: "Queued"),
            ]

        case .partialFailure:
            return [
                SampleMeeting(title: "P01 Interview — triage",
                              attendees: ["R. Nakamura"], hiddenAttendees: 0,
                              start: date(56, 9, 0), durationMinutes: 49, expiresInDays: 5,
                              state: .imported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P05 Interview — ward handover",
                              attendees: ["J. Whitfield"], hiddenAttendees: 0,
                              start: date(4, 11, 0), durationMinutes: 51, expiresInDays: 56,
                              state: .imported, isTicked: true, organiser: nil,
                              progress: nil, failure: nil),
                SampleMeeting(title: "P06 Interview — ward handover",
                              attendees: ["M. Okafor", "A. Bianchi"], hiddenAttendees: 3,
                              start: date(3, 14, 30), durationMinutes: 64, expiresInDays: 57,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: "Lost connection at 71%"),
                SampleMeeting(title: "P07 Interview — ward handover",
                              attendees: ["Sarah Chen"], hiddenAttendees: 4,
                              start: date(3, 16, 0), durationMinutes: 58, expiresInDays: 58,
                              state: .notImported, isTicked: true, organiser: nil,
                              progress: nil, failure: "Not enough disk space"),
            ]
        }
    }
}
#endif
