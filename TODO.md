# Bristlenose — Where I Left Off

Last updated: 30 Jan 2026

---

## Done (0.1.x)

- [x] Full 12-stage pipeline (ingest → render)
- [x] HTML report with CSS theme (v5), clickable timecodes, popout video player
- [x] Sentiment histogram (horizontal bars, side-by-side AI + user-tag charts)
- [x] Friction points, user journeys
- [x] Favourite quotes (star, reorder, FLIP animation, CSV export)
- [x] Inline quote editing (pencil icon, contenteditable, localStorage persistence)
- [x] Tag system — AI-generated badges (deletable with restore) + user-added tags (auto-suggest, keyboard nav), localStorage persistence, CSV export with separate AI/User columns
- [x] Atomic design system (`bristlenose/theme/`) — tokens, atoms, molecules, organisms, templates; CSS concatenated at render time
- [x] JavaScript extraction — report JS broken out of `render_html.py` into 8 standalone modules (`bristlenose/theme/js/`): storage, player, favourites, editing, tags, histogram, csv-export, main; concatenated at render time mirroring the CSS pattern; `render_html.py` reduced from 1534 → 811 lines
- [x] `bristlenose render` command — re-render reports from intermediate JSON without retranscribing or calling LLMs
- [x] Apple Silicon GPU acceleration (MLX)
- [x] PII redaction (Presidio)
- [x] Cross-platform support (macOS, Linux, Windows)
- [x] AGPL-3.0 licence with CLA
- [x] Renamed gourani → bristlenose
- [x] Published to PyPI (0.1.0)
- [x] Published to GitHub (cassiocassio/bristlenose)
- [x] Homebrew tap (cassiocassio/homebrew-bristlenose) — `brew install cassiocassio/bristlenose/bristlenose` works
- [x] README with install instructions (brew, pipx, uv)
- [x] CONTRIBUTING.md with release process and design system documented

---

## Next up: CI/CD automation

These are ready to implement. Do them in order — each builds on the previous.

### 1. CI on every push/PR (most valuable, do first)

GitHub Actions workflow: `.github/workflows/ci.yml`
- Run `ruff check .`
- Run `mypy bristlenose/`
- Run `pytest`
- Trigger on push to `main` and on pull requests

### 2. Publish to PyPI on tagged release

GitHub Actions workflow: `.github/workflows/release.yml`
- Trigger on push of `v*` tags
- Build sdist + wheel with `python -m build`
- Upload to PyPI using trusted publisher (no API token in secrets)
- Requires one-time setup: go to pypi.org/manage/project/bristlenose/settings/publishing/ and add a trusted publisher for the GitHub repo + workflow

### 3. Auto-update Homebrew tap after PyPI publish

GitHub Actions workflow in the **homebrew-bristlenose** repo
- Triggered by repository_dispatch from the main release workflow
- Fetches new sdist URL + sha256 from PyPI JSON API
- Patches `Formula/bristlenose.rb`
- Commits and pushes

### 4. GitHub Release with changelog

Add to the release workflow (item 2)
- After PyPI publish, create a GitHub Release on the tag
- Use auto-generated release notes (PR titles since last tag)

---

## Feature roadmap

Organised from easiest to hardest. The README has a condensed version; this is the full list.

### Trivial (hours each)

- [ ] Search-as-you-type filtering — filter visible quotes by text content
- [ ] Hide/show quotes — toggle individual quotes, persist state
- [ ] Keyboard shortcuts — j/k navigation, s to star, e to edit, / to search
- [ ] JS: `'use strict'` — add to each JS module to catch accidental globals and silent errors
- [ ] JS: shared `utils.js` — extract duplicated quote-stripping regex (`QUOTE_RE` / `CSV_QUOTE_RE`) into a shared module
- [ ] JS: magic numbers → config — extract `150`ms blur delay, `200`ms animation, `250`ms FLIP duration, `2000`ms toast, `8` max suggestions, `48`px min input into a shared constants object
- [ ] JS: histogram hardcoded colours — replace inline `'#9ca3af'` / `'#6b7280'` with CSS custom properties (`var(--bn-colour-muted)`) via classes or `getComputedStyle()`
- [ ] JS: drop `execCommand('copy')` fallback — `navigator.clipboard.writeText` is sufficient for all supported browsers; remove deprecated fallback or gate behind a warning

### Small (a day or two each)

- [ ] Theme management in browser — create/rename/reorder/delete themes in the report, dark mode, user-generated CSS themes (token architecture ready)
- [ ] Lost quotes — surface quotes the AI didn't select, let users rescue them
- [ ] Transcript linking — click a quote to jump to its position in the full transcript
- [ ] .docx export — export the report as a Word document
- [ ] Edit writeback — write inline corrections back to cooked transcript files
- [ ] JS: split `tags.js` (453 lines) — separate AI badge lifecycle, user tag CRUD, and auto-suggest UI into `ai-badges.js`, `user-tags.js`, `suggest.js`
- [ ] JS: explicit cross-module state — replace implicit globals (`userTags` read by `histogram.js`) with a shared namespace object (`bn.state.userTags`) or pass state through init functions
- [ ] JS: auto-suggest accessibility — add ARIA attributes (`role="combobox"`, `aria-expanded`, `aria-activedescendant`) so screen readers can navigate the tag suggest dropdown

### Medium (a few days each)

- [ ] Multi-participant sessions — handle recordings with more than one interviewee
- [ ] Speaker diarisation improvements — better accuracy, manual correction UI
- [ ] Batch processing dashboard — progress bars, partial results, resume interrupted runs
- [ ] JS tests — add lightweight DOM-based tests (jsdom or Playwright) covering tag persistence, CSV export output, favourite reordering, and edit save/restore

### Packaging (partially done)

- [x] PyPI (`pipx install bristlenose`)
- [x] Homebrew tap (`brew install cassiocassio/bristlenose/bristlenose`)
- [ ] Snap for Ubuntu/Linux (`snap install bristlenose`)
- [ ] Windows installer (winget or similar)

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, version number, tool config |
| `bristlenose/cli.py` | Typer CLI entry point (`run`, `transcribe-only`, `analyze`, `render`) |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator (full run, transcribe-only, analyze-only, render-only) |
| `bristlenose/stages/render_html.py` | HTML report renderer — loads CSS + JS from theme/, all interactive features |
| `bristlenose/theme/` | Atomic CSS design system (tokens, atoms, molecules, organisms, templates) |
| `bristlenose/theme/js/` | Report JavaScript modules (storage, player, favourites, editing, tags, histogram, csv-export, main) — concatenated at render time |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection |
| `CONTRIBUTING.md` | CLA, code style, design system docs, full release process |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap:** https://github.com/cassiocassio/homebrew-bristlenose
- **PyPI tokens:** https://pypi.org/manage/account/token/
