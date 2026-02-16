# QA Script — React Component Library Round 1

**Branch:** `serve`
**Worktree:** `/Users/cassio/Code/bristlenose_branch serve`
**Date:** 16 Feb 2026

Run these checks to verify the Round 1 delivery (CSS rename + tooling + Badge/PersonBadge/TimecodeLink + SessionsTable refactor).

---

## 1. Automated checks

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"

# Python tests (should see 1144 passed)
.venv/bin/python -m pytest tests/ -q

# Python lint (should say "All checks passed!")
.venv/bin/ruff check .

# Frontend tests (should see 19 passed across 3 files)
cd frontend && npm test

# ESLint (should produce no output = clean)
npm run lint

# TypeScript (should produce no output = clean)
npm run typecheck

# Vite build (should succeed, ~39 modules)
npm run build
```

**Expected:** all green, zero failures, zero lint errors.

---

## 2. CSS rename verification

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"

# Should find ZERO results — old name is completely gone
grep -r "person-id" bristlenose/ frontend/src/ tests/ docs/

# Should find results in all expected files — new name is in place
grep -r "person-badge" bristlenose/theme/molecules/person-badge.css
grep -r "bn-person-badge" bristlenose/stages/render_html.py
grep -r "bn-person-badge" bristlenose/server/routes/dev.py
grep -r "bn-person-badge" bristlenose/theme/templates/session_table.html
grep -r "bn-person-badge" bristlenose/theme/templates/dashboard_session_table.html
grep -r "bn-person-badge" frontend/src/islands/SessionsTable.tsx
grep -r "bn-person-badge" tests/test_navigation.py
```

**Expected:** zero hits for old name, hits in every file listed for new name.

---

## 3. Visual parity (manual, requires a rendered project)

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"

# Render a test project (need one with people.yaml for speaker names)
.venv/bin/python -m bristlenose render trial-runs/project-ikea

# Open the report and check the session table
open trial-runs/project-ikea/bristlenose-output/bristlenose-project-ikea-report.html
```

**Check in browser:**
- [ ] Sessions tab: speaker badges render with code + name (e.g. `[p1] Alice`)
- [ ] Sessions tab: moderator header shows "Moderated by [m1] Rachel"
- [ ] Project tab: dashboard compact session table also shows badges
- [ ] No visual difference from before the rename (CSS classes match)

---

## 4. Serve mode visual parity (manual, requires Vite)

```bash
# Terminal 1: start the backend
cd "/Users/cassio/Code/bristlenose_branch serve"
.venv/bin/python -m bristlenose serve trial-runs/project-ikea --dev

# Terminal 2: start Vite
cd "/Users/cassio/Code/bristlenose_branch serve/frontend"
npm run dev
```

**Check at `http://localhost:5173`:**
- [ ] Sessions table loads via React (API fetch)
- [ ] Speaker badges use `.bn-person-badge` class (inspect in DevTools)
- [ ] Badge + name render identically to the static report
- [ ] Visual diff tool at `/visual-diff.html` shows no regressions

---

## 5. Component file structure

```bash
cd "/Users/cassio/Code/bristlenose_branch serve/frontend/src"

# Should see: Badge.tsx, Badge.test.tsx, PersonBadge.tsx, PersonBadge.test.tsx,
#             TimecodeLink.tsx, TimecodeLink.test.tsx, index.ts
ls components/

# Should see: format.ts
ls utils/

# Should see eslint.config.js, test-setup.ts in expected locations
ls ../eslint.config.js
ls test-setup.ts
```

---

## 6. Commit history

```bash
cd "/Users/cassio/Code/bristlenose_branch serve"
git log --oneline -5
```

**Expected 3 commits from this session:**
1. `rename .bn-person-id → .bn-person-badge across codebase`
2. `add React component library: Badge, PersonBadge, TimecodeLink`
3. `docs: CSS ↔ React alignment table, per-round refactoring schedule`
