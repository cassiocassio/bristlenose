/// Parses ANSI-stripped pipeline stdout lines to detect phase transitions.
///
/// Monotonic: the phase only advances forward, never regresses. This matches
/// the pipeline's sequential execution — once quotes are extracted, we don't
/// go back to transcription.
struct StageDetector {
    private(set) var currentPhase: ShoalPhase = .early

    /// Process a new stdout line and return the (possibly advanced) phase.
    @discardableResult
    mutating func processLine(_ line: String) -> ShoalPhase {
        let lower = line.lowercased()

        // Stage 8: topic segmentation complete → middle phase
        if currentPhase < .middle,
           lower.contains("segmented"), lower.contains("topic") {
            currentPhase = .middle
        }

        // Stage 9: quote extraction complete → late phase
        if currentPhase < .late,
           lower.contains("extracted"), lower.contains("quote") {
            currentPhase = .late
        }

        // Stage 12: render complete → done
        if currentPhase < .complete,
           lower.contains("rendered"), lower.contains("report") {
            currentPhase = .complete
        }

        return currentPhase
    }
}
