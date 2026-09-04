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
- **CLI plurals**: any count-bearing CLI string uses `count_noun(n, "singular")` from `bristlenose/utils/text.py` — wraps `inflect.engine().plural_noun()`, so irregulars (`child`→`children`, `person`→`people`, `boundary`→`boundaries`) and compound nouns (`"topic boundary"`→`"topic boundaries"`) work automatically. Don't hand-roll `f"{n} thing{'s' if n != 1 else ''}"` or add a sibling helper next to `count_noun`. Pass `plural=` explicitly only when inflect's default disagrees (rare). CLI is English-only in alpha; the React SPA + desktop use i18next CLDR plurals via `t(key, count=n)` — different surface, different mechanism, don't conflate. The Python-side `t()` under `bristlenose/locales/preflight.json` doesn't support CLDR plurals yet; when/if CLI gets localised post-alpha, `count_noun` grows a CLDR-aware path
- **Changelog version/date format**: `**X.Y.Z** — _D Mon YYYY_` (e.g. `**0.8.1** — _7 Feb 2026_`). Bold version, em dash, italic date. No hyphens in dates, no leading zero on day. Used in both `CHANGELOG.md` and the changelog section of `README.md`
- **The React SPA is the product; the Jinja2 static renderer (`bristlenose/stages/s12_render/`) is a deprecated sealed byproduct.** Rules: (1) New features and design changes go to the React SPA only. (2) Offline sharing = open in serve mode → **Export HTML** toolbar button (embeds the React bundle + JSON; never calls `s12_render/`). (3) **Serve mode never falls back to static render** — if the SPA is missing from the bundle, `_mount_prod_report` returns a fail-loud 500, not the static HTML (that fallback masked BUG-3). (4) CSS in `bristlenose/theme/` is shared with the static render incidentally; design intent lives in `frontend/`. (5) Vanilla JS in `bristlenose/theme/js/` is frozen — data-integrity fixes only. Future direction (repurpose `--static` as a markdown deliverable): `docs/design-cli-improvements.md` §Future direction.

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls), `serve` (local dev server), `status` (read-only project state from manifest), `doctor` (dependency health checks), `configure` (store a provider key + make it current), `use` (switch the current provider). **There is no vendor-default provider**: the CLI resolves `--llm` → env → current provider (written by `configure`/`use`) → sole configured key → diagnose — see `docs/design-cli-provider-selection.md`; the `"anthropic"` field default in `config.py` is only the desktop-contract backstop. **Default command**: `bristlenose <folder>` is shorthand for `bristlenose run <folder>` — if the first argument is an existing directory (not a known command), `run` is injected automatically.

Serve mode: FastAPI + SQLite + React SPA. See `bristlenose/server/CLAUDE.md` for architecture.

Assistant surfaces (both ground in `bristlenose/server/grounding.py` — one shared core, never a parallel sibling): the **in-app chat lens** (a cited question box; `docs/design-chat-lens.md`) and the **MCP endpoint** at `/mcp/` for external agents — read-only, four tools, scoped bearer. Ships on **both** channels: the CLI via the optional `bristlenose[mcp]` extra, and the macOS app in the bundled sidecar (`docs/design-mcp-server.md`, spike accepted 30 Jul 2026). On the Mac the transport is a **`.mcpb` extension** rather than a pasted config — `desktop/mcpb/` holds a zero-dependency Node proxy that reads a runtime handshake file the host writes, so there is no address or token to copy and nothing to redo when the port rotates; exposure is per project (**Turn On Agent Access**, sidebar antenna) and setup is **Settings ▸ MCP Agents** (`docs/design-mcp-extension.md`, shipped 1 Aug 2026). The product frame is **two offerings**: (1) the report as one link with two modes — read it / ask it; (2) stay in your own local agent. `INVARIANTS` in `grounding.py` is the single model-facing statement set for both. **Bristlenose knows the protocol, never the client** — we can offer, we cannot observe; any design that needs to read another app's state is the wrong design.

Desktop app: `desktop/` — SwiftUI macOS shell. Alpha ships a bundled, signed PyInstaller sidecar running `bristlenose serve`, distributed via internal TestFlight. v0.2 currently uses launcher-style scaffolding (dev-only, not shippable). See `docs/archive/design-desktop-app.md` for the overall app design, `docs/design-modularity.md` for cross-channel component decisions (CLI ≡ macOS Python code; packaging differences only), and `docs/private/road-to-app-store.md` for the 14-checkpoint path to TestFlight.

Frontend: `frontend/` — Vite + React + TypeScript + React Router. See `frontend/CLAUDE.md` for gotchas and architecture.

Export: self-contained HTML "leave-behind" (React SPA + inlined API data, opened offline from `file://`). Rendered by a **dedicated single-file Vite build** (`frontend/vite.export.config.ts`, `codeSplitting:false`) — a blob/data-URL module bootstrap does NOT work from an opaque `file://` origin. **Anti-drift is mechanical:** `tests/test_serve_export_coverage.py` reads `app.openapi()` and fails if any project GET read isn't classified `EMBED_PATH_TEMPLATES` or `SERVER_ONLY_PATH_TEMPLATES` in `routes/export.py` — so adding a route is offline-by-default and a new gap fails the build, not the user's download. Read-only via `isExportMode()` store-layer gate (controls hidden, not disabled). Embedded JSON is XSS-escaped (`ensure_ascii=True` alone is NOT enough — see the export-JSON gotcha below). v1 no video; the timecode/media apparatus stays in the embed for v2. Full spec: `docs/design-export-html.md`. See Key conventions for the static-render deprecation rules.

LLM providers: Claude, ChatGPT, Azure OpenAI, Gemini, Local (Ollama). See `bristlenose/llm/CLAUDE.md`.

Quote exclusivity: **every quote appears in exactly one report section.** See `bristlenose/stages/CLAUDE.md`.

Analysis page: `bristlenose/analysis/` — signal concentration metrics, pure math. Uses plain dataclasses (not Pydantic). Cell keys use `"label|sentiment"` format. See `docs/design-analysis-future.md`.

LLM prompts: Markdown files in `bristlenose/llm/prompts/`. Archive old versions to `bristlenose/llm/prompts-archive/`. See `bristlenose/llm/CLAUDE.md`.

Report JavaScript: the frozen vanilla modules in `bristlenose/theme/js/`. See `bristlenose/theme/js/MODULES.md` — and take the count from `_JS_FILES` in `stages/s12_render/theme_assets.py`, never from prose. This line said 17, MODULES.md said 20, `hello-world-architecture.md` said 23, and the list held 26 (19 Aug 2026). A number that lives in four documents is a number that is wrong in three of them.

Video thumbnails: `bristlenose/utils/video.py` — auto-extracted keyframes per session. See `docs/design-html-report.md`.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. Override with `--output`. See `bristlenose/stages/CLAUDE.md` for the full directory layout.

Key helpers: `OutputPaths` in `output_paths.py` (consistent path construction), `slugify()` in `utils/text.py` (project names in filenames — lowercase, hyphens, max 50 chars). Report filenames include project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`, `frontend/`, `desktop/`
- **Design artifacts** (tracked, not shipped): `docs/mockups/`, `docs/design-system/`, `experiments/` — HTML mockups, style guides, throwaway prototypes. These are working materials for contributors, kept in the tree for backup and collaboration. Users never navigate to them. Add new mockups to `docs/mockups/`, not the repo root. **Serve mode auto-discovery**: `bristlenose serve --dev` mounts all three directories and auto-discovers `*.html` files for the Design section in the About tab (`_build_dev_section_html()` in `app.py`). New HTML files added to these directories appear automatically — no code changes needed. **`experiments/` is excluded from `ruff check`** (per `pyproject.toml`) — throwaway research scripts don't need to pass lint; don't waste cycles fixing F401 unused-imports in there
- **User-facing docs live in the website repo, not here.** The single-page `docs/manual.md` was retired at the website v2 cutover (archived to `docs/archive/manual.md`; `bristlenose.app/manual.html` now 404s by design). User docs are per-topic Markdown in the website repo's `docs-src/` tree, published under `bristlenose.app/docs/`. **When a CLI change lands, the user-facing surfaces to true are: `README.md`, `man/bristlenose.1`, and the website's `docs-src/cli.md`** — three places, no fourth. Don't edit `docs/archive/manual.md` to keep it current.
- **Marketing site** (deployed, separate private repo): the marketing site, server-side ops endpoints, deploy script, and ancillary publishing/PR assets live in a separate private deploy repo on the maintainer's machine. Its `build.py` renders `docs-src/*.md` plus a few pages sourced live from this repo (e.g. the changelog, read straight from `CHANGELOG.md` so there's no second copy to drift). **Note:** the rsync deploy needs SSH agent access and is run manually by the maintainer. **`build.py` renders only `docs/` — it does NOT copy `assets/`; `deploy.sh` does that at ship time.** So previewing a local `site.css`/`site.js` edit serves the *stale* copy already in `build/site/assets/`, with no error — the page renders, the change just isn't there (cost a debug cycle 3 Aug 2026 chasing an empty icon span that was actually a stale `ICONS` map). `rsync -a assets/ build/site/assets/` after `./build.py` before previewing. Illustration/screenshot conventions for the docs live in `docs/design-docs-system.md` Part D
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`
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

### Ruff F401 (unused imports) — reports only, won't auto-fix

F401 is marked `unfixable` in `pyproject.toml` so `ruff check --fix` (and the PostToolUse hook) won't delete imports during incremental edits. Ruff still *reports* unused imports — remove them manually when they're genuinely unused.

### A blocked PreToolUse hook kills the WHOLE Bash call, not the offending fragment

The `leak-scan.sh` / `block-checkout.sh` PreToolUse hooks match against the
**entire command string**, and a match blocks the whole invocation — so every
other command batched into that call silently never runs. Bit twice on 8 Aug
2026. First: a call doing `sed -i '' … && grep -cE '<blocked-pattern>' … && git
add …` was refused because the *grep pattern* named a blocked path. The grep was
a leak-**check**, not a leak. The `sed` never ran, and the next command reported
the file unchanged — which reads as "my edit didn't apply" rather than "the whole
call was refused". Second, and more instructive: the attempt to write *this very
gotcha* was refused, because the explanatory text quoted the blocked string as an
example.

Three rules. **(1)** Never put a blocked pattern in a command string, even as a
search term — grep via a shell variable, or use `git check-ignore` instead.
**(2)** The hook fires on Edit/Write to public docs too, so *documentation about*
a blocked pattern must paraphrase it (this file's own convention: say "the
maintainer's private planning notes, kept outside the public tree"). **(3)** After
a refusal, assume **nothing** in that call ran; re-verify state before
re-issuing, rather than assuming the parts before the offending fragment
succeeded.

### Only Mach-O EXECUTABLES carry entitlements — bundles and dylibs never do

The `.app` holds ~227 Mach-Os but only **4 are executables** (the host, ffmpeg,
ffprobe, the sidecar). The rest are Python `.so` extension **bundles** and
**dylibs**, which carry no entitlements at all — they inherit from the loading
process. So `find -perm -111` plus "assert app-sandbox" reports **223 of 227
missing it** against a correctly-signed, ASC-accepted package. Filter on
`file -b "$b" | grep -qE 'Mach-O.*executable'`, never bare `Mach-O`.

Those 4 are exactly the set the 14 Jul 2026 nested-signing rejections were about,
so the gate is worth having — but a gate that cries wolf gets switched off, which
is worse than no gate. `desktop/scripts/check-pkg-shippable.sh` has the working
form with the reasoning inline.

**Release-channel mechanics** (five channels, their triggers, and the two
different expiry clocks — `.dmg` 30 days from the *build*, TestFlight 90 from the
*upload*) are mapped in `docs/release-channels.md`. The measured `altool`
contract — including that `--list-providers` refuses API-key auth while
`--list-apps` accepts it, and that `--show-progress` must be TTY-gated or it
bloats a log 12,000× — is in `docs/design-testflight-upload.md` § Observed
contract. Don't re-derive either.

### "Is this Swift file in the Xcode project?" is not a question `project.pbxproj` can answer

`Bristlenose.xcodeproj` uses **`PBXFileSystemSynchronizedRootGroup`** (Xcode 16+),
which references the *folder*, not the files. Membership is by living on disk
under `Bristlenose/` or `BristlenoseTests/` — so no individual `.swift` filename
appears in `project.pbxproj` at all, and the obvious audit

```
grep -q "$(basename "$f")" project.pbxproj || echo "MISSING FROM PROJECT: $f"
```

reports **every** Swift file as missing. On 21 Aug 2026 that was 250 files,
printed as a wall of `MISSING FROM PROJECT:` against a project that builds
clean — alarming, entirely false, and it cost a cycle to disbelieve.

The check the grep was reaching for is real but different: a file can be
*written and never committed*, which is how `main` stopped building on 18 Aug
(`c837f8b5` — `CloudPlatform.swift:52` read a flag whose file was untracked).
**Ask git, not the pbxproj:** `git status --porcelain -- 'desktop/**/*.swift'`.
An untracked `.swift` is the actual failure mode; an unlisted one is the norm.

Tell that you are in this trap: the "missing" list is *all* of them, or the
count matches `ls desktop/Bristlenose/Bristlenose/*.swift | wc -l`. Confirm with
`grep -c PBXFileSystemSynchronizedRootGroup project.pbxproj` — non-zero means
filenames were never going to be in there.

**Nor can it answer "what is the deployment target?" — and that one fails
*plausibly*.** The file holds several `XCBuildConfiguration` blocks; which one a
scheme resolves to is decided by the build system, not by reading order, and the
project deliberately carries **two** floors — production at `MACOSX_DEPLOYMENT_TARGET
= 15.0` on all four app schemes, and `BristlenoseTests` at 26.1
(`docs/design-platform-policy.md` §"Pillar 3"; pinned by
`desktop/scripts/check-deployment-floors.sh`).
Hand-parsing therefore returns a real number that is nonetheless the wrong one for
the scheme you meant, with nothing to signal the error.

