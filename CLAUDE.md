# Bristlenose — Project Context for Claude

## What this is

Bristlenose takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report — extracted quotes, themes, sentiment, friction points, user journeys — that the researcher edits, shares, and keeps as a file they own. The user is a working researcher under deadline, not an engineer.

The pipeline runs on the user's own machine; the analysis itself is a **cloud LLM call** to Claude (Anthropic), ChatGPT (OpenAI), Azure OpenAI (enterprise), or Gemini (Google), and that is the normal, recommended, everyday path. Local models via Ollama are a supported minority option (slower, wants a capable machine, technical setup) — never the proud default.

**Don't pitch or reason about Bristlenose as "local-first" or "privacy-first".** It isn't the stance, and "nothing leaves your laptop" is plainly false: the analysis *is* an outbound LLM call, and researchers' recordings and deliverables typically already live on a client's Teams/SharePoint/Drive. Lead with the outcome and the owned artefact. This does **not** relax participant-data governance — PII redaction, re-identification keys and retention remain real craft obligations (`docs/methodology/consent-gradient.md`).

## Commands

- `.venv/bin/python -m pytest tests/` — run tests. **Free**: `addopts = -m "not slow"` in `pyproject.toml` deselects the `slow` marker, so the everyday command never makes a paid LLM call. It used to — until 3 Sep 2026 the bare command billed the account on every run, and a session following these instructions had no way to know without reading the test files
- `.venv/bin/python -m pytest tests/ -m slow` — the **paid** suite: real LLM calls, ~$0.01/run (a `-m` on the command line overrides `addopts`). Opt in deliberately; it is excluded from CI and ratcheted by `scripts/check-ratchet.py` as coverage given up. With no credit it now **skips** with a "SKIPPED, NOT PASSED" message rather than erroring — a genuine `BAD_REQUEST` still fails
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

Scene colours: `bristlenose/utils/scene_colour.py` — one colour per speaker turn, for the session tapestry (what was on screen, not who spoke). Computed in `run()` just before render (on a first analysis, also per session in the readable chain, `readable_chain.py`, so a row arrives with its colours), written to `.bristlenose/intermediate/scene-colours/`, about 1.5 s per hour of video. **Its constants are the colour lab's defaults** (`experiments/session-tapestry/colour-lab.html`, regenerated by `colour_lab.py`). Retune in the lab, then change both. Serve reads them in `GET /api/projects/{id}/tapestry` (`server/routes/tapestry.py`), drawn by `frontend/src/components/SessionTapestry.tsx` as a disclosure slice under each Sessions-grid row, and closed as a skinny participant strip under the row (`TapestryPreview.tsx`) that the timeline springs out of (`utils/tapestryMotion.ts`). **Scene strips** (`bristlenose/utils/scene_strip.py`, every frame at 4 fps, what was on screen moment by moment, drawn inside the clips; the notch per scene change is parked behind `featureFlags.sceneNotches`) are computed by **serve, never the pipeline** — a background thread after the report is readable (`server/scene_strips.py`), so a run never waits on them. See `experiments/session-tapestry/README.md` § Scene stripes. The same thread then takes the **hover thumbnail**'s frames (`utils/turn_frames.py`: one per participant turn and one per colour change inside it), served only behind the bearer token at `/sessions/{sid}/turn-frames` and kept out of the HTML export, since they are participants' screens — § Hover thumbnail.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. Override with `--output`. See `bristlenose/stages/CLAUDE.md` for the full directory layout.

