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

    @Test("Exactly the distress and drift states have a door")
    func everyVariantIsClassified() {
        // Named, not counted: a count is satisfied by the wrong six as easily as
        // the right six, and says nothing when it changes. This set IS the
        // contract — gaining or losing a door fails here and names which.
        let actionable = Set(Self.exemplars.filter { $0.glyphAction != .none }.map(\.tag))
        #expect(actionable == [.cantFind, .failed, .failedDiagnostic,
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

    @Test("cantFind's glyph performs the Locate it names")
    func cantFindRoutesToLocate() {
        // It described itself in-source as "a Locate affordance" while rendering
        // as a static `NSImageView`; Locate lived only in the context menu.
        for reason in [CantFindReason.moved, .missingBookmark,
                       .unmountedVolume(name: "Backup"), .networkUnreachable(host: "nas")] {
            #expect(SubtitleVariant.cantFind(reason: reason).glyphAction == .locate)
        }
    }

    @Test("Both data-drift deltas reach the files sheet")
    func deltasRouteToFiles() {
        // `.unanalysed` was a `Button` on the SwiftUI row and lost its click in
        // the AppKit cutover; `.missing` never had one.
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
