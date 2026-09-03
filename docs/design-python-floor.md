# The Python 3.10 floor — evidence and decision

*Grounded 3 September 2026. Read-only pass: nothing bumped, no `pyproject.toml`
edit, no PR touched.*

Companion artifact (same content, with the constraint diagrams):
<https://claude.ai/code/artifact/10ea51c6-dc84-4134-94fb-ae70d84eca39>

This is the **Aug 2026 quarterly review's floor item**, which was past due.
`docs/design-platform-policy.md` § Pinning register carries the row *"Python
3.10 floor | EOL October 2026. Decision point. | Quarterly review preceding the
EOL"*. This is that review.

## Decision

**Hold at 3.10 through October. Move to `>=3.12` on 1 November 2026.**

Revised from an earlier `>=3.11` recommendation, which rested on protecting
Debian bookworm — a population that does not survive contact with the dates.

### Why 3.12 and not 3.11

Nothing plausible sits on 3.11. Worked through:

| where a Bristlenose user's `python3` comes from | version | affected by a 3.12 floor? |
|---|---|---|
| Ubuntu 22.04 LTS | 3.10.6 | yes — but a 3.11 floor cuts it too |
| Ubuntu 24.04 LTS (current LTS, to May 2029) | 3.12.3 | no |
| Ubuntu 26.04 LTS | 3.14.3 | no |
| Debian 12 bookworm | 3.11.2 | **regular security support ended 11 June 2026** |
| Debian 13 trixie (stable) | 3.13.5 | no |
| RHEL 9 / Rocky / Alma | **3.9** default | already below the *current* floor; 3.11 and 3.12 are both opt-in module installs |
| Amazon Linux 2023 | **3.9** default | same |
| Apple `/usr/bin/python3` | **3.9.6** (measured) | already below the current floor |
| Windows (python.org installer) | whatever is current | no |

**3.11 appears in no Ubuntu LTS, is the default on no enterprise distro, and on
Debian has been out of regular security support since June.** A floor of 3.11
would protect a population that cannot be named.

Meanwhile 3.12 is what Bristlenose *already ships on*, everywhere:

- Homebrew formula — `depends_on "python@3.12"`
- Snap — `base: core24`, staging `python3.12-minimal`
- macOS sidecar — `Python.framework` 3.12, `build-sidecar.sh` hard-fails without it
- `.tool-versions` — `python 3.12`
- `[tool.mypy] python_version = "3.12"`… currently `"3.10"`, and `[tool.ruff]
  target-version = "py310"` — both of which would move with the floor

And `ci.yml`'s own matrix comment already classifies 3.11 as **ANTICIPATED**
("nothing ships these"), against 3.12 as **SHIPPED**. Setting the floor at an
anticipated version, when a shipped one sits one step up and costs nobody, is
the odd choice.

Two facts land on the same number: **3.12 is the current Ubuntu LTS, and 3.12 is
what every Bristlenose channel already ships.**

### What this is not

It is **not** a CI-speed decision. Dropping to 3.12 removes four of ten matrix
cells and 46% of runner-minutes — but the repo is public so those are free, and
the **wall-clock saving is 3m05s either way**, because the critical path is
bound by `3.13 macos` plus macOS runner queueing, which neither move touches.
See *CI cost* below. Three minutes per push is not a reason to exclude anybody.

It is a **coherence** decision: `requires-python` should name a version something
actually ships, and today it names one nothing does.

### The paired action — the Snap is edge-only

"Ubuntu 22.04 users can use the Snap instead" is the natural mitigation and it
is **not currently true today**: the Snap is published to *edge*, and `snap.yml`
is `workflow_dispatch` only (auto-triggers parked May 2026).

**Less tangled than it first looks, though.** Snap promotion to stable is already
decided and is **marketing-driven** — it rides the autumn "try the beta" push,
not an App Store milestone. Both land in the same autumn window, so they are
compatible by default rather than in tension. The rule is simply: **don't ship
the floor bump into a world where `snap install bristlenose --edge` is still the
only Linux answer.** Not a gate on the floor, a sequencing note.

### For the Held register (`docs/dependency-premortem-log.md`)