On 3 Sep 2026 three successive parses of that file gave three different answers —
first 15.0, then "26.1 everywhere", then a contradiction — and **two of them reached
a committed doc** before `xcodebuild` settled it. The same pass also reported
`SWIFT_APPROACHABLE_CONCURRENCY = YES` when the resolved value is `NO`.

**Ask the build system, and name the scheme:**

```
xcodebuild -showBuildSettings -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -target Bristlenose -configuration Release | grep -E 'SWIFT_|DEPLOYMENT'
```

Tell that you are in this trap: two different values for the same setting, and a
story forming about which is "stale". Both are probably live. Policy already
flags the underlying hazard as unfixed — Pillar 3 carries an open action to add a
comment block to the pbxproj naming which scheme uses which target, precisely
because it is "easy to bump one without the other".

**Nor can the `.entitlements` file answer "is this build sandboxed?" — and it
answers *no* when the truth is yes.** `BristlenoseDebug.entitlements` contains
exactly one key, `keychain-access-groups`. There is no `com.apple.security.app-sandbox`
in it, and `grep -l app-sandbox desktop/**/*.entitlements` matches nothing — so
reading the file, or grepping for the entitlement, concludes the Debug build runs
unsandboxed. It does not: the sandbox comes from **`ENABLE_APP_SANDBOX = YES` as a
build setting**, which Xcode 15+ merges into the synthesised entitlements at sign
time. The file is a *supplement*, not the manifest.

Cost two silent write failures on 3 Sep 2026 while measuring Settings pane
heights: a test writing to `~/Documents` and then to `/private/tmp/...` produced
no file and no error either time (`try?` swallowing a sandbox denial that the
tree said could not happen), and the payload only landed once it was pointed at
`NSTemporaryDirectory()` — i.e. `~/Library/Containers/app.bristlenose/Data/tmp/`.
**Same fix as the paragraph above:** ask the build system, name the scheme.

```
xcodebuild -showBuildSettings -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -target Bristlenose -configuration Debug | grep -E 'ENABLE_APP_SANDBOX|ENABLE_HARDENED'
```

Tell that you are in this trap: a file write that neither succeeds nor raises, on
a path the entitlements file says nothing forbids.

### macOS BSD userland — use GNU coreutils

macOS ships BSD versions of `sed`, `grep`, `awk`, `find`, `xargs`, `date`, `stat`, `readlink`, `tar`, and others. These differ from the GNU versions in subtle, bug-inducing ways:

- **`sed`**: no `\b` word boundary, `-i` requires backup extension arg (`sed -i '' ...`), no `\x00` hex escapes. **Use `gsed`** (installed via `brew install gnu-sed`)
- **`grep`**: BSD `-P` (PCRE) doesn't exist. Use `ggrep` or `rg` (ripgrep) for PCRE patterns
- **`date`**: BSD uses `-j -f` for parsing, GNU uses `-d`. Completely incompatible date arithmetic
- **`readlink`**: BSD has no `-f` (canonicalize). Use `greadlink -f` or `realpath`
- **`xargs`**: BSD `-r` (no-run-if-empty) doesn't exist — GNU behaviour is the default on BSD but the flag is missing
- **`stat`**: completely different flag syntax (`-f` vs `-c` for format strings)
- **`tar`**: BSD tar is `bsdtar` (libarchive), differs from GNU tar in flag handling, especially for `--transform`
- **`find`**: BSD `-regex` uses basic regex by default (GNU uses Emacs regex); `-regextype` doesn't exist
- **`awk`**: BSD awk is ancient POSIX awk — no `gensub`, no `length(array)`, no `FPAT`

**Rule: when writing shell commands that use regex or platform-specific flags, prefer `gsed`/`ggrep`/`gawk`/`greadlink` (all from `brew install coreutils gnu-sed gawk findutils grep`), or use Python/Perl for portability.** The `g`-prefixed GNU tools are always available on this machine.

### zsh does NOT word-split unquoted variables — `for f in $LIST` silently iterates once

The Bash tool runs under zsh, and zsh (unlike bash/sh) does **not** perform word-splitting on unquoted parameter expansions. So the everyday bash idiom `LIST="a.md b.md"; for f in $LIST; do …; done` treats the whole string as **one** word — `[ -f "$f" ]` then fails for the nonexistent filename `"a.md b.md"`, the loop body never runs, and **nothing errors**. The silent-no-op is the trap: a bulk `gsed -i` sweep over a file list "succeeds" (exit 0, no output) while changing zero files, and you only notice when the verification step reports the same findings you thought you'd just fixed (cost a debug cycle during the 15 Jul docs-truing sweep). Fixes: iterate an explicit literal list (`for f in a.md b.md; do`), use a real array (`files=(a.md b.md); for f in "${files[@]}"`), force splitting with zsh's `${=LIST}`, or `printf '%s\n' … | while read -r f`. Same family as the unmatched-glob gotcha below — zsh's defaults differ from bash in ways that fail *quietly*, so **verify a bulk edit actually changed files** (`git status` / re-grep) rather than trusting a clean exit.

### zsh unmatched-glob does NOT abort a multi-command Bash call

The Bash tool runs under zsh. When a glob matches nothing, zsh prints `zsh: no matches found: <pattern>` and — unlike `set -e` or bash's default — **skips that one command but continues to the next line in the same call.** So a "clean up, then run the payload" script whose cleanup glob matched nothing (`rm -f dir/*.json` with no files there) still runs the payload. The trap: you see the `no matches found` error, assume the whole script aborted, and **relaunch — double-running the payload.** This cost a real double-spend of LLM credits on the quote-stability experiment (3 Jul 2026: a background extraction ran twice because a guard `rm -f scratch/run_*.json` "failed" but Python ran anyway, then I relaunched). Fixes: use `find dir -name '*.json' -delete` (no-match-safe, no nomatch error), or guard with `setopt +o nomatch` / `2>/dev/null || true` **on its own line**, or just don't put a bare-glob cleanup ahead of a payload in the same call. When a Bash call errors early, verify what actually ran (check for output files) before relaunching.

**Same family, one line up the stack: an unquoted glob in a *flag argument* kills the whole call.** `grep -rn "x" dir --include=*.swift` fails with `zsh: no matches found: --include=*.swift` — zsh tries to expand `*.swift` against the *current directory* before grep ever sees it, so the flag only survives when a matching file happens to sit in `cwd`. It works from the repo root and fails from anywhere else, which reads as "grep is broken here". Bash passes the same string through untouched, so the idiom is muscle memory from everywhere else. **Quote it: `--include='*.swift'`.** Applies equally to `--exclude=`, `rsync --filter=`, `find -name`, and any tool taking a pattern as a flag value.

### `rg -rn` is NOT "recursive + line numbers" — `-r` is `--replace` and silently rewrites every match

Muscle memory from `grep -rn` is wrong for ripgrep: **rg is recursive by default**, and `-r/--replace` **takes an argument**. So `rg -rn "pattern" path/` parses as `-r n` — replace every match with the literal string `n` — and prints doctored lines with no error, no warning, and exit 0.

The trap is that the output still looks like source code. Searching for `mlx|cuda|ram` with `rg -rn` returned `import n_whisper`, `"n-community/whisper-large-v3"`, `ctranslate2.get_n_device_count()`, and `Memory: {self.n:.0f}GB` — every occurrence of the *search terms* replaced by `n`, in lines that otherwise parse as plausible Python. Bit twice in one session (2 Aug 2026); the second time the mangled hit was a real design doc (`design-gemma4-local-models.md` rendering as "n 4 model family"), which reads as a genuinely odd filename rather than a tooling artefact.

**Fix:** drop the `-r`. `rg -n "pattern" path/` is what you meant — recursion is implicit. If you genuinely want replacement it's `rg -r '<replacement>' "pattern"`, argument mandatory. **Tell:** identifiers that should be distinctive collapsing to a single repeated letter, or a match count that looks right while the matched *text* is missing the term you searched for.

Same family as the two zsh gotchas above — shell tooling whose defaults differ from the obvious analogue and fail *quietly*. When a search result looks strange, re-run the search before believing it.

### `set -e` does NOT fire on a failing left operand of `&&` — so `cmd && ok "passed"` is a gate that cannot fail

POSIX shells deliberately exempt any command whose status is *being tested* from `errexit`, and the left operand of `&&` is one. So this, which reads exactly like an assertion:

```bash
stapler validate "$DMG" && ok "stapler validate: passed"
```

…prints nothing on failure, raises nothing, and **falls straight through to the next line**. Verify it yourself: `bash -c 'set -euo pipefail; false && echo B; echo REACHED'` prints `REACHED` and exits `0`.

Two of `build-dmg.sh` stage 10's four final gates were written this way and were decorative through two releases (fixed 4 Aug 2026, `fc1d6ca7`). The near-miss it enabled: a complete, correctly-sized, correctly-hashed `.dmg` that `spctl` called `rejected — Unnotarized Developer ID` sat looking finished for 14 hours because the gate meant to catch that printed nothing.

**Rule: an assertion uses `|| die`, never `&& ok`.** If you want the success line too, `cmd || die "…"; ok "…"`. Applies equally to `cmd && a || b` chains — the `||` arm swallows a genuine failure of `a` as well. Audit any `check-*.sh` or build script for `&& ok`, `&& echo`, `&& printf` where the left side is a real check.

**And it is not only a script problem — it bites hardest in a throwaway verification
command.** `git status --porcelain && echo "(clean)"` prints `(clean)` on a **dirty** tree,
because `git status` succeeds at reporting the dirt. Same for `pytest -q && echo PASSED`,
`grep -c pattern f && echo FOUND`, and every `cmd && echo "✓ …"` typed to confirm a step
during a session. These are worse than the scripted kind: nobody reviews them, they scroll
past inside a larger tool call, and the reassuring string is the part that gets read and then
reported to the user as fact. Bit on 28 Aug 2026 — a close-out reported a clean working tree
while ten files were modified by a concurrent session. **When the point of a command is to
confirm something, print the evidence and read it — `git status --porcelain` alone, then
judge — rather than appending a verdict the shell cannot withhold.**

### A one-line fix landing on the wrong arm of a ternary is invisible to every gate

`.foregroundStyle(a ? .tertiary : .primary)` needed `.tertiary` → `.secondary`.
What landed was `.primary` → `.secondary` — the *other* arm. Both results are
valid Swift, both are real style tokens, the file compiled, the suite stayed
green, and the finding was written up as **resolved** in the review notes kept
outside the public tree. The failing value sat on the shipped surface for a day
(22 Aug 2026), on the one row whose whole job is naming the project you just
revoked.

Nothing mechanical can catch this: a ternary's two arms are the same type, so
swapping which one you edited produces working code either way. Two habits do:

1. **The tell is a comment that argues against its own code.** The block above
   the line spent eight lines explaining why `.tertiary` fails — 1.88:1,
   unimproved by Increase Contrast, semantically Apple's *disabled* colour — and
   then applied it. When prose and code disagree at arm's length, the code
   usually lost an edit, not the argument.
2. **Re-read the diff hunk, not the file.** `git show <sha> -- <file>` on the
   fix shows `- a ? .tertiary : .primary` / `+ a ? .tertiary : .secondary` in
   two adjacent lines, where the intent was to change the first token. Reading
   the finished file instead invites you to see what you meant.

Generalises past styles to any two-branch expression where both values
typecheck: `if/else` returns, `??` defaults, dictionary fallbacks, ternaries in
JSX. **And it generalises past code: a finding marked "resolved" is a claim
about intent, not evidence about the tree.** Verify a resolution by reading the
line it names.

### Deleting a UI surface can orphan the test that was pinning a WIRE CONTRACT

`PUT /framework-states` is a **full replacement** — `put_framework_states`
(`server/routes/data.py`) deletes every row for the project and re-inserts only
what the body carried, and its own docstring says so. Two clients existed over
time. v1's `setFrameworkDisabled` sent the whole disabled set, and
`SidebarStore.test.ts` pinned that with an exact-payload assertion. The v2
navigator, written months later, sent `{[id]: enabled}` — a patch, to an
endpoint that has no patch. Switching one codebook off deleted every other
codebook's `false` row, so **only one could be off at a time**, and 0.29.0
shipped that to nine channels.

Nothing was red at any point. The server did exactly what it documents. The v2
tests asserted that the switch *renders*, never what it *sends*. And when
`baa1aa0e` deleted v1, the one test pinning the contract went on passing against
a function nothing called any more — a green assertion about dead code, guarding
a live call site it had never touched.

The second-order cost is the part to remember: absence means enabled, so every
wiped row read as an OFF→ON transition and was handed to `_start_catch_ups` —
switching one codebook off could start AutoCode runs, and LLM spend, on others.
A payload bug reached into the researcher's review queue.

