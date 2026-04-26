# Archetypes — decision tree and canonical examples

Six archetypes. Every doc gets exactly one. Classification drives the
edit action; ambiguity defaults to the safer label.

| Letter | Name | Rough test |
|---|---|---|
| A | Fresh | All load-bearing claims current |
| B | Mostly-good with drift | One section drifted, rest verbatim-current |
| C | Middle ground | Multiple sections need triage |
| D | Very stale | Body is a historical artefact |
| E | Insufficient evidence | Cannot cross-check; escalate |
| P | Pending / aspirational | Describes unshipped work |

# Decision tree

```
Did the doc describe shipped or aspirational work?
├─ Aspirational (future roadmap, unshipped feature) → P
└─ Shipped
   ├─ Can you cross-check claims against code?
   │  └─ No (code silent, external systems, unclear) → E
   └─ Yes — how many sections have material drift?
      ├─ None → A
      ├─ At most one → B
      ├─ Multiple, but body still worth rescuing → C
      └─ Body no longer useful except as historical record → D
```

**Ambiguity default:** when hesitating between B and C, pick C. When
hesitating between C and D, pick C unless the body would mislead a
cold reader in every major section.

# Hard tests for each

## A — Fresh

A reader in six months picks up this doc and every load-bearing claim
they act on turns out to be correct. Changelog may be added confirming
the trued-up date. No body edits needed.

## B — Mostly-good with drift

You can list the drifted sections on one hand. Everything else reads
accurately to a new contributor. Fix: targeted inline edits to the
drifted section(s), changelog header listing what changed.

## C — Middle ground

You'd classify as B but you keep thinking "and also…". Multiple
sections need rescue-and-triage. Some true, some drifted, some
superseded by decisions made elsewhere. Fix: section-by-section
treatment. Rescue verbatim where correct, rewrite where drifted, add
`> **Superseded by X as of Y**` banner where superseded. Changelog
summarises the rescue.

## D — Very stale

Body no longer describes how the thing works or how we plan to build
it. Fix: **don't rewrite the body**. Prepend a superseded report,
move to `docs/archive/` with front-matter `archived-historical` (if
factually obsolete) or `archived-reference` (if body still offers
reasoning insight even if obsolete).

## E — Insufficient evidence

Cannot cross-check with reasonable confidence. Examples: doc describes
a subsystem whose code isn't where the doc says; code is silent where
doc expects observable behaviour; external systems you can't inspect.
Do not guess. Escalate — skill prompts human to disambiguate before
any edits.

## P — Pending / aspirational

Doc describes forward-looking work not yet shipped. Classifying
against "shipped reality" is a category error. Stays in top-level
`docs/` with front-matter `status: pending`, body unaltered, changelog
entry confirming doc remains aspirational as of the truing date.

# Canonical before/after examples

Drawn from the Track C truing pass (Apr 2026), which reconciled seven
design docs covering macOS sidecar-signing work (checkpoints C0–C3,
~40 commits). These illustrate what a well-executed archetype action
looks like.

## Example 1 — Pre-spike guess → empirical result (Archetype B fix)

**Drift class:** 1 (pre-spike guesses reality contradicted).

**Before** (`docs/private/road-to-alpha.md` §3):

> C0 spike (see sprint2-tracks.md) will enumerate the actual minimum
> entitlement set by building v0.1 fresh under Hardened Runtime and
> logging every violation. The list below is the best pre-spike guess.

**After:**

> C0 spike completed 18 Apr 2026 (`7d121fa`, `8bd6883`). The minimum
> entitlement set was empirically determined — one key only
> (`com.apple.security.cs.disable-library-validation`). The pre-spike
> guess below was mostly wrong: `allow-unsigned-executable-memory` and
> `allow-jit` are not required. See
> `design-desktop-python-runtime.md` §"Entitlement table" for the
> empirical truth and §"How this was determined" for the test rig.
> The list below is preserved as the pre-spike baseline only — do not
> treat it as current.

**Why this works:** replaces hope with evidence + commit anchors +
cross-ref to authoritative section. Old content preserved as visibly
stale, not deleted. Future readers debugging "why did we pivot?" can
trace the delta.

## Example 2 — "Still unresolved" → "fixed + fail-loud contract" (B/C fix)

**Drift class:** 2 ("still unresolved in CN" about things fixed in
CN+1). Also 4 (shipped guard-rails not documented).

**Before** (`docs/design-desktop-python-runtime.md` §Bundling
gotchas):

> 3. React static bundle must be pre-built. The sidecar runs without
>    `bristlenose/server/static/` but emits a WARNING log line. Still
>    unresolved in C1 — `desktop/scripts/build-sidecar.sh` does not
>    yet invoke `npm run build` before PyInstaller. Slated for C2 /
>    the build-all orchestration script.

