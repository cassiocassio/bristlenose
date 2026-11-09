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
/// genuinely different kinds of thing. Decision #182, option B (9 Nov 2026):
/// each lens returns to the element the reader was on.
///
/// | Lens | What the anchor is | How it is applied |
/// |---|---|---|
/// | Quotes | the quote card (`q-p1-10`), or a group heading (`theme-…`, `section-…`) above the first card | scroll |
/// | Codebook | the code row (`code-12`), in the codebook the lens opens on | scroll |
/// | Signals | the card (`signal-theme-theme-3--frustration`); the page shows its place first | scroll |
/// | Sessions | a place the SPA understands: `s1#t-66` (session and paragraph), or a bare `s3` | **navigate** |
/// | Project, Discussion, Screens | — | nothing; the top |
///
/// Sessions is the odd one: its position is a *route*, not an offset, so
/// restoring it means navigating rather than scrolling. The anchor is opaque
/// here — the SPA reports it and the SPA's own address arrival
/// (`TranscriptPage`'s hash landing) applies it — so this file never parses it.
/// Two fields would have to be kept mutually exclusive by convention; one field
/// plus this table makes the exclusivity structural, and puts the whole rule
/// where it can be read at once.
///
/// Discussion stays at the top: none of its elements carries an id, the same
/// question is a different element in each of its two layouts, and it arrives
/// by query (`?item=&turn=`), so restoring it would be a feature of its own.
/// Until 9 Nov 2026 Signals restored to the top too (decided 16 Aug 2026), and
/// Codebook's stored `codebook-fw-…` ids named an element the v2 lens never
/// rendered, so it also came back at the top.
///
/// The frontend half of the table lives in `useAnchorReporter` — that decides
/// what to *report*, this decides what to *do with it*. They have to agree, and
/// each names the other.
enum LensAnchor {

    /// What restoring a remembered anchor should actually do.
    enum Action: Equatable {
        /// Scroll the report to this element id.
        case scroll(String)
        /// Navigate to this place on the Sessions lens: a session id, or a
        /// session and a paragraph (`s1#t-66`).
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
        case .quotes, .codebook, .signals: return .scroll(anchor)
        case .sessions:                    return .session(anchor)
        // Decision #182 (9 Nov 2026): the right lens is enough for Project and
        // Screens; Discussion has nothing to scroll to (see the type doc).
        case .project, .discussion, .screens: return .top
        }
    }

    /// Whether this lens remembers a position at all — the gate on *storing*,
    /// so an anchor reported by one lens can't be written against another.
    static func remembersPosition(_ lens: Tab?) -> Bool {
        switch lens {
        case .quotes, .codebook, .signals, .sessions: return true
        case .project, .discussion, .screens, nil: return false
        }
    }
}