| Held bump | Cluster | Reason (blocks now) | Release-predicate (lifts it) | Last watched | Status |
|---|---|---|---|---|---|
| **Python floor** `>=3.10` → `>=3.12` | platform | Ubuntu 22.04 LTS ships `python3` = 3.10.6 and is in standard security maintenance until **May 2027**; raising the floor refuses `pip install bristlenose` there, and the Snap that would catch those users is still edge-only. The floor meanwhile costs nothing measurable — six transitive packages sit 1–2 minors back, no OSV advisory differs between the 3.10 and 3.12 closures, and no declared direct dependency has dropped 3.10 | **CPython 3.10 reaches EOL 31 Oct 2026.** On 1 Nov set `requires-python = ">=3.12"`, `[tool.ruff] target-version = "py312"`, `[tool.mypy] python_version = "3.12"`, drop the 3.10 and 3.11 CI cells (10 → 6), and promote the Snap off edge in the same change. No upstream event required — the predicate is a calendar date fixed by python.org, so this hold cannot rot | 2026-09-03 | held |

It belongs in the Held register rather than the pinning register because the
reason is an ecosystem date, not one of our own.

## The ceiling — a separate, deferred watch (do not couple it to the floor)

**Decided 3 Sep 2026: this is kept apart from the floor decision, and keeping
them apart is the decision.** The floor move is cheap, daily-beneficial and hurts
almost nobody; bolting a speculative upstream problem onto it is how a clean
decision stalls. **Re-examine ≈ March 2027** — or sooner if a user reports a 3.15
install failure. An earlier draft of this doc called the ceiling "more urgent
than the floor" and told the reader to watch it harder; that framing is
superseded.

**Python 3.15 releases on 1 October 2026** (PEP 790) — four weeks *before* 3.10's
EOL. On it, `pip install bristlenose` does not degrade; it **fails outright**:

```
ERROR: Ignored the following versions that require a different python version:
  2.2.363 Requires-Python >=3.10,<3.15; 2.2.364 Requires-Python >=3.10,<3.15
ERROR: No matching distribution found for presidio-analyzer>=2.2.362
```

`presidio-analyzer` and `presidio-anonymizer` are **core** dependencies (stage 7
PII removal), and both 2.2.364 declare `requires-python = ">=3.10,<3.15"`. No
version satisfying our `>=2.2.362` floor admits 3.15, so the resolver has
nothing to pick and the whole install dies. Reproduced above with
`pip --dry-run --python-version 3.15`.

**presidio lags a Python release by roughly eight months.** 3.14 shipped
7 Oct 2025; presidio capped `<3.14` in 2.2.360 (9 Sep 2025) and only floated to
`<3.15` in 2.2.363 on 28 June 2026 — 8.7 months later. The same lag applied to
3.15 puts presidio's admission around mid-2027.

So from 1 October the supported band is squeezed at both ends at once, and the
end we do not control is the one that bites:

| | low end | high end |
|---|---|---|
| today | 3.10, EOL 31 Oct 2026 | 3.14 |
| from 1 Oct 2026 | 3.10 EOL — ours to fix, three config lines | 3.15 exists and cannot install — presidio's to fix, ~mid-2027 |

**The channel that breaks first is Fedora Copr** — already the channel running
ahead of the floor. `.copr/Makefile` pins `python3.14`, and Fedora's Python 3.15
system-wide change is proposed for **F45** (F44 stays on 3.14). When that chroot
lands the pin fails loudly by design, and the obvious fix — bumping it to
`python3.15` — then fails on presidio inside mock, with the same
`from versions: none` shape `docs/design-fedora-packaging.md` already documents
for the architecture mismatch.

**And note what presidio actually is here: the binding constraint on this
project from four directions at once** — `cryptography<49.0.0` (three open
advisories, and it ships in the Mac bundle), `numpy<2.5.0`, `requires-python
<3.15`, and being a core dep with no route around it. When dependency health
looks stuck, presidio is the first place to look, not Python.

Nothing to do today but record it. Suggested Held-register row:

| Held bump | Cluster | Reason (blocks now) | Release-predicate (lifts it) | Last watched | Status |
|---|---|---|---|---|---|
| **Python 3.15 support** *(deferred watch — re-examine ≈ Mar 2027, not coupled to the floor)* | PII / presidio | `presidio-analyzer` + `presidio-anonymizer` 2.2.364 declare `requires-python = ">=3.10,<3.15"`. Both are core deps, so on 3.15 the whole install fails at resolve — not a degraded path, no install at all. 3.15 lands **1 Oct 2026**; presidio historically admits a new Python ~8.7 months late | presidio ships a release whose `requires-python` upper bound admits 3.15 (`<3.16`). Then add a 3.15 CI cell and re-pre-mortem. Watch **Fedora F45** as the first channel to force the question — `.copr/Makefile` pins `python3.14` and will need bumping when that chroot lands | 2026-09-03 | held |

