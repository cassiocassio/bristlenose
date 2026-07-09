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
/// **Precedence chain for the subtitle** lives in the pure, testable
/// `ProjectSubtitle.resolve` (see memory `feedback_exception_precedence_chain`
/// and `docs/design-desktop-project-status.md` §5): cantFind (availability) >
/// failed > running > stopped/partial > ready+missing > ready+unanalysed >
/// ready (bare date). One state per row; we don't stack errors. Tooltips carry
/// the full picture.
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
    /// Per-project watcher state — session count + unanalysed/missing deltas.
    /// Nil before the first folder scan resolves (or when the project has no
    /// watcher entry). An in-flight copy is surfaced via `copyFraction` + the
    /// resolver's precedence (copying outranks the deltas), not by nil-ing this.
    let unanalysed: UnanalysedState?
    /// Display state of a drag-import copy landing files in THIS project, or nil
    /// when no copy targets it. Computed at the call site from
    /// `CopyMachinery.inFlight` (matched by `projectID`) so the row re-renders as
    /// the byte fraction ticks. Drives the "Copying · N%" / "Cancelling…"
    /// subtitle *and* the trailing determinate ring — the row is copy's only
    /// surface (the toolbar copy pill was removed; per-project ops live on the
    /// row, app-global ops in the title-bar pill — §4 placement axis).
    let copyState: CopyDisplay?
    /// Cancels the in-flight copy into this project. Wired to the trailing ring's
    /// hover-× and the row's "Cancel copy" context-menu item (the latter keeps
    /// cancel reachable for keyboard / VoiceOver, mirroring run-Stop). Nil when
    /// no cancellable copy is in flight.
    let onCancelCopy: (() -> Void)?
    /// Called when the user taps the `+N unanalysed` subtitle segment. Caller
    /// opens the `NewFilesSheet` in watcher mode.
    let onOpenUnanalysed: (() -> Void)?
    /// Called when the user clicks the failure glyph (or picks "Show
    /// Diagnostics…"). Caller selects the row + flips `isShowingDiagnostics`.
    let onShowDiagnostics: (() -> Void)?
    /// Drives the glyph-anchored diagnostic popover. Owned by ContentView
    /// (keyed to the selected diagnostic project) so the context-menu backstop
    /// can open the same popover.
    @Binding var isShowingDiagnostics: Bool

    @EnvironmentObject var i18n: I18n
    @EnvironmentObject var pipelineRunner: PipelineRunner
    @EnvironmentObject var projectIndex: ProjectIndex
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
        copyState: CopyDisplay? = nil,
        onCancelCopy: (() -> Void)? = nil,
        onRename: @escaping (String) -> Void,
        onShowInFinder: @escaping () -> Void,
        onDelete: @escaping () -> Void,
        onLocate: (() -> Void)? = nil,
        onOpenUnanalysed: (() -> Void)? = nil,
        onShowDiagnostics: (() -> Void)? = nil,
        isShowingDiagnostics: Binding<Bool> = .constant(false)
    ) {
        self.project = project
        self._isRenaming = isRenaming
        self.isDropTarget = isDropTarget
        self.unanalysed = unanalysed
        self.copyState = copyState
        self.onCancelCopy = onCancelCopy
        self.onRename = onRename
        self.onShowInFinder = onShowInFinder
        self.onDelete = onDelete
        self.onLocate = onLocate
        self.onOpenUnanalysed = onOpenUnanalysed
        self.onShowDiagnostics = onShowDiagnostics
        self._isShowingDiagnostics = isShowingDiagnostics
        self._liveData = ObservedObject(wrappedValue: liveData)
    }

    var body: some View {
        // Baseline-align the identity icon to the *title* (not centred across
        // the two-line row), so it reads as belonging to the project name
        // rather than floating between the title and the status line. SF
        // Symbols baseline-align with adjacent text by design.
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            leadingIcon
            VStack(alignment: .leading, spacing: 1) {
                titleLine
                subtitleLine
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .help(rowTooltip)
        // Extend hit region vertically into the SwiftUI List inter-row gap.
        // SidebarDropDelegate hit-tests via the row's rendered frame, so
        // padding here widens the captured rectangle and stops gap-drops
        // between sibling rows from routing to the List-level URL fallback
        // (which would create the project at root instead of inside the
        // surrounding folder). Symmetric with FolderRow.
        .padding(.vertical, 2)
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
        // by overwriting the chosen icon. A just-created project that was
        // auto-assigned a random icon plays a one-shot tumble reveal.
        let name = project.icon ?? IconPickerPopover.defaultIcon
        TumblingProjectIcon(
            symbol: name,
            dimmed: !available,
            reveal: projectIndex.pendingIconReveal == project.id,
            onRevealComplete: { projectIndex.consumeIconReveal(project.id) }
        )
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
        //
        // `resolve` arbitrates the precedence; this switch only *renders* the
        // winner — i18n + date formatting live here, not in the resolver.
        switch subtitleVariant {
        case .cantFind:
            // `resolve` returns `.cantFind` exactly when `availability` is
            // `.cantFind`, so we derive the reason-aware glyph + factual text
            // from `availability` directly. cantFind's subtitle is always
            // non-nil; the placeholder arm is defensive.
            if let text = availability.subtitle(using: i18n) {
                subtitleText(prefix: availability.sfSymbolName ?? "questionmark.folder",
                             prefixColor: .orange,
                             text: text,
                             style: .secondary)
            } else {
                Text(" ").font(.caption).hidden()
            }
        case .failed(let summary):
            diagnosticSubtitle(kind: .error, text: summary)
        case .failedDiagnostic:
            // Sidebar is the attention surface, not the detail surface —
            // budget is ~22 EN chars before DE/ES/FR swell truncates. The
            // toolbar pill carries the dominant category + count; the sidebar
            // row just says "row needs your eyes". Per
            // `feedback_sidebar_is_attention_not_affordance`.
            diagnosticSubtitle(kind: .error,
                               text: i18n.t("desktop.pipeline.diagnostic.header.failed"))
        case .completedPartial:
            diagnosticSubtitle(kind: .warning,
                               text: i18n.t("desktop.pipeline.diagnostic.header.completed_partial"))
        case .stopping, .running, .queued, .stopped, .partial, .unreachable,
             .addingInterviews, .copying, .copyCancelling:
            subtitleText(prefix: nil,
                         text: pipelineActivityText(subtitleVariant, separator: " · ") ?? "",
                         style: .secondary)
        case .ready(let date, let delta):
            HStack(spacing: 4) {
                Text(formatBareDate(date)).font(.caption).foregroundStyle(.secondary)
                if let delta {
                    Text("·").font(.caption).foregroundStyle(.tertiary)
                    deltaSegment(delta)
                }
            }
        case .deltaOnly(let delta):
            // Delta without a date anchor (legacy / CLI-analysed project).
            // No middle-dot separator since there's nothing on the left to
            // separate from.
            deltaSegment(delta)
        case .placeholder:
            // Hidden but layout-occupying so row heights remain consistent.
            Text(" ").font(.caption).hidden()
        }
    }

    /// Localised visible text for the verb-led pipeline-activity variants.
    /// `separator` is " · " for the row, ", " for VoiceOver (commas read as
    /// pauses). Returns nil for non-activity variants — those are rendered
    /// (and voiced) through other paths. Single source for both the visible
    /// subtitle and the accessibility phrase, so their wording can't drift.
    private func pipelineActivityText(_ variant: SubtitleVariant, separator: String) -> String? {
        switch variant {
        case .stopping:
            return i18n.t("desktop.chrome.pipeline.stopping")
        case .running:
            return runningSubtitle(separator: separator)
        case .queued(let position):
            return i18n.t("desktop.chrome.pipeline.queuedPosition",
                          ["position": String(position)])
        case .stopped:
            return i18n.t("desktop.chrome.pipeline.stopped")
        case .partial(let transcribeOnly):
            return i18n.t(transcribeOnly
                ? "desktop.chrome.pipeline.transcribed"
                : "desktop.chrome.pipeline.partialRun")
        case .unreachable(let reason):
            return reason
        case .addingInterviews(let count):
            return i18n.plural("desktop.chrome.addingInterviews", count: count)
        case .copying(let fraction):
            // Byte-% (no file-item "N of M" source exists). "%" placement is
            // per-locale in the string; the number is a 0…100 int (no grouping
            // below 1000, so no locale formatting needed).
            let percent = min(100, max(0, Int((fraction * 100).rounded())))
            return i18n.t("desktop.chrome.pipeline.copying", ["percent": String(percent)])
        case .copyCancelling:
            return i18n.t("desktop.chrome.copyCancelling")
        case .cantFind, .failed, .failedDiagnostic, .completedPartial,
             .ready, .deltaOnly, .placeholder:
            return nil
        }
    }

    /// Right-aligned subtitle slot. Precedence: per-project run activity wins,
    /// then an in-flight copy (the determinate ring + hover-cancel — copy's home
    /// now that the toolbar pill is gone), then the iCloud status glyph, then
    /// empty.
    ///
    /// The activity indicator carries the *motion* signal for an in-flight run
    /// or copy (the determinate ring; hover swaps it for a cancel ×). The cloud
    /// glyph is the outline `icloud` (not `.fill`, not `.and.arrow.down`):
    /// status-only, no action attached — Finder's treatment for cloud-managed
    /// locations. macOS fetches evicted files transparently on open; no explicit
    /// download affordance for TF. Run, copy, and iCloud-eviction are mutually
    /// exclusive in practice, but the precedence keeps it honest either way.
    @ViewBuilder
    private var subtitleRightSlot: some View {
        let activity = ProjectRowActivityIndicator.Kind.from(
            pipelineState: pipelineState,
            progress: liveData.progress[project.id]
        )
        if activity != .none {
            ProjectRowActivityIndicator(
                kind: activity,
                onStop: { pipelineRunner.cancel(project: project) }
            )
        } else if let copyState {
            // Copy is a per-project op, so its progress + cancel live on the row
            // (not a global title-bar pill). Determinate ring + hover-cancel
            // while copying; an indeterminate spinner during the cancel rollback
            // (the × is gone — you can't cancel a cancel).
            switch copyState {
            case .copying(let fraction):
                ProjectRowActivityIndicator(
                    kind: .copying(fraction: fraction),
                    onStop: onCancelCopy
                )
            case .cancelling:
                ProgressView()
                    .controlSize(.small)
                    .frame(width: 16, height: 16)
                    .accessibilityHidden(true)
            }
        } else if case .inCloud = availability {
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

    /// Failure-family subtitle: a clickable `MessageKind` glyph (xmark/red for
    /// failures, triangle/orange for partial — the canonical taxonomy) that
    /// opens the diagnostic popover anchored to itself, plus the summary text.
    /// The glyph is a `Button(.plain)` with pointing-hand hover (the `+N`
    /// pattern) — mouse-only; VoiceOver hears the state via `accessibilityLabel`
    /// and reaches diagnostics via the row context menu.
    @ViewBuilder
    private func diagnosticSubtitle(kind: MessageKind, text: String) -> some View {
        HStack(spacing: 4) {
            Button {
                onShowDiagnostics?()
            } label: {
                Image(systemName: kind.symbolName)
                    .foregroundStyle(kind.tint)
                    .imageScale(.small)
            }
            .buttonStyle(.plain)
            .onHover { hovering in
                if hovering { NSCursor.pointingHand.push() } else { NSCursor.pop() }
            }
            .popover(isPresented: $isShowingDiagnostics, arrowEdge: .trailing) {
                if let state = pipelineState {
                    ProjectDiagnosticPopover(
                        project: project, state: state, liveData: liveData
                    )
                    .padding(16)
                    .frame(width: 360, height: 320)
                }
            }
            .accessibilityHidden(true)
            Text(text)
                .font(.caption)
                .foregroundStyle(.secondary)
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

    /// Render a count-bearing chrome phrase using the active locale's CLDR
    /// plural category (one/few/many/other). Czech needs all four; en/es/fr/de
    /// carry one+other; ko/ja carry only other. The `_other` fallback for an
    /// absent stem lives in `I18n.plural`.
    private func deltaText(prefix: String, count: Int) -> String {
        i18n.plural("desktop.chrome.\(prefix)", count: count)
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

    /// The arbitrated subtitle state for this row. The cross-source precedence
    /// chain lives in the pure, unit-tested `ProjectSubtitle.resolve`; this
    /// property only marshals the row's inputs. (`subtitleContent` renders the
    /// winner — i18n + date formatting happen there, not in the resolver.)
    private var subtitleVariant: SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: availability,
            pipelineState: pipelineState,
            isStopping: isStoppingProgress,
            // The flag-OFF SwiftUI row (being deleted at cutover) doesn't wire the
            // Adding-interviews gesture store — that lives on the AppKit sidebar.
            addingCount: nil,
            copy: copyState,
            lastRunAt: project.lastPipelineRunAt,
            missingCount: unanalysed?.missingFiles.count ?? 0,
            unanalysedCount: unanalysed?.newFiles.count ?? 0
        )
    }

    /// Compose the in-flight progress subtitle from the live `run_progress`
    /// ladder (stage · N of M · ETA), via the pure `RunProgressSubtitle` helper.
    /// `separator` is " · " for the visible row, ", " for the VoiceOver phrase.
    /// Callers handle the stopping case first (it outranks progress).
    private func runningSubtitle(separator: String) -> String {
        let p = liveData.progress[project.id]
        return RunProgressSubtitle.compose(
            stage: p?.stage,
            sessionsComplete: p?.sessionsComplete,
            sessionsTotal: p?.sessionsTotal,
            etaRemainingSeconds: p?.etaRemainingSeconds,
            resuming: p?.attachedFromOrphan ?? false,
            separator: separator,
            localize: { i18n.t($0, $1) }
        )
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
        // While a run is in flight, lead with the full (untruncated) progress
        // ladder so the one-line subtitle — which truncates the full form on a
        // narrow column — is recoverable on hover. Progress fields are
        // counts/timings only (RunProgressEvent is PII-free), so this keeps the
        // tooltip's "counts only, never filenames" invariant.
        if case .running = pipelineState, !isStoppingProgress {
            parts.append(runningSubtitle(separator: " · "))
        }
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

    /// Pick the interview-count form via the locale's CLDR plural category.
    /// Routes through `deltaText` so every chrome count string shares one
    /// plural-selection path (cs needs one/few/many/other, not a binary split).
    private func interviewCountText(_ count: Int) -> String {
        deltaText(prefix: "interviewCount", count: count)
    }

    // MARK: - Accessibility

    /// The arbitrated subtitle, rendered as words for VoiceOver — derived from
    /// the *same* `subtitleVariant` the sighted row shows, so the spoken and
    /// visible states can't drift (and can't compose two conditions onto one
    /// line). Returns nil for `.cantFind` / `.ready` / `.deltaOnly` /
    /// `.placeholder`: availability and the count/delta segments are voiced
    /// separately in `accessibilityLabel`.
    private var pipelineStateAccessibilityPhrase: String? {
        let variant = subtitleVariant
        switch variant {
        case .failed(let summary):
            return summary
        case .failedDiagnostic:
            return i18n.t("desktop.pipeline.diagnostic.header.failed")
        case .completedPartial:
            return i18n.t("desktop.pipeline.diagnostic.header.completed_partial")
        case .stopping, .running, .queued, .stopped, .partial, .unreachable,
             .addingInterviews, .copying, .copyCancelling:
            // Comma separator: VoiceOver reads commas as pauses
            // ("Transcribing, 7 of 8, ~1 min left"); "·" doesn't.
            return pipelineActivityText(variant, separator: ", ")
        case .cantFind, .ready, .deltaOnly, .placeholder:
            return nil
        }
    }

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
        // Pipeline state — the visible subtitle carries this for sighted
        // users, but this combined label overrides children, so VoiceOver
        // would otherwise never hear "Analysing…", "Queued", "Failed".
        if let phrase = pipelineStateAccessibilityPhrase {
            label += ", \(phrase)"
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
