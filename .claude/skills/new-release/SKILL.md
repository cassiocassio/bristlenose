---
name: new-release
description: Ship a release — bump version, finalise changelog/readme, tag, push, and verify PyPI. The ONLY workflow command that touches public distribution (PyPI, Homebrew, the public changelog, the tag). Evening window on weekdays. Supports --dry-run.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Edit, Glob, Grep, AskUserQuestion
---

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
```

Must be on `main` with a clean tree. If not, stop.

## Step 2: Confirm version + window

Show what landed since the last tag: `git log <lasttag>..HEAD --oneline`. Decide the new `X.Y.Z` with the user (semver: patch for fixes, minor for features). 

**Weekday evening rule:** releases land after 9pm London. If it's daytime on a weekday, confirm with the user before proceeding (override is fine — it's a guideline). Weekends: any time. Log `bash .claude/skills/_shared/wflog.sh new-release version "<X.Y.Z>"`.

## Step 3: Changelog + README (this skill OWNS the entry)

Write the release entry in `CHANGELOG.md` and the README changelog section in house format: `**X.Y.Z** — _D Mon YYYY_` (bold version, em dash, italic date, no leading zero on day, no hyphens in date). Gather the bullets from the `summary` fields `/close-feature` left in `.claude/current-task.json` for work landed since the last release, plus `git log <lasttag>..HEAD --oneline`. There is no "unreleased" buffer section — the entry appears already-dated, like the existing CHANGELOG entries.

## Step 4: Bump (writes skipped if --dry-run)

```bash
./scripts/bump-version.py <X.Y.Z>   # updates __init__.py, man page .TH date, creates tag at CURRENT HEAD
git tag -d v<X.Y.Z>                  # tag points at the wrong commit until the bump commit lands — delete, re-tag after commit
git add CHANGELOG.md README.md bristlenose/__init__.py   # + any other files bump-version.py staged
git commit -m "bump to <X.Y.Z>"
git tag v<X.Y.Z>
```

**If `--dry-run`: print exactly what would run and STOP here.** Log `bash .claude/skills/_shared/wflog.sh new-release dry-run-stop "<X.Y.Z>"`.

## Step 5: Push + verify PyPI (the part that reaches the world)

```bash
git push origin main
git push origin v<X.Y.Z>
```

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
