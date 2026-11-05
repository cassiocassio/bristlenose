# CodeRabbit trial: does it find anything `/usual-suspects` doesn't?

**Status:** proposal, 30 Oct 2026. Nothing here has been run.

## The question

CodeRabbit's open-source plan is free for public repos. Bristlenose works on
`main` and opens no PRs, so adopting it means opening PRs as a review lane.
That is only worth doing if it finds true problems that `/usual-suspects`
(the fan-out of repo-aware review agents) does not, at an acceptable noise
cost. The trial answers that and nothing else.

Not in scope: PR summaries, walkthrough diagrams, one-click fixes. They are
real features, but they are not a reason to adopt a reviewer. If the finding
count is zero they can be judged separately, in an afternoon.

## What the docs say (read 30 Oct 2026)

Sources: docs.coderabbit.ai (`code-review-overview`, `reference/configuration`,
`reference/review-commands`, `management/plans`).

- **OSS plan:** Team features, no subscription, public repos. Rate limits are
  per repository and scale with community size: 1–10 PR reviews per developer
  per hour, 100–300 files per review, 25 chat messages per developer per hour.
- **Under 10 stars, reviews are manual only** (Trigger review button or
  `@coderabbitai review`). Bristlenose has 7 stars. That suits a trial: no
  surprise reviews, and every run is deliberate. Expect the 1 per hour end
  of the range.
- **Drafts are skipped** unless `reviews.auto_review.drafts: true`. The
  docs do not say what a manual `review` does on a draft. Measure it
  (step 3 of the run order).
- **Commands:** `review` (commits since last review), `full review` (from
  scratch), `configuration` (shows the resolved config), `rate limit`.
- **Config** (`.coderabbit.yaml`): `reviews.profile` (`quiet` / `chill` /
  `assertive`), `path_filters`, `path_instructions`,
  `reviews.tools.{ruff,semgrep,gitleaks}`, `knowledge_base.learnings.scope`
  (`auto` means local for public repos), `knowledge_base.code_guidelines`
  (on by default, so it may read `CLAUDE.md`; verify with `configuration`).
- **Not documented:** data retention and whether code is used for training.
  The code is public, so this does not block a trial, but read their privacy
  policy before pointing it at anything unpublished.

## Arms

| Arm | What | Why |
|---|---|---|
| **A** | CodeRabbit, `profile: assertive`, defaults otherwise | The thing under test. `assertive` because a trial that hides weak findings under `chill` measures the profile, not the tool |
| **B** | `/usual-suspects` against the same diff | The incumbent |
| **C** | One plain `code-review` agent, no fan-out | Separates "many repo-aware agents" from "any decent reviewer". If A ≈ C and both < B, the lore is doing the work |

Run each arm once per PR. For three PRs, run A and B a second time to see how
much of any difference is just LLM variance. Do not read a one-seed gap as a
difference.

## Corpus

Roughly 16 PRs against a throwaway public fork (see Mechanics):

- **12 seeded.** A real recent commit's diff with one defect injected, so the
  defect sits inside realistic code and is not the whole diff.
- **4 clean controls.** Real recent commits, unmodified, that have already
  passed the existing reviews. They measure false positives. Make two of
  them noise bait: a pure rename, a comment edit, formatting.

Seed strata, four each:

1. **Generic defects any reviewer should catch.** Swallowed exception,
   off-by-one, missing timeout on a subprocess, unescaped value in embedded
   JSON, mutable default argument, a test with an assertion that cannot fail.
2. **Repo-lore defects.** Taken from `.claude/gotchas.md`: each entry is a
   real incident with a known fix. Recreate it by reintroducing the bug
   (a `\d{2}` timecode reader, `git mv` after an unstaged edit, a name-to-runner
   table that skips missing names, a locale key added to 20 of 21 files).
   Repo-lore is where Arm B should win; it is the stratum that decides
   whether CodeRabbit adds anything or just duplicates a generic linter.
3. **Cross-file / contract defects.** The diff is locally fine but breaks
   something it does not touch: a route added without an export
   classification, a renamed key still used as a string literal elsewhere,
   a doc that now disagrees with the code.

Seeded PRs must stay small. The per-review file cap is 100–300 files;
anything over about 15 files measures the limit, not the reviewer.

## Single-blind seeding

If you plant the bugs you will know where they are, and you will score
generously. So an agent plants them:

1. A seeding agent (fresh context, given only the stratum and the base
   commit) picks a real commit, injects one defect of the named class, and
   writes the **answer key** to a path outside the repo. The key holds
   `id`, `file`, `line range`, `class`, `severity`, `mechanism in one
   sentence`, `what a correct fix looks like`.
2. You do not open the key until every arm has run on every PR.
3. The seed commit message and PR title are neutral and identical in
   style across all PRs. No `seed`, `bug`, `test` or `fix` in a branch,
   title or description.
4. Scoring is done on findings stripped of tool signatures and shuffled
   (CodeRabbit's badges, `[bot]` headings and walkthrough boilerplate removed;
   `/usual-suspects` agent headings removed).

