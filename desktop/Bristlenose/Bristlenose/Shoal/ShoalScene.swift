import SpriteKit

/// All available flocking behaviors, selectable from the debug menu.
let allFlockingBehaviors: [FlockingBehavior] = [
    AliveV2Flocking(),
    AliveFlocking(),
    ClassicFlocking(),
]

/// SpriteKit scene that runs the typographic flocking animation.
///
/// The flocking algorithm is pluggable via `FlockingBehavior` — the scene
/// handles spawning, lifecycle, depth, and end-state animations. The behavior
/// only computes the steering force per boid per frame.
final class ShoalScene: SKScene {

    private(set) var boids: [Boid] = []
    private var currentPhase: ShoalPhase = .early
    private var lastUpdateTime: TimeInterval = 0
    private var elapsedTime: TimeInterval = 0

    /// The active flocking algorithm. Can be swapped at runtime via the debug menu.
    var behavior: FlockingBehavior = allFlockingBehaviors[0]

    // End-state flags (mutually exclusive)
    private var isSettling = false
    private var settlingStartTime: TimeInterval = 0
    private var isDead = false
    private var isTriumphing = false
    private var triumphStartTime: TimeInterval = 0

    // MARK: - Lifecycle

    override func didMove(to view: SKView) {
        backgroundColor = .clear
        view.allowsTransparency = true
        scaleMode = .resizeFill
        spawnBoids(for: .early)
    }

    // MARK: - Phase transitions

    /// Clear all boids and reset to initial state. Used by demo mode.
    func reset() {
        removeAllActions()
        for boid in boids {
            boid.removeAllActions()
            boid.removeFromParent()
        }
        boids.removeAll()
        currentPhase = .early
        isSettling = false
        isDead = false
        isTriumphing = false
        lastUpdateTime = 0
        elapsedTime = 0
        spawnBoids(for: .early)
    }

    /// Advance to a new pipeline phase, spawning additional boids.
    func advanceToPhase(_ phase: ShoalPhase) {
        guard phase > currentPhase else { return }
        currentPhase = phase

        if phase == .complete {
            run(.sequence([
                .wait(forDuration: ShoalConfig.settlingDelay),
                .run { [weak self] in self?.triumph() },
            ]))
        } else {
            spawnBoids(for: phase)
        }
    }

    // MARK: - Update loop

    override func update(_ currentTime: TimeInterval) {
        let dt: TimeInterval
        if lastUpdateTime == 0 {
            dt = 1.0 / 60.0
        } else {
            dt = min(currentTime - lastUpdateTime, 1.0 / 30.0)
        }
        lastUpdateTime = currentTime
        elapsedTime += dt

        // Dead: gravity takes over, no flocking
        if isDead {
            for boid in boids {
                boid.velocity.dy -= 120 * CGFloat(dt)
                boid.velocity.dx *= 0.98
                boid.position.x += boid.velocity.dx * CGFloat(dt)
                boid.position.y += boid.velocity.dy * CGFloat(dt)
                boid.zRotation += CGFloat.random(in: -0.02...0.02)
            }
            return
        }

        // Triumphing: accelerate toward viewer, scale up, burst outward
        if isTriumphing {
            let t = min(CGFloat(currentTime - triumphStartTime) / 1.5, 1.0)
            let easeIn = t * t
            let centre = CGPoint(x: size.width / 2, y: size.height / 2)
            for boid in boids {
                let scale = 1.0 + easeIn * 4.0
                boid.xScale = scale
                boid.yScale = scale
                let dx = boid.position.x - centre.x
                let dy = boid.position.y - centre.y
                let outwardSpeed = 200 + easeIn * 600
                let dist = sqrt(dx * dx + dy * dy)
                if dist > 1 {
                    boid.position.x += (dx / dist) * outwardSpeed * CGFloat(dt)
                    boid.position.y += (dy / dist) * outwardSpeed * CGFloat(dt)
                }
            }
            return
        }

        // Settling: decelerate and centre-pull (re-render fallback)
        var maxSpeed = ShoalConfig.maxSpeed
        var extraCentrePull: CGFloat = 0

        if isSettling {
            let t = min(CGFloat(currentTime - settlingStartTime) / CGFloat(ShoalConfig.settlingDuration), 1.0)
            let easeOut = 1.0 - (1.0 - t) * (1.0 - t)
            maxSpeed = ShoalConfig.maxSpeed * (1.0 - easeOut * 0.92)
            extraCentrePull = easeOut * 20
        }

        let sceneSize = size
        let centre = CGPoint(x: sceneSize.width / 2, y: sceneSize.height / 2)

        for boid in boids {
            // Build neighbour list (depth-filtered)
            let neighbours = boids.filter { other in
                other !== boid && abs(boid.depth - other.depth) < ShoalConfig.depthNeighbourThreshold
            }

            // Delegate to the pluggable flocking algorithm
            var steer = behavior.steer(
                boid: boid,
                neighbours: neighbours,
                sceneSize: sceneSize,
                elapsedTime: elapsedTime,
                dt: dt
            )

            // Centre pull (settling only)
            if extraCentrePull > 0 {
                steer.dx += (centre.x - boid.position.x) * 0.01 * extraCentrePull
                steer.dy += (centre.y - boid.position.y) * 0.01 * extraCentrePull
            }

            // Clamp steering force
            steer = steer.clamped(to: ShoalConfig.maxForce)

            // Integrate velocity
            let speedMul = boid.speedMultiplier
            boid.velocity.dx += steer.dx * CGFloat(dt)
            boid.velocity.dy += steer.dy * CGFloat(dt)

            // Clamp speed
            let speed = boid.velocity.magnitude
            let effectiveMax = maxSpeed * speedMul
            let effectiveMin = ShoalConfig.minSpeed * speedMul
            if speed > effectiveMax {
                boid.velocity = boid.velocity.scaled(to: effectiveMax)
            } else if speed < effectiveMin && speed > 0.1 {
                boid.velocity = boid.velocity.scaled(to: effectiveMin)
            }

            // Update position
            boid.position.x += boid.velocity.dx * CGFloat(dt)
            boid.position.y += boid.velocity.dy * CGFloat(dt)

            // Depth oscillation
            let depthOsc = sin(CGFloat(elapsedTime) * ShoalConfig.depthDriftRate + boid.depthPhaseOffset)
            boid.depth = 0.5 + depthOsc * 0.4

            boid.applyDepthEffects()
        }
    }

