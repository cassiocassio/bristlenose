import Foundation

/// Native mirror of the serve endpoint `GET /api/doctor` payload — the local
/// (non-network) subset of `bristlenose/doctor.py`'s `DoctorReport`, decoded
/// from JSON by `DoctorReportView`.
///
/// Deliberately a *fresh* type, not the pipeline `PipelineSummary` /
/// `StageOutcome` / `Cause` family — those mirror the run-events wire contract
/// and are the wrong shape for a health checklist. This is a flat list of
/// `(status, label, detail, fix)` rows, one per check.
///
/// The check `label`/`detail`/`fix` strings are English-only: they originate in
/// `doctor.py`, which is English-only in alpha (the CLI is), and the Diagnostics
/// menu that opens this window is itself English-only literals.
struct DoctorCheck: Decodable, Identifiable, Equatable {
    /// Wire status: "ok" | "warn" | "fail" | "--" (SKIP). Mapped to a
    /// `MessageKind` for rendering via `DoctorStatus.messageKind(for:)`.
    let status: String
    let label: String
    let detail: String
    /// Human-readable, install-aware remediation text (resolved server-side
    /// from the check's `fix_key`). Empty when the check has no remedy.
    let fix: String

    /// Identity for `ForEach` — one row per check, labels are unique per report.
    var id: String { label }

    enum CodingKeys: String, CodingKey {
        case status, label, detail, fix
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        status = try c.decode(String.self, forKey: .status)
        label = try c.decode(String.self, forKey: .label)
        // Defensive: tolerate a future payload that drops these optional-ish
        // fields rather than failing the whole decode.
        detail = (try c.decodeIfPresent(String.self, forKey: .detail)) ?? ""
        fix = (try c.decodeIfPresent(String.self, forKey: .fix)) ?? ""
    }

    /// Direct init for previews / tests (bypasses JSON).
    init(status: String, label: String, detail: String, fix: String = "") {
        self.status = status
        self.label = label
        self.detail = detail
        self.fix = fix
    }
}

struct DoctorReport: Decodable, Equatable {
    let checks: [DoctorCheck]
}

/// Pure, testable mapping from the doctor wire status → the shared `MessageKind`
/// vocabulary (the same five-glyph taxonomy the CLI and the diagnostic popover
/// use, so a health row in the app reads like a doctor line in the terminal).
///
/// Lives here (not in the view) per the desktop testability rule: "if a SwiftUI
/// view is making a decision, the decision belongs in a testable helper."
enum DoctorStatus {
    /// OK→success, WARN→warning, FAIL→error, SKIP("--")→skipped. An unknown
    /// wire value falls back to `.info` (the spare kind) rather than crashing.
    static func messageKind(for wireStatus: String) -> MessageKind {
        switch wireStatus {
        case "ok":   return .success
        case "warn": return .warning
        case "fail": return .error
        case "--":   return .skipped
        default:     return .info
        }
    }
}
