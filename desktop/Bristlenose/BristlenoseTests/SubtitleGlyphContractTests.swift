import Foundation
import Testing

@testable import Bristlenose

/// The sidebar status line's glyph contract: **every state is classified, and a
/// glyph and its destination are decided together.**
///
/// Written after the 26 Aug 2026 audit. The defect it pins is not a wrong value
/// but an *unasked question*: `subtitlePrefixGlyph` — the one function deciding
/// whether a row draws a glyph — ended in `default: return nil`, while the three
/// sibling switches over the same enum each carried a written comment forbidding
/// exactly that arm. So `.unreachable` and `.deltaOnly(.missing)` fell through it
/// silently, and no compiler error and no test ever asked.
///
/// The existing `ProjectSubtitleTests` could not have caught it: they assert
/// which variant *wins* the precedence chain, never what the winner renders. And
/// every test touching `.unreachable` passed a throwaway string (`"volume gone"`,
/// `"offline"`, `"x"`) because the payload was `String` — so they proved the
/// value round-tripped and nothing about whether it was a legal message.
///
/// The companion Python gate (`tests/test_sidebar_status_line_contract.py`) owns
/// what the strings *say*; this file owns which states have a door.
@Suite struct SubtitleGlyphContractTests {

    // MARK: - Exhaustiveness scaffolding

    /// One tag per `SubtitleVariant` case.
    ///
    /// This is the compile-time half of the guard: `tag` below switches over
    /// every case with **no `default`**, so adding a case to `SubtitleVariant`
    /// stops this test target compiling until it is classified here — and
    /// `everyVariantHasAnExemplar` then fails until it is also exercised. The
    /// two together are what the production `default:` arm was standing in the
    /// way of.
    enum VariantTag: CaseIterable {
        case cantFind, failed, failedDiagnostic, completedPartial, stopping
        case running, queued, stopped, partial, unreachable, addingInterviews
        case copying, importingBatch, copyCancelling, ready, deltaOnly, placeholder
    }

    /// Every case, once, with a representative payload.
    static let exemplars: [SubtitleVariant] = [
        .cantFind(reason: .moved),
        .failed(summary: "All topic segmentation calls failed."),
        .failedDiagnostic,
        .completedPartial,
        .stopping,
        .running,
        .queued(position: 2),
        .stopped,
        .partial(transcribeOnly: true),
        .unreachable(reason: .timedOut),
        .addingInterviews(count: 3),
        .copying(fraction: 0.5),
        .importingBatch(done: 3, total: 4),
        .copyCancelling,
        .ready(date: Date(timeIntervalSince1970: 1_000_000), delta: nil),
        .deltaOnly(.unanalysed(count: 2)),
        .placeholder,
    ]

    @Test("Every SubtitleVariant case is exercised by an exemplar")
    func everyVariantHasAnExemplar() {
        let covered = Set(Self.exemplars.map(\.tag))
        let missing = VariantTag.allCases.filter { !covered.contains($0) }
        #expect(missing.isEmpty, "unexercised variants: \(missing)")
    }

    // MARK: - The contract

