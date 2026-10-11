# Third-party Claude skills against Bristlenose: a measured review

_11 Oct 2026. The research ran without touching `main`. The fixes and lens changes
it led to landed afterwards; see §3 and the commit log. Every reviewer's raw
findings and the judges' scores are kept in the maintainer's private notes,
outside the public tree (see Files)._

The question was whether the well-regarded public Claude Code skills for
Python, TypeScript and Swift would beat what this repo has grown by hand, and
whether any of them should run across the whole codebase. The answer below
rests on three experiments, not on star counts:

1. **A blind bug-finding benchmark.** 14 real bugs from this repo's own
   history, each fixed between July and October 2026. None is described in the
   root `CLAUDE.md`, so a reviewer cannot recall the answer from the briefing.
   Each reviewer got the pre-fix source and a scope hint, and no repo, history
   or web access. 11 review arms ran; anonymised LLM judges scored them against
   the real fix commits. The Swift arms were run twice.
2. **A property-based-testing trial.** Hypothesis tests were written for
   `utils/timecodes.py` and `slugify`/`safe_filename`, with and without the
   Trail of Bits skill, then scored by **mutation**: 12 mutants written before
   any test existed and hidden from the writers, each run under 3 seeds. The
   existing example-based suite was the control.
3. **A HEAD check** of the real defects the reviewers surfaced that the
   historical fixes did not address.

## What was surveyed

Four research passes covered skills.sh, awesome-* lists, GitHub (stars,
recency and licence via `gh api`) and the official marketplace. The leading
candidates, pinned at the SHA read:

| Source | ★ | Licence | Pinned | Read in full |
|---|---|---|---|---|
| trailofbits/skills | 7.5k | CC-BY-SA-4.0 | `442fc9d6c8` | property-based-testing, sharp-edges, insecure-defaults, fp-check, differential-review, variant-analysis, mutation-testing, modern-python |
| anthropics/claude-plugins-official | 37.7k | Apache-2.0 | `f359d43b40` | pr-review-toolkit, code-simplifier, security-guidance, the LSP plugins |
| mattpocock/skills | 285k | MIT | `49dd158d10` | diagnosing-bugs, code-review, tdd |
| getsentry/skills | 1.0k | Apache-2.0 | `d18b7aa8ba` | find-bugs, security-review |
| vercel-labs/agent-skills | 32k | **none at repo level** | `063bee94c3` | react-best-practices (70 rules), composition-patterns, web-design-guidelines |
| AvdLee/SwiftUI-Agent-Skill + Swift-Concurrency | 3.7k / 1.7k | MIT | `204dba7c67` / `d5770817d2` | swiftui-expert (36 refs incl. macOS), swift-concurrency |
| twostraws/SwiftUI-Agent-Skill (vendored here at 1.1) | 5.7k | MIT | `f9800713b2` (2.0.0) | swiftui-pro; swift-concurrency-pro, swift-testing-pro |
| CharlesWiltgen/Axiom | 1.2k | MIT | `d35eaca69e` | axiom-macos, axiom-security |
| obra/superpowers | 297k | MIT | — | systematic-debugging, verification-before-completion, TDD |
| fastapi / typer, bundled skills | — | MIT | in `.venv` | already on disk in `site-packages/*/.agents/skills/` |

Nothing was installed and no third-party script was run. Skill text was fed to
reviewers as data.

## Results

### 1. Bug-finding benchmark

Recall against the real fix: HIT = 1, PARTIAL = ½. Cases are listed in
`benchmark/cases-table.md`.

| Arm | Cases | Recall | VALID other | WRONG |
|---|---|---|---|---|
| **in-house `silent-failure-hunter`** | 14 | **10.0 (71%)** | 21 | 0 |
| baseline: "careful senior engineer", no skill | 14 | 9.0 | 23 | 0 |
| **in-house `code-review`** | 14 | 9.0 | 27 | 0 |
| Sentry find-bugs | 14 | 9.0 | 21 | 1 |
| official pr-review-toolkit (sfh + type-design + comment) | 14 | 8.5 | 23 | 0 (11 nits) |
| Pocock code-review | 14 | 8.0 | 24 | 0 |
| ToB sharp-edges + insecure-defaults | 14 | 7.5 | 26 | 2 |
| Vercel react-best-practices (TS only) | 4 | 2.5 (= baseline 2.5) | 6 | 0 |

