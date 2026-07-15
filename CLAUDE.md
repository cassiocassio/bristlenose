# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Claude (Anthropic), ChatGPT (OpenAI), Azure OpenAI (enterprise), Gemini (Google), or local models via Ollama (free, no account required).

## Commands

- `.venv/bin/python -m pytest tests/` — run tests
- `.venv/bin/ruff check bristlenose/` — lint (no global ruff install)
- `.venv/bin/ruff check --fix bristlenose/` — lint and auto-fix
- `.venv/bin/mypy bristlenose/` — type check (informational, not a hard gate)
- `cd e2e && npm test` — Playwright E2E tests (layers 1–3: console, links, network; Chromium + WebKit)

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Bump semantics — minor = feature, patch = fix.** A release that adds *any* user-facing feature bumps the **minor** (`0.20.0 → 0.21.0`); a release that's purely bug-fixes bumps the **patch** (`0.20.0 → 0.20.1`). Feature-bearing releases advance the minor fast — that's fine and expected pre-1.0. **Do not** let features accumulate under a long patch run: the 0.15.0 → 0.15.19 line (nineteen patches, many carrying real features) was a mistaken habit, not the convention. When unsure, ask "does this add a capability?" — yes → minor.
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`. Use `./scripts/bump-version.py` to bump (updates `__init__.py`, man page, creates git tag). **The tag is created immediately on current HEAD — before the bump commit lands.** That means it points at the wrong commit until you delete and re-tag after committing. Standard flow: write CHANGELOG + README first, run `bump-version.py`, `git tag -d v<X.Y.Z>`, stage everything (`CHANGELOG.md README.md` + the three version files the script staged), commit, `git tag v<X.Y.Z>`, push branch then tag separately
- **Markdown style template** in `bristlenose/utils/markdown.py` — single source of truth for all markdown/txt formatting. Change formatting here, not in stage files
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates (see `bristlenose/theme/CLAUDE.md`)
- **Licence**: AGPL-3.0 with CLA
- **Provider naming**: user-facing text says "Claude", "ChatGPT", and "Azure OpenAI" (product names), not "Anthropic" and "OpenAI" (company names). Researchers know the products, not the companies. Internal code uses `"anthropic"` / `"openai"` / `"azure"` as config values — that's fine, only human-readable strings need product names
- **CLI plurals**: any count-bearing CLI string uses `count_noun(n, "singular")` from `bristlenose/utils/text.py` — wraps `inflect.engine().plural_noun()`, so irregulars (`child`→`children`, `person`→`people`, `boundary`→`boundaries`) and compound nouns (`"topic boundary"`→`"topic boundaries"`) work automatically. Don't hand-roll `f"{n} thing{'s' if n != 1 else ''}"` or add a sibling helper next to `count_noun`. Pass `plural=` explicitly only when inflect's default disagrees (rare). CLI is English-only in alpha; the React SPA + desktop use i18next CLDR plurals via `t(key, count=n)` — different surface, different mechanism, don't conflate. The Python-side `t()` under `bristlenose/locales/preflight.json` doesn't support CLDR plurals yet; when/if CLI gets localised post-alpha, `count_noun` grows a CLDR-aware path
- **Changelog version/date format**: `**X.Y.Z** — _D Mon YYYY_` (e.g. `**0.8.1** — _7 Feb 2026_`). Bold version, em dash, italic date. No hyphens in dates, no leading zero on day. Used in both `CHANGELOG.md` and the changelog section of `README.md`
- **The React SPA is the product; the Jinja2 static renderer (`bristlenose/stages/s12_render/`) is a deprecated sealed byproduct.** Rules: (1) New features and design changes go to the React SPA only. (2) Offline sharing = open in serve mode → **Export HTML** toolbar button (embeds the React bundle + JSON; never calls `s12_render/`). (3) **Serve mode never falls back to static render** — if the SPA is missing from the bundle, `_mount_prod_report` returns a fail-loud 500, not the static HTML (that fallback masked BUG-3). (4) CSS in `bristlenose/theme/` is shared with the static render incidentally; design intent lives in `frontend/`. (5) Vanilla JS in `bristlenose/theme/js/` is frozen — data-integrity fixes only. Future direction (repurpose `--static` as a markdown deliverable): `docs/design-cli-improvements.md` §Future direction.

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls), `serve` (local dev server), `status` (read-only project state from manifest), `doctor` (dependency health checks). **Default command**: `bristlenose <folder>` is shorthand for `bristlenose run <folder>` — if the first argument is an existing directory (not a known command), `run` is injected automatically.

Serve mode: FastAPI + SQLite + React SPA. See `bristlenose/server/CLAUDE.md` for architecture.

Desktop app: `desktop/` — SwiftUI macOS shell. Alpha ships a bundled, signed PyInstaller sidecar running `bristlenose serve`, distributed via internal TestFlight. v0.2 currently uses launcher-style scaffolding (dev-only, not shippable). See `docs/archive/design-desktop-app.md` for the overall app design, `docs/design-modularity.md` for cross-channel component decisions (CLI ≡ macOS Python code; packaging differences only), and `docs/private/road-to-app-store.md` for the 14-checkpoint path to TestFlight.

Frontend: `frontend/` — Vite + React + TypeScript + React Router. See `frontend/CLAUDE.md` for gotchas and architecture.

Export: DOM snapshot from serve mode (self-contained HTML). See Key conventions for the static-render deprecation rules.

LLM providers: Claude, ChatGPT, Azure OpenAI, Gemini, Local (Ollama). See `bristlenose/llm/CLAUDE.md`.

Quote exclusivity: **every quote appears in exactly one report section.** See `bristlenose/stages/CLAUDE.md`.

Analysis page: `bristlenose/analysis/` — signal concentration metrics, pure math. Uses plain dataclasses (not Pydantic). Cell keys use `"label|sentiment"` format. See `docs/design-analysis-future.md`.

LLM prompts: Markdown files in `bristlenose/llm/prompts/`. Archive old versions to `bristlenose/llm/prompts-archive/`. See `bristlenose/llm/CLAUDE.md`.

Report JavaScript: 17 modules in `bristlenose/theme/js/`. See `bristlenose/theme/js/MODULES.md`.

Video thumbnails: `bristlenose/utils/video.py` — auto-extracted keyframes per session. See `docs/design-html-report.md`.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. Override with `--output`. See `bristlenose/stages/CLAUDE.md` for the full directory layout.

Key helpers: `OutputPaths` in `output_paths.py` (consistent path construction), `slugify()` in `utils/text.py` (project names in filenames — lowercase, hyphens, max 50 chars). Report filenames include project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`, `frontend/`, `desktop/`
- **Design artifacts** (tracked, not shipped): `docs/mockups/`, `docs/design-system/`, `experiments/` — HTML mockups, style guides, throwaway prototypes. These are working materials for contributors, kept in the tree for backup and collaboration. Users never navigate to them. Add new mockups to `docs/mockups/`, not the repo root. **Serve mode auto-discovery**: `bristlenose serve --dev` mounts all three directories and auto-discovers `*.html` files for the Design section in the About tab (`_build_dev_section_html()` in `app.py`). New HTML files added to these directories appear automatically — no code changes needed. **`experiments/` is excluded from `ruff check`** (per `pyproject.toml`) — throwaway research scripts don't need to pass lint; don't waste cycles fixing F401 unused-imports in there
- **User manual** (rendered to bristlenose.app/manual.html): `docs/manual.md` — authoritative source for the manual page on the marketing site. Edit here; deploy step in the website repo renders it to HTML. PRs welcome (typo fixes, clarifications, eventual translations).
- **Marketing site** (deployed, separate private repo): the marketing site, server-side ops endpoints, deploy script, and ancillary publishing/PR assets live in a separate private deploy repo on the maintainer's machine. The deploy script reads `docs/manual.md` from this public repo and renders it alongside the marketing content. **Note:** the rsync deploy needs SSH agent access and is run manually by the maintainer
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`
- **Gitignored (private)**: `docs/private/`, `trial-runs/` — contain names, contacts, strategy, pricing, legal drafts, and value judgements that don't belong on the public repo. Local-only, backed up by a separate code-backup script, never committed to git. Do not suggest `git add -f` for files here. Conceptually these belong in the founder-only private repo and migrate there at TestFlight cutover (see `project_private_docs_migration_plan.md` memory).

## Deployment targets

Bristlenose runs on three targets: macOS arm64 (primary dev), Linux x86_64 via GitHub Actions CI (release pipeline), and — newly — Claude Code Cloud VMs (ephemeral Ubuntu x86_64,  but reachable when the user picks Cloud in the picker). Cloud is useful for code/test/lint/frontend-build work, **not** for pipeline runs on private interview data. See `docs/design-deployment-targets.md for the audit checklist and use-case boundary table.