    // MARK: - Spawning

    private func spawnBoids(for phase: ShoalPhase) {
        let targetCount: Int
        switch phase {
        case .early:    targetCount = ShoalConfig.earlyCount
        case .middle:   targetCount = ShoalConfig.middleCount
        case .late:     targetCount = ShoalConfig.lateCount
        default:        return
        }

        let toSpawn = max(0, targetCount - boids.count)
        guard toSpawn > 0 else { return }

        let activeTexts = Set(boids.compactMap { $0.text })
        let words = WordPool.words(for: phase, count: toSpawn, excluding: activeTexts)

        for word in words {
            let pos = randomEdgePosition()
            let depth = CGFloat.random(in: 0.1...0.9)
            let boid = Boid(word: word, position: pos, depth: depth)

            boid.alpha = 0
            boid.run(.fadeAlpha(to: boid.baseAlpha, duration: ShoalConfig.spawnFadeDuration))

            addChild(boid)
            boids.append(boid)
        }
    }

    private func randomEdgePosition() -> CGPoint {
        let edge = Int.random(in: 0...3)
        switch edge {
        case 0:  return CGPoint(x: .random(in: 0...size.width), y: size.height + 20)
        case 1:  return CGPoint(x: .random(in: 0...size.width), y: -20)
        case 2:  return CGPoint(x: -20, y: .random(in: 0...size.height))
        default: return CGPoint(x: size.width + 20, y: .random(in: 0...size.height))
        }
    }

    // MARK: - End-state animations

    func die() {
        guard !isDead, !isTriumphing else { return }
        isDead = true
        for boid in boids {
            boid.velocity.dx += CGFloat.random(in: -30...30)
            boid.run(.sequence([
                .wait(forDuration: 1.5),
                .fadeOut(withDuration: 0.8),
            ]))
        }
    }

    func triumph() {
        guard !isDead, !isTriumphing else { return }
        isTriumphing = true
        triumphStartTime = lastUpdateTime
        for boid in boids {
            boid.run(.sequence([
                .wait(forDuration: 1.2),
                .fadeOut(withDuration: 0.3),
            ]))
        }
    }

    private func beginSettling() {
        guard !isSettling else { return }
        isSettling = true
        settlingStartTime = lastUpdateTime
        let fadeDelay = ShoalConfig.settlingDuration - ShoalConfig.settlingFadeDuration
        for boid in boids {
            boid.run(.sequence([
                .wait(forDuration: fadeDelay),
                .fadeOut(withDuration: ShoalConfig.settlingFadeDuration),
            ]))
        }
    }
}
