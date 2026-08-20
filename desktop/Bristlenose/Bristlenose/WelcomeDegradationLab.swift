#if DEBUG
import SwiftUI
import AppKit

// MARK: - Welcome Degradation Lab (Diagnostics ▸ Degradation Lab)
//
// A stress rig for ONE question: when a welcome cell is too short for its
// content, what gives — and which layer decided?
//
//   • Scale            visual op, semantic damage. Shrinks the type ladder, so
//                      `.title3` can render smaller than an unscaled
//                      `.subheadline` and the hierarchy INVERTS. This is what
//                      `BookShelfView` does today.
//   • Ellipsis         visual op, honestly marked. `…` means "material
//                      omitted" — the right protocol when the view must act
//                      alone (un-authorable strings: LLM themes, participant text).
//   • Clause split     visual op impersonating a semantic one. Infers joints
//                      from punctuation. Fails SILENTLY: emits a well-formed,
//                      correctly-punctuated sentence that has quietly shed or
//                      inverted a claim. This rig makes it fail loudly instead,
//                      by showing every candidate with its risk verdict.
//   • Authored ladder  semantic authors, visual selects. `ViewThatFits` over
//                      hand-written complete variants. The house pattern —
//                      `SlotItem.text` + `.more` already works this way.
//
// Not a shipping surface. `#if DEBUG`, launched from the Diagnostics menu like
// Keycap Gallery / Shimmer Tuner, `.commandsRemoved()` on its Window scene.
//
// Two findings the rig is built to make visible:
//
//   1. UNREFLOWABLE FURNITURE NEEDS A FLOOR. The cover fan is greedy — without
//      a declared `minHeight` the VStack always "fits" by starving the covers,
//      so `ViewThatFits` never engages and the ladder is dead code. Set covers
//      to 4 and drag Height down to watch the floor do its work.
//   2. THE HEURISTIC OVER-FLAGS. Norman's tail ("blame the design, not the
//      user") trips the negation check, but dropping it doesn't break the head.
//      A false-positive rate is exactly what this rig is for measuring — the
//      flags say "check", never "broken".

// MARK: - Corpus

struct FitSpecimen: Identifiable {
    let id = UUID()
    let group: String
    let name: String
    let title: String

    // The authored ladder, shortest rung to longest. Every rung is a COMPLETE
    // reading — none is a fragment of the one above — so the view can pick any
    // of them without editing anyone's meaning.
    //
    //   short   the minimum cell (700pt window, sidebar out): ~165×163
    //   line    the core sentence; the rung that must always fit
    //   more    a follow-up, for a default window
    //   depth   real substance, for a maximised display
    //
    // `nil` at any rung is authoring debt, not an omission — the lab badges it.
    var short: String? = nil
    let line: String
    var more: String? = nil
    var depth: String? = nil
    var covers: Int = 0

    /// Longest first — the order `ViewThatFits` needs.
    var ladder: [String] {
        var out: [String] = []
        if let m = more, let d = depth { out.append("\(line) \(m) \(d)") }
        if let m = more { out.append("\(line) \(m)") }
        out.append(line)
        if let sh = short { out.append(sh) }
        return out
    }

    var topRung: Int { (more == nil ? 0 : 1) + (depth == nil ? 0 : 1) + (short == nil ? 0 : 1) + 1 }
}

enum FitCorpus {
    static let groupOrder = ["Books (real)", "Science cell", "Study tools cell",
                             "Clause shapes", "Meaning traps", "Extremes", "Scripts"]

