---
status: current
last-trued: 2026-07-11
trued-against: HEAD@main on 2026-07-11
---

# Shoal motion — tuning, the murmuration default, and pipeline-driven disturbance

Design notes for the typographic shoal's *motion* (not its density — that's the
`areaPerBoid` work in `ShoalConfig`, and the perf ceiling is in
`docs/design-llm-call-telemetry.md` §Engineering risk). Covers the Jul 2026
retune from "floating" to "murmuration", the live-tuning bench, and the coupling
of flock disturbances to real pipeline stage boundaries.

All code is in `desktop/Bristlenose/Bristlenose/Shoal/`. The shoal is desktop-only
(SpriteKit); there is no Python change here — the pipeline already emitted the
feed batches this work reacts to.

---

## The problem: "floating"

The flock read as *floating* — gently milling, never darting, no collective
sweep. The ethology was already in the code (`AliveV2Flocking`: topological-7
neighbours, cascade startle, boldness, burst-and-coast — see
`docs/bibliography-flocking.md`), but three constants held it underwater:

1. **`maxForce = 30`** (`ShoalScene.update`, applied as `steer.clamped(to:)`).
   `maxForce` is an *acceleration* (pt/s²). Cancelling a boid's 60 pt/s velocity
   to turn it costs 60 ÷ 30 = **~2 s** of sustained max force — so nothing snaps.
   Worse, it clamped the *total* steering vector, so the dramatic impulses the
   behaviours computed (`cascadeFleeForce = 100`, `startleForce = 80`) were
   **crushed to the same 30** as idle flocking. The startle wave existed but
   could never express.
2. **`maxSpeed = 60` / `minSpeed = 15`** — even with snappy turns, a 60 pt/s
   ceiling ambles; a 15 pt/s floor lets boids dawdle.
3. **No global structure** — every boid wandered independently and bounced off
   the edge margin. A real murmuration *travels as one animal* and banks
   together; there was no shared flow to produce that.

## The fix: a tunable model + a global attractor + event-driven disturbance

