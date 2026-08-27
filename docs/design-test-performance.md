# Test performance — the CI critical path is 5× longer than it needs to be

**Status:** measured, **not yet applied**. The one prerequisite fix has landed; the three CI changes have not.
**Measured:** 2026-08-26, local M-series (12 core) + CI run `32602750413` (last green before the measurement).

Sibling to [`design-ci.md`](design-ci.md) (workflow structure) and [`design-test-philosophy.md`](design-test-philosophy.md) (what to test, not how fast).

## The finding in one line

CI spends **~32 minutes** on a Python matrix that, with three cheap changes, should take **~5–6**. Two of the three are one-line edits to `ci.yml`; the third needed a real bug fixed first, which is now done.

## Where the time actually goes

From the last green run before measuring (`32602750413`), job-level:

| Job | Duration |
|---|---|
| `frontend-lint-type-test` | 1 m 40 s |
| `test (3.13, ubuntu)` | 14 m 41 s |
| `test (3.12, ubuntu)` | 18 m 01 s |
| `test (3.11, ubuntu)` | 26 m 31 s |
| **`test (3.10, ubuntu)`** | **32 m 11 s** ← critical path |
| `e2e` | 3 m 29 s |
| **Whole run** | **37 m 22 s** |

Step-level on the slowest and fastest cells shows install is *not* the problem — it's 44 s on both. It's all in `Run tests`: **31 m 13 s** on 3.10 against **13 m 40 s** on 3.13.

`e2e` declares `needs: [test, frontend-lint-type-test]`, so it waits on the slowest cell. The frontend job finished at 22:34:46 and e2e started at 23:06:57 — **32 minutes idle.**

## Lever 1 — coverage is paid 8 times and used once

`ci.yml`'s test step runs:

```
pytest --tb=short -q -m "not slow" --cov --cov-report=term-missing --cov-report=xml:coverage.xml
```

on all **8** matrix cells. The upload step immediately below is gated:

```yaml
if: always() && matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'
```

So seven cells pay the full tracing cost and discard the result. Measured on a 249-test subset (`test_serve_data_api` + `test_serve_codebook_api` + `test_curation_roundtrip` + `test_mcp_server`):

| Config | Time | Overhead |
|---|---|---|
| No coverage | 104.6 s | baseline |
| `--cov` (default C tracer) | 174.9 s | **+67 %** |
| `--cov` + `COVERAGE_CORE=sysmon` | 104.0 s | **~0 %** |

**This also explains the matrix gradient**, which looks like an interpreter-speed story and isn't. Coverage's C tracer costs more on older interpreters, and PEP 669 `sys.monitoring` — which makes tracing essentially free — only exists on 3.12+. A real CPython 3.10→3.13 speedup is ~1.3–1.5×; the observed 2.3× is mostly the tracer.

## Lever 2 — `COVERAGE_CORE=sysmon`

One environment variable on the single cell that keeps coverage. Free tracing on 3.12+.

**Precondition, already satisfied:** sysmon's restriction is around branch coverage. `[tool.coverage.run]` in `pyproject.toml` sets `source` and `omit` only — there is no `branch = true` — so this is the unrestricted case. **If branch coverage is ever turned on, re-measure before assuming sysmon still applies.**

## Lever 3 — pytest-xdist

The suite is CPU-bound and *diffuse*: 4162 tests in 444.94 s serially, with the slowest 25 durations summing to only ~40 s. There is no hot spot to optimise; `user + sys ≈ real`, i.e. one core saturated. That is the ideal shape for process-level parallelism.

| Config | Time | Speedup |
|---|---|---|
| Serial, no coverage | 444.9 s | baseline |
| `-n 4` (models a 4-core CI runner) | 125.3 s | **3.55×** |
| `-n auto` (12 core local) | 66.3 s | **6.7×** |
| `-n 4` + `--cov` + `COVERAGE_CORE=sysmon` | 127.4 s | coverage free |

