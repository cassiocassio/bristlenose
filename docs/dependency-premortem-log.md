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
| **thinc** (major) | spaCy ecosystem (now spacy+thinc only) | `spacy 3.8.16` pins `thinc<8.4.0,>=8.3.12` (installed metadata). thinc 9.1.1 is spaCy-4 era and inverts the old story — it is *thinc 9* that pins `confection<1.0.0`, against spaCy 3.8.16's `confection<2.0.0,>=1.3.2` | **Re-specified 2026-09-03.** Was *"spaCy 4 reaches GA"* — a predicate that could not fire: latest stable is **3.8.16 (2026-08-24)**, actively maintained, while the 4.0 line is three dev releases, the newest **2 years 4 months old** (`4.0.0.dev3`, 2024-04-22) and the two before it **yanked**. Now the machine-checkable form: **`spacy` floats its `thinc<8.4.0` cap** — one deps.dev `GetRequirements` field. Take spacy+thinc together | 2026-09-03 | held |
| **weasel** (major) | spaCy ecosystem | _(graduated 2026-09-03 — the recorded reason was false. `spacy 3.8.16` now **requires** `weasel<2.0.0,>=1.0.0`, not the recorded `weasel<0.5`; **weasel 1.0.0 is installed in both venvs and `pip check` is clean**. It moved alone, without a pre-mortem, which is why nobody noticed. The major-ignore stays — it blocks 2.x, which spaCy does cap — but for this reason, not the recorded one)_ | n/a — graduated. Falsifies the "one atomic spaCy-4 wave" framing: spaCy 3.8.x floats its own caps without a major | 2026-09-03 | **graduated** |
| **confection** (major) | spaCy ecosystem | _(graduated 2026-09-03 — recorded reason false. `spacy 3.8.16` requires `confection<2.0.0,>=1.3.2` and `thinc 8.3.13` requires `confection<2.0.0,>=1.1.0`, not the recorded `confection<1.0`; **1.3.3 is installed**. Major-ignore stays, blocking 2.x)_ | n/a — graduated | 2026-09-03 | **graduated** |
| **starlette** 1.x | FastAPI / starlette | _(graduated 2026-06-09 — FastAPI 0.136.3 dropped the `starlette<1.0` cap, pair pre-mortemed in the graduated-holds wave)_ | n/a — graduated | 2026-06-09 | **graduated** |
| **anthropic** 1.x | LLM SDKs · anthropic→httpx2 | The mechanism stands — 1.x's `messages.create` is keyword-only, no `temperature`, no `**kwargs` — but **both halves of the predicate are now met.** Code: `client.py` sends temperature via `extra_body` (`09bb5e82`), which exists on 0.125.0 and 1.3.0 alike, so the wire request is unchanged and the kwarg that broke is gone. **Proven live 4 Sep 2026**, not read: `claude-sonnet-4-6` (a sunset-list model) returned a valid `QuoteExtractionResult` with its temperature carried in `extra_body`. Product: slider removed (`fe145d32`). `test_every_kwarg_we_send_exists_on_the_installed_sdk` now introspects the real signature, closing the mocked-kwarg blind spot Entry 6 was lost in | Nothing outstanding on our side. Re-pre-mortem the `httpx2` transport wave (anthropic 1.x + openai 2→3 + google-genai 1→2) and float the ceiling | 2026-09-04 | **ready — re-pre-mortem the wave** |
| **mcp** 2.1+ | assistant surface · mcp→mcp-types (pinned `==`) | 2.1 masks any exception that is not a `ToolError`/`MCPError` behind a generic `Error executing tool <name>`, so our refusals (raised as `ToolInputError`, a bare `ValueError`) lost their reason. **Fixed `e6a161c3`** — and the fix was a base class, not the seven-site refactor this row assumed: `ToolInputError` now inherits the SDK's `ToolError` (guarded import; the module still imports without the optional `mcp` extra, proven in a subprocess), and the sanitised server-error message rides the same class so its pointer to `bristlenose.log` survives too. **Verified against the held version itself**: a scratch venv on mcp 2.1.1 + mcp-types 2.1.1 runs `test_mcp_server.py` **73/73**, and pinned 2.0.0 stays 73/73. (Real SDK, not a live network call — MCP is local) | Float the ceiling as the **pair** (`mcp` + `mcp-types`, pinned `==`) and re-pre-mortem | 2026-09-04 | **ready — float the pair** |
| **tokenizers** 0.23.1 | ~~HF transformer stack~~ — **wrong cluster; it is the faster-whisper transcription path** | _(RETIRED 2026-09-03, ignore dropped in `a6f8cc66` — a tombstone twice over. (1) Predicate met: `transformers 5.16.1` requires `tokenizers<0.24.0,`**`>=0.23.1`** — the cap floated and 0.23.1 became its *floor*. (2) The coupling has no referent here: `transformers` is installed in **neither** venv, is absent from `pyproject.toml` and `bristlenose-sidecar.spec`, and nothing under `bristlenose/` imports it; the real dependent is `faster-whisper 1.2.1` → `tokenizers<1,>=0.13`, which forbids nothing. A Dependabot ignore never constrains pip's resolver, only its PRs — which is why 0.23.1 installed itself anyway and the rule ended up blocking a version we ship)_ | n/a — retired | 2026-09-03 | **retired** |
| **WTForms** 3.2.2 | sqladmin / serve DB | _(graduated 2026-06-09 — sqladmin 0.27.2 floated `wtforms<3.3`, pair pre-mortemed in the graduated-holds wave)_ | n/a — graduated | 2026-06-09 | **graduated** |
| **cryptography** 49/50 | **presidio ceiling** (new cluster) · presidio→cryptography | `presidio-anonymizer 2.2.364` — **the latest release** — pins `cryptography>=48.0.1,<49.0.0`, so we sit exactly on the floor with nowhere to go. Three open advisories on 48.0.1 (CVE-2026-69247/69248/69249; the PYSEC and GHSA ids are aliases of the same three, so it is three, not six), fixed in 49.0.0 and 50.0.0. **It ships**: `_internal/cryptography-48.0.1.dist-info` is in the built sidecar. Exposure assessed, not assumed — all three are X.509 path-validation or PKCS#7 surfaces we never call; `s07_pii_removal.py:468` uses presidio's `replace` operator only, so we never enter its crypto path, and cryptography otherwise arrives via `pyjwt[crypto]` and `google-auth` for signature verification | `presidio-anonymizer` floats to `cryptography<50` or `<51`; then move presidio-anonymizer + cryptography **atomically**, as the 2026-06-09 security wave did with 44→48 | 2026-09-03 | held |
| **numpy** 2.5+ | **presidio ceiling** — *not* the numpy-ABI cluster any more | **The binding cap moved and it is no longer numba.** `numba 0.67.0` floats to `numpy<2.6`; `presidio-analyzer 2.2.364` (latest) pins `numpy>=1.19.0,<2.5.0`. A real resolve lands on 2.4.6 at 3.11, 3.12, 3.13 and 3.14 alike, so this reads as a floor problem and is not one | presidio-analyzer floats its numpy cap **and** the Python floor question is settled (numpy 2.5.2 declares `requires_python>=3.12`). Move as the quartet numpy+numba+llvmlite+presidio-analyzer | 2026-09-03 | held |
| **websockets** 17+ | google-genai → websockets | `google-genai 2.22.0` (latest) pins `websockets<17.0`. Sole reverse-dep (`pip show websockets` → `Required-by: google-genai`; uvicorn[standard]'s is floor-only), and **zero `import websockets` in `bristlenose/`**. The resolver returns 16.1.1 on every interpreter 3.10–3.14, so the floor standing behind this cap is shadowed and buys nothing | genai floats to `websockets<18` **and** the Python floor is ≥3.11 (websockets 17.0 requires it). ⚠️ Do not hand-force: taking 17.0 under `requires-python = ">=3.10"` silently breaks the declared floor | 2026-09-03 | held |
| **@eslint/js 10 / eslint 10** | **npm peer-cap chain** (new cluster) · `@eslint/js → eslint → eslint-plugin-jsx-a11y` | The hold was being enforced on **one of three** members, so the others could walk it past the pin. `@eslint/js@10.0.1` declares `peerDependencies: {eslint: "^10.0.0"}` while eslint is major-ignored at 9.39.4, and `eslint-plugin-jsx-a11y@6.10.2` (latest) peer-caps eslint at `^9` with no eslint-10 release in existence. Unlike a pip cap this fails as **ERESOLVE at `npm ci`**, not a warning. Paid for once already: landed 2 Jul 2026 (`7cc28c44`), reverted 3 Jul (`e449aad3`), recorded at `frontend/CLAUDE.md:23`. Both missing members added to the ignore list in `a6f8cc66` | `eslint-plugin-jsx-a11y` ships eslint-10 support; then bump `eslint` + `@eslint/js` + `eslint-plugin-jsx-a11y` in **one commit** | 2026-09-03 | held |
| **snapcore/action-build** `v1.3.0` (node20) — **we are pinned to a FORK** | GitHub Actions runtime · snap build path | **The recorded predicate could never fire, because snapcore is not the publisher.** Measured 4 Sep 2026: `snapcore/action-build` is `fork=true`, `parent=canonical/action-build`. It was created 23 Sep 2024 and last pushed the *same day* — 5 stars against upstream's 45; the entire `snapcore` org has 3 public repos and its newest activity anywhere is `snapd-ci` in Jan 2025. The "chore: update to node24" PR sitting there (#1, opened 5 Apr 2026) is a PR against a fork nobody watches. Upstream `canonical/action-build` is quiet but alive — #96, #94 and #98 all open on node24, touched Apr–Jun 2026 — yet `master` is **still** `runs.using: node20` and its newest tag is the same `v1.3.0` we pin, so repointing fixes provenance, not the runtime. **Node24 risk closed 4 Sep 2026 by a real run**: after the repoint (`30483d17`, identical SHA), run 33907334405 built the snap on `canonical/action-build` under the runner's forced-node24 and produced revision 14 | **Not a version wait — a migration decision.** See the note below the table; three options, none of which is "wait for snapcore". Nothing needs deciding before 16 Sep: the blast radius is a red `snap.yml` **build** on push (publishing is `workflow_dispatch`, the channel is edge) | 2026-09-04 | held — migration decision; **node24 risk closed** |
| **snapcore/action-publish** `v1.2.0` (node20) — **also a fork** | GitHub Actions runtime · snap publish path | Same shape: `fork=true`, `parent=canonical/action-publish`, 1 star against upstream's 40, created and abandoned 23–24 Sep 2024. Its node24 PR (#1, 5 Apr 2026) has **zero comments**. Upstream has #52 and #54 open on node24 (May–Jun 2026) and `master` is still node20 at the same `v1.2.0` we pin. **Note this half has no craft-actions replacement** — `canonical/craft-actions` ships `pack` and `setup` only, no publish — so the publish path is either upstream `action-publish` or the snapcraft CLI with `SNAPCRAFT_STORE_CREDENTIALS`. **The one path skipped 59/59 is now exercised**: on 4 Sep 2026 `canonical/action-publish`, forced onto Node 24 (the runner's own warning names it), published revision 14 to `latest/edge` — confirmed in the store's channel-map, not just the run's green | Same decision as action-build; the two move together | 2026-09-04 | held — migration decision; **node24 risk closed** |

<!-- Watch grounding: deps.dev GetRequirements for the upstream caps
     (spacy→thinc, fastapi→starlette), GetVersion for publishedAt/scorecard,
     OSV for advisories. spaCy-4 GA is the single event that clears the top
     three rows as one wave. -->

### Note — the snap build path (4 Sep 2026)

The two snapcore rows above are not one stale pin, they are **two layers of
stale**: an abandoned fork of a quiet upstream, while Canonical's current
tooling moved somewhere else entirely. Options, with the trade each carries:

1. **Repoint to `canonical/*`.** Same tags, same node20, so it buys provenance
   and a predicate with visible activity behind it — not a runtime fix. Cheapest,
   and defensible on supply-chain grounds alone: we currently trust a stale fork
   of an org that is not the publisher.
2. **`canonical/craft-actions`** (pushed 2 Sep 2026, the craft-family monorepo).
   Its `snapcraft/pack` and `snapcraft/setup` are **`using: composite`**, so the
   node-runtime question does not apply to them at all — there is nothing for
   16 Sep to remove. Caveats: **v0.1.1**, 4 stars, no formal releases despite the
   repo existing since Jan 2023; **no publish action**; and the inputs differ
   (`path`/`verbosity`/`channel`/`revision`/`lxd-channel` against the old
   `path`/`build-info`/`snapcraft-channel`/`snapcraft-args`/`ua-token`/`snap`),
   so `snap.yml` needs reworking rather than repointing.
3. **Drop GitHub Actions from the snap path.** Two Canonical-hosted routes:
   **`snapcraft remote-build`** (Launchpad farm, multi-arch, hands the `.snap`
   back so **publishing stays deliberate** — needs full clones, no `--depth 1`,
   and public upload unless a private Launchpad project is registered), or
   **Build from GitHub** (snapcraft.io's native service, zero actions, six
   architectures — but it **auto-releases to edge on every merge to main**, which
   is exactly the behaviour `snap.yml` deliberately engineered out).

**The unclaimed prize is arm64.** The snap is amd64-only, which is why amd64 VMs
exist to test it from an arm64 dev machine. Both Canonical-hosted routes build
arm64 for free, which retires that dance — a larger day-to-day win than the
node24 fix that surfaced all this.

**No upstream deprecation says stop using the actions.** They are still
documented and still recommended in places, including a recent Canonical
robotics how-to. This is a fit judgement, not a forced move.


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

---

## Entry 7 — 2026-09-03 — the Aug 2026 quarterly review (9 open PRs + latent pip wave + un-ignored npm majors)

- **Grounded against:** `.venv` **and** `.venv-sidecar` installed metadata; the
  built bundle at `desktop/Bristlenose/Resources/bristlenose-sidecar/_internal/`;
  `desktop/bristlenose-sidecar.spec` excludes; `pyproject.toml`; the pinning
  register; `.github/dependabot.yml`; OSV + deps.dev + PyPI release metadata;
  `action.yml` read at each candidate tag; and the **live CI check results on
  every open PR**, which turned out to matter more than usual (below).
- **Prior calibration applied:** 4 scored, 4 hits, 0 misses, 0 false-alarms.
  Entry 6's tuning — *at a major boundary on an SDK we call directly, the
  heuristic is void; introspect the signature* — was applied to `anthropic`
  1.3.0, and then applied a **second time the same day** against a corrected
  register row claiming the break was gone. Entry 5's *"a 0-false-alarm record
  is earned permission to say green loudly"* is why the Actions set below is a
  field of greens with one merge-order red rather than five ambers.
- **Trigger:** the Aug 2026 quarterly dep review, past due (`TODO.md` — May was
  the last, executed 2026-06-09).

### Prophecy

| Bump (from→to) | Verdict | Surface | Blast radius & receipt |
|---|---|---|---|
| **#129+#132 codeql init+autobuild 3.37.8→4.37.9, merged without `analyze`** | 🔴 WILL-BREAK | runtime (CI red) | `codeql.yml:44,55,58` carry **one SHA across three actions**, and codeql-action throws if `analyze` loads a config from a different `init`. No `analyze` PR existed — `open-pull-requests-limit: 5` was exactly full. **CI confirmed it independently:** #129 and #132 are the only two of the five Actions PRs failing `Analyze (python)` and `Analyze (javascript)`. |
| **#134 anthropic `<1`→`<2`** | 🔴 WILL-BREAK | runtime — silent, deterministic, default path | `messages.create@v1.3.0` is keyword-only, no `temperature`, no `**kwargs`. Narrowed by `bb9e201d` but not cleared: `providers.py` `default_model="claude-sonnet-4-6"` **is in** `_ANTHROPIC_ACCEPTS_SAMPLING`, so `client.py:557` populates `sampling` and `:577` splats it. Executed, not read. |
| **#135 mcp `<2.1`→`<2.2`** | 🔴 WILL-BREAK | runtime — silent (refusals lose their reason) | mcp 2.1 masks a tool exception behind a generic `Error executing tool <name>`; `mcp_server.py` raises `ToolInputError` (a `ValueError`, `:66`) at **seven** sites. **CI confirmed:** #135 fails the entire 10-cell Python matrix, while every other dependency PR fails only `lint`/`release-suites`, red on main for unrelated reasons. |
| **`@eslint/js` 9.39.4→10.0.1** *(was in no ignore list)* | 🔴 WILL-BREAK | resolver (npm ERESOLVE) | `@eslint/js@10.0.1` peer-requires `eslint ^10`; eslint is major-ignored at 9.x and `eslint-plugin-jsx-a11y@6.10.2` peer-caps `^9`, with no eslint-10 release. Precedent in-repo: landed 2 Jul (`7cc28c44`), reverted 3 Jul (`e449aad3`). |
| **cryptography 48.0.1→50.0.1** | 🔴 WILL-BREAK | resolver | `presidio-anonymizer 2.2.364`, **the latest release**, pins `cryptography<49.0.0`. Three open CVEs, and it ships in the bundle. See the Held register. |
| **numpy 2.4.6→2.5.2** | 🔴 WILL-BREAK | resolver | Cap moved owner: numba 0.67 floats to `<2.6`, but `presidio-analyzer 2.2.364` pins `numpy<2.5.0`. ⚠️ numpy 2.5.2 also declares `requires_python>=3.12`. |
| **thinc 8.3.13→9.1.1** | 🔴 WILL-BREAK | resolver | `spacy 3.8.16` pins `thinc<8.4.0,>=8.3.12`. |
| **websockets 16.1.1→17.1** | 🟡 NON-EVENT ⚠️LATENT | resolver-gated | `google-genai 2.22.0` pins `websockets<17.0`; sole reverse-dep; zero direct imports. ⚠️ 17.0 needs Python ≥3.11 against a declared `>=3.10`. |
| **size-limit + @size-limit/file 12.1.0→13.0.3 *as separate merges*** | 🟡 NON-EVENT | resolver | `@size-limit/file` peer-pins `size-limit` exactly. **As a pair → 🟢**: 13.0's only break is dropping Node 20; CI is 24. |
| **#136 frontend group (13 updates)** | 🟢 SAFE *(and it wasn't)* | — | Every member within-caret, no Node gate crossed, react-router's only 7.x break is the `unstable_*` rename and `grep -rn 'unstable_' frontend/src/` is empty. **The green was right about compatibility and wrong about consequence** — see *the miss that wasn't a version problem* below. |
| **#118 @playwright/test 1.60.0→1.62.1** | 🟢 SAFE | — | Minor within 1.x. Merged. Entry 1 scored a hit on this exact shape. |
| **#133 setup-node v7 · #130 download-artifact v8.0.1 · #131 repository-dispatch v4.0.1 · codeql triple as a *triple*** | 🟢 SAFE | — | All `runs.using: node24`, `action.yml` read at each tag. Changed inputs are surfaces this repo doesn't use (`packageManager` auto-cache can't fire — no such field anywhere; `artifact-ids`/`skip-decompress` unused; `add-snippets` never passed). Applied in `4daad56b`. |
| **starlette 1.3.1→1.6.0** | 🟢 SAFE | — | Introspected against the installed 1.6.0 in `.venv-sidecar`: all ten import sites resolve, middleware signatures byte-identical, `GZipMiddleware` gained a kwarg (additive). `fastapi 0.141.1` requires `starlette>=0.46.0`, **no cap**. |
| **tokenizers 0.23.1→0.23.2 · numba+llvmlite pair · openai 3.7 · google-genai 2.22 · mcp 2.0.1 · sqladmin · uvicorn · SQLAlchemy · pydantic 2.13.5 · scipy · ctranslate2 · mlx pair · typer · rich · protobuf · lxml · the utility tail** | 🟢 SAFE | — | Patch/minor within major, or dev-only with no bundle presence. **Nineteen were already resolved and running in `.venv-sidecar`.** `torch 2.13→2.14` is free: `"torch"` is in the spec `excludes` and `_internal/torch` is absent — zero bundle bytes. |

### The miss that wasn't a version problem — #136 and the bundle budget

Every compatibility claim about #136 held. It was still unmergeable, and the
pre-mortem did not see why: **thirteen bumps together push the gzipped SPA past
its 220 kB `size-limit` budget**, a hard gate (not in `soft-gates.json`). Main
was already at **206.61 kB** — inside 6% of the ceiling — so any group bump
trips it.

**Tuning for the next pass: a bump's blast radius includes the budgets it is
measured against, not only the APIs it calls.** Ask what hard gates the change
is weighed by — bundle size, install size, cold-start — and whether the current
headroom absorbs it. That is a cheap question and it was never asked.

Resolved by splitting rather than by raising the budget. `react-router` was the
only member with a security reason to move and cost **1.11 kB** of the 13.4 kB
available (206.61 → 207.72), clearing all seven High advisories —
`npm audit --omit=dev` went 7 → **0**. `package.json` already said `^7.14.2`, so
it was lockfile-only: exactly two entries moved, 7.14.2 → 7.18.3 (`6e627839`).
The other twelve stay unmerged pending a bundle pass or a **deliberate** budget
decision.

On the advisories, assessed rather than assumed: **none of the seven was
reachable.** Six need framework/SSR/RSC mode and `router.tsx:58` is a
client-side data router; the seventh needs an attacker-controlled navigation
target, and all seven call sites build paths from internal ids behind a literal
`/report/` prefix. Clean audit, not a closed incident.

### Refuted while grounding — the two-venv "testing gap"

This pass asserted that `.venv` and `.venv-sidecar` diverging on 26 packages
meant *"the suite has never run against the versions that ship."* **Measurement
refuted it, and it is recorded here so it is not re-derived.** There is no
lockfile, no constraints file and no `--constraint` in `ci.yml`, so CI's
`pip install -e ".[dev,serve]"` is a **fresh resolve** — the same strategy
`build-sidecar.sh` uses. The only packages in the sidecar and not in CI's
install are `altgraph`, `macholib`, `pyinstaller`, `pyinstaller-hooks-contrib`,
all build tooling. The `dev` extra deliberately carries `mcp` and
`mlx`/`mlx-whisper` so the matrix covers those surfaces. And Entry 6 is the
direct receipt: mcp 2.1.1 was caught by CI *while the local venv sat on 2.0.0* —
CI resolving **ahead**, the opposite of the claim. `.venv` was simply a month
stale.

The one real defect in that area is separate and unfixed:
`scripts/generate-third-party-binaries.py:161` resolves from `.venv`, so
`THIRD-PARTY-BINARIES.md` — the file whose own header calls it the canonical
inventory of what ships — records dev versions (`starlette 1.3.1` against the
sidecar's 1.6.0) and lists `tokenizers`, which is not in the bundle at all.

### Applied on the day

- **Merged:** #118; `react-router` alone (`6e627839`).
- **Superseded and closed:** #129–#133, by the one-commit Actions sweep
  (`4daad56b`) — codeql triple on a single SHA, plus the other three.
- **Held and closed:** #134, #135, and #139 (which is #134 raised again).
- **`dependabot.yml`:** `tokenizers` ignore retired; `@eslint/js` +
  `eslint-plugin-jsx-a11y` added (`a6f8cc66`); the three ceiling-holds moved to
  the `versions:` form (`a97bedda`); `open-pull-requests-limit` 5 → **15**.
- **Migrated off `actions/attest-sbom` (#138 closed, not merged).** The PR
  proposed 2.4.0 → **4.1.0**, and attest-sbom is deprecated **as of its own
  v4.0.0** — *"in favor of `actions/attest` … applications should make plans to
  migrate"*. v4.1.0's `action.yml` is a four-line passthrough that forwards
  `subject-path` and `sbom-path` to `actions/attest`, which are exactly the two
  inputs `release.yml` passes — so taking the PR and migrating produce identical
  behaviour, differing only in whether a dead layer sits in between. Moved
  straight to `actions/attest@v4.2.2` (node24, actively maintained, no
  deprecation of its own). **v3.0.0 was the intuitive answer and is the wrong
  one:** it is merely the last release before the deprecation, dates from Aug
  2025, and is terminal. Note the node-runtime argument does *not* apply here —
  attest-sbom v3 and v4.1 are both `using: 'composite'`, so nothing was emitting
  a node20 annotation; this is purely about not pinning to a dying layer.

### The ignore form was wrong for a ceiling

`anthropic` carried `update-types: ["version-update:semver-major"]` from 27 Aug
and **never once suppressed the PR** — #134 stood a week under it, and #139 was
raised while it was still in force. A ceiling in `pyproject.toml` produces an
*"Update `<dep>` requirement"* PR that widens the constraint, and `update-types`
does not filter that shape; **`versions:` does**, which is why the retired
`tokenizers` rule worked for three months. Fixed for `anthropic`, `mcp` and
`mcp-types`. The other five keep `update-types` deliberately: `pydantic` and
`fastapi` are floor-only pins and the spaCy trio are transitive with no
constraint of ours, so they emit ordinary version-update PRs.

### The unknowns

- ❔ **Which `starlette` shipped in 0.29.1's artefact.** The `.app` was built
  31 Aug 18:57; every dist-info in `.venv-sidecar` is stamped 22:09, i.e. the
  venv was recreated *after* the build. starlette is pure-Python so it leaves no
  dist-info in `_internal/` to read. The 🟢 above rests on introspecting the
  installed 1.6.0 plus the changelogs, **not** on "1.6.0 has shipped". Cheap
  next step: `copy_metadata("starlette")` in the spec, so the bundle records it.
- ❔ **Whether `presidio-anonymizer` intends to float `cryptography<49`.**
  2.2.364 is latest and no upstream signal was found either way — which is why
  it is a predicate rather than a verdict.

### Live evidence — 4 Sep 2026

One real call per (provider, model) through the actual `LLMClient.analyze()`,
with the maintainer's keys, rotated afterwards. It found what 4,375 mocked tests
structurally could not — a mock accepts any request shape and any response.

| call | result |
|---|---|
| `gpt-5.6-terra` — modern params + strict Structured Outputs | **PASS** |
| `gpt-4o` — legacy params + strict Structured Outputs | PASS |
| `claude-sonnet-4-6` — temperature via `extra_body` | **PASS** |
| `claude-opus-5`, `claude-haiku-4-5-20251001` | PASS |
| `claude-sonnet-5` — the new default | **FAIL 5/5** |
| `gemini-2.5-flash` | blocked — see below |

**Sonnet 5 fails our tool schema on real input, and the default was reverted
(`c3a34866`).** On a realistic two-sentence transcript it returns the tool
input with `quotes` as a JSON *string* — the entire result re-serialised inside
the first field — deterministically; a terse prompt never triggers it and
`max_tokens` makes no difference. Opus 5, Haiku 4.5 and Sonnet 4.6 are clean on
the identical input, so it is specific to Sonnet 5. Real transcripts are far
longer than the one that reproduces it. "Sonnet class, current version" remains
the rule; the current Sonnet cannot be honoured today, and the receipt sits in
`providers.py` beside the value. Not yet done: the quote-stability corpus, and
whether the stringifying is tied to the schema's `verbatim_excerpt`
"copy-paste" instruction.

**Gemini, once the key was reachable: both picker models are retired for new
users.** `bristlenose configure google` wrote a login-keychain item the CLI
reads, and the first call returned `404 — no longer available to new users`
for **both** `gemini-2.5-flash` and `gemini-2.5-pro`, each naming its
replacement (`gemini-3.6-flash`; `gemini-3.1-pro-preview`). Google's
deprecations page showed no shutdown date for either the day before — soft
retirement is a separate status it does not carry, so "no retirement date" was
true and useless. This overturns the hold-on-cost: the working full-Flash
models (3.6/3.7/3.8) are one price, so nothing cheaper existed to prefer.
Default → `gemini-3.8-flash`, picker → flash + `3.5-flash-lite`, Pro dropped
rather than ship a preview. **Tuning: a vendor "no retirement date" is not
evidence a model is *obtainable*; only a call from a fresh account is.**

**Gemini is blocked by a keychain split, not a key.** `credentials_macos.py:43`
and `KeychainHelper.swift:74` use the identical item name, but the app writes
its items to the **iCloud** keychain (synchronizable) while the CLI's
`/usr/bin/security` reads and writes the **login** keychain — same name, two
keychains, confirmed in Keychain Access showing both side by side. The login one holds a
22-char placeholder; the app's holds the real key and shows Online. On any Mac
with the app installed the CLI and the app cannot share credentials. Not this
review's to fix; the most consequential thing the afternoon found.


### Stale-register drift found while grounding

1. **`weasel` and `confection` rows were factually false** — both holds had
   silently graduated. `spacy 3.8.16` requires `weasel<2.0.0,>=1.0.0` and
   `confection<2.0.0,>=1.3.2`; both are installed and clean. The rows said
   `weasel<0.5` and `confection<1.0`. **The "one atomic spaCy-4 wave" framing is
   falsified by observation:** spaCy 3.8.x floats its own caps without a major.
2. **`thinc`'s predicate could never fire.** *"spaCy 4 reaches GA"* — the 4.0
   line is three dev releases, newest 2 years 4 months old, two of them yanked.
   Re-specified to a cap float.
3. **`tokenizers` was a live tombstone**, retired above.
4. **The `mcp` row undercounted the migration** — "three call sites" against
   seven `raise ToolInputError`, and it named a harder fix than upstream
   requires (`ToolError`'s own docstring says raising the SDK's `ToolError`
   already yields `is_error=True` with the message in `content`).
5. **The `anthropic` row was corrected mid-review and then over-corrected** —
   updated to *"code-ready, wave-blocked"* on the strength of `bb9e201d`, which
   fixed the API-400 on post-4.6 models but not the SDK-signature break on the
   default model. Restored in `6e24f8d6`. *A finding marked resolved is a claim
   about intent, not evidence about the tree.*
6. **The snapcore mitigant expired 8 Aug 2026** — `snap.yml` was restored to
   `push`/`pull_request`, so the node20 annotation surfaces on every push.
7. **Eleven `dependabot.yml` ignores had no register row.** Four now do; the
   npm set (`jsdom`, `vite`, `vitest`, `eslint` family, `typescript`,
   `lighthouse`, `@playwright/test`) still shares one stated reason — *"tied to
   Node major"* — against `.tool-versions: node 24`, unre-read since it was
   written.
8. **`lighthouse 12.x` — fourth consecutive flag.** Entry 5 proposed the
   structural fix (*a register row may not restate a value that lives in a
   tracked config file; it may only name the file*). Still unapplied.

### New clusters — named, not smuggled in

Recommend adding to the catalog in `docs/design-dependency-premortem.md`:

- **Presidio ceiling cluster** — `presidio-analyzer/anonymizer →
  {cryptography, numpy, spacy, phonenumbers, pydantic}`, plus a
  `requires-python <3.15` ceiling. Entry 2 modelled presidio as a floor-*raiser*;
  at 2.2.364 it is the tightest **ceiling** in the graph and owns two caps the
  existing map attributes elsewhere (numba for numpy; nothing for cryptography).
  It is a core dependency, so it constrains every channel.
- **codeql-action as a chain-within-a-fan** — a refinement of Entry 5's "fan,
  not a chain": `init`/`autobuild`/`analyze` enforce version consistency on each
  other while Dependabot emits them as separate PRs subject to
  `open-pull-requests-limit`.
- **npm peer-cap chain** — `@eslint/js → eslint → eslint-plugin-jsx-a11y`.
  Unlike pip caps these are *peer* declarations, so the failure is `ERESOLVE` at
  `npm ci`, and an ignore list must cover the whole chain or it covers nothing.