## HTML report features

The generated HTML report has interactive features: inline editing (quotes, headings, names), search-as-you-type, view switching, CSV export, tag filter, hidden quotes, and per-participant transcript pages with deep-linked timecodes. Full implementation details in `docs/design-html-report.md`. Key concepts: people file merge strategy, speaker codes, anonymisation boundary, tag filter persistence, hidden quotes with `.bn-hidden` defence-in-depth. See `bristlenose/theme/CLAUDE.md` for CSS/design gotchas, `bristlenose/theme/js/MODULES.md` for JS module details, `bristlenose/theme/CSS-REFERENCE.md` for per-component CSS docs.

Doctor command: `bristlenose doctor` — runtime environment checks. See `docs/design-doctor-and-snap.md`.

Snap + man page: see `docs/design-doctor-and-snap.md` and `docs/release.md`. **`man/bristlenose.1` is a symlink to `bristlenose/data/bristlenose.1`** — single source of truth. Edit either; both update. Validate with `mandoc -Tlint bristlenose/data/bristlenose.1` (macOS-default; `groff` / `nroff` aren't installed). `bump-version.py` refreshes both the version and the `.TH` ISO date on every bump (don't write "March 2026"-style human dates in `.TH` — they bitrot and produce mandoc WARNINGs).

CLI output: Cargo/uv-style checkmark lines with per-stage timing. Time estimation via Welford's algorithm in `bristlenose/timing.py`. See `bristlenose/stages/CLAUDE.md` for pipeline runtime details.