**Swift, two independent runs each (5 cases):**

| Arm | Run 1 | Run 2 | Mean |
|---|---|---|---|
| baseline | 3 | 4.5 | **3.75** |
| AvdLee swiftui-expert + swift-concurrency | 4 | 3 | 3.5 |
| twostraws swiftui-pro + swift-concurrency-pro (vendored) | 2 | 3 | **2.5** |
| Axiom macOS | 2 | — | 2 |

**Combinations (all 14 cases):** baseline + `code-review` = 9.0, no gain,
because both miss the same cases. `code-review` + `silent-failure-hunter` =
10.5. The union of every arm = 11.5.

### 2. Property-based testing, scored by mutation

Of 12 mutants, 11 are non-equivalent; M5 is equivalent and survives
everything.

| Suite | Reliable kills (3/3 seeds) | Expected kills | Real defects found |
|---|---|---|---|
| existing example tests (7 files, 219 tests) | 7 | 7 | — |
| Hypothesis, no skill | 4 | 5.7 | 2 |
| **Hypothesis + ToB property-based-testing** | **6** | **7.3** | 2 (same two) |
| existing ∪ ToB | 8 reliable + 1 at 2/3 | — | — |

Mutants that survive the existing suite: **M4** (a slug ends in `-` after
truncation), **M10** (a colon-less `+0100` offset is not normalised), **M11**
(a simple-format `.5` reads as 0.005) and **M12** (hyphens are not collapsed).
The ToB tests kill M4 reliably and M12 at 2/3. The two real defects, found by
both arms with no hint:

- `safe_filename("a.:.b") == "a..b"`. `..` is stripped *before* the unsafe
  characters, so it reassembles, which breaks the docstring's own guarantee.
  It is not exploitable, because no separator survives.
- `format_timecode_ms(59.9996) == "00:00:60.000"`. The function has no callers,
  and it is already on the dead-code list.

### 3. Live defects surfaced as a side effect (checked at HEAD `3fa3aa51`, all since fixed)

| # | Defect | Where | Severity | Fixed |
|---|---|---|---|---|
| 1 | Two LLM assignments for one quote violate `uq_proposed_tag_job_quote`, which rolls back **the whole paid AutoCode job**, and a retry repeats it. The `best_by_quote` collapse exists only in the re-apply path | `server/autocode.py` ~358–377, 510 | high | `83bab663` |
| 2 | `serve_deps` sits in five `_COMMAND_CHECKS` lists but is absent from `_check_fns`, and is silently skipped, so the gate cannot fail | `doctor.py` ~1733–1747 | medium | `fd6286ee` |
| 3 | `WKUserContentController` retains the Coordinator, which retains the web view. No `removeScriptMessageHandler` exists, so replaced web views leak and keep posting into the shared bridge | `WebView.swift` ~152, 165, 231 | medium | `d29c4fc4` |
| 4 | `removeFilePresenter` is called only from `deinit`. If the coordinator retains presenters, `deinit` never runs and the security scope stays open. The retention premise is unverified, and a weak-ref test settles it | `ProjectFolderWatcher.swift` ~199–208 | medium | `1e6dcf7f` |
| 5 | Inline `ref` callback calls `el.focus()` on every render, which pulls focus back during the blur window | `QuoteCard.tsx` ~517 | low-med | `473786f7` |
| 6 | Data-container handshake copy does not fail closed (the group copy does) | `MCPHandshake.swift` ~163 | low-med | `7a519706` |
| 7 | `fullNameAt` budgets the 42 px date while the 70 px weekday date is showing, so the row overflows by up to 28 px | `SessionsSidebar.tsx` ~116, 190 | low | `b1ec59b1` |
| 8 | Accounts pane captures `serveManager` once. Mostly mitigated by `applyEnvChange` | `SettingsView.swift` ~289 | low | `924c58cc` |

