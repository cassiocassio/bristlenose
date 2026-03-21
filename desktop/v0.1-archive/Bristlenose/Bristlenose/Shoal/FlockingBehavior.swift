import SpriteKit

/// Protocol for swappable flocking algorithms.
/// The scene calls `steer()` once per boid per frame. The implementation
/// returns a steering force vector — the scene handles velocity integration,
/// speed clamping, position update, and depth effects.
protocol FlockingBehavior {
    /// Human-readable name for the debug menu.
    var name: String { get }

    /// Compute the steering force for a single boid given its neighbours and the scene context.
    func steer(
        boid: Boid,
        neighbours: [Boid],
        sceneSize: CGSize,
        elapsedTime: TimeInterval,
        dt: TimeInterval
    ) -> CGVector
}

// MARK: - Classic Reynolds (smooth, uniform)

/// Original three-rule boids: separation, alignment, cohesion + boundary avoidance.
/// Smooth and orderly but not very alive.
struct ClassicFlocking: FlockingBehavior {
    let name = "Classic Reynolds"

    func steer(
        boid: Boid,
        neighbours: [Boid],
        sceneSize: CGSize,
        elapsedTime: TimeInterval,
        dt: TimeInterval
    ) -> CGVector {
        var separation = CGVector.zero
        var alignment  = CGVector.zero
        var cohesion   = CGVector.zero
        var sepCount   = 0
        var alignCount = 0
        var cohCount   = 0

        for other in neighbours {
            let dx = other.position.x - boid.position.x
            let dy = other.position.y - boid.position.y
            let dist = sqrt(dx * dx + dy * dy)
            guard dist > 0.1 else { continue }

            if dist < ShoalConfig.separationRadius {
                separation.dx -= dx / dist
                separation.dy -= dy / dist
                sepCount += 1
            }
            if dist < ShoalConfig.alignmentRadius {
                alignment.dx += other.velocity.dx
                alignment.dy += other.velocity.dy
                alignCount += 1
            }
            if dist < ShoalConfig.cohesionRadius {
                cohesion.dx += other.position.x
                cohesion.dy += other.position.y
                cohCount += 1
            }
        }

        var steer = CGVector.zero

        if sepCount > 0 {
            steer.dx += (separation.dx / CGFloat(sepCount)) * ShoalConfig.separationWeight
            steer.dy += (separation.dy / CGFloat(sepCount)) * ShoalConfig.separationWeight
        }
        if alignCount > 0 {
            let avgDx = alignment.dx / CGFloat(alignCount) - boid.velocity.dx
            let avgDy = alignment.dy / CGFloat(alignCount) - boid.velocity.dy
            steer.dx += avgDx * ShoalConfig.alignmentWeight
            steer.dy += avgDy * ShoalConfig.alignmentWeight
        }
        if cohCount > 0 {
            let targetDx = cohesion.dx / CGFloat(cohCount) - boid.position.x
            let targetDy = cohesion.dy / CGFloat(cohCount) - boid.position.y
            steer.dx += targetDx * 0.01 * ShoalConfig.cohesionWeight
            steer.dy += targetDy * 0.01 * ShoalConfig.cohesionWeight
        }

        // Boundary avoidance
        addBoundaryForce(to: &steer, boid: boid, sceneSize: sceneSize)

        return steer
    }
}

// MARK: - Alive (personality, wander, field of view, startle)

/// Extended boids with individual personality, wandering impulse, limited field
/// of view, and occasional startle. Flocks split and reform naturally.
struct AliveFlocking: FlockingBehavior {
    let name = "Alive"

