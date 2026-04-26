import SwiftUI

/// A single project row in the sidebar.
///
/// Shows the project name with a document icon. Supports inline rename triggered by:
/// - `isRenaming` binding (menu-driven, context menu, or [+] button)
///
/// When a project is unavailable (volume ejected, folder moved), the row shows
/// grey text with a secondary line explaining why. Moved/deleted projects get
/// a `questionmark.folder` icon; volume-not-mounted projects keep `doc.text` greyed.
///
/// Slow-double-click rename is parked — `simultaneousGesture(TapGesture())` and
/// `onTapGesture` both break List selection on macOS 26. See 100days.md.
///
/// Commit on Return, cancel on Escape.
struct ProjectRow: View {

    let project: Project
    @Binding var isRenaming: Bool
    var isDropTarget: Bool = false
    let onRename: (String) -> Void
    let onShowInFinder: () -> Void
    let onDelete: () -> Void
    let onLocate: (() -> Void)?

    @EnvironmentObject var i18n: I18n
    @EnvironmentObject var pipelineRunner: PipelineRunner
    @State private var editText: String = ""
    /// Trailing spinner appears only after a short delay so the steady-state
    /// case (manifests already on disk, scan resolves in a few ms) shows no
    /// indicator at all. Avoids a stadium-wave of spinners at every launch.
    @State private var showScanIndicator: Bool = false
    @FocusState private var isTextFieldFocused: Bool

    private var available: Bool { project.isAvailable }
    private var reason: Project.UnavailabilityReason? { project.unavailabilityReason }
    private var pipelineState: PipelineState? { pipelineRunner.state[project.id] }
    /// Observed so the row reflects `isStopping` updates instantly.
    @ObservedObject private var liveData: PipelineLiveData
    private var isStoppingProgress: Bool {
        liveData.progress[project.id]?.isStopping ?? false
    }

    init(
        project: Project,
        isRenaming: Binding<Bool>,
        isDropTarget: Bool = false,
        liveData: PipelineLiveData,
        onRename: @escaping (String) -> Void,
        onShowInFinder: @escaping () -> Void,
        onDelete: @escaping () -> Void,
        onLocate: (() -> Void)? = nil
    ) {
        self.project = project
        self._isRenaming = isRenaming
        self.isDropTarget = isDropTarget
        self.onRename = onRename
        self.onShowInFinder = onShowInFinder
        self.onDelete = onDelete
        self.onLocate = onLocate
        self._liveData = ObservedObject(wrappedValue: liveData)
    }

    var body: some View {
        HStack(spacing: 6) {
            rowLabel
            Spacer(minLength: 4)
            trailingIndicator
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(Color.accentColor, lineWidth: 2)
                .opacity(isDropTarget ? 1 : 0)
        )
        .onAppear { scheduleScanIndicator() }
        .onChange(of: pipelineState) { _, _ in scheduleScanIndicator() }
    }