    // Elaboration rungs are drawn from the published docs — research-foundations,
    // signals, codebook-frameworks, tag-for-meaning and academic-sources in the
    // website repo's `docs-src/`. Nothing here is invented for the lab: the whole
    // premise of a wide-screen rung is that it is worth reading, and only the
    // real material clears that bar.
    static let all: [FitSpecimen] = [
        .init(group: "Books (real)", name: "Norman", title: "Don Norman",
              short: "Made human-centred design a discipline.",
              line: "The book that made human-centred design a discipline — blame the design, not the user.",
              more: "Its seven principles explain why interactions succeed or fail: discoverability, feedback, conceptual models, signifiers, mapping, constraints, and the difference between slips and mistakes.",
              depth: "Bristlenose ships them as a codebook you can apply by hand or through AutoCode. It is a bottom-up lens — it diagnoses why something was hard to use, where Garrett's five planes instead place a finding at the level it lives on.",
              covers: 4),
        .init(group: "Books (real)", name: "Nielsen", title: "Jakob Nielsen",
              short: "Ten heuristics that still anchor the field.",
              line: "Ten usability heuristics that still anchor how the field spots friction.",
              more: "Refined from a factor analysis of 249 real usability problems, running from \u{201C}visibility of system status\u{201D} through to \u{201C}help and documentation\u{201D}.",
              depth: "Still the most widely used checklist in usability evaluation, adapted here for coding participant quotes \u{2014} strongest at surfacing status confusion, control anxiety and error-message quality. Nielsen and Molich published the original method at CHI \u{2019}90; the refined ten followed in 1994.",
              covers: 4),
        .init(group: "Books (real)", name: "Braun & Clarke", title: "Braun & Clarke",
              short: "The guide to reflexive thematic analysis.",
              line: "The practical guide to reflexive thematic analysis \u{2014} themes from participants\u{2019} own words.",
              more: "Their six-phase method is the basis for how Bristlenose forms themes: inductively, emerging from the data rather than matched against a fixed list.",
              depth: "\u{201C}Using thematic analysis in psychology\u{201D} (Qualitative Research in Psychology, 2006) is among the most-cited papers in the social sciences. Bristlenose takes the inductive path by default; applying a codebook is the deductive one, and most studies end up using both.",
              covers: 4),
        .init(group: "Books (real)", name: "Lazarus", title: "Richard Lazarus",
              short: "Appraisal theory.",
              line: "Appraisal theory \u{2014} emotion as how we weigh what happens to us.",
              more: "The seven sentiments Bristlenose tags \u{2014} frustration, confusion, doubt, surprise, satisfaction, delight and confidence \u{2014} rest on that foundation.",
              depth: "The taxonomy is drawn from emotion science rather than invented for the product: Scherer\u{2019}s appraisal work and Russell\u{2019}s account of core affect underpin it, chosen to capture the states that matter in a research interview without over-specifying.",
              covers: 4),

        // Science-cell slots that today carry one sentence and an illustration.
        .init(group: "Science cell", name: "Emergent themes", title: "Emergent themes",
              short: "Themes emerge from participants\u{2019} own words.",
              line: "Themes emerge from participants\u{2019} own words, not a fixed taxonomy (Braun & Clarke, 2006).",
              more: "Codes are produced inductively \u{2014} you read the quotes and name what is actually there, rather than matching against a list decided in advance.",
              depth: "Applying a framework is the deductive path, and both are legitimate; most studies use a framework for structure plus their own codes for what it misses. The revision itself is the analysis \u{2014} expect to merge, rename and regroup as your understanding of the data grows."),
        .init(group: "Science cell", name: "Seven sentiments", title: "Seven sentiments",
              short: "Seven sentiments, from emotion science.",
              line: "Seven sentiments, grounded in appraisal theory (Scherer) and core affect (Russell).",
              more: "Frustration, confusion and doubt read as negative; satisfaction, delight and confidence as positive; surprise is neutral \u{2014} it flags something worth looking at, in either direction.",
              depth: "Each quote also carries an intensity from 1 to 3. The negative signals are deliberately more granular than the positive ones, because frustration, confusion and doubt each point at a different class of design problem \u{2014} performance, information architecture and credibility respectively. Purely descriptive quotes are left untagged."),
        .init(group: "Science cell", name: "Signals", title: "Signals",
              short: "A signal shows where attention concentrates.",
              line: "A signal combines how strongly participants feel, how much they focus on a theme, and how far they agree.",
              more: "Concentration compares where quotes land against an even spread; agreement counts the distinct participants behind a column \u{2014} nine quotes from nine people are not nine quotes from one.",
              depth: "The three figures combine into a strength reported as strong, moderate or emerging, and each sentiment signal carries a flag naming the shape: Win, Problem, Niggle, Success or Surprising. A negative pattern shared widely and felt strongly is a Problem; the same sentiment from one person is a Niggle. The thresholds are deliberate starting points, not measurements \u{2014} use a card to decide where to look, then read the quotes."),
        .init(group: "Science cell", name: "Dignity", title: "Dignity without distortion",
              short: "Quotes are tidied, never twisted.",
              line: "Quotes are tidied for readability \u{2014} never twisted to say something else.",
              more: "A participant should sound like themselves on a good day, and never like someone else.",
              depth: "Filler and false starts come out; meaning, hedging and strength of feeling stay in. The transcript keeps the original wording, so any tidied quote can be checked against what was actually said."),

        // The big square cell \u{2014} the one with the largest void at full screen.
        .init(group: "Study tools cell", name: "Tag", title: "Tag",
              short: "Press `t` to tag a quote.",
              line: "Select one or more quotes, and press `t` to tag them with a code from your codebook.",
              more: "In qualitative research, attaching a label to a piece of data is coding \u{2014} a tag in Bristlenose is a code.",
              depth: "Tag the meaning, not the topic. \u{201C}Onboarding\u{201D} is a topic; \u{201C}gave up before finishing onboarding\u{201D} is a finding. Codes that name a need, a barrier or a moment of confusion are the ones that turn into themes; codes that name a subject just file quotes tidily."),
        .init(group: "Study tools cell", name: "AutoCode", title: "AutoCode",
              short: "AutoCode proposes tags; you decide.",
              line: "Let AutoCode propose tags across every quote \u{2014} you Accept or Deny.",
              more: "It works from whichever codebook you have installed, so the suggestions speak your scheme rather than a generic one.",
              depth: "Patterns are only real if codes are applied consistently, which is where a machine pass earns its place \u{2014} it applies the same reading to all several hundred quotes without tiring. Every proposal is yours to reject, and the rejections are as informative as the acceptances."),
        .init(group: "Study tools cell", name: "Codebooks", title: "Codebooks",
              short: "Start from a framework, or build your own.",
              line: "Build a codebook, or start from a ready-made research framework.",
              more: "Norman, Nielsen, Garrett, Morville and Yablonski each bring a different lens to the same set of quotes, and you can layer more than one.",
              depth: "There is no single correct framework. Norman and Nielsen suit usability and interaction problems; Garrett and Morville suit broader experience and information-architecture questions; Yablonski\u{2019}s laws suit attention, memory and decision-making. The sentiment layer is always there to orient you first."),

        .init(group: "Clause shapes", name: "Em dash", title: "Em dash",
              short: "The report is one file you own.",
              line: "The report is one file you own \u{2014} open it anywhere, forever."),
        .init(group: "Clause shapes", name: "Semicolon", title: "Semicolon",
              short: "Cloud and local models both work.",
              line: "Cloud models are faster and sharper; local ones never leave your Mac."),
        .init(group: "Clause shapes", name: "Colon", title: "Colon",
              line: "One rule governs the whole grid: geometry is fixed and content bends."),
        .init(group: "Clause shapes", name: "Comma list", title: "Comma list",
              line: "Bristlenose reads sessions, participants, quotes, sections and themes."),
        .init(group: "Clause shapes", name: "Parenthetical", title: "Parenthetical",
              short: "Themes emerge from participants\u{2019} own words.",
              line: "Themes emerge from participants\u{2019} own words (Braun & Clarke, 2006) rather than a fixed taxonomy."),
        .init(group: "Clause shapes", name: "Nested markers", title: "Nested markers",
              short: "Tagging is analysis.",
              line: "Tagging is analysis \u{2014} you group quotes under a code, the findings surface, and the themes name themselves."),
        .init(group: "Clause shapes", name: "No marker", title: "No marker",
              line: "Ten usability heuristics that still anchor how the whole field spots friction today."),
        .init(group: "Clause shapes", name: "Hyphens only", title: "Hyphens only",
              line: "A human-centred, well-researched, peer-reviewed method with no clause break at all."),

        .init(group: "Meaning traps", name: "Negation in tail", title: "Negation in tail",
              short: "Quotes are tidied, never twisted.",
              line: "Quotes are tidied for readability \u{2014} never twisted to say something else."),
        .init(group: "Meaning traps", name: "Contrast in tail", title: "Contrast in tail",
              short: "Your recordings never leave your Mac.",
              line: "The analysis runs in the cloud, but your recordings never leave your Mac."),
        .init(group: "Meaning traps", name: "Balance claim", title: "Balance claim",
              short: "Cloud or local \u{2014} both are supported.",
              line: "Cloud models are faster and sharper; local ones cost nothing and stay private."),
        .init(group: "Meaning traps", name: "Payload after colon", title: "Payload after colon",
              line: "There is exactly one thing to remember: nothing is deleted without asking you first."),

        .init(group: "Extremes", name: "Very short", title: "Very short",
              line: "Appraisal theory.", covers: 2),
        .init(group: "Extremes", name: "Very long", title: "Very long",
              short: "A signal scores opinion strength, focus and agreement.",
              line: "A signal is a score combining the strength of participants\u{2019} opinions or feelings, their level of focus on an area or theme, and a measure of how much they agree with one another \u{2014} surfaced per theme, per session and across the whole study.",
              covers: 4),
        .init(group: "Extremes", name: "Unbreakable token", title: "Unbreakable token",
              line: "See https://bristlenose.app/docs/research-foundations.html for the whole method."),
        .init(group: "Extremes", name: "Markdown bold", title: "Markdown bold",
              short: "Drop **.srt**, **.vtt** or **.docx** to skip transcription.",
              line: "Drop **.srt**, **.vtt** or **.docx** and skip transcription entirely \u{2014} the text you have is enough."),

        .init(group: "Scripts", name: "\u{65E5}\u{672C}\u{8A9E} (head-final)", title: "\u{65E5}\u{672C}\u{8A9E}",
              line: "\u{30C6}\u{30FC}\u{30DE}\u{306F}\u{56FA}\u{5B9A}\u{306E}\u{5206}\u{985E}\u{3067}\u{306F}\u{306A}\u{304F}\u{3001}\u{53C2}\u{52A0}\u{8005}\u{81EA}\u{8EAB}\u{306E}\u{8A00}\u{8449}\u{304B}\u{3089}\u{7ACB}\u{3061}\u{4E0A}\u{304C}\u{308A}\u{307E}\u{3059}\u{3002}", covers: 4),
        .init(group: "Scripts", name: "\u{D55C}\u{AD6D}\u{C5B4} (head-final)", title: "\u{D55C}\u{AD6D}\u{C5B4}",
              line: "\u{C8FC}\u{C81C}\u{B294} \u{ACE0}\u{C815}\u{B41C} \u{BD84}\u{B958}\u{AC00} \u{C544}\u{B2C8}\u{B77C} \u{CC38}\u{C5EC}\u{C790} \u{C790}\u{C2E0}\u{C758} \u{B9D0}\u{C5D0}\u{C11C} \u{B5A0}\u{C624}\u{B985}\u{B2C8}\u{B2E4}.", covers: 4),
        .init(group: "Scripts", name: "\u{7E41}\u{9AD4}\u{4E2D}\u{6587}", title: "\u{7E41}\u{9AD4}\u{4E2D}\u{6587}",
              line: "\u{4E3B}\u{984C}\u{4F86}\u{81EA}\u{53C3}\u{8207}\u{8005}\u{81EA}\u{5DF1}\u{7684}\u{8A71}\u{8A9E}\u{FF0C}\u{800C}\u{4E0D}\u{662F}\u{56FA}\u{5B9A}\u{7684}\u{5206}\u{985E}\u{67B6}\u{69CB}\u{3002}", covers: 4),
        .init(group: "Scripts", name: "Deutsch (compounds)", title: "Deutsch",
              short: "Themen entstehen aus den eigenen Worten der Teilnehmenden.",
              line: "Themen entstehen aus den eigenen Worten der Teilnehmenden \u{2014} nicht aus einer vorgegebenen Kategorisierung.",
              more: "Codes entstehen induktiv: Sie lesen die Zitate und benennen, was tats\u{E4}chlich da ist.",
              covers: 4),
        .init(group: "Scripts", name: "Fran\u{E7}ais", title: "Fran\u{E7}ais",
              short: "Les th\u{E8}mes \u{E9}mergent des mots des participants.",
              line: "Les th\u{E8}mes \u{E9}mergent des mots des participants eux-m\u{EA}mes, et non d\u{2019}une taxonomie fig\u{E9}e.",
              more: "Les codes sont produits de mani\u{E8}re inductive : vous lisez les extraits et nommez ce qui s\u{2019}y trouve r\u{E9}ellement.",
              covers: 4),
    ]

