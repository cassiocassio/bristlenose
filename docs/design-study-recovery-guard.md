---
status: step-1-implemented
updated: 2026-10-28
scope: R114 / reliability 179; destructive automatic recovery only
---

# Synced-study safety — smallest useful delivery

Owner requested a William of Ockham reset on 28 October: deliver the simplest
implementation providing most of the safety benefit, step by step. Later work
may be tracked in 100days; preserve all previous thinking and experiments.

## Delivery sequence

| Step | Benefit | Boundary and acceptance |
| --- | --- | --- |
| 1. Machine-owned recovery | Opening on this Mac cannot automatically restore/delete another Mac's unfinished analysis. | Require stable local machine and exact run identity under existing local settle lock. Foreign, missing, legacy, malformed and mismatched identity preserve output and backup; positive local crashes still recover. |
| 2. Conservative startup admission | An uncertain unfinished study cannot start ordinary writers here. | Refuse server/importer/jobs and analysis/reanalysis before opening writable state. Existing unavailable/status UI explains the cause. Test actual CLI/native entry points and source bytes. |
| 3. Optional fixed reader | Read a known complete report while editing is refused. | Start from validated immutable local contents; read-only for the entire reader lifetime. No automatic adoption or editing re-entry. Unsupported resources/policy mean unavailable, never fallback to changing source. |

Step 1 is a destructive-recovery fix, not a study-wide lock. Ordinary startup
still writes a log/database after recovery. Explicit `run` still has separate
recovery paths. Do not advertise those paths as protected until step 2 is proven.
No marker provides a distributed lock, proves unseen cloud changes have arrived,
or makes live shared SQLite safe. Missing ownership is uncertainty, not a crash.

## Step 1 implementation

`machine_identity.py` derives a namespaced hash from OS machine identity, not
hostname, study contents or PID. Unknown/unavailable identity returns None.
New run.pid includes machine_id. Automatic reclaim checks positive local
machine ownership and matching latest run_id before entering destructive
reclaim under the same existing local settle lock. Legacy local crashes no
longer recover automatically; preserving uncertain work is the intentional cost.

Tests cover foreign/unknown markers byte-for-byte, known-local recovery, marker
writing and supported identity discovery/error handling. A factory-boundary test
executes real create_app through recovery and stops at its first writer, proving
only the pre-write recovery boundary. Existing lifecycle tests exercise full
same-machine server startup. Neither is proof that all foreign startup writes
are refused; that is step 2.

## Step 1 receipt — 28 October

Commit `e83c68c79`, branch codex/study-recovery-guard, based on main4e8cc854a.
Final regression200passed/3deselected/2expectedfail in32.81s; Ruff clean.
Independent runtime review found malformed Windows registry type could raise;
fixed with explicit type check and valid/int/None/invalid regression cases,
then rechecked clean. Logs:/tmp/bn-r114-final-{regressions,ruff}.log.
Two earlier main-checkout attempts aborted during optional native MLX hardware
imports in known-open CLI tests; not passing evidence. Explicit-run tests remain
out of this step's scope; these are among the deselected cases. No real study,
cloud provider or paid pipeline operation was tested. No push/merge/release.

## Preserved future work

The larger prototype remains on `codex/study-access-poc`, worktree
`/Users/cassio/.codex/worktrees/study-access-poc/bristlenose`. Its design owner is
`docs/design-study-read-only.md`; implementation/evidence map is
`docs/design-study-read-only-plan.md`; experiments are under
`experiments/study-access-poc/` (README, FINDINGS, HANDOVER, RESEARCH).
Canonical private tracking is `docs/private/100days.md` and
`docs/private/reviews/study-read-only.md` in the main checkout.

Park seamless handover, private writable-storage migration, automatic incoming
publication/adoption, unfinished-text recovery UI, editing re-entry and all-lens
parity. Keep immutable reader/checkpoint validation and writer inventory as
reusable tested work. Do not delete code, tests or research merely because they
are no longer prerequisites for this release. Reassess old review findings
against the capability actually selected; do not mechanically carry obligations
for removed capabilities into the minimal fix.

Return to the larger design when there is demonstrated demand for uninterrupted
cross-Mac handover, and agree a bounded end-to-end acceptance journey before
resuming implementation. Duplication/merge and cloud-provider APIs stay outside
this delivery.