Three moves, all additive — the old "floating" motion is preserved (see
[Reverting](#reverting-to-floating)).

### 1. `ShoalTuning` — live knobs, defaults from `ShoalConfig`

`ShoalTuning.swift` is an `@Observable` bag of knobs. **Every field defaults from
`ShoalConfig`**, so a freshly-constructed `ShoalTuning()` reproduces the shipping
constants byte-for-byte. Consumption splits two ways:

| Knob | Consumed by | Notes |
|---|---|---|
| `maxForce`, `maxSpeed`, `minSpeed` | `ShoalScene.update` (integration) | the master floatiness levers |
| `separationScale`, `alignmentScale`, `cohesionScale`, `wanderScale` | `FlockingBehavior.steer` | ×multipliers (1.0 = current) layered on each boid's per-boid personality weight — so no `Boid` change |
| `cascadeStartleChance`, `cascadeFleeForce` | `AliveV2Flocking.steer` | absolute; the now-unclamped startle |
| `attractorStrength`, `attractorDriftRate`, `attractorRetargetInterval` | `ShoalScene.updateAttractor` + all behaviours | the global flow (below) |
| `cohortSize`, `startleSeedRadius` | `ShoalScene.disturb` | disturbance magnitudes |
| `attractor` (`CGPoint`) | scene writes / behaviours read | **not a control** — live shared state |

The scene holds one `var tuning`; behaviours receive it as a `steer(…)`
parameter. Because it's a reference type, slider mutations on the bench are seen
by the next frame with no notification plumbing.

### 2. The global attractor (murmuration flow)

`ShoalScene.updateAttractor` eases a shared point (`tuning.attractor`) toward a
target that re-rolls every `attractorRetargetInterval` seconds. Every behaviour
adds a **constant-magnitude** pull toward it (`addAttractorForce`, gated by
`attractorStrength > 0`). Because the pull doesn't fall off with distance, the
flock overshoots each target on its momentum and *sweeps past* — that's what
produces the coherent turns and density bands. At `attractorStrength == 0` (the
Floating default) it's a no-op, so the classic behaviours are untouched unless
engaged.

Theory: near-critical flocks show scale-free correlations (Cavagna & Giardina
2014) — the shared attractor is a crude stand-in for the whole-flock coherence
that makes a murmuration read as one organism.

### 3. Disturbance driven by pipeline stage boundaries

The run's shoal-feed (`bristlenose/shoal_feed.py`) emits **three content batches,
once each**, at real stage boundaries:

| Batch | Emitted at (`pipeline.py`) | Disturbance | Recipe (`ShoalScene.disturb`) |
|---|---|---|---|
| `word` | transcript merge (~:1256) | `.wordsArrive` | **the flock forms** — a cohort streams in from an edge toward the centroid; no fright |
| `theme` | topic segmentation — section/topic labels (~:1401) | `.themesLand` | **structure snaps** — one boid spooks; the Alive V2 cascade ripples it outward as a manoeuvre wave (Attanasi 2014); a half-cohort joins |
| `sentiment` | quote extraction (~:1576) | `.sentimentArrives` | **the emotional turn** — the attractor swoops to a new point (the flock wheels), a light startle from the centroid, coloured joiners |

Three composable primitives back the recipes:

- **`spawnCohort(count:)`** — newcomers enter off-edge aimed at the flock
  centroid at full speed (they visibly *arrive*). To bound the population, the
  oldest few peel off and fade first — birds leave as others join, which is
  itself murmuration-like churn. Floor-protected by `ShoalConfig.minCount`.
- **`seedStartle(around:radius:)`** — seeds `isStartled` in boids within a
  radius; Alive V2's existing cascade propagation carries it through the flock.
  **Only reads under Alive V2** — Classic/Alive ignore the flag.
- **`swoopAttractor()`** — snaps the attractor target to a fresh point. **Only
  visible when `attractorStrength > 0`** (i.e. under the murmuration tuning).

**Wiring** (`ShoalRunView.pollFeed`): `ShoalFeed.read` now returns a `Snapshot`
carrying `kinds: Set<String>` alongside the word pool. The poller diffs `kinds`
across polls; the first appearance of a kind fires the matching disturbance via
the `disturbanceRequest` binding into `ShoalView` → `scene.disturb(_:)`. Each
fires exactly once (each `emit_*` is called once per run). Edge case: if two
kinds surface in the same 1.5 s poll (rare — stages are seconds-to-minutes
apart), the later/bigger moment wins (`disturbance(forNewKinds:)` prefers
sentiment > theme > word); the earlier join is absorbed into it.

---

## Production default: murmuration (Jul 2026)

The **real analysis run** ships the murmuration feel.
`ShoalRunView` constructs its tuning via `ShoalTuning.productionDefault()`, which
applies `applyMurmurationPreset()` — the single source of truth shared with the
bench's "Murmuration" button, so tuning the preset moves production too.

Current preset (eyeball values — retune freely):

```
maxForce 250   maxSpeed 210   minSpeed 80
alignmentScale 1.3   cohesionScale 1.2   separationScale 1.0   wanderScale 0.4
cascadeStartleChance 0.0025   cascadeFleeForce 160
attractorStrength 90   attractorDriftRate 0.5   attractorRetargetInterval 6
```

Accessibility is unaffected: `ContentView` already gates the whole `ShoalRunView`
on Reduce Motion and the show-animation preference, so the faster motion is only
shown when motion is allowed.

---

## The tuning bench

**Window ▸ (Debug) ▸ Shoal Screensaver** (`ShoalDebugView`, `#if DEBUG` only).
A right-hand inspector drives a live `ShoalTuning`; the scene reads it each
frame. Sections:

- **Preset** — `Floating` (`resetToDefaults`) ↔ `Murmuration` (`applyMurmurationPreset`),
  plus **Copy values** → the current knobs as paste-ready Swift
  (`ShoalTuning.exportValues`) on the clipboard, to bake into the preset or hand
  back to a maintainer.
- **Motion** — max force / max / min speed.
- **Flocking** — separation / alignment / cohesion / wander scales.
- **Startle (Alive V2)** — chance + flee force.
- **Murmuration** — attractor pull / drift rate / retarget interval.
- **Disturbance** — `Words arrive` / `Themes land` / `Sentiment arrives` buttons
  (fire the recipes by hand, since the bench has no live pipeline) + cohort size
  + startle radius.
- **Scene** — population (0–600, the density/GPU probe) + Fail/Reset.

The behaviour picker (Classic / Alive / Alive V2) stays top-right of the scene.
To feel the intended result: **Alive V2 + Murmuration**, then fire the buttons.
The bench starts on Floating so it A/Bs against the previous behaviour.

---

## Reverting to Floating

The pre-murmuration motion is fully preserved:

- **Everywhere:** it's the default-init `ShoalTuning()` / `resetToDefaults()`,
  still reachable from the bench's "Floating" preset.
- **Production:** change `ShoalRunView`'s `tuning` initialiser from
  `ShoalTuning.productionDefault()` to `ShoalTuning()`. Nothing else moves — the
  disturbance wiring stays, but with `attractorStrength = 0` the swoop is inert
  and motion returns to the old amble.

The three `FlockingBehavior` implementations are unchanged in spirit — only
threaded with tuning scales — so the whole evolutionary sequence
(Classic → Alive → Alive V2) is intact and selectable.

---

## File map

| File | Role |
|---|---|
| `Shoal/ShoalTuning.swift` | `@Observable` knobs; `resetToDefaults` / `applyMurmurationPreset` / `productionDefault` |
| `Shoal/FlockingBehavior.swift` | `steer(…, tuning:)`; scales; `addAttractorForce` |
| `Shoal/ShoalScene.swift` | force/speed clamps from tuning; `updateAttractor`; `ShoalDisturbance` + `disturb` + `spawnCohort`/`seedStartle`/`swoopAttractor` |
| `Shoal/ShoalFeed.swift` | `read → Snapshot { words, kinds }` |
| `Shoal/ShoalRunView.swift` | production embed; `productionDefault()`; batch-kind → disturbance wiring |
| `Shoal/ShoalView.swift` | injects tuning + `disturbanceRequest` into the scene |
| `Shoal/ShoalDebugView.swift` | the tuning bench (`#if DEBUG`) |

## See also

- `docs/bibliography-flocking.md` — the academic sources behind each behaviour.
- `docs/design-llm-call-telemetry.md` §In-run UX / §Engineering risk — why the
  shoal exists and the O(n²) main-thread perf ceiling.
- `bristlenose/shoal_feed.py` — the Python feed writer (the batches reacted to).