    static func items(in group: String) -> [FitSpecimen] { all.filter { $0.group == group } }
}

// MARK: - Risk model

enum FitVerdict: Int, Comparable {
    case ok = 0, check = 1, refuse = 2
    static func < (a: Self, b: Self) -> Bool { a.rawValue < b.rawValue }

    var label: String { self == .ok ? "OK" : self == .check ? "CHECK" : "REFUSE" }
    var color: Color { self == .ok ? .green : self == .check ? .orange : .red }
}

struct FitRisk: Identifiable {
    let id = UUID()
    let label: String
    let detail: String
    let verdict: FitVerdict
}

struct ClauseCandidate: Identifiable {
    let id = UUID()
    let text: String
    let dropped: String
    let marker: String
    let risks: [FitRisk]
    var verdict: FitVerdict { risks.map(\.verdict).max() ?? .ok }
}

// MARK: - The algorithm under test

enum ClauseSplitter {
    private struct Marker {
        let token: String, name: String, rank: Int, verdict: FitVerdict
    }

    /// Ranked by how gracefully the tail drops. Em dash tails are nearly always
    /// an appositive or gloss; colon tails are the payload.
    private static let markers: [Marker] = [
        .init(token: " — ", name: "em dash",       rank: 0, verdict: .ok),
        .init(token: " – ", name: "en dash",       rank: 1, verdict: .ok),
        .init(token: "; ",  name: "semicolon",     rank: 2, verdict: .ok),
        .init(token: " - ", name: "spaced hyphen", rank: 3, verdict: .ok),
        .init(token: ", ",  name: "comma",         rank: 4, verdict: .check),
        .init(token: ": ",  name: "colon",         rank: 5, verdict: .refuse),
    ]

    private static let negations = ["not ", "never", "no ", "nor ", "without", "n’t", "n't"]
    private static let contrasts = ["but ", "yet ", "though", "although", "however", "whereas", "while "]