Key helpers: `OutputPaths` in `output_paths.py` (consistent path construction), `slugify()` in `utils/text.py` (project names in filenames — lowercase, hyphens, max 50 chars). Report filenames include project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`, `frontend/`, `desktop/`
- **Design artifacts** (tracked, not shipped): `docs/mockups/`, `docs/design-system/`, `experiments/` — HTML mockups, style guides, throwaway prototypes. These are working materials for contributors, kept in the tree for backup and collaboration. Users never navigate to them. Add new mockups to `docs/mockups/`, not the repo root. **Serve mode auto-discovery**: `bristlenose serve --dev` mounts all three directories and auto-discovers `*.html` files for the Design section in the About tab (`_build_dev_section_html()` in `app.py`). New HTML files added to these directories appear automatically — no code changes needed. **`experiments/` is excluded from `ruff check`** (per `pyproject.toml`) — throwaway research scripts don't need to pass lint; don't waste cycles fixing F401 unused-imports in there
- **User-facing docs live in the website repo, not here.** The single-page `docs/manual.md` was retired at the website v2 cutover (archived to `docs/archive/manual.md`; `bristlenose.app/manual.html` now 404s by design). User docs are per-topic Markdown in the website repo's `docs-src/` tree, published under `bristlenose.app/docs/`. **When a CLI change lands, the user-facing surfaces to true are: `README.md`, `man/bristlenose.1`, and the website's `docs-src/cli.md`** — three places, no fourth. Don't edit `docs/archive/manual.md` to keep it current.
- **Marketing site** (deployed, separate private repo): the marketing site, server-side ops endpoints, deploy script, and ancillary publishing/PR assets live in a separate private deploy repo on the maintainer's machine. Its `build.py` renders `docs-src/*.md` plus a few pages sourced live from this repo (e.g. the changelog, read straight from `CHANGELOG.md` so there's no second copy to drift). **Note:** the rsync deploy needs SSH agent access and is run manually by the maintainer. **`build.py` renders only `docs/` — it does NOT copy `assets/`; `deploy.sh` does that at ship time.** So previewing a local `site.css`/`site.js` edit serves the *stale* copy already in `build/site/assets/`, with no error — the page renders, the change just isn't there (cost a debug cycle 3 Aug 2026 chasing an empty icon span that was actually a stale `ICONS` map). `rsync -a assets/ build/site/assets/` after `./build.py` before previewing. **And the host caches assets for THIRTY DAYS.** DreamHost's `mod_expires` default serves `/assets/*` with `max-age=2592000` (HTML gets 600); it is server-side, sits in no `.htaccess` the repo owns, and nothing in git will ever show it to you. With pages referencing a bare `/assets/site.js`, a returning visitor keeps whatever CSS/JS they first cached for a month — and a reload does **not** help, because the file is still inside its freshness window so the browser never asks the server. Measured 24 Sep 2026: a mobile-nav fix was deployed and verified live by `curl` and by a 41-page headless sweep, and went on doing nothing on the maintainer's phone. **Every one of those checks fetches fresh, so none of them can see this class of bug** — only a device that has been to the site before can. `build.py` now stamps a content hash into each asset reference (`site.js?v=<sha8>`), which the 10-minute HTML cache propagates within minutes; a new asset URL cannot be served from a cache that has never seen it. **Tell: a deployed change that works for everyone except the people who were already using the site.** **`deploy.sh` publishes the website repo's WORKING TREE, not its last commit** — `cd "$(dirname "$0")"` then build and rsync, with no check for uncommitted edits. So when another session has the homepage or stylesheets half-edited, a deploy ships their work-in-progress to bristlenose.app alongside yours (5 Oct 2026: six uncommitted files of typography work sat in the tree at the 0.34.0 deploy). Deploy from a clean checkout of the committed HEAD instead — `git -C ~/Code/bristlenose-website worktree add --detach <dir> HEAD`, then `<dir>/deploy.sh --yes`; it reads the changelog from this repo by absolute path, so it works from anywhere. Never stash or commit the other session's edits to clear the way. **And during a release run, a website deploy publishes the release's changelog early:** `build.py` renders the changelog page and stamps the footer version from this repo's working tree, which already holds the new version's entry before PyPI does. Point it at the last released tag instead: `git worktree add --detach <dir> v<last>`, then `BRISTLENOSE_PUBLIC_REPO=<dir> <site-worktree>/deploy.sh --yes` (`deploy.sh`'s footer check reads the same variable). Done this way for the 18 Oct 2026 privacy deploy during 0.41.0. Illustration/screenshot conventions for the docs live in `docs/design-docs-system.md` Part D
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`
- **Raw agent-review output stays private; conclusions go public.** A fan-out review produces findings nobody has verified, and some are security-shaped ("bypasses the allowlist", "leaves token-bearing temp files"). Committing them to this public repo would publish unverified vulnerability reports. Keep raw findings in the maintainer's private notes, and publish the method, the results and the verified fixes (11 Oct 2026, `experiments/skills-research/README.md` § Files).
- **Gitignored (private)**: `docs/private/`, `trial-runs/` — contain names, contacts, strategy, pricing, legal drafts, and value judgements that don't belong on the public repo. Local-only, backed up by a separate code-backup script, never committed to git. Do not suggest `git add -f` for files here. Conceptually these belong in the founder-only private repo and migrate there at TestFlight cutover (see `project_private_docs_migration_plan.md` memory).

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

- **The index is shared between sessions**: commit with `git commit -F- -- <paths>`; check `git diff <file>` for hunks you didn't write; read the `--stat`; never `--amend` or reset another session's commit; a whole-file rewrite can erase their edit; another session's commit briefly stashes your unstaged edits (failures that track your diff and then vanish).
- **Any task is a claim about HEAD**: before the first edit, `git log -S` / grep for the fix or feature; a doc comment naming a collaborator is a version stamp; date the session's own commits before reasoning about the log.
- **`git mv` after an unstaged edit commits the old content** (`R100` is the tell); `git diff --quiet` can't see a staged change (use `HEAD` or `status --porcelain`); compare trees, not commits, to ask whether a branch holds unique work.
- **`git checkout` is hooked off in the main repo**: resolve conflicts with `git show :3:path > path`, rescue a file with `git show branch:path > path`. The native `pre-push` hook checks every ref; never `pre-commit install --hook-type pre-push`.
- **During a release freeze, commit in a separate `git clone --local`** (hooks copied in, no `git switch`) and fetch the branch back as `after-pypi/<v>-…`; a fresh clone's first Swift build misses `GeneratedBuildInfo`.
- **Worktrees** (rare): never remove one from inside it; check absolute paths in Edit calls; they don't inherit gitignored binaries; a sidecar built in one updates only that worktree.
- **Cloud sessions**: local `main` is stale (read `origin/main`); rescue docs from `claude/…` branches with `git show`; use the GitHub MCP for PRs.

**Tests, gates and verification** — [full entries](.claude/gotchas.md#tests-gates-and-verification)

- **Tests must not depend on the machine**: `no_local_llm_config` isolates LLM config; stub installed tools (`which`) and test both answers; a scratch repo that commits needs `user.email`/`user.name`; on Windows call `release_log_file()` before moving an output folder; fake platform stat fields with a proxy, not `os.stat_result`'s dict.
- **Prove a test can fail, and prove each fix is pinned**: mutate each fix alone; pin the caller, not only the helper; run mutation passes under `PYTHONDONTWRITEBYTECODE=1` and assert the mutation landed; a hand-rolled harness runs from inside the mutant copy and matches `[0-9] failed`; undo a mutation by the reverse patch, never by restoring a whole-file copy (it erases a concurrent session's edit); a killed mutation run skips its reverse (grep the marker before committing).
- **A gate that can't fail isn't a gate**: a piped background task's exit code is the last stage's (read the summary line); verifying through a pipe hides the TTY path (a pty you open has a 0×0 window); a gate matching on proximity or a name drifts with the file; a trapped Swift `assert` reds the whole suite at 0.000s.
- **Deleting or renaming can orphan a contract**: a deleted component's tests may have been the only witness to a wire contract or helper; an inverted default can orphan what a test really pins; a renamed map key leaves string-literal callers on a working fallback (grep the key as a string, test the destination); a one-line fix can land on the wrong arm of a ternary (re-read the hunk).
- **A harness or audit covers only what it reaches**: a cross-check guarantees up to the function it asserts against; before calling a doc path dead, read the sentence (past tense or a proposal heading is fine).
- **Mocking and timing**: `patch.dict(sys.modules)` around `detect_hardware()` aborts on Apple Silicon, and a mocked package makes submodule imports order-dependent (run touched files alone); `interrupt_main()` doesn't wake a blocked wait (use `signal.pthread_kill`); a lock probed from a helper thread is released in that thread (conftest restores the run's signal handlers after each test); a path-loaded `@dataclass` module goes into `sys.modules` first; a timeout that keeps needing doubling is a hang.
- **E2E**: check `lsof -i :8150` for a stale serve; Node-side `fetch()` needs the bearer token; don't trust `networkidle`; assert `res.ok` inside `page.evaluate`; every suppression is registered in `e2e/ALLOWLIST.md`.
- **CI**: the pytest job has no built frontend (monkeypatch `_STATIC_DIR`); CI runs on `main` pushes and PRs only; the smoke fixture's committed `pipeline-events.jsonl` is a contract; `gen-test-inventory.py` in a scratch worktree writes `"tests": null`; Presidio slow tests need `en_core_web_lg`.
- **Lint**: Ruff F401 reports but never auto-fixes; delete a mis-targeted mypy `# type: ignore`, never re-target it; `from __future__ import annotations` doesn't satisfy F821.

**Python, CLI and code conventions** — [full entries](.claude/gotchas.md#python-cli-and-code-conventions)

- **Rich's `console.print()` eats `[name]`** (`markup=False` or `escape()`); `Console(width=min(80, Console().width))` is intended; export filenames use `safe_filename()`, not `slugify()`.
- **Logging**: `-v` drives the terminal, `BRISTLENOSE_LOG_LEVEL` the file at `<output>/.bristlenose/bristlenose.log`; a message is always one line (pass tracebacks as `exc_info=`); every LLM call logs one `llm_request` line; `BRISTLENOSE_FAKE_THUMBNAILS=1` is for layout tests.
- **Small facts**: `PipelineResult.model_rebuild()` follows `PeopleFile`; `format_finder_date()` imports datetime locally; `doctor.py` imports `platform`/`urllib` in functions (patch at stdlib level); `check_backend()` catches `Exception`. Before deleting a CLI flag or command, grep `desktop/` and `.github/workflows/`.

**Pipeline, data and participant privacy** — [full entries](.claude/gotchas.md#pipeline-data-and-participant-privacy)

- **Rollups and caches lie quietly**: `attempted == succeeded + failed` holds by construction (check across buckets); the pipeline has three stage vocabularies sharing only `transcribe` and `render`; a stage-level `COMPLETE` overrides the per-session map, absence is not a state, and a cache hit must write the manifest forward. The CLI verb is `transcribe`, not `transcribe-only`.
- **User folders**: filter with `is_os_metadata()` (`._*`, `.DS_Store`) and skip dataless iCloud files before reading; `.ts` is excluded from media extensions on purpose.
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
- **Homebrew**: tap repo `homebrew-bristlenose`; the formula pip-installs in `post_install`, so anything needing auto-link installs in `def install`; under 6.0 tap trust bare `brew upgrade` skips us (print the fully-qualified name, pass `HOMEBREW_NO_ASK=1`).
- **Website**: bristlenose.app has two privacy pages plus terms, and a change to what leaves the machine edits all three. Audit export CSS selectors on whole tokens and QA them on a fresh project.

Area gotchas live with the code: React/TypeScript/frontend gotchas (routing, video player, stores, testing), see `frontend/CLAUDE.md`; pipeline runtime gotchas (resume, caching, llm_client lifecycle, metadata), see `bristlenose/stages/CLAUDE.md`; stage/pipeline gotchas (topic maps, transcripts, coverage, speaker codes), see `bristlenose/stages/CLAUDE.md`; JS/CSS/report gotchas (load order, modals, hidden quotes, toolbar), see `bristlenose/theme/CLAUDE.md`; LLM/provider gotchas (Azure, Ollama, provider registry, max_tokens), see `bristlenose/llm/CLAUDE.md`.

## Reference docs (read when working in these areas)

**Must-read before writing user-facing text:**
- `docs/glossary.md` — terminology + tone guide
- `docs/platform-text-map.md` — shared/desktop/CLI text forking, `dt()`/`ct()` inventory
- `docs/design-shared-formats.md` — **read before writing any `format*` helper that renders a value a user reads.** The register of formats duplicated across Python / TypeScript / Swift: which agree (pinned by `tests/fixtures/shared-format-contract.json`, asserted from both pytest and vitest), which don't, and which differ on purpose. Two classes: *parsed* contracts, where a mismatch breaks function and which were already handled, and *rendered* ones, where a mismatch is a visible inconsistency — every drift measured in the 22 Aug 2026 audit was the second kind. Nomenclature rule: **one stem per format, house casing per language** (`duration_human` / `formatDurationHuman` / `DurationFormat.human`), because a family with no shared stem is a family no grep will find — which is exactly how session duration reached four live renderings. `timecode` closed 22 Aug 2026 (was 9 implementations / 3 formats; now one per language — minutes padded, hours never: `05:30`, `1:12:45`). **It is also the one entry with a PARSED half** — transcript .txt/.md files are a round-trip format, so the reader regex in `pipeline.py` must stay `\d{1,2}`; it was `\d{2}` and a `[1:00:00]` segment was dropped *silently*, no error, a short transcript the only symptom. `finder_filename` closed the same day (floor vs ceil on the 2:1 split — they disagreed on every 3-, 4- and 6-char extension, i.e. every common media file). No open gaps as of 22 Aug 2026 — and three by 12 Sep 2026, found by the time audit (`docs/time-defects.md`): a fourth Python `timecode` copy in `miro_board.py` that the enrolment gate could not see (it asserts identity across four import sites of seven), `finder_date` pinned by zero cases, and a zero-duration fork catalogued but asserted by nothing. The register's own "Open holes" block lists them; the first is closed, the other two are Tier 2. **Before adding a `format*` function, check whether the format is already in the register — and before changing a rendered format, check whether anything parses it back, every reader and not just the one named after the format.**

**Must-read before touching tag suggestion, telemetry, or data governance:**
- `docs/methodology/` — canonical methodology docs. Treat as authoritative: when code and doc disagree, the doc is the spec and the code is wrong.
  - `tag-rejections-are-great.md` — rejection-telemetry theory, alpha experiments, six-field data model, ten-year ratchet endgame
  - `consent-gradient.md` — Level 0–3 data-governance gradient, sensitivity model, consent UX principles, sequencing discipline
  - `framework-arc-quarterly-review.md` — quarterly review template and the long-arc commitments it reviews against

**Sibling CLAUDE.md files:** `frontend/`, `bristlenose/theme/`, `bristlenose/stages/`, `bristlenose/llm/`, `bristlenose/server/`, `desktop/`

**Cross-cutting:**
- `docs/design-feature-flags.md` — **read before gating anything.** Five mechanisms across three codebases, chosen by the question the gate answers: parked-feature flags (SPA only, `featureFlags.ts`), Swift compile-time conditions (`#if DEBUG`, `DistributionChannel`), runtime host detection (`_BRISTLENOSE_*`, `isEmbedded()`/`isExportMode()`), debug seeds (`BRISTLENOSE_DEBUG_*`), and the user diagnostics preference. Python and Swift have no parked-feature flag yet; the doc gives the shape to copy

**Frontend / UI:**
- `bristlenose/theme/js/MODULES.md`, `bristlenose/theme/CSS-REFERENCE.md` — JS + CSS component reference
- `docs/design-sidebar-playground.md` — 6-column grid, overlay, drag-resize, minimap, dev playground
- `docs/design-responsive-layout.md` — quote grid, density, breakpoints
- `docs/design-react-migration.md` — active migration plan
- `docs/design-react-component-library.md` — 16 primitives
- `docs/design-minimap.md`, `docs/design-inspector-panel.md`, `docs/design-finding-weight.md`

**Pipeline / backend:**
- `docs/design-analysis-lifecycle.md` — **the cross-cutting view of analyse / re-analyse / incremental**: one state machine, sequence diagrams, the affordance inventory, and the observed failure modes (four outcomes, not three). Read before adding or changing any analysis-triggering control
- `docs/design-pipeline-resilience.md` — manifest, event sourcing, resume, provenance
- `docs/design-screens.md` — **the plan for screens (proposal, 13 Oct 2026; one project, Mac first, OCR engine pluggable):** joins what was said, what was on the shared screen and which screen they were on. Read before touching OCR, screen text, the Screens lens, or quote↔screen joins; its two evidence records are `design-screen-text-search.md` and `design-screens-lens.md`. **Its §4 privacy line was corrected 17 Oct 2026: Bristlenose never sends screens anywhere on its own (never to the LLM); anything the researcher chooses — exports, their cloud tools, MCP — is open.** The exports (folder, clipboard, Miro board) are planned in `design-screens-export.md`
- `docs/design-project-identity.md` — **decided 13 Oct 2026, built 15–16 Oct (phases 2, 4, 5 and 6; phase 3 obviated): a study is its database plus a marker id (`study_marker.py`, with a visible `bristlenose-study.txt` beacon Locate… finds by Spotlight), a recording is a content fingerprint (`utils/fingerprint.py`, registry version 3), a path is a hint that heals.** §11a records where the build departed from the note and the known limits. Read before touching the project row match, `sessions.json` keys, `SourceFile.path`, the MCP project key, or the sidebar's drop and relocate code
- `docs/design-lifecycle-failure-modes.md` — **read before changing where a project's database, output or events live, or anything that runs across a stash, restore, crash, rename or move.** The register of lifecycle failure modes, each designed out with its proving test or open with its reason (its § The score has the count); `tests/test_lifecycle_scenarios.py` engineers them against the real server and stash code, with strict xfails for the open ones
- `docs/design-pipeline-diagnostic-popover.md` — **read before adding any new error / status / message that surfaces in the popover, the pill, the sidebar glyph, or any toast.** Five-kind `MessageKind` taxonomy (`bristlenose/ui_kinds.py`), length budgets, anti-patterns, flowchart for fitting new messages into the existing vocabulary instead of inventing new glyphs/colours
- `docs/design-platform-transcripts.md`, `docs/design-transcript-coverage.md`
- `docs/design-people.md` — **problem-first spec for person identity: jobs to be done, then UX, then data.** Read before touching names, speaker roles, or anything that renders a person. Owns the ranked sequence, the settled decision 1 (codes are globally-numbered slots, identity a layer above; renumbering falls out of renaming — supersedes §11c's (session,code)-rekey direction), the one still-open product call (decision 2: whose name survives an export), and §H's sequenced work packages
- `docs/design-speaker-splitting.md`, `docs/design-speaker-role-detection.md`
- `docs/design-speaker-editing.md`, `docs/design-transcript-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md`
- `docs/design-multi-project.md` — scope rules (instance vs project tables)
- `docs/design-session-management.md`
- `docs/design-logging.md`

**Export:**
- `docs/design-export-html.md` (anonymisation), `docs/design-export-locale.md` (one language per deliverable — shipped in 0.28.0), `docs/design-export-quotes.md` (CSV/XLS), `docs/design-export-clips.md`, `docs/design-export-slides.md`, `docs/design-miro-bridge.md`, `docs/design-footer-feedback-react.md`

**Desktop:**
- `docs/archive/design-desktop-app.md`, `docs/design-desktop-security-audit.md`
- `docs/design-modularity.md` — **canonical cross-channel component strategy** (CLI + macOS, Background Assets, no-fork principle, trickle-to-full-capability)
- `docs/design-desktop-python-runtime.md` — Mac sidecar mechanics
- `docs/private/road-to-app-store.md` — current Apple-side gate sequence (Sprint 2 plan archived; see 100days.md for live plan)
- `docs/design-project-sidebar.md`, `docs/design-wkwebview-messaging.md`
- `docs/design-desktop-menu-actions.md`, `docs/design-desktop-settings.md`

**Assistant surfaces (MCP + chat lens):**
- `docs/design-mcp-server.md` — the endpoint, its four tools, §6a's sheet-era as-built record (superseded, kept as history)
- `docs/design-mcp-extension.md` — **the shipped Mac path**: handshake file (§3.1), proxy contract (§3.2, §5b's three states), Settings ▸ MCP Agents (§3.7), the Turn On/Off Agent Access verb swap (§3.6a), the exposure badge (§5a-bis), packaging + build gates (§4), and §5c's spike + live-install measurements
- `docs/design-chat-lens.md` — the in-app cited question box (same grounding core)
- `docs/design-mcp-native-proxy.md` — **read before touching agent access on macOS 27 or the ChatGPT channel.** Measured 29 Sep 2026: ChatGPT installs a local plugin in one click (`codex://plugins/<name>?marketplacePath=<marketplace.json>`), runs its tools in Work mode only, and does **not** supply Node; macOS 27 decides a container read by the *responsible* process, and a team-signed proxy launched as its own responsible process needs no grant — but that route is private SPI and was rejected for the App Store. What is built (on `main`, unreleased) is a sandboxed helper carrying the team app group, in `desktop/mcp-helper/`, gated by `desktop/scripts/check-mcp-helper.sh` (§6.9–§6.11)
- `docs/design-mcp-files-and-folders.md` — the System Settings ▸ Files & Folders route for the Node proxy on macOS 27 (shipped copy, all 21 locales); now the fallback for a build without the native helper, and the recovery sentence

**Analysis / research methodology:**
- `docs/design-research-methodology.md` — read before changing prompts or analysis logic
- `docs/academic-sources.html` — theoretical foundations
- `docs/design-signals-future.md`, `docs/design-quote-sequences.md`, `docs/design-dashboard-stats.md`, `docs/design-signal-elaboration.md`

**i18n:** `docs/design-i18n.md` — terminology table, implementation gotchas

**Codebook:** `docs/design-codebook-norman.md` (**read before rewording any framework tag** — the decision register, the evidence policy for data that cannot be cited, and the harness; a decision there is reopened by a witness quote that fails, never by a hunch), and its siblings `design-codebook-garrett.md`, `design-codebook-morville.md`, `design-codebook-nielsen-register.md`, `design-codebook-yablonski.md` — every authored codebook has a register, a golden fixture under `tests/fixtures/codebook-golden/`, and `tests/test_codebook_registers.py` gates them: a settled decision without a witness fails, a fixture tag that does not exist fails, and **a `not_this` that points at a tag in another codebook which does not exist fails** (every 22 Sep 2026 audit found such pointers; `docs/codebook-audits/` holds the audits). A tag or group that changes name carries `renamed_from:` so `codebook_sync` migrates installed rows, `docs/design-codebook-v2.md` (the navigator that ships), `docs/design-codebook-state-model.md` (what the enable/disable switch means — the canonical spec), `docs/design-codebook-library.md`, `docs/design-codebook-focus.md`, `docs/design-moderator-question-pill.md`, `docs/design-dynamic-codebook-builder.md`. The v1 island's decision log is history: `docs/archive/design-codebook-island.md`

**HTML report / dashboard / auth:**
- `docs/design-html-report.md`, `docs/design-dashboard-navigation.md`
- `docs/design-sentiment-charts.md`, `docs/design-badge-action-pill.md`
- `docs/design-react-islands.md`, `docs/design-autocode.md`

**Ops / release:**
- `docs/release.md`, `docs/file-map.md`, `CONTRIBUTING.md`, `INSTALL.md`, `SECURITY.md`
- **`docs/testing/README.md` — the testing & acceptance hub (start here for anything test/QA/acceptance).** Three-tier model (CI · Playwright · acceptance matrix · human walk), `docs/testing/coverage-inventory.md` (the single source of surfaces: 27 formats · 5 exports · 5 lenses · 5 providers), `docs/testing/acceptance-matrix.md` (mechanical tier, Phase-1 plan), `docs/testing/test-data-generation.md` (fixture recipe). Built already: `tests/test_no_fake_success_acceptance.py` (skips without fixtures) + `e2e/`. The by-hand walk lives in the private QA doc.
- `docs/design-ci.md`, `docs/archive/design-test-strategy.md`, `docs/design-playwright-testing.md`, `docs/design-test-philosophy.md`
- `docs/design-doctor-and-snap.md`, `docs/design-homebrew-packaging.md`, `docs/design-fedora-packaging.md` (Copr — **live since 28 Aug 2026**, see the status section; §7 holds the standing obligations, and the measured `ffmpeg-free` codec verdict)
- `docs/design-cli-improvements.md`, `docs/design-llm-call-telemetry.md`, `docs/design-performance.md`
- **The release chain has a board.** `.venv/bin/python scripts/release-board.py` draws `.release/<v>/board.html` from the files the train writes; `--serve` runs it live on loopback behind a per-run token; `release.sh run --board` starts one detached if none is serving and prints the link, and without the flag prints it only if one exists (the release never needs the board — §8 of the design doc has the five layers) — the feed is `desktop/scripts/sink.sh` teeing the `@bn` protocol into `.release/<v>/bn-events.log` (`docs/design-release-board.md`). Two rules that cost a day: the board reads and never derives (no data is a third state, and the driver writes its own boundary lines so an empty sink is *ran, no record*, not *did not run*), and `printf %q` + `shlex` is not a round-trip — values are normalised before quoting and the parser counts what it cannot read.
- **The release chain is executable, and it is documented in three places, not one.** [`scripts/README.md`](scripts/README.md) is the index (what to type: `release.sh plan|run|verify`, the gates, the suites that prove the gates). [`desktop/scripts/REPORT-STYLE.md`](desktop/scripts/REPORT-STYLE.md) Part 2 is the *rules* a script follows — where constants live (`scripts/project.conf`), why probes are tri-state, what each exit code means (`75` = acts done, verification pending), the testability seams, and the shell traps this codebase has already paid for. `docs/design-release-machine.md` is the architecture and `docs/release-premortem.md` replays six months of release incidents against the current scripts. `docs/design-release-principles.md` is the *why* under all three — the saga/pivot shape, the tri-state-oracle and TOCTOU rules, gates-as-a-population, and what to measure — each line anchored to the incident that paid for it. **Four places, then.** Read the principles before adding a gate or a retry; they are what stops the next one being born dead.
- `docs/design-decisions.md` (why)
- `docs/ROADMAP.md`

## Working preferences

### Branch workflow (solo — trunk by default)

**This is a solo project; the default is trunk.** Work directly on `main`, in the main repo, in the env that's already built. Commit at every green checkpoint. **Do not spin a branch/worktree per feature** — the cost is the worktree's env build (`.[dev,serve]` venv + frontend build + ffmpeg/model symlinks + smoke test), paid on creation *and* teardown, routinely out of proportion to the work. GitHub's branch-per-feature + PR flow is built for teams across timezones; for one person it's pure ceremony. (5 → 50 → 500 devs need it; a team of one does not.)

**A branch is free; a worktree costs an env.** `git branch foo` is a 40-byte pointer — instant, no env. `git worktree add` is a second working copy that must be built and proven. Your safety net is git *history*, not worktree *isolation*:
- **Commit often** — every green checkpoint is a rollback point.
- **Checkpoint before risky surgery:** `git branch -f checkpoint` (free pointer); roll back with `git reset --hard checkpoint`.
- **Undo something already committed:** `git revert <sha>` — safe, never loses history. This is the "plausible rollback".
- **Rescue one file from a bad session:** `git restore -s <good-sha> -- <path>`.
- **Panic button:** `git reflog` → `git reset --hard HEAD@{n}`. Nothing is lost for 90 days.
- **Safe remote backup, no CI/release:** `git push origin main:wip`.

`main` is not "released" until *you* push + tag (evening rule), so a half-done change on local `main` is fine — just don't push it. Trunk is also *safer* for this repo: the two worst recorded incidents (edits landing on the wrong working copy; stale `__pycache__` after an in-place switch) were both *caused by* the multi-worktree pattern. Fewer working copies = fewer feet to shoot.

**Don't default to offering a new branch.** When a handoff/plan is written, the default next step is to do the work on `main`, NOT to hand back a `/new-branch` invocation. Only propose a worktree when the exception below genuinely applies, and say *why*. (Defaulting-to-branch is exactly how the retired "short-lived branches / one-branch-plus-nudges" rules accreted — don't regrow them. See memory `feedback_solo_trunk_default.md`.)

**The worktree is the rare exception — only when two envs must be live at once:** a long pipeline run going while you code something else, or a genuine second parallel Claude session that would clobber the working tree. Then — and only then — use **`/new-branch`** (never hand-roll a worktree; DIY ones produce broken envs: missing extras, unbuilt frontend, missing symlinks). Checkpoint *pointers* (`git branch -f`) are not worktrees and need no skill.

**Session-start check** (cheap, still worth it):

```bash
pwd
git branch --show-current
test -f .claude/setup-incomplete && cat .claude/setup-incomplete
.venv/bin/python -c 'import sys; print("venv", ".".join(map(str, sys.version_info[:2])))'; grep '^python ' .tool-versions
```

**The venv's minor must match `.tool-versions`.** If it doesn't, the env has drifted off the pin — rebuild before doing real work (`rm -rf .venv && python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev,serve]'`), don't work around it. Drift is silent: the suite still passes on a neighbouring minor, so nothing fails until a release build disagrees with the dev box. Found 4 Aug 2026 — a crash-recovery `uv venv` had quietly rebuilt `.venv` on 3.11 **and** dropped `presidio-analyzer`/`presidio-anonymizer` (core deps, stage 7 PII removal) from the install, with a green suite throughout because those tests mock or skip. **Don't reach for `uv` or `mise` to fix it** — that migration is Phases 1–4 of `docs/design-dev-environment.md` and is explicitly gated post-TestFlight; the house mechanism is `python3.12 -m venv` + `pip install -e`. A stray untracked `uv.lock` is the tell.

If you're in a worktree (rare) and `.claude/setup-incomplete` exists, its env isn't prepped — don't start real work until `/new-branch` finishes or setup is done manually (frontend build, venv, smoke test). A `PreToolUse` hook in `.claude/settings.json` blocks `git checkout`/`git switch` to feature branches from the main repo — harmless under trunk (you stay on `main`) and it still guards against accidental in-place checkouts.

**Session-handoff sentinels:** `.claude/setup-incomplete` (negative — `/new-branch` setup didn't finish) and `.claude/last-end-session.json` (positive — `/end-session` signed off; carries `head_sha` for drift detection). Both gitignored.

**Branch handoff plan:** if `HANDOFF.md` exists at a worktree root (gitignored symlink to `.claude/plans/<branch>.md`), it's the **starting brief** — read it first, don't synthesise from sandpit logs. Canonical home is `docs/private/handoffs/<branch>.md` (gitignored, backed up by `backup.sh`). **Handoffs are NOT specs** — before drafting a plan, run `git log -3 -p <files-the-handoff-names>` and grep commit bodies for decision-shapes ("not Y", "deferred to", "rejected", "chose X over Y", "post-TF", "status-only"). If a recent commit chose against an affordance the handoff proposes, raise it as a question BEFORE planning. Recent commits win unless the user overrides. (Memory `feedback_handoff_not_a_spec.md`.)

**Skills for the worktree exception (not the default path):**
- **`/new-branch <name>`** — creates branch + worktree + venv + symlinks + `docs/BRANCHES.md` entry. Use only for genuine parallel-env work; never hand-roll a worktree (DIY ones ship broken envs). If `disable-model-invocation` blocks auto-invocation, read `.claude/skills/new-branch/SKILL.md` and follow every step manually.
- **`/new-feature <name>`** / **`/close-feature`** — the trunk default: start / finish work on `main`, no worktree. See `.claude/skills/WORKFLOW.md`.
- **`/close-branch <name>`** — archives a merged worktree branch; reads `.claude/last-end-session.json` and prompts before archiving an un-end-sessioned or drifted branch.
- **Reverting a merge:** `git revert -m 1 <merge-commit-hash>`.

See `docs/BRANCHES.md` for any active worktrees and the parked set.

### General

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- **Self-check at end of task**: fewer unnecessary changes in the diff than last time? clarifying questions asked *before* implementing rather than after a wrong turn? no rewrite mid-task because the first pass was overcomplicated? If any of those is "no," that's the lesson for next time
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")
- **Human QA after each task**: when you finish a task, suggest only the checks a human needs to do that automated tests can't cover (visual regression, browser interaction, UX feel). Skip this for pure data/logic work where unit tests are sufficient. Include copy-pasteable commands to make it easy (e.g. server start command, URL to open). Don't duplicate what pytest already covers
- **NEVER use Claude Code preview tools (`preview_start`, `preview_screenshot`, `preview_snapshot`, `preview_eval`, etc.) for QA.** They consistently fail for Bristlenose — wrong port, missing Vite HMR, white-on-white rendering, incomplete React mount. Every attempt wastes time. Bristlenose needs the full stack (Vite dev server on 5173 + FastAPI serve on 8150) running together. For QA, tell the user to run the full stack in their own browser:
  ```
  .venv/bin/bristlenose serve --dev trial-runs/project-ikea
  ```
  `--dev` auto-starts Vite on :5173 as a subprocess (cleaned up on exit). Then open http://localhost:8150/report/. For worktrees: use the port from `.claude/launch.json`

### Release timing (evening releases)

Releases land after 9pm London on a **working day**; **the act that lands a
release is the tag push.** Weekends and **UK bank holidays: any time** — the
rule exists to keep release notifications out of client working hours, and on a
day when clients are not working there is nothing to keep them out of. The `pypi` environment's required-reviewer hold was **removed on
23 Aug 2026** — it had been the reason the tag could go out early, because a
tagged run then waited for a human before publishing.

**Why it went.** At the approval moment every fact is mechanical: both CI runs,
the artefact's signature and staple, `tag == HEAD`, the version not already on
PyPI. A human clicking Approve at 11pm re-verifies none of them. The click was
a second asking of a question already answered by typing "release" — and at
**97 releases in 204 days** that ceremony was expensive and the judgement empty.

**Removing the hold did not remove the gate.** `publish` needs `build` needs
`ci`, and `release.yml` invokes `ci.yml` with `strict-macos: true`. PyPI cannot
receive a version whose full matrix, e2e and strict macOS suite did not pass on
the tagged commit. `check-release-ready.sh`'s `publish gate` row asserts that
chain and **fails** if it is ever broken — the click became assertions that
actually inspect the artefact.

Consequences:

1. Push `main` **any time** — it never publishes and it buys CI signal.
2. **The tag goes LAST**, after the Mac uploads and after a strict CI verdict on
   `main`. `ci.yml` exposes `strict-macos` on `workflow_dispatch`, so the strict
   verdict is obtainable without a tag — which is what preserves the 0.25.2
   lesson (every verdict before every irreversible act) now that the tag is the
   publishing act. `./scripts/release.sh run` encodes this order.
3. **The tag push is what waits for 9pm — on working days only.** Weekends and
   UK bank holidays: any time. Still two back-to-back commands, never one
   `--tags` — the bundled push is how the tag-driven workflow gets debounced
   into never firing.

   **Check the holiday, don't derive it.** The UK government publishes the
   official list, so this is one command and never a calculation:

   ```bash
   curl -s https://www.gov.uk/bank-holidays.json | jq -r --arg d "$(date +%F)" '."england-and-wales".events[] | select(.date==$d) | .title'
   ```

   Non-empty output is the answer — today is that holiday, so the window is
   open now. Added 31 Aug 2026, when a release was scheduled to wait until 9pm
   on the **Summer bank holiday**: "is it a weekday" was answered by `date +%u`,
   which returns 1 for a Monday whether or not anyone is working. Reasoning it
   out from "last Monday in August" is the same mistake one step later — the
   division is *working day*, and England-and-Wales, Scotland and Northern
   Ireland do not share a calendar, which is exactly why the feed is keyed by
   nation.

**Override:** push when something is urgent. This is a guideline, not a gate.

**A running release freezes `main`, locally.** While a `release.sh run` driver is
alive, the `release-freeze` pre-commit hook refuses commits in this checkout and
its worktrees (not pushes of earlier commits, `--no-verify`, or other machines,
and not the gap after a failed step, when a fix is supposed to land):
a commit then would move HEAD under the release, forcing a rebuild and a fresh
strict-CI run, and could change what ships (0.34.0 was planned as 0.33.1 and
became a minor that way). The release's own commits pass; a fix the release
needs goes in with `BN_RELEASE_FREEZE_OK=1 git commit …`. **Work that must not
go live before the new version is on PyPI** (an install guide naming it, a
one-liner that installs it) waits on a branch named `after-pypi/<version>`.
The same holds for any channel: `after-<channel>/<version>[-anything]`
(`after-winget/0.36.0` holds the docs that make winget the lead Windows route),
in this repo or the website's. `release.sh verify` lists every hold in both
repos with `land`, `wait` or `?` per channel. It lands a hold when that channel
carries the version or a later one, without waiting for every channel to
verify, and reports a misnamed `after-*` branch rather than skipping it.

**Why:** avoids release notifications during client working hours; batches
releases into a predictable window. Both halves of that purpose are about *when
other people are at work*, which is the test to apply when a new edge case turns
up — not the shape of the calendar.

### Post-push PyPI verification (mandatory)

A tag push that reaches GitHub is NOT the same as a release that reaches PyPI. The release pipeline silently stalled from v0.15.5 to v0.15.9 (five versions, ~6 days) because no step checked that PyPI actually accepted the upload. **After pushing the tag, verify before declaring the release done:**

```sh
for i in $(seq 1 20); do
  sleep 90
  pypi=$(curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version)
  echo "[$i] PyPI: $pypi"
  [ "$pypi" = "<X.Y.Z>" ] && break
done
```

20 iterations × 90s = 30 minutes. Recent releases have run 23–25 minutes (v0.15.13: 25m41s, v0.15.14: 23m22s); the original 15-minute budget routinely expired during a normal release. **v0.23.0 took ~2 hours across three attempts** — budget generously on a release that touches the test suite. If PyPI still reports the previous version after 30 minutes: `gh run view --workflow=release.yml` to check the workflow fired. Apply the v0.15.0 debouncing workaround (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`) if it didn't.

**`/pypi/<pkg>/json` is CDN-cached and CAN read stale — don't trust a single negative.** During the v0.23.0 verification the poll returned `0.23.0`, and a re-check seconds later returned `0.22.0` from a different edge node. A stale read looks exactly like "the release never published" and would send you into unnecessary tag surgery on an already-successful run. **Confirm with the version-specific endpoint**, which is authoritative and unambiguous:

```sh
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/bristlenose/<X.Y.Z>/json   # 200 = published
```

A cache-busted index (`?cb=$RANDOM` + `Cache-Control: no-cache`) is the second check; `releases["<X.Y.Z>"]` should hold 2 files (sdist + wheel). Check `gh run view <id> --json conclusion` too — a `success` conclusion plus a 200 on the version URL means published, whatever the cached index says.

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

When the user says "let's switch to branch X" or similar, **automatically run this checklist before switching**:

### Pre-switch checks (on current branch)

1. **Check for uncommitted changes** — `git status`
   - If changes exist, commit them with a descriptive message (ask user for message if unclear)
   - Never leave uncommitted work when switching branches
2. **Run tests** — `.venv/bin/python -m pytest tests/`
   - If tests fail, warn the user before proceeding
3. **Run linter** — `.venv/bin/ruff check .`
   - If lint errors, fix them or warn before proceeding

### Switch

4. **Execute the switch** — `git checkout <branch-name>`
   - If branch doesn't exist locally but exists on remote: `git checkout -b <branch-name> origin/<branch-name>`
   - If branch doesn't exist anywhere, ask user if they want to create it

### Post-switch cleanup

5. **Clear Python cache** — `find . -name __pycache__ -exec rm -rf {} +`
   - Editable installs cache imports; stale `.pyc` files cause mysterious bugs
6. **Reinstall package** — `.venv/bin/pip install -e .`
   - Shebang paths and import paths may reference old locations
7. **Report status** — `git status` + `git log --oneline -3`
   - Show user what branch they're on and recent commits

### Why this matters

Python editable installs (`pip install -e .`) write absolute paths into `.pth` files. Switching branches can leave stale bytecode that serves old code, causing:
- `ImportError` for modules that don't exist on the new branch
- Functions behaving like the old branch's version
- Mysterious test failures

The PreferencesFile incident (keyboard-navigation branch, Feb 2026) was caused by exactly this — stale imports from a feature that was stashed on another branch.

## Session-end housekeeping

When the user signals end of session, **run `/end-session`** — the skill handles verify, document, commit, and close-out. See `.claude/skills/end-session/SKILL.md` for the full checklist.

## Current status

**Internal TestFlight since 14 Jul 2026** — shipping build **0.42.0 (5269)** — first build accepted by App Store Connect: **0.20.0 (2068)**, App-Sandbox + Hardened-Runtime + arm64-only, signed Apple Distribution.

**Latest release: 0.42.0, 20 Oct 2026** — tag `v0.42.0` on `7cefa0b3`, verified 9 of 9. Each release's account (what shipped, every stop, run times) is in [`docs/release-log.md`](docs/release-log.md), versions in [CHANGELOG.md](CHANGELOG.md), active work in [TODO.md](TODO.md). The paragraphs this section carried release by release, 0.29.0–0.38.0, are kept verbatim in [`docs/status-history.md`](docs/status-history.md). **A release updates the shipping-build and latest-release lines above and writes its account in the release log; it does not add a paragraph here.**

**Standing facts a release needs:**
- **Entitlements split, gated by `tests/test_entitlements_split.py`:** the Mac App Store build carries one app group, `group.app.bristlenose`; the Developer-ID `.dmg` must not (a `CODE_SIGN_ENTITLEMENTS` override in `build-dmg.sh`). `associated-domains` (`webcredentials:bristlenose.app`, Zoom's HTTPS sign-in callback) is on all three files (the `.dmg` too since 18 Oct 2026, so Zoom import works there; its Developer ID profile is minted at export with the capability); the App-ID capability is on and the `Bristlenose Mac App Store` profile was regenerated with it on 17 Oct 2026 (a release archive needs that profile, not the 12 Sep one). Neither entitlements file is `skip-worktree` (`git ls-files -v | grep "^S"`).
- **Fedora Copr is live** (since 28 Aug 2026, fedora-43-x86_64): CVE tracking of the vendored wheelhouse is ours, `.copr/Makefile` pins Fedora's Python, and the Copr token expires **23 Feb 2027** (renew). The SRPM job runs on any architecture, so `rpm/make-srpm.sh` pins x86_64 wheels; confirm a publish from `repodata/`, not the results listing (`docs/design-fedora-packaging.md` §7).
- **`v0.26.0` was tagged and abandoned**; treat it as a version that never existed.

React migration complete; bundled-sidecar desktop is the primary distribution path; the CLI ships on PyPI, Homebrew, Snap and Fedora Copr; the static render is a sealed byproduct.
