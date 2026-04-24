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
    @State private var showPopover = false
    @State private var nowTick: Date = Date()

    private var state: PipelineState? { pipelineRunner.state[project.id] }
    private var progress: PipelineProgress? { liveData.progress[project.id] }

    /// The pill is hidden for steady-state projects (idle/scanning/ready).
    private var isVisible: Bool {
        switch state {
        case .running, .queued, .failed: return true
        default: return false
        }
    }

    var body: some View {
        if isVisible {
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
            .task(id: project.id) {
                // Tick once a second so elapsed time updates while popover is
                // open. Cancelled when project changes or view disappears.
                while !Task.isCancelled {
                    nowTick = Date()
                    try? await Task.sleep(for: .seconds(1))
                }
            }
        }
    }

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
        if case .failed = state {
            return Color.red.opacity(0.08)
        }
        return Color.secondary.opacity(0.08)
    }

    private var pillHelp: String {
        switch state {
        case .running: return "Show pipeline progress for \(project.name)"
        case .queued: return "Pipeline run queued for \(project.name)"
        case .failed: return "Pipeline run failed for \(project.name)"
        default: return ""
        }
    }

    private var failureCategoryLabel: String {
        guard case .failed(_, let category) = state else { return "Failed" }
        switch category {
        case .auth:    return "Provider key issue"
        case .network: return "Network error"
        case .quota:   return "Rate limited"
        case .disk:    return "Out of disk space"
        case .whisper: return "Transcription failed"
        case .unknown: return "Failed"
        }
    }

    // MARK: - Popover

    @ViewBuilder
    private var popoverContent: some View {
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
            } else if case .failed(let summary, let category) = state {
                failedPopoverBody(summary: summary, category: category)
            }

            DisclosureGroup("Show technical details") {
                technicalDetails
            }
            .font(.caption)
        }
    }

    private var headlineStatus: String {
        switch state {
        case .running:
            if let p = progress, p.isStopping { return "Stopping" }
            return "Running"
        case .queued:  return "Queued"
        case .failed:  return "Failed"
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

    @ViewBuilder
    private func failedPopoverBody(summary: String, category: PipelineFailureCategory) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(summary).font(.callout)
            HStack(spacing: 8) {
                Button("Retry") {
                    pipelineRunner.start(project: project)
                    showPopover = false
                }
                .keyboardShortcut(.defaultAction)
                Button("Copy error details") {
                    copyErrorDetails()
                }
                if category == .auth {
                    Spacer()
                    // Deeplink to Settings — opens the native Settings scene.
                    // The LLM tab is the default tab so we don't need a sub-route.
                    Button("Change provider") {
                        NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                        showPopover = false
                    }
                }
            }
        }
    }

    private var technicalDetails: some View {
        let lines = liveData.outputLines[project.id] ?? []
        let tail = lines.suffix(20)
        return ScrollView {
            Text(tail.joined(separator: "\n"))
                .font(.system(.caption2, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
        }
        .frame(maxHeight: 140)
    }

    // MARK: - Helpers

    private func copyErrorDetails() {
        let lines = liveData.outputLines[project.id] ?? []
        // Pre-pasteboard sanitisation: replace project path with a sentinel so
        // a hastily-emailed log doesn't leak the user's folder structure.
        let sanitised = lines
            .joined(separator: "\n")
            .replacingOccurrences(of: project.path, with: "<project>")
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(sanitised, forType: .string)
    }

    private static func format(elapsed: TimeInterval) -> String {
        let total = Int(elapsed)
        let m = total / 60
        let s = total % 60
        return String(format: "%d:%02d", m, s)
    }
}
