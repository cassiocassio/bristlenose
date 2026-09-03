---
status: current
last-trued: 2026-09-03
trued-against: release.sh's seven verbs incl. run/retry/recover; the RELEASE_STEPS_FILE credential seam; the pypi hold removed 23 Aug
---

# The release machine — architecture

**Status: SHIPPED.** _Corrected 3 Sep 2026 — this line read "proposed, 23 Aug
2026" while §18 and §19 below described what shipped that same day, and the doc
carried no front-matter at all, so nothing mechanical contradicted it either. A
pointer sweep reading only the header got the wrong answer in the reassuring
direction._ **Rewritten after review** — the first draft's central structural
choice was wrong and its scope was too large. Both are recorded in §14 rather
than quietly dropped.

**Refines D1** of `docs/design-bn-release-skill.md` and implements part of the
"what to build first" list that doc left open. **Corroborated by**
`docs/design-release-system-audit.md` §6.3, which reached the same finding
independently on 14 Aug — *"Phase 6 preaches probe-don't-remember, then needs a
remembered delivery UUID; the dmg resume path exists as header prose, not
mechanism; the mid-flight channel-state matrix has no representation anywhere."*

**Companion mockup:** `docs/mockups/release-machine-paths.html`.

**Prior art surveyed:** Debian `britney2`, Fedora Bodhi, openSUSE Factory /
`totest-manager`, the Linux kernel `-rc` cadence, Mozilla's train model,
GoReleaser, JReleaser, release-please, Spinnaker/Temporal, in-toto/SLSA (§2).

---

## 1 · The problem, stated from evidence

`docs/release-log.md`'s 0.27.0 entry is the input. Nine tricky things. The first
draft claimed three of them were one failure — *"a fact existed and was never
recorded"* — and built a conveyor around that claim. **Review falsified it:**

| # | Symptom | Actually |
|---|---|---|
| 1 | Five runs reported exit 0; three had failed | **Recorded.** The log said `✗ Build failed`. It was *read* wrong |
| 6 | "I approved it" vs `pending_deployments` pending | **Recorded.** The API said pending. It was *read* wrong |
| 7 | Perf red for four runs, nobody knew | Genuinely unrecorded — and it is a *workflow*, not a channel |

Two of three are **reading** failures, not recording failures. That matters
because `docs/design-release-system-audit.md` §6.4 already names the cost of the
obvious fix: *"Knowledge quadruplication. Drift between copies is
unpredictability on a delay."* A fourth artefact to read is not obviously the
cure for a reading problem.

So the scope is now **two tiers**, and the second is conditional:

- **Tier A — make the existing facts read correctly, and probe what isn't
  probed.** ~120 lines across files that already exist. Closes 6 of 9.
- **Tier B — the event log and driver.** Closes the remaining two (measured
  timings, stranded steps) at roughly three times the cost. **Deferred until
  Tier A has run for two releases** and the release log says whether the gap is
  still worth closing.

## 2 · What the prior art agrees on

Nine systems, one shape: a **conveyor** that owns order and state; **gates that
can only say no**; and a small number of **human verdicts that are named,
located and few**. The property that matters most:

> **The human decision is a verdict, not work.** Fedora has one Go/No-Go.
> openSUSE has one Factory Maintainer acceptance. Debian's overrides are
> committed hint files. Nowhere does a human *perform a step*.

`/bn-release` already has all three layers. The conveyor is the weak one — but
see §1: weak is not the same as absent, and the cheapest repairs are to the
reading, not to the recording.

Borrowings that survive review:

| From | Idea | Where |
|---|---|---|
| Debian age policy | a gate has a freshness property | §5 A5 |
| in-toto | "did the step run" is evidence, not memory | §7, deferred |
| Spinnaker | Manual Judgment is a modelled stage | already shipped — the `pypi` hold |
| `check-release-ready.sh` | **probes are tri-state** | §5 A6 — in-house, not borrowed |

## 3 · What `report.sh` is, and what it is not

`desktop/scripts/report.sh` emits six event kinds — `meta · step · check · gate
· art · done` — with `bn_trap_fail` guaranteeing a terminus on any exit path.
The first draft called this "the conveyor's event protocol, unpersisted" and
proposed persisting it inside `build_report.py`. **That was wrong, in four
independent ways, all reproduced during review:**

1. **`bn_autowrap` takes `PIPESTATUS[0]` and discards the renderer's status**
   (`report.sh:114-117`). A sink inside `build_report.py` sits in the one
   process whose exit code is thrown away by design. Sink fails → `rc=0`, zero
   events, nothing says so.
2. **`_BN_ACTIVE` suppression is process-tree-based, not stream-based**
   (`report.sh:49-50, 100-101`). A driver that renders its own output silences
   every child's events — measured at 0 bytes. This is also why
   `build-all.sh:76-107` invoking five `check-*.sh` children as `>/dev/null`
   means **one** script emits during a real release, not six.
3. **`printf '%q'` emits ANSI-C `$'…'` for control characters; `shlex.split`
   raises on an apostrophe inside one; `parse_event` returns `None` and the line
   is dropped.** rsync's carriage returns and altool's *"Couldn't communicate"*
   are exactly the adoption targets.
4. **`_st()` maps any unrecognised status to `INFO`, and `_on_done` treats
   anything ≠ `fail` as success.** `@bn done status=partial` renders a **green
   ✓ Done** and exits 0 — the design's own failure class, aimed at itself.