## Gotchas

### Ruff F401 (unused imports) — reports only, won't auto-fix

F401 is marked `unfixable` in `pyproject.toml` so `ruff check --fix` (and the PostToolUse hook) won't delete imports during incremental edits. Ruff still *reports* unused imports — remove them manually when they're genuinely unused.

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

### AppleDouble files on external drives

When macOS copies files to a filesystem that can't store xattrs/resource forks natively (ExFAT, FAT32, SMB shares, some NFS exports), Finder creates a `._<name>` sidecar alongside every user file to carry the metadata. These are **binary blobs that share the user file's extension** — `._foo.mp4` looks like a video to anything that classifies by suffix; `._s1.txt` looks like a transcript and crashes utf-8 decode (`UnicodeDecodeError: byte 0xb0`).

Any directory scanner that walks a user-supplied folder must filter these. Use `is_os_metadata(path)` from `bristlenose/utils/fs.py` — it catches `._*` AND `.DS_Store`. Already applied at `discover_files` (s01_ingest), `load_transcripts_from_dir` (pipeline.py), and the server importer scan sites. **When adding a new scan site that walks a project folder, call `is_os_metadata` first.** The Swift `ProjectFolderWatcher` already filters via `.skipsHiddenFiles` + `name.hasPrefix(".")`.

### i18n — single source of truth

- **Locale files live in `bristlenose/locales/` only** — `frontend/src/locales/` was deleted. The frontend imports via Vite alias `@locales`. Don't create locale files in the frontend tree. `I18n.swift` (desktop) reads the same JSON at runtime
- **`useTranslation()` is the hook; `i18n.t()` is the direct import** — use the hook inside React components; use `import i18n from "../i18n"` + `i18n.t()` in stores, announce utilities, and other non-component code
- **New keys must go in every locale directory** — currently 21: en, es, ja, fr, de, ko, cs, it, pl, ru, uk, da, sv, nb, tr, nl, fi, pt-BR, pt-PT, zh-Hant, zh-Hant-HK (pl/ru/uk/da/sv/nb/tr/nl/fi are machine-seeded, pending native review). **`zh-Hant-HK` is the one exception — a thin *override* fork, not a full locale:** it carries only genuine HK-idiom differences (e.g. `軟件` vs Taiwan `軟體`) and inherits everything else via the deliberate `zh-Hant-HK → zh-Hant → en` fallback (spec: `docs/design-i18n.md` §"the Traditional pair"). **Do NOT add ordinary new keys to it** — absent = inherits `zh-Hant`; an English placeholder there would pin it and *break* that inheritance once `zh-Hant` is translated. So "every locale directory" means the 20 full locales; HK gets only real HK overrides. Every `t("key")` call needs an entry in each of the 20. If using `dt()`, the desktop override must also go in each `desktop.json`
- **Adding a whole new language = 9 JSON files + 9 registration sites across THREE surfaces (web, Python, native Swift).** Create `bristlenose/locales/<code>/` with all 9 namespace files (`common, cli, desktop, doctor, enums, pipeline, preflight, server, settings`), then register the code in all of:
  - **Web/Python (6):** `SUPPORTED_LOCALES` in [frontend/src/i18n/index.ts](frontend/src/i18n/index.ts) **and** [bristlenose/i18n.py](bristlenose/i18n.py); the `expected` set in [bristlenose/doctor.py](bristlenose/doctor.py) (`Bundle: locales` check); the `LOCALE_LABELS` map in **both** [SettingsPanel.tsx](frontend/src/islands/SettingsPanel.tsx) and [SettingsModal.tsx](frontend/src/components/SettingsModal.tsx) (native name, e.g. `it: "Italiano"`); and the mock list in [LocaleStore.test.ts](frontend/src/i18n/LocaleStore.test.ts).
  - **Native Swift desktop (3) — EASY TO MISS, the desktop Settings window has its OWN picker, NOT the React one:** `supportedLocales` in [desktop/Bristlenose/Bristlenose/I18n.swift](desktop/Bristlenose/Bristlenose/I18n.swift); the `Picker` `Text("…").tag("…")` list in [AppearanceSettingsView.swift](desktop/Bristlenose/Bristlenose/AppearanceSettingsView.swift); and the `expected` set in [I18nTests.swift](desktop/Bristlenose/BristlenoseTests/I18nTests.swift). The desktop reads the locale JSON from the bundle via `Bundle.main` (the xcodeproj `Copy Sidecar Resources` phase rsyncs all of `bristlenose/locales/`, so the data ships automatically — only the Swift code lists above need the edit). A plain Cmd+R self-heals the sidecar (touching `bristlenose/locales/` moves the freshness fingerprint).
  - The web runtime loader needs NO edit — it's a Vite dynamic-import glob (`import(\`.../locales/${locale}/${ns}.json\`)`), so files are picked up automatically. Lazy locale chunks are **excluded from the bundle-size budget** (the `size-limit` glob negates `common-*`/`settings-*`/`desktop-*`/`enums-*`/etc.), so a new language is size-neutral on the web bundle.
  - Register Apple-HIG + QDA terms for the language in `bristlenose/locales/glossary.csv` so Weblate shows translators the agreed taxonomy. Translate in the language's **Apple-HIG register** (imperative for buttons/commands, impersonal for body text — match the platform, don't invent a register). If `pluralCategory` in `I18n.swift` doesn't handle the language explicitly, it falls through to the `one`/`other` default (correct for it/es/de; check CLDR for others).