    @ViewBuilder
    private var rowLabel: some View {
        Label {
            if isRenaming {
                TextField("Project name", text: $editText)
                    .textFieldStyle(.plain)
                    .focused($isTextFieldFocused)
                    .onSubmit {
                        commitRename()
                    }
                    .onExitCommand {
                        cancelRename()
                    }
                    .onAppear {
                        editText = project.name
                        // Delay focus slightly so the TextField is fully mounted.
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                            isTextFieldFocused = true
                        }
                    }
                    // Commit when focus leaves (e.g. clicking elsewhere).
                    .onChange(of: isTextFieldFocused) { _, focused in
                        if !focused && isRenaming {
                            commitRename()
                        }
                    }
            } else {
                VStack(alignment: .leading, spacing: 1) {
                    if available {
                        Text(project.name)
                    } else {
                        Text(project.name)
                            .foregroundStyle(.secondary)
                    }

                    if !available {
                        switch reason {
                        case .volumeNotMounted(let hint):
                            Text(hint)
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        case .movedOrDeleted:
                            Text(i18n.t("desktop.chrome.locate"))
                                .font(.caption)
                                // No explicit foregroundStyle — inherits primary (deselected)
                                // or white (selected) from the List selection environment.
                        case nil:
                            EmptyView()
                        }
                    } else {
                        // Reserve the subtitle line so row heights stay fixed
                        // across the sidebar — Mail/Notes/Finder convention.
                        // Hidden placeholder when there's no real subtitle.
                        if let subtitle = pipelineSubtitle {
                            Text(subtitle)
                                .font(.caption)
                                .foregroundStyle(pipelineSubtitleStyle)
                        } else {
                            Text(" ")
                                .font(.caption)
                                .hidden()
                        }
                    }
                }
            }
        } icon: {
            if case .movedOrDeleted = reason {
                Image(systemName: "questionmark.folder")
                    .foregroundStyle(.secondary)
            } else {
                if available {
                    Image(systemName: project.icon ?? IconPickerPopover.defaultIcon)
                } else {
                    Image(systemName: project.icon ?? IconPickerPopover.defaultIcon)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    /// Trailing element: spinner while scanning (after delay), red glyph for
    /// failures, otherwise empty. Spinner uses `.controlSize(.small)` to match
    /// Finder's "determining size…" indicator.
    @ViewBuilder
    private var trailingIndicator: some View {
        if isScanning && showScanIndicator {
            ProgressView()
                .controlSize(.small)
        } else if case .failed = pipelineState {
            Image(systemName: "exclamationmark.circle.fill")
                .foregroundStyle(.red)
                .imageScale(.small)
        } else {
            EmptyView()
        }
    }

    // MARK: - Pipeline state display

    private var isScanning: Bool {
        if case .scanning = pipelineState { return true }
        return false
    }

    /// Subtitle text for the pipeline state. Nil means no subtitle row — the
    /// label collapses to single-line like projects without a state.
    /// Copy is draft-quality for alpha; final strings belong in
    /// `bristlenose/locales/*/desktop.json` (see `docs/design-i18n.md`).
    private var pipelineSubtitle: String? {
        switch pipelineState {
        case .none, .scanning, .idle:
            return nil
        case .queued(let position):
            return "Queued · position \(position)"
        case .running:
            return isStoppingProgress ? "Stopping…" : "Analysing…"
        case .ready(let date):
            return "Analysed \(Self.formatAnalysed(date))"
        case .partial(let kind, _):
            // transcribe-only completed; full-analysis verbs land in next UX iteration.
            return kind == "transcribe-only" ? "Transcribed" : "Partial run"
        case .stopped:
            return "Stopped"
        case .failed(let summary, _):
            // Use the human summary the runner already computed for us — far
            // more useful than a generic "Last run failed".
            return summary
        case .unreachable(let reason):
            return reason
        }
    }

    /// Failed subtitle gets a slightly stronger colour so the human summary
    /// reads as actionable, not muted away.
    private var pipelineSubtitleStyle: HierarchicalShapeStyle {
        if case .failed = pipelineState { return .secondary }
        return .tertiary
    }

    /// Relative for the first week ("2 hr ago"), absolute thereafter
    /// ("14 Mar"). Matches Mail's pattern.
    private static func formatAnalysed(_ date: Date) -> String {
        let elapsed = Date().timeIntervalSince(date)
        if elapsed < 7 * 24 * 60 * 60 {
            return relativeFormatter.localizedString(for: date, relativeTo: Date())
        }
        return absoluteFormatter.string(from: date)
    }

    private static let relativeFormatter: RelativeDateTimeFormatter = {
        let f = RelativeDateTimeFormatter()
        f.unitsStyle = .short
        return f
    }()

    private static let absoluteFormatter: DateFormatter = {
        let f = DateFormatter()
        f.setLocalizedDateFormatFromTemplate("d MMM")
        return f
    }()

    /// Schedule the spinner to appear after a brief delay, but only if the
    /// scan hasn't already resolved by then. Most local-disk reads complete
    /// in single-digit ms — those rows never show a spinner at all.
    private func scheduleScanIndicator() {
        guard isScanning else {
            showScanIndicator = false
            return
        }
        let projectID = project.id
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(250))
            // Re-check after the delay — the scan may have resolved already,
            // and the row may now be looking at a different project.
            guard project.id == projectID, isScanning else { return }
            showScanIndicator = true
        }
    }

    // MARK: - Accessibility

    private var accessibilityLabel: String {
        var label = project.name
        if !available {
            switch reason {
            case .volumeNotMounted(let hint):
                label += ", \(i18n.t("desktop.chrome.projectUnavailable")), \(hint)"
            case .movedOrDeleted:
                label += ", \(i18n.t("desktop.chrome.projectMoved"))"
            case nil:
                break
            }
        } else if let subtitle = pipelineSubtitle {
            label += ", \(subtitle)"
        }
        return label
    }

    // MARK: - Rename

    private func commitRename() {
        let trimmed = editText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty && trimmed != project.name {
            onRename(trimmed)
        }
        isRenaming = false
    }

    private func cancelRename() {
        isRenaming = false
    }
}
