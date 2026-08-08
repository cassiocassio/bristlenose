---
status: proposed
last-trued: 2026-08-08
trued-against: 1e2e4bed@main — channel facts from release-channels.md
---

# `/bn-release` — orchestrating the five channels

_Status: **design only**, nothing built. Plans a skill that runs a release across
some or all of PyPI · GitHub Release · Homebrew · TestFlight · `.dmg`, having
first proven the tree, the changelog and the docs are actually ready._

## The problem it solves

Today a full release is ~12 commands across three surfaces, four expiry clocks,
two signing identities, and a verification step you have to *remember* because
nothing enforces it. The pieces are all built and individually good
([release-channels.md](release-channels.md)). What's missing is the thing that
holds them together and refuses to start when the tree isn't ready.

The recurring failure isn't a broken script. It's **shipping something
half-described** — a version on PyPI whose CHANGELOG entry is missing, a new CLI
flag documented in the README but not the man page or the website, a TestFlight
build from a commit that also carries an unrelated untracked file. Each is
individually small and each is invisible to the scripts, because no script reads
prose.

## Shell or skill? — the question worth settling first

Three shapes are possible, and the choice is not a matter of taste:

- **(a) Pure shell.** One `release.sh`. Deterministic, testable, runs at 11pm
  without a Claude session, costs nothing, works in CI.
- **(b) Pure skill.** A `SKILL.md` telling Claude what to run. Adaptive, reads
  prose, explains failures — and non-reproducible, unavailable when Claude is,
  and capable of *deciding* to skip a step.
- **(c) Split.**

**The deciding principle is the one this repo already learned twice:** a gate
must live *inside* the irreversible act, not beside it. `check-dmg-shippable.sh`
is called from within `upload-dmg.sh` because a sibling step is one an operator
can forget on the one night it matters. `check-pkg-shippable.sh` is a precondition
inside `upload-testflight.sh` with no flag to skip it.

Apply that one level up and the answer falls out: **every irreversible act, and
its preconditions, must be shell.** Not because shell is nicer, but because a
precondition inside a script is *structurally* unskippable, whereas a
precondition in a skill is an instruction a model can misread, and it is the
model that would then be pushing a tag or uploading a build.

That gives the acceptance test for this whole design:

> **You must be able to do a complete release with no Claude session at all**,
> by running the scripts in order. If that stops being true, too much logic has
> leaked into the skill.

The skill is then a **better front door, never a required one** — and it must add
no *capability* the shell lacks, only convenience and judgement.

### What that leaves the skill

Narrower than it first appears. Genuinely LLM-only work is two things:

1. **Reading prose against a diff** — is the CHANGELOG entry an honest
   description of `git log <last-tag>..HEAD`? Does new CLI surface reach all
   three doc surfaces? No script can do this; it is the actual recurring failure.
2. **Triage under partial failure** — PyPI published, Homebrew's poll timed out,
   TestFlight came back INVALID: what to retry, what to accept, what needs a
   human. Shell can *report* this well; deciding is judgement.

