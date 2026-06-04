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
