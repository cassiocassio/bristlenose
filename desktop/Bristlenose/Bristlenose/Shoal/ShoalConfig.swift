import AppKit
import SpriteKit

// MARK: - Phase

/// Pipeline progress mapped to visual density and word style.
enum ShoalPhase: Int, Comparable {
    case early = 0      // transcription — sparse, dim fragments
    case middle = 1     // topics / sections — bolder labels appear
    case late = 2       // quotes / themes — sentiment colour

    // No completion/settling end-state: the embedded run view unmounts the
    // scene the instant the run ends, so the crossfade to the report is the
    // ending — there is no frame in which a completion animation could render.

    static func < (lhs: ShoalPhase, rhs: ShoalPhase) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}

// MARK: - Sentiment

enum ShoalSentiment {
    case positive
    case negative
    case neutral

    var color: NSColor {
        switch self {
        case .positive: .systemGreen
        case .negative: .systemRed
        case .neutral:  .labelColor
        }
    }
}

// MARK: - Constants

enum ShoalConfig {
    // Frame rate — decorative drift, capped below the display refresh so motion
    // stays fluid rather than straining for 120 Hz ProMotion (which reads as
    // judder when frames are missed). 30 fps looked janky, 50 fps smooth on a
    // 16" M2 Max (2026-07 test). SpriteView honours this via preferredFramesPerSecond.
    static let preferredFPS = 50

    // Boid count is DERIVED FROM THE SCENE'S RENDER AREA (points²), not a fixed
    // per-phase constant — a bigger canvas (external display, full window) holds
    // a denser flock before it reads as clutter. ~one boid per `areaPerBoid`
    // points², clamped to [minCount, maxCount], then scaled by the phase ramp so
    // the flock still thickens early → late as analysis proceeds.
    //
    // Tuning: `areaPerBoid` is an eye call on real hardware — lower = denser.
    // Calibrated so a full-window 16" detail pane lands ~100; a larger external
    // display scales up toward the ceiling. Point-area responds to the user's
    // display-scaling ("More Space") choice; it does NOT know physical DPI, so a
    // physically bigger screen at the same point-density gets the same count —
    // add a DPI term here if default-scaled large displays read too sparse.
    //
    // Perf note: the old fixed 50-boid cap was what perf-review's PASS rested on.
    // Raising the ceiling trades that static guarantee for the `preferredFPS` cap
    // plus real-hardware smoothness testing (the flocking sim is O(n²) on the
    // main thread — see the spatial-grid follow-up if high counts ever jank).
    static let areaPerBoid: CGFloat = 15_000
    static let minCount = 24      // floor: a tiny window / weak hardware still flocks
    static let maxCount = 200     // ceiling: perf guard (was 50 when the count was fixed)

    // Phase ramp — fractions of the area-derived base (early → middle → late).
    static let earlyFraction:  CGFloat = 0.4
    static let middleFraction: CGFloat = 0.7
    static let lateFraction:   CGFloat = 1.0

    /// Area-derived boid target for a phase. Pure — unit-tested in
    /// `ShoalConfigTests`. `area` is the scene's `width * height` in points².
    static func targetCount(forArea area: CGFloat, phase: ShoalPhase) -> Int {
        let base = min(max(area / areaPerBoid, CGFloat(minCount)), CGFloat(maxCount))
        let fraction: CGFloat
        switch phase {
        case .early:  fraction = earlyFraction
        case .middle: fraction = middleFraction
        case .late:   fraction = lateFraction
        }
        return max(1, Int((base * fraction).rounded()))
    }

    // Flocking radii (points)
    static let separationRadius: CGFloat = 40
    static let alignmentRadius:  CGFloat = 80
    static let cohesionRadius:   CGFloat = 120

    // Flocking weights
    static let separationWeight: CGFloat = 1.5
    static let alignmentWeight:  CGFloat = 1.0
    static let cohesionWeight:   CGFloat = 0.8

    // Speed (points per second)
    static let maxSpeed: CGFloat = 60
    static let minSpeed: CGFloat = 15
    static let maxForce: CGFloat = 30

    // Boundary avoidance
    static let edgeMargin:    CGFloat = 50
    static let edgeTurnForce: CGFloat = 50

    // Depth (0 = far, 1 = near)
    static let depthDriftRate: CGFloat = 0.3   // oscillation frequency multiplier
    static let depthMin:       CGFloat = 0.0
    static let depthMax:       CGFloat = 1.0
    static let depthNeighbourThreshold: CGFloat = 0.3

    // Depth → visual mapping
    static let scaleAtFar:  CGFloat = 0.6
    static let scaleAtNear: CGFloat = 1.0
    static let alphaAtFar:  CGFloat = 0.4
    static let alphaAtNear: CGFloat = 1.0
    static let speedAtFar:  CGFloat = 0.7
    static let speedAtNear: CGFloat = 1.0

    // Wander (Reynolds steering behavior — organic turns)
    static let wanderCircleDistance: CGFloat = 40  // how far ahead the wander circle is projected
    static let wanderCircleRadius:  CGFloat = 20   // radius of the wander circle
    static let wanderAngleJitter:   CGFloat = 0.4  // max random angle change per frame (radians)
    static let wanderWeight:        CGFloat = 0.6  // base wander force weight

    // Startle (random impulse for occasional breakaway)
    static let startleChance:  Double  = 0.002  // probability per boid per frame
    static let startleForce:   CGFloat = 80     // impulse magnitude

    // Spawn
    static let spawnFadeDuration: TimeInterval = 0.5

    // Topological neighbours (AliveV2)
    static let topologicalNeighbourCount = 7

    // Curiosity / investigate-return cycle (AliveV2)
    static let curiosityChance: Double = 0.003       // probability per boid per frame of becoming curious
    static let curiosityDurationMin: TimeInterval = 1.0
    static let curiosityDurationMax: TimeInterval = 3.0
    static let curiosityRange: CGFloat = 90          // how far from current position to investigate
    static let curiosityFlockingDampen: CGFloat = 0.2 // alignment/cohesion multiplier during investigation
    static let curiosityReturnDuration: TimeInterval = 0.8

    // Cascade startle (AliveV2)
    static let cascadeStartleChance: Double = 0.0015 // probability per boid per frame of spontaneous startle
    static let cascadeRadius: CGFloat = 60           // how far a startle propagates
    static let cascadeDelay: TimeInterval = 0.15     // propagation window (recently startled can trigger others)
    static let cascadeFleeForce: CGFloat = 100       // impulse magnitude when startled
    static let cascadeDuration: TimeInterval = 0.5   // how long the startle effect lasts

    // Speed pulse — burst and coast (AliveV2)
    static let speedPulseAmplitude: CGFloat = 0.15   // ±15% speed modulation
}
