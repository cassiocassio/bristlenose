# scripts

Repo-level scripts: **release**, **gates**, **the suites that prove the gates**,
and a tail of performance, fixture and board tooling. The macOS build half lives
in [`desktop/scripts/`](../desktop/scripts/) and has its own
[README](../desktop/scripts/README.md).

The *rules* — how these scripts are shaped, why probes are tri-state, what each
exit code means, where constants live — are Part 2 of
[`desktop/scripts/REPORT-STYLE.md`](../desktop/scripts/REPORT-STYLE.md). This
file is the index: what to type, and when.

**Thinking of lifting this into another project?** `docs/design-release-machine.md`
§20 is the honest account: what is actually reusable (the shape and two
doctrines, not the scripts), how far the identity extraction got, what is
measured to work on Linux and what is macOS-only, and what was knowingly left
undone. Read it before assuming any of this is general.

Every script resolves its own paths (via `$0`), so invoke it from anywhere.

---

## Ship a release

```bash
./scripts/release.sh plan     # what would happen — bare = the next minor, narrated
./scripts/release.sh run      # do it — bare = the next minor; typing the version is the consent
./scripts/release.sh verify   # is it actually live on every channel? bare = the tree's version
./scripts/release.sh status   # fold the event log for the current run
```

The version and the bump kind are one fact spelled two ways, so either alone
suffices — `run 0.29.0` infers the minor, `run --bump patch` infers the version,
both from the **last tag**, never the tree (which is mid-bump exactly when it
matters). Given both, they cross-check: one clean step of the wrong kind is
refused as a typo. A resume needs neither — the run dir's first ledger line
remembers its own bump, and a contradicting flag is refused. Every inference is
narrated, and for a **fully inferred** version the confirmation prompt is
mandatory: `--yes` cannot skip typing a version that was never given (headless,
the read hits EOF and dies having done nothing). `retry <step>`, `abandon` and
`recover` likewise find the sole run under `.release/` when no version is
given.

| | |
|---|---|
| [`release.sh`](release.sh) | The conductor's page, executable. `plan · run · verify · status · abandon · retry · recover`, all with inferred defaults (above). **The tag is the release** — `run` puts it last, after the soft uploads, takes its strict verdict from a `workflow_dispatch` of CI on `main`, and refuses to tag any HEAD the recorded verdict does not name. |
| [`check-release-ready.sh`](check-release-ready.sh) | Preflight. The mechanical half of the release skill: a precondition inside a script is structurally unskippable, one in a skill is an instruction a model can misread. `run` calls it as step 1; run it alone any time. |
| [`verify-channels.sh`](verify-channels.sh) | Is a version live on all seven channels? No version = the tree's. Iterates `CHANNELS` from `project.conf`, one tri-state probe each — including TestFlight, asked directly via `upload-testflight.sh --probe` when the ASC key is present. |
| [`project.conf`](project.conf) | Every project-specific literal — name, repo, tap, site, version file, derived URLs, workflow names, and the channel set. Sourced by the three above. Change identity here, never in a script. |
| [`release-board.py`](release-board.py) | **Watching it.** Draws `.release/<v>/board.html` — the Tube map of a release: the line of stations from the run's own `steps.tbl`, the ledger folded with `release.sh`'s rules, the sink's build steps / checks / gates / preflight rows / channel verdicts / clocks / CI, liveness from the lock's pid. No network, no time axis, no data is a third state, and a **confounded-expectations log** counts everything the feed said that the board has no rule for. `--serve` runs it live on loopback behind a per-run token (in the 0600 handshake) — the page patches pane by pane as the run dir changes, running stations pulse only while the heartbeat is fresh, and the server exits itself after four idle hours. `release.sh run --board` starts one detached if none is serving and prints the link; without the flag it prints the link only if it finds one (it never needs the board). `--replay` writes a scrubber over the real generator at every ledger line. `--with-logs` writes a separately named file that carries raw log tails and says not to attach it; the live view carries them too, and never leaves the machine. Design: `docs/design-release-board.md` §8. |
| [`bump-version.py`](bump-version.py) | Writes and **stages** the version files. Deliberately does not commit and does not tag — the tag belongs on a commit that does not exist yet. |

