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
| [`bump-version.py`](bump-version.py) | Writes and **stages** the version files. Deliberately does not commit and does not tag — the tag belongs on a commit that does not exist yet. |

## Gates

Each answers one question, deterministically, and is wired into the preflight or
CI. Each has a suite below that proves it fires.

| | |
|---|---|
| [`check-doc-surfaces.sh`](check-doc-surfaces.sh) | Every CLI flag reaches all three doc surfaces (README, man page, website CLI page). Unescapes roff before comparing — the naive grep reports present flags as missing. |
| [`check-dep-drift.py`](check-dep-drift.py) | Names the packages whose resolved version drifted from the inventory; a major is a hard stop. Names them, rather than answering yes/no, because "is the inventory stale?" is not the answer that helps at 10pm. |
| [`check-tracked-vs-gitignore.sh`](check-tracked-vs-gitignore.sh) | Fails if a **tracked** file matches a `.gitignore` rule — committed before its rule existed, therefore silently public while looking ignored. |
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
```

> **Use `.venv/bin/python`, not `python3`, for anything that inspects installed
> packages.** `check-dep-drift.py` under the system interpreter reports 110
> packages "absent" and four bogus MAJOR drifts — the system `certifi` read as
> our `certifi`. It does not error; it answers confidently about the wrong
> environment, and `test-dep-drift.py` then fails its own restore assertion.
> Same trap, one layer out, as everything in Part 2's closing section.

| | |
|---|---|
| [`test-lib.sh`](test-lib.sh) | The shared harness — `ok/bad/head_/eq/finish`, `meta_check` (proves `eq` can fail), `guard_tracked` (restores tracked files on **any** exit path, signals included). |
| [`test-release-sh.sh`](test-release-sh.sh) | The driver's decisions and the step table's shape, driven with synthetic input via `RELEASE_LIB=1`. |
| [`test-release-e2e.sh`](test-release-e2e.sh) | The **real** `run` loop end to end against a fake step table (`RELEASE_STEPS_FILE`). Found two bugs no pure-function test could reach. |
| [`test-verify-channels.sh`](test-verify-channels.sh) | Every probe verdict and rollup, including the ones that must not read as pass. |
| [`test-preflight-substance.sh`](test-preflight-substance.sh) · [`test-preflight-gates.sh`](test-preflight-gates.sh) | The preflight's substance verdicts; and a replay of the 0.27.0 build failure where a rename made a gate's assertion unsatisfiable. |
| [`test-doc-surfaces.sh`](test-doc-surfaces.sh) · [`test-dep-drift.py`](test-dep-drift.py) · [`test-tap-provenance.py`](test-tap-provenance.py) | Their namesake gates, same pattern. |
| [`test-check-ratchet.py`](test-check-ratchet.py) | The ratchet's **write** path, which `ratchet-tighten.yml` now runs unattended. Points `CEILINGS`/`METRICS` at temp objects rather than mutating a tracked file, so it needs no restore and never runs mypy. Proven red against the pre-fix script. |

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
