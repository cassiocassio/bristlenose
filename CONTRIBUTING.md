# Contributing to Bristlenose

Thanks for your interest in contributing!

## Contributor Licence Agreement

By submitting a pull request or patch to this project, you agree that:

1. You have the right to assign the contribution.
2. You grant the project maintainer (Martin Storey, martin@cassiocassio.co.uk)
   a perpetual, worldwide, irrevocable, royalty-free licence to use, modify,
   sublicence, and relicence your contribution — including under licences
   other than AGPL-3.0.
3. Your contribution is provided as-is, without warranty.

This allows the maintainer to offer commercial or dual-licence versions
of Bristlenose in the future without needing to contact every contributor
individually.

## How to contribute

1. Fork the repo and create a branch.
2. Make your changes.
3. Run `ruff check` and `pytest` before submitting.
4. Open a pull request with a clear description of what and why.

## Code style

- Python 3.10+
- Ruff for linting (config in `pyproject.toml`)
- Type hints everywhere
- Jinja2 templates for HTML components (in `bristlenose/theme/templates/`)

## Project layout

```
bristlenose/          # main package
  cli.py              # Typer CLI (run, transcribe, analyze, render, serve, status, doctor)
  config.py           # Pydantic settings (env vars, .env, bristlenose.toml)
  doctor.py           # Doctor check logic (7 checks, run_all, run_preflight)
  doctor_fixes.py     # Install-method-aware fix instructions
  models.py           # Pydantic data models (quotes, themes, enums)
  pipeline.py         # orchestrator (full run, transcribe-only, analyze-only, render-only)
  stages/             # 12-stage pipeline (ingest → render)
    render_html.py    # HTML report renderer (Jinja2 templates + CSS from theme/, embeds JS)
  llm/
    prompts.py        # LLM prompt templates
    structured.py     # Pydantic schemas for LLM structured output
  people.py           # people file: load, compute, merge, write, name extraction
  theme/              # design system (atomic CSS + Jinja2 templates) — see below
    tokens.css
    atoms/
    molecules/
    organisms/
    templates/        # Jinja2 HTML templates + CSS page layouts
      *.html          # 13 component templates (quote card, toolbar, etc.)
      *.css           # page-level CSS (report, transcript, print)
    js/               # 20 JS modules concatenated at render time
    index.css         # documents concatenation order
  utils/
    hardware.py       # GPU/CPU detection
snap/
  snapcraft.yaml      # Snap recipe (classic confinement, core24 base)
tests/
pyproject.toml        # package metadata, deps, tool config (hatchling build)
```

---

## Design system (`bristlenose/theme/`)