## Gates

Each answers one question, deterministically, and is wired into the preflight or
CI. Each has a suite below that proves it fires.

| | |
|---|---|
| [`check-doc-surfaces.sh`](check-doc-surfaces.sh) | Every CLI flag reaches all three doc surfaces (README, man page, website CLI page). Unescapes roff before comparing — the naive grep reports present flags as missing. |
| [`check-dep-drift.py`](check-dep-drift.py) | Names the packages whose resolved version drifted from the inventory; a major is a hard stop. Names them, rather than answering yes/no, because "is the inventory stale?" is not the answer that helps at 10pm. |
| [`check-providers-live.py`](check-providers-live.py) | One real call per **shipped** (provider, model) — derived from the registry and the macOS picker, so it cannot drift from what ships. Three questions per model: is the key alive, does the model still exist, does our request shape validate. The mocked suite cannot ask any of them, and the app's "Online" light validates only the key. Needs keys; pence per run; a release gate via `check-release-ready.sh`. |
| [`check-tracked-vs-gitignore.sh`](check-tracked-vs-gitignore.sh) | Fails if a **tracked** file matches a `.gitignore` rule — committed before its rule existed, therefore silently public while looking ignored. |
| [`git-hooks/pre-push`](git-hooks/pre-push) | Refuses to push any ref whose **tree** carries a path the current `.gitignore` marks private — the pre-scrub branch or tag that `check-tracked-vs-gitignore.sh` cannot see, because that one reads the index. A native git hook reading **every** ref, deliberately not a pre-commit stage (whose handler returns on the first). Install: one symlink, see its header. |
| [`check-locales.py`](check-locales.py) | Locale completeness and placeholder parity, honouring the runtime fallback chain and CLDR plural suffixes. Warnings by default; `--strict` to gate. |

## Prove the gates

> A gate that reports 0 problems on a clean tree is either correct or blind, and
> the two look identical from outside.

Every suite injects the defect its gate exists to catch, asserts the red, and
restores. They need no network, no keys and no release.

```bash
for t in scripts/test-*.sh; do
  [ "$t" = scripts/test-lib.sh ] && continue      # the harness, not a suite
  bash "$t" || break
done
.venv/bin/python scripts/test-dep-drift.py
.venv/bin/python scripts/test-tap-provenance.py
.venv/bin/python scripts/test-release-board.py
```

> **The inventory scripts read `.venv-sidecar`, not the interpreter that runs
> them.** Since 5 Sep 2026 `check-dep-drift.py` and
> `generate-third-party-binaries.py` take `--python` (default
> `.venv-sidecar/bin/python`, the venv the bundle is built from), so the
> launching interpreter no longer decides the answer. The trap moved rather
> than vanished: a `--python` that is a symlink to the venv's python from
> *outside* its `bin/` lands on the base interpreter, and a half-built sidecar
> venv is a real interpreter with a wrong site-packages — both answer
> confidently about the wrong environment. The tool itself (`pip-licenses`)
> still comes from `.venv`'s `[release]` extra.

