import Foundation
import Testing
@testable import Bristlenose

/// The availability truth table — the state machine IS the test. Each case
/// names one row; the walk-back suite pins the D1-C reconciliation direction
/// (prior answers while loading, document identity overturns it).
struct LensAvailabilityTests {

    private func derive(
        pane: DetailPaneKind = .report,
        serveState: ServeState = .running(port: 8150),
        documentState: DocumentState = .loading,
        prior: Bool = false
    ) -> LensAvailability {
        LensAvailability.derive(
            pane: pane,
            serveState: serveState,
            documentState: documentState,
            priorPredictsViewableDocument: prior
        )
    }

    // MARK: - Pane gates (no document will mount → never available)

    @Test func noProjectIsUnavailable() {
        #expect(derive(pane: .noProject) == .unavailable(.noProject))
    }

    @Test func unreachableProjectIsUnavailable() {
        #expect(derive(pane: .unavailable) == .unavailable(.projectUnreachable))
    }

    @Test func nonDocumentPanesAreUnavailable() {
        #expect(derive(pane: .shoal, prior: true) == .unavailable(.noDocument))
        #expect(derive(pane: .dragInterviews, prior: true) == .unavailable(.noDocument))
        #expect(derive(pane: .unsupportedSubset, prior: true) == .unavailable(.noDocument))
    }

    // MARK: - Serve gate

    @Test func failedSidecarIsUnavailableWhateverThePriorSays() {
        #expect(derive(serveState: .failed(error: "boom"), prior: true)
                == .unavailable(.serveFailed))
    }

    // MARK: - Document identity is definitive

    @Test func spaDocumentIsAvailableEvenAgainstAPessimisticPrior() {
        // The dim→lit walk-back: prior said no (e.g. failed project whose
        // serve turns out to have a report — P5's world), document wins.
        #expect(derive(documentState: .spa, prior: false) == .available)
    }

    @Test func statusPageIsUnavailableEvenAgainstAnOptimisticPrior() {
        // The lit→dim walk-back: prior said yes, the document turned out to
        // be the status page — the rare, expensive direction. Every outcome
        // dims identically; the outcome names the reason, not the behaviour.
        for outcome in [StatusPageOutcome.noRun, .failed, .cancelled, .unknown] {
            #expect(derive(documentState: .statusPage(outcome), prior: true)
                    == .unavailable(.statusPage))
        }
    }

    // MARK: - Loading: the prior answers (D1-C)

    @Test func loadingFollowsThePrior() {
        #expect(derive(documentState: .loading, prior: true) == .available)
        #expect(derive(documentState: .loading, prior: false)
                == .unavailable(.awaitingDocument))
    }

    @Test func bootingServeStillFollowsThePrior() {
        // `.starting` / `.idle` (lazy start): no document yet, prior decides —
        // a known-good project's lenses stay lit through the switch (no blink).
        #expect(derive(serveState: .starting, prior: true) == .available)
        #expect(derive(serveState: .idle, prior: true) == .available)
        #expect(derive(serveState: .starting, prior: false)
                == .unavailable(.awaitingDocument))
    }
}

/// The prior's table. It mirrors the DEPLOYED serve rule (SPA iff last
/// terminus completed) — when P5 changes the serve rule, these rows flip in
/// the same commit. Drift is cheap (the document message corrects it); the
/// table erring DIM on uncertainty is the load-bearing property.
struct ArtifactPriorTests {

    private func predicts(_ state: PipelineState?, sessions: Int? = nil) -> Bool {
        ArtifactPrior.predictsViewableDocument(pipelineState: state, sessionCount: sessions)
    }

    @Test func completedTerminusPredictsViewable() {
        #expect(predicts(.ready(Date(timeIntervalSince1970: 0))))
        #expect(predicts(.partial(kind: "transcribe-only", stagesComplete: [])))
        #expect(predicts(.completedPartial(summary: PipelineSummary())))
    }

    @Test func nonCompletedTerminusPredictsStatusPage() {
        // Pre-P5 serve rule: any non-completed last terminus intercepts —
        // even when an older good report exists, so no sessionCount override.
        #expect(!predicts(.failed("x", category: .auth), sessions: 12))
        #expect(!predicts(.failedWithDiagnostic(summary: PipelineSummary()), sessions: 12))
        #expect(!predicts(.stopped(stagesComplete: []), sessions: 12))
        #expect(!predicts(.idle, sessions: 12))
        #expect(!predicts(.unreachable(reason: .timedOut), sessions: 12))
    }

    @Test func unknownRunStateFallsBackToArtifactEvidence() {
        // Running / queued / scanning / no state yet: the run state doesn't
        // carry the last terminus — a populated analysis DB is the evidence.
        let unknownTerminusStates: [PipelineState?] = [.running, .queued(position: 1), .scanning, nil]
        for state in unknownTerminusStates {
            #expect(predicts(state, sessions: 3))
            #expect(!predicts(state, sessions: 0))
            #expect(!predicts(state, sessions: nil))
        }
    }
}