Result counts are **identical** to the serial run — 4162 passed, 5 skipped, 22 xfailed — with no fixture, port, or SQLite collisions. The FastAPI/SQLite fixtures are already parallel-safe.

## The prerequisite bug (fixed)

`-n 4` initially aborted with:

```
Different tests were collected between gw2 and gw0
```

`tests/test_format_ingest_coverage.py` parametrised `test_classify_routes_every_advertised_extension` over five **sets** (`AUDIO_EXTENSIONS`, `VIDEO_EXTENSIONS`, `SUBTITLE_SRT_EXTENSIONS`, `SUBTITLE_VTT_EXTENSIONS`, `DOCX_EXTENSIONS`). Set iteration order depends on `PYTHONHASHSEED`, which differs per worker process, so each worker collected a different test order and xdist refused to run.

Fixed by wrapping each in `sorted()` — the pattern the same file already used at lines 101–102 for `_AUDIO` / `_VIDEO`.

**This is a latent bug independent of xdist:** test IDs were unstable run-to-run, which makes any per-test-ID reference (a rerun incantation, a flake report, a CI annotation) unreliable. Worth keeping whether or not the parallel work is ever picked up.

**General rule:** parametrising over a `set` is never right. Sort it at the parametrise site.

## The three changes, not yet applied

1. **Scope coverage to one cell.** Make `--cov …` conditional on `matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'` — matching the upload gate directly below it, which is the condition that already exists and is already correct.
2. **`COVERAGE_CORE=sysmon`** in the env of that cell.
3. **`pytest-xdist>=3.8`** in the `dev` extra of `pyproject.toml`, and `-n auto` on the test command.

Optional, structural: `e2e`'s `needs: [test, …]` waits on the slowest cell. Once the cells are ~5 minutes this stops mattering, but it is why the frontend job idles for 32 minutes today.

## Projected

Critical-path cell (3.10 ubuntu, 31 m 13 s in `Run tests`): ÷1.67 from dropping unused coverage → ~18 m 40 s; ÷3.5 from `-n 4` → **~5–6 min**. Whole CI run **37 m 22 s → ~10–12 min**.

## Not verified — do these before trusting it

- **Coverage percentage parity** between xdist and serial. pytest-cov combines worker data automatically and the XML was written correctly, but the *number* was not diffed against a serial baseline. Low stakes today: `[tool.coverage.report]` has no `fail_under`, so coverage is informational, not a gate. If it ever becomes a gate, verify first.
- **macOS runner core count** differs from the 4 modelled here, so those cells will scale differently.
- **`-n auto` on CI** picks up the runner's core count; on small cells xdist's per-worker startup could exceed the saving. Measure per cell rather than assuming.
- **`pytest-xdist` is not currently installed** — it was installed to take these measurements and then removed, so `.venv` matches `pip install -e '.[dev,serve]'`. Reinstate with the `pyproject.toml` change above, not by hand (an undeclared package in `.venv` is exactly the silent drift that cost the 4 Aug 2026 presidio incident).

## Reproduce

```sh
.venv/bin/pip install pytest-xdist
# baseline
.venv/bin/python -m pytest -q -m "not slow" --durations=25
# parallel
.venv/bin/python -m pytest -q -m "not slow" -n 4
# coverage tax, three ways (subset)
.venv/bin/python -m pytest tests/test_serve_data_api.py tests/test_mcp_server.py -q
.venv/bin/python -m pytest tests/test_serve_data_api.py tests/test_mcp_server.py -q --cov --cov-report=
COVERAGE_CORE=sysmon .venv/bin/python -m pytest tests/test_serve_data_api.py tests/test_mcp_server.py -q --cov --cov-report=
```

Note the shell trap: pytest file lists must be **literal** in zsh. `SUB="a.py b.py"; pytest $SUB` passes one argument, pytest errors instantly on a nonexistent path, and a `| tail -3` hides the summary line — so it reads as a suspiciously fast pass. Cost a cycle during this measurement; it is the documented zsh no-word-splitting gotcha in `CLAUDE.md` wearing a new hat.