## The finding that changes the question

Both blockers that prompted this turned out **not to be floor problems**, and
they fail in different ways.

**numpy.** 2.5.2 does declare `requires_python >=3.12`. But `presidio-analyzer
2.2.364` requires `numpy>=1.19.0,<2.5.0`, so on a real resolve numpy lands on
**2.4.6 at 3.11, 3.12, 3.13 and 3.14 alike**. Moving the floor to 3.12 does not
get us numpy 2.5.2 — presidio does. The floor is worth exactly one step here,
3.10's 2.2.6 up to 2.4.6, available at 3.11.

**websockets.** 17.1 declares `>=3.11`, and `google-genai 2.22.0` caps
`websockets<17.0`. The resolver returns **16.1.1 on every interpreter from 3.10
to 3.14**. The floor buys nothing at all here — a pure coupling hold that
happens to have a floor standing behind it.

Same shape both times: a cap that binds strictly before the floor does, so the
floor is *shadowed* and cannot be observed until the cap lifts. It matters
because a floor problem and a coupling problem have different fixes and
different owners — and read from a table of `requires_python` values alone,
both look like floor problems.

## Question 1 — who is needy

Across all 161 distributions in the two venvs, **eight** have a latest release
3.10 cannot install. **Not one is a declared dependency** — every direct dep in
`pyproject.toml`, core and all six extras, still publishes for 3.10. All eight
are transitive.

Of the eight, `websockets` is cap-shadowed (above) and `scikit-learn` is not in
our closure at all (it appears only behind `networkx`'s `example` extra, which
we never install). That leaves **six the floor genuinely holds back**:

| package | on 3.10 | available | needs | notes |
|---|---|---|---|---|
| `av` | 17.1.0 | 18.1.0 | 3.11 | never imported by `bristlenose/`; only faster-whisper's audio path |
| `onnxruntime` | 1.23.2 | 1.29.0 | 3.11 | six minors back; the old one drags `sympy`, `mpmath`, `coloredlogs`, `humanfriendly` |
| `rpds-py` | 0.30.0 | 2026.6.3 | 3.11 | transitive of `jsonschema` via the MCP stack |
| `numpy` | 2.2.6 | 2.4.6 | 3.11 | further step to 2.5.2 is presidio's to give, not the floor's |
| `networkx` | 3.4.2 | 3.6.1 | 3.11 | macOS only, via `torch` |
| `scipy` | 1.15.3 | 1.17.1 → 1.18.1 | 3.11 → 3.12 | macOS only, via `mlx-whisper`. **The only package that distinguishes 3.11 from 3.12** |

Against the brief's three categories: none is **(c)** blocked today, none is
**(b)** missing a security fix, all six are **(a)** sitting on an older version
indefinitely — and the two with the widest gaps are packages no Bristlenose
module imports.

**Security delta from the floor: zero.** An OSV batch query over all four
closures (Linux and macOS × 3.10 and 3.12) returns exactly one flagged package,
the same package at the same version in all four.

## Question 2 — what breaks if we move up

Nothing does, and the classic laggard assumption is out of date:

- `numba 0.67.0` ships wheels tagged `cp310 cp311 cp312 cp313 cp314`.
- `llvmlite 0.49.0` ships the same five.
- `mlx`, `mlx-metal`, `mlx-whisper`, `ctranslate2`, `torch`, `tokenizers` and
  `faster-whisper` all resolve to an **identical version on every interpreter
  from 3.10 to 3.14**.

`scipy` is the single exception and it is a floor-*raiser*, not a
ceiling-holder — it needs 3.12 for its latest, which argues for moving up.

Checked properly, **no package in the closure has a `requires_python` upper
bound below 3.15**. There is no ceiling between here and 3.14.

> **Method trap.** The obvious wheel check is wrong: `abi3` wheels are
> forward-compatible, so a naïve `cp3XX in filename` scan reports
> `cryptography`, `tokenizers`, `psutil`, `hf-xet` and `safetensors` as having
> no wheels on most versions when one wheel covers all of them. Parse the full
> `(python, abi, platform)` tag triple.

### What the 3.14 cells are really testing