**Rule: deleting a component is also deleting whatever its tests were the only
witness to.** Before removing one, list the store/helper functions it was the
last production caller of, and move any wire-contract assertion onto the
replacement's call site in the same commit. **Tell:** a `grep -rn '<helper>'
src/ | grep -v test` that returns nothing — an exported function whose only
remaining callers are tests is usually a contract that has quietly lost its
guard. Generalises to any replacement endpoint (PUT-as-replace, `set`-shaped
config writes) where a partial body is silently valid.

### Verifying only through a pipe hides the entire TTY code path

`foo | tail`, `foo | grep`, `foo > file` all make stdout a non-tty, and any well-behaved CLI *changes behaviour* accordingly: Rich/`clig.dev`-style renderers skip animation, spinners and live regions don't start, colour drops. So a bug that only exists in the animated path is **invisible to every piped run** and instantly visible to the human who runs it bare.

Bit on 4 Aug 2026: `build_report.py` forced `Console(width=92)` regardless of the real terminal, so on a narrower window every line wrapped to two rows while Rich's `Live` moved the cursor up one — each refresh smeared a new copy down the screen. Every verification run during the work was piped, `_start_live()` returns early on a non-tty, and the bug was never once exercised. The user saw it on the first real run.

**When you've verified something only through a pipe, say so** — and prefer running it bare at least once (or with a pty) before claiming it works. The related house idiom is already documented above: `Console(width=min(80, Console().width))` — never force a console wider than the terminal.

**The desktop analogue, and it is the more expensive one: a test suite hides the whole rendered surface.** On 20 Aug 2026 the format-torture corpus had been run through the acceptance harness repeatedly and reported clean. One screenshot of the *same corpus* in the `.app` produced three defects — diagnostic rows that named no file, refusals rendered in error red, and fifteen sessions dropped behind a `transcripts: succeeded=57` that the next bucket contradicted with `attempted=42`. None was visible to 4,037 passing tests, because a test asserts what someone thought to ask, and nobody had thought to ask what the pane *said*. **After any pipeline or diagnostic change, run the corpus through the app once and look at it** — `experiments/folder-of-horrors/synthesise.sh` builds it. The tell for that last class is generic and worth carrying: **a summary bucket whose `attempted` disagrees with the next bucket's**, which nothing in the schema forbids.

### `attempted == succeeded + failed` is a TAUTOLOGY in most rollups — it cannot catch a silent drop

The obvious guard against "a session vanished" is per-bucket conservation. It is
the wrong one nearly everywhere, and it fails in the most flattering way: green on
the very incident it was written for. Wherever `succeeded` is **derived by
subtracting** failures — every rollup in `Pipeline.run`, before *and* after
`6497711a` — the identity holds by construction. The 20 Aug loss reported
`transcripts: attempted=57 succeeded=57 failed=0`, and `57 == 57 + 0` passes.
`ingest` is worse still: `pipeline.py` builds it as `attempted=succeeded +
len(failed)` **literally**. And it false-*positives* where `_record_parse_failure`
fires per **file** inside `for f in session.files` while the counters are per
**session** — one session with two bad subtitles gives `1 == 0 + 2`, red on a
correct run.

It has teeth in exactly one place: **`run_transcription_only`**, whose rollup
measures success independently (a session counts when it produced segments), so a
silent recording really does fall out of the sum. That is also the only command
with **no downstream bucket**, so the cross-bucket check below cannot reach it —
which is why `scripts/acceptance/invariants.py::assert_sessions_accounted` exists
and why the `transcribe:no-key` cell drives that command specifically.

**The check that does catch the general case is cross-bucket**, not within-bucket:
`transcripts → topics → quotes` are all denominated in *sessions* (`s08:51`,
`s09:128`), so `topics.attempted == transcripts.succeeded` fails on the real bug
(42 ≠ 57). `themes` is `1 + 1` LLM calls (`s10:49`, `s11:49`) — the chain ends
before it. Any such check must also be truncation-aware: `_truncate_failed` caps
`failed` at `STAGE_FAILED_MAX + 1` without touching the counters.

**Naming trap in the same area:** the CLI verb is **`bristlenose transcribe`**.
`transcribe-only` is the *run kind* (`KindEnum.TRANSCRIBE_ONLY`, what the desktop
reads from the events log) and is **not** a command — `bristlenose transcribe-only`
exits with "No such command". The internal function is `run_transcription_only`,
which makes all three names differ.

### A backgrounded `pytest … | tail`'s reported exit code is `tail`'s, not pytest's

Sibling to the two above, and the one most likely to produce a **confident false
"tests passed"**. A background Bash task reports the exit status of the
*pipeline*, which in a shell without `pipefail` is the status of the **last**
stage. So `pytest tests/ -q 2>&1 | tail -15` reports **exit code 0 even when
pytest failed**, because `tail` succeeded at tailing. The completion
notification then says "completed (exit code 0)" and reads exactly like a green
run.

Hit twice on 16 Aug 2026 while verifying the docx-parser work. Both runs were
genuinely green, so nothing broke — which is precisely why it is worth writing
down: the tell only appears when the suite is red, and by then the habit of
trusting the notification is already formed.

**Rule: never report a suite result from the exit code of a piped background
task — `Read` the output file and quote the real summary line** (`N passed, M
skipped…`). If you want the exit code to mean something, either drop the pipe
(`pytest … > out.txt 2>&1`) or set `set -o pipefail` first. The same applies to
`ruff … | tail`, `npm run build | tail`, and any `cmd | head` gate.

### AppleDouble files on external drives

When macOS copies files to a filesystem that can't store xattrs/resource forks natively (ExFAT, FAT32, SMB shares, some NFS exports), Finder creates a `._<name>` sidecar alongside every user file to carry the metadata. These are **binary blobs that share the user file's extension** — `._foo.mp4` looks like a video to anything that classifies by suffix; `._s1.txt` looks like a transcript and crashes utf-8 decode (`UnicodeDecodeError: byte 0xb0`).

Any directory scanner that walks a user-supplied folder must filter these. Use `is_os_metadata(path)` from `bristlenose/utils/fs.py` — it catches `._*` AND `.DS_Store`. Already applied at `discover_files` (s01_ingest), `load_transcripts_from_dir` (pipeline.py), and the server importer scan sites. **When adding a new scan site that walks a project folder, call `is_os_metadata` first.** The Swift `ProjectFolderWatcher` already filters via `.skipsHiddenFiles` + `name.hasPrefix(".")`.

### macOS claims `.ts` and `.mts` as VIDEO — never accept a media extension by suffix alone

macOS's UTI table maps `.ts` to `public.mpeg-2-transport-stream` and `.mts` to
AVCHD, so Spotlight indexes them as `public.movie`. On a dev machine that is
catastrophically wrong: `mdfind 'kMDItemContentTypeTree == "public.movie"'`
returned **33,381 `.ts` files** on this Mac, every one of them TypeScript, plus
268 `.mts` that were all `.d.mts` declaration files. Not a single real transport
stream among them.

Consequence: `.ts` is **deliberately excluded** from `AUDIO_EXTENSIONS` /
`VIDEO_EXTENSIONS` in `models.py`, and must stay excluded. Accepting it by
suffix would make `bristlenose run frontend/` ingest the source tree as
recordings. `.mts` *is* accepted (AVCHD camcorders genuinely write it and the
`.d.mts` collision only bites inside `node_modules`, which no researcher drops
on us) — but if transport streams ever need first-class support, gate on
content sniffing, never on the extension.

Generalises: any time you reach for Spotlight or a UTI to classify user media,
sanity-check the result against `file`/`ffprobe` before believing it. The
system's answer is about *the extension*, not about the bytes.

### i18n — single source of truth

- **Locale files live in `bristlenose/locales/` only** — `frontend/src/locales/` was deleted. The frontend imports via Vite alias `@locales`. Don't create locale files in the frontend tree. `I18n.swift` (desktop) reads the same JSON at runtime
- **`useTranslation()` is the hook; `i18n.t()` is the direct import** — use the hook inside React components; use `import i18n from "../i18n"` + `i18n.t()` in stores, announce utilities, and other non-component code
- **New keys must go in every locale directory** — currently 22: en, es, ca, ja, fr, de, ko, cs, it, pl, ru, uk, da, sv, nb, tr, nl, fi, pt-BR, pt-PT, zh-Hant, zh-Hant-HK (pl/ru/uk/da/sv/nb/tr/nl/fi/ca are machine-seeded, pending native review). **`zh-Hant-HK` is the one exception — a thin *override* fork, not a full locale:** it carries only genuine HK-idiom differences (e.g. `軟件` vs Taiwan `軟體`) and inherits everything else via the deliberate `zh-Hant-HK → zh-Hant → en` fallback (spec: `docs/design-i18n.md` §"the Traditional pair"). **Do NOT add ordinary new keys to it** — absent = inherits `zh-Hant`; an English placeholder there would pin it and *break* that inheritance once `zh-Hant` is translated. So "every locale directory" means the 21 full locales; HK gets only real HK overrides. Every `t("key")` call needs an entry in each of the 21. If using `dt()`, the desktop override must also go in each `desktop.json`
- **No test enforces en→locale key parity — don't assume a green suite means the locales are complete.** `tests/test_pipeline_diagnostic_locale_keys.py` looks like that gate but isn't: it checks *hardcoded allow-lists* (`_REQUIRED_PILL_CATEGORIES`, `_REQUIRED_HEADERS`, `_CHROME_COUNT_PREFIXES`), so adding a key to `en` never obliges anyone to extend them and the gap ships silently. That is exactly how two gaps survived until an `i18n-review` agent pass found them (30 Jul 2026): `export.scope.*` sat in `en/common.json` alone, and 19 `desktop.json` keys were missing from **all** 19 non-en locales — `menu.project.analyse` had been rendering English "Analyse" in every locale's project context menu. **When you add a key that the allow-lists cover, extend them in the same commit; when you add one they don't, no *test* will fail.** Cheapest audit: `.venv/bin/python scripts/check-locales.py` already does the flattened-key diff — but it reports missing keys as **warnings** (exit 0), and CI runs it non-strict, so the gap still ships unless someone reads the output. Use `--strict` to make it a hard gate, or an `i18n-review` agent pass for the judgement calls it can't make.
- **…and the gate is blind in the other direction too: an ABSENT en key can never be reported missing.** `check-locales.py` flattens `en/<ns>.json` and diffs each locale *against it*, so a surface that was never enrolled in English has nothing to be missing **from** — it is invisible by construction, not by oversight. This is a distinct hole from the allow-list one above: that one misses keys the *tests* don't enumerate; this one misses keys *English* doesn't have, and no amount of `--strict` closes it. Both `check-locales.py` and `test_pipeline_diagnostic_locale_keys.py` read a locale as complete when the whole feature is absent from every file including `en`. **Worked example (18 Aug 2026):** the macOS Settings ▸ Accounts pane shipped with zero `i18n.t` call sites — every string a Swift literal, `SettingsView.swift` hardcoding the pane title `"Accounts"` while the other five panes read `desktop.settingsTabs.*`. `check-locales.py` was green throughout. Worse, the source comment justified it as *"English-only, like the rest of the cloud-import surface"* — which was **already false when written**: that debt was paid two days earlier (`49ec8a50`, 16 Aug), and `docs/design-cloud-import.md:1320` had predicted this exact recurrence in writing ("the gap that reappears will do so silently"). It did, in 48 hours. **The only gate is the diff:** a new user-facing surface is reviewed for `i18n.t` call sites at the point it lands, because after that nothing mechanical will ever ask again. Tell: grep a newly-added `.swift`/`.tsx` view for `i18n.t(` / `t("` and get zero hits.
- **…and a THIRD gate is blind, this one on the wire: `test_swift_contract_parity.py` compares only the *intersection* of the two sides' fields.** Its docstring says so plainly — *"A field Swift doesn't declare is fine — the contract is schema-additive"* — which is correct for the drift it was built to catch (optionality disagreeing on a field **both** sides decode) and useless for the one that follows. **Adding a field to `bristlenose/events.py` and forgetting the Swift mirror passes every test in the repo.** No import fails, no decode breaks, nothing is red; the field simply never reaches the Mac, and the surface that needed it goes on rendering whatever it did before. **Worked example (22 Aug 2026):** `Cause` grew `reason` so the diagnostic popover could localise refusals instead of rendering `Cause.message` raw in all 21 non-en locales. Python-only would have shipped green — 4143 passing tests, `check-locales.py` clean, a popover still in English. Note the shape: this hole and the two above are the *same* failure at three altitudes — every gate we own asks "do the things I was told to enumerate agree?", none asks "is anything missing that nobody enumerated?" **Rule: a new field on `Cause` / `StageFailure` / `StageOutcome` / `PipelineSummary` is a two-file change plus the fixture, always — `desktop/Bristlenose/Bristlenose/PipelineSummary.swift` and `tests/fixtures/pipeline-summary-contract.json` (bump `version`, and add a scenario that *uses* the field, or the Swift round-trip proves nothing about it). Note `EventLogReader.swift` holds a **second, partial** `Cause` mirror that the parity test never sees at all — check whether your field belongs there too; terminus-level causes are the only thing it decodes.**
- **Seeding an existing key into the other locales? Look for an already-translated twin first.** Bristlenose forks text across surfaces (`dt()`, and the native menu mirrors much of the web UI), so the string you're about to machine-translate often already exists, reviewed, under a different key. `export.scope.{all,selected,starred}` was a verbatim match for `menu.quotes.copyScope{All,Selected,Starred}` in all 19 locales — reused with `{{count}}`→`{{n}}`, which beat translating and made the web dropdown read identically to the macOS menu. Grep the *English* value across `en/*.json` before writing any new translation.
- **Adding a whole new language = 9 JSON files + 10 registration sites across THREE surfaces (web, Python, native Swift).** Create `bristlenose/locales/<code>/` with all 9 namespace files (`common, cli, desktop, doctor, enums, pipeline, preflight, server, settings`), then register the code in all of:
  - **Web/Python (7):** `SUPPORTED_LOCALES` in [frontend/src/i18n/index.ts](frontend/src/i18n/index.ts) **and** [bristlenose/i18n.py](bristlenose/i18n.py); the `expected` set in [bristlenose/doctor.py](bristlenose/doctor.py) (`Bundle: locales` check); the `LOCALE_LABELS` map in **both** [SettingsPanel.tsx](frontend/src/islands/SettingsPanel.tsx) and [SettingsModal.tsx](frontend/src/components/SettingsModal.tsx) (native name, e.g. `it: "Italiano"`); the mock list in [LocaleStore.test.ts](frontend/src/i18n/LocaleStore.test.ts); and the locale tuples in [tests/test_pipeline_diagnostic_locale_keys.py](tests/test_pipeline_diagnostic_locale_keys.py) — `_ALL_LOCALES` (every full locale) **plus** exactly one CLDR-shape tuple: `_PLURAL_LOCALES` if the language inflects by count (the common case — one/other like it/es/de, and four-form cs/pl/ru/uk go here too since they carry `one`+`other`), or `_SINGLE_FORM_LOCALES` if it's ja/ko/zh-shaped (`_other` only). A thin fallback override goes in `_FALLBACK_ONLY_LOCALES` instead of `_ALL_LOCALES` (zh-Hant-HK is the only one). Don't skip this on the theory that the four-form tests will catch it — those derive from the presence of `_few` and need no edit; the tuples do. `test_every_locale_dir_is_classified` fails the moment a locale dir isn't in one of these lists, so the suite tells you — but only after you've added the directory.
  - **Native Swift desktop (3) — EASY TO MISS, the desktop Settings window has its OWN picker, NOT the React one:** `supportedLocales` in [desktop/Bristlenose/Bristlenose/I18n.swift](desktop/Bristlenose/Bristlenose/I18n.swift); the `Picker` `Text("…").tag("…")` list in [AppearanceSettingsView.swift](desktop/Bristlenose/Bristlenose/AppearanceSettingsView.swift); and the `expected` set in [I18nTests.swift](desktop/Bristlenose/BristlenoseTests/I18nTests.swift). The desktop reads the locale JSON from the bundle via `Bundle.main` (the xcodeproj `Copy Sidecar Resources` phase rsyncs all of `bristlenose/locales/`, so the data ships automatically — only the Swift code lists above need the edit). A plain Cmd+R self-heals the sidecar (touching `bristlenose/locales/` moves the freshness fingerprint).
  - The web runtime loader needs NO edit — it's a Vite dynamic-import glob (`import(\`.../locales/${locale}/${ns}.json\`)`), so files are picked up automatically. Lazy locale chunks are **excluded from the bundle-size budget** (the `size-limit` glob negates `common-*`/`settings-*`/`desktop-*`/`enums-*`/etc.), so a new language is size-neutral on the web bundle. **It is NOT size-neutral on the HTML export** — that is a separate single-file build (`inlineDynamicImports: true`), and because the loader's import is a template literal, Vite's glob matches `locales/*/*.json` and inlines **all 192 files**: every locale, every namespace, including `cli`, `doctor`, `preflight`, `server` and `pipeline`, which a browser report cannot use. Measured 23 Aug 2026: 1,802 KB of a 3.38 MB export, ~half the file a researcher hands to a client, and the reason Perf's export-size gate has been red since 21 Aug. Adding a language taxes every exported report ever produced. Fix proposed in `docs/design-export-locale.md`.
  - **Run `.venv/bin/python scripts/check-locales.py` after seeding** — it needs no edit for a new language (it iterates whatever dirs exist) and is the gate that reads the seeded *content*, not just the enrolment lists. It flattens every `en/<ns>.json` key and diffs against each locale, honouring the runtime fallback chain and CLDR plural suffixes. **Errors** (exit 1): invalid JSON, placeholder mismatch (`{{var}}` sets must match en — plural forms only have to stay within the en group's union), and a ru/uk `_one` that omits `{{count}}` when `_other` carries it. **Warnings** (exit 0 unless `--strict`): genuine missing keys, orphan keys, empty values. So a green run does **not** mean the locale is complete — read the `missing key(s)` warnings, they're the drift list. Also runs in CI on any `bristlenose/locales/**` change (`.github/workflows/i18n-check.yml`), non-strict. `flatten()` drops `_comment_*` pseudo-keys (the locale files' stand-in for JSON comments), so a note lives in `en` alone instead of being demanded from all 21 — added 21 Aug 2026 after one had been duplicated into 20 files. **As of 21 Aug 2026 the tree is warning-free for the first time**, which makes `--strict` a free CI change; whether to take it is `docs/i18n-defects.md` Decision 2.
  - Register Apple-HIG + QDA terms for the language in `bristlenose/locales/glossary.csv` so Weblate shows translators the agreed taxonomy. Translate in the language's **Apple-HIG register** (imperative for buttons/commands, impersonal for body text — match the platform, don't invent a register). If `pluralCategory` in `I18n.swift` doesn't handle the language explicitly, it falls through to the `one`/`other` default (correct for it/es/de; check CLDR for others).
- **Platform text forking** — `dt(t, key)` checks `desktop:` namespace first (falls back to base key). `ct(t, key)` returns `null` on desktop (hides CLI-only text). Both in `frontend/src/utils/platformTranslation.ts`. See `docs/platform-text-map.md`
- **SwiftUI `CommandMenu` titles can't use runtime strings** — menu titles stay in English; only items inside are translated
- **The pipeline-view CLI keeps its own English mirror of the pipeline reason/note strings.** `bristlenose/pipeline_view/cli.py` is i18n-free (CLI is English-only in alpha), so it hardcodes `_REASON_TEXT` / `_NOTE_TEXT` dicts keyed by the *same* locale keys the JSON uses. **Those keys live in the `settings` namespace — `settings.pipeline.reasons.*` / `settings.pipeline.quality.*` — not `pipeline.*`**, which this line said until 21 Aug 2026 and which sends a grep to a 4-key file that has none of them. (`_PROVIDER_DISPLAY` is *not* a mirror: it is built from the provider registry at import time and cannot drift.) When you touch one of those strings, grep `cli.py` for the same key and update both. **But first read `docs/i18n-defects.md` item 5:** measured 21 Aug, 3 of 23 mirrored strings diverge, and all three are a technical name in the terminal against a plain name in the SPA (`spaCy en_core_web_lg not installed` vs `language model not installed`). That may be a deliberate register fork rather than drift, in which case "keep both in sync" is the wrong instruction — the decision is open.
- **Don't round-trip locale JSON through `json.load`/`json.dump` to add a key.** The 7 `common.json` files mix literal Unicode (`…`, `—`) with `\u` escapes (mostly in non-ASCII locales). `json.dump(ensure_ascii=False)` rewrites every `\u` → literal; `ensure_ascii=True` rewrites every literal → `\u`. Either way you get a 1000-line diff for a 2-line change. Use a targeted text replace (find an anchor unique to each locale — `}\n  },\n  "feedback":` works for inserting at end of `export`) and `json.dumps(value, ensure_ascii=True)` per-value to escape only the new strings. **Repeat-pass corollary:** when a second pass replaces a value inserted by an earlier pass (e.g. fixing ja `やり直す` → `取り消す`), the in-file form is the `\u` escape because the first pass used `ensure_ascii=True`. A literal Japanese match-string won't find it. Re-encode the match string via `json.dumps(..., ensure_ascii=True)` before `text.replace(...)`

- **CJK punctuation is SETTLED — measure the platform, don't reason from a style guide.** Japanese labels take a **halfwidth** `:` + space (`名前:` is Apple's own Save dialog); Japanese prose lead-ins `注：` / `例：` take **fullwidth**, no space; Chinese takes fullwidth throughout. Measured: Apple ja 431 halfwidth vs 2 fullwidth, Microsoft ja 38,041 vs 88, Apple zh-Hant 239 fullwidth vs 0. The JTF translation-industry guide says fullwidth for Japanese and is the wrong authority for macOS chrome — both vendors treat `:` as an international symbol, not Japanese 約物. A sweep on 20 Aug 2026 got this backwards in both directions and was reverted (`4bd85ff4`). Details + reproduce command: `.claude/agents/i18n-review.md` §6a.
See `docs/design-i18n.md` for implementation gotchas (Apple glossary cross-check, `useMemo` deps, sentiment tag translation, Intl.DateTimeFormat quirks, Korean plurals, data vs chrome translation, German typographic quote JSON escaping, test mocking requirements). **For a whole new language, `docs/adding-a-language.md` is the canonical step-by-step** — the summary above is a lossy index over it and has drifted before (it undercounted the registration sites while that guide's Step 8 was correct, 3 Aug 2026). When the two disagree, trust the guide and fix the summary.

### A file-wide regex over locale JSON deletes same-named keys in other namespaces

Pruning a retired key with `re.sub(r'^\s*"undo":\s*.*?,\s*\n', "", s, flags=re.M)`
across a whole `desktop.json` also deletes `menu.edit.undo` — same key name, different
namespace, and the pattern has no idea which block it is in. Done 19 Aug 2026 while
removing `toast.undo`; it took `menu.edit.undo` ("Undo") out of all 21 locales, and the
Edit-menu fallback label with it. `check-locales.py` stayed **green**, because English
lost the key too and the gate diffs each locale *against English* (the blind spot the
i18n section above already documents from the other direction).

Two more traps in the same family, both hit in that pass: a key that is **last in its
block has no trailing comma**, so a `,\s*\n`-anchored pattern silently skips it (the
prune "succeeded" and the key was still there); and removing the last key of a block
leaves `"toast": {}`, which is valid JSON and invisible to every gate.

**Rule: scope the prune to the block.** Parse, locate the namespace, and rewrite only
within it — or match the fully-qualified path, never the bare key name. Verify with
`git diff` on one locale and read every `-` line before repeating across 21;
`json.load` + key-list comparison before/after is the cheap check that catches all
three.

**And scoping to the block is not enough if the namespace name repeats.**
`en/common.json` carries two `"codebook"` blocks — a nested prose/methodology one
(`sectionsTitle`/`sectionsBody`/`themesBody`) and the real top-level namespace, the one
that holds `codebook.frameworks`. A first-match `^\s*"codebook"\s*:\s*\{` plus
brace-matching selects the *prose* block, and the key you came for simply isn't in it
(measured 21 Aug 2026). How that fails depends on the tool: assert "exactly one match
inside the block" and it fails loudly; reach for a bare `re.sub` and it changes nothing,
reports success, and joins the silent-no-op family above. **Select the block by
*content* — the one that actually carries the key, asserted unique — or by
fully-qualified path, never by first match on the name.**

### Other gotchas

- **Rich's `console.print()` eats `[name]` as markup tags.** Square-bracket sequences are parsed as Rich style markup; unknown style names (e.g. `[serve]`, `[apple]`) are silently consumed, so `pip install bristlenose[serve]` renders as `pip install bristlenose`. Two fixes by site type: (1) plain-text output (doctor fix messages, log lines) → `console.print(text, markup=False)`; (2) sites with intentional Rich markup interpolating user-supplied text → `from rich.markup import escape; console.print(f"[bold]{escape(value)}[/bold]")`. Audit any new `console.print` that interpolates package-spec / file-glob / version-range text
- **E2E allowlists must be registered.** Every `if (...) return;`-style suppression inside a Playwright spec (e.g. "this 404 is expected") needs (a) a matching entry in `e2e/ALLOWLIST.md` and (b) a `// ci-allowlist: CI-A<N>` comment marker above the code. Categories: `infra` (stack artefact, never fixable) / `by-design` (intentional correct behaviour) / `deferred-fix` (real bug, must link to 100days.md tracker). Prevents the e2e gate from accumulating silent suppressions nobody can audit six months later. See the register header for schema, retired IDs, and v2 tooling (validator + staleness gate, deferred until ~10 entries).
- **The sidecar is built from `.venv-sidecar`, NOT `.venv` — so `.venv` is the wrong control for any bundle question.** `build-sidecar.sh:45` uses a dedicated venv carrying only `.[serve,apple,desktop,mcp]`, and its contents genuinely differ: on 30 Aug 2026 `.venv` held numba 0.66.0 / llvmlite 0.48.0 / mlx 0.32.0 while `.venv-sidecar` held 0.67.0 / 0.49.0 / 0.32.2. Nothing pins that stack, so **any `pyproject.toml` edit invalidates the deps fingerprint (`shasum pyproject.toml` + `pip freeze`, line 155), recreates the venv from scratch, and re-resolves every transitive dependency to whatever is newest** — a pin on `anthropic` moved numba two minors sideways three days later. The trap when debugging: "it works fine in the venv, so the library is not the problem" is a **non-comparison**, and it cost a full session on the SIGILL investigation. Reach for `.venv-sidecar/bin/python`, and read the shipped versions out of the bundle (`_internal/*.dist-info`) or out of `THIRD-PARTY-BINARIES.md`, which is regenerated from the sidecar and is the only tracked record of what actually shipped.
- **Auditing wheel availability by grepping `cp3XX` out of the filename is WRONG — `abi3` wheels are forward-compatible.** A wheel tagged `cp311-abi3` installs on 3.11 *and every later CPython*, so the obvious `cp3XX in filename` scan reports it missing everywhere except 3.11. Measured 3 Sep 2026 during the Python-floor audit: that check claimed `cryptography` ships **no** wheels for 3.10, 3.12 or 3.13 — it ships one covering all of them — and said the same of `tokenizers`, `psutil`, `hf-xet` and `safetensors`. The output is convincing because it looks like a finding: a column of `—NONE—` against packages that self-evidently do ship wheels. **Tell:** a package you know is universally available showing gaps on scattered, non-adjacent versions. **Fix:** parse the whole `(python, abi, platform)` tag triple — `py3-none-any` is universal, `cp3X-cp3X` is exact, `cp3X-abi3` is 3.X *and later*. Better, don't infer at all: `pip install --dry-run --report --python-version X --only-binary=:all: --platform …` answers it with the real resolver, and the result can be diffed against a CI install log to prove the model before you trust it. Same family as the `rg -rn` and zsh gotchas above — tooling that fails *quietly* and plausibly. Reusable method: `docs/design-python-floor.md` § Method.
- **A build gate that checks a file is PRESENT has not checked it is INTACT — and `codesign` will happily bless a corrupt binary.** PyInstaller shells out to `strip` per collected binary and never checks its exit status. On 30 Aug 2026 `strip` died of SIGBUS mid-`writeout` on the 128 MB `libllvmlite.dylib`, leaving a file of exactly the right size with **16 KB of zeros inside `__TEXT,__text`**; signing ran afterwards, so `codesign -v --strict` passed, `otool -L` was unchanged, and every build gate was green. On arm64 an all-zero word is `udf #0`, so the first numba JIT to reach that page raised SIGILL — every run died seconds into transcription, wrote no terminus event, and therefore **no lens would open in that project either**, which reads as an unrelated frontend bug. `strip=False` now (it saved 48 KB of a 479 MB bundle across a 14-binary sample, because wheels already ship stripped), and `desktop/scripts/check-bundle-integrity.py` fails the build on any zero-run ≥4096 bytes in executable code — ~4s over 224 Mach-Os, wired into `build-sidecar.sh` on **every** real invocation, since a bundle already corrupt when cached would otherwise be skipped forever. Full post-mortem: `docs/sidecar-transcription-crash.md`.
- **PyInstaller bundle datas: source dir present ≠ bundle dir present.** Non-`.py` runtime files (YAML, JSON, Markdown, JS, CSS, etc.) only ship if they're in `desktop/bristlenose-sidecar.spec`'s `datas=[...]` list. Python packages get bytecompiled into `base_library.zip` automatically; data files don't. Two gates catch this class: `desktop/scripts/check-bundle-manifest.sh` (source→spec, ~60ms, runs in `build-all.sh` step 1b) and `bristlenose doctor --self-test` (spec→bundle, ~2-3s, runs in step 2a). The source→spec gate is per-file: each runtime file must be matched by a datas entry that's the file itself or a directory ancestor — so single-file `(file_path, parent_dir)` entries are accepted alongside whole-directory ones. Unit tests can't catch this — they run against `pip install -e .` where data files live at their real paths
- **`from __future__ import annotations` doesn't satisfy ruff F821 if the annotated name isn't imported.** Type annotations become strings at runtime, but ruff's F821 still validates that the name is reachable in the module scope. So `def foo() -> Path:` with a per-function `from pathlib import Path` inside the body fails F821. Move the import to top-of-file
- **E2E tests: stale server on port 8150 gives wrong results** — `playwright.config.ts` uses `reuseExistingServer: !process.env.CI`. If a previous `bristlenose serve` is running locally on port 8150 (e.g. from `bristlenose serve trial-runs/project-ikea`), Playwright silently connects to it instead of starting the smoke-test fixture. This produces completely wrong measurements (353 quotes instead of 4). Always check `lsof -i :8150` before running E2E tests locally. In CI this can't happen (`reuseExistingServer: false`). The perf-gate spec has a server identity guard (`project_name === "Smoke Test"`) to catch this
- **E2E Node-side `fetch()` needs auth token explicitly** — Playwright's `extraHTTPHeaders` only applies to browser contexts (page navigation). Node-side `fetch()` in test fixtures gets 401'd without the bearer token. `e2e/fixtures/routes.ts` reads `_BRISTLENOSE_AUTH_TOKEN` from env and passes it via `authHeaders()`. Set the env var when running E2E tests: `_BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test`
- **E2E: `waitForLoadState('networkidle')` is too fragile for SPAs** — fires after a 500ms idle window, which can beat deferred `useEffect` mounts on slow CI runners. Missed nodes look like "passed" tests and you measure the wrong state. In `perf-gate.spec.ts` the pattern is a `waitForPageReady()` helper that chains: `networkidle` → wait for `#bn-app-root` children → wait for `document.querySelectorAll('*').length` to be stable across two 200ms polls. Copy this pattern for any E2E spec that measures DOM state
- **E2E: in-browser `fetch()` in `page.evaluate` can silently 401** — a dropped auth token turns into 1ms latency and a ~50-byte error body. Without `res.ok` assertions this registers as "excellent latency" and sails past size thresholds. Always assert `res.ok` inside the evaluate (`expect(ok).toBe(true)`) AND add a sanity floor for payload sizes (`expect(sizeBytes).toBeGreaterThan(500_000)` when real size is ~1.6 MB). The server identity guard (first test, serial mode) catches most cases but defence-in-depth matters
- **Export JSON embedded in a `<script>` block: `ensure_ascii=True` is NOT enough — you MUST also escape `<` `>` `&`.** The long-standing belief that "`ensure_ascii=True` escapes `<` as `\u003c`" is **FALSE** (verified 26 Jul 2026): `ensure_ascii` only escapes code points **> 127**; `<` `>` `&` `/` are ASCII and pass through **unchanged**, so a literal `</script>` in untrusted embedded content (transcript text from third-party files, participant/tag/project names) breaks out of the data `<script>` → **stored XSS** in a shared artifact. After `json.dumps(..., ensure_ascii=True)`, chain `.replace("<","\u003c").replace(">","\u003e").replace("&","\u0026")`. Fixed in `export.py:_build_export_html` + regression test `test_embedded_data_cannot_break_out_of_script`. **AUDIT SIBLING SITES** that inherited this false belief: the serve-mode `/report` embed and the CSV/HTML quote exports — any `json.dumps`-into-`<script>` relying on `ensure_ascii` alone is vulnerable
- **A CSS class audited by substring silently matches a LONGER class — audit selectors on whole tokens.** `theme/templates/export.css` is the read-only gate for the HTML export (every rule is `.bn-export-mode <sel> {display:none}`), and it is pure CSS, so renaming a control in `frontend/src` defeats a rule with **no error** — it just stops matching, and the affordance reappears in every exported report from then on. The mechanical stop is `tests/test_export_css_selectors.py`. **Two traps it had to be built around, both of which a naive version fails.** (1) **Whole-token matching is mandatory:** `badge-accept-flash` is a live animation class, so a substring search reports the stale `.badge-accept` as *found* — the very bug the gate exists to catch would have passed it. Match `(?<![\w-])name(?![\w-])`; `-` is a class-name character, so `\b` is not enough. (2) **`frontend/src` is the whole corpus, deliberately:** `bn-export-mode` is written in exactly one place (`server/routes/export.py`, onto a body holding only `<div id="bn-app-root">` plus the single-file React bundle), so the frozen vanilla renderer in `theme/js/` never receives it and a rule naming a vanilla-only class can **never fire**. Widening the search to `bristlenose/theme/` would green-light exactly the dead rules the gate exists to catch. Five selectors were stale at once on 15 Aug 2026, three of them live leaks (`.bn-counter` → the real class is `.bn-hidden-badge`; `.codebook-add-tag` → `.tag-add-row`; `.codebook-picker-btn` → no class existed at all). **When repointing one, cross-check `templates/print.css`** — it is the sibling read-only surface, it names the same controls, and it had not drifted. **And QA the result against a FRESH project:** the export inlines the *per-project baked* `<output_dir>/assets/bristlenose-theme.css` in preference to the bundled source (`routes/export.py`), so exporting from an already-rendered project embeds the OLD export.css and shows the controls still visible, with no error — same baked-CSS staleness trap as serve mode, one layer further out.
- **Export filenames: use `safe_filename()` not `slugify()`** — `slugify()` lowercases and hyphenates (`"Acme Research"` → `"acme-research"`). `safe_filename()` preserves spaces and case for human-readable Finder names. Both are in `bristlenose/utils/text.py`. Use `safe_filename()` for all export naming (zip folders, transcript files, clip files, download filenames)
- **Tests must not depend on local environment** — CI runs with no API keys, no Ollama, no local config. Always mock environment-dependent functions. The v0.6.7–v0.6.13 release failures were caused by tests that passed locally but failed in CI
- **`os.stat_result(tuple(st), {...})`'s second dict is PLATFORM-GATED — it silently drops fields the OS doesn't declare.** Faking a macOS-only stat field this way (`st_flags`, `st_birthtime`) works on macOS and becomes a **no-op on Linux**: the attribute never lands, the code under test correctly takes its Linux branch, and the assertion fails there while passing on every local run. No error, no warning — the fake just isn't there. Cost the v0.23.0 release a full 30-minute cycle (3 failures in `tests/test_cloud_materialisation.py`, both ubuntu matrix cells red, both macOS cells green). **Fake platform-specific stat fields with a proxy object**, never with `os.stat_result`'s optional dict: `class _Stat: def __init__(self, st): self._st = st; self.st_flags = …` plus `__getattr__` forwarding. The proxy carries the attribute on any OS, and production code reads it by name. Same file's `test_linux_without_st_flags_is_false` already used the proxy shape to prove the *opposite* case — copy that, not the dict. Generalises to any `os.*_result` (`statvfs_result`, `times_result`): construct a proxy, not the real type
- **PII redaction: `model_copy()` is shallow** — when redacting transcript segments, `seg.model_copy()` copies the Pydantic model but `words` (a list of `Word` objects) still references the original unredacted words. Always clear `clean_seg.words = []` after replacing `clean_seg.text`. Same caution applies to any field that might contain PII (`speaker_label`, `source_file`)
- **`CredentialStore.set()` returning cleanly is NOT evidence anything was stored — read it back.** `MacOSCredentialStore.set()` catches `CalledProcessError`/`FileNotFoundError`/`PermissionError`/`OSError` and returns normally, **by design**: under App Sandbox `/usr/bin/security` is unreachable, so the write is a silent no-op and the CLI Mac path stays graceful. The consequence is that a clean return says only that nothing raised. Any caller that reports success off the back of a `set()` is reporting something it never checked — the Miro OAuth callback did exactly this, printing "Connected to Miro ✓" while the token existed in **no** store at all (it also lacked the paste path's in-session fallback, so there was no second copy). The Swift side has the identical shape one layer over: `KeychainHelper.serviceNames` is an **allowlist**, and `CloudGrantStore` shipped against an unregistered key persisting nothing, with no error anywhere. Both were invisible for the same reason — nobody read back. Fixed 18 Aug 2026 (`d3c5f572`): `_store_token_verified` in `server/routes/miro.py` stores then `get()`s, and a mismatch is a WARNING, not a shrug. Note a read-back returning a *different* value is also failure — an env var shadows both the file and keychain reads, so the value just written is then not the one that will be used. **When wiring any new credential write, verify the round-trip; when a "saved" state disagrees with a later read, suspect the write, not the reader.**
- **PII summary is a re-identification key** — `pii_summary.txt` lists every original PII value with timecodes. It lives in `.bristlenose/` (hidden), NOT in the shareable output root. Never move it back to the output directory
- **LLM call log is a re-identification key** — `<output_dir>/.bristlenose/llm-calls.jsonl` carries session ids, prompt shas, and timing fingerprints (sibling to `pii_summary.txt`). Never include in any export, support bundle, or shareable archive. Mode `0o600` + `O_NOFOLLOW` enforced by `bristlenose/llm/telemetry.py`. Kill switch: `BRISTLENOSE_LLM_TELEMETRY=0`
- **`pii_score_threshold` is the only PII config that's wired** — `pii_llm_pass` and `pii_custom_names` are declared in `config.py` but unimplemented; since `fa78e936` (14 Aug 2026) setting either makes `s07_pii_removal.py` **refuse the run** (fail-loud — an unimplemented privacy control must not warn-and-continue). Don't write code that reads them without implementing the feature first
- **Presidio slow tests need spaCy model** — `@pytest.mark.slow` tests in `test_pii_audit.py` require `presidio-analyzer` + `spacy` + `en_core_web_lg` (400MB download). They're deselected by default everywhere (`addopts`), not just in CI. Run with `pytest -m slow`
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only
- **Auditing CLI flag deletion: grep Swift call sites too.** A3 deleted `--static` from `bristlenose run` because the static-render naming was a conflation — but the same Typer option was aliased as `--no-serve` and the macOS sidecar's `PipelineRunner.swift:957` was passing it to suppress auto-serve so Swift's ServeManager can manage the serve port separately. Deleting both spellings broke the desktop alpha path. Caught during the doc-sweep verification before any cohort tester saw it; restored as `--no-serve` (without the misleading `--static` alias). Rule for future: when deleting a CLI flag, `grep -rn '"--<flag>"' desktop/` *before* the Python edit, not after. Aliases are typically there because two semantically-distinct concerns share a single option declaration — separate the concerns at deletion time, don't just drop both names. **This extends to whole commands, and to CI workflows as a call site.** `bristlenose render` was removed (`7258cdb`) but `.github/workflows/install-test.yml` kept invoking it at four job sites, reddening `Install & Smoke Test` on every run for ~11 days (24 May–4 Jun 2026) — and it went unnoticed because the machine-local CI monitor (`~/.claude/scripts/ci-status-check.sh`) was watching a stale workflow `name:`. When deleting a CLI command or flag, `grep -rn` **both** `desktop/` **and** `.github/workflows/` before the Python edit
- `doctor.py` imports `platform` and `urllib` locally inside function bodies (not at module level). When testing, patch at stdlib level (`patch("platform.system")`) not module level
- `check_backend()` catches `Exception` (not just `ImportError`) for faster_whisper import — torch native libs can raise `OSError` on some machines
- **Never remove a worktree from inside it.** Always `cd /Users/cassio/Code/bristlenose` first, then `git worktree remove ...`. See `docs/BRANCHES.md`
- **`git mv` after editing-but-not-staging silently drops your edits from the commit.** If you Edit a file and then `git mv old new` *without* `git add`-ing the edit first, git stages the rename against the file's **HEAD blob** (index shows `R100`, identical content) and leaves your working-tree edits as an **unstaged** modification at the new path. A naive `git commit` of the staged rename then commits the file with its OLD content — your changes vanish silently. Bit during the true-the-docs archive sweep (26 Jul 2026): five docs got front-matter + superseded banners, were `git mv`'d to `docs/archive/`, and the renames showed `R100` — the banners were unstaged. Fix: after any `git mv` of a file you edited, `git add <new-path>` to fold the edits into the rename (similarity then drops to `R<100`), or stage the edit *before* moving. Tell: `git diff --cached --name-status` shows `R100` when you know you changed the content — that's the smell.
- **`git diff --quiet` cannot see a STAGED change — it compares worktree to INDEX, so "is there anything to commit?" is the one question it cannot answer.** The 0.29.1 bump step used `git diff --quiet -- <files> && echo 'already committed' || git commit`: bump-version.py STAGES what it touches, the diff saw worktree==index, took the && arm, printed the reassuring string and committed nothing — then `git push` shipped an un-bumped main, and the tag would have landed on a version already immutable on PyPI (saved only by an unrelated failure; fixed in `00e1d683`). Ask `git diff --quiet HEAD -- <files>` when the question is "does the tree differ from the commit", and `git status --porcelain` when it's "is anything pending". Same family as `cmd && ok "passed"`: the success arm asserted a conclusion the command never established.
- **The index is SHARED between concurrent sessions — `git add` hands your files to whoever commits next.** `git add` writes to one `.git/index` for the whole repo, so a second Claude session running `git commit` picks up **your** staged files along with its own. Bit on 21 Aug 2026: six files (a dashboard fix, its tests, four trued design docs) were staged surgically, and in the seconds before `git commit` the other session committed — carrying all six into a commit whose subject was about the re-analyse sheet. Nothing was lost, but the work was attributed to an unrelated message, and the changelog entries that cited "commit subject X" now pointed at a subject that was never written. **Fix: use the pathspec form, `git commit -F- -- <paths>`, which commits those paths from the working tree and ignores the index entirely** — no staging step, so nothing of yours is ever sitting in a shared index waiting to be swept up. Corollary, same incident: **don't cite a SHA while another session is active.** That commit was rewritten twice within a minute (`3c04a291` → `e583105e`, work landing in `d8399d2c`), so a SHA written into a doc was stale before the file was saved. Use `file:line` plus a `git log -S'<distinctive string>'` incantation, which survives any rewrite. And **never reach for `--amend` or a reset to "fix" the attribution** — that commit is the other session's, and rewriting it under concurrency is how work actually gets lost.
- **A bug report describes the tree its author read, not necessarily HEAD — check before you fix.** A detailed report (file, line numbers, quoted code, the contract to restore) reads as a specification and invites you to start editing. Its **line numbers are a version stamp.** On 22 Aug 2026 a report cited an ungated control at `SessionsTable.tsx:436`/`:466`; at HEAD that control sat at `:453`/`:496` and was already gated — the fix had landed two days earlier in `cb4f1e28`, together with a mechanical gate (`tests/test_export_css_selectors.py`) and three related fixes the report knew nothing about. A full cycle went into re-deriving it, down to near-identical comment wording, and it was reported back as discovery; the session's net code output was zero. **The check is two commands, before the first edit:** `git log --oneline -3 -- <file>` (has someone just been here?) and `git log -S'<distinctive string from the report>' -- <file>` (was this exact thing already changed?). **Tell:** the quoted snippet isn't at the quoted line. When that happens, stop — you and the reporter are reading different versions, and the gap is the answer. This is the concrete cost of skipping *confirm it still reproduces at HEAD*, which is not optional just because a report is specific.
- **`git checkout --theirs/--ours` is blocked during merges in the main repo** — the `.claude/hooks/block-checkout.sh` PreToolUse hook intercepts every `git checkout` to prevent feature-branch checkouts in `bristlenose/`. It can't distinguish "checkout a branch" from "resolve a conflicted file via --theirs/--ours." Workaround: write the index stage directly. `git show :3:path/to/file > path/to/file` takes the branch (theirs) version; `:2:` takes HEAD (ours); `:1:` takes the merge-base. Then `git add path/to/file` to stage
- **Renaming the repo directory breaks the venv.** Fix: `find . -name __pycache__ -exec rm -rf {} +` then `.venv/bin/python -m pip install -e '.[dev]'`
- **Xcode subprocess leakage → `[forkpty: Device not configured]` / `[Could not create a new process and open a pseudo-tty.]` in Terminal.app.** Symptom: Terminal.app refuses to open new windows with the forkpty dialog; Nova/iTerm2 crash on opening local terminals; new shell processes can't spawn. Cause: per-user process limit (`sysctl kern.maxprocperuid`, typically 1064–2128) hit by leaking subprocesses. **Xcode is the usual culprit** — SourceKitService, swift-frontend, lldb-rpc-server, dispatch helpers, indexing workers accumulate, especially across multiple worktrees or when indexing wedges. Diagnose via Activity Monitor → sort by Process Name → look for one app with 100+ entries (often `claude` workers post-`/usual-suspects`, often Xcode helpers, often both). **Fix:** quit Xcode (not always full reboot needed); if Activity Monitor reveals leaked headless `claude` workers, bulk-Force-Quit them. `killall SourceKitService` respawns clean and is gentler than restarting Xcode. Re-baseline: `ps -u "$USER" \| wc -l` should be < 500 on idle.
- **`/sync-board` parser silently drops items with mis-positioned orthogonal tags.** The parser regex (`scripts/sync_100days.py` `_ITEM_WITH_DESC_RE`) requires `\s*[—–-]\s*` IMMEDIATELY after the closing `**` of the bold title. Anything between the closing `**` and the em-dash separator breaks the match — the line is skipped entirely (no error, no warning, just absent from the parsed items list). When adding orthogonal tags like `[Beta-must]` / `[stage-2-prereq]` / 🔴 / 🟡 alongside the standard `[Sn]` sprint tag, **place them after the em-dash, in the description**, not before. Wrong: `- [S3] **Title** [stage-2-prereq] 🔴 — desc`. Right: `- [S3] **Title** — [stage-2-prereq] 🔴 desc`. Verify with `python3 -c "from sync_100days import parse_doc; items = parse_doc(...); print(len(items))"` after edits — count should match expectations. Same trap exists for nested `**bold**` inside descriptions: if a description contains `**word**` somewhere and the title's `**...**` isn't followed by ` — `, the regex backtracks and absorbs body text into the title, producing 1500-character card titles on the board. Fix: ensure title `**...**` is always followed by ` — ` (em-dash), and avoid nested `**bold**` inside descriptions of items intended for /sync-board (use `_emphasis_` instead).
- **`commit-msg` hook scans for private-content leakage.** A `commit-msg` hook (`~/.bristlenose-leak-patterns`) blocks commits whose **message** references private-only patterns. The pre-commit hook only blocks the diff; this one blocks the message. Workaround: rephrase the message to drop the reference (e.g. "see the gitignored plan note" or just omit the pointer). Don't `--no-verify` — fix the message. The hook list lives at `~/.bristlenose-leak-patterns`. **The leak patterns include filename stems too**, not just paths: `road-to-alpha`, `sprint2-tracks`, `100days`, `qa-backlog`, `succession-plan` — referencing any of these in a commit message (or in a public doc, via the PreToolUse `leak-scan.sh` hook) blocks. Use indirect language: "alpha-checkpoint planning notes" instead of "road-to-alpha", "sprint planning notes" instead of "sprint2-tracks". The same `leak-scan.sh` hook also fires on Edit/Write to public docs that contain these strings — applies symmetrically. **The bare directory path `docs/private/` is itself a blocked pattern**, not just the filename stems — so a new public doc can't even name the directory when pointing at maintainer-only material. Write "the maintainer's private planning notes, kept outside the public repo/tree" instead of `docs/private/<file>` (cost two write-retries authoring `docs/ARCHITECTURE.md`, 14 Jul 2026).
- **Transitive bare-name shellouts from PyPI deps break under macOS App Sandbox.** `bundled_binary_path("ffmpeg")` only helps callers we control — but PyPI deps like `mlx_whisper.audio.load_audio` shell out to bare `"ffmpeg"` via `subprocess.run(["ffmpeg", …])`, bypassing our helper. Under the sandbox the inherited PATH excludes Homebrew, so the bare lookup fails with `[Errno 2] No such file or directory: 'ffmpeg'` and transcription silently produces empty transcripts. Fix: `prepend_bundled_to_path()` in `bristlenose/utils/bundled_binary.py` is called from `bristlenose/__init__.py` before any submodule loads. No-op outside the bundle. Same fix transparently covers `faster_whisper` and any other transitive bare-name shellout. **When adding a new PyPI dep that processes media files, audit it for bare-name shellouts** — `grep -r 'subprocess.*\["ffmpeg"\|"sox"\|"mediainfo"' .venv/lib/python*/site-packages/<dep>` will catch the common ones. The PATH-prepend already handles ffmpeg/ffprobe; for other binaries you'd need to add them to the bundle datas list and extend `bundled_binaries_dir()`.
- **Python 3.12+ `mimetypes.init([])` doesn't skip system files.** Intuition says "pass empty list = skip system walk." Wrong. CPython 3.12.13 `mimetypes.py:378` does `files = knownfiles + list(files)` when `files` is non-None — so `init([])` reads `knownfiles + []` = the full system list. Under macOS App Sandbox those reads raise `PermissionError`, which `init()` doesn't catch — `mimetypes._db` stays poisoned and every subsequent `guess_type()` raises, surfacing as HTTP 500 on `/static/*.js`. The reliable escape hatch is `mimetypes.knownfiles = []` *before* any init (lazy or explicit) fires. Done in `bristlenose/__init__.py:8-22` so it lands before any submodule import. See `docs/design-desktop-asset-serving.md` "Shipped upstream fix" subsection
- **In a worktree, double-check absolute paths in Edit/Write calls.** When the worktree's path looks like `/Users/cassio/Code/bristlenose_branch <name>/<file>` and the main repo's path is `/Users/cassio/Code/bristlenose/<file>`, an Edit call to the latter silently lands the change on `main`'s working tree, NOT this worktree. Symptom: `git status` in the worktree shows nothing changed; `git status` in main shows an unwanted modification. Particularly easy to trip when grep output uses relative paths (`../bristlenose/...` from `frontend/`) and you mentally translate to an absolute path. Always start absolute paths with the current `pwd` prefix; if in doubt run `pwd` first. Recovery: `cd /Users/cassio/Code/bristlenose && git checkout -- <file>` (safe if main is clean), then redo with the right worktree path.
- **Worktrees don't inherit gitignored binaries.** `desktop/Bristlenose/Resources/{ffmpeg,ffprobe,models/}` are large static binaries fetched once into the main repo via `desktop/scripts/fetch-ffmpeg.sh` (gitignored, won't follow worktrees). If you open a worktree's `Bristlenose.xcodeproj` and Cmd+R, Xcode's Copy Resources phase finds nothing to copy — the resulting `.app` ships *without* ffprobe and the pipeline silently can't probe video files (analysis surfaces "Failed" with no obvious cause). `/new-branch` Step 9 now symlinks these from main; if you set up a worktree by hand, do the same or run `desktop/scripts/fetch-ffmpeg.sh` from inside the worktree
- **Status-bar `-dirty` ≠ source dirty.** `desktop/Bristlenose/Bristlenose/GeneratedBuildInfo.swift` is regenerated every Xcode compile, so `git describe`-style status strings show `<sha>-dirty` even on a clean source tree. Don't use the `-dirty` suffix as evidence of "build is from uncommitted source"; check `git status --porcelain | grep -v GeneratedBuildInfo` if you need to know whether the bundle reflects committed code
- **Building bundled sidecar in a worktree only updates *that* worktree's bundle.** `desktop/scripts/build-sidecar.sh` resolves `ROOT="$DESKTOP_DIR/.."` — i.e. whatever repo holds the script you ran. If the active `.app` is launching from the main-repo's Xcode project but you ran `build-sidecar.sh` from a worktree, the active bundle is stale relative to your edits. Open the worktree's `desktop/Bristlenose.xcodeproj` (not main's) so Xcode picks up the worktree's freshly-built sidecar
- **QA-ing a *frontend/CSS* change in the bundled `.app`: the JS half is now automatic, the CSS half still isn't.** The bundled `.app` (`sidecar=bundled` in the footer = prod serve, not `--dev`) gets the SPA from two baked sources. (1) **JS — automatic since 29 Jun 2026.** `desktop/scripts/build-sidecar.sh` now runs `npm run build` itself before bundling (and the sidecar source-fingerprint covers `frontend/src` + `bristlenose/locales`, so the Xcode "Copy Sidecar Resources" freshness gate, `check-sidecar-freshness.sh`, **fails loudly** if the bundle predates a frontend edit). So you no longer hand-run `npm run build` for the `.app` — just rebuild the sidecar (`desktop/scripts/build-sidecar.sh` [+ `sign-sidecar.sh` + clean build]) and the React bundle inside `…/bristlenose-sidecar/_internal/bristlenose/server/static/` is current. This also closes the `/new-branch --from-cloud` trap (it `ditto`s **main's** sidecar in; the next sidecar build now rebuilds the worktree's frontend and re-stamps, so the gate flags the stale ditto'd bundle until you do). The PostToolUse hook `frontend-stale-reminder.sh` nudges after any frontend/locale edit. (2) **CSS — still manual.** `bristlenose/theme/organisms/sidebar.css` is **not** in the Vite output; it's served as `/report/assets/bristlenose-theme.css`, which in prod (`serve_theme_css_with_fallback`, `app.py`) *prefers the per-project baked copy* `<output_dir>/assets/bristlenose-theme.css` and only falls back to the bundled source when the project has none. So an already-rendered project serves its **stale** baked CSS even after a correct sidecar rebuild. Fix: test against a **freshly-imported** project (no baked copy → fallback serves the rebuilt source) or regenerate the baked file — `.venv/bin/python -c "from bristlenose.stages.s12_render.theme_assets import load_default_css; open('<proj>/bristlenose-output/assets/bristlenose-theme.css','w').write(load_default_css())"` run from the **worktree venv** (reads branch source). Dev mode (`serve --dev` + `?embedded` for embedded-only features) sidesteps both — live JS from Vite, live CSS from source — but it's a browser, not the WKWebView; for a feature whose whole point is the native context, the `.app` pass is the real acceptance test
- **Python 3.14's `ensurepip` is broken for `python -m venv` on some macOS installs.** If default `python3` points at 3.14 (brew-installed), `/new-branch` (or plain `python3 -m venv .venv`) fails with `ensurepip --upgrade --default-pip returned non-zero exit status 1`. Fix: use `python3.12 -m venv .venv` explicitly — 3.12 is what CI uses and what every other worktree uses. This will shake out when 3.14 tooling stabilises, but as of April 2026 it's a real papercut on fresh worktree setup
- **Stale `__pycache__` can serve old CSS after theme edits.** Stage 12's static-render code reads CSS files at runtime, but stale `.pyc` bytecode can interfere with the import chain. If theme CSS changes aren't appearing in the byproduct HTML on disk (or in `bristlenose serve`'s auto-rendered output), run `find . -name __pycache__ -exec rm -rf {} +` before re-running. For daily dev, set `export PYTHONDONTWRITEBYTECODE=1` in your shell profile to prevent `.pyc` creation entirely
- **`Console(width=min(80, Console().width))`** — the `Console()` inside `min()` is a throwaway instance that auto-detects the real terminal width. This is the intended pattern; don't cache it
- **Homebrew tap repo must be named `homebrew-bristlenose`** (not `bristlenose-homebrew`). See `docs/design-homebrew-packaging.md`
- **Homebrew formula uses `post_install` pip to avoid dylib relinking failures.** See `docs/design-homebrew-packaging.md`
- **Anything installed in brew `post_install` skips the auto-link phase.** Homebrew runs `def install` → link phase → `def post_install`. Files placed in the Cellar by `post_install` (pip-installed scripts, generated configs, man pages from wheel data scheme) land *after* link has run, so brew never symlinks them into `/opt/homebrew/bin/`, `/opt/homebrew/share/man/`, etc. Symptom seen: pip's wheel-data scheme placed `bristlenose.1` at `<cellar>/share/man/man1/` during `post_install`, but `man bristlenose` silently didn't resolve because the auto-link symlink was never created. **Fix pattern:** install the file in `def install` from a stable path. The sdist source is unpacked into `buildpath` before `def install`, so `man1.install "bristlenose/data/bristlenose.1"` (canonical path inside the package) works — `man/bristlenose.1` is a symlink to the same file. Install in `def install`, not `post_install`, for anything that needs auto-linking
- **Homebrew 6.0 tap trust: `brew install` works, bare `brew upgrade` silently skips us.** Since 6.0 (11 Jun 2026) non-official taps must be trusted before their Ruby is evaluated, and the gate is **ARGV-based** (`explicitly_allowed?` in Homebrew's `trust.rb`): a tap is allowed only when its name appears in the typed command. So `brew install cassiocassio/bristlenose/bristlenose` still works (fully-qualified name is in ARGV, self-trusts for that invocation, auto-taps a clean machine) — but bare `brew upgrade` never names us, drops the formula from the plan, and emits an `opoo` **warning, not an error**. `brew outdated` likewise omits us. Net effect: an existing install goes stale indefinitely with nothing a user would notice. Mitigations, all shipped: the tap formula's `caveats` prints the trust command on every fresh install; README / INSTALL / the website install + welcome pages carry it; `bristlenose doctor`'s `check_brew_tap_trust` catches installs that predate the change — and note it gates on the **Cellar keg path**, deliberately *not* `doctor_fixes.detect_install_method()`, which returns `"brew"` for any `sys.executable` under a Homebrew prefix and so also matches `pip install` into a Homebrew *Python*; reuse the loose detector for phrasing a fix message, never for deciding whether the brew *formula* is installed (pinned by `test_pip_into_homebrew_python_skips`). **Don't** reach for `HOMEBREW_NO_REQUIRE_TAP_TRUST=1` — documented as a temporary opt-out slated for removal. Note trust from a qualified install is per-invocation and **not** persisted (nothing written to `trust.json`); only an explicit `brew trust` persists, and the on-disk key is `trustedformulae` while `brew trust --json=v1` normalises it to `formulae` — read the JSON, don't parse the file. **Two corollaries that bit us in the same audit:** (1) **never print a short-name brew command for our own formula** — `brew upgrade bristlenose` is *refused* when the tap is untrusted, i.e. it fails for exactly the users being told to run it; always the fully-qualified `brew upgrade cassiocassio/bristlenose/bristlenose` (pinned by `test_serve_deps_missing_brew`). (2) **Programmatic `brew install` shellouts need `env={**os.environ, "HOMEBREW_NO_ASK": "1"}`** — 6.0's ask mode prompts whenever the plan pulls in dependencies, and both our shellouts (`preflight/ffmpeg.py`, `ollama.py`) run *after* our own Confirm prompt on a TTY, so without it the user confirms one decision twice. Full failure mode: `docs/design-homebrew-packaging.md` §Known tradeoffs
- **`BRISTLENOSE_FAKE_THUMBNAILS=1`** env var — layout testing only. Defined as `_FAKE_THUMBNAILS` in `bristlenose/stages/s12_render/dashboard.py`
- **Logging**: two independent knobs — `-v` controls terminal (WARNING/DEBUG), `BRISTLENOSE_LOG_LEVEL` env var controls log file (default INFO). Log file lives at `<output_dir>/.bristlenose/bristlenose.log` — **not** at `.bristlenose/bristlenose.log` relative to cwd. When grepping per-project logs, always prefix with the output dir. See `docs/design-logging.md`
- **LLM request latency**: every `LLMClient.analyze()` call emits one INFO line `llm_request | provider=X | model=Y | elapsed_ms=N | schema=Z` (added Apr 2026 for perf baselining). Greppable for median/p95 analysis — see `docs/design-perf-fossda-baseline.md` step 6. New providers get this automatically (wrapping is in the dispatcher, not per-provider)
- For React/TypeScript/frontend gotchas (routing, video player, stores, testing), see `frontend/CLAUDE.md`
- For pipeline runtime gotchas (resume, caching, llm_client lifecycle, metadata), see `bristlenose/stages/CLAUDE.md`
- For stage/pipeline gotchas (topic maps, transcripts, coverage, speaker codes), see `bristlenose/stages/CLAUDE.md`
- For JS/CSS/report gotchas (load order, modals, hidden quotes, toolbar), see `bristlenose/theme/CLAUDE.md`
- For LLM/provider gotchas (Azure, Ollama, provider registry, max_tokens), see `bristlenose/llm/CLAUDE.md`
- **Cloud-session `claude/...` branches: cherry-pick the docs, drop the staging dir.** When a Claude Code Cloud session (often phone-started) creates a `claude/<name>-XXXXX` branch, it tends to dump work into a staging dir like `_<name>-extract-me/` plus a design doc. The script/rules usually get installed to `~/bin/` + `~/.claude/` on the Mac during the session, so the staging dir is throwaway. Rescue pattern: `git checkout main && git checkout origin/claude/<name>-XXXXX -- docs/design-<thing>.md && git commit && git push && git branch -D … && git push origin --delete …`. Don't merge the whole branch — the staging dir doesn't belong in the tree. Also: the cloud session may leave the main repo dir checked out to the feature branch with stale "modifications" that are just main's progression — `git checkout -- <files>` is safe (vs-main diff is empty)
- **Inside a cloud session, local `main` is stale — read `origin/main` instead.** The cloud env clones origin/main as the working branch at session start, then leaves the local `main` ref pointing at whatever commit it cloned from. Any subsequent commits to origin/main during the session don't update local `main`. Sitrep and "what shipped in the window" audits via `git log main --since=...` silently return a truncated view (only commits up to the cloud-clone point). Always use `origin/main` (or `HEAD` when on the working branch) for window queries from cloud: `git log origin/main --since="N days ago" --pretty=...`. Confirm at session start: `git rev-parse main` vs `git rev-parse origin/main` — if they differ, local `main` is the stale one
- **Cloud session, no `gh` CLI — use the GitHub MCP for PR + merge.** When the user asks for a merge from a cloud env, the path is `mcp__github__create_pull_request` then `mcp__github__merge_pull_request` (load via ToolSearch with `select:` query). The MCP repo scope is restricted per the system prompt (`cassiocassio/bristlenose` only) — calls to other repos are denied. After merging from cloud, the version tag should be created from the dev machine (`git tag v<X.Y.Z> <merge-sha>`) before pushing to PyPI — `scripts/bump-version.py` writes and stages the version files for the local dev flow, and the tag belongs on the merge commit, which doesn't exist until the PR lands. (This used to say the script "tags HEAD-before-commit"; it no longer tags at all — 14 Aug 2026. The advice is unchanged, the reason is simpler.)
- **Release-to-PyPI workflow doesn't always fire on tag push via `--tags`** — `git push origin main --tags` triggers the branch-push workflows (CI, CodeQL, Snap) but the tag-driven `Release to PyPI` workflow can silently miss the event. Workaround: `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` — same SHA, fresh trigger, semantic no-op. Root cause appears to be GitHub Actions debouncing tag-push events bundled with branch-push events. Future fix: add `workflow_dispatch:` to `release.yml` so it can be re-triggered without tag surgery
- **A failed release run and a release run that never fired need different fixes — don't reach for the tag-redelivery workaround reflexively.** Two distinct failure modes: (1) the workflow *never fired* (debounce) → the `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` redelivery above. (2) the workflow *fired and a job failed* (e.g. e2e stalled on the Playwright browser CDN) → NOT a redelivery case. Critically, **`gh run rerun <id> --failed` replays the *tagged commit*, not `main`'s latest** — so if a later commit on `main` already fixed the failing step, re-running the old run just fails again on the unfixed code. The fix is to move the tag to the fixed commit (`git tag -f v<X.Y.Z> <fixed-sha> && git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`), which triggers a fresh run on the fix. Diagnose first with `gh run view <id>` (did it fire? which job failed?) before choosing. Worked example 4 Jun 2026: v0.15.13's run failed on the e2e Playwright-browser CDN stall; a `--failed` rerun of the stale-commit run failed identically, while moving the tag to `14af414` (which bumped `@playwright/test` 1.59.1→1.60.0 to fix the chromium-install hang on Node 24) published cleanly. Ground truth is always `curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version`, not the run's conclusion
- **A test timeout that keeps needing doubling is a hang, not a slow path — and here it was a real bug.** `tests/test_run_lifecycle.py`'s SIGINT/SIGTERM tests failed on ubuntu-latest only, and were "fixed" three times by raising the deadline (15s `proc.wait` → poll at 120s → 240s), each time diagnosed as matrix CPU contention. It was never slowness. `run_lifecycle` appended `run_started` at one statement and only opened its `try:` several statements later, leaving the pid-file write, the log line and `telemetry.set_run_context` **outside every handler**. A signal landing in that window raised `KeyboardInterrupt` straight out of `__enter__`, **no terminus event was ever written**, and the run read as *stranded* — reconciled to `run_failed` on the next start. A researcher who pressed Ctrl-C during startup was told their run had **failed**. The test aimed straight at the window because it signalled as soon as `run_started` appeared; on a loaded runner the subprocess was still inside it. Fixed 8 Aug 2026: the guard now opens on the statement after `append_event(started_event)`, and the tests wait on a **readiness sentinel** the subprocess writes just before `signal.pause()`, so the signal reaches a genuinely paused process. Deadlines came back to 60s. Three lessons: (1) polling the events file rather than `proc.wait` is still right — keep `_wait_for_event`; (2) **wait for the state you are about to act on, not a proxy that merely precedes it** — `run_started` is written during startup, several statements before the body runs; (3) when a flaky test only fails under load, suspect an unguarded window before you suspect the clock, and prove it by *widening* the window deterministically (patch the slow call) rather than racing it. Pinned by `test_subprocess_sigint_during_startup_is_cancelled`, which fails on the old code while the original test still passes — the reason it had to be added rather than just relaxing the deadline
- **CI `test` job doesn't `npm run build` the frontend** — `bristlenose/server/static/` is empty in pytest CI, so `_mount_prod_report` returns the C3 fail-loud "Build incomplete" 500 page instead of an SPA HTML response. Any new pytest test that hits a `/report/*` route in prod mode (`create_app(..., dev=False)`) fails with `AssertionError: …Build incomplete…`. Two ways out: (1) build the frontend in CI test job (~30-60s/cell — recommended long-term); (2) use the existing `prod_app_factory` pattern in `tests/test_server_status_page.py` which monkeypatches `_STATIC_DIR` to a tmp dir containing a synthetic Vite-shaped `index.html` with `<div id="bn-app-root">`. **`dev=True` on `create_app` does NOT route to `_mount_dev_report`** — mount selection reads the `_BRISTLENOSE_DEV` env var (named `hmr` inside `create_app`), not the `dev=` param. Setting `dev=True` only enables playground/admin/debug-500 features; for the dev mount you'd need to set env-var before calling. Use the `_STATIC_DIR` monkeypatch instead
- **CI fires on push-to-main and pull_request-to-main only, not on feature branch pushes** — `.github/workflows/ci.yml` `on:` block has no `push.branches: [<feature>]`. Pushing to a non-main branch updates origin but triggers nothing. To get CI signal before merging, open the PR. (Counter-intuitive coming from projects that run CI on every branch push.) `release.yml` fires only on `push.tags: ["v*"]`
- **Smoke fixture must include a `pipeline-events.jsonl` with a `RunCompletedEvent`** — `tests/fixtures/smoke-test/input/bristlenose-output/.bristlenose/pipeline-events.jsonl` carries a hand-crafted terminus event so `app.state.last_run[1]` populates on server startup, so `status_page.detect_status` returns `None`, so `/report/*` falls through to the SPA mount. Without it the server-rendered status page intercepts ("Nothing to see here, yet.") and every SPA-based test against the fixture fails on `#bn-app-root` being absent. Run_id and timestamps are stable strings — don't regenerate them on whim, or perf-history will see git-noise as a perf change. Regression-pinned by `tests/test_server_status_page.py::TestSmokeFixtureMountsSPA` + `e2e/tests/spa-mounts.spec.ts`. **Any new test fixture that boots `bristlenose serve` against it inherits this contract** — give it a terminus event or the SPA never mounts. **This committed `.bristlenose/` dir LOOKS like runtime detritus but is a deliberate contract — don't delete it or assume the gitignore should swallow it.** Everywhere else `.bristlenose/` is a per-run state dir (db, log, llm-calls.jsonl) carrying re-identification keys and is gitignored; this one fixture is the sole tracked exception, re-included via a surgical negation in `.gitignore` (the dir + `pipeline-events.jsonl` + `intermediate/*.json` are tracked; logs/db stay ignored even inside it). If a future cleanup proposes synthesizing it at test-time, that's a legitimate option — but until then, keeping it committed is the intended resting state (7 Jun 2026)
- **Test-only fixes re-use the existing tag; they don't bump the version** — when a fix touches only `tests/`, `e2e/`, fixtures, `CLAUDE.md`, `docs/`, `.claude/` agent tooling, `.github/`, or workflow files (anything excluded from the sdist/wheel — the wheel ships only `bristlenose/` per `[tool.hatch.build.targets.wheel] packages`, and the sdist `exclude`s `.claude/`), the shipped wheel is byte-identical with or without the fix. This covers whole *features* that live outside `bristlenose/` (e.g. the Cassandra agent + `/cassandra` skill + dependency register, 5 Jun 2026) — "new in the repo" ≠ "new in the package"; the version labels the PyPI/Homebrew/Snap artifact, not git state. Re-use the existing tag by force-moving it to the fix-merge SHA (`git tag -f v<X.Y.Z> <merge-sha>`) and re-pushing (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`). Don't bump to <X.Y.Z+1> — adds bookkeeping (CHANGELOG entry, README snippet, homebrew tap dispatch) for no semantic gain and forks the version line for cosmetic reasons. Counter-rule: PyPI immutability — if the version ever successfully published, you can't re-upload, and a bump IS required. Verify with `curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version` before deciding

## Reference docs (read when working in these areas)

**Must-read before writing user-facing text:**
- `docs/glossary.md` — terminology + tone guide
- `docs/platform-text-map.md` — shared/desktop/CLI text forking, `dt()`/`ct()` inventory
- `docs/design-shared-formats.md` — **read before writing any `format*` helper that renders a value a user reads.** The register of formats duplicated across Python / TypeScript / Swift: which agree (pinned by `tests/fixtures/shared-format-contract.json`, asserted from both pytest and vitest), which don't, and which differ on purpose. Two classes: *parsed* contracts, where a mismatch breaks function and which were already handled, and *rendered* ones, where a mismatch is a visible inconsistency — every drift measured in the 22 Aug 2026 audit was the second kind. Nomenclature rule: **one stem per format, house casing per language** (`duration_human` / `formatDurationHuman` / `DurationFormat.human`), because a family with no shared stem is a family no grep will find — which is exactly how session duration reached four live renderings. `timecode` closed 22 Aug 2026 (was 9 implementations / 3 formats; now one per language — minutes padded, hours never: `05:30`, `1:12:45`). **It is also the one entry with a PARSED half** — transcript .txt/.md files are a round-trip format, so the reader regex in `pipeline.py` must stay `\d{1,2}`; it was `\d{2}` and a `[1:00:00]` segment was dropped *silently*, no error, a short transcript the only symptom. `finder_filename` closed the same day (floor vs ceil on the 2:1 split — they disagreed on every 3-, 4- and 6-char extension, i.e. every common media file). No open gaps as of 22 Aug 2026. **Before adding a `format*` function, check whether the format is already in the register — and before changing a rendered format, check whether anything parses it back, every reader and not just the one named after the format.**

**Must-read before touching tag suggestion, telemetry, or data governance:**
- `docs/methodology/` — canonical methodology docs. Treat as authoritative: when code and doc disagree, the doc is the spec and the code is wrong.
  - `tag-rejections-are-great.md` — rejection-telemetry theory, alpha experiments, six-field data model, ten-year ratchet endgame
  - `consent-gradient.md` — Level 0–3 data-governance gradient, sensitivity model, consent UX principles, sequencing discipline
  - `framework-arc-quarterly-review.md` — quarterly review template and the long-arc commitments it reviews against

**Sibling CLAUDE.md files:** `frontend/`, `bristlenose/theme/`, `bristlenose/stages/`, `bristlenose/llm/`, `bristlenose/server/`, `desktop/`

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
- `docs/design-pipeline-diagnostic-popover.md` — **read before adding any new error / status / message that surfaces in the popover, the pill, the sidebar glyph, or any toast.** Five-kind `MessageKind` taxonomy (`bristlenose/ui_kinds.py`), length budgets, anti-patterns, flowchart for fitting new messages into the existing vocabulary instead of inventing new glyphs/colours
- `docs/design-platform-transcripts.md`, `docs/design-transcript-coverage.md`
- `docs/design-people.md` — **problem-first spec for person identity: jobs to be done, then UX, then data.** Read before touching names, speaker roles, or anything that renders a person. Owns the ranked sequence, the settled decision 1 (codes are globally-numbered slots, identity a layer above; renumbering falls out of renaming — supersedes §11c's (session,code)-rekey direction), the one still-open product call (decision 2: whose name survives an export), and §H's sequenced work packages
- `docs/design-speaker-splitting.md`, `docs/design-speaker-role-detection.md`
- `docs/design-speaker-editing.md`, `docs/design-transcript-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md`
- `docs/design-multi-project.md` — scope rules (instance vs project tables)
- `docs/design-session-management.md`
- `docs/design-logging.md`

**Export:**
- `docs/design-export-html.md` (anonymisation), `docs/design-export-locale.md` (one language per deliverable — proposed), `docs/design-export-quotes.md` (CSV/XLS), `docs/design-export-clips.md`, `docs/design-export-slides.md`, `docs/design-miro-bridge.md`, `docs/design-footer-feedback-react.md`

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

**Analysis / research methodology:**
- `docs/design-research-methodology.md` — read before changing prompts or analysis logic
- `docs/academic-sources.html` — theoretical foundations
- `docs/design-analysis-future.md`, `docs/design-quote-sequences.md`, `docs/design-dashboard-stats.md`, `docs/design-signal-elaboration.md`

**i18n:** `docs/design-i18n.md` — terminology table, implementation gotchas

**Codebook:** `docs/design-codebook-island.md`, `docs/design-moderator-question-pill.md`, `docs/design-dynamic-codebook-builder.md`

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
- **The release chain is executable, and it is documented in three places, not one.** [`scripts/README.md`](scripts/README.md) is the index (what to type: `release.sh plan|run|verify`, the gates, the suites that prove the gates). [`desktop/scripts/REPORT-STYLE.md`](desktop/scripts/REPORT-STYLE.md) Part 2 is the *rules* a script follows — where constants live (`scripts/project.conf`), why probes are tri-state, what each exit code means (`75` = acts done, verification pending), the testability seams, and the shell traps this codebase has already paid for. `docs/design-release-machine.md` is the architecture and `docs/release-premortem.md` replays six months of release incidents against the current scripts.
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

**Internal TestFlight since 14 Jul 2026** — shipping build **0.29.0 (3067)** — first build accepted by App Store Connect: **0.20.0 (2068)**, App-Sandbox + Hardened-Runtime + arm64-only, signed Apple Distribution.

**0.29.1 shipped 31 Aug 2026, evening — verified 9 of 9 channels.** A patch,
and a regression in 0.29.0's own headline feature: only one codebook could be
switched off at a time, because the new navigator sent a single-key patch to a
replacement endpoint — every write deleted every other codebook's state row,
and each wiped row could start an unrequested catch-up AutoCode run. The
navigator now sends the whole disabled set and mirrors it into SidebarStore
(the second half: other lenses read the switch from there, hydrated once per
session). Three tests pin the payload — the thing nothing had ever asserted;
see Gotchas, "Deleting a UI surface can orphan the test that was pinning a
wire contract". The release ran the day the evening rule learned about **bank
holidays** (working day, not weekday — check gov.uk/bank-holidays.json, don't
derive), and surfaced two release-machine defects, both fixed the same night:
the bump step's `git diff --quiet` guard could not see a STAGED bump (it
announced a commit it never made — an un-bumped push, saved only by an
unrelated failure), and `run` could discover a missing credential four steps
in — credentials are now resolved, probed and displayed above the one typed
confirmation (fingerprint pins, per-type keychain policy, announced dialogs,
caffeinate; the five-agent audit is in `docs/design-release-machine.md`).
Copr hit the Source0 CDN race even with `needs: verify-pypi` — the fetch now
re-asks a 404 for ten minutes, and the wheelhouse arch pin from the morning
held on an aarch64 builder.

**0.29.0 shipped 31 Aug 2026** on all nine channels — PyPI, GitHub Release,
Homebrew, Snap, TestFlight (build 3067), the notarised `.dmg`, the website
changelog, and Fedora Copr. It is the codebook release: the lens rebuilt as a
navigator with a browsable library, and three false claims corrected (the
uninstall dialog promising preserved AutoCode results, `pipx install
bristlenose` yielding a CLI whose `run` exits 1, and the privacy page denying a
server that exists). It also retired the v1 codebook lens — `CodebookPanel` and
its sidebar are deleted, `Tab.codebookV2` is out of the enum, and the lens took
`tag` back from the temporary `tag.square`.

Two release-machine defects surfaced during the run; both are fixed on main.
**A single negative ASC read was treated as proof of absence** — the TestFlight
probe asked App Store Connect seconds after a successful upload, got an empty
list because the build index had not propagated, and offered to re-upload a
build number that is spent forever. Only Apple's own `DUPLICATE` refusal
stopped it, which is luck rather than a gate; `BN_PROBE_WINDOW_S` now re-reads
across the propagation window. **And the Copr wheelhouse inherited the
builder's architecture** — see the Fedora paragraph below.

**Standing guard for every release: do not let the `associated-domains` entitlement ride** — it is `skip-worktree`, so `git status` cannot see it; committing it obliges regenerating the Mac App Store profile or the archive fails to sign, and it is for a parked feature.

**Fedora/Copr — LIVE since 28 Aug 2026**, serving 0.29.0 from `cassiocassio/bristlenose` (fedora-43-x86_64 only; F42 was dropped by Copr). Install is `sudo dnf copr enable cassiocassio/bristlenose && sudo dnf install bristlenose` — proven on a clean F43 box before the docs went live (marker → `rpm`, man page rpm-owned with no home copy, `ffmpeg-free` serving, both SPA halves present). Rebuilds are automatic: `trigger-copr` in `release.yml`, **`needs: verify-pypi` never `publish`** (Source0 is fetched from PyPI during the build and would race the CDN). Standing obligations from `docs/design-fedora-packaging.md` §7: **CVE tracking for the vendored wheelhouse is ours forever** (`dnf` cannot see inside it), and **the wheelhouse tracks Fedora's Python on Fedora's calendar** — `.copr/Makefile` pins `python3.14` so a chroot move fails loudly, but a human still edits the line. The Copr API token (repo secrets + `~/.config/copr`) expires **23 Feb 2027**; the channel is live now, so the answer at the expiry alert is RENEW.

**The SRPM job's architecture is not the chroot's, and is not stable.** Copr
schedules the `make_srpm` stage wherever it likes: 0.28.0's ran on x86_64,
0.29.0's ran on **aarch64** against the same fedora-43-x86_64 chroot, and
`pip wheel` — which builds for whoever runs it — produced a `linux_aarch64`
wheelhouse. Pure-Python wheels are arch-agnostic and resolved fine, so the
failure surfaced inside mock as `Could not find a version that satisfies the
requirement pyyaml>=6.0 ... (from versions: none)` — the first dependency with
a compiled extension, and a message that names nothing about architecture.
**`from versions: none` rather than a version conflict is the tell**: the
package is there and no wheel is *compatible*. Nothing in the tree had changed.
`rpm/make-srpm.sh` now pins with `pip download --platform manylinux_*_x86_64`
in two passes — `pysrt` is sdist-only on PyPI and `--only-binary=:all:` refuses
it, so it is built locally first, where being pure Python makes it
`py3-none-any` and correct for every arch — and asserts afterwards that no
foreign-arch wheel reached the wheelhouse (`musllinux` named explicitly, being
x86_64 with the wrong libc). The fix is proven, not merely green: the rebuild
landed on aarch64 again and produced x86_64 wheels. **And verifying a Copr publish has
two ways to read as "the build produced nothing", both false.** The result
directory lists **no `.rpm` at all** — Copr stopped putting them there, and the
known-good previous build is the control that proves it is normal, not a defect;
the authoritative records are `<build-dir>/results.json` and the repo metadata
under `repodata/`, which is what a `dnf` client actually reads. And the listing
is served behind a redirect, so a `curl` without **`-L`** greps an empty
redirect body and reports no files, with no error. Confirm a publish by reading
`repomd.xml` → `primary.xml.gz` for the `<location href=...>` and then a `HEAD`
on the RPM itself — a build's own `succeeded` flag is not evidence the artefact
is fetchable.

**Still owed from 0.27.0:** the Catalan native pass (owned, a few weeks out — no release waits on it, since nine other locales ship machine-seeded pending review). The Welcome AI cell's hardcoded `Setup →` was **closed in `7f8f2645` + `89b11f5a`** and this line went on claiming it for days: the call site reads `i18n.t("desktop.welcome.aiSetup") + " →"`, the key is in all 21 full locales carrying Apple's own per-locale verb, and `zh-Hant-HK` is correctly absent because it inherits `zh-Hant`. Left as a worked example of the trap in Gotchas: **an owed item is a claim about the tree, exactly as a resolved one is** — verify by reading the line it names (`git log -S` on the string) before spending a cycle re-deriving finished work. **`v0.26.0` was tagged and abandoned** — it pointed 34 commits behind real work; it reached no channel and is in no changelog. Treat it as a version that never existed.

**Recent releases, in one line each** — **0.28.0** the Export-HTML button that worked only in the Mac app, and exported reports halved (3.38 → 1.55 MB) by embedding one language instead of 22; **0.25.0** the Sessions responsive grid and spatial arrow navigation; **0.24.0** Focus Mode and the single appearance seam (`AppAppearance.swift`); **0.23.0** the assistant surface end to end (`/mcp` on both channels, the `.mcpb` extension, Settings ▸ MCP Agents). Full entries in [CHANGELOG.md](CHANGELOG.md) — kept there rather than mirrored here, because a version history in two places is a version history wrong in one. React migration complete (Steps 1–10); bundled-sidecar desktop is the primary distribution path; CLI ships on PyPI + Homebrew + Snap + Fedora Copr. Static render is a sealed byproduct.

See [CHANGELOG.md](CHANGELOG.md) for version history, [TODO.md](TODO.md) for active work, and `git log` for the unabridged story.