| | |
|---|---|
| [`test-lib.sh`](test-lib.sh) | The shared harness — `ok/bad/head_/eq/finish`, `meta_check` (proves `eq` can fail), `guard_tracked` (restores tracked files on **any** exit path, signals included). |
| [`test-release-sh.sh`](test-release-sh.sh) | The driver's decisions and the step table's shape, driven with synthetic input via `RELEASE_LIB=1`. |
| [`test-release-e2e.sh`](test-release-e2e.sh) | The **real** `run` loop end to end against a fake step table (`RELEASE_STEPS_FILE`). Found two bugs no pure-function test could reach. |
| [`test-verify-channels.sh`](test-verify-channels.sh) | Every probe verdict and rollup, including the ones that must not read as pass. |
| [`test-preflight-substance.sh`](test-preflight-substance.sh) · [`test-preflight-gates.sh`](test-preflight-gates.sh) | The preflight's substance verdicts; and a replay of the 0.27.0 build failure where a rename made a gate's assertion unsatisfiable. |
| [`test-doc-surfaces.sh`](test-doc-surfaces.sh) · [`test-dep-drift.py`](test-dep-drift.py) · [`test-tap-provenance.py`](test-tap-provenance.py) | Their namesake gates, same pattern. |
| [`test-check-ratchet.py`](test-check-ratchet.py) | The ratchet's **write** path — `--tighten`, which `ratchet-tighten.yml` runs unattended, and `--adopt`, which installs a CI measurement here. Points `CEILINGS`/`METRICS` at temp objects rather than mutating a tracked file, so it needs no restore and never runs mypy. Proven red against the pre-fix script. |
| [`test-sink.sh`](test-sink.sh) | The event sink (`desktop/scripts/sink.sh` + the tee in `report.sh`): the round-trips `printf %q` used to break (newline + apostrophe, tab, non-ASCII under `LC_ALL=C`), the no-ops (no sink, unwritable, relative), ownership in renderer and plain mode with a nested child, the partial-line rule, and a grep for bash-4 constructs, since a `/bin/bash` 3.2 build phase sources it. |
| [`test-release-board.py`](test-release-board.py) | The board's fold against dead and live pids, the no-data table pane by pane, partial verifies, the dmg clock's parity with `AlphaBuild.swift`, merge order, the CI matrix, a confounded fixture with one of each section, the escaping and canary rules, and the real 0.28.0 ledger as a committed fixture. |
| [`test-pre-push.sh`](test-pre-push.sh) | The pre-push guard, driven with fabricated ref lines against a leaky commit built from plumbing — no index or working-tree mutation. The case that matters is the offender **second** in a multi-ref push, the one pre-commit's stage cannot fail. |

## Performance

| | |
|---|---|
| [`perf-stress.sh`](perf-stress.sh) | Generate a synthetic fixture, nuke the cache, serve it, measure. Refuses to run against an occupied port — the stale-server trap that once produced 353 quotes instead of 4. |
| [`perf-history.sh`](perf-history.sh) | Table of results from `e2e/.perf-history.jsonl`. |
| [`perf-breakdown.py`](perf-breakdown.py) | Per-stage wall-time and LLM-time for one completed run. |
| [`compare-runs.py`](compare-runs.py) · [`compare-render.sh`](compare-render.sh) | Diff two pipeline runs; diff a render against its baseline. |

## Fixtures, corpora and generated assets

[`generate-stress-fixture.py`](generate-stress-fixture.py) ·
[`stress-tag-fixture.py`](stress-tag-fixture.py) ·
[`download-fossda.sh`](download-fossda.sh) ·
[`scrape-apple-corpus.py`](scrape-apple-corpus.py) ·
[`seed-zh-hant-hk.py`](seed-zh-hant-hk.py) ·
[`generate-app-icons.py`](generate-app-icons.py) ·
[`generate-third-party-binaries.py`](generate-third-party-binaries.py)

## Acceptance

[`acceptance/`](acceptance/) — `run_matrix.py` drives the acceptance matrix,
`invariants.py` holds the assertions that no unit test can make (notably
`assert_sessions_accounted`, the one place where per-bucket conservation is not
a tautology). Hub: [`docs/testing/README.md`](../docs/testing/README.md).

## Delivery board

`sync-*.py` and [`populate-gh-project.py`](populate-gh-project.py) sync the
maintainer's planning notes — kept outside the public tree — to the GitHub
project board. Parser gotchas are in the root [`CLAUDE.md`](../CLAUDE.md).