The worry was a green cell silently skipping the transcription stack. It didn't,
and the answer splits by OS.

**The Ubuntu 3.14 cell never had that stack at any Python version.** `mlx` and
`mlx-whisper` are marked `sys_platform == 'darwin' and platform_machine ==
'arm64'` in the `dev` extra, and they are what pull in `numba`, `llvmlite`,
`scipy` and `torch`. On Linux those four are absent on 3.10 exactly as much as
on 3.14. Nothing was dropped; it was never there. That is a standing Linux-wide
gap, not a 3.14 artefact.

**The macOS 3.14 cell does exercise it, and is green.** From the CI log of run
`33735809497`: runner image `macos-26-arm64`, Python 3.14.6, install line
carrying `mlx-0.32.2`, `mlx-metal-0.32.2`, `mlx-whisper-0.4.3`, `numba-0.67.0`,
`llvmlite-0.49.0`, `scipy-1.18.1`, `torch-2.14.0`. Passed in 9 minutes.

**The real caveat is the gate, not the coverage.** Every macOS cell runs
`continue-on-error: true` unless `strict-macos` is set, which happens only on a
release tag. So the transcription stack is tested on exactly the cells that
cannot redden a push.

### The 3.14 `ensurepip` hold has already cleared

Tested directly against Homebrew's `python@3.14` 3.14.6: `python3.14 -m venv`
exits 0 and produces a working interpreter with `pip 26.1.2`. The blocker is
gone a month before its own October re-check date, and CI independently
overtook the row by adding a 3.14 cell on both OSes on 28 August.

## Question 3 — channel by channel

`requires-python` only ever confronts an interpreter the user already has. Every
channel that carries its own Python is untouched by the floor at any value.

| channel | Python | exposed to the floor? | evidence |
|---|---|---|---|
| **macOS desktop app** | 3.12 | **No** — bundles | `Python.framework` in the signed sidecar; `build-sidecar.sh:112` hard-fails without `python3.12`. The register is right that bumping it is a signing/entitlement event. The floor cannot reach the primary distribution path |
| **Snap** | 3.12 | **No** — bundles | `base: core24`, with `python3.12-minimal` + `libpython3.12-stdlib` staged in (`snap/snapcraft.yaml`). Strict-confined, so the host `python3` isn't visible. Published to *edge* only |
| **Homebrew** | 3.12 | **No** — pins | `depends_on "python@3.12"`; the formula builds its venv from that interpreter explicitly |
| **Fedora Copr** | 3.14 | **No** — ahead of the floor | `.copr/Makefile` installs and names `python3.14`; F43 ships 3.14.7. This channel has run two minors above the floor since it went live on 28 August |
| **PyPI · pip/pipx/uv** | user's | **Yes — the only one** | Raising `requires-python` makes `pip install` refuse. `uv` is a partial exception; it can fetch its own Python |

### The distro question

| distro | `python3` | standard support ends |
|---|---|---|
| Ubuntu 22.04 LTS (jammy) | **3.10.6** | **May 2027** (ESM to May 2032) |
| Ubuntu 24.04 LTS (noble) | 3.12.3 | May 2029 |
| Ubuntu 26.04 LTS (resolute) | 3.14.3 | May 2031 |
| Debian 12 (bookworm, oldstable) | 3.11.2 | — |
| Debian 13 (trixie, stable) | 3.13.5 | — |

**Ubuntu 22.04 is the crux and the whole reason to wait for the EOL date rather
than move now.** Versions from `packages.ubuntu.com` / `packages.debian.org`;
support dates from Canonical's own release-cycle page, which disagreed with
endoflife.date — the aggregator's "standard support" column for LTS releases is
wrong.

## CI cost

The matrix is `["3.10","3.11","3.12","3.13","3.14"] × [ubuntu-latest,
macos-latest]` — **ten cells, not the eight the policy doc says**. From run
`33735809497`, the last full green matrix:

The two available figures differ by 5×, so it matters which one is meant — and
an earlier draft of this doc quoted the larger one while naming the smaller one
as the cost, which invites reading a 3-minute saving as a 17-minute one:

- **Runner-minutes: 18 of 68 (27%)** dropping 3.10 alone; **31 of 68 (46%)**
  dropping 3.10 and 3.11 together. The repository is public, so Actions minutes
  are free. Neither number costs anything.
- **Wall-clock on the critical path: 3m05s of 44m (7%) — the same for both.**
  The cells run concurrently, and once 3.10 goes the binding cell is
  `3.13 macos` at 09:53:29. Dropping 3.11 as well changes nothing further.