Caveat: an agent that has read `CLAUDE.md` and `gotchas.md` will seed
repo-lore bugs well and generic ones in a recognisably agent-shaped way.
For stratum 1, take defects from real bugs fixed earlier in `git log`
(revert the fix) where one exists, and use the agent only to fill gaps.

## Scoring

Each seeded defect gets one of four marks per arm, set by reading the
finding against the key:

- **Miss:** nothing on the hunk, or only a generic remark about it.
- **Located:** flags the right lines but not the mechanism.
- **Diagnosed:** names the file, the lines and the mechanism. **This is a hit.**
- **Fixed:** the suggested change would actually fix it.

"Mentions the line" is not a hit. This stops a noisy reviewer scoring by
flagging everything.

Every finding that is **not** on the key is classified blind:

- **True, new:** a real problem the diff introduced beyond the seed.
- **True, pre-existing:** real, but already in the base.
- **Valid nit:** correct but not worth a change.
- **Wrong.**
- **Noise:** correct and pointless (restating the diff, praising).

For the adjudication, use a second agent on a different model from the
seeder, and spot-check its disagreements yourself. Do not adjudicate
without the shuffle.

## Measures

Per arm, and per stratum:

| Measure | Definition |
|---|---|
| **Recall** | seeded hits / 12 |
| **Unique true findings** | true findings (seeded or not) that no other arm raised |
| **Precision** | (hits + true-new) / all findings |
| **Noise per PR** | findings that are wrong or noise, per PR, and on the 4 controls alone |
| **Cost** | your minutes to triage per PR; for B and C, tokens or £; for A, nothing |
| **Variance** | A and B repeated on 3 PRs: how many findings recur |

**Unique true findings** is the headline. Recall rewards finding what is
easy; the only reason to add a tool is the problems the others missed.

## Decision rule (set now, before running)

Proposed, adjust before the first run and not after:

- **Adopt** (for outside-contributor PRs and for opt-in review of risky
  diffs) if A has at least **2 unique true findings across the 16 PRs** and
  noise on the controls is at most **2 per PR**.
- **Adopt for contributor PRs only** if A's unique true findings are 0–1
  but its recall on stratum 1 matches B's. It is then a cheap first pass
  for strangers' code, not a second opinion for yours.
- **Drop** otherwise.

With 12 seeds none of this is statistically significant. Report counts, not
p-values, and treat a gap of under about 3 seeds as a tie.

## Mechanics

1. **Fork, do not use `main`.** Create a throwaway public fork
   (`<you>/bristlenose-review-trial`) and install CodeRabbit on that repo
   only. Reasons: seeded PRs never touch the real PR list; `learnings` from
   your replies stay out of the real repo; CI can be switched off
   (Actions disabled) so 16 PRs don't run 16 full matrices. Cost: a fork has
   0 stars, so expect 1 review per hour. Spread 16 PRs over two days
   and use `@coderabbitai rate limit` to check.
2. **Work in a `git clone --local`**, not the main checkout. The index is
   shared with other sessions and the checkout hook blocks `switch`. Push
   with `git push fork <sha>:refs/heads/review/<n>`.
3. **Config on the fork's default branch**, not on the PRs, so every PR is
   reviewed under the same config: `profile: assertive`, `path_filters`
   excluding `docs/`, `bristlenose/locales/`, `frontend/node_modules/` and
   generated files. Run `@coderabbitai configuration` on the first PR and
   confirm it resolved as intended, including whether `CLAUDE.md` is read as
   a guideline.
4. **Give B the same inputs as A.** Apply the PR diff in a clean clone at the
   base commit, run `/usual-suspects` on it, do not pass the PR description.
5. **Order.** Run A first on all PRs (the rate limit is the slow part), run
   B and C meanwhile, then do the key reveal and scoring.
6. **Privacy rule stands.** Raw findings stay in the maintainer's private,
   gitignored notes. Only the method (this file) and the verified conclusion
   go public. The fork is public and holds fake bugs only; delete it at the
   end.

## What would invalidate this

- **Seeded bugs are easier than real ones.** A tool that finds planted bugs
  may still miss the subtle real ones. Stratum 2 and the real-history
  reverts reduce this; they do not remove it.
- **Both arms read `CLAUDE.md`.** If CodeRabbit ingests it, stratum 2 no longer
  separates "repo lore" from "reads the instructions". Check `configuration`;
  if it does read it, run a second pass of A with `CLAUDE.md` excluded
  through `knowledge_base.code_guidelines` and report both.
- **Model drift.** Both tools change underneath you. Run all arms within one
  week and record dates.
- **Small n.** See the decision rule. A tie is a legitimate result.
- **Your triage time is the real cost** of any extra tool, and it is the
  hardest thing to measure honestly. Time it with a clock for every PR.

## Run order

1. Fork, install, write `.coderabbit.yaml`, run `configuration`. (30 min)
2. Seeding agent produces 12 seeded + 4 control PRs and the key. (1 hr)
3. First PR only: trigger `review` as a draft and as non-draft, record
   whether a draft is reviewed. Use the answer to fix the procedure.
4. Run A across all PRs over two days; run B and C in parallel.
5. Strip, shuffle, adjudicate, reveal the key, score.
6. Write the result in the private notes; update this file's Status line
   with the verdict and the date. Delete the fork.
