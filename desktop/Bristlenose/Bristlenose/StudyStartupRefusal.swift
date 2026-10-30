import Foundation

/// Facts from a refused startup, not proof that the other computer is still running.
/// Names and times are display-only; Python's admission check owns the decision.
struct StudyStartupRefusal: Equatable, Decodable, Sendable {
    enum Reason: String, Decodable, Sendable {
        case foreign = "foreign_unfinished"
        case unverified = "unverified_unfinished"
    }

    static let exitCode: Int32 = 75
    static let prefix = "@study-startup-refused "
    static let unverified = Self(reason: .unverified, machineName: nil, startedAt: nil)

    let reason: Reason
    let machineName: String?
    let startedAt: String?

    enum CodingKeys: String, CodingKey {
        case reason
        case machineName = "machine_name"
        case startedAt = "started_at"
    }

    static func fromLine(_ line: String) -> Self? {
        guard line.hasPrefix(prefix), line.utf8.count <= 8192,
              let data = String(line.dropFirst(prefix.count)).data(using: .utf8),
              let result = try? JSONDecoder().decode(Self.self, from: data) else { return nil }
        return result
    }

    var failureMessage: FailureMessage {
        FailureMessage(english: reason == .foreign
            ? "Analysis started on another Mac. This study cannot be viewed or edited here."
            : "An unfinished analysis was found, but the Mac that started it could not be verified. This study cannot be viewed or edited here.",
            startupRefusal: self)
    }

    @MainActor
    func headline(using i18n: I18n) -> String {
        localized(reason == .foreign ? "foreignTitle" : "unknownTitle", using: i18n)
    }

    @MainActor
    func consequence(using i18n: I18n) -> String {
        localized("consequence", using: i18n)
    }

    /// Control and invisible format scalars (bidi overrides, zero-width space) are
    /// refused in a name read back from a synced file. The joiners that build family
    /// emoji and spell Persian words stay: a real Mac name should not be blanked.
    static func isUnsafeDisplayScalar(_ scalar: Unicode.Scalar) -> Bool {
        switch scalar.properties.generalCategory {
        case .control: return true
        case .format: return scalar != "\u{200C}" && scalar != "\u{200D}"
        default: return false
        }
    }

    @MainActor
    func detail(using i18n: I18n, now: Date = Date()) -> AttributedString {
        guard reason == .foreign else { return AttributedString(localized("unknownBody", using: i18n)) }
        let name = machineName.flatMap { candidate -> String? in
            guard !candidate.isEmpty, candidate.count <= 256,
                  !candidate.unicodeScalars.contains(where: { Self.isUnsafeDisplayScalar($0) })
            else { return nil }
            return candidate
        }
        let time = startedAt.flatMap(EventLogReader.parseISO8601).map { date in
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: i18n.locale)
            if Calendar.current.isDate(date, inSameDayAs: now) {
                formatter.timeStyle = .short
                return localized("todayAt", using: i18n)
                    .replacingOccurrences(of: "{{time}}", with: formatter.string(from: date))
            }
            formatter.dateStyle = .medium
            formatter.timeStyle = .short
            return formatter.string(from: date)
        }
        let subject = [name ?? localized("anotherMac", using: i18n), time].compactMap { $0 }.joined(separator: " ")
        let sentence = localized("foreignBody", using: i18n).replacingOccurrences(of: "{{detail}}", with: subject)
        var result = AttributedString(sentence)
        // Attributed text, not markdown: a computer name cannot inject formatting.
        if name != nil || time != nil, let range = result.range(of: subject) {
            result[range].inlinePresentationIntent = .stronglyEmphasized
        }
        return result
    }

    var diagnosticDetails: String {
        var lines = ["Reason: \(reason.rawValue)"]
        if reason == .foreign {
            if let machineName { lines.append("Started on: \(machineName)") }
            if let startedAt { lines.append("Started at: \(startedAt)") }
        }
        lines.append("Startup refused before study writers started.")
        return lines.joined(separator: "\n")
    }

    @MainActor
    private func localized(_ leaf: String, using i18n: I18n) -> String {
        let key = "desktop.studyStartup." + leaf
        let value = i18n.t(key)
        return value == key ? Self.english[leaf, default: key] : value
    }

    private static let english = [
        "foreignTitle": "Started on another Mac",
        "unknownTitle": "Activity not confirmed",
        "foreignBody": "Analysis started on {{detail}}.",
        "unknownBody": "An unfinished analysis was found, but the Mac that started it could not be verified.",
        "consequence": "This study cannot be viewed or edited here.",
        "anotherMac": "another Mac",
        "todayAt": "today at {{time}}",
    ]
}