    @Test("A door exists only where there is detail with no other home")
    func everyVariantIsClassified() {
        // Named, not counted: a count is satisfied by the wrong five as easily
        // as the right five. This set IS the contract — gaining or losing a door
        // fails here and names which.
        //
        // `.cantFind` is deliberately absent. It carries a glyph (your project
        // is unreachable — look) but no door: its one fact, the volume or host
        // name, is already in the subtitle, and Locate is a general project verb
        // that belongs in right-click. An earlier version of this test asserted
        // the opposite, on a rule invented in `ProjectSubtitle.swift` rather than
        // taken from the design — which is how a gate comes to enforce something
        // nobody agreed to.
        let actionable = Set(Self.exemplars.filter { $0.glyphAction != .none }.map(\.tag))
        #expect(actionable == [.failed, .failedDiagnostic,
                               .completedPartial, .unreachable, .deltaOnly],
                "actionable set drifted: \(actionable.sorted { "\($0)" < "\($1)" })")
    }

    @Test("Unreachable opens the diagnostic popover — for every reason")
    func unreachableIsDiagnostic() {
        for reason in UnreachableReason.allCases {
            let variant = SubtitleVariant.unreachable(reason: reason)
            #expect(variant.glyphAction == .diagnostics,
                    "\(reason) must have a door — it renders a glyph")
            #expect(variant.isDiagnostic)
            // The row dims: "can't be opened right now", same as `.cantFind`.
            #expect(variant.isUnreachable)
        }
    }

    @Test("cantFind marks, it does not act")
    func cantFindIsAMarkerNotADoor() {
        // The house rule is that inline glyphs are typographic markers
        // (`design-pipeline-diagnostic-popover.md`), and the sidebar is
        // "attention, not affordance". A glyph earns the glance; it does not
        // owe a click.
        for reason in [CantFindReason.moved, .missingBookmark,
                       .unmountedVolume(name: "Backup"), .networkUnreachable(host: "nas")] {
            #expect(SubtitleVariant.cantFind(reason: reason).glyphAction == .none)
        }
    }

    @Test("Both data-drift deltas reach the files popover")
    func deltasRouteToFiles() {
        // A list is the canonical thing that earns a door: a context menu shows
        // verbs and cannot show one, so this content has no other home. It went
        // briefly to `NewFilesSheet` — a modal three separate artefacts had
        // already recorded as wrong — before landing on the popover.
        #expect(SubtitleVariant.deltaOnly(.unanalysed(count: 2)).glyphAction == .files)
        #expect(SubtitleVariant.deltaOnly(.missing(count: 3)).glyphAction == .files)
        // A `.ready` carrying a delta is the same disagreement with a date in
        // front of it; a clean `.ready` has nothing to say.
        let date = Date(timeIntervalSince1970: 1_000_000)
        #expect(SubtitleVariant.ready(date: date, delta: .missing(count: 1)).glyphAction == .files)
        #expect(SubtitleVariant.ready(date: date, delta: nil).glyphAction == .none)
    }

    @Test("Progress states carry no glyph and no door — info, by the 18 Jun rulings")
    func progressStatesAreInert() {
        let progress: [SubtitleVariant] = [
            .stopping, .running, .queued(position: 1), .stopped,
            .partial(transcribeOnly: true), .addingInterviews(count: 1),
            .copying(fraction: 0.5), .importingBatch(done: 1, total: 2),
            .copyCancelling, .placeholder,
        ]
        for variant in progress {
            #expect(variant.glyphAction == .none,
                    "\(variant) is progress, not distress — its affordance is the ring's hover-cancel")
        }
    }

    // MARK: - Attention: does this earn the glance?

    @Test("A door implies a glyph — no invisible click targets")
    func everyDoorHasAGlyph() {
        // The sound half of the rule this suite originally over-stated. A glyph
        // need not have a door (`.cantFind` marks and doesn't act), but a door
        // must have a glyph: a click target the researcher cannot see is worse
        // than no target. Briefly violated when the unanalysed delta's *text*
        // was made clickable with no signifier at all.
        for variant in Self.exemplars where variant.glyphAction != .none {
            #expect(variant.glyphKind != nil,
                    "\(variant.tag) opens something with nothing drawn to click")
        }
    }

    @Test("Extra files are blue info, missing files are orange warning")
    func driftKindsFollowSeverity() {
        // Nothing has gone wrong when files are waiting — there is more material
        // than the report has read, and the researcher put it there. Orange
        // would be the app scolding someone for using Finder.
        #expect(SubtitleVariant.deltaOnly(.unanalysed(count: 3)).glyphKind == .info)
        // Files that were analysed and have since vanished are a different
        // condition: the report cites recordings that aren't there.
        #expect(SubtitleVariant.deltaOnly(.missing(count: 2)).glyphKind == .warning)
    }

    @Test("The glyph marks news, not the availability of an act")
    func glyphMarksNewsNotActs() {
        // The distinction the whole rule turns on. `.stopped` and `.partial`
        // both have something the researcher *could* do — resume, analyse — and
        // get no glyph, because they already know: they caused it. `.unanalysed`
        // has the same shape of act and does get one, because the app noticed
        // something that happened outside it.
        #expect(SubtitleVariant.stopped.glyphKind == nil)
        #expect(SubtitleVariant.partial(transcribeOnly: true).glyphKind == nil)
        #expect(SubtitleVariant.deltaOnly(.unanalysed(count: 1)).glyphKind != nil)
    }

    @Test("Progress states say nothing at all")
    func progressHasNoGlyph() {
        for variant in [SubtitleVariant.running, .stopping, .queued(position: 1),
                        .copying(fraction: 0.4), .importingBatch(done: 1, total: 2),
                        .addingInterviews(count: 2), .copyCancelling, .placeholder] {
            #expect(variant.glyphKind == nil, "\(variant.tag) is progress, not news")
        }
    }

    @Test("cantFind's colour comes from its kind, its symbol from the reason")
    func cantFindKeepsReasonSpecificSymbol() {
        // One state, three pictures — an unmounted volume, an unreachable host
        // and a moved folder are different situations. Only the tint is shared,
        // which is what stops it drifting from the rest of the vocabulary.
        #expect(SubtitleVariant.cantFind(reason: .moved).glyphKind == .warning)
        #expect(ProjectAvailability.cantFind(reason: .unmountedVolume(name: "Backup"))
            .sfSymbolName == "externaldrive.badge.xmark")
        #expect(ProjectAvailability.cantFind(reason: .networkUnreachable(host: "nas"))
            .sfSymbolName == "network.slash")
        #expect(ProjectAvailability.cantFind(reason: .moved).sfSymbolName == "questionmark.folder")
    }

    // MARK: - The payload that used to be a String

    @Test("Every unreachable reason carries a kind and two distinct locale keys")
    func reasonsAreFullySpecified() {
        let labels = Set(UnreachableReason.allCases.map(\.localeKey))
        let explanations = Set(UnreachableReason.allCases.map(\.explanationKey))
        #expect(labels.count == UnreachableReason.allCases.count, "locale keys must be distinct")
        #expect(explanations.count == UnreachableReason.allCases.count)
        #expect(labels.isDisjoint(with: explanations), "row and popover must not share a key")

        for reason in UnreachableReason.allCases {
            // The discriminator is usability + self-resolution, not cause:
            // warning where it may come back on its own, error where something
            // must change. Never success/info/skipped — this row is distress.
            #expect([.warning, .error].contains(reason.kind), "\(reason) has kind \(reason.kind)")
            #expect(reason.localeKey.hasPrefix("desktop."), "keys are namespaced by file")
            #expect(reason.explanationKey.hasPrefix("desktop."))
        }
    }

    @Test("Reason kinds match the 18 Jun rulings table")
    func reasonKindsFollowTheRulings() {
        // "still fetching after ~3 min → warning: a human should look, but
        // nothing failed"; "file resident but unreadable → error".
        #expect(UnreachableReason.timedOut.kind == .warning)
        #expect(UnreachableReason.folderMissing.kind == .warning)
        #expect(UnreachableReason.unreadable.kind == .error)
        #expect(UnreachableReason.damaged.kind == .error)
        #expect(UnreachableReason.scanFailed.kind == .error)
    }

    @Test("The copy payload carries the CLI glyph, the headline and the path")
    func unreachablePlaintextIsPasteable() {
        let text = ProjectDiagnosticPopover.formatUnreachablePlaintext(
            kind: .warning, headline: "Not responding",
            explanation: "The folder didn't answer.",
            projectName: "Study 3", projectPath: "/Volumes/Backup/Study 3")
        #expect(text.contains("⚠"), "plaintext uses the Unicode glyph so it reads like a CLI line")
        #expect(text.contains("Study 3"))
        #expect(text.contains("/Volumes/Backup/Study 3"), "the path is the diagnosis")
        #expect(text.contains("Not responding"))
    }
}

private extension SubtitleVariant {
    /// **Exhaustive, no `default`** — this is the compile-time guard. A new case
    /// in `SubtitleVariant` breaks the test target here.
    var tag: SubtitleGlyphContractTests.VariantTag {
        switch self {
        case .cantFind:         return .cantFind
        case .failed:           return .failed
        case .failedDiagnostic: return .failedDiagnostic
        case .completedPartial: return .completedPartial
        case .stopping:         return .stopping
        case .running:          return .running
        case .queued:           return .queued
        case .stopped:          return .stopped
        case .partial:          return .partial
        case .unreachable:      return .unreachable
        case .addingInterviews: return .addingInterviews
        case .copying:          return .copying
        case .importingBatch:   return .importingBatch
        case .copyCancelling:   return .copyCancelling
        case .ready:            return .ready
        case .deltaOnly:        return .deltaOnly
        case .placeholder:      return .placeholder
        }
    }
}
