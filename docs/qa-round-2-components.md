# QA Script — React Component Library Round 2

**Branch:** `serve`
**Worktree:** `/Users/cassio/Code/bristlenose_branch serve`
**Date:** 16 Feb 2026

Run these checks to verify the Round 2 delivery (CSS refactoring + EditableText + Toggle).

---

## 1. Automated checks

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"

# Python tests (should see 1144 passed)
.venv/bin/python -m pytest tests/ -q

# Python lint
.venv/bin/ruff check .

# Frontend tests (should see 47 passed across 5 files)
cd frontend && npm test

# ESLint
npm run lint

# TypeScript
npm run typecheck

# Vite build
npm run build
```

**Expected:** all green, zero failures, zero lint errors.

---

## 2. CSS refactoring — no rules lost

The CSS refactoring moved rules between files but the concatenated stylesheet should be identical in behaviour. Verify no rules were dropped.

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"

# star-btn should be in toggle.css, NOT in button.css
grep -l "\.star-btn" bristlenose/theme/atoms/toggle.css    # should hit
grep -c "\.star-btn" bristlenose/theme/atoms/button.css     # should be 0

# hide-btn should be in toggle.css, NOT in hidden-quotes.css
grep -l "\.hide-btn" bristlenose/theme/atoms/toggle.css           # should hit
grep -c "\.hide-btn" bristlenose/theme/molecules/hidden-quotes.css # should be 0

# toolbar-btn-toggle rules should be in toggle.css, NOT in button.css
grep -l "\.toolbar-btn-toggle" bristlenose/theme/atoms/toggle.css  # should hit
grep -c "\.toolbar-btn-toggle" bristlenose/theme/atoms/button.css   # should be 0 (comments mention it, but no rules)

# Editing states should be in editable-text.css, NOT in quote-actions or name-edit
grep -l "editing-bg" bristlenose/theme/molecules/editable-text.css    # should hit
grep -c "editing-bg" bristlenose/theme/molecules/quote-actions.css     # should be 0
grep -c "editing-bg" bristlenose/theme/molecules/name-edit.css         # should be 0

# .edited should be in editable-text.css, NOT in quote-actions or name-edit
grep -l "\.edited" bristlenose/theme/molecules/editable-text.css      # should hit
grep -c "\.edited" bristlenose/theme/molecules/quote-actions.css       # should be 0
grep -c "\.edited" bristlenose/theme/molecules/name-edit.css           # should be 0
```

**Expected:** all rules present in new files, absent from old files.

---

## 3. `_THEME_FILES` order

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"
grep -n "toggle\|editable-text" bristlenose/stages/render_html.py
```

**Expected:**
- `atoms/toggle.css` appears after `atoms/button.css`
- `molecules/editable-text.css` appears before `molecules/quote-actions.css`

---

## 4. Visual regression — static report (manual, requires rendered project)

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"
.venv/bin/python -m bristlenose render trial-runs/project-ikea
open trial-runs/project-ikea/bristlenose-output/bristlenose-project-ikea-report.html
```

**Check in browser — these all use the CSS rules that were moved:**
- [ ] Quote starring: click star icon, quote goes bold with accent left border
- [ ] Quote editing: click pencil, yellow contenteditable bg appears, dashed underline after save
- [ ] Quote hiding: hover shows eye-slash icon, click hides with animation, badge dropdown works
- [ ] Heading editing: click inline pencil next to section/theme heading, yellow bg, dashed underline after save
- [ ] Name editing: click pencil in participant table, yellow bg, dashed underline after save
- [ ] AI tag toolbar toggle: toggle button shows active/inactive state correctly
- [ ] No visual difference from before the refactoring

---

## 5. Serve mode — React mount + Vite HMR (manual)

```bash
# Terminal 1: backend
cd "/Users/cassio/Code/bristlenose_branch serve"
.venv/bin/python -m bristlenose serve trial-runs/project-ikea --dev

# Terminal 2: Vite
cd "/Users/cassio/Code/bristlenose_branch serve/frontend"
npm run dev
```

**Check at `http://localhost:5173`:**
- [ ] Sessions table loads via React (API fetch, green tint in renderer overlay)
- [ ] No console errors related to missing CSS classes
- [ ] Visual diff tool at `/visual-diff.html` shows no regressions

---

## 6. Component file structure

```bash
cd "/Users/cassio/Code/bristlenose_branch serve/frontend/src"

# Should see 10 files: 5 components × (component + test)  + index.ts
ls components/

# Expect: Badge.tsx, Badge.test.tsx, EditableText.tsx, EditableText.test.tsx,
#          PersonBadge.tsx, PersonBadge.test.tsx, TimecodeLink.tsx, TimecodeLink.test.tsx,
#          Toggle.tsx, Toggle.test.tsx, index.ts
```

---

## 7. Barrel export

```bash
grep "export" frontend/src/components/index.ts
```

**Expected 5 exports:** Badge, EditableText, PersonBadge, TimecodeLink, Toggle (alphabetical).

---

## 8. Documentation updated

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"

# CHANGELOG has Round 2 entry
grep -c "Round 2" docs/CHANGELOG-serve.md                     # should be ≥1

# CSS-REFERENCE has new file entries
grep -c "toggle.css" bristlenose/theme/CSS-REFERENCE.md        # should be ≥1
grep -c "editable-text.css" bristlenose/theme/CSS-REFERENCE.md # should be ≥1

# Alignment table shows Done (Round 2)
grep "Done (Round 2)" docs/design-react-component-library.md  # should show 2 lines

# Next-session prompt updated (no Option A about mount point injection)
grep -c "mount point" docs/next-session-prompt.md              # should be 0
grep -c "EditableText" docs/next-session-prompt.md             # should be ≥1
```
