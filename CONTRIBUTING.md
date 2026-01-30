# Contributing to Bristlenose

Thanks for your interest in contributing!

## Contributor Licence Agreement

By submitting a pull request or patch to this project, you agree that:

1. You have the right to assign the contribution.
2. You grant the project maintainer (Cassio) a perpetual, worldwide,
   irrevocable, royalty-free licence to use, modify, sublicence, and
   relicence your contribution — including under licences other than
   AGPL-3.0.
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

## Project layout

```
bristlenose/          # main package
  cli.py              # Typer CLI (run, transcribe-only, analyze, render)
  config.py           # Pydantic settings (env vars, .env, bristlenose.toml)
  models.py           # Pydantic data models (quotes, themes, enums)
  pipeline.py         # orchestrator (full run, transcribe-only, analyze-only, render-only)
  stages/             # 12-stage pipeline (ingest → render)
    render_html.py    # HTML report renderer (loads CSS from theme/, embeds JS)
  llm/
    prompts.py        # LLM prompt templates
    structured.py     # Pydantic schemas for LLM structured output
  theme/              # design system (atomic CSS) — see below
    tokens.css
    atoms/
    molecules/
    organisms/
    templates/
    index.css         # documents concatenation order
  utils/
    hardware.py       # GPU/CPU detection
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
    button.css                #    fav-star, edit-pencil, restore, toolbar-btn
    input.css                 #    tag input + sizer
    toast.css                 #    clipboard toast
    timecode.css              #    clickable timecodes
    bar.css                   #    sentiment bar, count, label, divider
  molecules/                  # 3. Molecules       (small groups of atoms)
    badge-row.css             #    badges flex container
    bar-group.css             #    bar-group row (label + bar + count)
    quote-actions.css         #    favourite/edit states, animations
    tag-input.css             #    input wrapper + suggest dropdown
  organisms/                  # 4. Organisms       (self-contained UI sections)
    blockquote.css            #    full quote card, rewatch items
    sentiment-chart.css       #    chart layout, side-by-side row
    toolbar.css               #    sticky toolbar
    toc.css                   #    table of contents columns
  templates/                  # 5. Templates       (page-level layout)
    report.css                #    body, article, headings, tables, links
    print.css                 #    @media print overrides
  index.css                   # human-readable index (not used by code)
```

### How it works

`render_html.py` defines a `_THEME_FILES` list that specifies the exact concatenation order. The function `_load_default_css()` reads each file, wraps it with a section comment, and joins them into one string. This is cached once per process, then written to `bristlenose-theme.css` in the output directory on every run (always overwritten -- user state like favourites and tags lives in localStorage, not CSS).

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

### Future: user-generated themes

The token architecture is designed to support user themes. A theme is just a CSS file that overrides `--bn-*` properties:

```css
/* dark-theme.css */
:root {
    --bn-colour-bg: #1a1a2e;
    --bn-colour-text: #e0e0e0;
    --bn-colour-border: #333;
}
```

This will be loaded via a theme picker in the browser toolbar (see roadmap). The infrastructure is ready -- what's needed is the picker UI and a way to bundle/discover theme files.

## Releasing

Day-to-day development just means committing and pushing to `main`. PyPI and Homebrew only need updating when you cut a release.

### 1. Bump the version

Edit `pyproject.toml`:

```toml
version = "0.2.0"
```

### 2. Build the distribution

```bash
pip install build twine     # if not already installed
python -m build
```

This creates `dist/bristlenose-0.2.0.tar.gz` and `dist/bristlenose-0.2.0-py3-none-any.whl`.

### 3. Publish to PyPI

```bash
twine upload dist/bristlenose-0.2.0*
```

Username is `__token__`. Password is a PyPI API token (starts with `pypi-`). Create tokens at https://pypi.org/manage/account/token/.

Verify at https://pypi.org/project/bristlenose/.

### 4. Update the Homebrew tap

The tap lives at https://github.com/cassiocassio/homebrew-bristlenose.

Get the new sdist URL and sha256:

```bash
python3 -c "
import json, urllib.request
with urllib.request.urlopen('https://pypi.org/pypi/bristlenose/0.2.0/json') as r:
    data = json.loads(r.read())
    for f in data['urls']:
        if f['packagetype'] == 'sdist':
            print(f'url: {f[\"url\"]}')
            print(f'sha256: {f[\"digests\"][\"sha256\"]}')
"
```

Edit `Formula/bristlenose.rb` in the tap repo — update `url`, `sha256`, and the version string in the `pip install` line. Commit and push.

### 5. Tag the release

```bash
git tag v0.2.0
git push origin v0.2.0
```

### Summary

| What              | When                  | How                                            |
|-------------------|-----------------------|------------------------------------------------|
| Commit to `main`  | Every change          | `git push`                                     |
| PyPI              | Each release          | `python -m build && twine upload dist/*`       |
| Homebrew tap      | After PyPI publish    | Update `url` + `sha256` in `Formula/*.rb`      |
| Git tag           | After PyPI publish    | `git tag vX.Y.Z && git push origin vX.Y.Z`    |

### Homebrew architecture note

The formula at `Formula/bristlenose.rb` creates a Python 3.12 virtualenv and runs `pip install bristlenose==<version>` from PyPI. This uses pre-built wheels rather than individual Homebrew resource stanzas. A traditional resource-stanza formula would require maintaining 100+ pinned dependencies (including PyTorch, onnxruntime, spacy) — impractical for an ML-heavy tool. The pip-in-venv approach is standard for custom taps with complex dependency trees.
