# Bristlenose — Project Context for Claude

Claude Code's entry point. Other harnesses (Codex and others) start at `AGENTS.md`; the two share these rules and must not disagree. If they conflict, this file wins: fix `AGENTS.md` in the same commit.

## What this is

Bristlenose takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report — extracted quotes, themes, sentiment, friction points, user journeys — that the researcher edits, shares, and keeps as a file they own. The user is a working researcher under deadline, not an engineer.

The pipeline runs on the user's own machine; the analysis itself is a **cloud LLM call** to Claude (Anthropic), ChatGPT (OpenAI), Azure OpenAI (enterprise), or Gemini (Google), and that is the normal, recommended, everyday path. Local models via Ollama are a supported minority option (slower, wants a capable machine, technical setup) — never the proud default.

**Don't pitch or reason about Bristlenose as "local-first" or "privacy-first".** It isn't the stance, and "nothing leaves your laptop" is plainly false: the analysis *is* an outbound LLM call, and researchers' recordings and deliverables typically already live on a client's Teams/SharePoint/Drive. Lead with the outcome and the owned artefact. This does **not** relax participant-data governance — PII redaction, re-identification keys and retention remain real craft obligations (`docs/methodology/consent-gradient.md`).

## Commands

- `.venv/bin/python -m pytest tests/` — run tests. **Free**: `addopts = -m "not slow"` in `pyproject.toml` deselects the `slow` marker, so the everyday command never makes a paid LLM call. It used to — until 3 Sep 2026 the bare command billed the account on every run, and a session following these instructions had no way to know without reading the test files
- `.venv/bin/python -m pytest tests/ -m slow` — the **paid** suite: real LLM calls, **~$0.63 and ~8 min per full run** measured 3 Nov 2026 on Claude (Console balance delta; the `-m slow` run is dominated by `TestLiveNorman`, ~$0.29 for its 5 batched calls over 120 quotes, and one test in that class pays for the whole class because they share a cache). That figure leaves out the 6 `test_no_fake_success_acceptance.py` pipeline cases, which skip unless `BRISTLENOSE_ANTHROPIC_API_KEY` / `BRISTLENOSE_OPENAI_API_KEY` are set and cost more when they run (a `-m` on the command line overrides `addopts`). Opt in deliberately; it is excluded from CI and ratcheted by `scripts/check-ratchet.py` as coverage given up. With no credit it now **skips** with a "SKIPPED, NOT PASSED" message rather than erroring — a genuine `BAD_REQUEST` still fails
- `.venv/bin/ruff check bristlenose/` — lint (no global ruff install)
- `.venv/bin/ruff check --fix bristlenose/` — lint and auto-fix
- `.venv/bin/mypy bristlenose/` — type check (informational, not a hard gate)
- `cd e2e && npm test` — Playwright E2E tests (layers 1–3: console, links, network; Chromium + WebKit)

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Bump semantics — minor = feature, patch = fix.** A release that adds *any* user-facing feature bumps the **minor** (`0.20.0 → 0.21.0`); a release that's purely bug-fixes bumps the **patch** (`0.20.0 → 0.20.1`). Feature-bearing releases advance the minor fast — that's fine and expected pre-1.0. **Do not** let features accumulate under a long patch run: the 0.15.0 → 0.15.19 line (nineteen patches, many carrying real features) was a mistaken habit, not the convention. When unsure, ask "does this add a capability?" — yes → minor.
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`. Use `./scripts/bump-version.py` to bump — it updates `__init__.py`, the man page and the pbxproj, stages them, and **does not commit or tag**. It can't tag correctly: the commit the tag belongs on doesn't exist yet (you add the CHANGELOG/README prose afterwards), so it used to tag pre-bump HEAD and every runbook carried a delete-and-re-tag correction. Removed 14 Aug 2026 — if you still have `git tag -d` in your fingers, it will now fail with "tag not found", which is the fix telling you it worked. Standard flow: run `bump-version.py`, write CHANGELOG + README + CLAUDE.md status, `git add` those, commit, **then** `git tag v<X.Y.Z>` (verify `git rev-parse HEAD` matches `git rev-parse v<X.Y.Z>^{}`), then push `main` and the tag as **two separate pushes** — never `--tags`, which both bundles the irreversible act with the free one and is how the tag-driven release workflow gets debounced into never firing
- **Markdown style template** in `bristlenose/utils/markdown.py` — single source of truth for all markdown/txt formatting. Change formatting here, not in stage files
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates (see `bristlenose/theme/CLAUDE.md`)
- **Licence**: AGPL-3.0 with CLA
- **Provider naming**: user-facing text says "Claude", "ChatGPT", and "Azure OpenAI" (product names), not "Anthropic" and "OpenAI" (company names). Researchers know the products, not the companies. Internal code uses `"anthropic"` / `"openai"` / `"azure"` as config values — that's fine, only human-readable strings need product names
- **CLI plurals**: any count-bearing CLI string uses `count_noun(n, "singular")` from `bristlenose/utils/text.py` — wraps `inflect.engine().plural_noun()`, so irregulars (`child`→`children`, `person`→`people`, `boundary`→`boundaries`) and compound nouns (`"topic boundary"`→`"topic boundaries"`) work automatically. Don't hand-roll `f"{n} thing{'s' if n != 1 else ''}"` or add a sibling helper next to `count_noun`. Pass `plural=` explicitly only when inflect's default disagrees (rare). **CLI terminal chrome is English by design, not pending** (`docs/design-i18n.md` §"Which surfaces are targets") — the terminal is the operator surface and the localised thing is the artefact it produces, so English `inflect` is the right answer here permanently, not an interim one. The React SPA + desktop use i18next CLDR plurals via `t(key, count=n)` — different surface, different mechanism, don't conflate
- **Changelog version/date format**: `**X.Y.Z** — _D Mon YYYY_` (e.g. `**0.8.1** — _7 Feb 2026_`). Bold version, em dash, italic date. No hyphens in dates, no leading zero on day. Used in both `CHANGELOG.md` and the changelog section of `README.md`
- **Changelog entry structure (from 0.30.0 on; nothing retrospective)**: the one-sentence summary line stays first, then the bullets are grouped under bold sub-headers `**New**`, `**Improved**`, `**Fixed**`, and `**Removed**` when something was taken away — in that order, only the non-empty ones, each ordered by importance within. A patch release has no `**New**` section; a `**New**` section means the bump is a minor. The header carries the verb, so a bullet never opens with "Added"/"Fixed": it keeps the house bold-led phrasing of the change as the user experiences it (`**Only one codebook could be off at a time.**` under Fixed, not "Fixed only one codebook…"). Tone of voice is unchanged — user impact, never effort; see the release-notes rule in `docs/design-bn-release-skill.md`. **Register and length (from 0.31.5):** plain, not dramatic — what was wrong, that it's fixed, one clause of cause if it earns trust, and any caveat a user acts on. Size follows the change's weight: a small fix is the bold line plus at most one sentence; a significant one two to four. Aim for about 60% of the 0.31.x entries. Before/after examples: that doc's §"Changelog register". Bold lines rather than `###` because the version heading is itself a bold line and the website renders the file as plain Markdown; the release-ready gate's body count only terminates on `**<digit>`, so a bold word is safe there
- **The React SPA is the product; the Jinja2 static renderer (`bristlenose/stages/s12_render/`) is a deprecated sealed byproduct.** Rules: (1) New features and design changes go to the React SPA only. (2) Offline sharing = open in serve mode → **Export HTML** toolbar button (embeds the React bundle + JSON; never calls `s12_render/`). (3) **Serve mode never falls back to static render** — if the SPA is missing from the bundle, `_mount_prod_report` returns a fail-loud 500, not the static HTML (that fallback masked BUG-3). (4) CSS in `bristlenose/theme/` is shared with the static render incidentally; design intent lives in `frontend/`. (5) Vanilla JS in `bristlenose/theme/js/` is frozen — data-integrity fixes only. Future direction (repurpose `--static` as a markdown deliverable): `docs/design-cli-improvements.md` §Future direction.

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands, as `bristlenose --help` lists them: `run` (full pipeline), `transcribe` (transcription only — **not** `transcribe-only`, which is the run *kind*, see the naming trap in Gotchas), `analyze` (skip transcription), `serve` (local dev server), `status` (read-only project state from manifest), `use` (switch the current provider), `configure` (store a provider key + make it current), `doctor` (dependency health checks), `codebooks` (list AutoCode frameworks), `pipeline` (which model runs each stage), `help`. `render` was **removed** — `cli.py:1590` is a hidden tombstone that errors; use `run` or `serve`. **There is no vendor-default provider**: the CLI resolves `--llm` → env → current provider (written by `configure`/`use`) → sole configured key → diagnose — see `docs/design-cli-provider-selection.md`; the `"anthropic"` field default in `config.py` is only the desktop-contract backstop. **Default command**: `bristlenose <folder>` is shorthand for `bristlenose run <folder>` — if the first argument is an existing directory (not a known command), `run` is injected automatically.

