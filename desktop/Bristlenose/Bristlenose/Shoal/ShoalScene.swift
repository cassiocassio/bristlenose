import SpriteKit

/// All available flocking behaviors, selectable from the debug menu.
let allFlockingBehaviors: [FlockingBehavior] = [
    AliveV2Flocking(),
    AliveFlocking(),
    ClassicFlocking(),
]

/// A flock-wide reaction, mapped to the three pipeline content batches. The real
/// run wires each to a batch arrival (`ShoalFeed`); the Debug bench fires them by
/// button. See `ShoalScene.disturb(_:)` for the recipe of each.
enum ShoalDisturbance: Equatable {
    case wordsArrive       // transcript merge — the flock forms; a cohort streams in
    case themesLand        // thematic grouping — a startle wave re-organises the flock
    case sentimentArrives  // quote extraction — the predator swoop + coloured joiners

    /// Map a `ShoalFeed` batch kind to its disturbance. `nil` for unknown kinds.
    init?(feedKind: String) {
        switch feedKind {
        case "word":      self = .wordsArrive
        case "theme":     self = .themesLand
        case "sentiment": self = .sentimentArrives
        default:          return nil
        }
    }
}

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

    /// Live-tunable knobs (force/speed clamps, flocking scales, murmuration
    /// attractor). Defaults reproduce the shipping `ShoalConfig` constants — the
    /// production embed leaves it untouched; the Debug screensaver drives it.
    var tuning = ShoalTuning()

    // Global attractor drift — the invisible point the flock banks toward when
    // `tuning.attractorStrength > 0`. Eased toward a target that re-rolls every
    // `attractorRetargetInterval` seconds. Written to `tuning.attractor` each
    // frame so the stateless behaviours can read the flock-wide point.
    private var attractorTarget: CGPoint = .zero
    private var attractorRetargetAt: TimeInterval = 0

    /// Live transcript words from the run's shoal-feed (via `ShoalFeed`). When
    /// non-empty, spawns draw from these instead of the canned `WordPool`.
    var liveWords: [WordPool.Word] = []

    // Death animation, debug-only: the embedded run view unmounts the scene
    // when a run ends, so there is no completion/settling end-state — only the
    // "Fail" path in the standalone Debug ▸ Shoal Screensaver window reaches this.
    private var isDead = false

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
        isDead = false
        lastUpdateTime = 0
        elapsedTime = 0
        spawnBoids(for: .early)
    }

    /// Advance to a new pipeline phase, spawning additional boids.
    func advanceToPhase(_ phase: ShoalPhase) {
        guard phase > currentPhase else { return }
        currentPhase = phase
        spawnBoids(for: phase)
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

        let maxSpeed = tuning.maxSpeed
        let sceneSize = size

        // Drift the global attractor (murmuration flow). Cheap; skipped visually
        // by the behaviours when strength is 0.
        updateAttractor(dt: dt)

        for boid in boids {
            // Build neighbour list (depth-filtered). NB: this O(n²) filter (a fresh
            // array per boid, per frame) is the shoal's binding perf constraint —
            // main-thread, NOT the GPU (150 boids janked on an idle M2 Max until the
            // 50fps cap). Spatial-grid + no-alloc struct sim is the follow-up if the
            // count ceiling rises. See docs/design-llm-call-telemetry.md §Engineering risk.
            let neighbours = boids.filter { other in
                other !== boid && abs(boid.depth - other.depth) < ShoalConfig.depthNeighbourThreshold
            }

            // Delegate to the pluggable flocking algorithm
            var steer = behavior.steer(
                boid: boid,
                neighbours: neighbours,
                sceneSize: sceneSize,
                elapsedTime: elapsedTime,
                dt: dt,
                tuning: tuning
            )

            // Clamp steering force
            steer = steer.clamped(to: tuning.maxForce)

            // Integrate velocity
            let speedMul = boid.speedMultiplier
            boid.velocity.dx += steer.dx * CGFloat(dt)
            boid.velocity.dy += steer.dy * CGFloat(dt)

            // Clamp speed
            let speed = boid.velocity.magnitude
            let effectiveMax = maxSpeed * speedMul
            let effectiveMin = tuning.minSpeed * speedMul
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

    /// Ease the shared attractor toward a target that re-rolls periodically, and
    /// publish it on `tuning.attractor` for the behaviours to read. The flock's
    /// momentum makes it overshoot each target, which is what turns a static pull
    /// into sweeping murmuration passes.
    private func updateAttractor(dt: TimeInterval) {
        guard size.width > 0, size.height > 0 else { return }

        // Initialise to centre on first run (or after a resize wiped it).
        if attractorTarget == .zero {
            let centre = CGPoint(x: size.width / 2, y: size.height / 2)
            tuning.attractor = centre
            attractorTarget = centre
        }

        // Re-roll to a fresh random point, kept inside a margin.
        if elapsedTime >= attractorRetargetAt {
            let m: CGFloat = 80
            let x = CGFloat.random(in: m...max(m, size.width - m))
            let y = CGFloat.random(in: m...max(m, size.height - m))
            attractorTarget = CGPoint(x: x, y: y)
            attractorRetargetAt = elapsedTime + TimeInterval(max(0.5, tuning.attractorRetargetInterval))
        }

        // Ease toward the target (frame-rate independent).
        let rate = min(1, tuning.attractorDriftRate * CGFloat(dt))
        var p = tuning.attractor
        p.x += (attractorTarget.x - p.x) * rate
        p.y += (attractorTarget.y - p.y) * rate
        tuning.attractor = p
    }

    // MARK: - Disturbance (event-driven — mapped to pipeline batches)

    /// Fire a flock-wide reaction. In the real run each maps to a `ShoalFeed`
    /// batch arrival (words → themes → sentiment); the Debug bench fires them by
    /// hand. The recipes compose three primitives — `spawnCohort` (joiners),
    /// `seedStartle` (fright wave, visible under Alive V2's cascade), and
    /// `swoopAttractor` (the predator turn, visible when a global flow is engaged).
    func disturb(_ kind: ShoalDisturbance) {
        let cohort = max(0, Int(tuning.cohortSize))
        switch kind {
        case .wordsArrive:
            // The gathering: members stream in, no fright.
            spawnCohort(count: cohort)
        case .themesLand:
            // Structure snaps into place: one bird spooks, the wave ripples out.
            if let seed = boids.randomElement() {
                seedStartle(around: seed.position, radius: tuning.startleSeedRadius)
            }
            spawnCohort(count: cohort / 2)
        case .sentimentArrives:
            // The emotional turn: the flock wheels toward a new point + joiners.
            swoopAttractor()
            seedStartle(around: flockCentroid(), radius: tuning.startleSeedRadius * 0.6)
            spawnCohort(count: cohort / 2)
        }
    }

    /// Seed a startle in all boids within `radius` of `point`, fleeing outward.
    /// Alive V2's cascade propagation then carries it through the flock as a
    /// manoeuvre wave (Attanasi 2014); Classic/Alive ignore the flag, so the wave
    /// only reads under Alive V2.
    private func seedStartle(around point: CGPoint, radius: CGFloat) {
        let r2 = radius * radius
        for boid in boids {
            let dx = boid.position.x - point.x
            let dy = boid.position.y - point.y
            if dx * dx + dy * dy <= r2 {
                boid.isStartled = true
                boid.startleTime = elapsedTime
                boid.startleSource = point
            }
        }
    }

    /// A cohort of newcomers streams in from one edge, aimed at the flock's
    /// centroid at full speed (they visibly *arrive*). To keep the population
    /// bounded, the oldest few peel off and fade first — birds leave as others
    /// join, which is itself murmuration-like churn.
    private func spawnCohort(count: Int) {
        guard count > 0, size.width > 0, size.height > 0 else { return }

        // Depart: peel off the oldest, but never below the floor.
        let depart = min(count, max(0, boids.count - ShoalConfig.minCount))
        if depart > 0 {
            for boid in boids.prefix(depart) {
                boid.removeAllActions()
                let away = CGVector(dx: .random(in: -1...1), dy: .random(in: -1...1))
                    .scaled(to: tuning.maxSpeed)
                boid.velocity = away
                boid.run(.sequence([.fadeOut(withDuration: 0.6), .removeFromParent()]))
            }
            boids.removeFirst(depart)
        }

        // Arrive: newcomers enter off-edge with velocity toward the flock centre.
        let centroid = flockCentroid()
        let active = Set(boids.compactMap { $0.text })
        let words = liveWords.isEmpty
            ? WordPool.words(for: currentPhase, count: count, excluding: active)
            : liveSample(count: count, excluding: active)

        for word in words {
            let pos = randomEdgePosition()
            let boid = Boid(word: word, position: pos, depth: .random(in: 0.2...0.9))
            boid.velocity = CGVector(dx: centroid.x - pos.x, dy: centroid.y - pos.y)
                .scaled(to: tuning.maxSpeed)
            boid.alpha = 0
            boid.run(.fadeAlpha(to: boid.baseAlpha, duration: ShoalConfig.spawnFadeDuration))
            addChild(boid)
            boids.append(boid)
        }
    }

    /// Snap the global attractor's target to a fresh point so the flock wheels
    /// toward it (the predator swoop). Only visible when `attractorStrength > 0`.
    private func swoopAttractor() {
        guard size.width > 0, size.height > 0 else { return }
        let m: CGFloat = 80
        attractorTarget = CGPoint(
            x: .random(in: m...max(m, size.width - m)),
            y: .random(in: m...max(m, size.height - m))
        )
        attractorRetargetAt = elapsedTime + TimeInterval(max(0.5, tuning.attractorRetargetInterval))
    }

    /// Mean position of the live flock (scene centre when empty).
    private func flockCentroid() -> CGPoint {
        guard !boids.isEmpty else { return CGPoint(x: size.width / 2, y: size.height / 2) }
        var sx: CGFloat = 0, sy: CGFloat = 0
        for boid in boids { sx += boid.position.x; sy += boid.position.y }
        return CGPoint(x: sx / CGFloat(boids.count), y: sy / CGFloat(boids.count))
    }

    // MARK: - Spawning

    private func spawnBoids(for phase: ShoalPhase) {
        // Count is derived from the current render area (see ShoalConfig) — a
        // bigger pane / external display holds a denser flock.
        let targetCount = ShoalConfig.targetCount(forArea: size.width * size.height, phase: phase)

        let toSpawn = max(0, targetCount - boids.count)
        guard toSpawn > 0 else { return }

        let activeTexts = Set(boids.compactMap { $0.text })
        // Live transcript words from the run feed take over from the canned pool
        // once they arrive; an empty pool falls back to the canned words.
        let words = liveWords.isEmpty
            ? WordPool.words(for: phase, count: toSpawn, excluding: activeTexts)
            : liveSample(count: toSpawn, excluding: activeTexts)

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

    // MARK: - Resize

    /// The render area changed (window resized/moved, entered/left full-screen,
    /// dragged to another display). Re-derive the flock size for the new area and
    /// grow or shrink toward it — keeps density roughly constant as the pane changes.
    override func didChangeSize(_ oldSize: CGSize) {
        super.didChangeSize(oldSize)
        guard !isDead, size.width > 0, size.height > 0 else { return }
        let target = ShoalConfig.targetCount(forArea: size.width * size.height, phase: currentPhase)
        if boids.count < target {
            spawnBoids(for: currentPhase)   // spawnBoids re-derives the same target and fills up to it
        } else if boids.count > target {
            trimBoids(to: target)
        }
    }

    /// Remove surplus boids with a fade — used when the render area shrinks. The
    /// faded boids leave the flock (`boids`) immediately so the sim stops steering
    /// them; their fade-and-remove action finishes independently.
    private func trimBoids(to target: Int) {
        guard boids.count > target else { return }
        let surplus = boids.count - target
        for boid in boids.suffix(surplus) {
            boid.removeAllActions()
            boid.run(.sequence([
                .fadeOut(withDuration: ShoalConfig.spawnFadeDuration),
                .removeFromParent(),
            ]))
        }
        boids.removeLast(surplus)
    }

    /// Draw from the live feed pool, excluding words already on screen; falls
    /// back to repeats if the fresh pool is smaller than the requested count.
    private func liveSample(count: Int, excluding active: Set<String>) -> [WordPool.Word] {
        let fresh = liveWords.filter { !active.contains($0.text) }
        let pool = fresh.isEmpty ? liveWords : fresh
        return Array(pool.shuffled().prefix(count))
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
        guard !isDead else { return }
        isDead = true
        for boid in boids {
            boid.velocity.dx += CGFloat.random(in: -30...30)
            boid.run(.sequence([
                .wait(forDuration: 1.5),
                .fadeOut(withDuration: 0.8),
            ]))
        }
    }

    #if DEBUG
    /// DEBUG stress-test: spawn/despawn to `target` boids, cycling a combined
    /// mixed-style word pool with repeats — for eyeballing density + GPU load
    /// far above the production cap. Driven by the `ShoalDebugView` slider; not
    /// a shipping path (production spawns are phase-driven via `spawnBoids`).
    func debugSetPopulation(_ target: Int) {
        let target = max(0, target)
        while boids.count > target {
            let extra = boids.removeLast()
            extra.removeAllActions()
            extra.removeFromParent()
        }
        guard boids.count < target else { return }
        let pool = WordPool.debugStressPool
        while boids.count < target {
            let word = pool[boids.count % pool.count]
            let boid = Boid(word: word, position: randomEdgePosition(), depth: .random(in: 0.1...0.9))
            boid.alpha = 0
            boid.run(.fadeAlpha(to: boid.baseAlpha, duration: ShoalConfig.spawnFadeDuration))
            addChild(boid)
            boids.append(boid)
        }
    }
    #endif
}
