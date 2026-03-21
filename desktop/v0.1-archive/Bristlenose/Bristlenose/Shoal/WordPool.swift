import AppKit

/// Hardcoded word pools for the typographic shoal spike.
/// Post-spike: replace with real data parsed from intermediate JSON files.
enum WordPool {

    struct Word {
        let text: String
        let fontSize: CGFloat
        let color: NSColor
    }

    // MARK: - Early phase — dim transcript fragments

    private static let earlyWords = [
        "um", "the thing is", "I really", "so basically",
        "what I noticed", "it was like", "you know",
        "I think", "and then", "right so", "I mean",
        "that part", "when I", "honestly", "the first time",
        "it felt", "I expected", "sort of", "in a way",
        "the problem", "actually", "I guess", "at first",
        "I wasn't sure", "it reminded me",
    ]

    // MARK: - Middle phase — topic and section labels

    private static let middleWords = [
        "Onboarding", "Dashboard", "Search", "Navigation",
        "Settings", "Checkout", "Profile", "Notifications",
        "First impression", "Account setup", "Data entry",
        "Help section", "Error handling", "Loading states",
        "Mobile view", "Homepage", "Pricing page",
        "Feature discovery", "Task completion", "Filtering",
    ]

    // MARK: - Late phase — themes and sentiments (coloured)

    private static let lateThemes: [(String, ShoalSentiment)] = [
        ("Trust", .positive),
        ("Friction", .negative),
        ("Clarity", .positive),
        ("Confusion", .negative),
        ("Delight", .positive),
        ("Frustration", .negative),
        ("Confidence", .positive),
        ("Doubt", .negative),
        ("Intuitive", .positive),
        ("Overwhelming", .negative),
        ("Surprise", .neutral),
        ("Satisfaction", .positive),
        ("Scepticism", .negative),
        ("Engagement", .positive),
        ("Anxiety", .negative),
        ("P1", .neutral),
        ("P2", .neutral),
        ("P3", .neutral),
        ("Moderator", .neutral),
    ]

    // MARK: - Public API

    /// Returns a batch of words appropriate for the given phase.
    /// `excluding` filters out text already visible in the scene.
    static func words(
        for phase: ShoalPhase,
        count: Int,
        excluding active: Set<String> = []
    ) -> [Word] {
        let candidates: [Word]
        switch phase {
        case .early:
            candidates = earlyWords
                .filter { !active.contains($0) }
                .map { Word(text: $0, fontSize: 11, color: .labelColor.withAlphaComponent(0.5)) }
        case .middle:
            candidates = middleWords
                .filter { !active.contains($0) }
                .map { Word(text: $0, fontSize: 13, color: .labelColor.withAlphaComponent(0.7)) }
        case .late, .complete, .settling:
            candidates = lateThemes
                .filter { !active.contains($0.0) }
                .map { Word(text: $0.0, fontSize: 15, color: $0.1.color) }
        }
        return Array(candidates.shuffled().prefix(count))
    }
}
