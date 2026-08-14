import AppKit

/// The decisions a sessions-popover row makes, lifted out of the view bodies so
/// they can be unit-tested — the house convention (`desktop/CLAUDE.md`
/// §Testing: "if a SwiftUI view is making a decision, the decision belongs in a
/// testable helper").
///
/// Row shape, in the agreed layout:
///
///     [p1]  Session 1   Yuki                 ← 1 participant: name on the title line
///                       26m · 10 Feb, 09:12
///           Session 6                        ← 2+: title, then one name per line
///     [p6]              Beth
///     [p7]              Participant
///     [p8]              Participant
///                       19m · 11 Feb, 09:00
///
/// Badges align to the **names**, not to the top of the margin: at top-of-margin
/// the first badge sits level with the title, so `p6` reads as a label for
/// *Session 6* — reintroducing the session-number/participant-number conflation
/// that dropping `#N` was meant to remove — and the last name is left with no
/// badge at all.
enum SessionsPopoverSpec {

    // MARK: - Model

    struct Participant: Equatable {
        let code: String        // "p6"
        let name: String?       // nil when the pipeline never named this speaker

        init(code: String, name: String?) {
            self.code = code
            // Treat empty-string names as unnamed — the API returns "" rather
            // than null for a speaker the pipeline didn't name.
            self.name = (name?.isEmpty ?? true) ? nil : name
        }
    }

    struct Session: Equatable {
        let sessionID: String   // "s6"
        let number: Int         // 6
        let isoDate: String?
        let durationSeconds: Double
        let participants: [Participant]
    }

    // MARK: - Row height

    /// Height for a row carrying `participantCount` participants.
    ///
    /// **This is `f(participantCount)`, not a binary.** An earlier draft framed
    /// it as "1-up vs stacked", which yields a two-case test that passes on a
    /// three-case bug — there are as many heights as there are participant
    /// counts. Parameterise tests over `n`.
    ///
    /// Built on `ProjectCellSpec` rather than a fresh constant: its 32pt base is
    /// measured against Finder / Notes / Mail, and its own comment records that
    /// *no native two-line source-list reference exists* — which is exactly this
    /// problem, already solved once. Sharing the spec is also what stops the
    /// popover and the sidebar drifting, which is the property the real control
    /// was chosen for.
    static func rowHeight(participantCount: Int) -> CGFloat {
        let base = ProjectCellSpec.rowHeight(twoLine: true)
        guard participantCount > 1 else { return base }
        return base + CGFloat(participantCount) * nameLineHeight
    }

    /// One stacked name line: the name's own line box plus the title↔subtitle
    /// gap, so the stack breathes the same way the base row does.
    static var nameLineHeight: CGFloat {
        ceil(ProjectCellSpec.titleFont.boundingRectForFont.height) + ProjectCellSpec.titleToSubtitle
    }

    /// True when the row stacks its speakers on their own lines.
    static func isStacked(participantCount: Int) -> Bool { participantCount > 1 }

    // MARK: - Type-select

    /// The string type-select matches against.
    ///
    /// Without this the default derivation matches the cell's `textField` — the
    /// **title** — so typing "beth" matches nothing, and type-select was one of
    /// the reasons for choosing a real table. Names lead because the name is
    /// what a researcher types.
    ///
    /// SPEC-1, be honest about the mechanism: AppKit's **default** matcher is
    /// anchored prefix matching, so out of the box only the *leading* name
    /// would be reachable — "beth" jumps, "p6" does not. The codes and title
    /// are appended for the wrapper's token-level matcher
    /// (`tableView(_:nextTypeSelectMatchFromRow:toRow:for:)` using
    /// `typeSelectMatches` below), which is what actually makes "p6" and
    /// "session 6" land. Names still lead so the default matcher alone covers
    /// the primary case if the delegate method is ever lost.
    ///
    /// `title` is the LOCALISED row title (`common.sessions.sessionLabel` —
    /// "Interview 6" in German), never a hardcoded English "Session N": the
    /// string a user types is the string they can see.
    static func typeSelectString(for session: Session, title: String, placeholder: String) -> String {
        var parts: [String] = []
        for p in session.participants {
            parts.append(p.name ?? placeholder)
            parts.append(p.code)
        }
        parts.append(title)
        return parts.joined(separator: " ")
    }

    /// Token-level prefix match for `nextTypeSelectMatchFromRow` — true when
    /// the search string prefixes the candidate as a whole OR any
    /// space-delimited token boundary within it. Case-insensitive, mirroring
    /// AppKit's own matcher. Pure so the wrapper's delegate method stays a
    /// one-line caller of a tested decision.
    static func typeSelectMatches(search: String, candidate: String) -> Bool {
        let needle = search.lowercased()
        guard !needle.isEmpty else { return false }
        let hay = candidate.lowercased()
        if hay.hasPrefix(needle) { return true }
        for index in hay.indices where hay[index] == " " {
            if hay[hay.index(after: index)...].hasPrefix(needle) { return true }
        }
        return false
    }

    // MARK: - Accessibility

    /// One composed label per row, replacing the subview-order reading.
    ///
    /// Left to AppKit, a stacked row serialises in grid order — plausibly
    /// "p6 p7 p8 Session 6 Beth Participant Participant 19m …" — which destroys
    /// the badge↔name pairing that the visual layout exists to convey. Adjacency
    /// in this string is the **only** thing carrying that pairing non-visually,
    /// so each code is spoken immediately before its own name.
    ///
    /// Commas, not middots: VoiceOver pauses on a comma and reads nothing at all
    /// for `·` (the same reasoning as `ProjectRow.swift:654`). Values come from
    /// the model, never from the rendered text field, because the visible text
    /// is truncated at 308pt and truncation is a visual loss that a screen-reader
    /// user should not inherit.
    ///
    /// `title` is the LOCALISED row title, for the same reason as
    /// `typeSelectString`: accessibility labels are user-facing text, and a
    /// German VoiceOver user must hear "Interview 6" — the words on screen —
    /// not a hardcoded English "Session 6".
    static func accessibilityLabel(for session: Session,
                                   title: String,
                                   placeholder: String,
                                   duration: String,
                                   date: String) -> String {
        var parts = [title]
        for p in session.participants {
            parts.append("\(p.code) \(p.name ?? placeholder)")
        }
        parts.append(duration)
        if date != SessionsFinderDate.emDash { parts.append(date) }
        return parts.joined(separator: ", ")
    }
}