**Conclusion: `report.sh` is a presentation protocol and should stay one.** It
is good at its job (`PIPESTATUS[0]` is correct on precisely the hazard the
release log records; the EXIT trap does not perturb the script's status). If
Tier B is ever built, **the driver is the sole event producer** — it writes the
log itself from what it observes, and never parses the `@bn` stream.

## 4 · Tier A — the work that is actually justified

Every item closes a numbered incident, touches a file that already exists, and
is independently shippable.

| | Change | File | Closes |
|---|---|---|---|
| **A0** | `.gitignore` rule for `.release/` | `.gitignore` | prerequisite for A7 — see §6 |
| **A1** | TTY-gate `--progress` on `[ -t 1 ]` | `upload-dmg.sh:289` | #2 |
| **A2** | Per-attempt upload log naming + `bn_art key=delivery` | `upload-testflight.sh:186,211` | the un-reconstructable UUID |
| **A3** | `pending_deployments` row, tri-state | `check-release-ready.sh` | #6 |
| **A4** | Dependency-drift row | `check-release-ready.sh` | #5 + the `openai` owed item |
| **A5** | Gate-freshness row | `check-release-ready.sh` + `.release/gates.jsonl` | build failure 1 |
| **A6** | `verify-channels.sh` | new, ~120 lines | #7, #8 · Phase 6 executable |
| **A7** | One rule in `SKILL.md` | `.claude/skills/bn-release/SKILL.md` | #1 |
| **A8** | Nothing-to-ship check | `check-release-ready.sh` | Phase 1's cheapest test, currently prose |
| **A9** | Refuse ad-hoc `SIGN_IDENTITY` | `build-all.sh:37,110` | six gates silently off — **shipped, then found insufficient**: see A9-bis |
| **A9-bis** | Split the overloaded signing variable | `build-all.sh`, `build-dmg.sh`, `check-release-ready.sh` | A9 made the ACCIDENT fail; it could not see that one variable named two certificates |
| **A10** | Doc-surface flag parity | `check-release-ready.sh` | Phase 2.2, currently prose |

**A9-bis — why A9 was necessary and not sufficient.** A9's principle was right and
is unchanged: *the ACCIDENT fails, the INTENT works*. What it could not see is that
`SIGN_IDENTITY` named **two different certificates**. `build-all.sh` signs an App
Store archive with Apple Distribution; `build-dmg.sh` signs a notarised download
with Developer ID Application — and both *export* the variable to their child
signers, so exporting the value one needs silently mis-signed the other.

A9 therefore hardened the half that fails loudly (unset) and left the half that
fails quietly (set, but for the other script). On 27 Aug 2026 that shipped a `.dmg`
whose inner app was correctly notarised Developer ID inside an image signed Apple
Distribution — caught by the last assertion before upload, 30 minutes and one
notarisation round-trip after the mistake was made.

Fixed by giving each entry point its own variable and asserting the certificate
*type*, so the wrong cert is refused at second zero. The child contract is
unchanged. The transferable lesson is narrower than "validate inputs": **a shared
name is a shared assumption, and an exported one is a shared assumption you cannot
see from the script that suffers for it.**

**A1 is the model for the whole tier.** `upload-testflight.sh:202` already gates
`--show-progress` on `[ -t 1 ]`. The first draft proposed `tr '\r' '\n'` in a
driver; the sibling script solved it properly one directory over, in one line,
and fixes the log for a human tailing it too. **Look next door before designing.**

**A4 is the highest-value item and was absent from the first draft.**
`THIRD-PARTY-BINARIES.md` is a committed, per-package resolved inventory;
`generate-third-party-binaries.py --check` already hard-fails `build-all.sh`
(it fired on 0.27.0's build failure 2). Running that same comparison in the
**preflight** moves discovery of `openai 2.9.1 → 3.0.0` from 10pm mid-release to
the free first step. Grade minor/patch `warn`, major `bad`. Cost: one script
invocation the build already makes, ~40 minutes earlier.

**A7 is the one that closes #1, and it is a sentence, not a system.** The pipe
that lost three build failures was the *agent's* (`build-all.sh … | tail` in a
background task), one level above the script — `upload-testflight.sh:202-205`
already implements redirect-then-`$?` verbatim and #1 happened anyway. The fix
is the rule `CLAUDE.md` already uses for pytest, applied to release steps:

> **Never report a step's outcome from a background task's exit code.** Redirect
> to a file, read the file, quote its verdict line.

## 5 · Contracts the Tier A rows must honour

**A5 · gate freshness needs a cross-release home.** Nothing records a gate's
last-run sha today. Freshness is inherently cross-version, so it cannot live in
a per-version directory: `.release/gates.jsonl`, appended by each gate (id, sha,
verdict, ts). **Absent = stale, reported as `never run under the freshness
system`** — not as a failure, so the first releases' noise is self-explaining
rather than training anyone to ignore it.

And it must **stop `run`, not just warn in `plan`.** The first draft made it a
warning on a screen offering `Run anyway` — under which 0.27.0's build failure 1
survives this design entirely. Override is `--allow-stale-gates`, recorded, so
the next release log can count how often it was used. *A bypass nobody counts is
a bypass that becomes the default.*

**A6 · every probe is tri-state, and the pattern is in-house.**
`check-release-ready.sh:204-215` and `:337-372` are exemplary and
`verify-channels.sh` should copy them rather than re-derive:

```bash
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$URL" 2>/dev/null || echo "000")
case "$CODE" in
  200) ok   "PyPI" "$V published" ;;
  404) bad  "PyPI" "$V not published" ;;
  *)   warn "PyPI" "could not reach PyPI (HTTP $CODE) — unverified" ;;
esac
```

> **A successful probe wins. An unsuccessful probe wins over nothing.**

A failed probe must never read as a negative one. `gh api …/pending_deployments`
with expired auth returns empty — folded naively that is *"no pending
deployment"*, i.e. **a network fault reading as a human approval.** This is
release-log #8's class (*"I can't probe this" was itself an unchecked claim*)
and the house rule from `design-release-system-audit.md` §3 covers it: **a check
that could not run reports that it could not run.**

**A6 · probe for the abandoned version, not just the target.** 0.27.0's real
website failure was the live changelog naming **0.26.0** — a version that no
longer existed — while the download served 0.27.0. A presence-of-target probe
passes the moment 0.28.0 appears and would not have caught it. Where a surface
renders from `CHANGELOG.md`, assert **absence of abandoned versions** too.

**A6 · assertions use `|| die`, never `&& ok`.** `verify-channels.sh` is nothing
but assertions, making it the highest-risk new file in the repo for the defect
`CLAUDE.md` documents at length and that `build-dmg.sh` shipped twice.

## 6 · Security contracts

Five findings, one of them proven by execution. **A0 is not optional and is not
"assumed".**

1. **`.release/` is not gitignored today.** Verified: `git check-ignore` exits 1,
   `git add -An .release/` stages the log and every step log. The first draft
   asserted the property in its data-structures section and assigned it to
   nobody. It is now **A0**, before anything creates the directory. No negation
   — the `.bristlenose/` fixture negations exist for a committed test contract
   and nothing here will ever need one; say so in the comment so a future
   session doesn't invent one.
2. **`upload-dmg.sh`'s stdout carries the publish host and path**
   (`:173,219,223,225,367`), a string `.gitignore`'s own comment says *"would be
   permanent in history"*. Any move of its log out from behind `desktop/build/`'s
   ignore rule is a leak path. A0 first; and **echoed commands name env vars
   rather than expanding them** — `upload-testflight.sh:296-297` already
   demonstrates the house pattern.
3. **Any log the release writes is 0600 + `O_NOFOLLOW`**, matching
   `bristlenose/llm/telemetry.py:268-269`. Different asset class from the
   re-identification keys — no participant data goes near this — but the same
   handling mechanism, because a 0644 exception invites the next one.
4. **Anything folded into `docs/release-log.md` needs a positive allowlist.**
   That file is tracked and public, and it is the only path in this design
   reaching git history — the one surface with no undo. Permitted: step names,
   statuses, exit codes, elapsed times, attempt counts, held intervals, channel
   verdicts. Never: `art` values, `log=` paths, `$HOME`-rooted paths, anything
   from `.ship-local.conf`.
5. **Out of band, and worth acting on separately: `pre-commit` is not
   installed.** `.git/hooks/` holds only `commit-msg`; `pre-commit` is on neither
   `PATH` nor `.venv/bin`. So `.pre-commit-config.yaml`'s **gitleaks** hook and
   its `tracked-vs-gitignore` sibling have never run here, while `SECURITY.md:233`
   states *"gitleaks pre-commit hook locally"* as a control. Either run
   `pre-commit install` or correct the claim — a security doc asserting an
   uninstalled control is worse than one that doesn't.

## 7 · Tier B — the event log, and why it waits

If Tier A leaves a gap worth closing, it is these two: **measured timings**
(§8's honesty mechanisation) and **stranded steps** (which has happened once).
The design, recorded now so it isn't re-derived:

**The driver is the sole event producer.** It writes `.release/<version>/events.jsonl`
from what it observes — step name, start, exit code, elapsed, log path — and
never parses `@bn`. That single placement kills §3's four defects, the two-writer
`seq` collision, and the discarded-stdout problem, and it removes the five-script
adoption entirely.

**Fold, don't store.** Run state is derived on every read. This preserves D1:

> **State someone else owns, you probe. State you own, you record.** An
> append-only log *records*; a state file *asserts*.

**But the skip decision is an assertion, and must be probed.** `run` skipping a
step recorded `ok` is a claim about the present drawn from a statement about the
past — and it goes stale exactly as 0.26.0's would have, whose log would say
`push main + tag ok` for a tag that was then deleted. **Before skipping any step
in the irreversible block, probe it.** Skipping on the log alone is fine for the
reversible block, and that asymmetry is deliberate.

**Verdict precedence — fail wins, absence is not ok:**

| script says | exit | verdict |
|---|---|---|
| `fail` | 0 | **fail** |
| `ok` | ≠ 0 | **fail** — never ok |
| nothing | 0 | **`unverified`** — not ok |
| nothing | ≠ 0 | fail |

The third row is the common one: `website deploy` runs in another repo,
`approve publish` is a browser, `snap edge` is `gh workflow run`. The fold must
distinguish *"no events because this step doesn't emit"* from *"no events
because it died before its first emit"*.

**The fold fails loud on corruption.** F3 makes a truncated final line the
*expected* case, so: fail on any unparseable line except a single trailing
partial one, reported by name. **Spend `seq`** — a gap is free, mechanical proof
of a lost event, and `attempt` numbering derives from the fold, so a dropped
line risks `logs/<step>.<n>.log` colliding and *overwriting the evidence of the
failure being debugged*.

**A step that recorded nothing is not a step that succeeded.** Assert it per
step. This is the single structural check that catches most of §3's class.

**Mechanisms that must be named correctly:** `flock` does not exist on macOS
(verified — `lockf` and `shlock` do). Use a `mkdir` mutex with the pid inside,
which makes the stale-lock case legible — and F3 produces stale locks by
construction. `date -v+30d`, not `date -d`. Validate the version argument with
the `case` guard at `upload-dmg.sh:123-131`: the realistic failure isn't
traversal, it's `0.28.O` folding a fresh empty log and reporting *"0 of 13 steps
done"* for a release eight steps in.

**Exit-code vocabulary**, because the first draft had `held` and `complete` both
exiting 0, and `verify` exiting 1 on what it called a normal outcome:
`0` complete · `75` held (`EX_TEMPFAIL`) · `1` failed · `2` lock held · `3`
stranded. *Held is not an error* stays a **presentation** rule.

**Tamper-evidence is separable from signing.** Signing (in-toto proper) is
correctly out of scope for a single-maintainer laptop and always will be. A
`prev` SHA-256 chain is ~3 lines, needs no keys, and is the property "an
append-only log cannot be wrong" already claims. Build that, or soften the claim.

## 8 · Logging and reporting

Tier A adds no new artefact. `docs/release-log.md` stays human-written, and
Phase 7's timings stay honestly marked `estimated`.

If Tier B lands, Phase 7 reads the fold — and **must fail loud and mark its
numbers `estimated` when the log is absent or incomplete**, or it reproduces the
exact honesty gap it exists to close, now wearing a "measured" label.

The timing split must not reconcile by construction. `pipeline = wall − held` is
a tautology of the same family as `attempted == succeeded + failed`, which
`CLAUDE.md` documents at length. Sum what was measured and show the remainder:

```
  pipeline time    1h01   measured · sum of 8 steps
  waiting on you   1h48   3 held intervals
  unaccounted        18m  between steps — driver idle, or a gap in the log
  wall clock       3h07
```

The fourth row is the only one that could ever catch anything.

## 9 · Configurability

Tier A: none. Every row is a preflight check or a one-line script change.

Tier B, if built — `--tier`, `--build-only`, `--skip <step>`, `retry <step>`,
`--allow-stale-gates`. **`--from <step>` is deliberately absent:** it lets a
human assert a position the log doesn't support, which is exactly the
"state file that can be wrong" capability §7 spends its argument removing,
re-entering as a flag. **One namespace** — the log's `step` identifier
everywhere, in `--skip`, in `retry`, and on every screen.

**Credentials are gathered at the confirmation, not discovered by steps
(31 Aug 2026).** The 0.29.1 run died at `build-all` on an unset
`SIGN_IDENTITY_APPSTORE` — four steps in, after an outward-facing push — and
the audit that followed found the whole class: the run's design intent is *one
authorisation, then bed*, so anything a step can ask for must be resolved,
probed and displayed **above the typed confirmation**, while a human is
provably present.

> **Amended 3 Sep 2026 — the block is skipped under the test seam.** A sandbox
> has no certificates, so gathering them above the confirmation killed
> `test-release-e2e.sh` outright: the driver died at exit 2 before the step loop
> the suite exists to exercise, 82 assertions all reporting one cause. The whole
> block is now guarded on `RELEASE_STEPS_FILE`, and the identity exports are
> conditional. A synthetic step table means there is no release to gather
> credentials for.
>
> **Why not a new bypass flag, which is the obvious fix:** it would be settable
> in production, and could therefore reinstate the exact 31 Aug bug this block
> exists to prevent. `RELEASE_STEPS_FILE` is already documented in
> `release.sh` as *"a testability seam, not a feature … Unset in every real
> invocation"*, so reusing it costs no new surface. Stubbing was also considered
> and does not work: `stat -f '%Lp'` is BSD and the suite runs on ubuntu, so the
> harness would have to impersonate a Mac. `verdict_signing_identity` keeps its
> coverage from `test-release-sh.sh`, which drives it directly as a pure
> text→verdict function. `cmd_run` now: refuses an ambient generic `SIGN_IDENTITY`
(the 27 Aug vector, made active rather than warned); sources
`.ship-local.conf` (env wins); resolves both signing identities **by
certificate type with per-type keychain policy** (the installer cert is
invisible under `-p codesigning` — measured) via the pure, suite-driven
`verdict_signing_identity` (fingerprint pins, because renewal twins share a
name); then runs an announced probe battery — a throwaway `codesign` per
identity, `notarytool history`, the ASC `.p8` (file + mode 600, Apple's
documented layout — a settled decision, not an omission), `git push
--dry-run`, `gh auth status`, ssh BatchMode to the dmg host, the Finder TCC
dialog `create-dmg` will need, bundled ffmpeg presence, and a `pmset` sleep
warning. Every probe is timeout-wrapped with exit 124 reported as
**blocked-on-a-dialog** (a distinct state: on an unattended resume a GUI
dialog *hangs* a probe rather than failing it). After the confirmation the
run is armed: identities exported **by fingerprint**, `GIT_TERMINAL_PROMPT=0`
+ askpass/ssh-askpass forced off so anything missed fails loud instead of
prompting, and the step loop held awake by `caffeinate -i -w $$` — idle sleep
was the overnight run's quietest failure mode, and no env var converts
machine sleep into an error.

Credentials stay in `desktop/scripts/.ship-local.conf`. Note the file holds two
sensitivity classes, which the first draft collapsed into one row: three ASC
identifiers that `upload-testflight.sh:53-54` correctly calls non-secret, and
`BRISTLENOSE_DMG_REMOTE`, which `.gitignore` separately rules must never be
committed. The `.p8` lives outside the repo entirely.

## 10 · DUX

Tier A changes nothing a human types except adding `verify-channels.sh`.

Tier B's subcommands are `plan · run · retry · recover · status · verify ·
abandon` — **seven, and each earns its place** (`recover` and `abandon` landed
after this was written as five). `verify` is not `status --channels` because they are
different cost classes: one folds a local file instantly, the other makes seven
network probes.

Five rules:

1. **Every step prints the command before running it** — the conductor rule,
   applied to the driver.
2. **A failure prints the exact line to re-run — innermost first.** The first
   draft's F1 offered an 11-minute rebuild that would fail identically; the
   command wanted is `check-window-surfaces.sh`, which runs in under a second.
3. **`status` is the default with no arguments** — and names which attempt it
   picked, since two version directories is the 0.26.0/0.27.0 situation exactly.
4. **Nothing irreversible runs without printing its consequence immediately
   before it.** The first draft marked these in `plan`, where nothing happens,
   and dropped them from `run`, where the act occurs.
5. **Every echoed command is redacted the same way a log tail is.** Rules 1 and
   5 together create a credential-echo surface, and the transcript is what gets
   pasted into a bug report.

**`run` = resume needs no defence beyond an internal one:** `bristlenose run
<folder>` already resumes from its own event log. Same verb, same laptop, same
semantics.

**Gap to name or refuse:** if `run` always resumes and `retry` is scoped to
stranded steps, there is no verb for *redo a step that already succeeded* — a
`.dmg` rebuild after a fix, with `build-dmg` recorded `ok`.

**And there is no `abandon`,** in a design built on a release whose headline was
an abandoned tag. The 0.27.0 log records the second-order consequence: the live
changelog renders from `CHANGELOG.md` at build time, so *"a version abandoned
before publication leaves a footprint on any surface already rendered from the
changelog"* — and its conclusion is that abandoning should treat the website
deploy as part of that decision. Either add the verb or print the consequence
alongside the raw `git push --delete` recipe.

## 11 · Options considered

| | Option | Verdict |
|---|---|---|
| **A** | Status quo | Rejected — but less decisively than the first draft claimed. Two of three headline failures were reading failures, which Tier A fixes without new machinery |
| **B** | GoReleaser / JReleaser | Rejected. Covers Homebrew, Snap, GitHub Release, notarization, SBOM — but assumes it owns the conveyor. An Xcode archive, `notarytool`, an rsync behind an SSH agent, a spent build number and a browser approval are not plugin-shaped. Three of seven channels adopted, four hand-driven, **and the order then lives in two places** |
| **C** | Temporal / durable execution | Theoretically exact, rejected on proportion: a server and workers under a process that runs twice a month on one laptop |
| **D** | Makefile | Rejected. Targets model dependencies, not irreversibility order, and timestamps are the state file D1 refuses |
| **E** | Python driver | Rejected narrowly — every step, gate and probe is already shell or `curl` |
| **F** | `.release-state.json` | Rejected — D1's actual target, and it remains right |
| **G** | Event log + thin shell driver, all at once | **Rejected on review.** Right shape, wrong size and wrong sink placement |
| **H** | **Tier A now; Tier B on evidence** | **Recommended** |

### Why H

1. **Tier A closes 6 of 9 incidents for ~120 lines**, in files that already
   exist, with no new artefact to read — which matters because two of the three
   headline failures were reading failures and §6.4 of the audit warns that a
   fourth copy is unpredictability on a delay.
2. **A4 alone closes the one owed item the first draft skipped**, using an
   inventory already in git and a generator the build already runs.
3. **It keeps every existing gate where it is** — inside the irreversible act.
4. **It does not weaken D1**, and §7 records the refinement for when it's needed.
5. **Tier B is designed, not deferred vaguely.** §3 and §7 hold the four defects
   and the precedence table, so the option stays open at full information.

## 12 · Build order

**Tier A**, in dependency order. A0 first, and only A0 is a prerequisite.

| | Step | Closes | Note |
|---|---|---|---|
| **A0** | `.gitignore` for `.release/` | — | Prerequisite. Also stops the preflight's untracked row drowning in machine files |
| **A1** | TTY-gate `--progress` | #2 | One line |
| **A2** | Per-attempt log + `art` delivery | UUID | One line each |
| **A3** | `pending_deployments` row | #6 | Tri-state |
| **A4** | Dependency-drift row | #5, owed | Highest value |
| **A6** | `verify-channels.sh` | #7, #8 | The only substantial one |
| **A5** | Gate freshness | build fail 1 | Needs A0 for `.release/gates.jsonl` |
| **A9** | Refuse ad-hoc `SIGN_IDENTITY` | 6 silent gates | One line. Sibling already does it |
| **A8** | Nothing-to-ship check | wasted releases | One `git diff --stat` |
| **A7** | The `SKILL.md` rule | #1 | A sentence |
| **A10** | Doc-surface flag parity | doc drift | The only fiddly one — roff escapes |

**Tier B is gated on evidence, not on time:** build it when two consecutive
release-log entries show a stranded step or an unusable timing estimate. If they
don't, that is the answer.

## 13 · Tests

Not blanket coverage — two named gaps, at the cheapest layer, in the house style
that `desktop/scripts/test-upload-dmg.sh` already demonstrates (pure decision
functions extracted and sourced, every assertion proven to fail on its own
violation, honest `skip` when an artefact isn't on disk).

| | What | Why |
|---|---|---|
| **T1** | `verify-channels.sh`'s **probe-verdict decision**, canned inputs | Not the network round trip — the tri-state decision. `200`/`404`/`000` in, ok/bad/warn out. This is A6's whole risk |
| **T2** | The **fold**, if Tier B lands | Its output authorises skipping irreversible steps. Synthetic `events.jsonl` in, state out. No I/O, no mocking — the plan's own words ("a pure function of the log") make the case |

Deliberately **not** tested: any fake-GitHub / fake-Apple / fake-PyPI rehearsal
harness. That is Options B/C's proportion problem recreated as test
infrastructure for a process that has a real acceptance test every time it runs.

**Noted, separate cleanup:** `test-upload-dmg.sh` and `test-ensure-sidecar.sh`
duplicate an identical `ok()/bad()` pair; `test-check-pkg-shippable.sh`
reinvents it a third way. Three near-duplicates is the Rule-of-Three trigger,
and this plan would add a fourth. A ~10-line `desktop/scripts/test-lib.sh`, as
its own commit, not a blocker here.

## 14 · What the first draft got wrong

Recorded rather than deleted, because the errors are more instructive than the
corrections.

1. **The sink was placed in `build_report.py`** — inside the one process whose
   exit code `bn_autowrap` discards, behind a process-tree suppression flag,
   behind a parser that drops events on an apostrophe. It would have reproduced
   the plan's own failure class on the audit trail, where nothing downstream
   would ever notice. §3.
2. **"Structurally impossible" was overclaimed for F1.** `upload-testflight.sh:202-205`
   already implements redirect-then-`$?` and #1 happened anyway, because the
   pipe was the agent's. The driver moves the boundary up one level; it does not
   remove it. §4 A7.
3. **The premise was wrong.** Two of the three "unrecorded facts" were recorded
   and misread. §1.
4. **`.gitignore` was asserted, not assigned.** §6.
5. **`@bn done status=partial` renders green.** The design's own class. §3.
6. **`flock` was specified on a platform that lacks it.** §7.
7. **§12 claimed independence it didn't have** — gate freshness lived in `plan`,
   a driver subcommand from the step after it.
8. **The mockup fabricated evidence.** `ProjectWindowController.swift` does not
   exist; `build-all.sh` has 11 steps, not 18; `check-window-surfaces` is a
   `bn_check` under step 1, not step 2. A screen whose job is trustworthy detail
   cannot be the one carrying invented detail.

## 15 · Open questions

1. **Approval: probe-only. Confirmed — but the reasoning changes.** Filed as
   *"a product question about ceremony"* it gets re-litigated at 11pm by someone
   correctly observing that ceremony is friction. The durable justification is
   **untrusted input**: the driver feeds an agent `git log` subjects, failing
   step-log tails containing third-party build output, and third-party API
   responses. A verb the agent can invoke is a verb that text can reach — the
   same channel `bristlenose/llm/billing_hints.py` already escapes provider
   exception strings for. Note also that probe-only guards the *hard* line and
   nothing else: `run` already crosses the soft line.
2. **`.release/` vs `.bristlenose/release/` — closed, `.release/` wins**, and
   not on cost. `.bristlenose/` is the per-run state dir holding `pii_summary.txt`
   and `llm-calls.jsonl`; nesting release machinery there means `rm -rf
   .bristlenose` to purge participant data also destroys the release record.
3. **Does Tier A make Tier B unnecessary?** The honest answer is that two
   releases of evidence will say. That is the same discipline `docs/release-log.md`
   was started under, applied to this document.

## 16 · Adversary review — what a well-resourced attacker gets

Written 23 Aug 2026 at the maintainer's request. Posture: an attacker with
abundant automation, starting from **only what is public** — the GitHub repo,
PyPI, the Homebrew tap, the Snap store, `bristlenose.app`. Goal: ship code to
Bristlenose users, or reach the maintainer's Mac.

**The prize is the Mac, not the repo.** One laptop holds the Apple Distribution
identity, the ASC API key, the SSH agent for the web host, a `gh` token with
repo scope, and `.ship-local.conf`. Every chain below is scored on whether it
reaches that machine or the artefacts it signs.

### What already holds — measured, not assumed

Say this first, because it changes which chains are worth an attacker's time.

- **No self-hosted runners.** All nine workflows are `ubuntu-latest` /
  `macos-latest` / `macos-15`. This closes the worst class outright — a fork PR
  cannot reach hardware.
- **Secret-bearing jobs are unreachable from a fork PR.** `snap.yml`'s publish
  job gates on `github.event_name == 'workflow_dispatch'`;
  `install-test.yml`'s key-bearing `full-run` gates on `schedule ||
  workflow_dispatch`. Both carry the reasoning inline.
- **`contents: read` at top level on 8 of 9 workflows**, with per-job escalation.
- **Trusted Publishing** — no long-lived PyPI token exists to steal. PEP 740
  provenance and SBOM attestations are already generated.
- **Third-party actions that touch secrets are SHA-pinned** —
  `peter-evans/repository-dispatch@ff45666b…`, `snapcore/action-publish@214b86e5…`.
- **The `pypi` environment hold** means no automated path publishes.

That is a genuinely hard target. The chains below are what remains.

### C1 — The dependency floor. Cheapest path, needs no contact with the repo.

`pyproject.toml:44-46` is floor-only by written policy and **there is no lock
file**. 0.27.0 proved the consequence empirically: `openai>=1.50` resolved to
**3.0.0** during the release build, discovered at 10pm.

So the attack is: compromise **any** package in the transitive tree — or just
its maintainer's account — and wait. `build-all.sh` runs PyInstaller against a
fresh resolve on the maintainer's Mac. Arbitrary code executes at build time on
the machine holding the signing identity, and the resulting sidecar is then
**signed, notarised and shipped to TestFlight by the legitimate pipeline.**

Nothing in the current design detects it. `THIRD-PARTY-BINARIES.md --check`
fires *during* the build, after the resolve.

**Mitigations.**
1. **A4 promoted from `warn` to a hard stop on a major**, and moved before any
   build. Detection is not the same as refusal.
2. **Hash-pin the build environment.** The runtime policy can stay floor-only —
   it is defensible, and pinning without a renovation bot ships known-vulnerable
   transitives for eighteen months. But the *sidecar build* should resolve from
   a committed `requirements-build.txt` with `--require-hashes`, regenerated
   deliberately. That splits "we take upgrades quickly" from "a release resolves
   what a release resolved."
3. **`art key=deps-sha`** recording the resolved set per release, so *"which
   versions were in build 2856"* stops being unanswerable.

### C2 — Prompt injection into the release agent. The novel one.

The repo is public, so anyone can open a PR or file an issue. The release agent
reads, as a matter of design: `git log <last-tag>..HEAD` subjects and bodies
(Phase 1), the diff, **failing step-log tails containing third-party build
output** (pip, npm, `xcodebuild`, `notarytool`), and third-party API responses
(PyPI JSON, `api.snapcraft.io`, the GitHub API).

It reads them at 11pm, holding Bash, after a human has granted **one
authorisation, not per channel** — a property §2 correctly wants for human
factors and which an attacker inherits.

`SECURITY.md:98-110` already accepts untrusted-text-reaching-a-model as live
risk, and `bristlenose/llm/billing_hints.py` escapes provider exception strings
on exactly this reasoning. The release path is the same channel, one layer out,
and is not covered.

**Mitigations.**
1. **The driver never constructs a command from repo or network content.** Step
   commands come from the driver's own `case`. Nothing read from a log, a diff,
   a commit message or an API response is ever interpolated into a command,
   `eval`-ed, or used to select a step.
2. **Quote, never interpolate.** Log tails and probe output are printed inside
   an explicit fenced block labelled as untrusted, so injected text is visibly
   data. This is what §15's answer to the approval question already depends on.
3. **Keep approval probe-only.** §15 records this; C2 is the reason, and it is
   the reason that survives an 11pm re-litigation.
4. Worth stating plainly: **`run` and `retry` already cross the soft line.** The
   agent can spend a build number and swap the public `.dmg` permalink today.
   Probe-only guards the hard line and nothing else.

### C3 — Mutable action tags inside the privileged jobs.

The pinning discipline is real but partial: third parties that touch secrets are
pinned; **`actions/*` are not.** Three jobs matter:

| Job | Permission | Unpinned action |
|---|---|---|
| `release.yml` `publish` | `id-token: write` (PyPI OIDC) | `actions/download-artifact@v4` |
| `release.yml` `github-release` | `contents: write` | `actions/checkout@v4` |
| tap `update-formula` | `contents: write` on the tap | `actions/checkout@v4` |

**The approval hold does not mitigate this.** It gates when the job *starts*; a
compromised action then runs *after* approval, holding the OIDC token. The
attacker's whole objective is to be inside that job at the moment the human
approves — and the human approves on schedule, every release.

`codeql.yml` additionally has **no top-level `permissions:` block**, so it
inherits the repository default rather than `contents: read`.

**Mitigations.** SHA-pin `actions/*` in those three jobs at minimum, with the
same inline-comment discipline the existing pins carry. Keep the
`pypa/gh-action-pypi-publish@release/v1` exception — it is PyPA's documented
guidance and the comment already explains why. Add `permissions: contents: read`
to `codeql.yml`. Enable Dependabot for `github-actions` so pins do not rot.

### C4 — The Homebrew tap is the softest distribution channel.

`update-formula.yml` holds `contents: write`, is driven by `repository_dispatch`,
and computes the formula by fetching the sdist URL **and its sha256 from PyPI**.

That sha256 is integrity-in-transit, not provenance: it is fetched from the same
place as the artefact, so it proves the download matches what PyPI served — and
nothing about whether what PyPI served is legitimate. Anyone who reaches PyPI
via C1 or C3 gets Homebrew for free, automatically, within minutes, and the tap
signs nothing.

`brew install` is also the channel with the *least* platform-level defence: no
notarisation, no Gatekeeper, no App Sandbox. It is a `pip install` in a trench
coat.

**Mitigation.** The provenance already exists and is not being checked — PEP 740
attestations are generated by the publish step. Have the tap workflow verify the
attestation (`gh attestation verify`, or PyPI's `/integrity` endpoint) before
writing the formula, and fail closed. This converts the tap from "trusts PyPI"
to "trusts a signature chained to this repository."

### C5 — The website: the phishing surface, and `CHANGELOG.md` as an injection path.

> **FIXED 23 Aug 2026** — website repo `4305119`, **not yet deployed**. Escaping
> happens at Markdown's raw-HTML stash, for externally-sourced pages only. Two
> layers were tried and rejected first, both instructive: escaping the *source*
> double-escapes code spans (`<code>use &lt;provider&gt;</code>` → a visible
> `&lt;provider&gt;`) and breaks autolinks; escaping at the stash *without*
> skipping the uicons/callouts preprocessors would eat the HTML those
> legitimately emit. Real changelog renders byte-identical; an 18-assertion
> guard asserts payloads inert at the element level, not by substring.

`bristlenose.app` serves the `.dmg`, and `/privacy.html` is the canonical URL
that **Apple, Microsoft Entra and Google Cloud all point at**. Its build renders
`CHANGELOG.md` live from this repo.

Two consequences. **First, `CHANGELOG.md` is a public-repo file that renders to
HTML on a domain three vendor consoles trust.** If that renderer passes raw HTML
through — common in Markdown pipelines unless explicitly disabled — a merged PR
touching the changelog is stored XSS on the domain that carries the privacy
policy and the download button. **Confirmed 23 Aug 2026 by running the site's own
`md_to_html()` against a changelog-shaped payload: raw HTML survives verbatim.**
`build.py:189` calls `markdown.Markdown(extensions=["tables","fenced_code",
"attr_list","sane_lists"])` — Python-Markdown 3.10.2, whose `safe_mode` was
removed at 3.0 — and no sanitiser (`bleach`, `nh3`) appears anywhere in the
repo. A `<script>` tag in `CHANGELOG.md` renders as a `<script>` tag on
`bristlenose.app`.

Blast radius is small and the fix is surgical: **exactly one page is sourced
from the public repo** (`build.py:46`, `src="CHANGELOG.md"`), and **no markdown
file in the site uses raw HTML** — only three hand-authored `content/*.html`
files do, and those bypass the renderer. So escaping raw HTML for
externally-sourced pages costs nothing and closes the boundary at the one place
it is crossed. Do that rather than sanitising everything: one trust boundary,
one control.

**Second, the `.dmg` permalink is a bare `mod_alias` redirect** with no published
checksum. The real defence is Gatekeeper — an attacker with the web host cannot
serve a `.dmg` that launches without a valid Developer ID signature and staple.
That defence is sound and worth naming as the reason this is MEDIUM not HIGH.
Still: publish the `.dmg` sha256 next to it, so the integrity claim does not rest
entirely on a control the user cannot see.

### C6 — This design's own new surface

Already covered in §6 and folded in: `.release/` unignored (A0),
`upload-dmg.sh`'s host+path on stdout, 0600 + `O_NOFOLLOW`, the allowlist on
what reaches the public release log, and the un-installed `pre-commit` hook that
`SECURITY.md:233` claims. Two additions from this review:

- **The fold never interpolates log content into a shell command**, and the
  driver never `eval`s. C2's rule, applied to the artefact this design adds.
- **`--allow-stale-gates` and any future bypass records an event.** A bypass
  nobody counts becomes the default, and a bypass an attacker can induce
  silently is worse.

### Priority

| | Chain | Reaches | Cost to attacker | Fix |
|---|---|---|---|---|
| 1 | **C1** dependency floor | signing Mac | low — one PyPI package | hash-pinned build env |
| 2 | **C3** mutable action tags | PyPI OIDC, repo, tap | low if a tag is ever repointed | SHA-pin three jobs |
| 3 | **C4** tap trusts PyPI's own hash | every `brew` user | free, follows C1/C3 | verify PEP 740 attestation |
| 4 | **C2** injection into the agent | signing Mac | moderate — needs a merged PR or a dep | never build commands from content |
| 5 | **C5** changelog → HTML | vendor-trusted domain | moderate | confirm the renderer escapes |

C1 and C3 are the two where a *single* external compromise reaches the signing
machine or the publishing right, and both are cheap to close. **They should be
done before Tier A**, because neither depends on any of it.


## 17 · Skill → script: what moves, what stays

The maintainer's question, answered as an audit rather than an assertion:
**everything `bn-release` knows that is mechanical should be in a script, and
this table says where each piece lands.** The test applied to each row is the
one `docs/design-bn-release-skill.md` already settled — *a precondition inside a
script is structurally unskippable; one in a skill is an instruction a model can
misread.*

### Already mechanical — no action

| Skill knowledge | Lives in |
|---|---|
| Version agreement across four files | `check-release-ready.sh` § Version consistency |
| CHANGELOG/README entry exists and is well-formed | § Prose |
| PyPI immutability · tag vs HEAD | § Not already released (tag→HEAD closed by audit §3.1) |
| Certs, profile expiry, ASC config, `.ship-local.conf` | § Mac channels |
| CI evidence for HEAD | § CI |
| `publish hold` still exists | § CI |
| `skip-worktree` divergence | added 22 Aug, found a second defect on first run |
| Every `check-*` precondition | inside the irreversible act it guards |

### Moving into a script — the gaps this review found

| | Skill knowledge, today | Why it must be mechanical |
|---|---|---|
| **A8** | *"Check nothing-to-ship first, because it is cheap and it is common"* + the exact `git diff --stat -- bristlenose/ frontend/` | Phase 1's cheapest test has **zero** coverage. It decides whether a release should happen at all, and it is a one-line diff. Prose at 11pm is the wrong place for it |
| **A9** | *"`SIGN_IDENTITY` is not optional. Unset it defaults to `-` and six gates go off, no warning, and you find out 35 minutes later at the upload"* | Measured true: `build-all.sh:37` defaults to `-`, and `:110`'s `if [ "$SIGN_IDENTITY" != "-" ]` skips the identity, profile and notary checks. **`build-dmg.sh` already refuses ad-hoc outright** — so this is sibling inconsistency, not a hard problem |
| **A10** | *"New CLI surface must reach `README.md`, `man/bristlenose.1` and the website's `docs-src/cli.md`"*, plus the roff-normalisation gotcha | The *judgement* (does this flag need documenting?) stays. The *parity* (a flag in `--help` absent from three surfaces) is a diff. The gotcha — `sed 's/\\-/-/g'` then strip `\fB` escapes, or every flag reads as missing — is a script detail, and cost a cycle on 31 Jul |
| **A6** | The seven-channel probe table · the two Snap probes · the expiry clocks · *"I can't probe this is itself a claim"* | Already A6. That last one is encoded by the table being exhaustive rather than by a reminder |
| **A2** | *"Capture the delivery UUID when `upload-testflight.sh` prints it — the one probe you cannot reconstruct later"* | A remembered value in a doc that preaches probe-don't-remember. `art` closes it |
| Tier B | Order · bump-commit-tag as one unit · tag **after** the commit · verify `tag == HEAD` · two pushes never `--tags` | The driver's `case`. Until Tier B, these stay prose — which is the honest cost of deferring it |
| Tier B | Consequence printed at the irreversible line (DUX rule 4) | Needs the driver |

### Staying in the skill — deliberately

These are the reason it is a skill at all, and none of them should migrate:

- **minor vs patch.** A month of refactoring can be invisible; one sentence in an
  LLM prompt re-judges every analysis. Never inferred from the diff.
- **Does the CHANGELOG entry describe what actually shipped?** Reading prose
  against a diff. *"Bug fixes"* over a feature-bearing range is the failure to
  catch, and no script can.
- **Does the website still describe the product?** Homepage rows drift and
  nothing trues them.
- **Tier 1 vs Tier 2.** An audience decision.
- **Drafting the prose** — CHANGELOG, `cli.md`, App Store What's New.
- **Triage under partial failure.** Shell reports per-channel truth well;
  deciding what to retry is judgement.
- **Phase 7 sections 3 and 4** — what went wrong, and what misled you. Sections
  2's *numbers* come from the fold if Tier B lands; the reading of them does not.

### The rule this audit produces

> **If the skill's prose contains an imperative with a testable subject, it is a
> missing gate.** *"`SIGN_IDENTITY` is not optional"*, *"check nothing-to-ship
> first"*, *"capture the UUID"* and *"never one `--tags`"* are all instructions
> to a reader about a condition a script could assert. Four of them, found by
> reading the skill against its own scripts — which is a pass worth repeating
> whenever the skill grows a new warning.


## 18 · Build report — what shipped, and what building it taught

**Built 23 Aug 2026**, commits `74527daf` (A0–A9) and `3dbb9dd0` (A10).
**All 11 Tier A items, plus the read-only half of Tier B.** 159 assertions green
across nine suites. `ruff check .` clean.

| | Item | Status |
|---|---|---|
| A0 | `.gitignore` `.release/` | ✅ verified with `git check-ignore` |
| A1 | `--progress` TTY-gated | ✅ |
| A2 | Per-attempt altool logs + UUID sidecar | ✅ |
| A3 | `publish state`, tri-state | ✅ |
| A4 | Dependency drift at preflight | ✅ **fired on the live tree immediately** |
| A6 | `verify-channels.sh` | ✅ 51 assertions |
| A7 | The `SKILL.md` rule | ✅ |
| A8 | `shippable diff` | ✅ 10 assertions |
| A9 | `SIGN_IDENTITY` required | ✅ exit 2 in 0s |
| A10 | Doc-surface parity | ✅ 18 assertions |
| A5 | Gate freshness | ✅ **built, but not as designed** — see below |

### A5 shipped without the ledger, and the ledger was the whole problem

The plan proposed `.release/gates.jsonl`, appended by each of thirteen gates and
compared against HEAD, so the preflight could tell whether a gate was stale. I
deferred it because it needed the `absent = stale` decision settled first and
meant touching every gate.

**Building it showed the ledger was unnecessary.** The source-only gates cost
~2s in total, so the honest answer to *"has this gate run against current
source?"* is to run it, in the preflight, now — which is the same principle D1
already applies to channels. **Probe, do not remember.**

That deletes the entire problem surface the deferral was about: no per-version
vs cross-version storage, no `absent = stale` rule, no stamp call retrofitted
into thirteen scripts, and no way for a stamp to disagree with reality. The
feature that was hardest to design turned out to be the one that shouldn't
exist.

**What made it affordable was measuring the thing nobody had measured.**
`check-window-surfaces` cost **23 seconds**, and its `SelectionSync` assertion
was grepping the whole `desktop/Bristlenose` tree — 2.4 GB, 7,596 files, mostly
build output and bundled models — to find zero matches. Scoped to the two source
directories: **23s → 0.07s**, on a gate that runs on every build. It was also
wrong in principle, because a stray match inside a build artefact would have
failed the gate on clean source.

Had that gate stayed at 23s, the ledger would have looked necessary and I would
have built it. **The plan's whole premise was an unmeasured cost.**

Four gates still need a built artefact or an argument
(`check-release-binary`, `check-mcpb`, `check-sidecar-appstore-strings`,
`check-sidecar-freshness`). They stay build-time and are **named in the code**
rather than silently omitted, so the omission is a decision.

### Six bugs found by building it — four of them in my own new code

The synthetic suites earned their keep on the first run, and what they caught is
more interesting than what they confirmed.

1. **A plain substring test made `0.28.10` satisfy `0.28.1`.** `verify-channels`
   would have reported a channel verified when it was not. Same family as
   `CLAUDE.md`'s `.badge-accept` / `.badge-accept-flash` note, and the same fix:
   match whole tokens. Both verdicts now check version boundaries.
2. **The anti-trivial-pass guard was itself passing trivially.**
   `grep -c . || echo 0` prints the count **and** exits non-zero when the count
   is zero, so the `||` arm appends a second line and the numeric test
   mis-evaluates. The guard written to stop a gate passing by seeing nothing was
   passing by seeing nothing.
3. **A test harness that could hide a real failure.** The deliberate-failure
   check ran inside `$( )` — a subshell — so its `FAIL++` was lost, and the
   harness decremented anyway. A suite with exactly one real failure would have
   reported zero and exited green.
4. **The doc gate enumerated 2 flags out of 25 and reported success.** Typer
   renders help inside Rich box-drawing, so the `^ +` anchor matched no command
   row and no subcommand was ever enumerated. It printed "2 flag(s) checked ·
   0 gaps" and exited 0.
5. **An injection test that appeared to prove the gate blind, and was itself
   wrong.** `--llm` appears in the man page **3× plain and 5× escaped**;
   removing only the escaped form left it findable. Worth recording because the
   instinct on a red injection test is to distrust the gate, and here the gate
   was right.

6. **A gate spending 23 seconds to assert nothing.** `check-window-surfaces`
   walked 2.4 GB of build output on every build, and a match inside an artefact
   would have failed it on clean source. Found only because A5's design turned
   on whether gates were cheap — a question the plan asserted the answer to
   without checking.

The shape the first five share: **every one is a check that reports success
while seeing nothing.** That is the same defect class as release-log 0.27.0 #1, arriving in
the code written to prevent it.

### Three design corrections found by running it, not by reasoning

- **A4 was graded `bad`, and is now `warn`.** `build-all.sh` step 2b already
  hard-fails on the identical condition, so a release physically cannot ship a
  stale inventory. A duplicate gate adds only a false-positive path — the tool's
  own output warns that per-platform venv differences flag drift that isn't real
  off the canonical runner. **Warn early, refuse late.**
- **A5 needed no ledger.** See above — the plan's central mechanism for this
  item was answering a question that measurement dissolved.
- **A10's first cut printed 16 warnings on a clean tree, forever.** Treating
  README, the man page and `cli.md` as peers is wrong: the man page is the
  complete reference, the other two are curated. Scoping them to flags new since
  the tag takes a permanent 16 down to 0.

### One fail-open found while depending on it

`build-all.sh`'s supply-chain gate skipped **entirely** when `pip-licenses` was
absent, so a signed build from a venv missing the `[release]` extra lost its only
inventory check silently. Found because A4's downgrade rested on that gate
existing — and verifying the thing you are about to depend on is how you find
that it does not. Now: skip on an ad-hoc build, **fail on a real identity**.

### Live findings on the current tree

- `dependency drift` — fired immediately on a stale inventory. The drift turned
  out to be **eight rows of `pre-commit`'s dependency tree**, installed ad-hoc
  earlier the same day. Regenerating would have been wrong: the file lists what
  ships in the sidecar, for procurement, and none of it ships. Fixed at source
  instead — `pre-commit` declared in `[dev]` (it was declared nowhere, which is
  why `SECURITY.md:233`'s claim was false) and its transitive tail added to
  `NEVER_SHIPPED`. Inventory back to byte-identical. **A gate that fires on a
  real change, whose correct resolution is not the obvious one.**
- `shippable diff` — correctly read the fortnight as *desktop-only, a rebuild
  not a release* before the concurrent session's frontend work landed.


## 19 · Tier B, read-only — shipped 23 Aug 2026

`scripts/release.sh` — **seven verbs**: `plan` · `run` · `retry` · `recover` ·
`status` · `verify` · `abandon`.

> **Corrected 3 Sep 2026.** This paragraph said *"**No `run`,** and that is the
> decision rather than an omission"*, and that `run` refuses and points at
> `/bn-release`. It ships: `cmd_run` is ~570 lines and drives the whole chain.
> The claim was contradicted by this doc's own §9 and by §19's later subsection,
> so the file argued with itself — and the read-only framing is the one a cold
> reader meets first. The original sentence is preserved here because the
> *reasoning* (gate the driver on evidence that has not arrived) is what §12
> still turns on; only the verdict moved.

**What it does own is the step table**, which until now was prose in
`SKILL.md` Phase 5 — retyped by a model every release, with estimates nobody had
measured. Both now live once, with the numbers from `release-log.md`'s 0.27.0
entry, and the skill defers to it rather than carrying a second copy (§6.4's
knowledge quadruplication, avoided rather than described).

The consequence of each irreversible step prints **immediately before that
step**. The first draft marked them in `plan`, where nothing happens, and dropped
them from the run, where the act occurs.

`abandon` exists because §10 named its absence. The 0.27.0 log's own conclusion
is that abandoning a tag must treat the website deploy as part of the decision;
that is now printed with the recipe rather than remembered.

**Exit codes are a vocabulary**: `0` ready · `1` not ready · `2` usage · `75`
`EX_TEMPFAIL` for held. Held is not an error — a release waiting on a person is
behaving correctly — but it must be distinguishable from `0`, or
`release.sh … && deploy-website` fires on a release that has published nothing.

### The step table's structural invariants are pinned

Because a table that says a step is irreversible without saying what it costs
lies at the exact moment someone is reading it to decide:

- exactly three irreversible steps, each naming its cost
- no reversible step claiming one
- the CI gate preceding all three — **moving it after is the 0.25.2 shape**
- the HARD line last
- step-id majors contiguous, sub-steps (`4a`, `13a`) allowed per REPORT-STYLE rule 3

Proven to fail on injection.

### Three bugs found building it, two of them mine

1. `status` called `rollup_exit` twice, leaking a bare `0` into the report.
2. The total counted the **Tier 2-only** Snap stable push into a Tier 1
   estimate, inflating it by ten minutes. There is now a tier column.
3. My own contiguity invariant rejected sub-step ids and flagged a *correct*
   table — the gate-that-cries-wolf shape, in a gate written the same hour.

### And the dependency row learned to say something

`generate-third-party-binaries.py --check` answers *"is the file stale?"*, which
is the answer that helps nobody decide anything at 10pm.
`scripts/check-dep-drift.py` names the packages and makes a **major** a hard
stop. Deliberately **not** an upper bound on `openai`: re-reading release-log #5,
the complaint is the discovery *moment*, not the bump, and capping contradicts
the written floor-only policy. The discovery moved; the floor did not.

Its tests found a real gap — versions numerically equal but textually different
(`1.2.3` vs `1.2.3.post1`, rc, dev) collapsed to `same`, silently dropping a
change the tool had seen. One of the two failures was the *test* asserting
`patch` for two identical strings; corrected rather than papered over.


### The CLI learned its defaults from being used (28 Aug 2026)

The 0.28.0 run was the first driven end to end, and the interface tax showed
immediately: `verify` demanded a version whose answer sat in the tree beside
it, and `run` demanded the version *and* the bump kind — one fact spelled two
ways, both times. Relaxed the day after the release, in `a81c5db7` and
`82e67268`:

- **Either spelling suffices.** `run 0.29.0` infers the kind, `run --bump
  patch` infers the version — always from the **last tag**, never the tree,
  which is mid-bump exactly when it matters (the double-bump incident's root).
  Given both, they cross-check: one clean step of the wrong kind dies as a
  typo; a multi-step leap warns and proceeds, both halves being explicit.
- **A resume needs neither.** The run dir's first ledger line records
  `bump=<kind>`; a resume reads it back and refuses a contradicting flag.
- **Bare `run` proposes the next minor** (the house bias — the 0.15.x line is
  what a patch habit looks like) and moves the consent from the flag to the
  prompt: for a **fully inferred** version the typed confirmation is
  mandatory, `--yes` cannot skip typing a version that was never given, and
  headless the read hits EOF and dies having created nothing. With a version
  or `--bump` given, `--yes` keeps its meaning — automation and resumes are
  untouched.
- **Bare `verify` probes the tree's version**, marked `· the tree's version`
  in the header. `retry <step>`, `abandon` and `recover` find the sole run
  under `.release/`, narrated.

Every inference prints what it chose — a silent default is a trap, a narrated
one is a colleague. The pure pair `next_version` / `bump_kind` carries the
translation and is unit-pinned both ways.

The change found one bug, in its own tests: the old assertion drove bare
`run` expecting an instant usage-refusal; under the new contract it prompts,
and with stdin left open that `read` blocked and hung the suite. The
rewritten pin runs in the sandbox with stdin closed and asserts the declined
run leaves nothing — the harness lesson being that any test invoking an
interactive path must close stdin or it is a hang waiting for its contract to
change.


## 20 · If this ever leaves this repo — notes for a future adopter

Written 24 Aug 2026, deliberately as notes rather than work. Nothing here is
scheduled; it exists so the next person (probably me) does not have to
re-derive it. The order below is roughly the order it would matter in.

### What is actually reusable

Not the scripts. The **shape**, which is three layers and holds for any project
that ships to more than one place:

- a **conveyor** that owns order and state and is deliberately dumb,
- **gates** that can only ever say *no*,
- a small number of **named, located human verdicts** — and the human decision
  is a verdict, not work.

Two doctrines under it carry more weight than any code here:

1. **State someone else owns, you probe. State you own, you record.** An
   append-only log *records*; a state file *asserts*. Fold, never store.
2. **A successful probe wins; an unsuccessful probe wins over nothing.**
   `unreachable` is not `absent`, and collapsing them is how a network fault
   comes to read as a human decision. §5 and §7 are the long form.

The third thing worth carrying is the defect class the whole body of work is
organised against: **a check that reports success while seeing nothing.** It
appeared eleven times during this build, several of them in code written that
same hour to prevent it, and twice in tests written to enforce the rule. Assume
it will happen to you too, and prefer gates that are *proven to fail on the
thing they exist to catch* over gates that merely pass on a clean tree.

### How far the extraction actually got

`scripts/` is identity-free in code — measured 24 Aug 2026, one occurrence of
the org name remains and it is inside a comment. Everything project-specific
lives in `scripts/project.conf`, and `test-release-sh.sh` fails if any constant
there loses its last consumer, so it cannot quietly rot back.

`CHANNELS` is the abstraction that earns its keep. Which channels a project
ships on is the whole difference between a CLI (`pypi homebrew snap`), a Mac app
(`testflight dmg`) and a hybrid that is both; `verify-channels.sh` iterates it
and a channel with no `probe_<name>` is a hard error rather than a silent pass.
A second project is a copy of that conf plus its probes.

**`desktop/scripts/` is not extracted and would be the real work**: 164
occurrences of the product name across 25 files, plus 12 bundle-id/domain
literals. That is the macOS build/sign/notarise/upload half, and it is where a
second Mac app would spend its time. Nothing about it is hard; it is just not
done, and it should not be attempted speculatively — the Rule of Three has been
met exactly once.

### Portability, as measured rather than assumed

Run 24 Aug 2026 on `ubuntu:24.04` (aarch64, bash 5.2, `/bin/sh` → dash), repo
cloned inside the container:

- **The macOS-only surface is exactly four things**, all inside the
  `SCOPE != cli` block of `check-release-ready.sh`: `security find-identity` /
  `security cms`, `/usr/libexec/PlistBuddy`, `date -j -f` (BSD-only; GNU has no
  `-j`) and `stat -f%Lp` (GNU is `-c%a`). So `--cli` is already the portable
  entry point — that is the design working, but nothing states it and nothing
  detects the OS.
- **Everything else ran identically.** The five source gates pass;
  `verify-channels.sh` exits 1 correctly with `gh` absent reported `unreachable`
  rather than a false pass; `pkill -P` / `pgrep -f` behave the same; `sed
  's/\x1b\[…//'` works under both seds; dash does not bite because every test
  stub body is POSIX. No GNU-only construct anywhere in the chain.
- **The failures were environmental, not portability.** Four assertions fail on
  a box with no `user.email` configured, because the sandboxes do `git init &&
  git commit --allow-empty`. They clear the moment an identity exists. The
  danger is *which* ones fail: the regression pins for the CI-sha fix, so a
  clean runner reports a false regression rather than a missing git config.

### The one thing that would most change the odds

**Run the suites in CI, on ubuntu.** — **done 28 Aug 2026 (`1c8fd3ee`), and it
paid on the first run.** The note below is preserved as written; what follows is
what happened.

> As of this note, 325 assertions across eight suites execute on exactly one
> machine, one OS, one shell and one git configuration. Two release scripts
> already run on Linux in CI with no suite behind them. The suites need no
> network, no keys and no release; the marginal cost is seconds, and every
> portability finding above took one `docker run` to surface and would never
> have surfaced otherwise.

The first Linux run was **red, with 33 failures, and both causes were real
defects in our own scripts** — neither observable on macOS:

- **Git identity (31 of 33).** Git guesses an identity from the hostname when
  none is configured; on a GitHub runner that guess yields `fatal: empty ident
  name`, so every manufactured sandbox's commit failed. The cascade is the
  instructive part: with no commit, `git rev-parse HEAD` on an unborn branch
  prints the literal `HEAD`, which then equalled the `HEAD` a test had written
  into `ci-sha`, so `verdict_tag_provenance` compared two sentinels, found them
  equal, and returned `dirty` — a verdict about nothing. Fixed in the *suites*,
  which manufacture the repos and must therefore configure them; that makes them
  portable to anyone's clean machine, not only to a runner we remembered to set up.
- **ANSI (the other 2).** Actions sets `FORCE_COLOR`, so Rich colours
  `bristlenose --help` off a tty. Each command row arrives as
  `ESC[2m│ESC[0m ESC[1;36mrun`, and stripping the box character leaves the
  *escape* at line start, so `check-doc-surfaces.sh`'s `^ +` anchor matched
  nothing. `NO_COLOR` does not help — `FORCE_COLOR` wins in Rich's precedence.

Worth recording that the second was red rather than silently green **only**
because of the gate's own "enumerated only N subcommands — refusing" guard,
written after an earlier draft reported 2 flags on a CLI with thirty. It fired
correctly on a platform nobody had run it on.

The prerequisite this section named — the suites' dependence on ambient git
identity — was **also real, and I mis-cleared it before starting.** Running
locally with `HOME` scrubbed and both git configs nulled passed all 385
assertions, which I read as the blocker being gone. macOS supplies a valid full
name from the passwd record, so the guess succeeds locally and fails on a
runner: the simulation could not reproduce it, and the note's estimate of *four*
failing assertions was itself low by a factor of eight. **A local simulation of
a foreign environment is evidence about the simulation.**

### Known gaps

Findings 43–59 in the maintainer's review notes, kept outside the public tree,
are the live list with severities, reproductions and file:line. In brief, and
none of them scheduled: `abandon` leaves the abandoned attempt's events armed
so a re-cut skips the rebuild; `plan --tier 2` prints a run command that cannot
execute tier 2; `_stop_step` kills one process generation so a deep step tree
orphans its payload; three probes conflate absent with unreachable; the tap
workflow copy has diverged from the tap repo again; and `verify-channels.sh`
still has no driver-level coverage for its remaining rows.

Do not treat that list as a backlog. It is a record of what was known and
deliberately not done, which is the more useful thing to hand forward.

## See also

- `docs/design-bn-release-skill.md` — D1 refined here (§7); its `scripts/release-cli.sh` slot is what Tier B would fill
- `docs/design-release-system-audit.md` — §3 the fail-open cluster, §6.3 this finding independently derived
- `docs/release-log.md` — the evidence
- `desktop/scripts/REPORT-STYLE.md` — the presentation protocol, staying presentation
- `bristlenose/events.py`, `bristlenose/run_lifecycle.py` — the same pattern, for user runs