Serve mode: FastAPI + SQLite + React SPA. See `bristlenose/server/CLAUDE.md` for architecture.

Assistant surfaces (both ground in `bristlenose/server/grounding.py` — one shared core, never a parallel sibling): the **in-app chat lens** (a cited question box; `docs/design-chat-lens.md`) and the **MCP endpoint** at `/mcp/` for external agents — read-only, four tools, scoped bearer. Ships on **both** channels: the CLI via the optional `bristlenose[mcp]` extra, and the macOS app in the bundled sidecar (`docs/design-mcp-server.md`, spike accepted 30 Jul 2026). On the Mac the transport is a **`.mcpb` extension** rather than a pasted config — `desktop/mcpb/` holds a zero-dependency Node proxy that reads a runtime handshake file the host writes, so there is no address or token to copy and nothing to redo when the port rotates. Since 0.32.0 (30 Sep 2026) that proxy is replaced by a sandboxed native helper, `desktop/mcp-helper/`, which the Claude tab installs as a `type: binary` `.mcpb` and the ChatGPT tab as a plugin; the Node proxy stays as the fallback (`docs/design-mcp-native-proxy.md` §6.9); exposure is per project (**Turn On Agent Access**, sidebar antenna) and setup is **Settings ▸ MCP Agents** (`docs/design-mcp-extension.md`, shipped 1 Aug 2026). The product frame is **two offerings**: (1) the report as one link with two modes — read it / ask it; (2) stay in your own local agent. `INVARIANTS` in `grounding.py` is the single model-facing statement set for both. **Bristlenose knows the protocol, never the client** — we can offer, we cannot observe; any design that needs to read another app's state is the wrong design.

Desktop app: `desktop/` — SwiftUI macOS shell. Alpha ships a bundled, signed PyInstaller sidecar running `bristlenose serve`, distributed via internal TestFlight. v0.2 currently uses launcher-style scaffolding (dev-only, not shippable). See `docs/archive/design-desktop-app.md` for the overall app design, `docs/design-modularity.md` for cross-channel component decisions (CLI ≡ macOS Python code; packaging differences only), and `docs/private/road-to-app-store.md` for the 14-checkpoint path to TestFlight.

Frontend: `frontend/` — Vite + React + TypeScript + React Router. See `frontend/CLAUDE.md` for gotchas and architecture.

Export: self-contained HTML "leave-behind" (React SPA + inlined API data, opened offline from `file://`). Rendered by a **dedicated single-file Vite build** (`frontend/vite.export.config.ts`, `codeSplitting:false`) — a blob/data-URL module bootstrap does NOT work from an opaque `file://` origin. **Anti-drift is mechanical:** `tests/test_serve_export_coverage.py` reads `app.openapi()` and fails if any project GET read isn't classified `EMBED_PATH_TEMPLATES` or `SERVER_ONLY_PATH_TEMPLATES` in `routes/export.py` — so adding a route is offline-by-default and a new gap fails the build, not the user's download. Read-only via `isExportMode()` store-layer gate (controls hidden, not disabled). Embedded JSON is XSS-escaped (`ensure_ascii=True` alone is NOT enough — see the export-JSON gotcha below). v1 no video; the timecode/media apparatus stays in the embed for v2. Full spec: `docs/design-export-html.md`. See Key conventions for the static-render deprecation rules.

LLM providers: Claude, ChatGPT, Azure OpenAI, Gemini, Local (Ollama). See `bristlenose/llm/CLAUDE.md`.

