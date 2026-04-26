import Foundation
import os

/// Reads `pipeline-events.jsonl` (Phase 4a-pre) and derives a `PipelineState`.
///
/// The events log is the single source of truth for run-level outcome data.
/// "Current state" is derived by tail-reading the log. Stage-complete data
/// for `.partial` / `.stopped` cases is read from the manifest at display
/// time, not the events log.
///
/// Read is bounded: at most 64 KB from the tail of the file. A run-started
/// event line is small (~200 B); a terminus event with a 4 KB capped
/// `cause.message` is well under 5 KB. 64 KB comfortably contains a few
/// dozen events — enough to find the most recent `run_*` line in any
/// realistic file. See `docs/design-pipeline-resilience.md` §"Phase 4a-pre".
///
/// This file is the Swift mirror of `bristlenose/events.py`; case names
/// (`run_started` / `run_completed` / `run_cancelled` / `run_failed`) are
/// the contract. Don't drift the names.
enum EventLogReader {
    private static let logger = Logger(subsystem: "app.bristlenose", category: "events")

    /// Filename inside `<output>/.bristlenose/`.
    static let filename = "pipeline-events.jsonl"

    /// Filename of the Python-side PID file inside `<output>/.bristlenose/`.
    /// Distinct from Swift's own per-project PID file in App Support.
    static let pidFilename = "run.pid"

    /// Decoded shape of one event line. Most fields are optional because
    /// only `run_started` carries `process`, only terminus events carry
    /// `cause` / `outcome` / `ended_at`, and so on.
    struct Event: Codable, Equatable {
        let event: String
        let kind: String
        let runId: String
        let startedAt: String
        let endedAt: String?
        let outcome: String?
        let cause: Cause?

        enum CodingKeys: String, CodingKey {
            case event, kind
            case runId = "run_id"
            case startedAt = "started_at"
            case endedAt = "ended_at"
            case outcome
            case cause
        }
    }

    struct Cause: Codable, Equatable {
        let category: PipelineFailureCategory
        let message: String?
        let signalName: String?

        enum CodingKeys: String, CodingKey {
            case category
            case message
            case signalName = "signal_name"
        }
    }

    /// Decoded shape of `run.pid`.
    struct PIDFile: Codable {
        let pid: Int32
        let startTime: String
        let runId: String

        enum CodingKeys: String, CodingKey {
            case pid
            case startTime = "start_time"
            case runId = "run_id"
        }
    }

    /// Read the most recent `run_*` event. Returns `nil` when the file is
    /// missing, empty, or contains no parseable events. Bounded read.
    static func tailEvent(at url: URL) -> Event? {
        let maxBytes = 65_536
        guard let (data, wasTruncated) = readBoundedTail(url: url, maxBytes: maxBytes) else {
            return nil
        }
        // JSONL: split on newlines, parse from the tail back.
        let text = String(data: data, encoding: .utf8) ?? ""
        var lines = Array(text.split(separator: "\n", omittingEmptySubsequences: true))
        // If we read from a truncated tail (file > maxBytes), the first slice
        // is almost certainly chopped mid-line. Drop it before iterating —
        // otherwise an accidentally-valid-looking JSON fragment would decode
        // to a wrong event.
        if wasTruncated, !lines.isEmpty {
            lines.removeFirst()
        }
        let decoder = JSONDecoder()
        for line in lines.reversed() {
            // Strip trailing NULs (power-loss padding).
            let cleaned = line.trimmingCharacters(in: CharacterSet(charactersIn: "\0\r"))
            guard !cleaned.isEmpty,
                  let lineData = cleaned.data(using: .utf8),
                  let event = try? decoder.decode(Event.self, from: lineData) else {
                continue
            }
            return event
        }
        return nil
    }

