import SwiftUI

/// Trailing-toolbar activity pill (Xcode pattern) for the currently-selected
/// project's pipeline run. Visible only when state is `.running`, `.queued`,
/// or `.failed` — empty otherwise so the toolbar stays quiet.
///
/// Pill click opens a popover with stage detail, elapsed time, a Stop button,
/// a "Show technical details" disclosure with the last stdout lines, and (on
/// failure) Retry + Copy-error-details secondaries.
///
/// Plan §Phase 3 point 3. Deliberately a Swift-only display surface — does not
/// touch `ActivityStore` / `ActivityChipStack` (those are React-side).
struct PipelineActivityItem: View {
    let project: Project
    @ObservedObject var pipelineRunner: PipelineRunner
    /// Observed separately so progress/output mutations don't cascade to
    /// quieter `pipelineRunner.state` consumers (e.g. ProjectRow).
    @ObservedObject var liveData: PipelineLiveData
    @EnvironmentObject var i18n: I18n
    @State private var showPopover = false
    @State private var nowTick: Date = Date()

    private var state: PipelineState? { pipelineRunner.state[project.id] }
    private var progress: PipelineProgress? { liveData.progress[project.id] }

    /// The pill is hidden for steady-state projects (idle/scanning/ready).
    private var isVisible: Bool {
        switch state {
        case .running, .queued, .failed, .completedPartial, .failedWithDiagnostic:
            return true
        default: return false
        }
    }

    var body: some View {
        Group {
            if isVisible {
                pillBody
            } else {
                EmptyView()
            }
        }
        // `.task(id:)` is more reliable than `.onAppear` for toolbar items
        // — fires on first mount AND on project switch. `.onAppear` was
        // observed not firing on toolbar items in some macOS 26 builds.
        .task(id: project.id) { applyDebugFixtureIfNeeded() }
    }

    @ViewBuilder
    private var pillBody: some View {
        Button {
            showPopover.toggle()
        } label: {
            pillContent
        }
        .buttonStyle(.plain)
        .help(pillHelp)
            .popover(isPresented: $showPopover, arrowEdge: .bottom) {
                // Fixed height envelope so the disclosure expansion doesn't
                // trigger an animated NSPopover resize that fights SwiftUI
                // ProgressView constraint pass — caused a hard main-thread
                // livelock requiring force-quit (QA, 20 Apr 2026).
                popoverContent.padding(16).frame(width: 360, height: 320)
            }
            .task(id: showPopover) {
                // Tick once a second so elapsed time updates while popover is
                // open. The elapsed-time display only renders inside the
                // running popover body; gating on `showPopover` (rather than
                // `project.id` as before) means we don't wake every second
                // for every visible pill across the app lifecycle.
                guard showPopover else { return }
                while !Task.isCancelled {
                    nowTick = Date()
                    try? await Task.sleep(for: .seconds(1))
                }
            }
    }

    /// One-shot debug-only override that swaps the project's state to
    /// `.completedPartial` / `.failedWithDiagnostic` / `.failed` from a
    /// fixture scenario. No-op in Release and when the env var is unset.
    private func applyDebugFixtureIfNeeded() {
        #if DEBUG
        switch DiagnosticFixture.loadIfEnabled() {
        case .none, .clean:
            return
        case .partial(let summary):
            pipelineRunner._debugSetState(.completedPartial(summary: summary), for: project.id)
        case .failed(let summary):
            pipelineRunner._debugSetState(.failedWithDiagnostic(summary: summary), for: project.id)
        case .noSummary(let message, let category):
            // Synthesize a minimal bristlenose.log so the Log button is
            // exercised under the fixture path (real failures populate it
            // naturally; the harness has to do it by hand).
            writeSyntheticLogIfMissing()
            pipelineRunner._debugSetState(.failed(message, category: category), for: project.id)
        }
        #endif
    }