So dropping 3.10 saves about three minutes per push, not seventeen. The matrix
is dominated by macOS runner queueing — a 17-minute gap between the last Ubuntu
cell finishing (09:22:51) and the last macOS cell starting (09:47:30) — which
dropping 3.10 does not touch. **This is not a reason to move the floor early, and not a reason to pick 3.12 over 3.11 either** — the wall-clock is identical.

`tests/test_packaging_artifacts_coverage.py` guards its `tomllib` import with
`pytest.importorskip` (stdlib only from 3.11), so that module **skips entirely
on the 3.10 cells**. Correctly written and correctly commented, but it means the
two slowest cells also test slightly less.

Nothing else in the codebase pays for the floor: **no `sys.version_info` branch
anywhere under `bristlenose/`, and no backport declared** — no `tomli`, no
`typing_extensions`, no `exceptiongroup`. The move costs no code change beyond
the three config lines.

## Act on this one — `cryptography` 48.0.1

The OSV sweep turned up exactly one flagged package, identically in all four
closures. Not a floor problem, no Held-register row, and the most actionable
thing in the sweep:

| advisory | severity | fixed in | what |
|---|---|---|---|
| `GHSA-jwv3-5hgf-82ww` | **HIGH** | 49.0.0 | duplicate self-signed intermediates cause exponential path-building in chain validation |
| `GHSA-m2h6-j472-rp4c` | MODERATE | 49.0.0 | verifier accepts wildcard DNS names, escaping a `permittedSubtrees` name constraint |
| `GHSA-g6cj-pr64-35w5` | **HIGH** | 50.0.0 | PKCS#7 `EnvelopedData` decryption exposes a Bleichenbacher oracle via distinguishable errors and timing |

`presidio-anonymizer 2.2.364` requires `cryptography>=48.0.1,<49.0.0` — the cap
excludes the fix for all three by exactly one major.

**Likely real exposure is nil, and that is worth stating precisely rather than
waving at.** No module under `bristlenose/` imports `cryptography`; it arrives
via presidio-anonymizer (AES for the PII encrypt/decrypt operators) and via
`google-auth` / `pyjwt` for token signing. All three advisories are X.509
path-validation or PKCS#7 surfaces we do not call. But a procurement scanner
does not read call graphs, and `SECURITY.md` makes commitments about this exact
scenario — so it wants a row, a predicate, and a written note that the exposure
was assessed rather than missed.

Suggested predicate: *presidio-anonymizer floats its `cryptography` cap past 49;
take the pair atomically, as the 9 June 2026 security wave did with 44→48.*

## The measured delta

A real `pip` resolve of `[dev,serve]` at each interpreter, on
`manylinux_x86_64` and `macosx_arm64`, **then diffed against the live CI install
logs for the 3.10 cells — every package matched**.

- **Six packages** resolve older on 3.10: `av`, `numpy`, `onnxruntime`,
  `rpds-py` everywhere; `networkx` and `scipy` additionally on macOS.
- **Four extra transitives** come along on 3.10 that newer resolutions drop —
  `sympy`, `mpmath`, `coloredlogs`, `humanfriendly`, all dragged by the older
  `onnxruntime`. 138 packages on 3.10 versus 134 above it.
- **3.11 → 3.12 changes exactly one package**: `scipy` 1.17.1 → 1.18.1, macOS
  only. That single row is the entire case for 3.12 over 3.11.
- **3.12 → 3.13 → 3.14 changes nothing.** Identical closures.

## Register drift found while grounding

1. **`jsdom` pinned to 27.x — the re-check condition can never fire.** The row
   reads *"Re-check once `#89` merges"*. PR #89 was **closed without merging on
   5 May 2026**. It will never merge, so the row can never come due — a
   permanent hold wearing the costume of a temporary one. `frontend/package.json`
   still carries `"jsdom": "^27.4.0"` and the dependabot ignore is still there.
   Give it a real predicate or delete it.
2. **Python 3.14 · `ensurepip` — blocker already gone.** Verified today (above).
   The matching CLAUDE.md gotcha ("as of April 2026 it's a real papercut")
   should be retired with the row.
