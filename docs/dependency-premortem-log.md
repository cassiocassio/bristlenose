# Dependency pre-mortem ledger

Cassandra's prophecies and their outcomes. One entry per pre-mortem pass.
Append-only; never renumber. The running tally lets us see, over time,
how well the oracle calls it.

See `docs/design-dependency-premortem.md` for how this works and
`.claude/skills/cassandra/SKILL.md` for how to add an entry (Mode A),
score one (Mode B `/cassandra --score`), or re-examine the holds below
(Mode C `/cassandra --watch`).

**Tally:** 4 prophecies scored — 4 hits, 0 misses, 0 false-alarms.

## Held register

The standing watch list. Each row is a **`(reason, release-predicate)`**
obligation, not a dead pin — `/cassandra --watch` re-evaluates each
predicate against fresh deps.dev / OSV metadata and graduates the row to
a fresh pre-mortem the day its coupling cluster becomes safe to take "as
a wave." An ignore in `.github/dependabot.yml` without a row here is a
tombstone; fix it by adding the row.

| Held bump | Cluster | Reason (blocks now) | Release-predicate (lifts it) | Last watched | Status |
|-----------|---------|---------------------|------------------------------|--------------|--------|
| **thinc** (major) | spaCy ecosystem | spaCy 3.8.x pins `thinc<8.4`; thinc 9.x is spaCy-4 era | spaCy 4 reaches GA **and** the cluster (spacy+thinc+weasel+confection+en_core_web_lg) co-resolves; take atomically | 2026-06-09 | held |
| **weasel** (major) | spaCy ecosystem | spaCy 3.8.x pins `weasel<0.5`; weasel 1.0 *requires* `confection>=1.0`, mutually exclusive with thinc 8.3's `confection<1.0` | same spaCy-4 wave as thinc | 2026-06-09 | held |
| **confection** (major) | spaCy ecosystem | thinc 8.3 pins `confection<1.0` | thinc moves to 9.x (⇒ spaCy 4 wave) | 2026-06-09 | held |
| **starlette** 1.x | FastAPI / starlette | _(graduated 2026-06-09 — FastAPI 0.136.3 dropped the `starlette<1.0` cap, pair pre-mortemed in the graduated-holds wave)_ | n/a — graduated | 2026-06-09 | **graduated** |
| **anthropic** 1.x | LLM SDKs · anthropic→httpx2 | ~~`1.0.0` removes `temperature` from `messages.create`, and the signature has **no `**kwargs`**~~ — **the code-side blocker is gone.** `client.py` no longer passes `temperature` as a named kwarg to Claude (`bb9e201d`), because sampling is per-**model**: Anthropic 400s it on every model after 4.6, and `claude-opus-4-8` — already in the macOS picker — was failing on every call. The *product* question is settled too: the slider is removed (`fe145d32`, `docs/design-decisions.md` §"Temperature is not a control we ship"); `output_config.effort` was examined and is **not** a relabel of it. What remains is only re-pre-mortem — the transport-major coupling and the other unexamined majors, not this parameter | Re-pre-mortem the wave (`anthropic` 1.x + `openai` 2→3 + `google-genai` 1→2, all on the `httpx2` coupling), then float the ceiling. No product decision is outstanding | 2026-09-03 | held — **code-ready, wave-blocked** |
| **mcp** 2.1+ | assistant surface · mcp→mcp-types (pinned `==`) | 2.1 masks a tool exception's message behind a generic `Error executing tool <name>` — sound hardening, and it breaks *our* design: `server/mcp_server.py:_run` signals a legitimate refusal by **raising** `ToolInputError` (our own `ValueError` subclass, :66), so an out-of-scope project stopped saying why it refused. Caught by strict CI on the 0.28.0 tag, not locally: the pin was floor-only, so a fresh resolve took 2.1.1 while the venv sat on 2.0.0 | Refusals must be **returned as tool results** rather than raised — three call sites (`:245`, `:252`, the out-of-scope guard) plus `test_mcp_server.py`'s two classes. Not a version bump; a change to how the surface signals. Then float the ceiling and re-pre-mortem. Note `mcp 2.0.0` requires `mcp-types==2.0.0` exactly, so the ceiling pins the pair | 2026-08-28 | held |
| **tokenizers** 0.23.1 | HF transformer stack | `transformers` 5.7.0 **and** 5.10.2 both pin `tokenizers<=0.23.0` (deps.dev verified 2026-06-05) | a transformers release floats its tokenizers cap to admit 0.23.1 (`GetRequirements` for transformers: cap becomes `<0.24`/`<=0.23.1`); then move tokenizers+transformers together | 2026-06-09 | held |
| **WTForms** 3.2.2 | sqladmin / serve DB | _(graduated 2026-06-09 — sqladmin 0.27.2 floated `wtforms<3.3`, pair pre-mortemed in the graduated-holds wave)_ | n/a — graduated | 2026-06-09 | **graduated** |
| **snapcore/action-build** `v1.3.0` (node20) | GitHub Actions runtime | Action declares `runs.using: node20`; **v1.3.0 is the newest tag upstream** (`releases/latest` 404s, tags = `v1.3.0`, `v1`). No node24 release exists to take. Emits the runner's forced-to-node24 annotation. Mitigant: `snap.yml` is `on: workflow_dispatch` only (parked May 2026). | snapcore publishes a release whose `action.yml` has `runs.using: node24` — then bump both snapcore SHAs together with their version comments | 2026-07-29 | held |
| **snapcore/action-publish** `v1.2.0` (node20) | GitHub Actions runtime | Same: `runs.using: node20`; v1.2.0 is the newest upstream tag. | Same predicate as action-build; move the pair | 2026-07-29 | held |

<!-- Watch grounding: deps.dev GetRequirements for the upstream caps
     (spacy→thinc, fastapi→starlette), GetVersion for publishedAt/scorecard,
     OSV for advisories. spaCy-4 GA is the single event that clears the top
     three rows as one wave. -->

---

## Entry 1 — 2026-06-04 — full outstanding bump wave (v0.15.x line)

- **Grounded against:** `.venv` installed metadata (`importlib.metadata`
  version + requires) + pinning register (`docs/design-platform-policy.md`)
  + ignore list (`.github/dependabot.yml`).
- **Prior calibration applied:** first prophecy — no prior entries. This
  seeds the ledger.
