import Foundation

// MARK: - Clause-boundary fitting for welcome-cell prose
//
// The house rule is that geometry is fixed and content bends — and that the
// bending is done by the SEMANTIC layer, never by shrinking type. This is the
// production subset of that: cut a sentence at its outermost clause boundary so
// a narrow cell gets a shorter *complete* reading rather than an ellipsis.
//
// It is safe only because the copy is written to make it safe. The standing
// constraint on welcome copy is INVERTED PYRAMID — payoff first, nothing
// load-bearing at the end — so dropping a tail loses detail, never the point.
// Prose that has not been written that way must not be cut this way.
//
// Deliberately narrow. It cuts only at markers whose tail is reliably an
// appositive or a gloss (em dash, en dash, semicolon), refuses head-final
// scripts outright, and refuses a stump too short to read as a sentence.
// Commas and colons are NOT cut: a comma may join a list, a subordinate clause
// or an appositive and you cannot tell which without parsing, and the tail
// after a colon is the payload rather than the elaboration.
//
// The rules were derived in Diagnostics ▸ Degradation Lab
// (`WelcomeDegradationLab.swift`, DEBUG only), which carries the fuller
// research version with per-cut risk verdicts and the stress corpus. When the
// pyramid rewrite lands, that lab is where a candidate sentence gets checked.
enum WelcomeClauseFit {
    /// Markers whose tail drops gracefully, outermost structure first.
    private static let markers = [" — ", " – ", "; "]

    /// A cut is refused below this, where a stump stops reading as a sentence
    /// and starts reading as a truncation.
    private static let minimumStump = 24

    /// Hiragana, katakana, hangul or CJK ideographs. These languages are
    /// head-final: the verb lands at the END, so cutting a tail removes the
    /// predicate and leaves a verbless fragment — ungrammatical, not just terse.
    static func isHeadFinal(_ s: String) -> Bool {
        s.unicodeScalars.contains { u in
            let v = u.value
            return (0x3040...0x30FF).contains(v)   // kana
                || (0xAC00...0xD7AF).contains(v)   // hangul syllables
                || (0x4E00...0x9FFF).contains(v)   // CJK unified ideographs
        }
    }

    /// The sentence cut at its FIRST safe clause boundary, re-punctuated — or
    /// `nil` when no cut is defensible, in which case the caller should fall
    /// back to its own last resort (an ellipsis, which at least marks the loss).
    static func shortened(_ s: String) -> String? {
        guard !isHeadFinal(s) else { return nil }

        // Outermost first: the earliest occurrence of the strongest marker.
        // Cutting at a weaker marker that sits inside a stronger marker's span
        // strands the opener — "…a discipline — blame the design." keeps a
        // dangling em dash whose resolution has been thrown away.
        for m in markers {
            guard let r = s.range(of: m) else { continue }
            let head = tidy(String(s[s.startIndex..<r.lowerBound]))
            guard head.count >= minimumStump, isBalanced(head) else { continue }
            return head
        }
        return nil
    }

    /// Drop the dangling marker and restore a terminal stop.
    private static func tidy(_ head: String) -> String {
        var t = head
        while let l = t.last, " \t—–-;,:".contains(l) { t.removeLast() }
        guard let l = t.last else { return t }
        if !".!?".contains(l) { t.append(".") }
        return t
    }

    /// A cut that orphans an opening bracket or quote is indefensible on any
    /// reading, however well the rest of it scans.
    private static func isBalanced(_ s: String) -> Bool {
        s.filter { $0 == "(" }.count == s.filter { $0 == ")" }.count
            && s.filter { $0 == "\u{201C}" }.count == s.filter { $0 == "\u{201D}" }.count
    }
}