3. **`lighthouse` 12.x — the register is behind its own ignore file.** The row
   says its blocker is gone and asks someone to re-validate or drop it;
   `.github/dependabot.yml` already carries a *different*, live reason
   (perf-baseline re-pin cost). Cassandra flagged this in Entries 1, 2 and 5.
   This is the fourth flag. Entry 5's proposed structural fix stands: *a register
   row may not restate a value that lives in a tracked config file; it may only
   name the file.*
4. **Pillar 2 describes a matrix that no longer exists.** It says *"Why
   3.10–3.13"* and calls 3.13 the ceiling; the matrix has run 3.10–3.14 since
   28 August. The Triage-boundary section says *"8-cell Python matrix"*; it is
   ten.
5. **presidio's `<3.15` ceiling is recorded nowhere** — see *The more urgent
   problem is the ceiling* above; this is the finding to act on.** `presidio-analyzer` and
   `presidio-anonymizer` 2.2.364 both declare `requires-python = ">=3.10,<3.15"`
   — the **nearest real ceiling on the entire project**, in neither register.
   Not hypothetical: 2.2.360–2.2.362 were capped `<3.14`, and only 2.2.363 on
   28 June 2026 floated it to `<3.15`, meaning the 3.14 CI cell became
   resolvable about eight weeks before it was added. The next Python that needs
   watching is 3.15, and presidio is who we will be waiting on.
6. **`typer[all]` requests an extra that no longer exists.** `pyproject.toml:22`
   declares `typer[all]>=0.12`; typer 0.27.2 provides no `all` extra, so every
   install — CI, contributor, sidecar build — prints `WARNING: typer 0.27.2 does
   not provide the extra 'all'`. Harmless, but it is in the install log of every
   channel and the fix is deleting four characters.

## Full table

Installed columns read `.venv` then `.venv-sidecar`. **The sidecar venv is what
ships**; where the two disagree the values are marked ⚠︎. They disagree on 26
packages — the dev venv is roughly a month stale, and is the wrong control for
any bundle question.

