# Merge Plan: keyboard-navigation → main

This branch contains keyboard navigation work. Preferences system is stashed separately.

## Branch Status

**Branch:** `keyboard-navigation`
**Base:** `main`
**Last updated:** This session

### Commits on branch:
1. `e524ab3` — add keyboard navigation design doc
2. `4c2cc52` — add visual experiments page for focus/selection styles
3. `9ea15d8` — finalise visual design for focus/selection states
4. `40b04a4` — **keyboard navigation: focus system + favourites→starred rename**

### Stashed (separate work):
- `stash@{0}` — **preferences system** (complete, tests passing)
  - To restore: `git checkout -b feature/preferences && git stash pop`

## What's on This Branch

### 1. Design Doc + Experiments (commits 1-3)
- `docs/design-keyboard-navigation.md` — full spec for focus/selection/keyboard shortcuts
- `experiments/focus-selection-styles*.html` — visual prototypes

### 2. Focus System (commit 4)
- `--bn-focus-shadow`, `--bn-selection-bg` tokens in `tokens.css`
- `.bn-focused`, `.bn-selected` classes in `atoms/interactive.css`
- `focus.js` — keyboard focus state, j/k navigation, click to focus, Escape to blur
- Integrated into boot sequence via `main.js`

### 3. Favourites → Starred Rename (commit 4)
Full rename across codebase:
- `favourites.js` → `starred.js`
- `.favourited` → `.starred`
- `.fav-star` → `.star-btn`
- `--bn-colour-favourited` → `--bn-colour-starred`
- View mode `"favourites"` → `"starred"`
- Menu text "Favourite quotes" → "Starred quotes"
- Added localStorage migration (auto-migrates old data)

## Preferences System (Stashed Separately)

Complete implementation by other session, stashed for clean separation.

**What it does:**
- Report-level preferences persisted in `preferences.yaml`
- Three preferences: `color_scheme`, `animations_enabled`, `ai_tags_visible`
- Browser-side reconciliation (localStorage vs baked values)

**Files:**
- `bristlenose/preferences.py` (new)
- `bristlenose/theme/js/preferences.js` (new)
- `tests/test_preferences.py` (new)
- Modifications to: `models.py`, `output_paths.py`, `pipeline.py`, `render_html.py`, `interactive.css`

**To merge later:**
```bash
git checkout main
git checkout -b feature/preferences
git stash pop
# fix any conflicts, test, commit, merge
```

## Merge Strategy

### Recommended: Merge keyboard-navigation first, then preferences

1. **Merge this branch to main:**
   ```bash
   git checkout main
   git merge keyboard-navigation
   ```

2. **Later, restore and merge preferences:**
   ```bash
   git checkout -b feature/preferences
   git stash pop
   # resolve any conflicts with starred rename
   git commit -m "add preferences system"
   git checkout main
   git merge feature/preferences
   ```

### Potential conflicts when merging preferences:
- `starred.js` — preferences checks `animations_enabled` but references old function names
- `interactive.css` — both branches add rules
- `main.js` — boot sequence order

## Pre-Merge Checklist

- [x] All tests pass (652 passed, 4 skipped, 22 xfailed)
- [x] Lint passes (`ruff check .`)
- [ ] Manual test: generate a report, verify focus works (j/k navigation)
- [ ] Manual test: verify starred works (star quotes, view mode, localStorage migration)
- [ ] Update root CLAUDE.md with new conventions
- [ ] Update TODO.md to mark completed items

## Files Changed (This Branch Only)

### New
- `bristlenose/theme/atoms/interactive.css`
- `bristlenose/theme/js/focus.js`
- `bristlenose/theme/js/starred.js`
- `docs/design-keyboard-navigation.md`
- `docs/merge-plan-keyboard-navigation.md`
- `experiments/focus-selection-styles.html`
- `experiments/focus-selection-styles-v2.html`
- `experiments/focus-selection-styles-v3.html`

### Deleted
- `bristlenose/theme/js/favourites.js`

### Modified
- `bristlenose/stages/render_html.py`
- `bristlenose/theme/CLAUDE.md`
- `bristlenose/theme/atoms/button.css`
- `bristlenose/theme/index.css`
- `bristlenose/theme/js/csv-export.js`
- `bristlenose/theme/js/main.js`
- `bristlenose/theme/js/search.js`
- `bristlenose/theme/js/view-switcher.js`
- `bristlenose/theme/molecules/quote-actions.css`
- `bristlenose/theme/templates/print.css`
- `bristlenose/theme/tokens.css`
