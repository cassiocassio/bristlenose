---
name: new-release
description: Ship a release — bump version, finalise changelog/readme, tag, push, and verify PyPI. The ONLY workflow command that touches public distribution (PyPI, Homebrew, the public changelog, the tag). Evening window on weekdays. Supports --dry-run.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Edit, Glob, Grep, AskUserQuestion
---

> **Shipping more than the CLI?** `/bn-release` orchestrates all channels —
> TestFlight, `.dmg`, Snap, the website — and hands back here for the CLI publish
> below. This skill remains the specialist for PyPI/tag/Homebrew and owns the
> tag-surgery decision tree; `/bn-release` deliberately does not duplicate it.

Cut a release of bristlenose. This is the **only** workflow verb that reaches the outside world. Treat it deliberately — it is the irreversible-outward one.

`$ARGUMENTS` may contain `--dry-run` (do everything except push / tag / publish — for testing).

**Instrumentation:** `bash .claude/skills/_shared/wflog.sh new-release <step> "<detail>"` at each step. `BRISTLENOSE_WORKFLOW_DEBUG=1` for verbose echo.

**Failure policy:** every step is critical — stop on failure. This command publishes; do not paper over a failed step.

## Step 1: Pre-flight

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"; hash -r 2>/dev/null || true
bash .claude/skills/_shared/wflog.sh new-release start "$ARGUMENTS"
git branch --show-current     # must be main
git status --short            # should be clean
git describe --tags --abbrev=0 2>/dev/null   # last release tag
curl -s https://pypi.org/pypi/bristlenose/json | python3 -c "import json,sys;print('PyPI now:',json.load(sys.stdin)['info']['version'])"
grep -E '__version__' bristlenose/__init__.py
gh run list --workflow=release.yml --limit 3   # did the last tag's release already fire — and fail?
```

Must be on `main` with a clean tree. If not, stop.

## Step 2: Confirm version + window

Show what landed since the last tag: `git log <lasttag>..HEAD --oneline`. Decide the new `X.Y.Z` with the user (semver: patch for fixes, minor for features).

**First decide which case you're in — they take different paths:**
- **Fresh bump (common):** `__version__` is the last *released* version and you're cutting a new `X.Y.Z`. Proceed through Step 3 → Step 4 (bump).
- **Publish-pending (already bumped, awaiting publish):** `__version__` already equals an existing local tag `vX.Y.Z` AND PyPI is *behind* it — a prior session bumped + tagged but the release never landed (deferred push, or a release run that fired and failed). **Skip Step 4 entirely — do NOT re-bump or re-tag.** Go straight to Step 5 and push `main` + the existing tag. If `git push origin vX.Y.Z` says "Everything up-to-date", the tag is already on origin → the release run already fired; check `gh run list --workflow=release.yml` for its conclusion:
  **Run this discriminator BEFORE choosing a branch — it forbids the first one:**
  ```bash
  git log vX.Y.Z..origin/main --oneline -- bristlenose/ frontend/
  ```
  Non-empty means shipped code has moved since the tag: the tagged commit is **not**
  what you now believe ships, so a rerun would publish stale code immutably. Rerun
  is then **off the table** regardless of how flaky the failure looks.

  - **fired and *failed* on a flaky/transient step, and the discriminator is empty** → `gh run rerun <id> --failed` (replays the *tagged* commit — correct only when the code is genuinely unchanged and the test just flaked).
  - **failed on something a *later* commit fixed, and nothing shipped from the tag yet** → move the tag: `git tag -f vX.Y.Z <fixed-sha> && git push --delete origin vX.Y.Z && git push origin vX.Y.Z` (fresh run on the fix).
  - **failed, a later commit fixed it, and Mac channels already shipped from the tag** → **supersede.** Leave the tag where it is (it is the accurate provenance for the TestFlight build and the published `.dmg`, and the `.dmg` manifest pins that commit — deleting it orphans the trail). Bump to `X.Y.Z+1`, rebuild every Mac artefact, and amend the superseded version's CHANGELOG entry to name the channels it reached and point at its replacement. Precedent: 0.25.0 → 0.25.1, and 0.25.2 → 0.25.3 on 10 Aug 2026.
  - Then resume Step 5's PyPI verify loop. (Worked example: 0.15.18 on 21 Jun 2026 — tag pushed at 14:35, release run failed on the flaky lifecycle test; `gh run rerun --failed` was the fix, no tag surgery. Counter-example: 0.25.2 on 9 Aug 2026 — same test, same look, but it was a genuinely incomplete fix and the discriminator was non-empty; a rerun would have published the broken half.)

**Evening rule:** releases land after 9pm London on a **working day**. If it's daytime on a working day, confirm with the user before proceeding (override is fine — it's a guideline). Weekends and **UK bank holidays: any time** — check, don't derive: `curl -s https://www.gov.uk/bank-holidays.json | jq -r --arg d "$(date +%F)" '."england-and-wales".events[] | select(.date==$d) | .title'` (non-empty = holiday, window open). Log `bash .claude/skills/_shared/wflog.sh new-release version "<X.Y.Z>"`.