    func steer(
        boid: Boid,
        neighbours: [Boid],
        sceneSize: CGSize,
        elapsedTime: TimeInterval,
        dt: TimeInterval
    ) -> CGVector {
        var separation = CGVector.zero
        var alignment  = CGVector.zero
        var cohesion   = CGVector.zero
        var sepCount   = 0
        var alignCount = 0
        var cohCount   = 0

        for other in neighbours {
            // Field of view check — only respond to visible neighbours
            guard boid.canSee(point: other.position) else { continue }

            let dx = other.position.x - boid.position.x
            let dy = other.position.y - boid.position.y
            let dist = sqrt(dx * dx + dy * dy)
            guard dist > 0.1 else { continue }

            if dist < ShoalConfig.separationRadius {
                separation.dx -= dx / dist
                separation.dy -= dy / dist
                sepCount += 1
            }
            if dist < ShoalConfig.alignmentRadius {
                alignment.dx += other.velocity.dx
                alignment.dy += other.velocity.dy
                alignCount += 1
            }
            if dist < ShoalConfig.cohesionRadius {
                cohesion.dx += other.position.x
                cohesion.dy += other.position.y
                cohCount += 1
            }
        }

        var steer = CGVector.zero

        // Use per-boid personality weights
        if sepCount > 0 {
            steer.dx += (separation.dx / CGFloat(sepCount)) * boid.separationWeight
            steer.dy += (separation.dy / CGFloat(sepCount)) * boid.separationWeight
        }
        if alignCount > 0 {
            let avgDx = alignment.dx / CGFloat(alignCount) - boid.velocity.dx
            let avgDy = alignment.dy / CGFloat(alignCount) - boid.velocity.dy
            steer.dx += avgDx * boid.alignmentWeight
            steer.dy += avgDy * boid.alignmentWeight
        }
        if cohCount > 0 {
            let targetDx = cohesion.dx / CGFloat(cohCount) - boid.position.x
            let targetDy = cohesion.dy / CGFloat(cohCount) - boid.position.y
            steer.dx += targetDx * 0.01 * boid.cohesionWeight
            steer.dy += targetDy * 0.01 * boid.cohesionWeight
        }

        // Wander: Reynolds' circle-based wander for organic turns
        boid.wanderAngle += .random(in: -ShoalConfig.wanderAngleJitter...ShoalConfig.wanderAngleJitter)
        let heading = boid.heading
        let circleCentre = CGVector(
            dx: cos(heading) * ShoalConfig.wanderCircleDistance,
            dy: sin(heading) * ShoalConfig.wanderCircleDistance
        )
        let wanderOffset = CGVector(
            dx: cos(boid.wanderAngle) * ShoalConfig.wanderCircleRadius,
            dy: sin(boid.wanderAngle) * ShoalConfig.wanderCircleRadius
        )
        steer.dx += (circleCentre.dx + wanderOffset.dx) * ShoalConfig.wanderWeight * boid.wanderStrength
        steer.dy += (circleCentre.dy + wanderOffset.dy) * ShoalConfig.wanderWeight * boid.wanderStrength

        // Speed regulation: steer toward preferred speed
        let currentSpeed = boid.velocity.magnitude
        if currentSpeed > 0.1 {
            let speedDiff = boid.preferredSpeed - currentSpeed
            steer.dx += (boid.velocity.dx / currentSpeed) * speedDiff * 0.1
            steer.dy += (boid.velocity.dy / currentSpeed) * speedDiff * 0.1
        }

        // Startle: occasional random impulse for breakaway moments
        if Double.random(in: 0...1) < ShoalConfig.startleChance {
            let angle = CGFloat.random(in: 0 ..< .pi * 2)
            steer.dx += cos(angle) * ShoalConfig.startleForce
            steer.dy += sin(angle) * ShoalConfig.startleForce
        }

        // Boundary avoidance
        addBoundaryForce(to: &steer, boid: boid, sceneSize: sceneSize)

        return steer
    }
}

// MARK: - Alive V2 (topological, curiosity, cascade startle, boldness, burst-coast)

/// Ethology-informed flocking with five key behaviours from real fish schools
/// and starling murmurations:
///
/// 1. **Topological neighbours** — track 7 nearest visible boids, not fixed radii
///    (Ballerini et al 2008). Creates natural sub-group splitting.
/// 2. **Curiosity cycle** — idle → investigating → returning. Bold boids peel off
///    to explore a random point, then rejoin (Herbert-Read et al 2011).
/// 3. **Cascade startle** — a startle ripples through the flock as a wave, not
///    simultaneously (Attanasi et al 2014, Potts et al 2022).
/// 4. **Boldness spectrum** — shy boids cluster tightly and startle easily; bold
///    boids wander more and lead breakaways.
/// 5. **Burst and coast** — sinusoidal speed modulation per boid, like real fish
///    fin strokes.
struct AliveV2Flocking: FlockingBehavior {
    let name = "Alive V2"

