import CoreGraphics
import Observation

/// Live-tunable knobs for the typographic shoal.
///
/// Every field DEFAULTS from `ShoalConfig`, so a freshly-constructed `ShoalTuning`
/// reproduces the shipping constants byte-for-byte — the production embed
/// (`ShoalRunView`) never mutates it, so its motion is unchanged. Only the
/// standalone Debug ▸ Shoal Screensaver window drives the values, via sliders
/// bound to this object (it's `@Observable`, so the scene reads the latest value
/// each frame with no notification plumbing).
///
/// The split is deliberate: **motion** knobs (`maxForce`/`maxSpeed`/`minSpeed`)
/// are consumed by `ShoalScene`'s integration loop; **flocking scales** and
/// **startle**/**attractor** knobs are consumed by the `FlockingBehavior`. The
/// scales are ×multipliers (1.0 = current) layered on top of each boid's
/// per-boid personality weight, so tuning them needs no change to `Boid`.
@Observable
final class ShoalTuning {

    // MARK: Motion (scene-consumed)

    /// Steering-force ceiling (pt/s²) — the master "floatiness" knob. Low values
    /// make turns take seconds AND crush the startle/attractor impulses to the
    /// same gentle nudge as idle flocking. Raise it to let motion snap and let
    /// the dramatic forces actually express.
    var maxForce: CGFloat = ShoalConfig.maxForce
    var maxSpeed: CGFloat = ShoalConfig.maxSpeed
    var minSpeed: CGFloat = ShoalConfig.minSpeed

    // MARK: Flocking scales (behaviour-consumed, ×multiplier on per-boid weights)

    var separationScale: CGFloat = 1
    var alignmentScale: CGFloat = 1
    var cohesionScale: CGFloat = 1
    var wanderScale: CGFloat = 1

    // MARK: Startle (behaviour-consumed, absolute — Alive V2)

    var cascadeStartleChance: CGFloat = CGFloat(ShoalConfig.cascadeStartleChance)
    var cascadeFleeForce: CGFloat = ShoalConfig.cascadeFleeForce

    // MARK: Murmuration — global attractor (the invisible predator/goal)

    /// Pull toward a slowly-wandering global point shared by the whole flock.
    /// `0` = off (the shipping default) → no global flow, behaviours untouched.
    /// Above zero the flock banks toward the point and overshoots on its
    /// momentum, producing the sweeping passes + density bands of a murmuration.
    var attractorStrength: CGFloat = 0
    /// How fast the attractor eases toward its current target (fraction/sec).
    var attractorDriftRate: CGFloat = 0.15
    /// Seconds between the attractor re-rolling to a fresh random target.
    var attractorRetargetInterval: CGFloat = 6

    /// Current attractor position (scene writes each frame, behaviours read).
    /// Not a control — live state shared through the tuning object so the
    /// stateless per-boid `steer(...)` can see the flock-wide point.
    var attractor: CGPoint = .zero

    // MARK: Disturbance (event-driven — fired by pipeline batches; bench = buttons)

    /// New members that stream in on a join event (and the count that peels off
    /// to keep the population bounded — birds leave as others arrive).
    var cohortSize: CGFloat = 10
    /// Radius of the initial fright seed; the Alive V2 cascade ripples outward
    /// from there into a manoeuvre wave.
    var startleSeedRadius: CGFloat = 120

    // MARK: - Export

    /// The current knob values as paste-ready Swift assignment lines — drop the
    /// body straight into `applyMurmurationPreset()` to bake a tuned patch, or
    /// hand it back to a maintainer. Excludes the live `attractor` point (state,
    /// not a knob). Used by the Debug bench's "Copy values" button.
    func exportValues() -> String {
        func n(_ v: CGFloat) -> String { String(format: "%g", Double(v)) }
        return """
        // Shoal tuning — captured from the bench
        maxForce = \(n(maxForce))
        maxSpeed = \(n(maxSpeed))
        minSpeed = \(n(minSpeed))
        separationScale = \(n(separationScale))
        alignmentScale = \(n(alignmentScale))
        cohesionScale = \(n(cohesionScale))
        wanderScale = \(n(wanderScale))
        cascadeStartleChance = \(n(cascadeStartleChance))
        cascadeFleeForce = \(n(cascadeFleeForce))
        attractorStrength = \(n(attractorStrength))
        attractorDriftRate = \(n(attractorDriftRate))
        attractorRetargetInterval = \(n(attractorRetargetInterval))
        cohortSize = \(n(cohortSize))
        startleSeedRadius = \(n(startleSeedRadius))
        """
    }

    // MARK: - Presets

    /// The tuning the **real analysis run** ships with (since Jul 2026): the
    /// murmuration feel — committed speed, snappy turns, global flow engaged.
    /// Shares its numbers with `applyMurmurationPreset()`, so tuning the bench
    /// preset moves the production default too. The pre-murmuration "Floating"
    /// motion is preserved — it's the default-init state / `resetToDefaults()`,
    /// still reachable from the Debug bench's "Floating" preset.
    static func productionDefault() -> ShoalTuning {
        let tuning = ShoalTuning()
        tuning.applyMurmurationPreset()
        return tuning
    }

    /// Restore the shipping constants — the "Floating (current)" baseline.
    func resetToDefaults() {
        maxForce = ShoalConfig.maxForce
        maxSpeed = ShoalConfig.maxSpeed
        minSpeed = ShoalConfig.minSpeed
        separationScale = 1
        alignmentScale = 1
        cohesionScale = 1
        wanderScale = 1
        cascadeStartleChance = CGFloat(ShoalConfig.cascadeStartleChance)
        cascadeFleeForce = ShoalConfig.cascadeFleeForce
        attractorStrength = 0
        attractorDriftRate = 0.15
        attractorRetargetInterval = 6
        cohortSize = 10
        startleSeedRadius = 120
    }

    /// Starting point for the "alive murmuration" feel — committed speed, snappy
    /// turns, calmer wander, and the global flow engaged. Eyeball values; the
    /// whole point of the harness is to tune outward from here on real hardware.
    func applyMurmurationPreset() {
        maxForce = 250
        maxSpeed = 210
        minSpeed = 80
        separationScale = 1.0
        alignmentScale = 1.3
        cohesionScale = 1.2
        wanderScale = 0.4
        cascadeStartleChance = 0.0025
        cascadeFleeForce = 160
        attractorStrength = 90
        attractorDriftRate = 0.5
        attractorRetargetInterval = 6
    }
}