- **Candidate set:** the two open Dependabot PRs (#116 frontend
  minor-and-patch group of 11; #110 `@playwright/test`) **plus** the
  latent pip wave the headline gap exposes (spaCy cluster majors, the
  numpy trio, starlette, google-genai, the LLM SDKs, rich, protobuf,
  fastapi/pydantic minors). The user's ask was "what happens if we do
  *all* the dep reviews and dependabots" — so this covers the full
  wave, not just what's merge-ready today.

### Prophecy

| Bump (from→to) | Verdict | Surface | Blast radius & receipt |
|----------------|---------|---------|------------------------|
| **thinc** 8.3.10→9.1.1 | 🔴 WILL-BREAK | resolver | spaCy 3.8.11 pins `thinc<8.4.0` (installed metadata). Lone bump = red install; takes the **Presidio PII path** down with it. thinc 9.x is spaCy-4 era. |
| **weasel** 0.4.3→1.0.0 | 🔴 WILL-BREAK | resolver | spaCy 3.8.11 pins `weasel<0.5.0`; weasel 1.0.0 *requires* `confection>=1.0.0` (PyPI metadata) — mutually exclusive with thinc 8.3's `confection<1.0`. Double-locked red. |
| **confection** 0.1.5→1.3.3 | 🔴 WILL-BREAK | resolver | thinc 8.3 pins `confection<1.0`. Can't move while thinc is 8.3 / spaCy is 3.8. |
| **numpy** 2.3.5→2.4.6 | 🔴 WILL-BREAK *if lone* / 🟢 SAFE *in trio* | runtime (silent) | numba 0.63.1 pins `numpy<2.4` (installed) → lone numpy bump throws at `import numba`. **But numba 0.65.1 caps `numpy<2.5`** (PyPI) → numpy+numba+llvmlite move together cleanly. The classic silent break; the group is the cure. |
| **numba** 0.63.1→0.65.1 | 🟢 SAFE *(trio)* | — | 0.65.1 floats its numpy cap to `<2.5` (PyPI). Take **with** numpy 2.4.6 + llvmlite 0.47, never alone-after-numpy. |
| **llvmlite** 0.46.0→0.47.0 | 🟢 SAFE *(trio)* | — | numba's codegen backend; moves in lockstep with numba 0.65. |
| **starlette** 0.52.1→1.2.1 | 🟡 RESOLVER-NON-EVENT | resolver-gated | FastAPI 0.129.0 caps `starlette<1.0.0` (installed metadata). Dependabot's PR won't resolve and dies on its own. **Un-gates** the day FastAPI floats the cap past 1.0. |
| **google-genai** 1.62.0→2.8.0 | 🟢 SAFE | — | We call `generate_content` on the async client (`self._google_client.aio.models`) with a `GenerateContentConfig(response_schema=…)` (`bristlenose/llm/client.py:690,698-704`) — paraphrased, not a verbatim quote. 2.0's breaking changes are in removed v1 aliases / Interactions surfaces we don't touch. **Highest-value green to confirm in the score pass.** |
| **anthropic** 0.77.1→0.105.2 | 🟢 SAFE | — | Large 0.x minor gap, but Messages + tool-use API is stable across the range; we don't use beta surfaces. |
| **openai** 2.16.0→2.41.0 | 🟢 SAFE ⚠️ LATENT | — | SDK clean. ⚠️ Orthogonal trap: `max_tokens` is rejected by GPT-5-class models (use `max_completion_tokens`) — bites only if someone points `--llm openai` at a GPT-5 model. Not caused by the bump; record, don't block. |
| **rich** 14.3.2→15.0.0 | 🟢 SAFE | — | We use `console.print` / tables / progress — 15.0's breaks are in rarely-used markup/measurement APIs. Confirm against call sites in score pass. |
| **protobuf** 6.33.5→7.35.0 | 🟢 SAFE | — | Transitive (grpc / genai). Pure-Python message path unaffected by the 7.0 C++-runtime changes. |
| **fastapi** 0.129.0→0.136.3 | 🟢 SAFE | — | Minor within 0.x; keeps the `starlette<1.0` cap. (FastAPI *major* is ignored in dependabot.yml.) |
| **pydantic** 2.12.5→2.13.4 | 🟢 SAFE | — | Minor within v2. (pydantic *major* is ignored.) |
| **spacy** 3.8.11→3.8.14 | 🟢 SAFE | — | Patch within 3.8; preserves the thinc/weasel pins. The *safe* way the cluster moves. |
| **lighthouse** 12.8.2→13.x | 🟢 SAFE *(ignored on stale rationale)* | — | Currently major-ignored "CI on Node 20"; but `.tool-versions` says **node 24**, and lighthouse 13 needs Node ≥22.19 — satisfied. The pin's reason is stale. No e2e spec asserts on lighthouse audit IDs (grep clean). See drift below. |
| **PR #116** frontend minor group (i18next, react, react-dom, react-i18next, react-router-dom, @vitejs/plugin-react, eslint, typescript-eslint, vite, vitest, @types/react) | 🟢 SAFE | — | All 11 are patch/minor within current majors (e.g. react 19.2.5→19.2.7, vite 8.0.10→8.0.16). No Node-major gate crossed. Merge-ready. |
| **PR #110** @playwright/test 1.59.1→1.60.0 | 🟢 SAFE | — | Minor; no bundled-browser channel rotation in range. Merge-ready. |

### The guaranteed breakages (act here first)

The spaCy cluster — **thinc, weasel, confection** — are guaranteed
resolver-reds while spaCy is 3.8.x. They are **not currently in the
dependabot.yml ignore list** (only pydantic + fastapi majors are). So
Dependabot *will* keep opening these as red PRs every Monday. Smallest
mitigation: add the three to the pip `ignore` list with
`version-update:semver-major`, reason "spaCy-4 era; gated by spaCy 3.8
pins; revisit at spaCy 4 GA."

numpy alone is the one *silent* runtime red in the set — but only if
bumped outside its trio. The minor-and-patch group bundles
numpy+numba+llvmlite, so the grouped PR is safe; the danger is a
hand-merged lone numpy.

### The non-events (no action; know why)

starlette 1.x — FastAPI's own `starlette<1.0` cap means the PR can't
resolve. Optionally add to ignore to suppress the recurring noise PR,
but it harms nothing if left to fail.

### The safe wave (take together)

google-genai 2.x, anthropic, openai, rich 15, protobuf 7, fastapi-minor,
pydantic-minor, spacy-patch, plus the numpy/numba/llvmlite **trio as one
unit**, plus the two open PRs (#116, #110). Confirm google-genai and
rich against their call sites in the score pass — they're the two greens
with the most surface area.

### Recommendations

1. **Merge #116 and #110 now** — clean minor/patch, no gates crossed.
2. **Add the spaCy cluster (thinc/weasel/confection) major-ignore** to
   the pip section of dependabot.yml — stops the recurring red PRs.
3. **Never merge a lone numpy PR** — only the numpy+numba+llvmlite group.
4. **Re-examine the lighthouse ignore** — its rationale is stale (CI is
   Node 24, not 20). Either drop the ignore or correct the comment.
5. The LLM SDK / web-stack greens move as one wave once the cluster
   ignores are in place.

### Stale-register drift found while grounding

- `.github/dependabot.yml` — the lighthouse ignore comment says
  "Lighthouse 13 requires Node ≥22.19; CI is on 20." CI is on **node 24**
  (`.tool-versions`). The rationale no longer holds.
- `docs/design-platform-policy.md` — lines referencing "CI Node 20" /
  Node-20-gated tooling are stale against `.tool-versions` (node 24).
  Misleads the next prophecy; worth a sweep.

### OUTCOME — partial (open)

- **PR #110 (@playwright/test 1.59.1→1.60.0):** SHIPPED via the v0.15.13
  release-pipeline fix path (commit on `e2e/package.json`, not via merging
  the Dependabot PR — #110 was Dependabot-closed). It fixed the
  chromium-install hang exactly as predicted. See CLAUDE.md "Release-to-PyPI
  workflow" gotcha for the receipt.
- **starlette 0.52.1→1.2.1 + fastapi 0.129.0→0.136.3 (atomic pair):**
  APPLIED 2026-06-09 as part of the graduated-holds wave (Branch 2).
  Predicate met — FastAPI 0.136.3 requirements now `starlette>=0.46.0` with
  no upper bound. pytest tests/ green (3078 pass / 7 skip / 42 xfail /
  243s); ruff clean.
- All other Entry-1 verdicts remain UNTESTED — the bumps haven't landed.

### SCORE — partial

- **@playwright/test 1.60.0** → 🟢 **HIT.** Prophecy was SAFE; shipped and
  fixed a real CI flake. Lesson: a green verdict on a minor playwright bump
  was the right call; no chromium channel rotation in range.
- **starlette 1.x (with fastapi 0.136.3 pair)** → 🟢 **HIT.** Prophecy was
  RESOLVER-NON-EVENT until FastAPI floated the cap; predicate satisfied
  4 days later, pair taken atomically, no break. Lesson: the
  resolver-gated framing held — never a lone bump, always wait for the cap.
- Everything else: pending — not yet merged.

---

## Entry 2 — 2026-06-05 — the long-tail pip wave (everything Entry 1 didn't enumerate)

- **Grounded against:** `.venv` installed metadata (`importlib.metadata` version +
  requires) + pinning register (`docs/design-platform-policy.md`) + ignore list
  (`.github/dependabot.yml`) + Entry 1 / Held register above. Four load-bearing
  target-version caps re-verified live against **deps.dev v3 GetRequirements**
  (2026-06-05): transformers 5.10.2 → `tokenizers<=0.23.0`; presidio-anonymizer
  2.2.362 → `cryptography>=46.0.4`; sqladmin 0.27.0 → `wtforms>=3.1,<3.2`;
  google-genai 2.8.0 → `websockets<17.0`. All four confirmed.
- **Prior calibration applied:** Entry 1 (2026-06-04) is still open/unscored — no
  scored outcomes yet to tune on. Entry 1's verdicts are treated as standing and
  NOT re-litigated; this entry covers only the long tail Entry 1 never enumerated.
- **Why not a duplicate of Entry 1:** installed Python metadata is byte-identical
  to Entry 1's grounding (nothing bumped locally since). Entry 1 scoped itself to
  the PR-driven set + the highest-risk latent pip (spaCy cluster, numpy trio,
  starlette, LLM SDKs, rich, protobuf, fastapi/pydantic minors, spacy patch,
  lighthouse, PR #116/#110). This entry is the **long tail** Entry 1 skipped:
  torch/HF inference cluster, cryptography major, av/typer/websockets/uvicorn,
  pyinstaller/setuptools, sklearn cluster, the HTTP + serve-DB stack, and the
  patch/minor utility floor. **Defining fact:** almost none of these are imported
  by `bristlenose/` code (torch, transformers, sentence-transformers, tokenizers,
  av, cryptography, websockets, scikit-learn, hdbscan, chardet, lxml, sqlmodel are
  all transitive) — so their only failure surface is the resolver, not runtime.

### Prophecy

| Bump (from→to) | Verdict | Surface | Receipt |
|----------------|---------|---------|---------|
| **tokenizers** 0.22.2→0.23.1 *(lone)* | 🔴 WILL-BREAK | resolver | `transformers` 5.7.0 **and** 5.10.2 both pin `tokenizers<=0.23.0` (deps.dev verified). 0.23.1>0.23.0 → red on both; pairing with transformers does NOT fix it. Hold at 0.22.x. |
| **WTForms** 3.1.2→3.2.2 *(lone)* | 🔴 WILL-BREAK | resolver | `sqladmin` 0.23.0 **and** 0.27.0 both pin `wtforms>=3.1,<3.2` (deps.dev verified). Bumping sqladmin does not help — hold WTForms at 3.1.x. |
| **cryptography** 44.0.3→48.0.0 *(lone)* | 🔴 WILL-BREAK *(lone)* / 🟢 *(paired)* | resolver | `presidio-anonymizer` 2.2.360 pins `cryptography<44.1` → lone red. `presidio-anonymizer` 2.2.362 *requires* `cryptography>=46.0.4` (deps.dev verified) → presidio patch forces crypto past 46, compatible with 48. **Mandatory pair.** Security-motivated: crypto 44.0.3 carries two open GHSAs (OSV); 48.0.0 clean. macOS arm64 + linux ship as prebuilt wheels — no toolchain bump. |
| **presidio-analyzer/anonymizer** 2.2.360→2.2.362 | 🟢 SAFE *(drags crypto 48)* | resolver | analyzer keeps `spacy>=3.4.4,!=3.7.0` + `phonenumbers<10` (both fine). anonymizer's `cryptography>=46.0.4` is the only new constraint → move PII trio (presidio×2 + crypto 48) atomically. |
| **websockets** 15.0.1→16.0 *(lone)* | 🟡 RESOLVER-NON-EVENT *(now)* / 🟢 *(with genai 2.x)* | resolver-gated | `google-genai` 1.62.0 caps `websockets<15.1.0` → lone PR can't resolve. `google-genai` 2.8.0 floats to `websockets<17.0` (deps.dev verified) → un-gates with the genai 2.x bump (already greened in Entry 1). Serve code uses no WebSockets (grep-clean) — pure resolver edge. |
| **torch** 2.10.0→2.12.0 | 🟢 SAFE | runtime (none on our path) | Transitive; `import torch` occurs only in `mlx_whisper/torch_whisper.py` (dead checkpoint-conversion tool, never imported at runtime per sidecar spec). faster-whisper doesn't import torch. torch-MPS-on-Tahoe regressions can't bite (we never touch torch-MPS). OSV-clean. ctranslate2 links no torch (`setuptools,numpy,pyyaml` only). |
| **transformers** 5.7.0→5.10.2 | 🟢 SAFE *(tokenizers held 0.22.x)* | resolver | Not imported in `bristlenose/`. Caps OK: `huggingface-hub<2.0` (1.17 ok), `torch>=2.4` (2.12 ok); `sentence-transformers` caps `transformers<6.0` (5.10 ok). Must keep tokenizers 0.22.x. |
| **sentence-transformers** 5.4.1→5.5.1, **huggingface_hub** 1.13→1.17, **hf-xet** 1.4.3→1.5.0, **ctranslate2** 4.7.0→4.7.2, **onnxruntime** 1.23.2→1.26.0, **mlx/mlx-metal** 0.30.5→0.31.2 | 🟢 SAFE | — | All transitive/loose; co-resolve. onnxruntime `numpy>=1.21.6` (ok); ct2 patch; mlx pair moves together (`collect_all("mlx")` in spec). |
| **av** 16.1.0→17.0.1 | 🟢 SAFE ⚠️ LATENT | — | Our audio/video extraction is ffmpeg-subprocess, not PyAV (`utils/video.py`, s02) — av never imported by `bristlenose/`. Only `faster-whisper/audio.py` uses it (loose `av>=11`). ⚠️ av 17 raises `av.ArgumentError` (was `ValueError`) on FFmpeg C errors — latent on the **Linux/CI** faster-whisper transcription error path only, not the Mac MLX path. |
| **typer** 0.21.1→0.26.7 + **typer-slim** 0.21.1→0.24.0 | 🟢 SAFE | — | CLI uses `Annotated[..., typer.Option()]` / `typer.Argument` / `@app.command` / `@app.callback` / `typer.Exit` — core API unchanged 0.21→0.26. 0.26's break is Click *vendoring*; zero `import click` / Typer-internal-Click access (grep-clean). |
| **uvicorn** 0.41→0.49 + **websockets** *(with genai)* | 🟢 SAFE | — | Serve uses no WebSockets; `websockets.legacy` deprecation is a warning to 2030, not a break. |
| **pyinstaller** 6.19→6.20 + **hooks-contrib** 2026.1→2026.5 | 🟢 SAFE *(build-verify)* | build | Point bump; spec is Mac-MLX-only with explicit `collect_all("mlx")` + curated datas/hiddenimports. Desktop ship path → re-run `check-bundle-manifest.sh` + `doctor --self-test` after. |
| **setuptools** 80.10.2→82.0.1 | 🟢 SAFE | build | Transitive build dep; nothing in `bristlenose/` imports `setuptools`/`pkg_resources` at runtime. |
| **mypy** 1.19.1→2.1.0 | 🟢 SAFE | — | Informational gate, not a hard CI gate (CLAUDE.md). A 2.0 stricter-inference change at worst adds advisory diagnostics; can't break install/tests/ship. |
| **scikit-learn** 1.8→1.9, **scipy** 1.17.0→1.17.1, **hdbscan** 0.8.42→0.8.44 | 🟢 SAFE | — | Not imported in `bristlenose/` (clustering s10/s11 is LLM-driven). Transitive via sentence-transformers/presidio. hdbscan `scikit-learn>=1.6` + `numpy<3` (ok). |
| **The patch/minor utility tail** — requests 2.34.2, urllib3 2.7.0, certifi, idna, charset-normalizer, chardet 5→7, more-itertools 10→11, pipdeptree 2→3, lxml 6.1.1, tiktoken 0.13, jiter 0.15, regex 2026.5.9, phonenumbers 9.0.31, sqlmodel 0.0.38, SQLAlchemy 2.0.50, sqladmin 0.27.0, Mako, anyio, click, coverage, filelock, fsspec, google-auth, httptools, markdown-it-py, mpmath, packaging, pathspec, platformdirs, pyasn1, Pygments, pytest/-asyncio/-cov, python-dotenv, python-multipart, ruff 0.15.16, smart_open, srsly/preshed (spaCy patch), tomli, typeguard, watchfiles, wrapt, cyclonedx, cloudpathlib, docstring_parser, pydantic_core/-settings | 🟢 SAFE | — | All patch/minor within current majors, or transitive with no `bristlenose/` import site. sqladmin 0.27 safe (it's the *gate* on WTForms, not itself broken). **Security-take within this row:** urllib3 2.7.0 / requests 2.34.2 / lxml 6.1.1 clear open OSV advisories. |

<!-- Verdict legend: 🔴 WILL-BREAK · 🟡 RESOLVER-NON-EVENT · 🟢 SAFE ·
     ❔ UNKNOWN (couldn't look) · ⚠️ LATENT (orthogonal). -->

### The guaranteed breakages (act here first)

Three reds, all **resolver-level** (loud, early, cheap — no silent runtime break in
this tail, because our code imports none of the offending packages):

1. **tokenizers 0.23.1 lone** — `transformers` 5.10.2 *still* caps `tokenizers<=0.23.0`
   (deps.dev-verified; the initial "5.10 floats the cap" hypothesis was wrong). Hold
   tokenizers at 0.22.x; it waits for a transformers release whose cap admits 0.23.1.
   Lands inside the `minor-and-patch` group PR, so that grouped PR goes red whenever it
   tries to pull 0.23.1 — needs a per-package ignore.
2. **WTForms 3.2.2 lone** — `sqladmin` (0.23 and 0.27) caps `wtforms<3.2`. Hold at 3.1.x.
3. **cryptography 48 ↔ presidio — a mandatory pair, not a lone bump.** crypto 48 + presidio
   2.2.360 = red; presidio 2.2.362 + crypto 44 = red; crypto 48 **+** presidio 2.2.362 =
   green. Also a security move (two open crypto GHSAs).

### The non-events (no action; know why)

- **websockets 16.0** — `google-genai` 1.62.0 caps `websockets<15.1.0`; lone PR can't
  resolve. Un-gates the moment genai reaches 2.x (`websockets<17.0`) — and Entry 1 already
  greens genai 2.x. No runtime stake. Take *with* the genai bump, never before.

### The safe wave (take together)

- **PII / security wave (atomic):** presidio-analyzer 2.2.362 + presidio-anonymizer 2.2.362
  + **cryptography 48.0.0**. All three or none. Security-driven — highest-priority merge.
- **HF / transcription wave (co-resolving):** transformers 5.10.2 + sentence-transformers
  5.5.1 + huggingface_hub 1.17 + hf-xet 1.5.0 + ctranslate2 4.7.2 + onnxruntime 1.26 +
  mlx/mlx-metal 0.31.2 + torch 2.12 — **but tokenizers stays at 0.22.x.**
- **Independent greens (any order):** typer 0.26.7 + typer-slim, uvicorn 0.49 (+ websockets
  16 *with* genai 2.x), av 17, mypy 2.1, setuptools 82, scikit-learn 1.9 / scipy 1.17.1 /
  hdbscan 0.8.44, sqladmin 0.27 (WTForms stays 3.1), sqlmodel 0.0.38, SQLAlchemy 2.0.50,
  the whole patch/minor tail.
- **pyinstaller 6.20 + hooks-contrib 2026.5** — safe but **build-verify after** (the two
  bundle gates) since it's the desktop ship path.

### The unknowns (couldn't look)

None. Every bump grounded against installed metadata and/or deps.dev GetRequirements;
every web/OSV query returned. No `PackageNotFoundError`, no empty set, no laundered green.

### Recommendations

1. **Add two ignore-with-predicate rules** to the pip section of `.github/dependabot.yml`,
   mirroring the spaCy-cluster pattern: hold **tokenizers** (reason "transformers caps
   `<=0.23.0`") and **WTForms** (reason "sqladmin caps `<3.2`"). Both are now Held-register
   rows above.
2. **Take the PII/security wave now** (presidio×2 + cryptography 48) — real security fix.
3. **Take the HF/transcription wave** with tokenizers pinned at 0.22.x.
4. **Pair websockets 16 with the google-genai 2.x bump** — never a lone PR.
5. **Take the independent greens** — clean, no gates.
6. **pyinstaller 6.20**: take it, then run the bundle gates before shipping a desktop build.
7. Tooling-sprint-sized wave — run `/cassandra --score` after applying to close the loop.

### Stale-register drift found while grounding

- `.github/dependabot.yml` lighthouse comment still says "CI is on 20" — CI is Node 24
  (`.tool-versions`). Same drift Entry 1 flagged; still present.
- `docs/design-platform-policy.md` pinning register "CI Node 20" / "lighthouse 12.x"
  rows are contradicted by the same doc's Pillar 1 ("CI and local-dev aligned on Node 24").
- The pinning register has no cross-reference to the ledger's Held register — a one-line
  "see `docs/dependency-premortem-log.md` § Held register for resolver-gated holds" pointer
  would stop the two registers drifting.

### Entry 1 delta

None. Grounding this pass did not change any Entry 1 verdict. Two adjacencies (not changes):
websockets 16 is the resolver-companion to Entry 1's google-genai 2.x green; the
cryptography/presidio security pair is new surface orthogonal to everything Entry 1 called.
Entry 1 stands in full.

### OUTCOME — partial (open)

- **Security wave (presidio×2 + cryptography 48):** APPLIED 2026-06-09.
  Atomic bump in `.venv` (`cryptography 44.0.3→48.0.0`,
  `presidio-analyzer 2.2.360→2.2.362`,
  `presidio-anonymizer 2.2.360→2.2.362`). Pre-bump OSV count on
  cryptography 44.0.3: three open advisories per `--watch` grounding;
  post-bump: zero. `pytest tests/` green (3078 passed / 7 skipped /
  42 xfailed / 168s). `ruff check .` clean. `pip check` clean (the
  `torch 2.10.0 is not supported on this platform` line is pre-existing
  macOS-arm64 noise unrelated to this wave).
- **WTForms 3.1.2→3.2.2 + sqladmin 0.23.0→0.27.2 (atomic pair):** APPLIED
  2026-06-09 as part of the graduated-holds wave (Branch 2). Predicate met
  — sqladmin 0.27.2 (2026-06-08) floated `wtforms<3.3`. Took the pair;
  pytest tests/ green (3078 pass / 7 skip / 42 xfail / 243s). Note that
  sqladmin actually jumped 0.23.0→0.27.2 (Entry 2 grounded against 0.23.0,
  not 0.27.0); the 0.23→0.27 minor gap was implicitly green per Entry 2 row
  18 ("sqladmin 0.27 safe").
- All other Entry-2 verdicts remain UNTESTED — those bumps haven't landed.

### SCORE — partial

- **Security wave atomic (presidio×2 + cryptography 48)** → 🟢 **HIT.**
  Prophecy was SAFE-as-trio / WILL-BREAK as lone bumps. Took the trio;
  tests green, dep-graph consistent, OSV count for crypto dropped to 0.
  Lesson: the deps.dev-verified mandatory-pair framing was correct — the
  bump was not litigable as "just upgrade crypto."
- **WTForms 3.2.x (with sqladmin 0.27.2 pair)** → 🟢 **HIT.** Prophecy was
  RESOLVER-WILL-BREAK as lone bump, then GRADUATED via `--watch` when
  sqladmin 0.27.2 dropped the cap. Pair taken same day; no break. Lesson:
  the predicate pattern works — Cassandra caught the cap-float within 24h
  of the sqladmin release.
- Everything else (tokenizers hold, HF wave, numpy trio, independent
  greens): pending — not yet merged.

---

## `--watch` — 2026-06-09 — held-register re-examination

Trigger: maintenance-overdue reminder on the May-2026 quarterly dep
review (TODO.md L64); user asked to ground Cassandra against current
state before any execution.

**Grounded against:** installed metadata + **deps.dev v3 (live)** + OSV.

### Held register — delta since 2026-06-05

| Row | Verdict | Receipt |
|-----|---------|---------|
| **thinc** (major) | still held | No spaCy 4 GA; predicate unmet. |
| **weasel** (major) | still held | Same wave as thinc. |
| **confection** (major) | still held | Same wave as thinc. |
| **starlette** 1.x | **GRADUATED** | FastAPI 0.136.3 requirements now `starlette>=0.46.0` — cap dropped entirely (deps.dev verified 2026-06-09). Wave is live: pair fastapi 0.129→0.136.3 + starlette 0.52→1.2.1, atomic. |
| **tokenizers** 0.23.1 | still held | transformers 5.10.2 (latest, 2026-06-04) still pins `tokenizers<=0.23.0,>=0.22.0`. Predicate unmet. |
| **WTForms** 3.2.2 | **GRADUATED** | sqladmin **0.27.2** (2026-06-08) floated to `wtforms>=3.1,<3.3` (deps.dev verified). Pair: sqladmin 0.27.0→0.27.2 + WTForms 3.1.2→3.2.x. |

### New security pressure noted

cryptography 44.0.3 OSV count: **3 open advisories on 2026-06-09**
(was 2 on 2026-06-05; PYSEC-2026-35 added). Resolved by the Entry 2
security wave applied above.

### Stale-register drift — fixed in the graduated-holds wave

- `.github/dependabot.yml` lighthouse comment "CI is on 20" → corrected
  2026-06-09 to reflect Node 24 + the real reason for keeping the ignore
  (perf-baseline re-pin cost on a deliberate lighthouse-13 audit).
- `docs/design-platform-policy.md` "CI Node 20" / "lighthouse 12.x"
  drift remains — out of scope for this branch; queued for a separate
  policy-doc sweep.

---

## Entry 5 — 2026-07-29 — GitHub Actions pins (`.github/workflows/*.yml`)

- **Grounded against:** each action's `action.yml` read at every candidate
  major tag via `gh api repos/<r>/contents/action.yml?ref=<tag>` (runtime
  `runs.using:` verified first-hand, not inferred), upstream release notes
  via `gh api repos/<r>/releases`, the **actions/runner C# source**
  (`src/Runner.Common/Util/NodeUtil.cs`,
  `src/Runner.Worker/Handlers/HandlerFactory.cs`,
  `src/Runner.Worker/JobExtension.cs`,
  `src/Runner.Common/Constants.cs`), the deprecation changelog
  (github.blog 2025-09-19), plus call-site greps across
  `.github/workflows/` and the pinning register.
- **Prior calibration applied:** 4 prior entries, 4 hits, 0 misses, 0
  false-alarms — but **all four were pip/npm. There is no GitHub-Actions
  coupling-cluster precedent in this ledger.** Two lessons do transfer:
  (1) *read the upstream metadata, never the headline* — here that meant
  reading `action.yml` at each tag and the runner's own source, which
  overturned two premises in the briefing I was handed (see "Briefing
  premises corrected" below); (2) a 0-false-alarm record is earned
  permission to say **green loudly**. This entry is a field of greens and
  says so without hedging.
- **Candidate set:** the 11 action pins across 9 workflows, plus the
  `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` mechanism itself.

### New cluster — name it: **GitHub Actions runtime (a fan, not a chain)**

This does not behave like any pip/npm cluster in this ledger. There are
**no inter-action version caps** — no action's metadata constrains another's,
so there is no resolver surface at all and no "atomic wave" requirement.
What couples them is a *single shared external axis*: the runner-provided
Node runtime. N actions each pinned independently to the same axis — a fan,
not a chain. Consequences:

- **No 🟡 RESOLVER-NON-EVENT verdicts are possible here.** Nothing can be
  gated by an upstream cap. Actions fail at *runtime* or not at all.
- **Composite actions hide transitive runtimes.** `runs.using: composite`
  is not "unaffected by the Node migration" — it delegates to sub-actions
  that have their own runtimes, invisible to any `outdated`-style table.
  `actions/attest-sbom@v2` is the live example (below).
- Recommend adding to the catalog in `docs/design-dependency-premortem.md`.

### The three central questions, answered from the runner source

**Q1 — Is `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` still load-bearing?**
**No. It is a confirmed no-op, and it never did what its comment claims.**

`NodeUtil.DetermineActionsNodeVersion()` resolves in strict phase order:

```csharp
if (requireNode24) { return Node24; }              // Phase 3
...
if (useNode24ByDefault) {                          // Phase 2 — LIVE since 2026-06-16
    if (allowUnsecureNode) { return Node20; }
    return Node24;                                 // forceNode24 never consulted
}
if (forceNode24) { return Node24; }                // Phase 1 — dead branch
return Node20;
```

Phase 2 (`actions.runner.usenode24bydefault`) went live **16 June 2026** and
returns `node24` *without ever reading* `forceNode24`. The variable is only
consulted in the Phase-1 branch, which is now unreachable. Under Phase 3
it is short-circuited even earlier.

**And it never silenced the annotation.** `HandlerFactory.cs` buckets a
node20-declared action by its *resolved* version: resolving to node24 adds
it to `UpgradedToNode24Actions`, and `JobExtension.cs:998-1004` emits
`context.Warning(...)` — a real annotation — for exactly that bucket:

> `Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: {list}.`

So setting `FORCE_` moved us from the `DeprecatedNode20Actions` warning to
the `UpgradedToNode24Actions` warning. **Two annotations, one traded for the
other.** The rationale comment at `ci.yml:10-12` ("Silence the per-step …
deprecation chatter") was *wrong when written*, not merely stale. The only
mechanism that removes the annotation is bumping the action to a
node24-native major — then `nodeData.NodeVersion == node24` takes the
`else if` branch in `HandlerFactory`, which tracks nothing and warns nothing.

**Q2 — Cosmetic or functional? Chase the punycode suspicion.**
**Cosmetic. The suspicion does not survive the primary source.**

`upload-artifact` PR #744 and `download-artifact` PR #451 both describe the
symptom verbatim:

> `(node:1234) [DEP0040] DeprecationWarning: The punycode module is deprecated. Please use a userland alternative instead.`

The fix bumps `@azure/storage-blob` to `^12.29.1` (swapping deprecated
`@azure/core-http` for `@azure/core-rest-pipeline`). It is a **stderr
DeprecationWarning, not a functional break** — `punycode` is still present
in the Node 24 runtime. "Forced onto node24" **is** equivalent to "built for
node24" for every action in this candidate set; the only observable delta is
log noise. Verdicts stay green on the merits, not on the annotation.

**Q3 — Is there a hard deadline?**
**Yes, but it is a non-event for this repo.** `Constants.cs:211-212`:

```csharp
public static readonly string Node24DefaultDate = "June 16th, 2026";
public static readonly string Node20RemovalDate = "September 16th, 2026";
```

16 Sept 2026 removes the **node20 binary** from the runner. That kills the
`ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` escape hatch — which this repo
does not use (grep clean). Our node20-declared actions are *already* being
force-run on node24 and will continue to be. **Nothing breaks on 16 Sept.**
The one real forward deadline is CodeQL: **v3 stops receiving updates in
December 2026** (github.blog 2025-10-28), so v3 silently stops gaining new
analysis capability rather than failing.

### Prophecy

| Bump (from→to) | Verdict | Surface | Blast radius & receipt |
|----------------|---------|---------|------------------------|
| **actions/checkout** v4→**v7** | 🟢 SAFE | — | v5 = first node24 (`action.yml@v5: using: node24`), runner floor v2.327.1 — all runners GitHub-hosted, satisfied free. v6's "persist creds to a separate file" (PR #2286) is inert: **nothing reads `.git/config` creds or re-uses the checkout token** — grep clean; `release.yml:154` passes `GH_TOKEN: ${{ github.token }}` explicitly. v7 blocks fork-PR checkout under `pull_request_target`/`workflow_run` (PR #2454) — **grep clean, only `workflow_call` is used** (`release.yml:20` → `ci.yml`). 10 call sites. |
| **actions/setup-python** v5→**v7** | 🟢 SAFE | — | v6 = node24. v7 removes the `pip-install` input (PR #1336) — `grep -rn "pip-install" .github/` **clean**. All 7 call sites pass only `python-version-file: '.tool-versions'`. |
| **actions/setup-node** v4→**v7** | 🟢 SAFE | — | v5 auto-caches **only when `package.json` has a `packageManager` field** (PR #1348) — absent from `frontend/package.json` and `e2e/package.json`, and there is **no root `package.json`**. v6 narrows auto-cache to npm (moot). v7 = ESM + new cache outputs. `ci.yml:131`'s explicit `cache: "npm"` + `cache-dependency-path` is untouched; the other 3 sites pass no `cache:`. |
| **actions/upload-artifact** v4→**v7** | 🟢 SAFE | — | v5 is *still node20*; **v6 is the first node24** (release note: "v5 had preliminary support … v6 by default will run on Node.js 24"). v7 adds `archive:` (opt-in, default `true`) + ESM. All 6 call sites use defaults with `name:`/`path:`/`retention-days:` only. |
| **actions/download-artifact** v4→**v7** | 🟢 SAFE | — | v5's breaking path change is **`artifact-ids:`-only** — `grep -rn "artifact-ids"` **clean**; all 4 sites use `name:` (`release.yml:121,147`, `snap.yml:48,80`). v6 *still node20*; **v7 is the first node24**. |
| **actions/download-artifact** v7→**v8** | 🟢 SAFE ⚠️ **LATENT** | runtime | The `Content-Type`-based decompress skip only affects artifacts uploaded with `archive: false` — we never set it, so every download is a zip and unzips as before. The `.snap` concern is a non-issue for that reason. **Latent:** `digest-mismatch` now defaults to `error` (was warn, PR #461) — correct hardening, but it converts a previously-survivable transfer flake into a red run. Fires only on real corruption; do not pre-emptively set it back to `warn`. |
| **github/codeql-action** v3→**v4** | 🟢 SAFE | — | `init/action.yml@v4` and `analyze/action.yml@v4` both `using: node24`. v4's removed input is `add-snippets` — `grep -rn "add-snippets" .github/` **clean**. Min CodeQL bundle 2.17.6; GitHub-hosted ships `codeql-bundle-v2.26.1`. The GHES ≤3.18 gate is irrelevant (github.com). `codeql.yml` passes only `languages` / `queries: security-extended` / `category`. **v3 stops receiving updates Dec 2026** — this is the one bump with a real forward clock. |
| **actions/attest-sbom** v2→**v3** | 🟢 SAFE — **and the correction that matters** | runtime (transitive) | **The briefing's table says "NOT node-related — `using: composite` at v2/v3/v4". That is right about the wrapper and wrong about the payload.** `attest-sbom@v2`'s composite body SHA-pins two **node20** sub-actions: `actions/attest-sbom/predicate@…534423` (`using: node20`) and `actions/attest@ce27ba3` = **v2.4.0** (`using: node20`, verified). So `attest-sbom@v2` **is** a node20 surface — on the release attestation path — invisible to any runtime table that stops at the wrapper. v3 fixes both (`predicate@2.0.0` + `actions/attest@v3.0.0`, both node24). |
| **actions/attest-sbom** v2→**v4** | 🟢 SAFE ⚠️ **LATENT — do not take** | — | v4 works, but **v4.0.0 deprecates the action** in favour of `actions/attest`, and its composite body's *first step* is literally `echo "::warning::actions/attest-sbom has been deprecated, please use actions/attest instead"`. Jumping v2→v4 **trades a node20 annotation for a deprecation annotation** and starts a migration clock. **v3 is the sweet spot: node24, no self-deprecation warning.** Take v3; schedule the `actions/attest` migration separately. |
| **peter-evans/repository-dispatch** v3→**v4.0.1** | 🟢 SAFE | — | `action.yml@v4: using: node24`; v4.0.0 is a runtime-only major, v4.0.1 fixes the node version declaration (PR #433). **No input changes** — `token`/`repository`/`event-type`/`client-payload` all unchanged. SHA-pinned at `release.yml:206`; **the bump must move the SHA *and* the trailing comment together** → `28959ce8df70de7be546dd1250a005dd32156697  # v4.0.1`. Blast radius is the Homebrew tap dispatch, which fails **silently** (cf. CLAUDE.md's release-pipeline gotchas) — verify the tap repo receives `update-formula` on the next release. |
| **snapcore/action-build** v1.3.0 | ⏸ **HELD / WATCHING** | — | `action.yml@v1.3.0: using: 'node20'`. **v1.3.0 is the newest tag upstream** (`gh api repos/snapcore/action-build/tags` → `v1.3.0, v1`); `releases/latest` 404s. No node24 release exists to take. Mitigant: `snap.yml` is `on: workflow_dispatch` **only** (auto-triggers parked May 2026, `snap.yml:3-8`), so the annotation surfaces only on manual runs. |
| **snapcore/action-publish** v1.2.0 | ⏸ **HELD / WATCHING** | — | `action.yml@v1.2.0: using: 'node20'`. v1.2.0 is the newest tag upstream. Same predicate, same parked-workflow mitigant. |
| **pypa/gh-action-pypi-publish** `release/v1` | 🟢 SAFE (non-candidate) | — | Docker action — outside the Node migration entirely. **Leave the moving tag alone**; `release.yml:127-133` documents why (Trusted-Publishing OIDC must track upstream). |

### The guaranteed breakages (act here first)

**None.** Zero 🔴s. Every action in the set either has a node24-native major
whose breaking changes land on surfaces this repo demonstrably does not use
(all greps clean), or has no newer release at all. Said plainly so the
contrast is usable: **this is a green sweep, and the reason it looks scary
is an annotation, not a fault.**

### The non-events (no action; know why)

Structurally impossible in this ecosystem — see "a fan, not a chain" above.
There are no inter-action caps, so nothing can be resolver-gated. The
nearest equivalent is the two snapcore holds, which are blocked by
*absence of an upstream release*, not by a cap.

### The safe wave (take together)

All ten greens in **one sweep commit**. They are mutually independent (no
cluster ordering to respect), and a single CI run exercises checkout ×10,
setup-python ×7, setup-node ×4, upload-artifact ×6, download-artifact ×4,
codeql ×3, attest-sbom ×1, repository-dispatch ×1. Two carve-outs:

- **attest-sbom → v3, not v4** (see the LATENT row).
- **download-artifact → v8** is fine; keep `digest-mismatch` at its new
  `error` default.

Note per CLAUDE.md: a workflow-only change **ships no wheel bytes** → re-use
the existing version tag, do not bump.

### The unknowns (couldn't look)

**None.** Every runtime fact was read first-hand from `action.yml` at the
specific tag; every behavioural claim traces to an upstream release note, a
merged PR body, or the runner's own source. No `gh api` call returned empty
and was laundered into a green. The one place I deliberately did *not*
guess: whether snapcore intends a node24 release — that is unknowable from
here, which is precisely why it is a **hold with a predicate** rather than
a green or a red.

### Briefing premises corrected while grounding

The candidate set I was handed was accurate on 11 of 11 runtime facts
(independently re-verified — including the counter-intuitive ones:
`upload-artifact@v5` and `download-artifact@v5`/`v6` really are still
node20). Three premises did not survive:

1. **"`attest-sbom` … NOT node-related."** It is — transitively, via two
   SHA-pinned node20 sub-actions. Composite ≠ exempt.
2. **"the lighthouse ignore comment in dependabot.yml ('CI is on 20')".**
   Already fixed on 2026-06-09 (`--watch` pass). The live comment reads
   "CI satisfies (Node 24 per `.tool-versions`)". *The briefing's stale
   premise was itself the drift.* Only the **policy-doc** half is still rotten.
3. **"punycode is where forced-onto-node24 ≠ built-for-node24."**
   Reasonable suspicion, but the PRs describe a DeprecationWarning.

### Cadence call — **single sweep commit, not a tooling sprint**

The register's trigger (§"Quarterly tooling review" item 6) is "three
deferred majors"; on a headline count of ten this looks like a sprint. It
is not, and the count is the wrong instrument here:

- A tooling sprint (1–2 days) exists to absorb **cluster risk** — atomic
  waves, resolver conflicts, ABI coupling, test-surface churn. This
  ecosystem has **none of that**. There is nothing to sequence.
- The change is ten `uses:` lines plus seven `env:` deletions. No wheel
  bytes, no lockfile, no runtime code, no test surface.
- Verification is **one green CI run**, which the repo already runs.

Equally: it is **above** the per-PR cost. Ten separate Dependabot PRs, each
needing a CI cycle and a merge, is exactly the tail-chasing the cadence
policy was written to prevent. **One sweep commit, one CI run, one review.**
That respects "move as a wave, not a phone call" without inflating a
half-hour edit into a sprint.

### Recommendations (ordered)

1. **(c) Fix the stale register rows first — it is free, and this is the
   third pass.** `docs/design-platform-policy.md:90` "CI Node 20" and the
   "lighthouse 12.x" row. Do this *first* because it costs nothing and
   because leaving it un-actioned a third time is how the register stops
   being trusted at all. **Structural fix, not another re-flag** — see below.
2. **(a) + (d) together, in one sweep commit.** Bump the ten greens
   (attest-sbom → **v3**, not v4) **and** delete
   `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` from all seven workflows plus the
   now-false rationale comment at `ci.yml:10-12`. These belong in the same
   commit: the env var's only justification was the annotation, and the
   bumps are what actually remove it. Deleting it alone would be a
   behaviour-neutral no-op; bumping alone would leave dead config with a
   misleading comment.
   - **The `mac-build.yml` / `secret-scan.yml` inconsistency dissolves
     here.** Do **not** add the var to the two workflows missing it —
     remove it from the seven that have it, and the fleet is consistent
     *and* correct. (Those two workflows were never wrong; they were
     accidentally right.)
3. **(b) Add the `github-actions` ecosystem to `.github/dependabot.yml` —
   but *after* the sweep lands.** This is the systemic fix and the actual
   root cause: with no `github-actions` block, nothing was watching, which
   is why pins drifted 1–4 majors unnoticed. Ordering matters — added
   *before* the sweep it opens ~10 PRs on Monday; added *after*, the first
   run is a near-no-op. Suggested shape: `directory: "/"`, weekly/Monday,
   `groups: { actions: { patterns: ["*"] } }` so the fan arrives as **one**
   grouped PR (the fan shape means grouping is safe — no inter-action
   caps), plus ignore-with-predicate rows for the two snapcore SHAs.
   Its omission is **accidental, not decided** — it appears nowhere in the
   policy doc's "Open questions / known gaps".

**What not to do:**

- **Do not take `attest-sbom@v4`.** v3 is strictly better today.
- **Do not hand-force the snapcore SHAs** to any "v1" moving tag — there is
  no node24 release to force to, and un-SHA-pinning a Snap-Store-credentialed
  step for cosmetic reasons trades a warning for a supply-chain regression.
- **Do not SHA-pin `pypa/gh-action-pypi-publish`** (`release.yml:127-133`).
- **Do not run a tooling sprint** for this.
- **Do not set `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`.** It buys nothing
  and dies on 16 Sept 2026.

### Stale-register drift found while grounding

`docs/design-platform-policy.md` pinning register:

- **`CI Node 20`** (line 90) — flatly contradicted by the same document's
  Pillar 1 (line 32: "CI and local-dev are aligned on **Node 24 LTS** …
  there are no hardcoded `node-version: "20"` pins") and by `.tool-versions`
  (`node 24`). Its re-check date (June 2026) is now **past**.
- **`lighthouse 12.x` — "Lighthouse 13 requires Node ≥22.19; CI is on 20"**
  — the stated *reason* is false. `.github/dependabot.yml` already carries
  the corrected reason (perf-baseline re-pin cost). The register is now
  *behind its own ignore file*.

**I flagged both in Entry 1 (log lines 119-124) and again in Entry 2
(lines 254-262). The dependabot half was fixed in the 2026-06-09 `--watch`
wave; the policy-doc half was explicitly "queued for a separate policy-doc
sweep" and never happened. This is the third flag. That is the Cassandra
condition in its literal form — correct, cited, repeatedly ignored — and
the honest reading is that the failure is mine, not the reader's: I kept
filing prose warnings into a ledger nobody re-reads instead of proposing
the edit that removes the failure mode.**

**Structural fix so it sticks this time — delete, don't re-word:**

> **A pinning-register row may not restate a value that lives in a tracked
> config file. It may only *name the file*.**

Applied:

- The **`CI Node 20` row should be deleted outright**, not corrected. It
  describes a pin that no longer exists; `.tool-versions` is the SSOT and
  Pillar 1 already says so. It should have died the day `.tool-versions`
  landed. A "corrected" row restating `Node 24` would rot again at the next
  LTS.
- The **`lighthouse` row's reason should cite `.tool-versions`**, not
  restate a Node number ("requires Node ≥22.19; see `.tool-versions` for the
  current CI Node").

This is mechanically checkable: **any register row containing a literal
version number that also appears in a tracked config file is drift by
construction.** That is a grep, and a candidate `/cassandra --watch` check.

Also still open from Entry 2 and worth folding into the same edit: the
pinning register has **no cross-reference to this ledger's Held register**.
One line — "see `docs/dependency-premortem-log.md` § Held register for
gated holds" — stops the two registers drifting apart.

### OUTCOME — open

Not yet applied. Nothing in this entry has landed.

### SCORE — pending

No verdicts scored. Tally line stays at 4 scored until `/cassandra --score`
runs against an applied sweep.

Scoring notes for the future pass — the falsifiable claims, so this entry
can be marked honestly rather than generously:

- If the sweep lands and **CI goes green with no node20 annotations**, the
  ten greens are hits and the FORCE_-is-a-no-op reading is confirmed.
- If **any** annotation survives the bump, the `HandlerFactory` reading is
  wrong and this entry took a miss on Q1.
- If `attest-sbom@v3` breaks the release attestation, that is a **miss** on
  a green — and the lesson would be that transitive composite runtimes need
  a build-level test, not just metadata reading.
- If the Homebrew tap does **not** receive `update-formula` on the first
  release after the `repository-dispatch` bump, that is a **miss** — and
  the standing hazard (silent Homebrew breakage) will have bitten again.


---

## Entry 6 — 2026-08-27 — `anthropic` major, blocking the 0.28.0 tag

- **Grounded against:** `.venv` installed metadata + **live SDK introspection** + `pyproject.toml` + `.github/dependabot.yml` + `THIRD-PARTY-BINARIES.md`
- **Prior calibration applied:** Entry 1 gave `anthropic 0.77.1→0.105.2` a 🟢 on the rationale *"Messages + tool-use API is stable across the range."* That scored a hit, but the rationale is **range-scoped to 0.x**. Applying the standing LLM-SDK heuristic ("big gaps look scary; breaks live in beta surfaces we don't call") would have produced a green here and been the **first miss**. **Tuning: at a major boundary on an SDK we call directly, the heuristic is void — introspect the installed signature.**
- **Trigger:** not a proposed bump. `check-release-ready.sh` surfaced it as inventory-vs-installed drift — **the major had already landed in the venv**, and 4246 tests had passed against it.

### Prophecy

| Bump (from→to) | Verdict | Surface | Receipt |
|----------------|---------|---------|---------|
| **anthropic** 0.122.0 → **1.1.0** (`temperature` kwarg) | 🔴 **WILL-BREAK** | runtime — silent, deterministic, 100% of Claude calls | `AsyncMessages.create` has no `temperature` and no `**kwargs`. Reproduced twice, independently: `TypeError: AsyncMessages.create() got an unexpected keyword argument 'temperature'`. Break site `bristlenose/llm/client.py:529`. Fires pre-network, so `max_retries=6` never engages |
| anthropic → `httpx2` transport swap | 🟢 SAFE | — | `httpx2 2.12.0` resolves clean; `import anthropic` OK; `truststore` already in the SBOM |
| anthropic client construction + exception classes | 🟢 SAFE | — | `AsyncAnthropic(api_key=, max_retries=)` constructs; all four caught exceptions still top-level |
| anthropic response surface | 🟢 SAFE | — | `content/model/stop_reason/usage` retained; `stop_reason` Literal still has `max_tokens`; both cache usage counters present |
| **openai** 3.0.0 → 3.5.0 | 🟢 SAFE | — | `chat.completions.create` **keeps** `temperature` — verified by introspection on installed 3.5.0 |
| **google-genai** 2.18.1 → 2.20.0 | 🟢 SAFE | — | `GenerateContentConfig.model_fields` **keeps** `temperature` — verified on installed |
| Live-model acceptance of `temperature` via `extra_body` | ❔ UNKNOWN | — | Binds and reaches transport, but the vendor guide scopes it to *"an older model that still does"*. Not verified against a current model; a live call was deliberately not spent |

### Why 4246 green tests proved nothing

Every anthropic test mocks `messages.create` with `AsyncMock`/`MagicMock`. A mock accepts `temperature=` *and* `bogus_kwarg=` without complaint, so the suite cannot see this class of defect at all.

**And the failure shape is the worst available.** `preflight/api_key.py:212-216` validates the key with a `messages.create` that does **not** pass `temperature` — so validation succeeds, `configure` reports the key good, `doctor` goes green, and the run dies at the first pipeline LLM call with a raw `TypeError` that `failure_classifier` has no bucket for. Green preflight, mid-run abandonment, no actionable cause.

### Recommendation (order is load-bearing)

1. `pyproject.toml:33` → `"anthropic>=0.39,<1"`. One line, no code change, restores the combination the tests and months of real runs actually exercised.
2. **Rebuild the venv so anthropic resolves `<1`.** Easy to miss and the one that matters for the Mac: `build-all.sh` bundles from this venv, so a ceiling without a rebuild leaves PyPI safe while TestFlight ships the break.
3. Regenerate `THIRD-PARTY-BINARIES.md` **only after** step 2 — regenerating now bakes 1.1.0 into a shipped SBOM that accurately records a broken combination.
4. Then tag.
5. Post-tag, do the 1.x migration deliberately, as a wave with the two other unexamined majors.

### New cluster named

**`anthropic → httpx2` (transport-major coupling).** `anthropic 1.x` and `openai 3.x` have both moved to `httpx2`; `google-genai` still pins `httpx<1.0`. The venv now carries both stacks. The next SDK major that moves transports will look isolated and won't be. Proposed for the catalog in `docs/design-dependency-premortem.md`.

### OUTCOME — open
<!-- filled in by /cassandra --score once the ceiling is applied and 0.28.0 ships -->

### SCORE — pending
<!-- The 🔴 is already reproduced, so it scores on whether the ceiling landed before the
     tag. The six 🟢s score only if the bumps are actually exercised; a SAFE never applied
     is untested, never a free hit. The ❔ is unscoreable until someone spends a live call. -->