| package | group | pin in pyproject | `.venv` | `.venv-sidecar` | latest on PyPI | `requires_python` installed | `requires_python` latest | verdict |
|---|---|---|---|---|---|---|---|---|
| `typer` | core | `>=0.12` | `0.27.1` ⚠︎ | `0.27.2` ⚠︎ | `0.27.2` | `>=3.10` | `>=3.10` | clear |
| `pydantic` | core | `>=2.5` | `2.13.4` ⚠︎ | `2.13.5` ⚠︎ | `2.13.5` | `>=3.9` | `>=3.9` | clear |
| `pydantic-settings` | core | `>=2.1` | `2.15.0` | `2.15.0` | `2.15.0` | `>=3.10` | `>=3.10` | clear |
| `faster-whisper` | core | `>=1.0` | `1.2.1` | `1.2.1` | `1.2.1` | `>=3.9` | `>=3.9` | clear |
| `pysrt` | core | `>=1.1` | `1.1.2` | `1.1.2` | `1.1.2` | — | — | clear |
| `webvtt-py` | core | `>=0.5` | `0.5.1` | `0.5.1` | `0.5.1` | `>=3.7` | `>=3.7` | clear |
| `python-docx` | core | `>=1.1` | `1.2.0` | `1.2.0` | `1.2.0` | `>=3.9` | `>=3.9` | clear |
| `presidio-analyzer` | core | `>=2.2.362` | `2.2.364` | `2.2.364` | `2.2.364` | `>=3.10,<3.15` | `<3.15,>=3.10` | py ceiling `<3.15` |
| `presidio-anonymizer` | core | `>=2.2.362` | `2.2.364` | `2.2.364` | `2.2.364` | `>=3.10,<3.15` | `<3.15,>=3.10` | py ceiling `<3.15` |
| `anthropic` | core | `<1,>=0.39` | `0.125.0` | `0.125.0` | `1.3.0` | `>=3.9` | `>=3.10` | cap-held · ours `<1` |
| `openai` | core | `>=1.50` | `3.5.0` ⚠︎ | `3.6.0` ⚠︎ | `3.7.0` | `>=3.10` | `>=3.10` | clear |
| `google-genai` | core | `>=1.0` | `2.20.0` | `2.20.0` | `2.22.0` | `>=3.10` | `>=3.10` | clear |
| `rich` | core | `>=13.0` | `15.0.0` | `15.0.0` | `15.0.0` | `>=3.9.0` | `>=3.9.0` | clear |
| `pyyaml` | core | `>=6.0` | `6.0.3` | `6.0.3` | `6.0.3` | `>=3.8` | `>=3.8` | clear |
| `jinja2` | core | `>=3.1` | `3.1.6` | `3.1.6` | `3.1.6` | `>=3.7` | `>=3.7` | clear |
| `inflect` | core | `>=7.0` | `7.5.0` | `7.5.0` | `7.5.0` | `>=3.9` | `>=3.9` | clear |
| `mlx` | apple | `>=0.16` | `0.32.0` ⚠︎ | `0.32.2` ⚠︎ | `0.32.2` | `>=3.10` | `>=3.10` | clear |
| `mlx-whisper` | apple | `>=0.4` | `0.4.3` | `0.4.3` | `0.4.3` | `>=3.8` | `>=3.8` | clear |
| `pytest` | dev | `>=8.0` | `9.1.1` | — | `9.1.1` | `>=3.10` | `>=3.10` | clear |
| `pytest-cov` | dev | `>=5.0` | `7.1.0` | — | `7.1.0` | `>=3.9` | `>=3.9` | clear |
| `pytest-xdist` | dev | `>=3.8` | `3.8.0` | — | `3.8.0` | `>=3.9` | `>=3.9` | clear |
| `pytest-asyncio` | dev | `>=0.24` | `1.4.0` | — | `1.4.0` | `>=3.10` | `>=3.10` | clear |
| `ruff` | dev | `>=0.8` | `0.16.1` | — | `0.16.5` | `>=3.7` | `>=3.7` | clear |
| `mypy` | dev | `>=1.13` | `2.3.0` | — | `2.3.1` | `>=3.10` | `>=3.10` | clear |
| `pre-commit` | dev | `>=4.0` | `4.6.2` | — | `4.6.2` | `>=3.10` | `>=3.10` | clear |
| `httpx` | dev | `>=0.27` | `0.28.1` | `0.28.1` | `0.28.1` | `>=3.8` | `>=3.8` | clear |
| `mcp` | dev | `<2.1,>=2.0` | `2.0.0` ⚠︎ | `2.0.1` ⚠︎ | `2.1.1` | `>=3.10` | `>=3.10` | cap-held · ours `<2.1` |
| `fastapi` | serve | `>=0.115` | `0.141.1` | `0.141.1` | `0.141.1` | `>=3.10` | `>=3.10` | clear |
| `uvicorn` | serve | `>=0.32` | `0.52.1` ⚠︎ | `0.52.4` ⚠︎ | `0.52.4` | `>=3.10` | `>=3.10` | clear |
| `sqlalchemy` | serve | `>=2.0` | `2.0.51` ⚠︎ | `2.0.52` ⚠︎ | `2.0.52` | `>=3.7` | `>=3.7` | clear |
| `sqladmin` | serve | `>=0.20` | `0.30.0` ⚠︎ | `0.31.0` ⚠︎ | `0.31.1` | `>=3.10` | `>=3.10` | clear |
| `openpyxl` | serve | `>=3.1` | `3.1.5` | `3.1.5` | `3.1.5` | `>=3.8` | `>=3.8` | clear |
| `alembic` | serve | `>=1.13` | `1.18.5` ⚠︎ | `1.19.1` ⚠︎ | `1.19.1` | `>=3.10` | `>=3.10` | clear |
| `pip-licenses` | release | `>=5.0` | `5.5.5` | — | `5.5.5` | `>=3.9` | `>=3.9` | clear |
| `pyinstaller` | desktop | `>=6.10` | — | `6.22.2` | `6.22.2` | `<3.16,>=3.8` | `<3.16,>=3.8` | py ceiling `<3.16` |
| `spacy` | transitive | `—` | `3.8.16` | `3.8.16` | `3.8.16` | `<3.15,>=3.9` | `<3.15,>=3.9` | py ceiling `<3.15` |
| `thinc` | transitive | `—` | `8.3.13` | `8.3.13` | `9.1.1` | `<3.15,>=3.10` | `>=3.9` | cap-held · spacy `<8.4.0` |
| `numpy` | transitive | `—` | `2.4.6` | `2.4.6` | `2.5.2` | `>=3.11` | `>=3.12` | floor-raiser · needs ≥3.12; cap-held · presidio-analyzer `numpy<2.5.0` |
| `numba` | transitive | `—` | `0.66.0` ⚠︎ | `0.67.0` ⚠︎ | `0.67.0` | `>=3.10` | `>=3.10` | clear |
| `llvmlite` | transitive | `—` | `0.48.0` ⚠︎ | `0.49.0` ⚠︎ | `0.49.0` | `>=3.10` | `>=3.10` | clear |
| `scipy` | transitive | `—` | `1.18.0` ⚠︎ | `1.18.1` ⚠︎ | `1.18.1` | `>=3.12` | `>=3.12` | floor-raiser · needs ≥3.12 |
| `cryptography` | transitive | `—` | `48.0.1` | `48.0.1` | `50.0.1` | `>=3.9, !=3.9.0, !=3.9.1` | `!=3.9.0,!=3.9.1,>=3.9` | **cap-held · presidio-anonymizer `<49.0.0` — 3 open advisories** |
| `starlette` | transitive | `—` | `1.3.1` ⚠︎ | `1.6.0` ⚠︎ | `1.6.0` | `>=3.10` | `>=3.10` | clear |
| `ctranslate2` | transitive | `—` | `4.8.1` ⚠︎ | `4.8.2` ⚠︎ | `4.8.2` | `>=3.9` | `>=3.9` | clear |
| `tokenizers` | transitive | `—` | `0.23.1` | `0.23.1` | `0.23.2` | `>=3.10` | `>=3.10` | clear |
| `websockets` | transitive | `—` | `16.1.1` | `16.1.1` | `17.1` | `>=3.10` | `>=3.11` | floor-raiser · needs ≥3.11; cap-held · google-genai `websockets<17.0` |
| `av` | transitive | `—` | `18.1.0` | `18.1.0` | `18.1.0` | `>=3.11` | `>=3.11` | floor-raiser · needs ≥3.11 |
| `onnxruntime` | transitive | `—` | `1.29.0` | `1.29.0` | `1.29.0` | `>=3.11` | `>=3.11` | floor-raiser · needs ≥3.11 |
| `rpds-py` | transitive | `—` | `2026.6.3` | `2026.6.3` | `2026.6.3` | `>=3.11` | `>=3.11` | floor-raiser · needs ≥3.11 |
| `networkx` | transitive | `—` | `3.6.1` | `3.6.1` | `3.6.1` | `!=3.14.1,>=3.11` | `!=3.14.1,>=3.11` | floor-raiser · needs ≥3.11 |
| `torch` | transitive | `—` | `2.13.0` | `2.13.0` | `2.14.0` | `>=3.10` | `>=3.10` | clear |
| `mcp-types` | transitive | `—` | `2.0.0` ⚠︎ | `2.0.1` ⚠︎ | `2.1.1` | `>=3.10` | `>=3.10` | cap-held · pinned to mcp |
| `transformers` | transitive | `—` | — | — | `5.16.1` | — | `>=3.10.0` | clear |
| `protobuf` | transitive | `—` | `7.36.0` | `7.36.0` | `7.36.1` | `>=3.10` | `>=3.10` | clear |
| `blis` | transitive | `—` | `1.3.3` | `1.3.3` | `1.3.3` | `>=3.9,<3.15` | `<3.15,>=3.9` | py ceiling `<3.15` |

