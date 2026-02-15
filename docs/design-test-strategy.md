# Testing & CI Strategy — Gap Audit

_Feb 2026. Written as Bristlenose evolves from CLI + static HTML to server app + React frontend._

## Why this audit

Phase 1 data API is complete. Manual UI testing caught bugs (double-prefix, IIFE wrapper) that the 94 API-level pytest tests couldn't see. Before expanding the design surface area (React component migration, export, multi-user), we need to understand what the testing and infrastructure gaps are and when to close them.

## Current state

### What we have (strengths)

| Layer | Coverage | Tool | CI gate? |
|-------|----------|------|----------|
| Python pipeline stages | ~1,150 tests | pytest | Yes |
| Data API (HTTP -> DB) | 94 tests (37 happy + 57 stress) | pytest + TestClient | Yes |
| Python linting | Full | Ruff | Yes |
| Type checking | Full | mypy | Informational (not blocking) |
| Dependency vulnerabilities | Python deps | pip-audit | Informational (not blocking) |
| Man page version | Matches `__version__` | CI check | Yes |
| Install smoke tests | pip/pipx/brew on Linux/macOS | Weekly cron + manual | Yes |
| Release automation | PyPI (OIDC), Homebrew tap, Snap | GitHub Actions | Yes |

### What's missing (gaps)

| Gap | Risk | When to fix |
|-----|------|-------------|
| **E2E browser tests** (JS -> API -> DB) | High — caught 2 bugs manually | Post-React migration |
| **Visual regression tests** (pixel-diff across browsers) | Medium — CSS breaks are silent | Post-React migration |
| **Frontend unit tests** (React components) | High — building UI with no tests | During React Phase 2 |
| **Frontend linting** (ESLint, Prettier) | High — no code quality checks | Before React Phase 2 |
| **JS/TS type checking in CI** | Medium — TypeScript exists but not gated | Before React Phase 2 |
| **Cross-browser testing** | Low now, high after public release | Post-React (Playwright runs 3 engines) |
| **Python test coverage tracking** | Medium — pytest-cov installed but not used | Now (easy) |
| **API contract tests** | Medium — response shape changes break JS silently | Post-React (TypeScript types enforce this) |
| **Accessibility testing** (axe-core, ARIA) | Medium — interactive report needs a11y | Post-React |
| **Database migration tests** | Medium — no Alembic yet | Before first schema change |
| **Multi-Python version CI** | Low — only tests 3.12, claims >=3.10 | Now (easy) |
| **Multi-platform CI** | Low — tests on Ubuntu only, macOS in install-test only | Now (easy) |
| **Security scanning** (SAST, npm audit) | Medium — pip-audit only, no frontend | Before public release |
| **Bundle size monitoring** | Low now, medium after React | Post-React Phase 2 |
| **Performance regression tests** | Low — single-user tool | When multi-user matters |
| **Docker/containers** | Low — Snap exists for Linux | When deployment model changes |

## Testing layers (target architecture)

After the React migration, the testing pyramid should look like:

```
                    /\
                   /  \     E2E (Playwright) — ~12 tests
                  /    \    Browser clicks -> API -> DB -> assert
                 /------\
                /        \   Visual regression (Playwright screenshots)
               /          \  Pixel-diff across browsers/viewports
              /------------\
             /              \  Integration (pytest + TestClient) — ~100 tests
            /                \ HTTP requests -> API -> DB -> assert JSON
           /------------------\
          /                    \  React component tests (Vitest + RTL) — many
         /                      \ Render component -> assert DOM -> fire events
        /------------------------\
       /                          \  Python unit tests (pytest) — ~1,150 tests
      /                            \ Pipeline stages, analysis, LLM, utilities
     /------------------------------\
```

## Tool choices

### E2E + Visual regression: Playwright

**Why Playwright over alternatives:**
- Python-native (`pip install pytest-playwright`) — same `pytest` runner, same CI
- Fast — headless Chrome in ~200ms
- Built-in screenshot comparison (`toMatchSnapshot()`) — no Percy/Chromatic subscription needed
- Runs Chromium, Firefox, and WebKit from one test — free cross-browser coverage
- Can intercept network requests (verify the PUT was actually sent)
- Can query SQLite directly in the same test process (Python has DB access)

**Why not Percy/Chromatic:** Paid services, external dependency, overkill for a single-maintainer project. Playwright's built-in visual comparison is sufficient. If the project grows to need cloud-hosted visual review (multiple contributors approving visual changes), Percy or Chromatic become worthwhile.

**Why not Selenium:** Heavier, slower, flakier. Being replaced by Playwright in most new projects.

**Why not Cypress:** JS-only (no Python API), can't query SQLite directly, doesn't fit the pytest workflow.

### React component tests: Vitest + React Testing Library

