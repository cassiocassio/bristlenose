import XCTest
@testable import Bristlenose

/// Regression-pins the pure derivation `ProjectRowActivityIndicator.Kind.from`.
/// The `switch` is exhaustive (no `default:`), so the compiler already forces a
/// decision on any new `PipelineState` case; these tests pin the *mapping*
/// (only `.running` shows the activity indicator; everything else defers to the
/// cloud glyph / subtitle text).
final class ProjectRowActivityIndicatorTests: XCTestCase {

    func testRunningMapsToRunning() {
        // No progress yet → spinner (fraction nil); the determinate fraction is
        // covered by RunProgressMathTests.
        XCTAssertEqual(
            ProjectRowActivityIndicator.Kind.from(pipelineState: .running),
            .running(fraction: nil)
        )
    }

    func testNonRunningStatesMapToNone() {
        let nonRunning: [PipelineState?] = [
            nil,
            .scanning,
            .idle,
            .queued(position: 1),
            .ready(Date()),
            .stopped(stagesComplete: []),
            .partial(kind: "transcribe-only", stagesComplete: []),
        ]
        for state in nonRunning {
            XCTAssertEqual(
                ProjectRowActivityIndicator.Kind.from(pipelineState: state),
                .none,
                "Expected .none for \(String(describing: state))"
            )
        }
    }
}
