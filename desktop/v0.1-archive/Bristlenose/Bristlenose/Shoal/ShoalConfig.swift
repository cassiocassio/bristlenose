import AppKit
import SpriteKit

// MARK: - Phase

/// Pipeline progress mapped to visual density and word style.
enum ShoalPhase: Int, Comparable {
    case early = 0      // Stages 1-5: transcription — sparse, dim fragments
    case middle = 1     // Stages 6-8: topics — bolder labels appear
    case late = 2       // Stages 9-11: quotes, clustering, theming — sentiment colour
    case complete = 3   // Stage 12: render done — trigger settling
    case settling = 4   // Post-completion deceleration and fade

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
    // Boid target counts per phase
    static let earlyCount  = 15
    static let middleCount = 30
    static let lateCount   = 45
    static let maxCount    = 50

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

    // Settling
    static let settlingDelay:       TimeInterval = 1.0   // seconds after .complete before .settling
    static let settlingDuration:    TimeInterval = 3.0
    static let settlingFadeDuration: TimeInterval = 1.0
    static let settlingCohesionWeight: CGFloat = 3.0

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