**Why Vitest:** Vite-native (we already use Vite), fast, Jest-compatible API, same config as the build.

**Why React Testing Library (RTL):** Tests components from the user's perspective (find by role, text, label) rather than implementation details. Encourages accessible markup.

### Frontend linting: ESLint + Prettier

**What to add to `frontend/package.json`:**
- `eslint` with `eslint-plugin-react-hooks` (catch hook rule violations)
- `eslint-plugin-jsx-a11y` (catch accessibility issues at lint time)
- `prettier` + `eslint-config-prettier` (formatting, no conflicts with ESLint)

### Visual regression baseline approach

1. Playwright renders each page/state to a screenshot
2. First run creates baseline images (committed to repo or stored in CI artifacts)
3. Subsequent runs pixel-diff against baseline
4. Threshold: allow ~0.1% pixel difference (anti-aliasing across platforms)
5. Failures show a visual diff image — easy to review

Pages to capture:
- Project tab (dashboard)
- Sessions tab (table with sparklines)
- Quotes tab (cards with tags, stars, badges)
- Codebook tab
- Analysis tab (heatmaps, signal cards)
- Transcript page (with annotations)
- Dark mode variant of each

## Convention: `data-testid` attributes

**Every React component must emit `data-testid` attributes on interactive elements from day one.** This makes E2E and component test selectors stable across refactors.

Naming convention: `data-testid="bn-{component}-{element}"`, e.g.:
- `data-testid="bn-quote-star"` — star toggle on a quote card
- `data-testid="bn-quote-hide"` — hide button
- `data-testid="bn-tag-input"` — tag input field
- `data-testid="bn-tag-badge"` — a tag badge (with `data-tag-name` for specificity)
- `data-testid="bn-session-row"` — a session table row (with `data-session-id`)

These can be stripped in production builds via a Vite plugin if bundle size is a concern, but should remain in dev/test builds.

## Implementation timeline

### Now (easy wins, no React dependency)

- [ ] **Enable pytest coverage** — add `--cov=bristlenose --cov-report=term` to CI. No threshold yet, just establish a baseline
- [ ] **Multi-Python CI** — test 3.10, 3.11, 3.12, 3.13 in matrix
- [ ] **Add macOS to main CI** — not just install-test

### Before React Phase 2 (component migration)

- [ ] **Vitest + RTL setup** — `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`
- [ ] **ESLint + Prettier** — `npm install -D eslint eslint-plugin-react-hooks eslint-plugin-jsx-a11y prettier`
- [ ] **TypeScript strict mode** — enable in `tsconfig.json`, fix incrementally
- [ ] **Frontend CI job** — `npm run lint && npm run type-check && npm run test`
- [ ] **`data-testid` convention** — document in CONTRIBUTING.md, enforce in code review

### During React Phase 2 (as components ship)

- [ ] **Component tests** — every new React component gets Vitest + RTL tests
- [ ] **A11y lint rules** — `eslint-plugin-jsx-a11y` catches issues at development time

### After React migration completes

- [ ] **Playwright E2E tests** — 12 tests covering all 11 DB-mutating user actions + 1 graceful degradation test (static HTML, no server)
- [ ] **Visual regression baselines** — Playwright screenshots of all pages/tabs in light + dark mode
- [ ] **Cross-browser CI** — Playwright runs Chromium + Firefox + WebKit
- [ ] **Bundle size budget** — track main bundle size, alert on growth
- [ ] **axe-core in Playwright** — accessibility assertions in E2E tests

### Before first schema change

- [ ] **Alembic setup** — migration tool for SQLite schema changes
- [ ] **Migration tests** — test upgrade + downgrade paths with test data

### Before public release / multi-user

- [ ] **Security hardening** — enable Dependabot, add `npm audit` to CI, consider CodeQL
- [ ] **Rate limiting** — protect API endpoints
- [ ] **Authentication** — if server exposed beyond localhost

## Cost-benefit summary

| Investment | One-time cost | Ongoing cost | Bugs it catches |
|-----------|--------------|-------------|-----------------|
| pytest coverage | 30 min | None | Dead code, untested paths |
| ESLint + Prettier | 2 hours | Minimal (auto-fix) | Code quality, a11y, formatting |
| Vitest + RTL | 1 day setup | 15 min per component | Component logic, render bugs |
| Playwright E2E | 1 day setup | Medium (selector maintenance) | Full-stack integration bugs |
| Visual regression | 2 hours setup | Low (baseline updates) | CSS regressions, layout breaks |
| Multi-Python CI | 30 min | None | Version compatibility |
| Bundle size tracking | 1 hour | None | Bundle bloat |

The React migration naturally closes 5 gaps (E2E, visual, cross-browser, JS unit tests, API contracts) because it introduces TypeScript + a testable component model + Playwright. The key insight is: **invest in frontend testing infrastructure _before_ building more components, not after.**