The report stylesheet follows [atomic design](https://bradfrost.com/blog/post/atomic-web-design/) principles. Each CSS concern lives in its own file. At render time, `render_html.py` reads and concatenates them in order into a single `bristlenose-theme.css` that ships alongside the report.

### Architecture

```
theme/
  tokens.css                  # 1. Design tokens  (CSS custom properties)
  atoms/                      # 2. Atoms          (smallest reusable pieces)
    badge.css                 #    base badge, sentiment variants, AI/user/add
    button.css                #    fav-star, edit-pencil, restore, toolbar-btn, toolbar-icon-svg
    logo.css                  #    report header layout, logotype, project name
    input.css                 #    tag input + sizer
    toast.css                 #    clipboard toast
    timecode.css              #    clickable timecodes
    bar.css                   #    sentiment bar, count, label, divider
  molecules/                  # 3. Molecules       (small groups of atoms)
    badge-row.css             #    badges flex container
    bar-group.css             #    bar-group row (label + bar + count)
    name-edit.css             #    participant name inline editing
    quote-actions.css         #    favourite/edit states, animations
    tag-input.css             #    input wrapper + suggest dropdown
  organisms/                  # 4. Organisms       (self-contained UI sections)
    blockquote.css            #    full quote card, rewatch items
    sentiment-chart.css       #    chart layout, side-by-side row
    toolbar.css               #    sticky toolbar, view-switcher dropdown
    toc.css                   #    table of contents columns
  templates/                  # 5. Templates + Jinja2 components
    report.css                #    body, article, headings, tables, links
    transcript.css            #    per-participant transcript pages
    print.css                 #    @media print overrides
    quote_card.html           #    Jinja2: single quote card
    toolbar.html              #    Jinja2: sticky toolbar
    report_header.html        #    Jinja2: header with logo and meta
    footer.html               #    Jinja2: report footer
    sentiment_chart.html      #    Jinja2: sentiment histogram
    ...                       #    (13 templates total)
  index.css                   # human-readable index (not used by code)
```

### How it works

**CSS:** `render_html.py` defines a `_THEME_FILES` list that specifies the exact concatenation order. The function `_load_default_css()` reads each file, wraps it with a section comment, and joins them into one string. This is cached once per process, then written to `bristlenose-theme.css` in the output directory on every run (always overwritten -- user state like favourites and tags lives in localStorage, not CSS).

**HTML templates:** Report components are Jinja2 templates in `theme/templates/`. Each template receives a context dict from `render_html.py` and renders a self-contained HTML fragment (quote card, toolbar, sentiment chart, etc.). `render_html.py` loads the Jinja2 environment once, then calls `template.render(context)` for each component. The Jinja2 templates live alongside the CSS templates in the same directory -- `.html` files are Jinja2, `.css` files are page-level stylesheets.

**JS:** `render_html.py` defines `_JS_FILES` (and separate lists for transcript/codebook pages) that specify concatenation order. Each `.js` file is an IIFE. They're joined into a single `<script>` block in the rendered HTML.

### Design tokens

All visual decisions live in `tokens.css` as CSS custom properties with a `--bn-` prefix:

```css
--bn-colour-accent: #2563eb;
--bn-font-body: "Inter", system-ui, sans-serif;
--bn-space-md: 0.75rem;
--bn-radius-md: 6px;
--bn-transition-fast: 0.15s ease;
```

Every other CSS file references tokens via `var(--bn-colour-accent)` etc. -- never hard-coded values. This makes the entire visual language overridable from a single file.

**Legacy aliases.** The Python code in `render_html.py` generates inline `style` attributes that reference the older unprefixed names (e.g. `var(--colour-confusion)`). To avoid a breaking change, `tokens.css` defines aliases at the bottom:

```css
--colour-confusion: var(--bn-colour-confusion);
```

These aliases point to the `--bn-` versions, so theme authors only need to override `--bn-*` tokens.

### Working with the CSS

**Adding a new component:**

1. Decide the atomic layer (is it an atom, molecule, or organism?).
2. Create a new `.css` file in the right folder.
3. Reference tokens, never hard-coded values.
4. Add the file to the `_THEME_FILES` list in `render_html.py` (order matters -- later files can override earlier ones).

**Adding a new token:**

1. Add the `--bn-*` property in `tokens.css`.
2. If the token is used in inline styles generated by Python, also add a legacy alias.

**Modifying existing styles:**

1. Find the right file by layer (use `index.css` as a map).
2. Edit the file directly. The change will appear on the next pipeline run.
3. No need to delete old output -- `bristlenose-theme.css` is always overwritten.

**Quick reference -- which file owns what:**

| I want to change...            | Edit this file              |
|--------------------------------|-----------------------------|
| Colours, fonts, spacing        | `tokens.css`                |
| How badges look                | `atoms/badge.css`           |
| How star/pencil buttons work   | `atoms/button.css`          |
| The tag input or suggest list  | `atoms/input.css` + `molecules/tag-input.css` |
| The whole quote card layout    | `organisms/blockquote.css`  |
| The sentiment chart            | `atoms/bar.css` + `molecules/bar-group.css` + `organisms/sentiment-chart.css` |
| Page layout, headings, tables  | `templates/report.css`      |
| What gets hidden when printing | `templates/print.css`       |

### Dark mode

Dark mode is built into `tokens.css` using the CSS `light-dark()` function. For full details on the dark mode cascade, how tokens work, and adding new colour tokens, see `bristlenose/theme/CLAUDE.md`.

## Releasing

Day-to-day development just means committing and pushing to `main`. CI runs automatically. PyPI and Homebrew are updated when you tag a release.

### Quick release

```bash
# 1. Bump the version in bristlenose/__init__.py
# 2. Add a changelog entry in CHANGELOG.md and README.md
#    Format: **X.Y.Z** — _D Mon YYYY_  (e.g. **0.8.1** — _7 Feb 2026_)
# 3. Commit, tag, and push:
git add bristlenose/__init__.py README.md
git commit -m "vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

GitHub Actions handles the rest: CI → PyPI publish → GitHub Release → Homebrew tap update. The snap workflow also triggers: edge on push to main, stable on tags.

For the full release pipeline details, cross-repo topology, secrets, Homebrew tap automation, and Snap Store setup, see [`docs/release.md`](docs/release.md).