    /// Hiragana, katakana, hangul or CJK ideographs anywhere → treat as head-final.
    /// Deliberately crude: the point is that the splitter must REFUSE, not that
    /// it should try harder.
    static func isHeadFinal(_ s: String) -> Bool {
        s.unicodeScalars.contains { u in
            let v = u.value
            return (0x3040...0x30FF).contains(v)   // kana
                || (0xAC00...0xD7AF).contains(v)   // hangul syllables
                || (0x4E00...0x9FFF).contains(v)   // CJK unified ideographs
        }
    }

    /// Strip the dangling marker and restore a terminal stop.
    static func tidy(_ head: String) -> String {
        var t = head
        while let l = t.last, " \t—–-;,:".contains(l) { t.removeLast() }
        guard let l = t.last else { return t }
        if !".!?".contains(l) { t.append(".") }
        return t
    }

    /// Every candidate the splitter can produce, longest first. The FULL string
    /// is not included — index 0 is the first actual cut.
    static func candidates(for s: String) -> [ClauseCandidate] {
        guard !isHeadFinal(s) else {
            return [ClauseCandidate(
                text: s, dropped: "", marker: "—",
                risks: [FitRisk(label: "head-final script",
                                detail: "The verb lands at the end of the sentence. Cutting the tail removes the predicate and leaves a verbless fragment — ungrammatical, not merely terse. ja · ko · zh-Hant · zh-Hant-HK.",
                                verdict: .refuse)])]
        }

        var out: [ClauseCandidate] = []

        // Parenthetical excision — the one operation that is a mid-string
        // removal rather than a tail cut, and the one that rarely hurts.
        if let open = s.firstIndex(of: "("), let close = s[open...].firstIndex(of: ")") {
            let inner = String(s[s.index(after: open)..<close])
            var kept = String(s[s.startIndex..<open]) + String(s[s.index(after: close)...])
            kept = kept.replacingOccurrences(of: "  ", with: " ")
                       .replacingOccurrences(of: " ,", with: ",")
                       .trimmingCharacters(in: .whitespaces)
            out.append(ClauseCandidate(text: kept, dropped: "(\(inner))", marker: "parenthetical",
                                       risks: risks(head: kept, dropped: inner, marker: "parenthetical",
                                                    markerVerdict: .ok, rank: -1, original: s)))
        }

        // Tail cuts at every occurrence of every marker — the ladder wants
        // several lengths, not just the safest one.
        for m in markers {
            var search = s.startIndex
            while let r = s.range(of: m.token, range: search..<s.endIndex) {
                let head = tidy(String(s[s.startIndex..<r.lowerBound]))
                let tail = String(s[r.upperBound...])
                out.append(ClauseCandidate(text: head, dropped: tail, marker: m.name,
                                           risks: risks(head: head, dropped: tail, marker: m.name,
                                                        markerVerdict: m.verdict, rank: m.rank, original: s)))
                search = r.upperBound
            }
        }

        if out.isEmpty {
            return [ClauseCandidate(
                text: s, dropped: "", marker: "none",
                risks: [FitRisk(label: "no clause marker",
                                detail: "Nothing to cut. The splitter falls straight through to an ellipsis — so this string is covered by the mechanism in name only.",
                                verdict: .refuse)])]
        }

        // Longest first; ties broken by marker safety.
        var seen = Set<String>()
        return out
            .sorted { a, b in
                a.text.count == b.text.count ? a.verdict < b.verdict : a.text.count > b.text.count
            }
            .filter { seen.insert($0.text).inserted }
    }

    /// True when the text opens a bracket or quote it never closes.
    private static func isUnbalanced(_ s: String) -> Bool {
        if s.filter({ $0 == "(" }).count != s.filter({ $0 == ")" }).count { return true }
        if s.filter({ $0 == "“" }).count != s.filter({ $0 == "”" }).count { return true }
        if s.filter({ $0 == "\"" }).count % 2 != 0 { return true }
        return false
    }

    private static func risks(head: String, dropped: String, marker: String,
                              markerVerdict: FitVerdict, rank: Int, original: String) -> [FitRisk] {
        var r: [FitRisk] = []

        // Cut the OUTERMOST structure first. If a stronger marker survives in
        // the head, this cut landed inside a span that marker opened — so the
        // head keeps a dangling em dash whose resolution has been thrown away.
        // Found by the rig on Norman: the comma rung is longer than the em-dash
        // rung, so longest-first ranked a broken candidate above a clean one.
        if rank > 0, let stranded = markers.first(where: { $0.rank < rank && head.contains($0.token) }) {
            r.append(FitRisk(label: "cut inside a clause",
                             detail: "The head still carries an unresolved \(stranded.name) — this cut landed inside the span that marker opened. Cut the outermost structure first, or not at all.",
                             verdict: .refuse))
        }

        // A cut that orphans a bracket or an opening quote is indefensible on
        // any reading. Rig found it on the Braun & Clarke citation.
        if isUnbalanced(head) {
            r.append(FitRisk(label: "unbalanced delimiter",
                             detail: "The cut orphaned an opening bracket or quote. Never split inside a bracketed or quoted span — excise the whole span instead.",
                             verdict: .refuse))
        }

        if markerVerdict == .refuse {
            r.append(FitRisk(label: "colon cut",
                             detail: "The tail after a colon is the payload — the head only sets it up. Cutting here keeps the preamble and discards the point.",
                             verdict: .refuse))
        }
        if marker == "comma" {
            r.append(FitRisk(label: "comma cut",
                             detail: "A comma may join a list item, a subordinate clause or an appositive. You cannot tell which without parsing — last-comma is often fine, first-comma decapitates.",
                             verdict: .check))
        }

        let ratio = original.isEmpty ? 1 : Double(head.count) / Double(original.count)
        if head.count < 20 || ratio < 0.35 {
            r.append(FitRisk(label: "stump too short",
                             detail: String(format: "Keeps %.0f%% of the sentence (%d chars). Below the floor it reads as broken rather than brief.", ratio * 100, head.count),
                             verdict: .refuse))
        }

        let lowerTail = dropped.lowercased()
        if negations.contains(where: { lowerTail.contains($0) }) {
            r.append(FitRisk(label: "negation in tail",
                             detail: "The dropped tail carries a negation. Sometimes harmless (“blame the design, not the user”), sometimes an inversion of the claim. Read the head alone and check it still says what you meant.",
                             verdict: .check))
        }
        if contrasts.contains(where: { lowerTail.hasPrefix($0) }) {
            r.append(FitRisk(label: "contrast lost",
                             detail: "The tail opened with a contrast, so the head was a qualified claim. Alone it reads unqualified — the sentence now overstates.",
                             verdict: .check))
        }
        if dropped.filter({ $0 == "," }).count >= 1 && marker == "comma" {
            r.append(FitRisk(label: "list truncated",
                             detail: "The cut lands inside an enumeration, so the remaining list looks complete when it isn’t.",
                             verdict: .check))
        }
        return r
    }
}