- **Platform text forking** — `dt(t, key)` checks `desktop:` namespace first (falls back to base key). `ct(t, key)` returns `null` on desktop (hides CLI-only text). Both in `frontend/src/utils/platformTranslation.ts`. See `docs/platform-text-map.md`
- **SwiftUI `CommandMenu` titles can't use runtime strings** — menu titles stay in English; only items inside are translated
- **The pipeline-view CLI keeps its own English mirror of `pipeline.*` strings — keep both in sync.** `bristlenose/pipeline_view/cli.py` is i18n-free (CLI is English-only in alpha), so it hardcodes `_REASON_TEXT` / `_NOTE_TEXT` / `_PROVIDER_DISPLAY` dicts keyed by the *same* `pipeline.reasons.*` / `pipeline.quality.*` keys the locale JSON uses. Editing a reason/note/provider string in the locales but not the CLI dict (or vice versa) silently diverges the CLI and React surfaces for the same host condition. Bit twice in v2: anonymisation reason ("spaCy en_core_web_lg not installed" CLI vs "language model not installed" locale) and the untested note. When you touch a `pipeline.*` string, grep `cli.py` for the same key and update both.
- **Don't round-trip locale JSON through `json.load`/`json.dump` to add a key.** The 7 `common.json` files mix literal Unicode (`…`, `—`) with `\u` escapes (mostly in non-ASCII locales). `json.dump(ensure_ascii=False)` rewrites every `\u` → literal; `ensure_ascii=True` rewrites every literal → `\u`. Either way you get a 1000-line diff for a 2-line change. Use a targeted text replace (find an anchor unique to each locale — `}\n  },\n  "feedback":` works for inserting at end of `export`) and `json.dumps(value, ensure_ascii=True)` per-value to escape only the new strings. **Repeat-pass corollary:** when a second pass replaces a value inserted by an earlier pass (e.g. fixing ja `やり直す` → `取り消す`), the in-file form is the `\u` escape because the first pass used `ensure_ascii=True`. A literal Japanese match-string won't find it. Re-encode the match string via `json.dumps(..., ensure_ascii=True)` before `text.replace(...)`

See `docs/design-i18n.md` for implementation gotchas (Apple glossary cross-check, `useMemo` deps, sentiment tag translation, Intl.DateTimeFormat quirks, Korean plurals, data vs chrome translation, German typographic quote JSON escaping, test mocking requirements).

### Other gotchas