Line numbers are a version stamp, and all eight are fixed (11 Oct 2026). #4's
unverified premise was confirmed by a weak-reference test before its fix.

## What the data says

1. **No third-party review skill beat a careful plain reviewer at finding real
   bugs.** The arms themselves reported that their highest-severity findings
   came from *no* skill reference (AvdLee 17 of 25, Axiom 13 of 22,
   pr-review-toolkit 30 of 73, Vercel "all high-severity ones").
   Correctness came from general reasoning; the rubrics mostly added
   low-severity, on-theme items.
2. **Checklist skills narrow attention.** The vendored swiftui-pro and
   swift-concurrency-pro scored below the baseline in both runs. A reviewer
   told to walk an API-modernity checklist spends its budget there. Their
   value is *knowledge for writing* SwiftUI (deprecated API, property-wrapper
   choice), which this benchmark does not measure, not *lensing a correctness
   review*.
3. **Run-to-run variance is larger than between-skill differences.** The
   baseline moved from 3 to 4.5 of 5 between two identical runs. Any
   single-run comparison here of ±1 case is noise, including the 10 vs 9 at
   the top of the table.
4. **Diversity of lens is the lever, not the skill.** `code-review` adds
   nothing to the baseline, because both miss the same cases.
   `silent-failure-hunter` adds a different angle (+1.5). The union of
   everything reaches 11.5 of 14. That is what `/usual-suspects` already does,
   and it is the right shape.
5. **Precision is not the problem.** The judges graded 3 findings WRONG out of
   about 560. The cost is volume: around 30 PLAUSIBLE findings per arm. So
   **fp-check-style verification is solving a problem you do not have**; the
   Ockham triage is the correct counterweight.
6. **Generative method skills do carry measurable value.** The ToB PBT skill
   produced tighter properties: it pushed constraints into strategies instead
   of `assume()`, and it avoided restating the code. That gave 6 reliable kills
   against 4. It also kills two mutants the existing suite misses. Both arms
   found the same two real defects, so the *technique* (Hypothesis) carries
   most of the value and the skill improves its quality.
7. **The in-house agents hold up.** `silent-failure-hunter` was the strongest
   single arm and the only one to name P1's real cause. The hand-built
   agents are not behind the public state of the art; for this codebase they
   are ahead of it, because they encode its failure history.

### Blind spots of this benchmark (read before over-trusting it)

- **14 cases, one model (Opus 5.5), LLM judges.**
- **Two cases may be contaminated.** `frontend/CLAUDE.md` and `desktop/CLAUDE.md`
  describe T1's and S1's causes. Reviewers could not read the repo, but that is not
  proof. Excluding both changes no conclusion (`benchmark/ARM-PROMPTS.md`, sensitivity
  table); replace them before reusing the set.
- **Isolation removed cross-file context.** T2 (the other write paths never
  dispatch an event) and S4 (each copy stamps its own `updated_at`) were missed
  by everyone. The T2 key depends on files outside the bundle; S4's was visible
  in the bundle and still missed. In a real repo a reviewer can grep, and LSP
  find-references would help, so recall in practice is higher for every arm.
- **Skills were applied as reading, not through native triggering.** A skill
  that works by firing at the right moment during *authoring* (swiftui-pro,
  the FastAPI skill) is under-measured here.
- **Security got little exercise.** Few of the 14 cases are security bugs, so
  the security skills' value is under-sampled, not disproven.
- **Performance and UX consistency were not measured at all.**

## Recommendation by option

### Adopt as-is: nothing wholesale

Every big pack fails on invasiveness before quality comes into it:

- **superpowers:** a SessionStart hook injects `<EXTREMELY_IMPORTANT>` workflow
  control into every session.
- **Axiom plugin:** six prebuilt Mach-Os and six hooks, including a 52 KB
  UserPromptSubmit router.
- **security-guidance** (official): on every Stop it sends the diff to Opus,
  pip-installs at SessionStart, and runs a background review on every
  commit and push.