// MARK: - Strategies

enum FitStrategy: String, CaseIterable, Identifiable {
    case scale    = "Scale (today)"
    case ellipsis = "Ellipsis"
    case clause   = "Clause split"
    case authored = "Authored ladder"

    var id: String { rawValue }

    var blurb: String {
        switch self {
        case .scale:    return "Visual op · collapses the type ladder"
        case .ellipsis: return "Visual op · loss is marked"
        case .clause:   return "Visual op wearing semantics · fails silently"
        case .authored: return "Semantic authors, visual selects"
        }
    }
}

// MARK: - Cover fan (the unreflowable furniture)

/// Fixed-size cards that cannot reflow — the reason a uniform scale was reached
/// for in the first place. `selfScale: false` reproduces today's behaviour
/// (fan drawn at full size inside a subtree the caller scales); `true` is the
/// proposed fix (fan takes the leftover space and scales alone).
private struct CoverFan: View {
    let count: Int
    var selfScale: Bool = true
    var floor: CGFloat = 48

    private let cardW: CGFloat = 106
    private let cardH: CGFloat = 152
    private let off: CGFloat = 34
    private let spines: [UInt] = [0x334155, 0x0F5C9E, 0x7C3AED, 0xB45309]

    /// Width the fan wants: one full cover plus a peek per extra cover.
    var naturalWidth: CGFloat { cardW + off * CGFloat(max(0, count - 1)) }

    private var fan: some View {
        ZStack(alignment: .topLeading) {
            ForEach(Array(0..<max(0, count)), id: \.self) { i in
                RoundedRectangle(cornerRadius: 5)
                    .fill(LinearGradient(colors: [labColor(spines[i % spines.count]),
                                                  labColor(spines[i % spines.count]).opacity(0.72)],
                                         startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: cardW, height: cardH)
                    .shadow(color: .black.opacity(0.22), radius: 6, y: 4)
                    .offset(x: CGFloat(i) * off)
                    .opacity(1 - Double(i) * 0.14)
                    .zIndex(Double(100 - i))
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    var body: some View {
        if count == 0 {
            EmptyView()
        } else if selfScale {
            GeometryReader { geo in
                // BOTH axes. Scaling on height alone was the obvious fix and is
                // wrong: the fan is 208pt wide at four covers, and the science
                // cell is ~165pt at minimum window size. Today's whole-subtree
                // scale accidentally covered this, because it shrank the fan
                // horizontally too — take that away without replacing it and
                // the fourth cover simply falls off the cell.
                let s = min(1, geo.size.height / cardH, geo.size.width / naturalWidth)
                fan
                    .frame(width: geo.size.width, height: cardH, alignment: .topLeading)
                    .scaleEffect(s, anchor: .topLeading)
            }
            // The floor is load-bearing. Without a minHeight the fan is greedy,
            // the VStack always "fits" by starving it, and ViewThatFits never
            // engages — the whole ladder becomes dead code.
            .frame(minHeight: floor, maxHeight: cardH)
        } else {
            fan.frame(height: cardH)
        }
    }
}

private func labColor(_ v: UInt) -> Color {
    Color(.sRGB,
          red: Double((v >> 16) & 0xFF) / 255,
          green: Double((v >> 8) & 0xFF) / 255,
          blue: Double(v & 0xFF) / 255)
}

private func labMarkdown(_ s: String) -> AttributedString {
    (try? AttributedString(markdown: s)) ?? AttributedString(s)
}

// MARK: - One strategy rendered into one fixed cell

/// Measured height of the laid-out content, so the lab can report the VOID
/// rather than estimate it. The void is the whole wide-screen question.
private struct ContentHeightKey: PreferenceKey {
    static let defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}

private struct SpecimenCell: View {
    let spec: FitSpecimen
    let strategy: FitStrategy
    let showLink: Bool
    let coverFloor: CGFloat
    let role: WelcomeCellRole
    /// Cap the text column at the 75-character ceiling instead of letting it
    /// run the full width of the cell.
    let capMeasure: Bool
    let maxTextWidth: CGFloat
    let cellHeight: CGFloat

    @State private var contentH: CGFloat = 0

    /// Title + two reserved body lines + fan + link, matching BookShelfView's 252.
    private let naturalHeight: CGFloat = 252

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(role.rawValue.uppercased())
                .font(.subheadline).fontWeight(.medium)
                .textCase(.uppercase).kerning(0.4)
                .foregroundStyle(.secondary)
            content
            dots   // the rotator's page indicator — 26pt the text never gets
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .padding(role.padding)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(nsColor: .controlBackgroundColor))
                .overlay(RoundedRectangle(cornerRadius: 10).fill(Color.accentColor.opacity(0.06)))
        )
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10)
            .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
        .onPreferenceChange(ContentHeightKey.self) { contentH = $0 }
        .overlay(alignment: .bottomTrailing) { fillBadge }
    }

    /// Void as a share of the cell. On a maximised display this is the number
    /// that decides whether longer prose is even the right lever.
    private var fillBadge: some View {
        let usable = max(1, cellHeight - role.furniture + 26 + 6)   // dots stay in the flow
        let pct = min(100, contentH / usable * 100)
        return Text("\(Int(pct))%")
            .font(.system(size: 9, weight: .bold, design: .monospaced))
            .foregroundStyle(pct < 55 ? Color.red : pct < 80 ? Color.orange : Color.secondary)
            .padding(.horizontal, 4).padding(.vertical, 1)
            .background(RoundedRectangle(cornerRadius: 3)
                .fill(Color(nsColor: .windowBackgroundColor).opacity(0.85)))
            .padding(5)
    }

