import SwiftUI

/// Diagnostic popover for a failure-shaped pipeline state — `.failed`,
/// `.completedPartial`, `.failedWithDiagnostic`. Extracted from
/// `PipelineActivityItem` so it can be presented from the sidebar row's failure
/// glyph (anchored to the project it describes), not only the toolbar pill.
///
/// Chrome (unchanged from the pill's design): status-as-title header + optional
/// "Show Log" + a Copy icon; a scrolling per-stage failure breakdown below. No
/// action row — Retry / Change provider / Re-analyse… live in the project's
/// natural run affordance + Settings. The reduced-fidelity `.failed` path (no
/// `PipelineSummary`) renders `degradedBody`.
///
/// The presenter supplies the size (`.padding(16).frame(width:360,height:320)`)
/// so the popover envelope matches wherever it's anchored. `showLog()` dismisses
/// via `@Environment(\.dismiss)`.
///
/// The static plaintext/overflow formatters below are the canonical home for the
/// copy-plaintext + overflow-plural logic — unit-tested directly.
struct ProjectDiagnosticPopover: View {
    let project: Project
    let state: PipelineState
    @ObservedObject var liveData: PipelineLiveData
    @EnvironmentObject var i18n: I18n
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text(headlineStatus).font(.headline)
                Spacer()
                if FileManager.default.fileExists(
                    atPath: PipelineRunner.logFileURL(for: project).path
                ) {
                    Button(i18n.t("desktop.pipeline.diagnostic.action.showLog")) {
                        showLog()
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .help(i18n.t("desktop.pipeline.diagnostic.action.showLogTooltip"))
                }
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

    private var headlineStatus: String {
        switch state {
        case .failed:
            return i18n.t("desktop.pipeline.status.headline.failed")
        case .completedPartial:
            return i18n.t("desktop.pipeline.diagnostic.header.completed_partial")
        case .failedWithDiagnostic:
            return i18n.t("desktop.pipeline.diagnostic.header.failed")
        default:
            return ""
        }
    }

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

    @ViewBuilder
    private func degradedBody(message: String, category: PipelineFailureCategory) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if !message.isEmpty {
                Text(message)
                    .font(.callout)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
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

    /// Reveal the per-project CLI log via LaunchServices (Console.app for most),
    /// then dismiss the popover. Apple-brokered handoff — works under App Sandbox.
    private func showLog() {
        NSWorkspace.shared.open(PipelineRunner.logFileURL(for: project))
        dismiss()
    }

    @ViewBuilder
    private func bucketsBody(summary: PipelineSummary) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            let buckets = summary.allBuckets.filter { !$0.outcome.failed.isEmpty }
            ForEach(Array(buckets.enumerated()), id: \.offset) { _, bucket in
                bucketGrid(name: bucket.name, outcome: bucket.outcome)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

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
                ForEach(Array(realFailures.enumerated()), id: \.0) { _, failure in
                    GridRow {
                        Image(systemName: MessageKind.error.symbolName)
                            .foregroundStyle(MessageKind.error.tint)
                            .font(.footnote)
                        Text(failure.sessionId ?? "")
                            .font(.system(.footnote, design: .monospaced))
                            .foregroundStyle(.secondary)
                        Text(failure.cause.message ?? failure.cause.category.rawValue)
                            .font(.footnote)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                if let overflow, let overflowMessage = overflow.cause.message,
                   !overflowMessage.isEmpty {
                    GridRow {
                        Image(systemName: MessageKind.warning.symbolName)
                            .foregroundStyle(MessageKind.warning.tint)
                            .font(.footnote)
                        Text("")
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

    /// Writes the plaintext diagnostic to the pasteboard. Silent copy — the
    /// native Mac pattern (Finder, Safari Copy URL). Dispatches on `state`.
    private func copyDiagnosticForCurrentState() {
        let text: String
        switch state {
        case .completedPartial(let summary):
            text = Self.formatDiagnosticPlaintext(
                summary: summary, projectName: project.name,
                projectPath: project.path, abandoned: false
            )
        case .failedWithDiagnostic(let summary):
            text = Self.formatDiagnosticPlaintext(
                summary: summary, projectName: project.name,
                projectPath: project.path, abandoned: true
            )
        case .failed(let message, let category):
            let tail = (liveData.outputLines[project.id] ?? []).suffix(20)
            text = Self.formatDiagnosticPlaintextDegraded(
                cause: message, category: category, projectName: project.name,
                projectPath: project.path, stdoutTail: Array(tail)
            )
        default:
            return
        }
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(text, forType: .string)
    }

    #if DEBUG
    private var isAllGlyphsSwatchMode: Bool {
        ProcessInfo.processInfo.environment[DiagnosticFixture.envVar] == "showcase_all_glyphs"
    }

    @ViewBuilder
    private var allGlyphsSwatch: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 6) {
            ForEach(MessageKind.allCases, id: \.rawValue) { kind in
                GridRow {
                    Image(systemName: kind.symbolName).foregroundStyle(kind.tint).font(.footnote)
                    Text(kind.rawValue).font(.footnote.weight(.medium))
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

    private var isAllStatesContextMode: Bool {
        ProcessInfo.processInfo.environment[DiagnosticFixture.envVar] == "showcase_all_states"
    }

    private struct DemoRow: Identifiable {
        let id: String
        let kind: MessageKind
        let sid: String
        let message: String
    }

    private var demoRows: [DemoRow] {
        [
            DemoRow(id: "1", kind: .success, sid: "s1", message: "OK"),
            DemoRow(id: "2", kind: .info, sid: "s2", message: "Cache hit on transcript hash"),
            DemoRow(id: "3", kind: .skipped, sid: "s3", message: "Already analysed; skipped this run"),
            DemoRow(id: "4", kind: .warning, sid: "s4",
                    message: "Audio quality below recommended threshold (16 kHz mono)"),
            DemoRow(id: "5", kind: .error, sid: "s5",
                    message: "Whisper transcription timed out after 600s"),
            DemoRow(id: "6", kind: .error, sid: "s6",
                    message: "Anthropic API returned 401: 'invalid_request_error: Your authentication credentials are invalid.' — verify your API key in Settings > LLM"),
            DemoRow(id: "7", kind: .warning, sid: "s7",
                    message: "Topic segmentation produced 0 topics — transcript likely too short or no clear topic boundaries detected"),
            DemoRow(id: "8", kind: .info, sid: "s8",
                    message: "Skipped re-transcription because the source file hash matches the cached transcript at .bristlenose/transcripts/s8.json — delete the cache to force re-run, or pass --rerun-stage transcribe"),
            DemoRow(id: "9", kind: .skipped, sid: "s9",
                    message: "No quotes extracted. The transcript was 8 minutes long but contained mostly back-channel cues (mmhm, yeah, right) without substantive content for quote mining."),
            DemoRow(id: "10", kind: .success, sid: "s100", message: "Transcribed in 23s"),
        ]
    }

    @ViewBuilder
    private var allStatesContext: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Text("Design-review sample").font(.callout.weight(.semibold))
                Text("(\(demoRows.count) states, real fonts)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("Every MessageKind rendered with the production popover's fonts and Grid layout. Production only shows .error and .warning rows; the others appear here for design assessment.")
                .font(.caption).foregroundStyle(.secondary)
            Grid(alignment: .topLeading, horizontalSpacing: 6, verticalSpacing: 4) {
                ForEach(demoRows) { row in
                    GridRow {
                        Image(systemName: row.kind.symbolName)
                            .foregroundStyle(row.kind.tint).font(.footnote)
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

    // MARK: - Static formatters (canonical home; unit-tested directly)

    /// Single source of truth for the human-readable failure-category string.
    static func humanCategoryLabel(_ category: PipelineFailureCategory) -> String {
        switch category {
        case .auth:       return "Provider key issue"
        case .network:    return "Network error"
        case .quota:      return "Rate limited"
        case .disk:       return "Out of disk space"
        case .whisper:    return "Transcription failed"
        case .userSignal: return "Stopped"
        case .apiRequest: return "Provider rejected request"
        case .apiServer:  return "Provider unavailable"
        case .missingDep: return "Setup needed"
        case .missingInput: return "Missing input"
        case .missingBinary: return "Missing tool"
        case .outputExists: return "Already analysed"
        case .outputTruncated: return "Output limit reached"
        case .unknown:    return "Failed"
        }
    }

    /// Extract the truncation count from the Python-emitted overflow message and
    /// render it via the active locale's CLDR plural form (Czech needs all of
    /// one/few/many/other). Falls back to the wire string when the regex misses.
    static func localisedOverflowText(message: String, i18n: I18n) -> String {
        guard let count = parseOverflowCount(from: message) else {
            return message
        }
        let base = "desktop.pipeline.diagnostic.overflow"
        let key = "\(base)_\(i18n.pluralCategory(count))"
        let rendered = i18n.t(key, ["count": String(count)])
        if rendered == key {
            return i18n.t("\(base)_other", ["count": String(count)])
        }
        return rendered
    }

    /// Parse `N` out of `"... and N more failures truncated"`. Returns nil for
    /// any wire shape that doesn't match — caller falls back to the raw string.
    static func parseOverflowCount(from message: String) -> Int? {
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

    /// Xcode "Copy Issue" pattern — plaintext, copy-pasteable. **English-only by
    /// design** (triager-greppable across reports); do NOT route through `i18n.t`.
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
        // Raw snake_case enum value is the triager-greppable form; do NOT humanise.
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
                    lines.append("  \(MessageKind.error.glyph) \(sid)  \(category)  \(message)")
                }
            }
            lines.append("")
        }
        return lines
            .joined(separator: "\n")
            .replacingOccurrences(of: projectPath, with: "<project>")
    }

    /// Degraded-fidelity variant for the `.failed` case (no `PipelineSummary`).
    /// Appends a stdout tail when populated. Same English-only triager shape.
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