    #if DEBUG
    /// Write a 4-line stand-in `bristlenose.log` so the Log button's
    /// existence-guard fires in fixture mode. Skips if the file already
    /// exists — real runs own the log, the harness only seeds it.
    private func writeSyntheticLogIfMissing() {
        let logURL = PipelineRunner.logFileURL(for: project)
        let fm = FileManager.default
        guard !fm.fileExists(atPath: logURL.path) else { return }
        let parent = logURL.deletingLastPathComponent()
        try? fm.createDirectory(at: parent, withIntermediateDirectories: true)
        let body = [
            "INFO bristlenose 0.0.0 (fixture) — synthesised by DiagnosticFixture.failed_no_summary",
            "INFO this file stands in for a real CLI log so the popover's Log button has",
            "INFO something to open. Production runs write the real log here.",
            "INFO sidecar_exit reason=parent_death uptime_sec=0 original_ppid=1 current_ppid=1",
            "",
        ].joined(separator: "\n")
        try? body.write(to: logURL, atomically: true, encoding: .utf8)
    }
    #endif

    // MARK: - Pill content

    @ViewBuilder
    private var pillContent: some View {
        HStack(spacing: 6) {
            switch state {
            case .running:
                if let p = progress, p.isStopping {
                    Text("Stopping…")
                        .font(.system(.caption, design: .default).weight(.medium))
                } else if let p = progress, p.stageIndex == 0 {
                    Text("Starting…")
                        .font(.system(.caption, design: .default).weight(.medium))
                } else if let p = progress {
                    Text("Stage \(p.stageIndex) · \(p.stageName.isEmpty ? "Working…" : p.stageName)")
                        .font(.system(.caption, design: .default).weight(.medium))
                        .lineLimit(1)
                } else {
                    Text("Analysing…")
                        .font(.system(.caption).weight(.medium))
                }
                ProgressView().controlSize(.small)

            case .queued(let position):
                Image(systemName: "clock")
                    .imageScale(.small)
                Text("Queued · \(position)")
                    .font(.system(.caption).weight(.medium))

            case .failed:
                Image(systemName: "exclamationmark.circle.fill")
                    .foregroundStyle(.red)
                    .imageScale(.small)
                Text(failureCategoryLabel)
                    .font(.system(.caption).weight(.medium))

            case .completedPartial(let summary):
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                    .imageScale(.small)
                Text(diagnosticPillLabel(for: summary))
                    .font(.system(.caption).weight(.medium))

            case .failedWithDiagnostic(let summary):
                Image(systemName: "exclamationmark.circle.fill")
                    .foregroundStyle(.red)
                    .imageScale(.small)
                Text(diagnosticPillLabel(for: summary))
                    .font(.system(.caption).weight(.medium))

            default:
                EmptyView()
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(
            Capsule().fill(pillBackground)
        )
        .overlay(
            Capsule().stroke(Color.secondary.opacity(0.25), lineWidth: 0.5)
        )
        .contentShape(Capsule())
    }

    private var pillBackground: Color {
        // Chrome stays neutral; the state-coloured glyph + shape inside the
        // pill carries the severity signal. Per `feedback_colour_discipline`
        // — content owns colour, chrome doesn't. Mac toolbar pills (Xcode
        // activity, Safari indicator, Things 3) follow the same rule.
        Color.secondary.opacity(0.08)
    }

    private var pillHelp: String {
        switch state {
        case .running: return "Show pipeline progress for \(project.name)"
        case .queued: return "Pipeline run queued for \(project.name)"
        case .failed, .failedWithDiagnostic:
            return "Pipeline run failed for \(project.name)"
        case .completedPartial:
            return i18n.t(
                "desktop.pipeline.diagnostic.tooltip.completed_partial",
                ["project": project.name]
            )
        default: return ""
        }
    }

    private var failureCategoryLabel: String {
        guard case .failed(_, let category) = state else { return "Failed" }
        return Self.humanCategoryLabel(category)
    }

    /// Single source of truth for the human-readable category string used in
    /// the pill, the disclosure text, and the copied payload.
    static func humanCategoryLabel(_ category: PipelineFailureCategory) -> String {
        switch category {
        case .auth:       return "Provider key issue"
        case .network:    return "Network error"
        case .quota:      return "Rate limited"
        case .disk:       return "Out of disk space"
        case .whisper:    return "Transcription failed"
        // .userSignal: unreachable in practice — RunCancelledEvent maps
        // to .stopped, not .failed; kept for completeness.
        case .userSignal: return "Stopped"
        case .apiRequest: return "Provider rejected request"
        case .apiServer:  return "Provider unavailable"
        case .missingDep: return "Setup needed"
        case .missingInput: return "Missing input"
        case .missingBinary: return "Missing tool"
        case .outputExists: return "Already analysed"
        case .unknown:    return "Failed"
        }
    }

    // MARK: - Popover

    @ViewBuilder
    private var popoverContent: some View {
        // All failure-shaped states route through `unifiedPopoverBody` —
        // chrome is identical (status-as-title header, [Log][Copy] icons),
        // body branches on whether a `PipelineSummary` is available. The
        // legacy `.failed` popover was undesigned scaffolding; this
        // collapses both surfaces into the diagnostic-popover design.
        if case .completedPartial = state {
            unifiedPopoverBody()
        } else if case .failedWithDiagnostic = state {
            unifiedPopoverBody()
        } else if case .failed = state {
            unifiedPopoverBody()
        } else {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(project.name).font(.headline)
                    Spacer()
                    Text(headlineStatus)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if case .running = state, let p = progress {
                    runningPopoverBody(progress: p)
                } else if case .queued(let position) = state {
                    Text("Waiting for another project to finish (position \(position) in queue).")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var headlineStatus: String {
        switch state {
        case .running:
            if let p = progress, p.isStopping { return "Stopping" }
            return "Running"
        case .queued:  return "Queued"
        case .failed:  return "Failed"
        case .completedPartial:
            return i18n.t("desktop.pipeline.diagnostic.header.completed_partial")
        case .failedWithDiagnostic:
            return i18n.t("desktop.pipeline.diagnostic.header.failed")
        default: return ""
        }
    }

    @ViewBuilder
    private func runningPopoverBody(progress p: PipelineProgress) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if p.isStopping {
                Text("Stopping…")
                    .font(.callout)
                Text("Waiting for the analysis subprocess to exit.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else if p.attachedFromOrphan && p.stageIndex == 0 {
                Text("Resuming analysis (reconnected after app restart).")
                    .font(.callout)
                if !p.lastLine.isEmpty {
                    Text(p.lastLine)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            } else if p.stageIndex == 0 {
                Text("Starting up — loading models and validating credentials.")
                    .font(.callout)
            } else {
                Text(p.stageName.isEmpty ? "Working…" : p.stageName)
                    .font(.callout)
                Text("Stage \(p.stageIndex)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            HStack {
                Text("Elapsed: \(Self.format(elapsed: max(0, nowTick.timeIntervalSince(p.startedAt))))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button(p.isStopping ? "Stopping…" : "Stop", role: .destructive) {
                    pipelineRunner.cancel(project: project)
                    showPopover = false
                }
                .controlSize(.small)
                .disabled(p.isStopping)
            }
        }
    }

    // MARK: - Helpers

    private static func format(elapsed: TimeInterval) -> String {
        let total = Int(elapsed)
        let m = total / 60
        let s = total % 60
        return String(format: "%d:%02d", m, s)
    }

    // MARK: - Unified popover (.failed / .completedPartial / .failedWithDiagnostic)

    /// Pill label derived from `summary.dominantCategory()`. Falls back to
    /// the English raw value if the locale string is missing (i18n.t returns
    /// the raw key, which is fine for triagers).
    private func diagnosticPillLabel(for summary: PipelineSummary) -> String {
        let category = summary.dominantCategory()
        return i18n.t("desktop.pipeline.diagnostic.pill.\(category.rawValue)")
    }

    /// Single popover surface for every failure-shaped state. Chrome is
    /// identical across `.failed`, `.completedPartial`, `.failedWithDiagnostic`:
    /// status-as-title + optional Log button + Copy icon in the header;
    /// scrolling body below. The body switches between `bucketsBody` (when a
    /// `PipelineSummary` is in hand) and `degradedBody` (when only a
    /// summary string + category from older sidecars / orphan-`run_started`
    /// is available). No bottom action row anywhere — Retry / Change provider /
    /// Re-analyse… live in the project's natural run affordance + Settings.
    @ViewBuilder
    private func unifiedPopoverBody() -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text(headlineStatus).font(.headline)
                Spacer()
                if FileManager.default.fileExists(
                    atPath: PipelineRunner.logFileURL(for: project).path
                ) {
                    // Mac-canonical small bordered button — Apple's HIG
                    // popover example pattern (Calendar event info, Mail VIP
                    // popovers, etc.). Verb-first label ("Show Log") matches
                    // Apple's "Show in Finder" / "Show Package Contents"
                    // idiom for reveal-and-look gestures.
                    Button(i18n.t("desktop.pipeline.diagnostic.action.showLog")) {
                        showLog()
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .help(i18n.t("desktop.pipeline.diagnostic.action.showLogTooltip"))
                }
                // Copy as `.bordered .small` icon button — symmetric chrome
                // with Show Log, asymmetric content (one text, one glyph).
                // Apple's Finder window toolbar idiom: bordered icon-only
                // buttons next to bordered text buttons read as one button
                // bar at consistent visual weight.
                Button {
                    copyDiagnosticForCurrentState()
                } label: {
                    Image(systemName: "doc.on.doc")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help(i18n.t("desktop.pipeline.diagnostic.action.copy"))
            }
            ScrollView {
                #if DEBUG
                if isAllGlyphsSwatchMode {
                    allGlyphsSwatch
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else if isAllStatesContextMode {
                    allStatesContext
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    popoverBodyForCurrentState()
                }
                #else
                popoverBodyForCurrentState()
                #endif
            }
        }
    }

    /// Dispatch the scroll body content based on `state`. Pulled out of
    /// `unifiedPopoverBody`'s `ScrollView` so the DEBUG-vs-Release branch
    /// stays a one-liner per arm.
    @ViewBuilder
    private func popoverBodyForCurrentState() -> some View {
        switch state {
        case .completedPartial(let summary), .failedWithDiagnostic(let summary):
            bucketsBody(summary: summary)
        case .failed(let message, let category):
            degradedBody(message: message, category: category)
        default:
            EmptyView()
        }
    }

    /// Body for the `.failed` legacy / orphan path — `PipelineSummary` is
    /// not available, so we render EventLogReader's existing reader string,
    /// the localised "Detailed cause not captured." hint, and the human
    /// category label. No stdout tail in the visible body — stdout (when
    /// populated) flows into the Copy plaintext + lives in the on-disk log
    /// reachable via the Log button.
    @ViewBuilder
    private func degradedBody(
        message: String, category: PipelineFailureCategory
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if !message.isEmpty {
                Text(message)
                    .font(.callout)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                // Show "Detailed cause not captured." ONLY when there's no
                // message to show. Previously appended unconditionally, so it
                // rode under every real summary and made captured failures
                // (the cause IS in the event log + last-run-failure.log) read
                // as if nothing was captured. The Log button reaches the tail.
                Text(i18n.t("desktop.pipeline.diagnostic.noStructuredCause"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            Text("Category: \(Self.humanCategoryLabel(category))")
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Reveal the per-project CLI log file via macOS LaunchServices. Respects
    /// the user's default `.log` handler (Console.app for most). Apple-brokered
    /// handoff — works under App Sandbox without extra entitlements because
    /// LaunchServices vends the file across the process boundary.
    private func showLog() {
        let logURL = PipelineRunner.logFileURL(for: project)
        NSWorkspace.shared.open(logURL)
        showPopover = false
    }

    @ViewBuilder
    private func bucketsBody(summary: PipelineSummary) -> some View {
        // SwiftUI `Grid` for the per-row layout. Three columns:
        // glyph / session id / message. The message column flexes
        // and wraps within itself — continuation lines hang at the
        // message column, not back to column 0. Cross-row drag-
        // select is sacrificed; per-Text drag-select within any
        // single message still works, and Copy details covers the
        // all-of-it case.
        VStack(alignment: .leading, spacing: 10) {
            let buckets = summary.allBuckets.filter {
                !$0.outcome.failed.isEmpty
            }
            ForEach(Array(buckets.enumerated()), id: \.offset) {
                _, bucket in
                bucketGrid(name: bucket.name, outcome: bucket.outcome)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    #if DEBUG
    /// True when env var is set to `showcase_all_glyphs`. Branches the
    /// popover body into the 5-glyph reference card. Debug-only.
    private var isAllGlyphsSwatchMode: Bool {
        ProcessInfo.processInfo.environment[DiagnosticFixture.envVar]
            == "showcase_all_glyphs"
    }

    /// Reference card: every `MessageKind` rendered with its SF Symbol +
    /// tint + name + CLI Unicode glyph (for comparison with the Mac
    /// rendering). Pure visual; not interactive.
    @ViewBuilder
    private var allGlyphsSwatch: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 6) {
            ForEach(MessageKind.allCases, id: \.rawValue) { kind in
                GridRow {
                    Image(systemName: kind.symbolName)
                        .foregroundStyle(kind.tint)
                        .font(.footnote)
                    Text(kind.rawValue)
                        .font(.footnote.weight(.medium))
                    Text(kind.glyph)
                        .font(.system(.footnote, design: .monospaced))
                        .foregroundStyle(.secondary)
                    Text(kind.symbolName)
                        .font(.system(.caption2, design: .monospaced))
                        .foregroundStyle(.tertiary)
                }
            }
        }
    }

    /// True when env var is set to `showcase_all_states`. Renders the
    /// real popover layout (real fonts, real Grid, real columns, real
    /// spacing) with synthetic rows showing every `MessageKind` and a
    /// range of message lengths — for visual design assessment of the
    /// typographic ladder in-context. Production never sees `.success`
    /// / `.info` / `.skipped` rows in this popover.
    private var isAllStatesContextMode: Bool {
        ProcessInfo.processInfo.environment[DiagnosticFixture.envVar]
            == "showcase_all_states"
    }

    /// Synthetic rows used by `allStatesContext`. Mix of kinds and
    /// message lengths (short / medium / long-wrap / very-long-wrap).
    /// Pure visual fixture — not on any production path.
    private struct DemoRow: Identifiable {
        let id: String
        let kind: MessageKind
        let sid: String
        let message: String
    }

    private var demoRows: [DemoRow] {
        [
            // short
            DemoRow(id: "1", kind: .success, sid: "s1",
                    message: "OK"),
            DemoRow(id: "2", kind: .info, sid: "s2",
                    message: "Cache hit on transcript hash"),
            DemoRow(id: "3", kind: .skipped, sid: "s3",
                    message: "Already analysed; skipped this run"),
            // medium
            DemoRow(id: "4", kind: .warning, sid: "s4",
                    message: "Audio quality below recommended threshold (16 kHz mono)"),
            DemoRow(id: "5", kind: .error, sid: "s5",
                    message: "Whisper transcription timed out after 600s"),
            // long-wrap (real Anthropic-style error body)
            DemoRow(
                id: "6", kind: .error, sid: "s6",
                message: "Anthropic API returned 401: 'invalid_request_error: Your authentication credentials are invalid.' — verify your API key in Settings > LLM"),
            DemoRow(
                id: "7", kind: .warning, sid: "s7",
                message: "Topic segmentation produced 0 topics — transcript likely too short or no clear topic boundaries detected"),
            // very long
            DemoRow(
                id: "8", kind: .info, sid: "s8",
                message: "Skipped re-transcription because the source file hash matches the cached transcript at .bristlenose/transcripts/s8.json — delete the cache to force re-run, or pass --rerun-stage transcribe"),
            DemoRow(
                id: "9", kind: .skipped, sid: "s9",
                message: "No quotes extracted. The transcript was 8 minutes long but contained mostly back-channel cues (mmhm, yeah, right) without substantive content for quote mining."),
            // multi-digit sid to test column auto-sizing
            DemoRow(id: "10", kind: .success, sid: "s100",
                    message: "Transcribed in 23s"),
        ]
    }

    @ViewBuilder
    private var allStatesContext: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Text("Design-review sample")
                    .font(.callout.weight(.semibold))
                Text("(\(demoRows.count) states, real fonts)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text("Every MessageKind rendered with the production popover's fonts and Grid layout. Production only shows .error and .warning rows; the others appear here for design assessment.")
                .font(.caption)
                .foregroundStyle(.secondary)
            Grid(alignment: .topLeading, horizontalSpacing: 6, verticalSpacing: 4) {
                ForEach(demoRows) { row in
                    GridRow {
                        Image(systemName: row.kind.symbolName)
                            .foregroundStyle(row.kind.tint)
                            .font(.footnote)
                        Text(row.sid)
                            .font(.system(.footnote, design: .monospaced))
                            .foregroundStyle(.secondary)
                        Text(row.message)
                            .font(.footnote)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }
    #endif

    @ViewBuilder
    private func bucketGrid(
        name: PipelineSummary.BucketName, outcome: StageOutcome
    ) -> some View {
        let realFailures = outcome.failed.filter { !$0.isOverflowPlaceholder }
        let overflow = outcome.failed.first(where: { $0.isOverflowPlaceholder })

        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Text(name.rawValue.capitalized)
                    .font(.callout.weight(.semibold))
                Text("(\(outcome.succeeded)/\(outcome.attempted))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if realFailures.count > 2 {
                Text("\(realFailures.count) failures")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Grid(alignment: .topLeading, horizontalSpacing: 6, verticalSpacing: 4) {
                ForEach(Array(realFailures.enumerated()), id: \.0) {
                    _, failure in
                    GridRow {
                        Image(systemName: MessageKind.error.symbolName)
                            .foregroundStyle(MessageKind.error.tint)
                            .font(.footnote)
                        Text(failure.sessionId ?? "")
                            .font(.system(.footnote, design: .monospaced))
                            .foregroundStyle(.secondary)
                        Text(
                            failure.cause.message ?? failure.cause.category.rawValue
                        )
                        .font(.footnote)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                // Skip the overflow row entirely when there's no message —
                // a nil/empty message would render as a blank italic line
                // (the regex in `localisedOverflowText` doesn't match empty,
                // so it returns the empty string).
                if let overflow, let overflowMessage = overflow.cause.message,
                   !overflowMessage.isEmpty {
                    GridRow {
                        // Overflow placeholder is a truncation note, not a
                        // warning in its own right — the failures it's hiding
                        // already carry the red. But ⚠ + orange matches the
                        // CLI vocabulary and reads as "more than fits";
                        // muting via .secondary would underplay it. Filled
                        // orange triangle is the right inline weight.
                        Image(systemName: MessageKind.warning.symbolName)
                            .foregroundStyle(MessageKind.warning.tint)
                            .font(.footnote)
                        Text("")  // empty sid cell preserves column alignment
                        Text(Self.localisedOverflowText(
                            message: overflowMessage, i18n: i18n
                        ))
                        .font(.footnote.italic())
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }

    /// Extract the truncation count from the Python-emitted overflow
    /// message ("... and N more failures truncated") and render via the
    /// CLDR plural key (`overflow_one` / `overflow_other`). Falls back to
    /// the wire string when the regex doesn't match — guards against
    /// future Python-side wording changes.
    ///
    /// Python keeps the wire shape as a single human-readable string
    /// rather than emitting a structured sentinel; the Swift side does the
    /// per-locale rendering. If/when more callers need this, lift to a
    /// shared helper. For now it lives on the only consumer.
    static func localisedOverflowText(message: String, i18n: I18n) -> String {
        guard let count = parseOverflowCount(from: message) else {
            return message
        }
        let key = count == 1
            ? "desktop.pipeline.diagnostic.overflow_one"
            : "desktop.pipeline.diagnostic.overflow_other"
        return i18n.t(key, ["count": String(count)])
    }

    /// Parse `N` out of `"... and N more failures truncated"`.
    /// Internal so tests can call directly. Returns `nil` for any wire
    /// shape that doesn't match — caller falls back to the raw string.
    static func parseOverflowCount(from message: String) -> Int? {
        // Python source: `bristlenose/events.py::_truncate_failed` emits
        // `f"... and {dropped} more failures truncated"`. Match the digits
        // following "and ". Permissive — tolerates leading/trailing
        // whitespace and unicode-ellipsis vs. three-dot prefix.
        let pattern = #"and\s+(\d+)\s+more"#
        guard let regex = try? NSRegularExpression(pattern: pattern),
              let match = regex.firstMatch(
                in: message,
                range: NSRange(message.startIndex..., in: message)),
              match.numberOfRanges >= 2,
              let range = Range(match.range(at: 1), in: message),
              let count = Int(message[range])
        else { return nil }
        return count
    }

    /// Writes the plaintext diagnostic to the system pasteboard. No flip /
    /// "Copied" affordance — silent copy is the native Mac pattern (Finder,
    /// Safari Copy URL). Users find feedback channels via app + website +
    /// GitHub rather than an in-popover mailto.
    ///
    /// Dispatches on `state`: `.failedWithDiagnostic` / `.completedPartial`
    /// → structured `formatDiagnosticPlaintext`; `.failed` →
    /// `formatDiagnosticPlaintextDegraded` with `liveData.outputLines` tail.
    private func copyDiagnosticForCurrentState() {
        let text: String
        switch state {
        case .completedPartial(let summary):
            text = Self.formatDiagnosticPlaintext(
                summary: summary,
                projectName: project.name,
                projectPath: project.path,
                abandoned: false
            )
        case .failedWithDiagnostic(let summary):
            text = Self.formatDiagnosticPlaintext(
                summary: summary,
                projectName: project.name,
                projectPath: project.path,
                abandoned: true
            )
        case .failed(let message, let category):
            let tail = (liveData.outputLines[project.id] ?? []).suffix(20)
            text = Self.formatDiagnosticPlaintextDegraded(
                cause: message,
                category: category,
                projectName: project.name,
                projectPath: project.path,
                stdoutTail: Array(tail)
            )
        default:
            return
        }
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(text, forType: .string)
    }

    /// Xcode "Copy Issue" pattern — plaintext, monospace-safe, copy-pasteable.
    /// Pure (static) so tests can snapshot without instantiating the view.
    /// See `docs/design-pipeline-diagnostic-popover.md` lines 112-123.
    ///
    /// **English-only by design.** The plaintext is for triagers + the
    /// `support@bristlenose.app` inbox; field labels are greppable across
    /// reports. Do NOT route these strings through `i18n.t()`.
    static func formatDiagnosticPlaintext(
        summary: PipelineSummary,
        projectName: String,
        projectPath: String,
        abandoned: Bool
    ) -> String {
        var lines: [String] = []
        let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?"
        let os = ProcessInfo.processInfo.operatingSystemVersionString
        lines.append("Bristlenose \(appVersion) (\(build)) on \(os)")
        lines.append("Project: \(projectName)")
        lines.append("Outcome: \(abandoned ? "Run failed" : "Partial completion")")
        // snake_case raw enum value (e.g. `missing_binary`, `user_signal`) is
        // emitted deliberately — this is the triager-greppable form. Do NOT
        // map through `humanCategoryLabel` here; that would humanise the
        // string for end-users at the cost of making support tickets harder
        // to grep across users' reports. See "Outcome:" comment above —
        // same English-only-by-design principle.
        lines.append("Dominant category: \(summary.dominantCategory().rawValue)")
        lines.append("")

        for (name, outcome) in summary.allBuckets where !outcome.failed.isEmpty {
            let durationSec = max(0, outcome.durationMs / 1000)
            let m = durationSec / 60
            let s = durationSec % 60
            lines.append(
                "Stage: \(name.rawValue)  "
                + "(\(outcome.succeeded)/\(outcome.attempted) succeeded, "
                + "\(m)m \(s)s)"
            )
            for failure in outcome.failed {
                if failure.isOverflowPlaceholder {
                    lines.append("  \(MessageKind.warning.glyph) \(failure.cause.message ?? "")")
                } else {
                    let sid = failure.sessionId ?? "—"
                    let category = failure.cause.category.rawValue
                    let message = failure.cause.message ?? ""
                    lines.append(
                        "  \(MessageKind.error.glyph) \(sid)  \(category)  \(message)"
                    )
                }
            }
            lines.append("")
        }
        // Sanitise absolute project path before returning so a hastily-emailed
        // log doesn't leak folder structure.
        return lines
            .joined(separator: "\n")
            .replacingOccurrences(of: projectPath, with: "<project>")
    }

    /// Degraded-fidelity variant of `formatDiagnosticPlaintext` for the
    /// `.failed` case (older sidecars / orphan-`run_started` paths where no
    /// `PipelineSummary` exists). Same English-only triager-greppable shape;
    /// appends a stdout tail when `liveData.outputLines` is populated (which
    /// it is for crash-style failures before the events log gets a terminus).
    static func formatDiagnosticPlaintextDegraded(
        cause: String,
        category: PipelineFailureCategory,
        projectName: String,
        projectPath: String,
        stdoutTail: [String]
    ) -> String {
        var lines: [String] = []
        let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?"
        let os = ProcessInfo.processInfo.operatingSystemVersionString
        lines.append("Bristlenose \(appVersion) (\(build)) on \(os)")
        lines.append("Project: \(projectName)")
        lines.append("Outcome: Run failed (no terminus event)")
        // Raw enum token — same grepability principle as the structured form.
        lines.append("Category: \(category.rawValue)")
        if !cause.isEmpty {
            lines.append("Cause: \(cause)")
        }
        if !stdoutTail.isEmpty {
            lines.append("")
            lines.append("Last output:")
            lines.append(stdoutTail.joined(separator: "\n"))
        }
        return lines
            .joined(separator: "\n")
            .replacingOccurrences(of: projectPath, with: "<project>")
    }
}

