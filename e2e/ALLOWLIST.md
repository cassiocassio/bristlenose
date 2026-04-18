# E2E CI Allowlist Register

This is the audit trail for every deliberate suppression in the Playwright e2e specs. If the e2e gate ignores a failure, the reason is here — one page, reviewable in GitHub diff without running any tooling.

The goal is to preserve the distinction, three months or three years from now, between:

- **"CI lubricant"** — browser/runner/stack artefacts that are never our bug (e.g. favicon 404), and
- **Real technical debt** — known product bugs that the test is quiet about because we haven't fixed them yet.

Without this register, an accumulating pile of `if (...) return;` checks in spec files becomes impossible to audit, and the gate turns into theatre.

## Rule

**Every suppression in `e2e/tests/*.spec.ts` must have a matching entry here.** The suppression in code carries a `// ci-allowlist: CI-A<N>` comment marker so a reviewer can find the register entry in one grep. Adding a suppression without a register entry is not an oversight — it's a convention violation and should be caught in review.

See the root `CLAUDE.md` "Gotchas" section for the one-line rule.

## Categories

Three mutually exclusive categories. Category determines whether the entry is audited over time, or noted-and-forgotten.

| Category | Meaning | Tracker field | Review cadence |
|---|---|---|---|
| `infra` | Stack/browser/runner artefact. Inherent to the complexity of the platform we chose. Not our bug, not our code. Never fixable, never tech debt. | `n/a` | Annual sanity check — has the stack changed? |
| `by-design` | The expected behaviour is intentional and semantically correct. The suppression teaches the test about that choice. Durable. Not tech debt. | `n/a` (or link to design doc) | Annual sanity check — is the design still correct? |
| `deferred-fix` | **Real bug.** Suppression unblocks CI while the fix is scheduled. **Must** link to a `100days.md` item (or issue) where the real work is tracked. | required | Checked every sprint; fixed promptly |

### Writing a rationale

One sentence. **Symptom, not story.** No customer or trial-run references. If private context is needed, put it in `docs/private/` and use a stub here: `rationale: see internal notes`. Same house-style rule Bristlenose uses for `SECURITY.md`.

### ID numbering

Sequential `CI-A1`, `CI-A2`, ... **Retired IDs are never reused** — this preserves the git archaeology (`git log -Sci-allowlist: CI-A7 -- e2e/`) even after an entry is removed. Removed entries move to the "Retired" section at the bottom with the date and reason.

## Register

| ID | Category | Spec | Rationale | Tracker | Added |
|---|---|---|---|---|---|
| CI-A1 | `infra` | `console.spec.ts` (favicon check) | Browsers automatically request `/favicon.ico`; our smoke fixture doesn't ship one. Never a product bug. | n/a | pre-existing |
| CI-A2 | `by-design` | `links.spec.ts` (`role=button` skip) | Interactive elements (modal openers, toggles) legitimately have no `href`; using `<a role="button">` is an intentional WAI-ARIA pattern. | n/a | pre-existing |
| CI-A3 | `by-design` | `network.spec.ts` (autocode status 404) | `GET /api/projects/*/autocode/*/status` returns 404 when no autocode job has been started for a framework — REST-correct ("resource absent"). The frontend at `CodebookPanel.tsx` treats the 404 as null-equivalent (`status: idle`). Changing the endpoint to 200+idle would be cosmetic churn on a working path. | n/a | 2026-04-18 |
| CI-A4 | `deferred-fix` | `console.spec.ts` (codebook route 404) | `/report/codebook/` emits a console error for a 404 subresource whose URL is truncated by `msg.text()`. Local `curl` of the page + listed assets all return 200; the culprit is runtime (likely route-chunk prefetch, CSS sprite, or font). Root cause not yet known. | `docs/private/100days.md` §2 Could → [S3] Codebook subresource | 2026-04-18 |

## Retired

_None yet. When an entry is removed, move its row here with `removed: YYYY-MM-DD` and a one-sentence reason (bug fixed / stack upgraded / obsolete test / etc.). Do not reuse the ID._

## Future v2 (not yet in place)

These were reviewed and explicitly deferred to keep v1 shippable with ci-cleanup. Tracked in `docs/private/100days.md` §11 Operations:

- **Validator script** (`scripts/check-ci-allowlists.py`) — parse both sides, fail CI on drift (code comment with no register entry, or register entry with no code comment). Trigger: ~10th entry, or before first external contributor, whichever comes first.
- **Staleness gate** — flag any `deferred-fix` entry with `added` > 90 days unless renewed. Trigger: first entry crosses 60 days. Oldest entry today (CI-A4) is brand new.
- **Regex-shape lint** — reject unanchored `.*` / `.+` patterns in suppression regexes. Mitigates the regex-widening attack that security review flagged. Ships with the validator.
- **CODEOWNERS on `e2e/tests/*.spec.ts`** — enforces review obligation. Tracked separately under supply-chain hardening in 100days.md §11.
