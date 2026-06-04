# Dependency pre-mortem ledger

Cassandra's prophecies and their outcomes. One entry per pre-mortem pass.
Append-only; never renumber. The running tally lets us see, over time,
how well the oracle calls it.

See `docs/design-dependency-premortem.md` for how this works and
`.claude/skills/cassandra/SKILL.md` for how to add an entry (Mode A),
score one (Mode B `/cassandra --score`), or re-examine the holds below
(Mode C `/cassandra --watch`).

**Tally:** 0 prophecies scored — 0 hits, 0 misses, 0 false-alarms.

## Held register

The standing watch list. Each row is a **`(reason, release-predicate)`**
obligation, not a dead pin — `/cassandra --watch` re-evaluates each
predicate against fresh deps.dev / OSV metadata and graduates the row to
a fresh pre-mortem the day its coupling cluster becomes safe to take "as
a wave." An ignore in `.github/dependabot.yml` without a row here is a
tombstone; fix it by adding the row.

| Held bump | Cluster | Reason (blocks now) | Release-predicate (lifts it) | Last watched | Status |
|-----------|---------|---------------------|------------------------------|--------------|--------|
| **thinc** (major) | spaCy ecosystem | spaCy 3.8.x pins `thinc<8.4`; thinc 9.x is spaCy-4 era | spaCy 4 reaches GA **and** the cluster (spacy+thinc+weasel+confection+en_core_web_lg) co-resolves; take atomically | 2026-06-04 | held |
| **weasel** (major) | spaCy ecosystem | spaCy 3.8.x pins `weasel<0.5`; weasel 1.0 *requires* `confection>=1.0`, mutually exclusive with thinc 8.3's `confection<1.0` | same spaCy-4 wave as thinc | 2026-06-04 | held |
| **confection** (major) | spaCy ecosystem | thinc 8.3 pins `confection<1.0` | thinc moves to 9.x (⇒ spaCy 4 wave) | 2026-06-04 | held |
| **starlette** 1.x | FastAPI / starlette | FastAPI caps `starlette<1.0` (installed metadata); the PR can't resolve | FastAPI floats its starlette cap past 1.0 (check `GetRequirements` for fastapi); then bump fastapi+starlette together | 2026-06-04 | held |
| **tokenizers** 0.23.1 | HF transformer stack | `transformers` 5.7.0 **and** 5.10.2 both pin `tokenizers<=0.23.0` (deps.dev verified 2026-06-05) | a transformers release floats its tokenizers cap to admit 0.23.1 (`GetRequirements` for transformers: cap becomes `<0.24`/`<=0.23.1`); then move tokenizers+transformers together | 2026-06-05 | held |
| **WTForms** 3.2.2 | sqladmin / serve DB | `sqladmin` 0.23.0 **and** 0.27.0 both pin `wtforms>=3.1,<3.2` (deps.dev verified 2026-06-05) | a sqladmin release floats `wtforms<3.2` → `<3.3`/`<4` (`GetRequirements` for sqladmin); then bump sqladmin+WTForms together | 2026-06-05 | held |

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

### OUTCOME — open
<!-- filled in by /cassandra --score after the bumps are applied -->

### SCORE — pending
<!-- hit / miss / false-alarm per verdict, with evidence and the lesson -->

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

### OUTCOME — open
<!-- filled in by /cassandra --score after the bumps are applied -->

### SCORE — pending
<!-- hit / miss / false-alarm per verdict, with evidence and the lesson.
     untested is the default; a hit costs proof (CI run, lockfile diff, test). -->