    func steer(
        boid: Boid,
        neighbours: [Boid],
        sceneSize: CGSize,
        elapsedTime: TimeInterval,
        dt: TimeInterval
    ) -> CGVector {

        // ── 1. Topological neighbours: 7 nearest visible ──────────────

        let visible = neighbours
            .filter { boid.canSee(point: $0.position) }
            .sorted { distSq(boid, $0) < distSq(boid, $1) }

        let topoNeighbours = Array(visible.prefix(ShoalConfig.topologicalNeighbourCount))

        // ── 2. Core flocking forces (sep / align / cohesion) ──────────

        var separation = CGVector.zero
        var alignment  = CGVector.zero
        var cohesion   = CGVector.zero
        var sepCount   = 0
        var alignCount = 0
        var cohCount   = 0

        for other in topoNeighbours {
            let dx = other.position.x - boid.position.x
            let dy = other.position.y - boid.position.y
            let dist = sqrt(dx * dx + dy * dy)
            guard dist > 0.1 else { continue }

            // Separation: always active for topological neighbours
            if dist < ShoalConfig.separationRadius * 1.5 {
                separation.dx -= dx / dist
                separation.dy -= dy / dist
                sepCount += 1
            }

            // Alignment and cohesion: all topological neighbours
            alignment.dx += other.velocity.dx
            alignment.dy += other.velocity.dy
            alignCount += 1

            cohesion.dx += other.position.x
            cohesion.dy += other.position.y
            cohCount += 1
        }

        var steerForce = CGVector.zero

        // Curiosity dampening: reduce alignment/cohesion when investigating
        let curiosityDampen: CGFloat
        switch boid.curiosity {
        case .investigating:
            curiosityDampen = ShoalConfig.curiosityFlockingDampen
        default:
            curiosityDampen = 1.0
        }

        if sepCount > 0 {
            steerForce.dx += (separation.dx / CGFloat(sepCount)) * boid.separationWeight
            steerForce.dy += (separation.dy / CGFloat(sepCount)) * boid.separationWeight
        }
        if alignCount > 0 {
            let avgDx = alignment.dx / CGFloat(alignCount) - boid.velocity.dx
            let avgDy = alignment.dy / CGFloat(alignCount) - boid.velocity.dy
            steerForce.dx += avgDx * boid.alignmentWeight * curiosityDampen
            steerForce.dy += avgDy * boid.alignmentWeight * curiosityDampen
        }
        if cohCount > 0 {
            let targetDx = cohesion.dx / CGFloat(cohCount) - boid.position.x
            let targetDy = cohesion.dy / CGFloat(cohCount) - boid.position.y
            steerForce.dx += targetDx * 0.01 * boid.cohesionWeight * curiosityDampen
            steerForce.dy += targetDy * 0.01 * boid.cohesionWeight * curiosityDampen
        }

        // ── 3. Curiosity / investigate-return cycle ───────────────────

        switch boid.curiosity {
        case .idle:
            // Chance to become curious — bold boids are twice as likely
            let curiosityMul = 0.5 + boid.boldness
            if Double.random(in: 0...1) < ShoalConfig.curiosityChance * curiosityMul {
                let angle = CGFloat.random(in: 0 ..< .pi * 2)
                let range = ShoalConfig.curiosityRange * .random(in: 0.6...1.4)
                let target = CGPoint(
                    x: boid.position.x + cos(angle) * range,
                    y: boid.position.y + sin(angle) * range
                )
                let duration = TimeInterval.random(
                    in: ShoalConfig.curiosityDurationMin...ShoalConfig.curiosityDurationMax
                )
                boid.curiosity = .investigating(target: target, until: elapsedTime + duration)
            }

        case .investigating(let target, let until):
            if elapsedTime >= until {
                // Investigation over — start returning
                boid.curiosity = .returning(until: elapsedTime + ShoalConfig.curiosityReturnDuration)
            } else {
                // Steer toward investigation target
                let dx = target.x - boid.position.x
                let dy = target.y - boid.position.y
                let dist = sqrt(dx * dx + dy * dy)
                if dist > 5 {
                    steerForce.dx += (dx / dist) * 30 * (0.5 + boid.boldness)
                    steerForce.dy += (dy / dist) * 30 * (0.5 + boid.boldness)
                } else {
                    // Arrived — return early
                    boid.curiosity = .returning(until: elapsedTime + ShoalConfig.curiosityReturnDuration)
                }
            }

        case .returning(let until):
            if elapsedTime >= until {
                boid.curiosity = .idle
            } else {
                // Strong cohesion pull back to nearest cluster
                if let nearest = topoNeighbours.first {
                    let dx = nearest.position.x - boid.position.x
                    let dy = nearest.position.y - boid.position.y
                    let dist = sqrt(dx * dx + dy * dy)
                    if dist > 1 {
                        steerForce.dx += (dx / dist) * 40
                        steerForce.dy += (dy / dist) * 40
                    }
                }
            }
        }

        // ── 4. Cascade startle ────────────────────────────────────────

        if boid.isStartled {
            // Flee from startle source
            let dx = boid.position.x - boid.startleSource.x
            let dy = boid.position.y - boid.startleSource.y
            let dist = sqrt(dx * dx + dy * dy)
            if dist > 1 {
                steerForce.dx += (dx / dist) * ShoalConfig.cascadeFleeForce
                steerForce.dy += (dy / dist) * ShoalConfig.cascadeFleeForce
            } else {
                // Random escape if right on top of source
                let angle = CGFloat.random(in: 0 ..< .pi * 2)
                steerForce.dx += cos(angle) * ShoalConfig.cascadeFleeForce
                steerForce.dy += sin(angle) * ShoalConfig.cascadeFleeForce
            }

            // Decay startle
            if elapsedTime - boid.startleTime > ShoalConfig.cascadeDuration {
                boid.isStartled = false
            }
        } else {
            // Spontaneous startle — bold boids are less easily startled
            let startleMul = 1.5 - boid.boldness // shy=1.5×, bold=0.5×
            if Double.random(in: 0...1) < ShoalConfig.cascadeStartleChance * startleMul {
                boid.isStartled = true
                boid.startleTime = elapsedTime
                boid.startleSource = boid.position // self-initiated, flee outward
            }

            // Cascade propagation: check for recently startled neighbours
            for other in neighbours {
                guard other.isStartled else { continue }
                guard elapsedTime - other.startleTime < ShoalConfig.cascadeDelay else { continue }

                let dx = other.position.x - boid.position.x
                let dy = other.position.y - boid.position.y
                let dist = sqrt(dx * dx + dy * dy)

                if dist < ShoalConfig.cascadeRadius {
                    // Shy boids propagate startle more readily
                    let sensitivity = 0.5 + (1.0 - boid.boldness) // shy=1.5, bold=0.5
                    let chance = (1.0 - dist / ShoalConfig.cascadeRadius) * sensitivity
                    if Double.random(in: 0...1) < chance {
                        boid.isStartled = true
                        boid.startleTime = elapsedTime
                        boid.startleSource = other.position // flee from the startled neighbour
                        break
                    }
                }
            }
        }

        // ── 5. Wander (same as AliveFlocking, scaled by boldness) ─────

        if !boid.isStartled {
            boid.wanderAngle += .random(in: -ShoalConfig.wanderAngleJitter...ShoalConfig.wanderAngleJitter)
            let heading = boid.heading
            let circleCentre = CGVector(
                dx: cos(heading) * ShoalConfig.wanderCircleDistance,
                dy: sin(heading) * ShoalConfig.wanderCircleDistance
            )
            let wanderOffset = CGVector(
                dx: cos(boid.wanderAngle) * ShoalConfig.wanderCircleRadius,
                dy: sin(boid.wanderAngle) * ShoalConfig.wanderCircleRadius
            )
            // Bold boids wander more strongly
            let wanderMul = boid.wanderStrength * (0.6 + boid.boldness * 0.8)
            steerForce.dx += (circleCentre.dx + wanderOffset.dx) * ShoalConfig.wanderWeight * wanderMul
            steerForce.dy += (circleCentre.dy + wanderOffset.dy) * ShoalConfig.wanderWeight * wanderMul
        }

        // ── 6. Speed regulation with burst-and-coast ──────────────────

        let speedPulse = 1.0 + ShoalConfig.speedPulseAmplitude *
            sin(CGFloat(elapsedTime) * boid.speedPulseFreq + boid.speedPulsePhase)
        let desiredSpeed = boid.preferredSpeed * speedPulse

        let currentSpeed = boid.velocity.magnitude
        if currentSpeed > 0.1 {
            let speedDiff = desiredSpeed - currentSpeed
            steerForce.dx += (boid.velocity.dx / currentSpeed) * speedDiff * 0.15
            steerForce.dy += (boid.velocity.dy / currentSpeed) * speedDiff * 0.15
        }

        // ── 7. Boundary avoidance ─────────────────────────────────────

        addBoundaryForce(to: &steerForce, boid: boid, sceneSize: sceneSize)

        return steerForce
    }
}