- **Rich's `console.print()` eats `[name]` as markup tags.** Square-bracket sequences are parsed as Rich style markup; unknown style names (e.g. `[serve]`, `[apple]`) are silently consumed, so `pip install bristlenose[serve]` renders as `pip install bristlenose`. Two fixes by site type: (1) plain-text output (doctor fix messages, log lines) → `console.print(text, markup=False)`; (2) sites with intentional Rich markup interpolating user-supplied text → `from rich.markup import escape; console.print(f"[bold]{escape(value)}[/bold]")`. Audit any new `console.print` that interpolates package-spec / file-glob / version-range text
- **E2E allowlists must be registered.** Every `if (...) return;`-style suppression inside a Playwright spec (e.g. "this 404 is expected") needs (a) a matching entry in `e2e/ALLOWLIST.md` and (b) a `// ci-allowlist: CI-A<N>` comment marker above the code. Categories: `infra` (stack artefact, never fixable) / `by-design` (intentional correct behaviour) / `deferred-fix` (real bug, must link to 100days.md tracker). Prevents the e2e gate from accumulating silent suppressions nobody can audit six months later. See the register header for schema, retired IDs, and v2 tooling (validator + staleness gate, deferred until ~10 entries).
- **PyInstaller bundle datas: source dir present ≠ bundle dir present.** Non-`.py` runtime files (YAML, JSON, Markdown, JS, CSS, etc.) only ship if they're in `desktop/bristlenose-sidecar.spec`'s `datas=[...]` list. Python packages get bytecompiled into `base_library.zip` automatically; data files don't. Two gates catch this class: `desktop/scripts/check-bundle-manifest.sh` (source→spec, ~60ms, runs in `build-all.sh` step 1b) and `bristlenose doctor --self-test` (spec→bundle, ~2-3s, runs in step 2a). The source→spec gate is per-file: each runtime file must be matched by a datas entry that's the file itself or a directory ancestor — so single-file `(file_path, parent_dir)` entries are accepted alongside whole-directory ones. Unit tests can't catch this — they run against `pip install -e .` where data files live at their real paths
- **`from __future__ import annotations` doesn't satisfy ruff F821 if the annotated name isn't imported.** Type annotations become strings at runtime, but ruff's F821 still validates that the name is reachable in the module scope. So `def foo() -> Path:` with a per-function `from pathlib import Path` inside the body fails F821. Move the import to top-of-file
- **E2E tests: stale server on port 8150 gives wrong results** — `playwright.config.ts` uses `reuseExistingServer: !process.env.CI`. If a previous `bristlenose serve` is running locally on port 8150 (e.g. from `bristlenose serve trial-runs/project-ikea`), Playwright silently connects to it instead of starting the smoke-test fixture. This produces completely wrong measurements (353 quotes instead of 4). Always check `lsof -i :8150` before running E2E tests locally. In CI this can't happen (`reuseExistingServer: false`). The perf-gate spec has a server identity guard (`project_name === "Smoke Test"`) to catch this
- **E2E Node-side `fetch()` needs auth token explicitly** — Playwright's `extraHTTPHeaders` only applies to browser contexts (page navigation). Node-side `fetch()` in test fixtures gets 401'd without the bearer token. `e2e/fixtures/routes.ts` reads `_BRISTLENOSE_AUTH_TOKEN` from env and passes it via `authHeaders()`. Set the env var when running E2E tests: `_BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test`
- **E2E: `waitForLoadState('networkidle')` is too fragile for SPAs** — fires after a 500ms idle window, which can beat deferred `useEffect` mounts on slow CI runners. Missed nodes look like "passed" tests and you measure the wrong state. In `perf-gate.spec.ts` the pattern is a `waitForPageReady()` helper that chains: `networkidle` → wait for `#bn-app-root` children → wait for `document.querySelectorAll('*').length` to be stable across two 200ms polls. Copy this pattern for any E2E spec that measures DOM state
- **E2E: in-browser `fetch()` in `page.evaluate` can silently 401** — a dropped auth token turns into 1ms latency and a ~50-byte error body. Without `res.ok` assertions this registers as "excellent latency" and sails past size thresholds. Always assert `res.ok` inside the evaluate (`expect(ok).toBe(true)`) AND add a sanity floor for payload sizes (`expect(sizeBytes).toBeGreaterThan(500_000)` when real size is ~1.6 MB). The server identity guard (first test, serial mode) catches most cases but defence-in-depth matters
- **Export JSON: always `ensure_ascii=True`** — `json.dumps(ensure_ascii=False)` does NOT escape `</script>` inside `<script>` tags. This is an XSS vector. The export endpoint embeds data as JSON in a script block — `ensure_ascii=True` escapes `<` as `\u003c`, preventing breakout
- **Export filenames: use `safe_filename()` not `slugify()`** — `slugify()` lowercases and hyphenates (`"Acme Research"` → `"acme-research"`). `safe_filename()` preserves spaces and case for human-readable Finder names. Both are in `bristlenose/utils/text.py`. Use `safe_filename()` for all export naming (zip folders, transcript files, clip files, download filenames)
- **Tests must not depend on local environment** — CI runs with no API keys, no Ollama, no local config. Always mock environment-dependent functions. The v0.6.7–v0.6.13 release failures were caused by tests that passed locally but failed in CI
- **PII redaction: `model_copy()` is shallow** — when redacting transcript segments, `seg.model_copy()` copies the Pydantic model but `words` (a list of `Word` objects) still references the original unredacted words. Always clear `clean_seg.words = []` after replacing `clean_seg.text`. Same caution applies to any field that might contain PII (`speaker_label`, `source_file`)
- **PII summary is a re-identification key** — `pii_summary.txt` lists every original PII value with timecodes. It lives in `.bristlenose/` (hidden), NOT in the shareable output root. Never move it back to the output directory
- **LLM call log is a re-identification key** — `<output_dir>/.bristlenose/llm-calls.jsonl` carries session ids, prompt shas, and timing fingerprints (sibling to `pii_summary.txt`). Never include in any export, support bundle, or shareable archive. Mode `0o600` + `O_NOFOLLOW` enforced by `bristlenose/llm/telemetry.py`. Kill switch: `BRISTLENOSE_LLM_TELEMETRY=0`
- **`pii_score_threshold` is the only PII config that's wired** — `pii_llm_pass` and `pii_custom_names` are declared in `config.py` but not used by `s07_pii_removal.py`. They emit runtime warnings when set. Don't write code that reads them without implementing the feature first
- **Presidio slow tests need spaCy model** — `@pytest.mark.slow` tests in `test_pii_audit.py` require `presidio-analyzer` + `spacy` + `en_core_web_lg` (400MB download). They're skipped in CI. Run with `pytest -m slow`
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only
- **Auditing CLI flag deletion: grep Swift call sites too.** A3 deleted `--static` from `bristlenose run` because the static-render naming was a conflation — but the same Typer option was aliased as `--no-serve` and the macOS sidecar's `PipelineRunner.swift:957` was passing it to suppress auto-serve so Swift's ServeManager can manage the serve port separately. Deleting both spellings broke the desktop alpha path. Caught during the doc-sweep verification before any cohort tester saw it; restored as `--no-serve` (without the misleading `--static` alias). Rule for future: when deleting a CLI flag, `grep -rn '"--<flag>"' desktop/` *before* the Python edit, not after. Aliases are typically there because two semantically-distinct concerns share a single option declaration — separate the concerns at deletion time, don't just drop both names. **This extends to whole commands, and to CI workflows as a call site.** `bristlenose render` was removed (`7258cdb`) but `.github/workflows/install-test.yml` kept invoking it at four job sites, reddening `Install & Smoke Test` on every run for ~11 days (24 May–4 Jun 2026) — and it went unnoticed because the machine-local CI monitor (`~/.claude/scripts/ci-status-check.sh`) was watching a stale workflow `name:`. When deleting a CLI command or flag, `grep -rn` **both** `desktop/` **and** `.github/workflows/` before the Python edit
- `doctor.py` imports `platform` and `urllib` locally inside function bodies (not at module level). When testing, patch at stdlib level (`patch("platform.system")`) not module level
- `check_backend()` catches `Exception` (not just `ImportError`) for faster_whisper import — torch native libs can raise `OSError` on some machines
- **Never remove a worktree from inside it.** Always `cd /Users/cassio/Code/bristlenose` first, then `git worktree remove ...`. See `docs/BRANCHES.md`
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
- **Cloud session, no `gh` CLI — use the GitHub MCP for PR + merge.** When the user asks for a merge from a cloud env, the path is `mcp__github__create_pull_request` then `mcp__github__merge_pull_request` (load via ToolSearch with `select:` query). The MCP repo scope is restricted per the system prompt (`cassiocassio/bristlenose` only) — calls to other repos are denied. After merging from cloud, the version tag should be created from the dev machine (`git tag v<X.Y.Z> <merge-sha>`) before pushing to PyPI — `scripts/bump-version.py` is designed for the local dev flow and tags HEAD-before-commit, which doesn't fit the cloud → PR → merge path
- **Release-to-PyPI workflow doesn't always fire on tag push via `--tags`** — `git push origin main --tags` triggers the branch-push workflows (CI, CodeQL, Snap) but the tag-driven `Release to PyPI` workflow can silently miss the event. Workaround: `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` — same SHA, fresh trigger, semantic no-op. Root cause appears to be GitHub Actions debouncing tag-push events bundled with branch-push events. Future fix: add `workflow_dispatch:` to `release.yml` so it can be re-triggered without tag surgery
- **A failed release run and a release run that never fired need different fixes — don't reach for the tag-redelivery workaround reflexively.** Two distinct failure modes: (1) the workflow *never fired* (debounce) → the `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` redelivery above. (2) the workflow *fired and a job failed* (e.g. e2e stalled on the Playwright browser CDN) → NOT a redelivery case. Critically, **`gh run rerun <id> --failed` replays the *tagged commit*, not `main`'s latest** — so if a later commit on `main` already fixed the failing step, re-running the old run just fails again on the unfixed code. The fix is to move the tag to the fixed commit (`git tag -f v<X.Y.Z> <fixed-sha> && git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`), which triggers a fresh run on the fix. Diagnose first with `gh run view <id>` (did it fire? which job failed?) before choosing. Worked example 4 Jun 2026: v0.15.13's run failed on the e2e Playwright-browser CDN stall; a `--failed` rerun of the stale-commit run failed identically, while moving the tag to `14af414` (which bumped `@playwright/test` 1.59.1→1.60.0 to fix the chromium-install hang on Node 24) published cleanly. Ground truth is always `curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version`, not the run's conclusion
- **Subprocess signal-handling tests: poll the events file, don't `proc.wait`** — `tests/test_run_lifecycle.py` originally used `proc.wait(timeout=15)` after sending SIGINT, then asserted on the cancel event. Failed on Python 3.10 / ubuntu-latest only — slow runner, the lifecycle's `KeyboardInterrupt` catch + `Cause` build + fsync took longer than 15 s under matrix CPU contention. Pattern that works: `_wait_for_event(f, predicate, timeout=120)` polling the events file, with `proc.wait(timeout=10)` only in the `finally` for cleanup. Monotonic against runner load. See `tests/test_run_lifecycle.py:_wait_for_event`. 120s is defensive but the underlying test parks on a `time.sleep(60)` subprocess body — refactor to event-driven start signal would be cheaper than the next doubling
- **CI `test` job doesn't `npm run build` the frontend** — `bristlenose/server/static/` is empty in pytest CI, so `_mount_prod_report` returns the C3 fail-loud "Build incomplete" 500 page instead of an SPA HTML response. Any new pytest test that hits a `/report/*` route in prod mode (`create_app(..., dev=False)`) fails with `AssertionError: …Build incomplete…`. Two ways out: (1) build the frontend in CI test job (~30-60s/cell — recommended long-term); (2) use the existing `prod_app_factory` pattern in `tests/test_server_status_page.py` which monkeypatches `_STATIC_DIR` to a tmp dir containing a synthetic Vite-shaped `index.html` with `<div id="bn-app-root">`. **`dev=True` on `create_app` does NOT route to `_mount_dev_report`** — mount selection reads the `_BRISTLENOSE_DEV` env var (named `hmr` inside `create_app`), not the `dev=` param. Setting `dev=True` only enables playground/admin/debug-500 features; for the dev mount you'd need to set env-var before calling. Use the `_STATIC_DIR` monkeypatch instead
- **CI fires on push-to-main and pull_request-to-main only, not on feature branch pushes** — `.github/workflows/ci.yml` `on:` block has no `push.branches: [<feature>]`. Pushing to a non-main branch updates origin but triggers nothing. To get CI signal before merging, open the PR. (Counter-intuitive coming from projects that run CI on every branch push.) `release.yml` fires only on `push.tags: ["v*"]`
- **Smoke fixture must include a `pipeline-events.jsonl` with a `RunCompletedEvent`** — `tests/fixtures/smoke-test/input/bristlenose-output/.bristlenose/pipeline-events.jsonl` carries a hand-crafted terminus event so `app.state.last_run[1]` populates on server startup, so `status_page.detect_status` returns `None`, so `/report/*` falls through to the SPA mount. Without it the server-rendered status page intercepts ("Nothing to see here, yet.") and every SPA-based test against the fixture fails on `#bn-app-root` being absent. Run_id and timestamps are stable strings — don't regenerate them on whim, or perf-history will see git-noise as a perf change. Regression-pinned by `tests/test_server_status_page.py::TestSmokeFixtureMountsSPA` + `e2e/tests/spa-mounts.spec.ts`. **Any new test fixture that boots `bristlenose serve` against it inherits this contract** — give it a terminus event or the SPA never mounts. **This committed `.bristlenose/` dir LOOKS like runtime detritus but is a deliberate contract — don't delete it or assume the gitignore should swallow it.** Everywhere else `.bristlenose/` is a per-run state dir (db, log, llm-calls.jsonl) carrying re-identification keys and is gitignored; this one fixture is the sole tracked exception, re-included via a surgical negation in `.gitignore` (the dir + `pipeline-events.jsonl` + `intermediate/*.json` are tracked; logs/db stay ignored even inside it). If a future cleanup proposes synthesizing it at test-time, that's a legitimate option — but until then, keeping it committed is the intended resting state (7 Jun 2026)
- **Test-only fixes re-use the existing tag; they don't bump the version** — when a fix touches only `tests/`, `e2e/`, fixtures, `CLAUDE.md`, `docs/`, `.claude/` agent tooling, `.github/`, or workflow files (anything excluded from the sdist/wheel — the wheel ships only `bristlenose/` per `[tool.hatch.build.targets.wheel] packages`, and the sdist `exclude`s `.claude/`), the shipped wheel is byte-identical with or without the fix. This covers whole *features* that live outside `bristlenose/` (e.g. the Cassandra agent + `/cassandra` skill + dependency register, 5 Jun 2026) — "new in the repo" ≠ "new in the package"; the version labels the PyPI/Homebrew/Snap artifact, not git state. Re-use the existing tag by force-moving it to the fix-merge SHA (`git tag -f v<X.Y.Z> <merge-sha>`) and re-pushing (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`). Don't bump to <X.Y.Z+1> — adds bookkeeping (CHANGELOG entry, README snippet, homebrew tap dispatch) for no semantic gain and forks the version line for cosmetic reasons. Counter-rule: PyPI immutability — if the version ever successfully published, you can't re-upload, and a bump IS required. Verify with `curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version` before deciding

