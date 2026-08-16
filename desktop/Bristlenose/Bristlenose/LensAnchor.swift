import Foundation

/// How a remembered position is *applied*, which differs by lens.
///
/// `LensMemory` restores the lens; this restores the place within it. The two
/// are stored side by side on `Project` (`lastLens`, `lastAnchor`) and the
/// anchor is meaningless without its lens — a `theme-onboarding` id means
/// nothing on Codebook.
///
/// ## Why one string field and not two
///
/// The stored value is interpreted per lens, and the interpretations are
/// genuinely different kinds of thing:
///
/// | Lens | What the anchor is | How it is applied |
/// |---|---|---|
/// | Quotes | a group heading id (`theme-…`, `section-…`) | scroll |
/// | Codebook | a framework section id (`codebook-fw-…`) | scroll |
/// | Sessions | a session id (`s3`) | **navigate** |
/// | Analysis, Project | — | nothing; the top |
///
/// Sessions is the odd one: its position is a *route*, not an offset, so
/// restoring it means navigating rather than scrolling. Two fields would have to
/// be kept mutually exclusive by convention; one field plus this table makes the
/// exclusivity structural, and puts the whole rule where it can be read at once.
///
/// The frontend half of the table lives in `useAnchorReporter` — that decides
/// what to *report*, this decides what to *do with it*. They have to agree, and
/// each names the other.
enum LensAnchor {

    /// What restoring a remembered anchor should actually do.
    enum Action: Equatable {
        /// Scroll the report to this element id.
        case scroll(String)
        /// Navigate to this session's transcript.
        case session(String)
        /// Land at the top — no position was remembered, or this lens keeps none.
        case top
    }

    /// Resolve a stored anchor against the lens it was stored for.
    ///
    /// Returns `.top` for a lens that keeps no position, and for an empty or
    /// absent anchor. Deliberately does **not** validate that the id still
    /// exists: the content is mutable, so the check would be a lie by the time
    /// it mattered. The apply path fails honestly instead — `scrollToAnchor`
    /// retries then gives up leaving the page at the top, and a missing session
    /// lands on `TranscriptPage`'s error state with the switcher as the way out.
    static func action(lens: Tab?, anchor: String?) -> Action {
        guard let lens, let anchor, !anchor.isEmpty else { return .top }
        switch lens {
        case .quotes, .codebook: return .scroll(anchor)
        case .sessions:          return .session(anchor)
        // Decided 16 Aug 2026: these restore to the top. Neither has a stable
        // structural position worth remembering, and inventing one would be a
        // guess the reader cannot predict.
        case .analysis, .project: return .top
        }
    }

    /// Whether this lens remembers a position at all — the gate on *storing*,
    /// so an anchor reported by one lens can't be written against another.
    static func remembersPosition(_ lens: Tab?) -> Bool {
        switch lens {
        case .quotes, .codebook, .sessions: return true
        case .analysis, .project, nil:      return false
        }
    }
}