/// Squared distance between two boids (avoids sqrt for sorting).
private func distSq(_ a: Boid, _ b: Boid) -> CGFloat {
    let dx = a.position.x - b.position.x
    let dy = a.position.y - b.position.y
    return dx * dx + dy * dy
}

// MARK: - Shared helpers

/// Boundary avoidance — soft turn force when near scene edges.
func addBoundaryForce(to steer: inout CGVector, boid: Boid, sceneSize: CGSize) {
    let margin = ShoalConfig.edgeMargin
    let turn = ShoalConfig.edgeTurnForce
    if boid.position.x < margin { steer.dx += turn }
    if boid.position.x > sceneSize.width - margin { steer.dx -= turn }
    if boid.position.y < margin { steer.dy += turn }
    if boid.position.y > sceneSize.height - margin { steer.dy -= turn }
}

// MARK: - CGVector helpers (shared)

extension CGVector {
    var magnitude: CGFloat {
        sqrt(dx * dx + dy * dy)
    }

    func clamped(to maxMag: CGFloat) -> CGVector {
        let mag = magnitude
        guard mag > maxMag else { return self }
        let scale = maxMag / mag
        return CGVector(dx: dx * scale, dy: dy * scale)
    }

    func scaled(to targetMag: CGFloat) -> CGVector {
        let mag = magnitude
        guard mag > 0.001 else { return self }
        let scale = targetMag / mag
        return CGVector(dx: dx * scale, dy: dy * scale)
    }
}