## Method

Nothing above is inferred from a version string.

- **Metadata** — `info.requires_python` and per-release `requires_python` from
  `pypi.org/pypi/<pkg>/json`, for all 161 distributions across both venvs plus
  every declared name.
- **Resolves** — `pip install --dry-run --report --python-version X
  --only-binary=:all: --platform …` for 3.10–3.14, Linux and macOS arm64, from
  the exact `[dev,serve]` requirement set.
- **Ground truth** — resolved versions diffed against the real install lines in
  CI run `33735809497` for the 3.10 Ubuntu and macOS cells. Every package
  matched.
- **Advisories** — OSV `querybatch` over each complete closure, then per-advisory
  range and severity from `api.osv.dev/v1/vulns/<id>`.
- **Distros** — `python3` versions from `packages.ubuntu.com` and
  `packages.debian.org`; support dates from Canonical's release-cycle page.

Two traps worth recording, both of which produce confident wrong answers:
`pysrt` is sdist-only on PyPI, so `--only-binary=:all:` refuses it and the
resolve dies naming the wrong package (the same trap the Copr wheelhouse already
documents); and a wheel-availability check that greps `cp3XX` out of the
filename misreads every `abi3` wheel, which is how a first pass here concluded
that `cryptography` ships no wheels for 3.10, 3.12 or 3.13.
