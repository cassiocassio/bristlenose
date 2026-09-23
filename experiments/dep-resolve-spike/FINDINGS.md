# Dependency-resolution spike — findings

Run it: `python3 experiments/dep-resolve-spike/spike.py` (stdlib, <1s, no side effects).

## Final result — every design is unsafe, and all for the same reason

| design | silent-wrong | refused late | refused early | first-time |
|---|---|---|---|---|
| **B lock** — resolve once, lanes install from a per-release lock | 1 | 3 | 1 | 13 |
| **A+dmg** — lanes reuse the venv, plus the missing build-dmg check | 1 | 4 | 1 | 12 |
| **today+dmg** — change nothing but add the build-dmg check | 1 | 13 | 0 | 4 |
| A reuse — lanes reuse the venv, no dmg check | 3 | 2 | 1 | 12 |
| shipped — preflight resolves + checks (landed 23 Sep) | 4 | 9 | 1 | 4 |
| today — the four-occurrence baseline | 4 | 10 | 0 | 4 |

`silent-wrong` outranks everything: it is the house defect, a check reporting
success while seeing nothing. `late` = refused after the bump, push and CI
dispatch, so a fix cascades. `early` = refused at preflight, where a fix is one
cheap step.

## The finding that changed the plan

**Every design still carries one silent-wrong, and it is the same one: S16.**

The inventory is generated from the **sidecar venv**
(`generate-third-party-binaries.py:9` — "Run `pip-licenses` against the SIDECAR
venv"). What ships is the **frozen bundle**. PyInstaller's `excludes` /
`collect_*` mean those are not the same set, and root `CLAUDE.md` records a live
instance: *"`presidio_analyzer-2.2.364.dist-info` sits in `_internal/` with no
package directory. A dist-info proves metadata shipped, not code."*

So a spec change that drops a package leaves the inventory describing something
the bundle does not carry — and **no resolve strategy can see it**, because they
all measure a resolve. That is why B-lock, the design that looked strongest,
fails here too: a lock records *intent*, never the artefact.

I did not find this. The review did, after the spike had already convinced me B
was the answer.

## What the spike caught before anyone shipped anything

1. **Design A scored 12/12 until I wrote scenarios aimed at it.** Its fallback is
   silent: when the fingerprint says stale it re-resolves live, and if that lands
   before `build-dmg` there is no check to catch the result (S12, S13). The first
   scoring flattered it because the same head wrote the design and the scenarios.
2. **My own scoring was lying about my own change.** `shipped` tied with `today`
   until refusals were graded by *when* they happen. The change landed 23 Sep
   moves a failure from post-bump to preflight; a flat CAUGHT column cannot
   express that, so the model said the change was worthless. It is not: S0 is
   exactly the case it was built for and it is the one column where `shipped`
   beats `today`.
3. **A modelled gate that cannot fail.** The first `_with_dmg_check` converted
   *every* silent-wrong into a catch, including S16 — which a venv-reading check
   physically cannot detect. It recommended a design on the strength of a catch
   that design cannot perform. Same shape as the defect the whole spike is about.

## The live hole, stated plainly

Scenario S2, on the code running in production today: a package publishing in
the ~15 minutes between `build-all` and `build-dmg` gives

    pkg = httpx 2.13.0     dmg = httpx 2.13.1

— the App Store build and the notarised `.dmg` carrying different dependency
closures out of one release, the committed inventory describing only one of
them, and nothing anywhere failing. `build-all.sh:396` runs the inventory check;
`build-dmg.sh` runs nothing. Not hypothetical: two independent resolves ten
minutes apart disagreed twice on 23 Sep 2026.

## Recommended order — changed by the spike and the review

1. **Generate the inventory from the BUNDLE, not from the venv.** Closes S16 for
   every design, and it is the only item here that no resolve strategy can
   substitute for. Read `_internal/*.dist-info` from the built bundle.
2. **Add the inventory check to `build-dmg`.** One step, closes the whole
   channel-divergence family (S2, S12, S13), takes `today` from 4 silent-wrong
   to 1 with no design change at all.
3. **Then, and only if the retries actually bite, the reuse gate (A).** It buys
   first-time-right (4/16 → 12/16). It is worth nothing until (1) and (2) land,
   and on its own it is *worse than doing nothing*, because its failure is
   silent where today's is loud.
4. **Do not build the per-release lock (B).** It wins on exactly S12/S13/S14,
   each of which needs a venv death or a concurrent pyproject edit *plus* a
   publish in the same gap — compound cases that have occurred zero times — and
   the payoff is a retry avoided, not a lie prevented. It adds an artefact, a
   staleness question, and makes a yanked version block a release that today
   self-heals.

## What the model still does not cover

- **Architecture.** `resolve()` is platform-blind. Both lanes run on one Mac, so
  this cannot fire today — but the Copr `aarch64` wheelhouse incident
  (`CLAUDE.md`) is precisely this failure on another surface, and the moment a
  lane moves to CI it becomes live. The assumption "both lanes run on the same
  host" is load-bearing and written down nowhere.
- **A warm wheel cache**, so B is scored pessimistically on "unreachable".
- **Licence text changing without a version change.**
- ffmpeg, the `.mcpb` and the frontend bundle, which have their own gates.