## Step 3: Changelog + README (this skill OWNS the entry)

Write the release entry in `CHANGELOG.md` and the README changelog section in house format: `**X.Y.Z** — _D Mon YYYY_` (bold version, em dash, italic date, no leading zero on day, no hyphens in date). Gather the bullets from the `summary` fields `/close-feature` left in `.claude/current-task.json` for work landed since the last release, plus `git log <lasttag>..HEAD --oneline`. There is no "unreleased" buffer section — the entry appears already-dated, like the existing CHANGELOG entries.

## Step 4: Bump (writes skipped if --dry-run)

**Skip this whole step if Step 2 found the publish-pending case** (already bumped + tagged) — re-bumping a version that's already tagged is wrong. This step is only for a *fresh* bump.

```bash
./scripts/bump-version.py <X.Y.Z>   # updates __init__.py, man page .TH, pbxproj; stages them; NO commit, NO tag
git add CHANGELOG.md README.md CLAUDE.md   # + anything else you edited; bump staged the version files
git commit -m "bump to <X.Y.Z>"
git tag v<X.Y.Z>                     # AFTER the commit, so it points at it
git rev-parse HEAD; git rev-parse v<X.Y.Z>^{}   # same SHA — confirm before pushing
```

**If `--dry-run`: print exactly what would run and STOP here.** Log `bash .claude/skills/_shared/wflog.sh new-release dry-run-stop "<X.Y.Z>"`.

## Step 5: Push, verify PyPI (the part that reaches the world)

```bash
git push origin main
git push origin v<X.Y.Z>
```

> **Changed 23 Aug 2026 — the tag push IS the release.** The `pypi`
> environment's required-reviewer hold was removed. There is no approval step
> any more; `release.yml` runs to completion on a tag.

**Push `main` freely. The tag is the irreversible act — do not push it until
everything else is done.** Once it lands, `release.yml` runs CI (macOS cells
*blocking*, unlike daily pushes) and, if green, publishes to PyPI, cuts the
GitHub Release and dispatches Homebrew — with no further human step.

The gate did not go away, it stopped being a click: `publish` needs `build`
needs `ci`, and `release.yml` invokes `ci.yml` with `strict-macos: true`. PyPI
cannot receive a version whose full matrix, e2e and strict macOS suite did not
pass on the tagged commit. `check-release-ready.sh`'s `publish gate` row
asserts that chain and **fails** if it is ever broken.

To get a strict verdict *before* committing to the tag, dispatch one on `main`:

```bash
gh workflow run ci.yml --ref main -f strict-macos=true
```

That is what `./scripts/release.sh run` does, and it is what keeps every
verdict ahead of every irreversible act now that the tag publishes.

If the preflight's `publish hold` line reports a reviewer **exists**, someone
has restored the hold — the tag then publishes nothing until approved, and the
tag-last ordering above is wrong for that state.

Then the **mandatory** verify loop (a tag reaching GitHub ≠ a release reaching PyPI):

```bash
for i in $(seq 1 20); do
  sleep 90
  pypi=$(curl -s https://pypi.org/pypi/bristlenose/json | python3 -c "import json,sys;print(json.load(sys.stdin)['info']['version'])")
  echo "[$i] PyPI: $pypi"
  [ "$pypi" = "<X.Y.Z>" ] && break
done
```

20 × 90s = 30 min (recent releases run 23–25 min). If PyPI still reports the old version after 30 min, apply the tag-redelivery workaround: `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` (see CLAUDE.md "Post-push PyPI verification"). Log `bash .claude/skills/_shared/wflog.sh new-release verified "<X.Y.Z>"`.

## Step 6: Report

Summarise: version, tag, PyPI status (verified / still pending), and the Homebrew tap dispatch reminder. Log `bash .claude/skills/_shared/wflog.sh new-release done "<X.Y.Z>"`.
