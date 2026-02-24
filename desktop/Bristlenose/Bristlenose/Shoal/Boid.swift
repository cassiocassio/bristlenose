import SpriteKit

/// A single word fragment in the typographic shoal.
/// SKLabelNode subclass carrying velocity, depth, and individual personality
/// traits for the boids algorithm.
final class Boid: SKLabelNode {

    /// Current velocity in points per second.
    var velocity: CGVector = .zero

    /// Depth in the 2.5D field: 0 = far (small, dim, slow), 1 = near (full size, bright, fast).
    var depth: CGFloat = 0.5

    /// Per-boid phase offset for depth oscillation so they don't all breathe in sync.
    let depthPhaseOffset: CGFloat

    /// The base alpha before depth modulation (preserves per-phase dimming).
    let baseAlpha: CGFloat

    /// Which pipeline phase spawned this boid (determines visual style).
    let spawnPhase: ShoalPhase

    // MARK: - Personality (per-boid variation)

    /// Individual weight multipliers — some boids are more social, some more independent.
    let separationWeight: CGFloat
    let alignmentWeight: CGFloat
    let cohesionWeight: CGFloat

    /// Preferred cruising speed — creates natural leaders and followers.
    let preferredSpeed: CGFloat

    /// Current wander angle (accumulates over time for smooth organic turns).
    var wanderAngle: CGFloat

    /// How strongly this boid wanders vs follows the flock.
    let wanderStrength: CGFloat

    /// Field of view in radians (boids only respond to neighbours they can "see").
    /// Real fish have ~270° vision. Blind spots create natural splitting.
    let fieldOfView: CGFloat

    // MARK: - Boldness (shy-bold continuum for AliveV2)

    /// Boldness trait: 0 = very shy, 1 = very bold. Affects curiosity, startle sensitivity,
    /// wander strength, and leadership tendency.
    let boldness: CGFloat

    // MARK: - Curiosity state (AliveV2)

    /// Internal curiosity lifecycle: idle → investigating → returning.
    enum CuriosityState {
        case idle
        case investigating(target: CGPoint, until: TimeInterval)
        case returning(until: TimeInterval)
    }

    var curiosity: CuriosityState = .idle

    // MARK: - Cascade startle (AliveV2)

    /// Whether this boid is currently startled (fleeing from a stimulus).
    var isStartled = false

    /// When the startle began (scene elapsed time).
    var startleTime: TimeInterval = 0

    /// The point to flee from (source of the startle).
    var startleSource: CGPoint = .zero

    // MARK: - Speed pulse (AliveV2)

    /// Per-boid frequency for burst-and-coast speed modulation.
    let speedPulseFreq: CGFloat

    /// Per-boid phase offset for speed modulation (not synchronised).
    let speedPulsePhase: CGFloat

    // MARK: - Init

    init(
        word: WordPool.Word,
        position: CGPoint,
        depth: CGFloat
    ) {
        self.depth = depth
        self.depthPhaseOffset = CGFloat.random(in: 0 ..< .pi * 2)
        self.baseAlpha = word.color.alphaComponent
        self.spawnPhase = {
            switch word.fontSize {
            case ..<12: return .early
            case ..<14: return .middle
            default:    return .late
            }
        }()

        // Personality: ±30% variation on flocking weights
        self.separationWeight = ShoalConfig.separationWeight * .random(in: 0.7...1.3)
        self.alignmentWeight  = ShoalConfig.alignmentWeight  * .random(in: 0.7...1.3)
        self.cohesionWeight   = ShoalConfig.cohesionWeight   * .random(in: 0.7...1.3)

        // Speed: ±20% variation
        let midSpeed = (ShoalConfig.minSpeed + ShoalConfig.maxSpeed) / 2
        self.preferredSpeed = midSpeed * .random(in: 0.8...1.2)

        // Wander
        self.wanderAngle = .random(in: 0 ..< .pi * 2)
        self.wanderStrength = .random(in: 0.3...1.0)

        // Field of view: 240°–300° (most can see broadly, a few have narrower vision)
        self.fieldOfView = .random(in: (4 * .pi / 3)...(5 * .pi / 3))

        // Boldness: 20% bold (0.7-1.0), 20% shy (0.0-0.3), 60% normal (0.3-0.7)
        let boldnessRoll = Double.random(in: 0...1)
        if boldnessRoll < 0.2 {
            self.boldness = .random(in: 0.0...0.3)   // shy
        } else if boldnessRoll > 0.8 {
            self.boldness = .random(in: 0.7...1.0)   // bold
        } else {
            self.boldness = .random(in: 0.3...0.7)   // normal
        }

        // Speed pulse: each boid has its own rhythm
        self.speedPulseFreq = .random(in: 1.5...3.5)
        self.speedPulsePhase = .random(in: 0 ..< .pi * 2)

        super.init()

        self.text = word.text
        self.fontName = ".AppleSystemUIFont"
        self.fontSize = word.fontSize
        self.fontColor = word.color.withAlphaComponent(1.0) // alpha managed separately
        self.horizontalAlignmentMode = .center
        self.verticalAlignmentMode = .center
        self.position = position

        // Random initial heading
        let angle = CGFloat.random(in: 0 ..< .pi * 2)
        let speed = CGFloat.random(in: ShoalConfig.minSpeed...ShoalConfig.maxSpeed)
        self.velocity = CGVector(dx: cos(angle) * speed, dy: sin(angle) * speed)

        applyDepthEffects()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError() }

    // MARK: - Heading

    /// Current heading angle in radians.
    var heading: CGFloat {
        atan2(velocity.dy, velocity.dx)
    }

    /// Whether a point is within this boid's field of view.
    func canSee(point: CGPoint) -> Bool {
        let dx = point.x - position.x
        let dy = point.y - position.y
        let angleToPoint = atan2(dy, dx)
        var diff = angleToPoint - heading
        // Normalise to [-π, π]
        while diff > .pi { diff -= 2 * .pi }
        while diff < -.pi { diff += 2 * .pi }
        return abs(diff) < fieldOfView / 2
    }

    // MARK: - Depth → visual mapping

    /// Map current depth to scale, alpha, and draw order.
    func applyDepthEffects() {
        let t = depth // 0 = far, 1 = near

        let s = ShoalConfig.scaleAtFar + t * (ShoalConfig.scaleAtNear - ShoalConfig.scaleAtFar)
        xScale = s
        yScale = s

        let a = ShoalConfig.alphaAtFar + t * (ShoalConfig.alphaAtNear - ShoalConfig.alphaAtFar)
        alpha = baseAlpha * a

        zPosition = t * 100 // near boids draw on top
    }

    /// Speed multiplier based on depth (far = slower parallax).
    var speedMultiplier: CGFloat {
        ShoalConfig.speedAtFar + depth * (ShoalConfig.speedAtNear - ShoalConfig.speedAtFar)
    }
}
