import SwiftUI

/// A single project row in the sidebar.
///
/// **Anatomy (two-line):**
/// - Title line: identity icon · project name · *(right)* session count
/// - Subtitle line: optional ⚠/❓ prefix glyph · status text · optional delta segment · *(right)* cloud arrow
///
/// **Right-edge convention:**
/// - Title-line right = canonical data quantity (the session count — Finder's
///   right column). Empty when the analysis DB isn't readable.
/// - Subtitle-line right = storage location qualifier (currently just the
///   iCloud download arrow). Finder-esque, only appears when the project's
///   sources live in iCloud.
///
/// **Precedence chain for the subtitle (see memory `feedback_exception_precedence_chain`):**
/// failed > running/stopped/partial > cantFind > ready+missing > ready+unanalysed > ready (bare date).
/// One state per row; we don't stack errors. Tooltips carry the full picture.
///
/// Slow-double-click rename is parked — `simultaneousGesture(TapGesture())` and
/// `onTapGesture` both break List selection on macOS 26.
/// Commit on Return, cancel on Escape.
struct ProjectRow: View {

    let project: Project
    @Binding var isRenaming: Bool
    var isDropTarget: Bool = false
    let onRename: (String) -> Void
    let onShowInFinder: () -> Void
    let onDelete: () -> Void
    let onLocate: (() -> Void)?
    /// Data state for this project (session count, unanalysed delta, missing
    /// delta). Nil while a drag-onto copy sheet is up for this project — the
    /// row falls back to "no deltas, no count" so the copy flow's own sheet
    /// is the user's focus (handoff §Stacking rule).
    let unanalysed: UnanalysedState?
    /// Called when the user taps the `+N unanalysed` subtitle segment. Caller
    /// opens the `NewFilesSheet` in watcher mode.
    let onOpenUnanalysed: (() -> Void)?

    @EnvironmentObject var i18n: I18n
    @EnvironmentObject var pipelineRunner: PipelineRunner
    @State private var editText: String = ""
    /// Spinner appears only after a short delay so the steady-state case
    /// (manifests already on disk, scan resolves in a few ms) shows no
    /// indicator at all. Avoids a stadium-wave of spinners at every launch.
    @State private var showScanIndicator: Bool = false
    @FocusState private var isTextFieldFocused: Bool