**After:** entire "Bundling gotchas" section replaced by "Bundle data
requirements" with a table showing the BUG-3/4/5 class (React SPA
static, codebook YAMLs, LLM prompts), each with commit anchor and
pre-fix symptom. React SPA is row 6 of 7, hard requirement, fail-loud
contract documented in a new "Fail-loud contracts" section.

**Why this works:** when the fix was structural (not just "do the
thing"), the doc restructuring mirrors it. "Gotchas" framing implied
future improvement; "requirements" framing codifies the invariant.

## Example 3 — Status-table desync (Archetype C fix, cross-doc)

**Drift class:** 3 (status-table desync across docs).

**Before** (`docs/private/road-to-alpha.md` table):

```
| 4 | PyInstaller sidecar signing script | ⬜ S2 |
| 5 | Hardened Runtime entitlements      | ⬜ S2 (comes with 4) |
```

**After:**

```
| 4 | PyInstaller sidecar signing script | ✅ C2 code done
      (fc95b99..cd04ee9); end-to-end archive blocked by
      SECURITY #5+#8 |
| 5 | Hardened Runtime entitlements      | ✅ C0 spike done
      (7d121fa) — one key only
      (cs.disable-library-validation); C2 shipping verified |
```

**Why this works:** status update isn't just ⬜ → ✅. The ✅ carries
commit anchor + one-line "what's still pending" (SECURITY #5+#8 is a
blocker, not a failure). Honest ✅ beats optimistic ✅. Cross-doc
sweep resolved parity with `sprint2-tracks.md` in the same pass.

## Example 4 — Shipped guard-rail, no prior doc coverage (C fix, structural)

**Drift class:** 4 (shipped guard-rails not documented).

**Before:** `check-bundle-manifest.sh` existed in the repo, wired into
`build-all.sh` step 2a, but appeared in zero design docs. A reader
opening the design docs would have no idea the gate existed or why.

**After:** new "Validation gates" section in runtime doc listing all
four gates (logging-hygiene, bundle-manifest, release-binary, doctor
self-test) with, for each:

- Stage (when it runs)
- Commit anchor
- Exactly what class of defect it catches
- Why a unit test can't catch it

**Why this works:** the "why a unit test can't catch it" line matters
most. Each gate exists because a specific class of bug slipped
through. Capture that.

**Structural-addition test passed:** four shipped things, shared
framing (fail-loud guard-rails extending from signing pipeline) —
earns a section. A one-off script wouldn't; it'd be a row in an
existing table.

## Example 5 — Session-notes lesson promoted (C fix, lesson migration)

**Drift class:** 5 (lessons stuck in session notes, not promoted).

**Before** (in `c2-session-notes.md` only):

> macOS default bash 3.2 → `wait -n` requires bash 4.3+. Fixed shebang
> to `#!/usr/bin/env bash` + homebrew bash in `$PATH`.

**After** (promoted to `design-desktop-python-runtime.md` signing
section):

> Uses a `bash wait -n` job pool, not `xargs -P`: BSD `xargs` on macOS
> drops child exit codes under concurrent jobs, so a single failed
> `codesign` would be masked in interleaved stderr (the script would
> "succeed" while shipping an unsigned dylib). Requires bash 4.3+ for
> `wait -n`; Apple's default `/bin/bash` is 3.2, so the shebang is
> `#!/usr/bin/env bash` + a Homebrew bash in `$PATH`.

**Why this works:** war-story version in session notes ("we found
this, here's what we did") is not what the design doc needs. Design
doc needs the invariant + the consequence if violated ("would ship an
unsigned dylib"). Both versions stay — war story in notes, invariant
in design. Session notes remain append-only.

# Cold-reader triage rule

When deciding which bullets from an agent's gap list deserve edits
this pass:

> Would a cold reader picking up this doc fresh in six months be
> misled by this gap?

If yes → fix this pass.
If no (cosmetic phrasing, commit-anchor nit, cross-ref staleness on a
minor point) → log and defer.

Volume of edits is not a success signal. Fewer well-chosen edits beats
many cosmetic ones.

# What about marked-historical docs?

A doc with an explicit "rejected path" or "historical — see X for
current approach" banner at top is **not a truing target**. It may
need a dated post-script acknowledging what happened after the
rejection — flag that separately. Don't try to drag the body to match
current reality; that erases the record.

# What about CLAUDE.md?

Out of scope for v1. CLAUDE.md files are always-loaded-into-context
truth docs with higher blast radius. A trued design doc + stale
sibling CLAUDE.md can be worse than two stale docs (trust-by-
association). Flag the limitation to the user; don't attempt.
