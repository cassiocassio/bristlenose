import Foundation

/// One line the sidecar prints when an LLM call it made was refused:
/// `[bristlenose] llm-refusal: {"v":1,"kind":"out_of_credit","provider":"anthropic",…}`.
///
/// The serve side of the pill's feed. A run reports through the events log and a
/// report chip through the bridge, but a call made by the sidecar on its own
/// (a signal refresh, the re-apply after a run) reported to neither, so a dead key
/// or an empty account lit nothing. The sidecar's client prints this line from its
/// one failure path (`bristlenose/llm/refusal_report.py`), and `ServeManager` reads
/// it before the line can reach the output buffer.
///
/// The fields are strings and optional values, never enums: an unknown `kind` or
/// `phase` must degrade to "not acted on", not to a decode failure that drops the
/// line. `kind` is `LLMFailureKind`'s raw value, which agrees with
/// `ProviderProblemCondition.fromLLMFailureKind` by convention.
struct LLMRefusalLine: Equatable, Decodable, Sendable {
    static let prefix = "[bristlenose] llm-refusal: "
    /// The writer caps a line well under this; a longer one is not ours.
    static let maxBytes = 2048

    /// The writer's schema version. Only 1 is understood: a line from a later schema is
    /// consumed and logged, never acted on as if it were this one.
    static let understoodVersion = 1

    let v: Int?
    let kind: String
    let provider: String
    let httpStatus: Int?
    let phase: String?
    let providerSignature: Bool?

    enum CodingKeys: String, CodingKey {
        case v, kind, provider, phase
        case httpStatus = "http_status"
        case providerSignature = "provider_signature"
    }

    /// What a line is. A line that begins with the prefix is ours even when it cannot be
    /// read, and must never reach the output the boot pane and the exit-error read: so
    /// `malformed` is consumed and logged by the caller, not passed on.
    enum Disposition: Equatable {
        case notOurs
        case refusal(LLMRefusalLine)
        case malformed
    }

    static func disposition(of line: String) -> Disposition {
        guard line.hasPrefix(prefix) else { return .notOurs }
        guard line.utf8.count <= maxBytes,
              let data = String(line.dropFirst(prefix.count)).data(using: .utf8),
              let decoded = try? JSONDecoder().decode(Self.self, from: data),
              decoded.v == nil || decoded.v == understoodVersion
        else { return .malformed }
        return .refusal(decoded)
    }

    /// The parsed refusal, or nil for a line that is not one (or is unreadable).
    static func fromLine(_ line: String) -> Self? {
        if case .refusal(let r) = disposition(of: line) { return r }
        return nil
    }

    /// What the pill can act on today: no credit, or a rejected key, from the
    /// provider this build knows. Everything else (a rate limit, an outage, a
    /// dropped connection) is said where it happened and gets no pill.
    var condition: ProviderProblemCondition? {
        ProviderProblemCondition.fromLLMFailureKind(kind)
    }

    var llmProvider: LLMProvider? { LLMProvider(rawValue: provider) }
}