## Reference docs (read when working in these areas)

**Must-read before writing user-facing text:**
- `docs/glossary.md` — terminology + tone guide
- `docs/platform-text-map.md` — shared/desktop/CLI text forking, `dt()`/`ct()` inventory

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
- `docs/design-pipeline-resilience.md` — manifest, event sourcing, resume, provenance
- `docs/design-pipeline-diagnostic-popover.md` — **read before adding any new error / status / message that surfaces in the popover, the pill, the sidebar glyph, or any toast.** Five-kind `MessageKind` taxonomy (`bristlenose/ui_kinds.py`), length budgets, anti-patterns, flowchart for fitting new messages into the existing vocabulary instead of inventing new glyphs/colours
- `docs/design-platform-transcripts.md`, `docs/design-transcript-coverage.md`
- `docs/design-speaker-splitting.md`, `docs/design-speaker-role-detection.md`
- `docs/design-speaker-editing.md`, `docs/design-transcript-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md`
- `docs/design-multi-project.md` — scope rules (instance vs project tables)
- `docs/design-session-management.md`
- `docs/design-logging.md`

**Export:**
- `docs/design-export-html.md` (anonymisation), `docs/design-export-quotes.md` (CSV/XLS), `docs/design-export-clips.md`, `docs/design-export-slides.md`, `docs/design-miro-bridge.md`, `docs/design-footer-feedback-react.md`

