# Typographic Shoal — Academic Bibliography

Research papers, algorithms, and biological studies informing the flocking animation in Bristlenose's pipeline processing view. For eventual inclusion in the app's About section.

---

## Foundational algorithms

### Reynolds 1987 — Flocks, Herds, and Schools: A Distributed Behavioral Model

**Craig W. Reynolds.** SIGGRAPH '87: Proceedings of the 14th annual conference on Computer graphics and interactive techniques, pp. 25–34, 1987.

The original "boids" paper. Introduces three local rules — separation, alignment, cohesion — that produce emergent flocking from purely local interactions. Each boid sees only its neighbours; no global coordinator. The resulting motion is strikingly lifelike despite the simplicity.

Our `ClassicFlocking` implementation is a direct translation of these three rules.

- **DOI:** [10.1145/37402.37406](https://doi.org/10.1145/37402.37406)
- **Web:** [red3d.com/cwr/boids](https://www.red3d.com/cwr/boids/)

### Reynolds 1999 — Steering Behaviors For Autonomous Characters

**Craig W. Reynolds.** Game Developers Conference 1999.

Extends the boids model with a vocabulary of steering behaviours: seek, flee, pursue, evade, wander, path following, obstacle avoidance, and more. The **wander** behaviour (project a circle ahead of the agent, pick a random point on its edge) is used in our `AliveFlocking` and `AliveV2Flocking` to create organic turns without sharp direction changes.

- **Web:** [red3d.com/cwr/steer](https://www.red3d.com/cwr/steer/)
- **PDF:** [red3d.com/cwr/steer/gdc99](https://www.red3d.com/cwr/steer/gdc99/)

---

## Biological foundations: starling murmurations

### Ballerini et al 2008 — Interaction ruling animal collective behavior depends on topological rather than metric distance

**M. Ballerini, N. Cabibbo, R. Candelier, A. Cavagna, E. Cisbani, I. Giardina, V. Lecomte, A. Orlandi, G. Parisi, A. Procaccini, M. Viale, V. Zdravkovic.** Proceedings of the National Academy of Sciences, 105(4), 1232–1237, 2008.

The key insight behind `AliveV2Flocking`: starlings interact with a fixed number of nearest neighbours (~6-7) regardless of distance, not with all birds within a fixed radius. This **topological** (count-based) rather than **metric** (distance-based) interaction rule means the flock holds together even when density varies — sub-groups naturally form and merge as each bird's nearest-7 shift.

Our implementation replaces fixed-radius neighbour checks with a sorted-by-distance, take-7 approach.

- **DOI:** [10.1073/pnas.0711437105](https://doi.org/10.1073/pnas.0711437105)

### Attanasi et al 2014 — Information transfer and behavioural inertia in starling flocks

**A. Attanasi, A. Cavagna, L. Del Castello, I. Giardina, T.S. Grigera, A. Jelić, S. Melillo, L. Parisi, O. Pohl, E. Shen, M. Viale.** Nature Physics, 10, 691–696, 2014.

Demonstrates that directional information propagates through starling flocks as a **linear wave** — a perturbation at one edge travels across the flock at constant speed, not instantaneously. The propagation speed is ~20-40 m/s, roughly 3× faster than if each bird only responded to its immediate neighbours (suggesting birds anticipate, attending to neighbours-of-neighbours).

This directly inspired our **cascade startle** mechanism: when one boid startles, the effect ripples outward through nearby boids with a time delay proportional to distance.

- **DOI:** [10.1038/nphys3035](https://doi.org/10.1038/nphys3035)

### Cavagna & Giardina 2014 — Bird Flocks as Condensed Matter

**A. Cavagna, I. Giardina.** Annual Review of Condensed Matter Physics, 5, 183–207, 2014.

Review treating bird flocks as a condensed matter system. Discusses scale-free correlations (behavioural fluctuations correlated across the entire flock regardless of size), critical dynamics, and the connection between biological collective behaviour and statistical physics. Provides the theoretical framework for understanding why local rules produce global coherence.

- **DOI:** [10.1146/annurev-conmatphys-031113-133834](https://doi.org/10.1146/annurev-conmatphys-031113-133834)

### Attanasi et al 2019 — Emergence of collective changes in travel direction of starling flocks from individual birds' fluctuations

**A. Attanasi, A. Cavagna, L. Del Castello, I. Giardina, A. Jelic, S. Melillo, L. Parisi, O. Pohl, E. Shen, M. Viale.** Journal of the Royal Society Interface, 12(108), 2015; also discussed in Behavioral Ecology and Sociobiology, 73, 2019.

Studies how collective turning events emerge from individual fluctuations. A single bird's spontaneous direction change can trigger a cascade that reorients the entire flock — but only if the flock is near a "critical point" where correlations are maximal. Also analyses how these waves are damped (not all fluctuations propagate).

- **DOI (2019):** [10.1007/s00265-019-2734-4](https://doi.org/10.1007/s00265-019-2734-4)
- **DOI (2015 Interface):** [10.1098/rsif.2015.0652](https://doi.org/10.1098/rsif.2015.0652)

---

## Biological foundations: fish schooling

### Herbert-Read et al 2011 — Inferring the rules of interaction of shoaling fish

**J.E. Herbert-Read, A. Perna, R.P. Mann, T.M. Schaerf, D.J.T. Sumpter, A.J.W. Ward.** Proceedings of the National Academy of Sciences, 108(46), 18726–18731, 2011.

Reconstructs interaction rules from tracking data of mosquitofish. Finds that fish primarily respond to one or two nearest neighbours (not the whole school), with attraction at long range and repulsion at short range. Speed regulation is significant — fish adjust speed based on neighbour positions, not just direction. Supports the topological neighbour approach and informed our speed regulation mechanics.

- **DOI:** [10.1073/pnas.1109355108](https://doi.org/10.1073/pnas.1109355108)

### Potts et al 2022 — Scale-free behavioural cascades and effective leadership in schooling fish

**W.M. Potts et al.** Scientific Reports, 12, 2022.

Demonstrates that startle responses in fish schools propagate as **scale-free cascades** — the size distribution of cascade events follows a power law. A single fish's startle can trigger anything from a local flinch to a whole-school evasion, depending on the school's state. Also examines how "bold" individuals (consistent leaders) are more likely to initiate cascades.

This informed both our cascade startle propagation and the boldness personality trait.

- **DOI:** [10.1038/s41598-022-14337-0](https://doi.org/10.1038/s41598-022-14337-0)

---

## Extensions and virtual ecosystems

### Delgado-Mata et al 2007 — On the use of virtual animals with artificial fear in virtual environments

**C. Delgado-Mata, J. Ibanez, S. Bee, R. Ruiz-Rodarte, R. Aylett.** New Generation Computing, 25(2), 145–169, 2007.

Extends Reynolds' boids with a fear/pheromone system: virtual animals emit alarm signals when threatened, neighbours detect and propagate the signal, creating realistic panic cascades. The "emotional contagion" model (fear spreads faster than the predator) is analogous to our cascade startle, where the startle wave moves faster than any individual boid.

- **DOI:** [10.1007/s00354-007-0009-5](https://doi.org/10.1007/s00354-007-0009-5)

---

## General references

### Wikipedia — Shoaling and schooling

Overview of the distinction between shoaling (social aggregation) and schooling (polarised, synchronised swimming). Covers anti-predator advantages, foraging benefits, and the "many eyes" hypothesis. Good entry point for the biology behind the different modes our animation transitions between.

- **URL:** [en.wikipedia.org/wiki/Shoaling_and_schooling](https://en.wikipedia.org/wiki/Shoaling_and_schooling)

### The Conversation — Why do flocks of birds swoop and swirl together in the sky?

**Andrea Flack.** Accessible summary of murmuration research, including the 7-neighbour topological rule and information transfer waves.

- **URL:** [theconversation.com/why-do-flocks-of-birds-swoop-and-swirl-together-in-the-sky-176194](https://theconversation.com/why-do-flocks-of-birds-swoop-and-swirl-together-in-the-sky-a-biologist-explains-the-science-of-murmurations-176194)

### FishLore — Neon Tetra Schooling Behavior

Community aquarist discussion of neon tetra schooling vs. shoaling. Describes the "spread out and forage, then temporarily school when alarmed" cycle that directly inspired our curiosity/investigate-return mechanic.

- **URL:** [fishlore.com/aquariumfishforum/threads/neon-tetra-schooling-behavior.106038](https://www.fishlore.com/aquariumfishforum/threads/neon-tetra-schooling-behavior.106038/)

---

## Implementation notes

Our three `FlockingBehavior` implementations represent an evolutionary sequence:

| Algorithm | Based on | Key features |
|-----------|----------|-------------|
| `ClassicFlocking` | Reynolds 1987 | Three rules, metric distance, uniform weights |
| `AliveFlocking` | Reynolds 1987 + 1999 | + personality, wander, field of view, random startle |
| `AliveV2Flocking` | Ballerini 2008, Attanasi 2014, Herbert-Read 2011, Potts 2022 | + topological neighbours, curiosity cycle, cascade startle, boldness spectrum, burst-and-coast |

The debug behaviour picker allows runtime comparison between all three.

---

*Last updated: Feb 2026*