    private var availability: ProjectAvailability { project.availability }
    private var available: Bool { availability.isReady }
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
        unanalysed: UnanalysedState? = nil,
        onRename: @escaping (String) -> Void,
        onShowInFinder: @escaping () -> Void,
        onDelete: @escaping () -> Void,
        onLocate: (() -> Void)? = nil,
        onOpenUnanalysed: (() -> Void)? = nil
    ) {
        self.project = project
        self._isRenaming = isRenaming
        self.isDropTarget = isDropTarget
        self.unanalysed = unanalysed
        self.onRename = onRename
        self.onShowInFinder = onShowInFinder
        self.onDelete = onDelete
        self.onLocate = onLocate
        self.onOpenUnanalysed = onOpenUnanalysed
        self._liveData = ObservedObject(wrappedValue: liveData)
    }

    var body: some View {
        HStack(alignment: .center, spacing: 6) {
            leadingIcon
            VStack(alignment: .leading, spacing: 1) {
                titleLine
                subtitleLine
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .help(rowTooltip)
        // Drop-target highlight traces the outer row container, not the
        // inner HStack — negative padding pushes the stroke past the row
        // content's natural bounds so it matches the selection pill shape
        // (Finder-style full-row drop affordance).
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.accentColor, lineWidth: 2)
                .opacity(isDropTarget ? 1 : 0)
                .padding(.horizontal, -6)
                .padding(.vertical, -3)
        )
        .onAppear { scheduleScanIndicator() }
        .onChange(of: pipelineState) { _, _ in scheduleScanIndicator() }
    }

    // MARK: - Leading icon

    @ViewBuilder
    private var leadingIcon: some View {
        // Identity icon — the project's chosen SF Symbol. Availability state
        // is signalled by dimming the name + a subtitle prefix glyph, never
        // by overwriting the chosen icon.
        let name = project.icon ?? IconPickerPopover.defaultIcon
        if available {
            Image(systemName: name)
        } else {
            Image(systemName: name).foregroundStyle(.secondary)
        }
    }

    // MARK: - Title line

    @ViewBuilder
    private var titleLine: some View {
        if isRenaming {
            renameField
        } else {
            HStack(spacing: 6) {
                if available {
                    Text(project.name).lineLimit(1)
                } else {
                    Text(project.name).foregroundStyle(.secondary).lineLimit(1)
                }
                Spacer(minLength: 4)
                titleRightSlot
            }
        }
    }

    /// Right side of the title line. Priority:
    /// 1. Spinner (scanning, after 250ms)
    /// 2. Session count (when DB readable)
    /// 3. Empty
    @ViewBuilder
    private var titleRightSlot: some View {
        if isScanning && showScanIndicator {
            ProgressView().controlSize(.small)
        } else if let count = unanalysed?.sessionCount {
            // Function: row metadata annotation (a count). Apple's role for
            // that is Footnote — let the system pick size, weight, line
            // height, Dynamic Type scaling. No overrides.
            Text("\(count)")
                .font(.footnote)
                .foregroundStyle(.tertiary)
        }
    }

    // MARK: - Subtitle line

    /// Subtitle line: prefix glyph + status text + optional tappable delta,
    /// with the cloud arrow right-aligned on the same line. Always renders
    /// something (even if a hidden placeholder) so row heights stay fixed —
    /// Mail/Notes/Finder convention.
    @ViewBuilder
    private var subtitleLine: some View {
        HStack(spacing: 4) {
            subtitleContent
            Spacer(minLength: 4)
            subtitleRightSlot
        }
    }

    @ViewBuilder
    private var subtitleContent: some View {
        // Subtitle text is uniformly `.secondary` per Apple's
        // `secondaryLabelColor` purpose: "subheading or additional
        // information." State is communicated by the prefix glyph and
        // its semantic colour (.red for failed, .orange for cantFind
        // warning) — not by graduating the text colour.
        switch subtitleVariant {
        case .failed(let summary):
            subtitleText(prefix: "exclamationmark.circle.fill",
                         prefixColor: .red,
                         text: summary,
                         style: .secondary)
        case .pipelineText(let text):
            subtitleText(prefix: nil, text: text, style: .secondary)
        case .cantFind(let text):
            subtitleText(prefix: "questionmark.folder",
                         prefixColor: .orange,
                         text: text,
                         style: .secondary)
        case .ready(let dateText, let delta):
            HStack(spacing: 4) {
                Text(dateText).font(.caption).foregroundStyle(.secondary)
                if let delta {
                    Text("·").font(.caption).foregroundStyle(.tertiary)
                    deltaSegment(delta)
                }
            }
        case .placeholder:
            // Hidden but layout-occupying so row heights remain consistent.
            Text(" ").font(.caption).hidden()
        }
    }

    /// Right-aligned subtitle slot — status glyph showing the project lives
    /// in iCloud, otherwise empty. Finder-esque placement.
    ///
    /// Uses the outline `icloud` (not `.fill`, not `.and.arrow.down`):
    /// status-only, no action attached. Matches Finder's sidebar treatment
    /// for cloud-managed locations — a quiet warning that opening the
    /// project may pause while macOS fetches evicted files. macOS handles
    /// the fetch transparently when the project is opened; no explicit
    /// download affordance for TF.
    @ViewBuilder
    private var subtitleRightSlot: some View {
        if case .inCloud = availability {
            Image(systemName: "icloud")
                .foregroundStyle(.secondary)
                .imageScale(.small)
        }
    }

    @ViewBuilder
    private func subtitleText(prefix: String?,
                              prefixColor: Color = .secondary,
                              text: String,
                              style: HierarchicalShapeStyle) -> some View {
        HStack(spacing: 4) {
            if let prefix {
                Image(systemName: prefix)
                    .foregroundStyle(prefixColor)
                    .imageScale(.small)
            }
            Text(text)
                .font(.caption)
                .foregroundStyle(style)
                .lineLimit(1)
        }
    }

    /// Tappable subtitle segment for the unanalysed delta. `Button` with
    /// `.buttonStyle(.plain)` — `.onTapGesture` on List-row content breaks
    /// selection on macOS 26 (see `desktop/CLAUDE.md` gotcha).
    @ViewBuilder
    private func deltaSegment(_ delta: SubtitleDelta) -> some View {
        switch delta {
        case .unanalysed(let count):
            Button(action: { onOpenUnanalysed?() }) {
                Text(deltaText(prefix: "unanalysedSubtitle", count: count))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            // Pointing-hand cursor is the native Mac affordance for inline
            // clickable text — no underline, no accent colour. Anchor-tag
            // styling belongs in the browser, not in native chrome.
            .onHover { hovering in
                if hovering { NSCursor.pointingHand.push() }
                else        { NSCursor.pop() }
            }
            .accessibilityHint(i18n.t("desktop.chrome.unanalysedSheetTitle",
                                      ["project": project.name]))
        case .missing(let count):
            Text(deltaText(prefix: "missingSubtitle", count: count))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    /// Pick singular vs plural key for a count-bearing delta phrase. Two-key
    /// shape (One/Other) because `I18n.swift` doesn't do CLDR-suffix lookup;
    /// some locales (fr/de/es) inflect on count=1 even for adjectival phrases.
    private func deltaText(prefix: String, count: Int) -> String {
        let key = count == 1
            ? "desktop.chrome.\(prefix)One"
            : "desktop.chrome.\(prefix)Other"
        return i18n.t(key, ["count": String(count)])
    }

    // MARK: - Rename field (unchanged from prior shape)

    @ViewBuilder
    private var renameField: some View {
        TextField("Project name", text: $editText)
            .textFieldStyle(.plain)
            .focused($isTextFieldFocused)
            .onSubmit { commitRename() }
            .onExitCommand { cancelRename() }
            .onAppear {
                editText = project.name
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                    isTextFieldFocused = true
                }
            }
            .onChange(of: isTextFieldFocused) { _, focused in
                if !focused && isRenaming { commitRename() }
            }
    }

    // MARK: - Subtitle variant + precedence

    /// One-of variants of the subtitle composition. The precedence chain
    /// collapses concurrent conditions into a single variant before we render.
    private enum SubtitleVariant {
        /// `.failed` pipeline state — ⚠ prefix + summary, no delta composition.
        case failed(summary: String)
        /// Verb-led pipeline state (running / stopped / partial / queued /
        /// unreachable) — text speaks; no prefix, no delta.
        case pipelineText(String)
        /// `.cantFind` availability — ❓ prefix + factual subtitle.
        case cantFind(String)
        /// `.ready` or `.inCloud` (or idle when project has analysis history) —
        /// bare date with optional single delta segment. Cloud arrow renders
        /// in the right slot independently.
        case ready(dateText: String, delta: SubtitleDelta?)
        /// Nothing to say — render a hidden placeholder to reserve height.
        case placeholder
    }

    private enum SubtitleDelta {
        case unanalysed(count: Int)
        case missing(count: Int)
    }

    /// Apply the precedence chain to the concurrent conditions to produce a
    /// single subtitle variant. The chain:
    /// 1. cantFind availability (volume issues — row is otherwise content-less)
    /// 2. failed pipeline state (surprising; needs visibility)
    /// 3. Other verb-led pipeline states (running / stopped / partial / queued)
    /// 4. ready + missing delta (data drift wins over feature gap)
    /// 5. ready + unanalysed delta
    /// 6. ready alone (bare date)
    /// 7. placeholder
    private var subtitleVariant: SubtitleVariant {
        // Availability beats everything when the project can't be reached.
        if case .cantFind = availability {
            if let text = availability.subtitle(using: i18n) {
                return .cantFind(text)
            }
            return .placeholder
        }

        // Pipeline-state subtitles.
        switch pipelineState {
        case .failed(let summary, _):
            return .failed(summary: summary)
        case .running:
            let key = isStoppingProgress
                ? "desktop.chrome.pipeline.stopping"
                : "desktop.chrome.pipeline.analysing"
            return .pipelineText(i18n.t(key))
        case .queued(let position):
            return .pipelineText(i18n.t(
                "desktop.chrome.pipeline.queuedPosition",
                ["position": String(position)]
            ))
        case .stopped:
            return .pipelineText(i18n.t("desktop.chrome.pipeline.stopped"))
        case .partial(let kind, _):
            let key = kind == "transcribe-only"
                ? "desktop.chrome.pipeline.transcribed"
                : "desktop.chrome.pipeline.partialRun"
            return .pipelineText(i18n.t(key))
        case .unreachable(let reason):
            return .pipelineText(reason)
        case .ready:
            // Source the date from `project.lastPipelineRunAt` rather than
            // the embedded PipelineState date so this arm and the
            // `.none/.scanning/.idle` fall-through arm agree on the
            // truth-source (the persisted project model).
            if let lastRun = project.lastPipelineRunAt {
                return .ready(dateText: formatBareDate(lastRun), delta: pickDelta())
            }
            return .placeholder
        case .none, .scanning, .idle:
            // No pipeline subtitle. If we have a last-run timestamp AND deltas,
            // fall through to a ready-style subtitle anchored on that date.
            if let lastRun = project.lastPipelineRunAt {
                return .ready(dateText: formatBareDate(lastRun), delta: pickDelta())
            }
            return .placeholder
        }
    }

    /// Per precedence: pick ONE delta. Missing wins over unanalysed
    /// (data drift > feature gap).
    private func pickDelta() -> SubtitleDelta? {
        guard let state = unanalysed else { return nil }
        if !state.missingFiles.isEmpty {
            return .missing(count: state.missingFiles.count)
        }
        if !state.newFiles.isEmpty {
            return .unanalysed(count: state.newFiles.count)
        }
        return nil
    }

    // MARK: - Date formatting (Schema A)

    /// Bare progressive coarsen — Just now / Today / Yesterday / D MMM /
    /// MMM YYYY. No verb prefix; the row's identity establishes that
    /// the date refers to "last analysed."
    ///
    /// Future-dated `date` (clock skew) skips the relative branches and goes
    /// straight to the absolute formatter — `RelativeDateTimeFormatter.named`
    /// would otherwise render "in 2 hours" on a "last analysed" subtitle.
    private func formatBareDate(_ date: Date) -> String {
        let appLocale = Locale(identifier: i18n.locale)
        let now = Date()
        let elapsed = now.timeIntervalSince(date)

        // Just now — under ~5 minutes. Future dates skip this branch.
        if elapsed >= 0 && elapsed < 5 * 60 {
            return i18n.t("desktop.chrome.dateRelativeJustNow")
        }

        let calendar = Calendar(identifier: .gregorian)
        // Future dates: always render absolute. Past dates use relative
        // names for today / yesterday.
        if elapsed >= 0 {
            if calendar.isDateInToday(date) || calendar.isDateInYesterday(date) {
                return relative(date, now: now, locale: appLocale)
            }
        }

        let nowYear = calendar.component(.year, from: now)
        let dateYear = calendar.component(.year, from: date)
        let f = DateFormatter()
        f.locale = appLocale
        if dateYear == nowYear {
            f.setLocalizedDateFormatFromTemplate("d MMM")
        } else {
            f.setLocalizedDateFormatFromTemplate("MMM yyyy")
        }
        return f.string(from: date)
    }

    /// Localised "today" / "yesterday" via Apple's named relative formatter.
    /// Leading-capitalise the first character to match sentence-start chrome
    /// — a no-op on CJK ideographs and Hangul (Unicode case folding leaves
    /// them untouched), so safe across all 6 locales.
    private func relative(_ date: Date, now: Date, locale: Locale) -> String {
        let f = RelativeDateTimeFormatter()
        f.locale = locale
        f.dateTimeStyle = .named
        f.unitsStyle = .full
        let s = f.localizedString(for: date, relativeTo: now)
        return s.prefix(1).uppercased() + s.dropFirst()
    }

    // MARK: - Pipeline state helpers

    private var isScanning: Bool {
        if case .scanning = pipelineState { return true }
        return false
    }

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
            guard project.id == projectID, isScanning else { return }
            showScanIndicator = true
        }
    }

    // MARK: - Tooltip (covers what the row doesn't show)

    /// Hover tooltip composes "6 interviews · 3 waiting, 1 missing" so the
    /// per-row precedence chain doesn't hide information from a user who
    /// goes looking for it.
    // PII: tooltip composition uses counts only — never interpolate
    // state.newFiles / missingFiles basenames here. Accessibility services
    // have system-wide read access; the watcher's "filenames stay UI-only"
    // invariant means rendered text only, no .help() / .accessibilityLabel.
    private var rowTooltip: String {
        var parts: [String] = []
        if let count = unanalysed?.sessionCount {
            parts.append(interviewCountText(count))
        }
        if let state = unanalysed {
            if !state.newFiles.isEmpty {
                parts.append(i18n.t("desktop.chrome.tooltipWaiting",
                                    ["count": String(state.newFiles.count)]))
            }
            if !state.missingFiles.isEmpty {
                parts.append(deltaText(prefix: "missingSubtitle",
                                       count: state.missingFiles.count))
            }
        }
        return parts.joined(separator: " · ")
    }

    /// Pick singular vs plural interview-count key. Some locales need the
    /// morphological split (en/es/fr/de); ko/ja use invariant counters
    /// but use the same two-key shape for consistency.
    private func interviewCountText(_ count: Int) -> String {
        let key = count == 1
            ? "desktop.chrome.interviewCountOne"
            : "desktop.chrome.interviewCountOther"
        return i18n.t(key, ["count": String(count)])
    }

    // MARK: - Accessibility

    private var accessibilityLabel: String {
        var label = project.name
        if !available {
            switch availability {
            case .cantFind(let reason):
                switch reason {
                case .unmountedVolume(let name), .networkUnreachable(let name):
                    label += ", \(i18n.t("desktop.chrome.projectUnavailable")), \(name)"
                case .moved, .missingBookmark:
                    label += ", \(i18n.t("desktop.chrome.projectMoved"))"
                }
            case .inCloud:
                label += ", \(i18n.t("desktop.availability.inCloud"))"
            case .ready:
                break
            }
        }
        // Always announce session count + deltas if present.
        if let count = unanalysed?.sessionCount {
            label += ", \(interviewCountText(count))"
        }
        if let state = unanalysed {
            if !state.newFiles.isEmpty {
                label += ", \(i18n.t("desktop.chrome.tooltipWaiting", ["count": String(state.newFiles.count)]))"
            }
            if !state.missingFiles.isEmpty {
                label += ", \(deltaText(prefix: "missingSubtitle", count: state.missingFiles.count))"
            }
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