**Desktop:**
- `docs/archive/design-desktop-app.md`, `docs/design-desktop-security-audit.md`
- `docs/design-modularity.md` — **canonical cross-channel component strategy** (CLI + macOS, Background Assets, no-fork principle, trickle-to-full-capability)
- `docs/design-desktop-python-runtime.md` — Mac sidecar mechanics
- `docs/private/road-to-app-store.md` — current Apple-side gate sequence (Sprint 2 plan archived; see 100days.md for live plan)
- `docs/design-project-sidebar.md`, `docs/design-wkwebview-messaging.md`
- `docs/design-desktop-menu-actions.md`, `docs/design-desktop-settings.md`

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
- **`docs/testing/README.md` — the testing & acceptance hub (start here for anything test/QA/acceptance).** Three-tier model (CI · Playwright · acceptance matrix · human walk), `docs/testing/coverage-inventory.md` (the single source of surfaces: 16 formats · 5 exports · 5 lenses · 5 providers), `docs/testing/acceptance-matrix.md` (mechanical tier, Phase-1 plan), `docs/testing/test-data-generation.md` (fixture recipe). Built already: `tests/test_no_fake_success_acceptance.py` (skips without fixtures) + `e2e/`. The by-hand walk lives in the private QA doc.
- `docs/design-ci.md`, `docs/archive/design-test-strategy.md`, `docs/design-playwright-testing.md`, `docs/design-test-philosophy.md`
- `docs/design-doctor-and-snap.md`, `docs/design-homebrew-packaging.md`
- `docs/design-cli-improvements.md`, `docs/design-llm-call-telemetry.md`, `docs/design-performance.md`
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
```

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

Releases should land on GitHub after 9pm London time on weekdays to avoid pushing version bumps during working hours. Weekends are fine any time.

**Workflow (weekdays only):**
1. Work on `main` as usual — commit everything locally
2. Don't push to `origin/main` until after 9pm
3. To see work remotely before release (CI checks, another machine): `git push origin main:wip` — the `wip` branch doesn't trigger releases
4. After 9pm: `git push origin main --tags`

**Weekends:** Push any time — no restrictions.

**Override:** Just push if something is urgent. This is a guideline, not a gate.

**Why:** Avoids notifications during client working hours; batches releases into a predictable window.

### Post-push PyPI verification (mandatory)

A tag push that reaches GitHub is NOT the same as a release that reaches PyPI. The release pipeline silently stalled from v0.15.5 to v0.15.9 (five versions, ~6 days) because no step checked that PyPI actually accepted the upload. **After every `git push origin main --tags`, verify before declaring the release done:**

```sh
for i in $(seq 1 20); do
  sleep 90
  pypi=$(curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version)
  echo "[$i] PyPI: $pypi"
  [ "$pypi" = "<X.Y.Z>" ] && break
done
```

20 iterations × 90s = 30 minutes. Recent releases have run 23–25 minutes (v0.15.13: 25m41s, v0.15.14: 23m22s); the original 15-minute budget routinely expired during a normal release. If PyPI still reports the previous version after 30 minutes: `gh run view --workflow=release.yml` to check the workflow fired. Apply the v0.15.0 debouncing workaround (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`) if it didn't.

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

**Internal TestFlight since 14 Jul 2026** (v0.20.x line) — first build accepted by App Store Connect: **0.20.0 (2068)**, App-Sandbox + Hardened-Runtime + arm64-only, signed Apple Distribution. React migration complete (Steps 1–10); bundled-sidecar desktop is the primary distribution path; CLI ships on PyPI + Homebrew + Snap. Static render is a sealed byproduct, not a user-facing product. See [CHANGELOG.md](CHANGELOG.md) for version history, [TODO.md](TODO.md) for active work, and `git log` for the unabridged story.