- **ToB modern-python:** PATH shims make bare `python` and `pip` exit 1, and it
  pushes uv, ty and prek over decided tooling.
- **fp-check:** global Stop and SubagentStop LLM hooks.
- **web-design-guidelines:** fetches its rules from an unpinned URL at runtime.

`swift-lsp` looked like the one low-risk adopt candidate, so it was tested before
installing, and it **fails on this project**. With no build server, sourcekit-lsp
type-checks each `.swift` file alone. Driven by a minimal LSP client the way the
plugin launches it (bare `sourcekit-lsp`, repo root), it returned:
- no go-to-definition across files;
- **zero** references to `MCPHandshake`, which four files use;
- **24 false compile errors**, such as "Cannot find type 'ServeManager' in scope".

Pointing it at an existing Xcode index store changed nothing. An agent given
this tool would be shown errors that do not exist, which is worse than no tool.
It would work only behind a build server (`xcode-build-server` plus a
`buildServer.json` kept in step with the scheme), a maintenance cost with no
measured need: in-repo reviewers already grep across files. Not adopted
(11 Oct 2026). `typescript-lsp` and `pyright-lsp` need global installs, and
`tsc` and mypy already cover them.

### Adapt: vendor a trimmed copy, the `swiftui-pro` pattern

| Skill | Why | How |
|---|---|---|
| **ToB property-based-testing** | Measured: +2 mutant kills over the existing suite, and better properties than without it | Vendor SKILL + 5 references with CC-BY-SA attribution. Add `hypothesis` to `[dev]`. Pin a CI profile (`derandomize=True` or a fixed seed): kills here were seed-dependent (M1 2/3, M12 2/3). Pair with `what-would-james-bach-say` for proportion |
| **twostraws swiftui-pro 2.0** | Knowledge for *writing* SwiftUI. Upstream moved 1.1 → 2.0 on 7 Oct, adding "keep the existing deployment target" and "no unrelated modernisation" | Re-vendor `api.md`, `views.md` and `localization.md`; skip `resizability.md`. **Stop using it as a correctness lens** in usual-suspects (it measured below baseline). Keep it as authoring knowledge |
| **AvdLee macOS references** | macOS-specific SwiftUI knowledge the vendored set lacks: Settings and Window scenes, `windowIdealPlacement`, Table, HSplitView, pasteboard | Vendor as reference material for `what-would-gruber-say` and `mac-arsed-mac-app`. Not a reviewer. Drop `webkit-integration.md` and `document-apps.md` (macOS 26 APIs) |

### Borrow: lift a technique into an existing agent

- **`silent-failure-hunter` ← sharp-edges.** Its "stringly-typed" and
  "fail-open" sections fired on real cases: `role === "moderator"` and
  "HTTP 400 accepted as a valid key". The `serve_deps` silent skip above is
  exactly this class.
- **`security-review` ← insecure-defaults references** (fail-open,
  permissive-access, debug features). Also sentry's `modern-threats.md`, for
  prompt injection against the chat lens and MCP.
- **`code-review` ← differential-review's two mechanical steps:** git-blame to
  catch a reintroduced fix, and blast radius by caller count. **← Pocock's
  "spec axis":** derive intent from docstrings and comments, then check the
  code against them. 62 of its 67 findings came from that axis, and both
  `safe_filename` and the timecode defects are docstring breaches.
- **`code-review` ← pr-review-toolkit `comment-analyzer`:** comments that
  argue against their code, count their own consumers, or name deleted
  collaborators. This repo's CLAUDE.md documents all three as recurring.
- **`perf-review` ← Vercel `rerender-*` and `rendering-*` rules.** React
  render discipline is not covered today. Drop `server-*`, SWR, `next/dynamic`
  and hydration. Paraphrase rather than copy: there is no repo licence.
- **`ux-critique` / `a11y-review` ← web-interface-guidelines**, a pinned
  snapshot of its 104 rules: `transition: all`, `…`, `Intl.*`, never block
  paste, `overscroll-behavior`.