    private var dots: some View {
        HStack(spacing: 0) {
            ForEach(Array(0..<5), id: \.self) { i in
                Capsule()
                    .fill(Color.accentColor.opacity(i == 1 ? 0.8 : 0.22))
                    .frame(width: i == 1 ? 14 : 6, height: 6)
                    .frame(width: 16)
            }
        }
        .frame(height: 26)
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder private var content: some View {
        switch strategy {
        case .scale:
            // Today's BookShelfView, verbatim in shape: the WHOLE subtree —
            // caption, fan and link — inside one uniform scale.
            GeometryReader { geo in
                let s = min(1, geo.size.height / naturalHeight)
                stack { body(spec.line, limit: nil) }
                    .frame(width: geo.size.width, height: naturalHeight, alignment: .topLeading)
                    .scaleEffect(s, anchor: .topLeading)
            }

        case .ellipsis:
            stack {
                ViewThatFits(in: .vertical) {
                    body(spec.line, limit: 4)
                    body(spec.line, limit: 3)
                    body(spec.line, limit: 2)
                    body(spec.line, limit: 1)
                }
            }

        case .clause:
            stack {
                ViewThatFits(in: .vertical) {
                    body(spec.line, limit: nil)
                    ForEach(usableCandidates) { c in body(c.text, limit: nil) }
                    body(spec.line, limit: 1)   // honest fallback when the ladder runs out
                }
            }

        case .authored:
            // Bidirectional. `ViewThatFits` takes the first candidate that fits,
            // so a longest-first list elaborates on a Studio Display and
            // contracts on a 700pt window through the SAME mechanism — no mode
            // switch, no second code path, and every rung a complete reading.
            stack {
                ViewThatFits(in: .vertical) {
                    ForEach(Array(spec.ladder.enumerated()), id: \.offset) { pair in
                        body(pair.element, limit: nil)
                    }
                    Color.clear.frame(height: 0)   // title alone — the last rung
                }
            }
        }
    }

    /// Candidates the splitter would actually be allowed to use.
    private var usableCandidates: [ClauseCandidate] {
        ClauseSplitter.candidates(for: spec.line).filter { $0.verdict != .refuse }
    }

    private func stack<C: View>(@ViewBuilder _ text: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(spec.title).font(.title3).fontWeight(.semibold)
            text()
            if spec.covers > 0 {
                CoverFan(count: spec.covers,
                         selfScale: strategy != .scale,
                         floor: coverFloor)
            }
            if showLink {
                Text("Learn more →").font(.callout).foregroundStyle(Color.accentColor)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(GeometryReader { g in
            Color.clear.preference(key: ContentHeightKey.self, value: g.size.height)
        })
    }

    private func body(_ s: String, limit: Int?) -> some View {
        Text(labMarkdown(s))
            .font(.body).foregroundStyle(.secondary)
            .lineLimit(limit)
            .truncationMode(.tail)
            .frame(maxWidth: capMeasure ? maxTextWidth : .infinity, alignment: .topLeading)
            .frame(maxWidth: .infinity, alignment: .topLeading)
    }
}

// MARK: - Analysis readout

private struct LadderReadout: View {
    let line: String

    var body: some View {
        let cands = ClauseSplitter.candidates(for: line)
        VStack(alignment: .leading, spacing: 10) {
            Text("Clause ladder")
                .font(.system(size: 13, weight: .semibold))
            Text("What the splitter proposes, longest first. A REFUSE rung is one the algorithm must not take; CHECK is a rung a human has to read before shipping.")
                .font(.caption).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            ForEach(cands) { c in
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(c.verdict.label)
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 5).padding(.vertical, 2)
                            .background(RoundedRectangle(cornerRadius: 3).fill(c.verdict.color))
                        Text("cut at \(c.marker)")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text("\(c.text.count) ch").font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.tertiary)
                    }
                    Text(c.text).font(.callout)
                        .fixedSize(horizontal: false, vertical: true)
                    if !c.dropped.isEmpty {
                        Text("dropped: \(c.dropped)")
                            .font(.caption).foregroundStyle(.tertiary)
                            .strikethrough()
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    ForEach(c.risks) { r in
                        HStack(alignment: .top, spacing: 5) {
                            Circle().fill(r.verdict.color).frame(width: 5, height: 5).padding(.top, 5)
                            VStack(alignment: .leading, spacing: 1) {
                                Text(r.label).font(.caption).fontWeight(.medium)
                                Text(r.detail).font(.caption2).foregroundStyle(.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                }
                .padding(9)
                .background(RoundedRectangle(cornerRadius: 6)
                    .fill(Color(nsColor: .controlBackgroundColor)))
                .overlay(RoundedRectangle(cornerRadius: 6)
                    .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
            }
        }
    }
}

// MARK: - The real geometry
//
// Both dimensions of every welcome cell derive from ONE number — the content
// width — because the spiral is framed `width: w, height: w / 1.618`
// (`WelcomeHomeView.swift:207`). So a height-only sweep tests a shape the app
// can never produce. The science cell is the major half of a vertical split
// inside the minor column of a horizontal one:
//
//     w      = contentWidth - 40                 // 20pt margin each side
//     cellW  = (w - 8) * 0.382                   // minor column of the outer split
//     cellH  = (w / 1.618 - 8) * 0.618           // major half of the inner split
//
// Which makes it very nearly SQUARE at every size, and means narrowing the
// window takes width and height away *together* — text wraps to more lines at
// the exact moment there is less room for lines. That compounding is the whole
// difficulty, and it is invisible if you sweep one axis at a time.
/// Which cell of the spiral is under test. They are NOT interchangeable: each
/// sits at a different depth of the split, so the same window width hands them
/// very different boxes — and the void at full screen is worst in the biggest.
enum WelcomeCellRole: String, CaseIterable, Identifiable {
    case studyTools = "Study tools"
    case science    = "Scientific background"
    case tip        = "Tip"

    var id: String { rawValue }
    var isLarge: Bool { self != .tip }
    var padding: CGFloat { isLarge ? 16 : 10 }

    /// Fixed chrome the text never gets: padding, the category tag, the
    /// rotator's dots row, and — in the study-tools cell — the drop card.
    var furniture: CGFloat {
        switch self {
        case .studyTools: return 32 + 17 + 8 + 26 + 6 + 100
        case .science:    return 32 + 17 + 8 + 26 + 6
        case .tip:        return 20 + 17 + 6 + 26 + 6
        }
    }
}

struct WelcomeGeometry {
    static let phi: CGFloat = 0.618
    static let gutter: CGFloat = 8

    let contentWidth: CGFloat
    let role: WelcomeCellRole

    var w: CGFloat { max(0, contentWidth - 40) }
    var spiralHeight: CGFloat { w / 1.618 }
    private var majorW: CGFloat { (w - Self.gutter) * Self.phi }
    private var minorW: CGFloat { max(0, (w - Self.gutter) * 0.382) }

    var cellW: CGFloat {
        switch role {
        case .studyTools: return max(0, majorW)
        case .science:    return minorW
        case .tip:        return max(0, (minorW - Self.gutter) * Self.phi)
        }
    }

    var cellH: CGFloat {
        switch role {
        case .studyTools: return max(0, spiralHeight)
        case .science:    return max(0, (spiralHeight - Self.gutter) * Self.phi)
        case .tip:        return max(0, (spiralHeight - Self.gutter) * 0.382)
        }
    }

    /// Vertical budget the content actually competes for.
    var budget: CGFloat { max(0, cellH - role.furniture) }

    /// The scale `BookShelfView` applies today — including to the prose.
    var todaysScale: CGFloat { min(1, budget / 252) }

    /// Text column width, and that width expressed as a MEASURE in characters.
    /// SF Pro at 13pt averages ~6.3pt per character.
    var textWidth: CGFloat { max(0, cellW - role.padding * 2) }
    var measure: Int { Int(textWidth / 6.3) }

    /// The classic typographic comfortable range. Above the ceiling the eye
    /// loses its place returning to the next line — which is why "just write
    /// more words" cannot be the whole answer to a Studio Display.
    static let measureFloor = 45
    static let measureCeiling = 75

    /// Width at which the measure hits the ceiling — where a column cap has to
    /// take over from simply letting the paragraph run.
    var cappedTextWidth: CGFloat { min(textWidth, CGFloat(Self.measureCeiling) * 6.3) }
}

// MARK: - The lab

struct WelcomeDegradationLab: View {
    @State private var selection: UUID? = FitCorpus.all.first?.id
    @State private var windowW: CGFloat = 1000
    @State private var sidebarW: CGFloat = 220
    @State private var phiLinked = true
    @State private var role: WelcomeCellRole = .science
    @State private var capMeasure = true
    /// Only consulted when `phiLinked` is off — freehand exploration.
    @State private var freeW: CGFloat = 300
    @State private var freeH: CGFloat = 300
    @State private var covers: Int = 4
    @State private var coverFloor: CGFloat = 48
    @State private var showLink = true
    @State private var dark = false
    @State private var sweeping = false
    @State private var sweepDown = true
    @State private var useCustom = false
    @State private var customTitle = ""
    @State private var customLine = ""
    @State private var customShort = ""
    @State private var customMore = ""
    @State private var customDepth = ""

    private let sweep = Timer.publish(every: 0.03, on: .main, in: .common).autoconnect()
    /// The app's own limits: `.frame(minWidth: 700)` on the main window
    /// (BristlenoseApp.swift:144), sidebar 180…300 (ContentView.swift:601).
    private let minWindow: CGFloat = 700
    private let maxWindow: CGFloat = 1800

    private var geometry: WelcomeGeometry {
        WelcomeGeometry(contentWidth: windowW - sidebarW, role: role)
    }
    private var cellW: CGFloat { phiLinked ? geometry.cellW : freeW }
    private var cellH: CGFloat { phiLinked ? geometry.cellH : freeH }

    private var activeSpec: FitSpecimen {
        if useCustom {
            return FitSpecimen(group: "Custom", name: "Custom",
                               title: customTitle.isEmpty ? "Custom specimen" : customTitle,
                               short: customShort.isEmpty ? nil : customShort,
                               line: customLine.isEmpty ? "Type a line to stress-test it." : customLine,
                               more: customMore.isEmpty ? nil : customMore,
                               depth: customDepth.isEmpty ? nil : customDepth,
                               covers: covers)
        }
        var s = FitCorpus.all.first(where: { $0.id == selection }) ?? FitCorpus.all[0]
        s.covers = covers
        return s
    }

    var body: some View {
        HSplitView {
            sidebar.frame(minWidth: 210, idealWidth: 230, maxWidth: 300)
            stage.frame(minWidth: 700)
        }
        .preferredColorScheme(dark ? .dark : .light)
        .toolbar {
            ToolbarItemGroup {
                Toggle("Link", isOn: $showLink)
                Picker("", selection: $role) {
                    ForEach(WelcomeCellRole.allCases) { Text($0.rawValue).tag($0) }
                }
                .labelsHidden().frame(width: 160)
                Toggle("Cap measure", isOn: $capMeasure)
                Toggle("φ-linked", isOn: $phiLinked)
                Toggle("Custom", isOn: $useCustom)
                Toggle("Sweep", isOn: $sweeping)
                Toggle("Dark", isOn: $dark)
            }
        }
        .onReceive(sweep) { _ in
            guard sweeping else { return }
            // Drag the WINDOW, which is the only thing a user can actually drag.
            let step: CGFloat = 4
            if sweepDown {
                windowW -= step
                if windowW <= minWindow { windowW = minWindow; sweepDown = false }
            } else {
                windowW += step
                if windowW >= maxWindow { windowW = maxWindow; sweepDown = true }
            }
        }
        .onChange(of: selection) { _, _ in
            covers = FitCorpus.all.first(where: { $0.id == selection })?.covers ?? 0
        }
        .frame(minWidth: 980, minHeight: 700)
    }

    // MARK: Sidebar

    private var sidebar: some View {
        VStack(spacing: 0) {
            List(selection: $selection) {
                ForEach(FitCorpus.groupOrder, id: \.self) { group in
                    Section(group) {
                        ForEach(FitCorpus.items(in: group)) { spec in
                            HStack(spacing: 6) {
                                Text(spec.name).font(.callout)
                                Spacer()
                                // How many rungs this specimen actually has.
                                // Fewer than 3 means it cannot elaborate on a
                                // wide display — visible authoring debt.
                                Text("\(spec.topRung)")
                                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                                    .foregroundStyle(spec.topRung >= 4 ? .green
                                                     : spec.topRung >= 3 ? .secondary : .orange)
                            }
                            .tag(spec.id)
                        }
                    }
                }
            }
            .disabled(useCustom)
            .opacity(useCustom ? 0.4 : 1)

            if useCustom {
                Divider()
                VStack(alignment: .leading, spacing: 6) {
                    Text("CUSTOM").font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundStyle(.secondary)
                    TextField("Title", text: $customTitle)
                    TextField("Line", text: $customLine, axis: .vertical).lineLimit(2...5)
                    TextField("Short rung (optional)", text: $customShort, axis: .vertical).lineLimit(1...3)
                    TextField("More rung (optional)", text: $customMore, axis: .vertical).lineLimit(1...4)
                    TextField("Depth rung (optional)", text: $customDepth, axis: .vertical).lineLimit(1...6)
                }
                .textFieldStyle(.roundedBorder)
                .font(.caption)
                .padding(10)
            }
        }
    }

    // MARK: Stage

    private var stage: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                intro
                rig
                grid
                Divider()
                LadderReadout(line: activeSpec.line)
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Degradation Lab").font(.system(size: 22, weight: .semibold))
            Text("Four strategies, one specimen, one cell — pick which cell of the spiral in the toolbar; they sit at different depths of the split and get very different boxes from the same window. Four strategies, one specimen, one cell. The rig is driven by the only number a user can actually change — the window width — and both cell dimensions derive from it exactly as the φ-spiral does, so the cell stays near-square and narrows and shortens together. Drag it, or hit Sweep. Scale keeps every word and destroys the type hierarchy; the clause splitter keeps the hierarchy and quietly edits the claim.")
                .font(.callout).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: 720, alignment: .leading)
        }
    }

    private var rig: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 14) {
                if phiLinked {
                    labelled("Window width", "\(Int(windowW))") {
                        Slider(value: $windowW, in: minWindow...maxWindow).frame(width: 210)
                    }
                    labelled("Sidebar", sidebarW == 0 ? "hidden" : "\(Int(sidebarW))") {
                        Picker("", selection: $sidebarW) {
                            Text("Hidden").tag(CGFloat(0))
                            Text("180").tag(CGFloat(180))
                            Text("220").tag(CGFloat(220))
                            Text("300").tag(CGFloat(300))
                        }
                        .labelsHidden().pickerStyle(.segmented).frame(width: 210)
                    }
                } else {
                    labelled("Width", "\(Int(freeW))") {
                        Slider(value: $freeW, in: 140...560).frame(width: 210)
                    }
                    labelled("Height", "\(Int(freeH))") {
                        Slider(value: $freeH, in: 90...560).frame(width: 210)
                    }
                }
                labelled("Covers", "\(covers)") {
                    Stepper("", value: $covers, in: 0...4).labelsHidden()
                }
                labelled("Cover floor", "\(Int(coverFloor))") {
                    Slider(value: $coverFloor, in: 0...96).frame(width: 120)
                }
            }
            derived
            Text("The ladder runs BOTH ways. Longest-first candidates mean the same ViewThatFits that contracts at 700pt elaborates on a Studio Display — but only to a point: past ~75 characters a line is too long to track back from, so a maximised cell needs a capped column plus more elements, not just more words. Width is the harder axis. Narrowing the window takes width and height away together — the line wraps to more rows at the same moment there are fewer rows to give it — so the squeeze compounds rather than adds. Cover floor at 0 is the second trap: the fan turns greedy, the stack always “fits” by starving it, and every ViewThatFits ladder silently stops engaging.")
                .font(.caption).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: 760, alignment: .leading)
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color(nsColor: .windowBackgroundColor)))
        .overlay(RoundedRectangle(cornerRadius: 8)
            .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5))
    }

    /// The chain from the one number the user can actually drag, to the scale
    /// today's shelf applies to its own prose.
    @ViewBuilder private var derived: some View {
        let g = geometry
        HStack(spacing: 0) {
            metric("content", "\(Int(g.contentWidth))")
            arrow
            metric("spiral w", "\(Int(g.w))")
            arrow
            metric("cell", "\(Int(cellW))×\(Int(cellH))")
            arrow
            metric("budget", "\(Int(g.budget))")
            arrow
            metric("measure", "\(g.measure)ch",
                   alarm: g.measure > WelcomeGeometry.measureCeiling || g.measure < WelcomeGeometry.measureFloor)
            arrow
            metric("today’s scale", String(format: "%.2f", g.todaysScale),
                   alarm: g.todaysScale < 0.8)
            arrow
            metric("top rung", "\(activeSpec.topRung)", alarm: activeSpec.topRung < 3)
            if covers > 0 {
                arrow
                let fanW = 106 + 34 * CGFloat(covers - 1)
                metric("fan wants", "\(Int(fanW))w", alarm: fanW > cellW - 32)
            }
        }
        .opacity(phiLinked ? 1 : 0.35)
    }

    private var arrow: some View {
        Text("→").font(.system(size: 9)).foregroundStyle(.tertiary).padding(.horizontal, 7)
    }

    private func metric(_ name: String, _ value: String, alarm: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(name).font(.system(size: 9)).foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundStyle(alarm ? Color.red : Color.primary)
        }
    }

    private func labelled<C: View>(_ name: String, _ value: String, @ViewBuilder _ control: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 4) {
                Text(name).font(.caption).foregroundStyle(.secondary)
                Text(value).font(.system(size: 10, design: .monospaced)).foregroundStyle(.tertiary)
            }
            control()
        }
    }

    private var grid: some View {
        ScrollView(.horizontal, showsIndicators: true) {
            gridBody.padding(.bottom, 6)
        }
    }

    private var gridBody: some View {
        LazyVGrid(columns: [GridItem(.fixed(cellW), spacing: 22),
                            GridItem(.fixed(cellW), spacing: 22)],
                  alignment: .leading, spacing: 22) {
            ForEach(FitStrategy.allCases) { s in
                VStack(alignment: .leading, spacing: 5) {
                    Text(s.rawValue).font(.system(size: 12, weight: .semibold))
                    Text(s.blurb).font(.caption2).foregroundStyle(.secondary)
                    SpecimenCell(spec: activeSpec, strategy: s,
                                 showLink: showLink, coverFloor: coverFloor,
                                 role: role, capMeasure: capMeasure,
                                 maxTextWidth: geometry.cappedTextWidth,
                                 cellHeight: cellH)
                        .frame(width: cellW, height: cellH)
                }
            }
        }
    }
}

#Preview("Degradation Lab") {
    WelcomeDegradationLab().frame(width: 1240, height: 900)
}
#endif
