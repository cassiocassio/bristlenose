import SwiftUI

/// Native Health window (Diagnostics ▸ Check Health). Fetches the local system
/// checks from the serve endpoint `GET /api/doctor` and renders them as a
/// native column-aligned checklist.
///
/// Rendering reuses the `Grid` *pattern* from `ProjectDiagnosticPopover`
/// (glyph · label · flexing wrapping detail, with a hanging secondary
/// continuation) so a health row in the app looks like a doctor line in the
/// terminal — same `MessageKind` glyph/tint vocabulary, shared CLI ↔ Mac.
///
/// It talks to the serve over plain HTTP with the bearer token from
/// `ServeManager` — no web bridge involved. `/api/doctor` is NOT auth-exempt
/// (it exposes env detail), so the token is required.
///
/// English-only, matching the Diagnostics menu that opens it (and `doctor.py`,
/// which is English-only in alpha).
struct DoctorReportView: View {
    @EnvironmentObject var serveManager: ServeManager
    @State private var loadState: LoadState = .loading

    enum LoadState: Equatable {
        case loading
        case loaded(DoctorReport)
        /// No serve process is running (no project open yet).
        case unavailable
        case failed(String)
    }

    var body: some View {
        // No in-content title — the `Window("System Health", …)` scene already
        // paints it in the title bar. Actions live in the window toolbar (the
        // Console.app / Activity Monitor idiom), not a hand-rolled header band.
        content
            .frame(minWidth: 420, minHeight: 320)
            .toolbar {
                ToolbarItemGroup(placement: .primaryAction) {
                    Button {
                        if let report = loadedReport { copyPlaintext(report) }
                    } label: {
                        Image(systemName: "doc.on.doc")
                    }
                    .help("Copy health report")
                    .disabled(loadedReport == nil)

                    Button {
                        Task { await load() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .help("Re-run the checks")
                    .disabled(loadState == .loading)
                }
            }
            .task { await load() }
    }

    /// The loaded report, if any — drives the Copy button's enablement + action.
    private var loadedReport: DoctorReport? {
        if case .loaded(let report) = loadState { return report }
        return nil
    }

    // MARK: - Content

    @ViewBuilder
    private var content: some View {
        switch loadState {
        case .loading:
            ProgressView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .unavailable:
            ContentUnavailableView(
                "No Running Project",
                systemImage: "stethoscope",
                description: Text("Open a project first — the health checks run against its server.")
            )
        case .failed(let message):
            ContentUnavailableView {
                Label("Couldn't Load Health", systemImage: "exclamationmark.triangle")
            } description: {
                Text(message)
            } actions: {
                Button("Try Again") { Task { await load() } }
            }
        case .loaded(let report):
            checklist(report)
        }
    }

    @ViewBuilder
    private func checklist(_ report: DoctorReport) -> some View {
        if report.checks.isEmpty {
            ContentUnavailableView(
                "No Checks",
                systemImage: "checkmark.circle",
                description: Text("The server returned no health checks.")
            )
        } else {
            ScrollView {
                Grid(alignment: .topLeading, horizontalSpacing: 10, verticalSpacing: 10) {
                    ForEach(report.checks) { check in
                        row(for: check)
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    @ViewBuilder
    private func row(for check: DoctorCheck) -> some View {
        let kind = DoctorStatus.messageKind(for: check.status)
        GridRow {
            Image(systemName: kind.symbolName)
                .foregroundStyle(kind.tint)
                .accessibilityLabel(kind.rawValue)
            Text(check.label)
                .font(.body.weight(.medium))
                .gridColumnAlignment(.leading)
            VStack(alignment: .leading, spacing: 3) {
                if !check.detail.isEmpty {
                    Text(check.detail)
                        .textSelection(.enabled)
                }
                if !check.fix.isEmpty {
                    Text(check.fix)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Fetch

    @MainActor
    private func load() async {
        loadState = .loading
        guard let port = serveManager.runningPort,
              let token = serveManager.authToken,
              let url = URL(string: "http://127.0.0.1:\(port)/api/doctor") else {
            loadState = .unavailable
            return
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                loadState = .failed("No response from the local server.")
                return
            }
            guard http.statusCode == 200 else {
                loadState = .failed("Server returned HTTP \(http.statusCode).")
                return
            }
            let report = try JSONDecoder().decode(DoctorReport.self, from: data)
            loadState = .loaded(report)
        } catch {
            loadState = .failed(error.localizedDescription)
        }
    }

    // MARK: - Copy

    private func copyPlaintext(_ report: DoctorReport) {
        let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?"
        let os = ProcessInfo.processInfo.operatingSystemVersionString
        let text = Self.formatPlaintext(
            checks: report.checks, appVersion: appVersion, build: build, os: os
        )
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(text, forType: .string)
    }

    /// Pure CLI-style plaintext for the Copy button — the same glyph column the
    /// terminal `doctor` uses (via `MessageKind.glyph`), so a pasted health
    /// report reads like a CLI run. English-only by design (triager-greppable).
    static func formatPlaintext(
        checks: [DoctorCheck], appVersion: String, build: String, os: String
    ) -> String {
        var lines: [String] = []
        lines.append("Bristlenose \(appVersion) (\(build)) on \(os)")
        lines.append("System health")
        lines.append("")
        for check in checks {
            let glyph = DoctorStatus.messageKind(for: check.status).glyph
            let detail = check.detail.isEmpty ? "" : "  \(check.detail)"
            lines.append("\(glyph) \(check.label)\(detail)")
            if !check.fix.isEmpty {
                for fixLine in check.fix.split(separator: "\n", omittingEmptySubsequences: false) {
                    lines.append("    \(fixLine)")
                }
            }
        }
        return lines.joined(separator: "\n")
    }
}