Quote exclusivity: **every quote appears in exactly one report section.** See `bristlenose/stages/CLAUDE.md`.

Signals lens: `bristlenose/signals/` — signal concentration metrics, pure math. Uses plain dataclasses (not Pydantic). Cell keys use `"label|sentiment"` format. See `docs/design-signals-future.md`.

LLM prompts: Markdown files in `bristlenose/llm/prompts/`. Archive old versions to `bristlenose/llm/prompts-archive/`. See `bristlenose/llm/CLAUDE.md`.

Report JavaScript: the frozen vanilla modules in `bristlenose/theme/js/`. See `bristlenose/theme/js/MODULES.md` — and take the count from `_JS_FILES` in `stages/s12_render/theme_assets.py`, never from prose. This line said 17, MODULES.md said 20, `hello-world-architecture.md` said 23, and the list held 26 (19 Aug 2026). A number that lives in four documents is a number that is wrong in three of them.

Video thumbnails: `bristlenose/utils/video.py` — auto-extracted keyframes per session. See `docs/design-html-report.md`.

Scene colours: `bristlenose/utils/scene_colour.py` — one colour per speaker turn, for the session tapestry (what was on screen, not who spoke), computed in `run()` before render and written to `.bristlenose/intermediate/scene-colours/`. **Its constants are the colour lab's defaults** (`experiments/session-tapestry/colour-lab.html`): retune in the lab, then change both. Serve reads them at `GET /api/projects/{id}/tapestry`. Scene strips and the hover thumbnail's frames are computed by **serve, never the pipeline**, and the frames are served only behind the bearer token and kept out of the HTML export (they are participants' screens). Full wiring: [`.claude/gotchas.md`](.claude/gotchas.md#long-entries-moved-from-the-root-5-nov-2026); `experiments/session-tapestry/README.md`.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. Override with `--output`. See `bristlenose/stages/CLAUDE.md` for the full directory layout.

Key helpers: `OutputPaths` in `output_paths.py` (consistent path construction), `slugify()` in `utils/text.py` (project names in filenames — lowercase, hyphens, max 50 chars). Report filenames include project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`, `frontend/`, `desktop/`
- **Design artifacts** (tracked, not shipped): `docs/mockups/`, `docs/design-system/`, `experiments/` — HTML mockups, style guides, throwaway prototypes. These are working materials for contributors, kept in the tree for backup and collaboration. Users never navigate to them. Add new mockups to `docs/mockups/`, not the repo root. **Serve mode auto-discovery**: `bristlenose serve --dev` mounts all three directories and auto-discovers `*.html` files for the Design section in the About tab (`_build_dev_section_html()` in `app.py`). New HTML files added to these directories appear automatically — no code changes needed. **`experiments/` is excluded from `ruff check`** (per `pyproject.toml`) — throwaway research scripts don't need to pass lint; don't waste cycles fixing F401 unused-imports in there
- **User-facing docs live in the website repo, not here.** The single-page `docs/manual.md` was retired at the website v2 cutover (archived to `docs/archive/manual.md`; `bristlenose.app/manual.html` now 404s by design). User docs are per-topic Markdown in the website repo's `docs-src/` tree, published under `bristlenose.app/docs/`. **When a CLI change lands, the user-facing surfaces to true are: `README.md`, `man/bristlenose.1`, and the website's `docs-src/cli.md`** — three places, no fourth. Don't edit `docs/archive/manual.md` to keep it current.
- **Marketing site** (deployed, separate private repo; its `build.py` renders `docs-src/*.md` plus pages read live from this repo, e.g. the changelog). Four traps: `build.py` renders only `docs/` and does **not** copy `assets/` (rsync them after building, or you preview stale CSS/JS); the host caches `/assets/*` for **thirty days**, so asset references carry a content hash (`?v=<sha8>`) and a deployed change that works for everyone except returning visitors is this; `deploy.sh` publishes the **working tree**, not the last commit, so deploy from a clean `git worktree add --detach` of HEAD and never stash or commit another session's edits; and during a release run a deploy publishes the changelog early, so point it at the last released tag with `BRISTLENOSE_PUBLIC_REPO=<dir>`. The rsync deploy needs SSH agent access and is run manually by the maintainer. Full account, with dates and measurements: [`.claude/gotchas.md`](.claude/gotchas.md#long-entries-moved-from-the-root-5-nov-2026).
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`
- **Raw agent-review output stays private; conclusions go public.** A fan-out review produces findings nobody has verified, and some are security-shaped ("bypasses the allowlist", "leaves token-bearing temp files"). Committing them to this public repo would publish unverified vulnerability reports. Keep raw findings in the maintainer's private notes, and publish the method, the results and the verified fixes (11 Oct 2026, `experiments/skills-research/README.md` § Files).
- **Gitignored (private)**: `docs/private/`, `trial-runs/` — contain names, contacts, strategy, pricing, legal drafts, and value judgements that don't belong on the public repo. Local-only, backed up by a separate code-backup script, never committed to git. Do not suggest `git add -f` for files here. Conceptually these belong in the founder-only private repo and migrate there at TestFlight cutover (see `project_private_docs_migration_plan.md` memory).

## Seams — what is true in more than one language

A value or name that Python, TypeScript and Swift must all agree on is **declared once and checked everywhere else by a test**. Before grepping for such a thing, look here; before adding one, join an existing mechanism rather than inventing a fourth. No values are written in this section, on purpose: a number copied into prose is one more copy to go stale.

- **Declared in Python, text copies elsewhere** (the serve port): `bristlenose/ports.py` is the source; `tests/test_default_port.py` pins every file that cannot import it and sweeps code for a copy nobody listed. A new copy of the port goes in its `MIRRORS`, or it imports the constant.
- **A contract in data, asserted from both languages**: `tests/fixtures/*-contract.json`, read by pytest and vitest (formats in `docs/design-shared-formats.md`). Change the JSON and both sides must follow.
- **Parity tests that read the other language's source**: `tests/test_*parity*.py` and `tests/test_swift_contract_parity.py`. `_BRISTLENOSE_*` environment names are one: Swift may only set what Python reads (`tests/test_env_name_parity.py`).
- **Derived from the running thing**: `tests/test_serve_export_coverage.py` (routes from `app.openapi()`), `tests/test_entitlements_split.py` (signing), `desktop/scripts/check-*.sh` (Swift-side floors and bundle contents; each needs a caller in `build-all.sh` or CI to count).
- **Not covered, by design**: the website repo's docs. `docs-src/cli.md` and the connect-an-agent page carry CLI facts this repo cannot pin; a CLI change lists them as owed (see Boundaries).

## Deployment targets

Bristlenose runs on three targets: macOS arm64 (primary dev), Linux x86_64 via GitHub Actions CI (release pipeline), and — newly — Claude Code Cloud VMs (ephemeral Ubuntu x86_64,  but reachable when the user picks Cloud in the picker). Cloud is useful for code/test/lint/frontend-build work, **not** for pipeline runs on private interview data. See `docs/design-deployment-targets.md for the audit checklist and use-case boundary table.

## HTML report features

The generated HTML report has interactive features: inline editing (quotes, headings, names), search-as-you-type, view switching, CSV export, tag filter, hidden quotes, and per-participant transcript pages with deep-linked timecodes. Full implementation details in `docs/design-html-report.md`. Key concepts: people file merge strategy, speaker codes, anonymisation boundary, tag filter persistence, hidden quotes with `.bn-hidden` defence-in-depth. See `bristlenose/theme/CLAUDE.md` for CSS/design gotchas, `bristlenose/theme/js/MODULES.md` for JS module details, `bristlenose/theme/CSS-REFERENCE.md` for per-component CSS docs.

Doctor command: `bristlenose doctor` — runtime environment checks. See `docs/design-doctor-and-snap.md`.

Snap + man page: see `docs/design-doctor-and-snap.md` and `docs/release.md`. **`man/bristlenose.1` is a symlink to `bristlenose/data/bristlenose.1`** — single source of truth. Edit either; both update. Validate with `mandoc -Tlint bristlenose/data/bristlenose.1` (macOS-default; `groff` / `nroff` aren't installed). `bump-version.py` refreshes both the version and the `.TH` ISO date on every bump (don't write "March 2026"-style human dates in `.TH` — they bitrot and produce mandoc WARNINGs).

**Auditing the man page mechanically? Unescape roff hyphens first.** Roff escapes `-` as `\-`, and it does so *inside* option names too — `--whisper-model` is written `\-\-whisper\-model`. So the obvious `grep -o '\-\-[a-z-]*'` (or a `--([a-z0-9-]+)` regex) captures only `whisper` and reports `--whisper-model`, `--self-test`, `--no-fetch`, `--skip-transcription` as **missing when they're present** — a whole audit pass of false positives (cost a cycle on 31 Jul 2026). Normalise before comparing: `man.replace("\\-", "-")` then strip font escapes `re.sub(r'\\f[BIRP]', '', man)`, and diff that against `bristlenose <cmd> --help` output. Same trap applies to the `.TH` line and any `grep` for a specific flag.

CLI output: Cargo/uv-style checkmark lines with per-stage timing. Time estimation via Welford's algorithm in `bristlenose/timing.py`. See `bristlenose/stages/CLAUDE.md` for pipeline runtime details.

## Gotchas

**The full entries — the incident, the measurement, the fix — are in [`.claude/gotchas.md`](.claude/gotchas.md), by theme.** Read the theme's section before working in that area; this index is the rule and the tell, nothing more.

**Shell, search and scripting** — [full entries](.claude/gotchas.md#shell-search-and-scripting)

- The Bash tool runs **zsh** on **BSD** macOS: `for f in $LIST` does not split, `$PIPESTATUS` is `$pipestatus`, a word starting `=` is a command lookup, `path=` is `PATH`, `$VAR:x` is a modifier (write `${VAR}:x`), `/dev/tcp` and `log` don't exist (use `/usr/bin/log`), an unmatched glob skips one command and carries on, and an unquoted heredoc runs `$(…)`. Use `gsed`/`ggrep`/`gawk`/`greadlink` or Python; `grep` here is ugrep.
- **An assertion is `cmd || die`, never `cmd && ok`**; chain any step that consumes the previous one's output; `set -e` does nothing inside the Bash tool; print the evidence rather than appending a verdict the shell cannot withhold. `printf "$big" | grep -q` under pipefail misses early matches: use a herestring.
- **A blocked PreToolUse hook refuses the whole Bash call**: never put a blocked pattern in a command, even as a search term; after a refusal assume nothing in the call ran. The leak-scan and `commit-msg` hooks block private filename stems and the private docs path: paraphrase them.
- **`rg -rn` replaces every match with `n`** (rg is recursive already: `rg -n`). A git `dir/**/*.x` pathspec matches nothing at the top level and `for-each-ref`'s `*` stops at `/`; `grep -v name.py` drops every file of that name; a deadline that kills a process but not its group still hangs `$(…)`.
- **`git ls-files` can't see gitignored files**: check existence on disk; a path that doesn't resolve may have moved (search the basename); before writing "recorded nowhere", look in the private notes.
- **A `pgrep -f` / `ps | grep` waiter matches its own command line**; never edit a bash script while a run of it is in flight; a scripted import insert can land inside a parenthesised import (import the module after); U+00A0 shows as a space (check `repr()` before believing an Edit mismatch).
- **Subagents share the scratchpad**: put a session-unique token in paths you'll re-read, and have a probe assert its own identity.
- **Venvs**: make them with `python3.12 -m venv`; `Path.resolve()` on a venv's python gives the base interpreter (use `.absolute()`); renaming the repo folder breaks the venv (clear `__pycache__`, reinstall `-e`).
- **`/sync-board`** joins doc and board on exact titles: put tags after the em dash, register a new numbered category in `KIND_MAP`, archive (never Done) a duplicate title.

**Git, worktrees and concurrent sessions** — [full entries](.claude/gotchas.md#git-worktrees-and-concurrent-sessions)

- **The index is shared between sessions**: commit with `git commit -F- -- <paths>`; check `git diff <file>` for hunks you didn't write; read the `--stat`; never `--amend` or reset another session's commit; a whole-file rewrite can erase their edit; another session's commit briefly stashes your unstaged edits (failures that track your diff and then vanish); a commit from a temporary index (`GIT_INDEX_FILE` + `read-tree`) reverts every commit that landed after the `read-tree`.
- **Any task is a claim about HEAD**: before the first edit, `git log -S` / grep for the fix or feature; a doc comment naming a collaborator is a version stamp; date the session's own commits before reasoning about the log.
- **`git mv` after an unstaged edit commits the old content** (`R100` is the tell); `git diff --quiet` can't see a staged change (use `HEAD` or `status --porcelain`); compare trees, not commits, to ask whether a branch holds unique work.
- **`git checkout` is hooked off in the main repo**: resolve conflicts with `git show :3:path > path`, rescue a file with `git show branch:path > path`. The hook matches the command text, so a `switch` aimed at the website or tap repo is refused too: commit to a branch there through `git worktree add <dir> <branch>`. The native `pre-push` hook checks every ref; never `pre-commit install --hook-type pre-push`.
- **During a release freeze, commit in a separate `git clone --local`** (hooks copied in, no `git switch`) and fetch the branch back as `after-pypi/<v>-…`; a fresh clone's first Swift build misses `GeneratedBuildInfo`.
- **Worktrees** (rare): never remove one from inside it; check absolute paths in Edit calls; they don't inherit gitignored binaries; a sidecar built in one updates only that worktree.
- **Cloud sessions**: local `main` is stale (read `origin/main`); rescue docs from `claude/…` branches with `git show`; use the GitHub MCP for PRs.

**Tests, gates and verification** — [full entries](.claude/gotchas.md#tests-gates-and-verification)

- **Tests must not depend on the machine**: `no_local_llm_config` isolates LLM config; stub installed tools (`which`) and test both answers; a scratch repo that commits needs `user.email`/`user.name`; on Windows call `release_log_file()` before moving an output folder; fake platform stat fields with a proxy, not `os.stat_result`'s dict.
- **Prove a test can fail, and prove each fix is pinned**: mutate each fix alone; pin the caller, not only the helper; run mutation passes under `PYTHONDONTWRITEBYTECODE=1` and assert the mutation landed; a hand-rolled harness runs from inside the mutant copy and matches `[0-9] failed`; undo a mutation by the reverse patch, never by restoring a whole-file copy (it erases a concurrent session's edit); a killed mutation run skips its reverse (grep the marker before committing).
- **A gate that can't fail isn't a gate**: a piped background task's exit code is the last stage's (read the summary line); verifying through a pipe hides the TTY path (a pty you open has a 0×0 window); a gate matching on proximity or a name drifts with the file; a negative fixture against a gate that rejects every fixture must match its row's ✗ line and pair with an intact fixture's ✓ (and `codesign --sign - App.app` re-signs the main executable bare); a trapped Swift `assert` reds the whole suite at 0.000s.
- **Deleting or renaming can orphan a contract**: a deleted component's tests may have been the only witness to a wire contract or helper; an inverted default can orphan what a test really pins; a renamed map key leaves string-literal callers on a working fallback (grep the key as a string, test the destination); a one-line fix can land on the wrong arm of a ternary (re-read the hunk).
- **A harness or audit covers only what it reaches**: a cross-check guarantees up to the function it asserts against; before calling a doc path dead, read the sentence (past tense or a proposal heading is fine).
- **Mocking and timing**: `patch.dict(sys.modules)` around `detect_hardware()` aborts on Apple Silicon, and a mocked package makes submodule imports order-dependent (run touched files alone); `interrupt_main()` doesn't wake a blocked wait (use `signal.pthread_kill`); a lock probed from a helper thread is released in that thread (conftest restores the run's signal handlers after each test); a path-loaded `@dataclass` module goes into `sys.modules` first; a timeout that keeps needing doubling is a hang.
- **E2E**: check `lsof -i :8484` for a stale serve; Node-side `fetch()` needs the bearer token; don't trust `networkidle`; assert `res.ok` inside `page.evaluate`; every suppression is registered in `e2e/ALLOWLIST.md`.
- **CI**: the pytest job has no built frontend (monkeypatch `_STATIC_DIR`); CI runs on `main` pushes and PRs only; the smoke fixture's committed `pipeline-events.jsonl` is a contract; `gen-test-inventory.py` in a scratch worktree writes `"tests": null`; Presidio slow tests need `en_core_web_lg`.
- **Lint**: Ruff F401 reports but never auto-fixes; delete a mis-targeted mypy `# type: ignore`, never re-target it; `from __future__ import annotations` doesn't satisfy F821.

**Python, CLI and code conventions** — [full entries](.claude/gotchas.md#python-cli-and-code-conventions)

- **Rich's `console.print()` eats `[name]`** (`markup=False` or `escape()`); `Console(width=min(80, Console().width))` is intended; export filenames use `safe_filename()`, not `slugify()`.
- **Logging**: `-v` drives the terminal, `BRISTLENOSE_LOG_LEVEL` the file at `<output>/.bristlenose/bristlenose.log`; a message is always one line (pass tracebacks as `exc_info=`); every LLM call logs one `llm_request` line; `BRISTLENOSE_FAKE_THUMBNAILS=1` is for layout tests.
- **Small facts**: `PipelineResult.model_rebuild()` follows `PeopleFile`; `format_finder_date()` imports datetime locally; `doctor.py` imports `platform`/`urllib` in functions (patch at stdlib level); `check_backend()` catches `Exception`. Before deleting a CLI flag or command, grep `desktop/` and `.github/workflows/`.

**Pipeline, data and participant privacy** — [full entries](.claude/gotchas.md#pipeline-data-and-participant-privacy)

- **Rollups and caches lie quietly**: `attempted == succeeded + failed` holds by construction (check across buckets); the pipeline has three stage vocabularies sharing only `transcribe` and `render`; a stage-level `COMPLETE` overrides the per-session map, absence is not a state, and a cache hit must write the manifest forward. The CLI verb is `transcribe`, not `transcribe-only`.
- **User folders**: filter with `is_os_metadata()` (`._*`, `.DS_Store`); a dataless (cloud placeholder) file is read with a bound (`fs.ensure_materialised`), never skipped and never narrated (`docs/design-cloud-files.md`); `.ts` is excluded from media extensions on purpose.
- **Participant data**: `pii_summary.txt`, `llm-calls.jsonl` and the transcription-quality record are re-identification keys, never in an export; `model_copy()` is shallow (clear `words`); only `pii_score_threshold` is wired (PERSON's bar; patterns floor at 0.40); embedded `<script>` JSON escapes `<` `>` `&` (`script_json`); a clean `CredentialStore.set()` proves nothing (`set_verified()`); `record_call` needs three contextvars (`serve_run_context()`).
- **Codebooks**: identical tag counts across a framework's groups are the tell of invented tags; an authored codebook carries only its author's terms, cited.

**i18n** — [full entries](.claude/gotchas.md#i18n)

- **Read § i18n before touching locales**: locale files live in `bristlenose/locales/` only; a new key goes into all 21 full locales (`zh-Hant-HK` takes only real overrides); rewording an `en` value is a 21-file change (`check-locales.py --strict`, pins); a value edit can redden vitest; reuse a key only if it means the same thing; scope locale JSON edits to the block; a new language has 9 registration sites across web, Python and Swift.

**macOS app, Xcode, signing and sandbox** — [full entries](.claude/gotchas.md#macos-app-xcode-signing-and-sandbox)

- **Ask `xcodebuild -showBuildSettings`, not the pbxproj or `.entitlements`**: membership, deployment target and sandboxing aren't readable from the files; an unsigned `.xctest` failing the app's signing needs the test intermediates, PlugIns and maybe `XCBuildData` cleared; only the 4 Mach-O executables carry entitlements.
- **Locale on the Mac**: `Bundle.preferredLocalizations(from:forPreferences: nil)` latches at launch (pass `Locale.preferredLanguages`); `@AppStorage` defaults are not registered defaults.
- **Sandbox and bundle**: transitive bare-name shellouts need `prepend_bundled_to_path()`; `mimetypes.knownfiles = []` before any init; the build-info `-dirty` suffix is `GeneratedBuildInfo.swift`; serve and export use the running version's theme CSS, never a project's baked copy (since 17 Oct 2026); `forkpty: Device not configured` is the process limit (quit Xcode or leaked workers).

**Release, CI and packaging** — [full entries](.claude/gotchas.md#release-ci-and-packaging)

- **Tags and PyPI**: push `main` and the tag separately (never `--tags`); a run that never fired needs tag redelivery, a failed one needs the tag moved to the fix; one commit gets two `ci.yml` runs and the gate is the `workflow_dispatch` one; test-only fixes reuse the tag unless the version reached PyPI.
- **The sidecar**: built from `.venv-sidecar`, not `.venv`; non-`.py` files ship only via the spec's `datas`; a present file isn't an intact one (`check-bundle-integrity.py`); ask the resolver about wheels, `abi3` covers later CPythons; a dependency's minor bump can start telemetry (prove opt-outs on disk).
- **Homebrew**: tap repo `homebrew-bristlenose`; its bot bumps only the url and sha, so a new extra in `post_install` is a tap commit, held on `after-pypi/<v>` until PyPI has it; the formula pip-installs in `post_install`, so anything needing auto-link installs in `def install`; under 6.0 tap trust bare `brew upgrade` skips us (print the fully-qualified name, pass `HOMEBREW_NO_ASK=1`).
- **Website**: bristlenose.app has two privacy pages plus terms, and a change to what leaves the machine edits all three. Audit export CSS selectors on whole tokens and QA them on a fresh project.

Area gotchas live with the code: React/TypeScript/frontend gotchas (routing, video player, stores, testing), see `frontend/CLAUDE.md`; pipeline runtime gotchas (resume, caching, llm_client lifecycle, metadata), see `bristlenose/stages/CLAUDE.md`; stage/pipeline gotchas (topic maps, transcripts, coverage, speaker codes), see `bristlenose/stages/CLAUDE.md`; JS/CSS/report gotchas (load order, modals, hidden quotes, toolbar), see `bristlenose/theme/CLAUDE.md`; LLM/provider gotchas (Azure, Ollama, provider registry, max_tokens), see `bristlenose/llm/CLAUDE.md`.

## Reference docs (read when working in these areas)

**Must-read before writing user-facing text:**
- `docs/glossary.md` — terminology + tone guide
- `docs/platform-text-map.md` — shared/desktop/CLI text forking, `dt()`/`ct()` inventory
- `docs/design-shared-formats.md` — **read before writing any `format*` helper that renders a value a user reads.** The register of formats duplicated across Python / TypeScript / Swift (pinned by `tests/fixtures/shared-format-contract.json`). One stem per format, house casing per language (`duration_human` / `formatDurationHuman` / `DurationFormat.human`); the `timecode` format also has a PARSED half, so the reader regex in `pipeline.py` must stay `\d{1,2}`. **Before adding a `format*` function, check the register, and before changing a rendered format, check whether anything parses it back.** History and open holes: [`.claude/gotchas.md`](.claude/gotchas.md#long-entries-moved-from-the-root-5-nov-2026).

**Must-read before touching tag suggestion, telemetry, or data governance:**
- `docs/methodology/` — canonical methodology docs. Treat as authoritative: when code and doc disagree, the doc is the spec and the code is wrong.
  - `tag-rejections-are-great.md` — rejection-telemetry theory, alpha experiments, six-field data model, ten-year ratchet endgame
  - `consent-gradient.md` — Level 0–3 data-governance gradient, sensitivity model, consent UX principles, sequencing discipline
  - `framework-arc-quarterly-review.md` — quarterly review template and the long-arc commitments it reviews against

**Sibling CLAUDE.md files:** `frontend/`, `bristlenose/theme/`, `bristlenose/stages/`, `bristlenose/llm/`, `bristlenose/server/`, `desktop/`. Each keeps rules, conventions and a one-line-per-entry **Gotchas index**; the full entries sit in a `gotchas.md` beside it (`desktop/` also has `reference.md` for long prose sections). **Keep a CLAUDE.md short:** a new gotcha goes in that `gotchas.md` with its headline added to the index, never as a long entry in CLAUDE.md. A comment that cites "`<dir>/CLAUDE.md`" for a gotcha means that `gotchas.md`

**Cross-cutting:**
- `docs/design-feature-flags.md` — **read before gating anything.** Five mechanisms across three codebases, chosen by the question the gate answers: parked-feature flags (SPA only, `featureFlags.ts`), Swift compile-time conditions (`#if DEBUG`, `DistributionChannel`), runtime host detection (`_BRISTLENOSE_*`, `isEmbedded()`/`isExportMode()`), debug seeds (`BRISTLENOSE_DEBUG_*`), and the user diagnostics preference. Python and Swift have no parked-feature flag yet; the doc gives the shape to copy

**Per-area reference docs** (frontend/UI, pipeline/backend, export, desktop, assistant surfaces, analysis and research methodology, i18n, codebook, HTML report/dashboard, ops/release) are in [`.claude/reference-docs.md`](.claude/reference-docs.md): read the group for the area you are working in. **Before touching the release chain** (`scripts/release.sh`, the gates), read the four release docs listed under Ops / release there: `scripts/README.md`, `desktop/scripts/REPORT-STYLE.md`, `docs/design-release-machine.md`, `docs/design-release-principles.md`.

## Working preferences

### Branch workflow (solo — trunk by default)

**Solo project; the default is trunk.** Work directly on `main` in the main repo, commit at every green checkpoint, and do not spin a branch or worktree per feature (a branch is a free pointer; a worktree costs an env build). Checkpoint with `git branch -f checkpoint`; undo with `git revert <sha>`; the panic button is `git reflog`. A worktree is the rare exception, only when two envs must be live at once, and then only via `/new-branch` (never hand-rolled). Session-start check: `pwd`, `git branch --show-current`, the venv minor must match `.tool-versions`. A handoff or plan's default next step is work on `main`, not a `/new-branch` invocation. If `HANDOFF.md` exists, read it first, but handoffs are not specs: `git log -3 -p` the files it names and raise any contradicting recent commit before planning. If the venv minor differs from `.tool-versions`, rebuild with `python3.12 -m venv` + `pip install -e '.[dev,serve]'`; don't use `uv` or `mise`. Full text and rollback recipes: [`.claude/branch-workflow.md`](.claude/branch-workflow.md).

### General

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- **Self-check at end of task**: fewer unnecessary changes in the diff than last time? clarifying questions asked *before* implementing rather than after a wrong turn? no rewrite mid-task because the first pass was overcomplicated? If any of those is "no," that's the lesson for next time
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")
- **Fix commits carry a `Found-by:` trailer** naming how the defect surfaced: `review` (a review run or agent), `register` (the lifecycle or failure-mode register), `ci`, `own-use` (the maintainer's trial runs), or `user` (an outside report). Skip it on features and docs. It exists so the next defect count has fewer "unknown" sources (22% of serious fixes in the 5 Nov 2026 defect-mining pass had no recorded source); no hook, no gate
- **Human QA after each task**: when you finish a task, suggest only the checks a human needs to do that automated tests can't cover (visual regression, browser interaction, UX feel). Skip this for pure data/logic work where unit tests are sufficient. Include copy-pasteable commands to make it easy (e.g. server start command, URL to open). Don't duplicate what pytest already covers
- **NEVER use Claude Code preview tools (`preview_start`, `preview_screenshot`, `preview_snapshot`, `preview_eval`, etc.) for QA.** They consistently fail for Bristlenose — wrong port, missing Vite HMR, white-on-white rendering, incomplete React mount. Every attempt wastes time. Bristlenose needs the full stack (Vite dev server on 5173 + FastAPI serve on 8484) running together. For QA, tell the user to run the full stack in their own browser:
  ```
  .venv/bin/bristlenose serve --dev trial-runs/project-ikea
  ```
  `--dev` auto-starts Vite on :5173 as a subprocess (cleaned up on exit). Then open http://localhost:8484/report/. For worktrees: use the port from `.claude/launch.json`

### Release timing (evening releases)

**The act that lands a release is the tag push.** It waits for after 9pm London on a **working day**; weekends and UK bank holidays: any time (check the gov.uk feed, never derive the holiday). Push `main` any time; the tag goes **last**, after the Mac uploads and a strict CI verdict on `main`; push `main` and the tag as two separate pushes, never `--tags`. **A running `release.sh run` freezes `main` locally**; work that must not go live before PyPI waits on an `after-pypi/<version>` branch (also `after-<channel>/<version>`; `release.sh verify` lists holds; a fix the release itself needs goes in with `BN_RELEASE_FREEZE_OK=1 git commit …`). After the tag, **verify on PyPI** with the version-specific endpoint (`/pypi/bristlenose/<X.Y.Z>/json`, 200 = published); the index JSON is CDN-cached and can read stale. The 9pm wait is a guideline, not a gate; push earlier when something is urgent. Full rules, the holiday command, the poll loop and the reasoning: [`docs/release-timing.md`](docs/release-timing.md).

## Gate policy — no gate goes soft by default

`continue-on-error` is how a check stops being a check. Sometimes right; never
open-ended. **Every soft gate declares a disposition** in
`docs/testing/soft-gates.json`, enforced by `scripts/check-gate-policy.py` in CI:

- **ratchet** — a number that may not rise (`docs/testing/ratchet.json`,
  `scripts/check-ratchet.py`). For debt too large to fix now and too easy to grow.
  mypy's 238 errors is the case it was built for.
- **expires** — a date by which somebody decides again. For things outside our
  control, where "fix it" is not the available action (upstream CVE feeds).
- **conditional** — soft here, hard where it matters. The macOS matrix is the
  model: informational on a push, blocking on a release tag.

**Why it is mechanical and not a convention:** `docs/design-ci.md` wrote
*"informational initially — promote to blocking once stable"*, the promotion
never came, and the Swift suite went unrun for three months while `v0.29.0`
shipped on nine channels with it red. A rule nobody is obliged to check is
indistinguishable from no rule. Reasoning and the other seven gaps:
`docs/testing/gaps.md`. The generated map of what runs where:
`docs/testing/inventory.md` (never hand-edit it).

**Adding a ratcheted number?** `scripts/check-ratchet.py --tighten` only lowers
a ceiling. Raising one is a deliberate edit in a commit that says why.

**A gate script with no caller is not a gate.** `desktop/scripts/check-deployment-floors.sh`
existed from 3 Sep 2026 while five documents said the floors were "pinned by" it — and
nothing invoked it until 12 Sep, when `build-all.sh` gained it as step 1c. Five consistent
statements, one unwired script: consistency is not correctness. When a doc says "pinned by
X" or "enforced by X", `grep -rn X desktop/scripts .github/workflows scripts` for the
*caller* before believing it — the script's own header proves only that it can fail.

**The same failure one level down: a dispatch table that skips names it lacks.** `run_preflight` listed `serve_deps` for four commands, and its `_check_fns` dict had no entry for it. The loop does `fn = _check_fns.get(name); if fn is not None:`, so the check never ran and nothing said so, from May until 11 Oct 2026 (`fd6286ee`). Worse, three tests asserted the *short* result counts, pinning the gap. Any name-to-runner table needs a structural test that every listed name resolves (`test_every_listed_check_runs`), because `.get()` plus a None-skip is a gate that cannot fail.

## Before committing

1. `.venv/bin/python -m pytest tests/` — all pass
2. `.venv/bin/ruff check .` — no lint errors (**note: check whole repo, not just `bristlenose/`** — CI runs `ruff check .` which includes `tests/`)

**CI parity matters.** The release workflow failed for 7 versions (v0.6.7–v0.6.13) because local checks didn't match CI:
- Local ran `ruff check bristlenose/`, CI runs `ruff check .` — test file lint errors went unnoticed
- Tests that depend on environment (API keys, installed tools) must mock those dependencies — CI has no keys configured

## Branch switching

Before switching: commit, run the tests and `ruff check .`. After: clear `__pycache__`, `pip install -e .`, report `git status` and `git log --oneline -3` (stale editable-install bytecode caused the PreferencesFile incident). Warn on failing tests or lint before switching; never switch with uncommitted work. The checklist in full: [`.claude/branch-workflow.md`](.claude/branch-workflow.md).

## Session-end housekeeping

### Shared Claude / Codex handoffs

- Use the existing records, not a separate agent progress register: `TODO.md` for the current handoff, `docs/private/100days.md` for backlog, and the relevant design/decision doc for owner rulings. Private docs stay gitignored; never force-add them.
- For each reliability ruling, record its id, owner's scope and deferrals, files changed, exact verification and review scope, and whether work is uncommitted, committed (sha), pushed or released. Name the agent; distinguish self-review from independent review. Leave a one-line release-note candidate in TODO for user-facing changes; `CHANGELOG.md` and README release entries are written at release time, not under an invented Unreleased heading.
- On pickup, read this guidance, TODO, the relevant decision record and recent git history; inspect the working tree before editing. One agent owns a ruling's edits at a time in the shared checkout. Re-read files before changing them; preserve unrelated edits and stage only owned paths.
- Respect `.claude/current-task.json`, workflow logs, review receipts and end-session sentinels as workflow state: do not overwrite another session's active task or mark a workflow completed unless its required steps actually ran. Claude auto-memory is supplementary; an agreed decision must also live in the shared project records.

**Standing line from the 30 Oct 2026 consolidation:** no push, tag, release or public changelog update is authorised. `codex/study-access-poc` stays unmerged and is not continued by default, and the Claude worktree `reliability/ruling-4-sent-register` is not retired until its owner confirms it is idle. The full account (what was merged, preserved and retired, and which branches and stashes remain) is in [`docs/session-consolidation-2026-10-30.md`](docs/session-consolidation-2026-10-30.md); read it before resuming any branch or stash named there.

When the user signals end of session, **run `/end-session`** — the skill handles verify, document, commit, and close-out. See `.claude/skills/end-session/SKILL.md` for the full checklist.

## Current status

**Internal TestFlight since 14 Jul 2026** — shipping build **0.44.0 (6058)** — first build accepted by App Store Connect: **0.20.0 (2068)**, App-Sandbox + Hardened-Runtime + arm64-only, signed Apple Distribution.

**Latest release: 0.44.0, 2 Nov 2026** — tag `v0.44.0` on `2a9e0769d`, verified 8 of 9 channels at tag time (website deployed after; winget follows). Each release's account (what shipped, every stop, run times) is in [`docs/release-log.md`](docs/release-log.md), versions in [CHANGELOG.md](CHANGELOG.md), active work in [TODO.md](TODO.md). The paragraphs this section carried release by release, 0.29.0–0.38.0, are kept verbatim in [`docs/status-history.md`](docs/status-history.md). **A release updates the shipping-build and latest-release lines above and writes its account in the release log; it does not add a paragraph here.**

**Standing facts a release needs:**
- **Entitlements split, gated by `tests/test_entitlements_split.py`:** the Mac App Store build carries one app group, `group.app.bristlenose`; the Developer-ID `.dmg` must not (a `CODE_SIGN_ENTITLEMENTS` override in `build-dmg.sh`). `associated-domains` (`webcredentials:bristlenose.app`, Zoom's HTTPS sign-in callback) is on all three files (the `.dmg` too since 18 Oct 2026, so Zoom import works there; its Developer ID profile is minted at export with the capability); the App-ID capability is on and the `Bristlenose Mac App Store` profile was regenerated with it on 17 Oct 2026 (a release archive needs that profile, not the 12 Sep one). Neither entitlements file is `skip-worktree` (`git ls-files -v | grep "^S"`).
- **Fedora Copr is live** (since 28 Aug 2026, fedora-43-x86_64): CVE tracking of the vendored wheelhouse is ours, `.copr/Makefile` pins Fedora's Python, and the Copr token expires **23 Feb 2027** (renew). The SRPM job runs on any architecture, so `rpm/make-srpm.sh` pins x86_64 wheels; confirm a publish from `repodata/`, not the results listing (`docs/design-fedora-packaging.md` §7).
- **`v0.26.0` was tagged and abandoned**; treat it as a version that never existed.

React migration complete; bundled-sidecar desktop is the primary distribution path; the CLI ships on PyPI, Homebrew, Snap and Fedora Copr; the static render is a sealed byproduct.

- **R114 minimal recovery branch:** `docs/design-study-recovery-guard.md` owns implementation evidence. Machine-owned recovery and pre-write startup refusal with approved native presentation are merged into local main via5a7830935/014c04685 (29 Oct); combined main gate 2846native/0fail and343Python/2xfail. No push/release. Retry must not restart an already-running server or launch analysis. Do not continue the larger handover prototype by default; `docs/private/100days.md` in main is the long-term planning source of truth; linked designs/experiments are supporting detail.

- **R114 UX gate (owner, 28 Oct):** complete mockup, review and explicit owner approval before any new UX implementation/activation; reuse existing patterns, invent no new UX features. Owner approved the revised startup-refusal flow and resumed on29Oct. Read-only browsing remains deferred; see minimal delivery doc and main100days.