    /// Map the most recent event + PID-file liveness + manifest stages-complete
    /// onto a `PipelineState`. Returns `nil` when the events log is missing —
    /// caller should fall back to its existing manifest inference.
    static func deriveState(
        eventsURL: URL,
        pidURL: URL,
        stagesComplete: [String]
    ) -> PipelineState? {
        guard FileManager.default.fileExists(atPath: eventsURL.path) else {
            return nil
        }
        guard let event = tailEvent(at: eventsURL) else {
            return nil
        }
        switch event.event {
        case "run_started":
            // In flight if the Python PID file confirms a live owned process.
            // Otherwise the prior run died without writing a terminus — display
            // as failed(unknown). The Python side reconciles on next start.
            if pythonOwnedRunIsAlive(at: pidURL) {
                return .running
            }
            return .failed(
                "Analysis stopped unexpectedly.",
                category: .unknown,
            )
        case "run_completed":
            return mapCompleted(event: event, stagesComplete: stagesComplete)
        case "run_cancelled":
            return .stopped(stagesComplete: stagesComplete)
        case "run_failed":
            let summary = event.cause?.message ?? "Failed"
            let category = event.cause?.category ?? .unknown
            return .failed(summary, category: category)
        default:
            // Unknown event type — likely forward-compat (Phase 4a stage events).
            // Swallow gracefully; not actionable for a human.
            logger.info("unexpected event: \(event.event, privacy: .public)")
            return nil
        }
    }

    private static func mapCompleted(
        event: Event, stagesComplete: [String]
    ) -> PipelineState {
        // `transcribe-only` completes without a render → .partial; allows the
        // UI to offer "Continue (analyse)". `run` and `analyze` produce a
        // full render → .ready.
        if event.kind == "transcribe-only" {
            return .partial(kind: event.kind, stagesComplete: stagesComplete)
        }
        // For .ready we want a Date — parse `ended_at` if available.
        let date: Date
        if let endedAt = event.endedAt, let parsed = parseISO8601(endedAt) {
            date = parsed
        } else {
            date = Date()
        }
        return .ready(date)
    }

    /// Returns `true` iff `<output>/.bristlenose/run.pid` exists, parses,
    /// and its `(pid, start_time)` matches a live process.
    static func pythonOwnedRunIsAlive(at pidURL: URL) -> Bool {
        guard let data = try? Data(contentsOf: pidURL),
              let payload = try? JSONDecoder().decode(PIDFile.self, from: data) else {
            return false
        }
        guard kill(payload.pid, 0) == 0 else { return false }
        // Verify start_time matches — defeats PID reuse.
        guard let lstart = psLstart(pid: payload.pid) else { return false }
        return lstart == payload.startTime
    }

    private static func psLstart(pid: Int32) -> String? {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/bin/ps")
        proc.arguments = ["-o", "lstart=", "-p", String(pid)]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = FileHandle.nullDevice
        do { try proc.run() } catch { return nil }
        proc.waitUntilExit()
        guard proc.terminationStatus == 0 else { return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let str = String(data: data, encoding: .utf8) else { return nil }
        let trimmed = str.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    /// Read the last `maxBytes` bytes of `url`. Returns `(data, wasTruncated)`
    /// where `wasTruncated` indicates the file exceeded `maxBytes` and the
    /// caller should drop the first slice (likely chopped mid-line).
    /// Returns `nil` on missing or unreadable file. Mirrors Python's
    /// `_iter_event_lines` recovery posture — caller handles malformed lines.
    private static func readBoundedTail(url: URL, maxBytes: Int) -> (Data, Bool)? {
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            return nil
        }
        defer { try? handle.close() }
        guard let endOffset = try? handle.seekToEnd() else { return nil }
        let truncated = endOffset > UInt64(maxBytes)
        let readFrom: UInt64 = truncated ? endOffset - UInt64(maxBytes) : 0
        guard (try? handle.seek(toOffset: readFrom)) != nil else { return nil }
        guard let data = try? handle.readToEnd() else { return nil }
        return (data, truncated)
    }

    /// Parse a Python-emitted ISO8601 timestamp. Tries with fractional
    /// seconds first (Python's default), falls back to without — Python's
    /// `datetime.isoformat()` omits fractional seconds when `microsecond == 0`.
    static func parseISO8601(_ string: String) -> Date? {
        if let date = iso8601WithFractional.date(from: string) { return date }
        return iso8601Plain.date(from: string)
    }

    private static let iso8601WithFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let iso8601Plain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()
}