- **Debugging memory ← Pocock diagnosing-bugs:** generate 3–5 *ranked,
  falsifiable* hypotheses before testing any; tag debug logs `[DEBUG-xxxx]`;
  minimise the repro until every element is load-bearing. The rest is already
  in the house rules.

### Iterate: what the data says about your own setup

- **Keep the fan-out; weight it toward different lenses, not more of the same
  lens.** Baseline + `code-review` gained nothing; adding
  `silent-failure-hunter` gained 1.5 cases.
- **Turn this benchmark into a regression eval for your own agents.** The
  harness (`benchmark/`) plus a judge is about an hour of agent time.
  Re-running it after editing an agent prompt tells you whether the edit
  helped. The prompts currently have no test.
- **Mutation testing earns a place** on the round-trip and format contracts
  (`docs/design-shared-formats.md`, timecodes, slug, transcript reader and
  writer, locale JSON escaping). The existing suite let 4 of 11 mutants live
  in 300 lines of utility code. ToB's mutation-testing skill does not support
  Python, so use `mutmut` directly. The `pbt/run_mutants.sh` here is a
  hand-rolled stand-in, and it carries two lessons recorded below.

## Should anything run at scale across the codebase?

- **Property-based tests: yes, targeted.** Use them on functions with a
  round-trip, idempotence or ordering contract. The shared-format register is
  the natural list. Not everywhere: most of the codebase has no algebra to
  exploit.
- **Review skills as a codebase-wide sweep: no.** The yield is the general
  reviewer's, not the skill's, and at around 5 findings per file-region you
  would bury the real ones in plausible ones. **An audit sweep with the
  in-house agents over the lifecycle-heavy Swift code and the DB-write paths
  is worth it, though:** 8 live defects fell out of 14 small files.
- **Mutation testing: yes, as a periodic measurement** over `bristlenose/utils`
  and the format and manifest code, with surviving mutants triaged rather
  than ratcheted to zero.

## By dimension

| Dimension | Measured effect of third-party skills | Best lever found |
|---|---|---|
| Correctness | None beyond a careful reviewer | lens diversity; PBT + mutation testing |
| Silent failure / fail-open | sharp-edges adds vocabulary | in-house sfh + sharp-edges sections |
| Security | under-sampled; no gain seen | insecure-defaults refs; *avoid* security-guidance's hooks |
| UX consistency | not measured | web-interface-guidelines (pinned); AvdLee macOS refs |
| Performance | not measured | Vercel rerender rules into perf-review |
| Test quality | **measured, positive** | ToB property-based-testing |
| Supply chain / safety of the tool itself | **negative for most packs** | vendor text, never install packs with hooks |

## Two harness lessons, recorded because both produced convincing wrong numbers

1. **Running pytest from the repo root imports the repo, not the mutant.**
   The first run against the existing suite said "12 of 12 survived": cwd went
   first on `sys.path`. The fix runs from inside the mutated copy and asserts
   `module.__file__` before trusting a verdict (`run_mutants.sh`).
2. **`*failed*` matches `2 xfailed`.** The first seed-aware run scored the
   unmutated baseline as "killed 3/3". The pattern is now `*[0-9]" failed"*`.
   Both are the "prove the mutation landed / a verdict the shell cannot
   withhold" family already in `CLAUDE.md`.

## Files

- `benchmark/PROTOCOL.md`, `JUDGE.md`, `cases-table.md`: the method and the 14 cases.
- **Not here:** every arm's raw findings, the judges' scores and the label
  mappings. They are in the maintainer's private notes, outside the public tree.
  The raw findings include security-shaped claims about the code that nobody
  has verified, and publishing unverified vulnerability reports is the wrong
  default. `benchmark/aggregate.py --scores <dir>` reproduces the tables from
  that copy.
- `pbt/test_props_tob_skill.py`, `test_props_no_skill.py`: the two Hypothesis
  suites. They live outside `testpaths`; Hypothesis is not a project
  dependency.
- `pbt/mutants.py`, `run_mutants.sh`, `*-mutants.txt`: mutants, harness and
  results. Paths are hard-coded to the session scratchpad; they are a record,
  not a tool.
