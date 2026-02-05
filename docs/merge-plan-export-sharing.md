# Merge Plan: export-sharing → main

Step-by-step guide for merging the export-sharing feature branch back to main.

**Branch:** `export-sharing`
**Created:** 5 Feb 2026
**Design doc:** `docs/design-export-sharing.md`

---

## Pre-merge Checklist

Before merging, verify:

- [ ] All phases implemented are tested (pytest passes)
- [ ] Linter passes (`ruff check .`)
- [ ] Design doc is up to date with any implementation changes
- [ ] `BRANCHES.md` has been read — check for conflicts with other active branches
- [ ] If `keyboard-navigation` merged first, this branch has been rebased on main

---

## Files Changed (update as you implement)

### New Files

| File | Phase | Purpose |
|------|-------|---------|
| `docs/design-export-sharing.md` | 0 | Design document |
| `docs/merge-plan-export-sharing.md` | 0 | This file |
| `bristlenose/theme/js/export.js` | 1 | Export dialog and state serialisation |
| `bristlenose/theme/molecules/export-dialog.css` | 1 | Dialog styling |
| `bristlenose/theme/organisms/made-with.css` | 5 | Branding footer styling |
| `tests/test_export.py` | 1+ | Export feature tests |

### Modified Files

| File | Phase | What changed |
|------|-------|--------------|
| `bristlenose/stages/render_html.py` | 0,1,5 | State hydration, export button, footer CTA |
| `bristlenose/theme/js/main.js` | 1 | Add `initExport()` to boot sequence |
| `bristlenose/theme/js/storage.js` | 0 | Add `getAllState()` for serialisation |
| `bristlenose/theme/index.css` | 1,5 | Import new CSS files |
| `bristlenose/config.py` | 3 | `--include-media`, `--portable` flags |
| `bristlenose/cli.py` | 4 | `bristlenose package` command |
| `TODO.md` | all | Mark phases complete |
| `CLAUDE.md` | 0 | Reference to design doc |

---

## Potential Conflicts

### With `keyboard-navigation` branch

Both branches modify:
- `bristlenose/stages/render_html.py`
- `bristlenose/theme/js/main.js`

**Resolution:** `keyboard-navigation` should merge first. After it merges:
```bash
git checkout export-sharing
git fetch origin
git rebase origin/main
# Resolve any conflicts in render_html.py and main.js
```

### With main (general)

If main has moved significantly:
```bash
git fetch origin
git rebase origin/main
```

---

## Merge Steps

### 1. Ensure clean state

```bash
git checkout export-sharing
git status  # should be clean
.venv/bin/python -m pytest tests/
.venv/bin/ruff check .
```

### 2. Rebase on latest main

```bash
git fetch origin
git rebase origin/main
```

If conflicts:
- For `render_html.py`: keep both button additions, ensure boot order is correct
- For `main.js`: add `initExport()` after the existing init calls

### 3. Final test

```bash
.venv/bin/python -m pytest tests/
.venv/bin/ruff check .
```

### 4. Merge to main

```bash
git checkout main
git merge export-sharing
git push origin main
```

### 5. Clean up

```bash
git branch -d export-sharing
# Update docs/BRANCHES.md to move this to "Completed Branches"
```

---

## Post-merge Tasks

- [ ] Update `docs/BRANCHES.md` — move to completed
- [ ] Update `TODO.md` — mark export phases as done
- [ ] Consider version bump if shipping to users
- [ ] Update README if user-facing feature is complete

---

## Implementation Progress

Track what's done as you implement:

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Foundation | Not started | |
| 1 — Save curated report | Not started | |
| 2 — Transcript pages | Not started | |
| 3 — Full archive | Not started | |
| 4 — Video clips | Not started | |
| 5 — Branding footer | Not started | |

---

## Notes for Future Sessions

_Add notes here as you work — things the next Claude session should know._

- Design doc created 5 Feb 2026
- TODO.md and CLAUDE.md updated with references
- No implementation started yet