Everything else people reach to a skill for — sequencing, progress, pretty
output, per-channel probing — this repo already does better in shell
(`report.sh`, the `check-*` family, `upload-dmg.sh`'s decision helpers).

**So: a thin skill over a fat shell.** If that means you mostly end up typing
`./scripts/release.sh` and rarely invoking `/bn-release`, that is the design
succeeding, not failing.

### The concrete split

| Layer | Artefact | Owns |
|---|---|---|
| Mechanical checks | `scripts/check-release-ready.sh` _(new)_ | tree, versions, changelog *format*, tag, PyPI immutability, certs, build number |
| Irreversible acts | `scripts/release-cli.sh` _(new)_ + existing `build-*`/`upload-*` | each gated internally, each independently runnable |
| Judgement | `/bn-release` skill | changelog *content*, doc coverage, bump-type sanity, failure triage |
| Presentation | `report.sh` | unchanged — the skill emits `@bn` events like everything else |

One consequence worth stating: **the skill's judgement checks are advisory and
cannot block.** Only mechanical checks stop a release. A model that is having an
off day should be able to annoy you, never to prevent you shipping — and equally,
never to wave through a mechanical failure.

## Five design decisions

### D1 — Probe the world; never keep a state file

A release spans 1–2 hours and things fail midway. The obvious answer is a
`.release-state.json` recording progress. **Don't.** A state file can disagree
with reality, and when it does it is confidently wrong in exactly the situation
where you least want that — which is the same lesson the backup audit produced
last week (a healthcheck that asserted liveness while the data was absent).

Every channel can be **asked**:

| Channel | The question | How |
|---|---|---|
| PyPI | is `X.Y.Z` published? | `curl .../pypi/bristlenose/X.Y.Z/json` → 200 |
| GitHub Release | does the release exist? | `gh release view vX.Y.Z` |
| Homebrew | is the formula bumped? | tap's formula `version` field |
| TestFlight | is build N on ASC? | `altool --build-status` |
| Snap | is the revision in the channel? | `snap info bristlenose` / store API |
| `.dmg` | is the versioned file live? | `HEAD` the versioned URL |

So **re-running `/bn-release` is the resume mechanism.** It re-probes, finds three
of five already done, and offers the remaining two. No state, no staleness, and
the same code path every time — which means the resume path is exercised on every
single run rather than only in emergencies.

### D2 — Mac artefacts first; the tag push last

Order the irreversible acts by how permanent they are, and do the permanent one
**last**:

| Act | Reversible? |
|---|---|
| `.dmg` publish | fully — repoint one redirect |
| GitHub Release | delete and recreate |
| Homebrew | self-corrects next release |
| TestFlight upload | build number spent forever, but the build is expirable |
| **PyPI publish** | **never. The version is immutable.** |

Building and validating the Mac artefacts first means a problem they expose — a
signing regression, an expired profile, a failed notarisation — is found while
the version can still be abandoned. Push the tag first and you have burned a PyPI
version to learn the same thing.

This also fits the evening rule for free: build during the day, push after 9pm.

### D3 — One authorisation, not per-step

Per the house rule, automate the mechanical end to end including the
outward-facing act, and put the human at the single point where judgement
differs. That point is **after the preflight, before the first irreversible act**
— once, with the consequences quantified.

Not: "upload to PyPI? [y/n]" then "upload to TestFlight? [y/n]". A prompt per step
trains you to type `y`, which is the opposite of a gate.

### D4 — There is no `--dry-run`, because the preflight always runs

The preflight is read-only and unconditional. Running `/bn-release` and declining
at the authorisation point **is** the dry run, and it is a better one than a flag
because it is the same code path the real release takes.

Same reasoning as `upload-testflight.sh`, where Apple's own `--validate-app` is
the dry run and a local one would just print the script back at you.

### D5 — Channel selection is explicit, defaults are computed

`/bn-release` with no arguments proposes the channels that are **ready and not
already done**, and says why each is in or out. `/bn-release --only testflight`
or `--skip snap` narrows it.

Crucially: **a channel that isn't ready is reported, not silently dropped.**
"Snap skipped — its triggers are parked, publishing is a manual workflow_dispatch"
is information. Silence is how you discover six months later that edge is stale.

## The flow

```
1  INTENT      version + channels
2  PREFLIGHT   read-only; mechanical checks (script) + judgement checks (skill)
3  PLAN        one legible page: what happens, in what order, what's irreversible
4  AUTHORISE   one decision
5  EXECUTE     resumable, live progress
6  VERIFY      probe every channel; report what's actually true
```

### 1 · Intent

Reads `__init__.py` for the current version. **Proposes** minor vs patch by
reading `git log` since the last tag against the house rule (minor = any
user-facing feature; patch = fixes only) — and says which commits drove the
suggestion. The human decides; the tool must not pick silently, because this is
exactly the call the 0.15.0→0.15.19 run got wrong nineteen times.

### 2 · Preflight

**Mechanical — `check-release-ready.sh`:**

- clean tree; on `main`; **untracked files listed explicitly** (today's release
  went out alongside an untracked doc that wasn't mine — harmless, but nobody
  decided that)
- venv minor matches `.tool-versions`
- `pytest` green, `ruff check .` clean
- version agrees across `__init__.py`, the man page `.TH`, and pbxproj
  `MARKETING_VERSION`
- CHANGELOG has an entry for the new version, in the house format
- README's changelog section agrees with CHANGELOG.md
- tag doesn't already exist
- **not already on PyPI** — immutability makes this the single most important
  mechanical check
- per-channel readiness: certs present and unexpired, profile ≥30 days,
  `.ship-local.conf` complete, build number not spent

**Judgement — the skill:**

- read `git log <last-tag>..HEAD` and ask whether the CHANGELOG entry *describes
  it*. Flag features that aren't mentioned; flag "bug fixes" over a feature-
  bearing range
- detect new user-facing surface (CLI flags, commands, settings) and check all
  three doc surfaces cover it — README, man page, website `docs-src/cli.md`
- read the man page with roff escapes normalised (`\-\-` → `--`) before diffing
  against `--help`, or every flag reads as missing
- sanity-check the bump type against what actually changed

### 3 · Plan

One page, in the house report style. Explicitly:

- ordered steps with wall-clock estimates (`.dmg` ≈ 40 min of notary waiting;
  TestFlight ≈ 35 min build + ~10 min upload; PyPI ≈ 25 min of CI)
- **a visible line where reversible becomes irreversible**
- what is being skipped and why
- what the preflight flagged that the human is choosing to accept

### 4 · Authorise · 5 · Execute · 6 · Verify

Execution is the existing scripts, in D2's order, with the report streaming. Every
channel's post-condition is **probed, not assumed** — the `--build-status`
confirmation in `upload-testflight.sh` is the pattern, and it exists because
altool can exit 0 on a build that never arrives.

Final output is a table of what is now true, per channel, with the expiry clocks
(`.dmg` 30 days from **build**; TestFlight 90 from **upload**).

## Snap is orchestrable — correcting a wrong first draft

The first draft parked Snap as "manual, don't touch". That was wrong, and the
distinction matters: **what's parked is the auto-trigger, not the publish.**

`snap.yml` has `workflow_dispatch` as its *only* trigger, and two publish jobs:

| Job | Fires when |
|---|---|
| `publish-edge` | `github.event_name == 'workflow_dispatch'` |
| `publish-stable` | `startsWith(github.ref, 'refs/tags/v')` |

Since the sole trigger is dispatch, **`publish-stable` is reached by dispatching
the workflow against the tag ref** — `gh workflow run snap.yml --ref vX.Y.Z`.
Dispatch against `main` and you get edge instead.

So Snap is a first-class orchestrated channel, and the release's Snap step is one
command with a channel implied by the ref. That's a nicer design than it looks:
the ref *is* the channel selector, so there's no separate flag to get wrong.

The reason `push`/`pull_request` were parked (a snap on every commit is noise)
argues *for* driving it from a release orchestrator, which is precisely the
per-release moment the parking left unserved. The consequence of not doing so is
already visible: nothing has reached edge since the triggers were parked.

**Open: does a normal release publish edge, stable, or both?** Snap's own
convention is that edge tracks development and stable is curated. Given
Bristlenose is pre-1.0 and the CLI is alpha, _leaning: edge on every release,
stable only when explicitly asked_ — but that's a product call, not a mechanical
one.

## What stays manual, deliberately

- **Writing the CHANGELOG.** The skill reads and critiques it; it does not author
  it. A generated changelog is a changelog nobody reads.
- **The website deploy.** Separate private repo, rsync over SSH agent, run by the
  maintainer. The skill checks the docs *match*; it does not deploy them.
- **Choosing the bump type.**

## Risks

1. **An orchestrator that hides which script failed is worse than the scripts.**
   Every step must name the underlying command and its log path, so any step can
   be re-run by hand. The skill is a conductor, not a wrapper.
2. **Preflight fatigue.** If it flags six advisory things every run, it gets
   waved through — the same dynamic that let 105 partial backups pass a green
   healthcheck. Ship with few, sharp checks; add only on evidence of a real miss.
3. **Judgement checks are the reason this is a skill, and also the least
   reproducible part.** Two runs may critique the same CHANGELOG differently.
   Mitigation: judgement checks are *advisory* and always shown with their
   evidence (the commits they read); only mechanical checks can block.
4. **Partial release is the normal end state**, not an error. PyPI can succeed
   while Homebrew's poll times out. The verify step must report per-channel truth
   rather than one overall verdict.

## Open questions

1. **Should `check-release-ready.sh` run in CI on every push to `main`?** It would
   catch changelog/doc drift continuously rather than at release time, when
   fixing it is most annoying. Cost: another gate that can cry wolf. _Leaning
   yes, advisory-only._
2. **Does `/bn-release` bump and commit, or expect that done?** Bumping is four
   files plus a tag dance with a documented footgun, so folding it in is
   tempting — but it makes the skill's first act a mutation, which sits badly with
   "preflight is read-only". _Leaning: the skill runs `bump-version.py` **after**
   authorisation, as step one of execute._
3. **How does it reach the website repo?** It's a separate private repo on this
   machine. Path via config like `.ship-local.conf`, or assume a sibling
   directory? _Leaning config, with a clear skip when absent._

## See also

- [release-channels.md](release-channels.md) — the five channels, triggers, clocks
- [release.md](release.md) — the CLI process in detail
- [design-testflight-upload.md](design-testflight-upload.md) — the gate-as-precondition
  pattern this generalises
- `desktop/scripts/check-pkg-shippable.sh` — the shape `check-release-ready.sh` copies
