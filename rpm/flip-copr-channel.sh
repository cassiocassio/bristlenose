#!/bin/bash
# Turn the Fedora Copr channel ON — after it is real, never before.
#
#   rpm/flip-copr-channel.sh <X.Y.Z>
#
# WHY THIS IS A SCRIPT AND NOT A CHECKLIST
#
# The whole channel is gated on one ordering that does not commute: the public
# docs promise `dnf copr enable` works, so they must not land until it does.
# That rule was written into docs/design-fedora-packaging.md §7 and then broken
# in the same commit that wrote it — INSTALL.md and README.md shipped the
# command while the Copr project still returned 404, and only a docs-truing
# pass caught it. Prose did not enforce it. This does: every precondition below
# is checked against the live service, and the script refuses rather than warns.
#
# WHAT IT DOES NOT DO
#
# Nothing irreversible, and nothing it cannot verify. It does not create the
# Copr project, trigger a build, add repo secrets, commit, push, or touch the
# website repo — those are named at the end for a human. It only makes the
# in-repo edits that become TRUE once the checks above them pass.
#
# Design: docs/design-fedora-packaging.md §7.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
. scripts/project.conf

VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "usage: rpm/flip-copr-channel.sh <X.Y.Z>" >&2; exit 2; }

R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; N=$'\033[0m'
ok()   { printf '  %b✓%b %s\n' "$G" "$N" "$1"; }
die()  { printf '  %b✗%b %s\n' "$R" "$N" "$1" >&2; exit 1; }
note() { printf '  %b·%b %s\n' "$Y" "$N" "$1"; }

printf '\n\033[1mFlip the Copr channel on · %s\033[0m\n\n' "$VERSION"

# ── Preconditions. Every one is a reason the docs would otherwise lie. ───────

grep -q 'CHANNELS=.*[" ]copr[" ]' scripts/project.conf 2>/dev/null \
    && die "copr is already in CHANNELS — this flip has already been done"
ok "copr is not yet in CHANNELS"

# The project must exist. A 404 here is the exact state that made the reverted
# docs false, so it is checked first and fatally.
_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 \
    "https://copr.fedorainfracloud.org/api_3/project?ownername=${COPR_OWNER}&projectname=${COPR_PROJECT}" \
    || echo 000)
[ "$_code" = "200" ] || die "Copr project ${COPR_OWNER}/${COPR_PROJECT} → HTTP ${_code} (need 200). Create it and build first."
ok "Copr project ${COPR_OWNER}/${COPR_PROJECT} exists"

# ...and must have a SUCCEEDED build of THIS version. A build that failed, or
# built something else, must not turn the channel on.
_built=$(curl -s --max-time 30 "$COPR_BUILDS" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for b in (d.get('items') or []):
    if b.get('state')=='succeeded':
        v=(b.get('source_package') or {}).get('version') or ''
        if v: print(v.split('-')[0]); break
" 2>/dev/null || true)
[ -n "$_built" ] || die "no succeeded build in the Copr project yet"
[ "$_built" = "$VERSION" ] || die "latest succeeded Copr build is ${_built}, not ${VERSION}"
ok "Copr has a succeeded build of ${VERSION}"

# PyPI must have it too — Source0 comes from there, so a Copr build of a
# version PyPI lacks would mean someone built from something else.
_pypi=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 \
    "https://pypi.org/pypi/${PROJECT_NAME}/${VERSION}/json" || echo 000)
[ "$_pypi" = "200" ] || die "PyPI does not have ${VERSION} (HTTP ${_pypi}) — the Copr build cannot be trusted"
ok "PyPI has ${VERSION}"

# The CI job needs two secrets. Without them a trigger-copr job reddens every
# release, which is worse than having no job at all.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    _secrets=$(gh secret list --json name --jq '.[].name' 2>/dev/null || true)
    for _s in COPR_LOGIN COPR_TOKEN; do
        printf '%s\n' "$_secrets" | grep -qx "$_s" \
            || die "repo secret ${_s} is not set — add it before wiring trigger-copr"
    done
    ok "repo secrets COPR_LOGIN and COPR_TOKEN are set"
else
    die "gh unavailable or unauthenticated — cannot verify the repo secrets exist"
fi

echo

# ── The edits. Only reached when every check above passed. ──────────────────

python3 - "$VERSION" <<'PYEOF'
import re, sys
version = sys.argv[1]

def edit(path, old, new):
    s = open(path).read()
    n = s.count(old)
    if n != 1:
        sys.exit("REFUSING: expected 1 anchor in %s, found %d — the file has drifted, "
                 "re-derive the edit by hand rather than letting this guess." % (path, n))
    open(path, "w").write(s.replace(old, new))
    print("  edited %s" % path)

# 1. The channel itself. probe_copr and the check-release-ready token gate are
#    both already written and tested; they activate off this one word.
edit("scripts/project.conf",
     'CHANNELS="pypi github homebrew testflight dmg snap website"',
     'CHANNELS="pypi github homebrew testflight dmg snap copr website"')

# 2. INSTALL.md — Copr becomes the Fedora path, pipx kept below it.
edit("INSTALL.md",
"""### Fedora

```bash
sudo dnf install pipx ffmpeg-free
pipx ensurepath
```

Close and reopen your terminal, then:

```bash
pipx install bristlenose
```
""",
"""### Fedora

```bash
sudo dnf copr enable cassiocassio/bristlenose
sudo dnf install bristlenose
```

Copr is Fedora's community build service — the equivalent of a PPA. The first command adds
the repository, the second installs from it, and `sudo dnf upgrade` keeps it current.

The package bundles Python and everything Bristlenose needs, and pulls FFmpeg from Fedora's
own repositories. It is built for **x86_64 only** — on ARM, use pipx below.

#### Fedora without Copr

```bash
sudo dnf install pipx ffmpeg-free
pipx ensurepath
```

Close and reopen your terminal, then:

```bash
pipx install bristlenose
```
""")

# 3. README — the install block and the Linux line.
edit("README.md",
"""# Ubuntu / Debian and most other distros (Snap) -- bundles Python + FFmpeg
sudo snap install bristlenose --edge
""",
"""# Ubuntu / Debian and most other distros (Snap) -- bundles Python + FFmpeg
sudo snap install bristlenose --edge

# Fedora (Copr) -- bundles Python, pulls FFmpeg from Fedora's own repos
sudo dnf copr enable cassiocassio/bristlenose
sudo dnf install bristlenose
""")
edit("README.md",
     "The Snap is **amd64 only** — on ARM Linux, use pipx.",
     "The Snap and the Fedora package are both **amd64/x86_64 only** — on ARM Linux, use pipx.")
edit("README.md",
     "- **Linux** -- pipx works today; the Snap ships on the edge channel (`snap install bristlenose --edge`)",
     "- **Linux** -- pipx works today; the Snap ships on the edge channel (`snap install bristlenose --edge`), and Fedora has a Copr (`dnf copr enable cassiocassio/bristlenose`)")
PYEOF

echo
ok "in-repo edits applied"
echo
printf '\033[1mStill for a human — none of it is in this repo:\033[0m\n'
note "1. Add the trigger-copr job to .github/workflows/release.yml."
note "   It MUST be \`needs: verify-pypi\`, not \`needs: publish\` — Copr fetches"
note "   Source0 during the build and would race PyPI's CDN. YAML is in"
note "   docs/design-fedora-packaging.md §7."
note "2. Website repo (separate): restore the Fedora section in docs-src/install.md"
note "   and the Copr line on the homepage Linux panel, then ./deploy.sh."
note "3. Update the five channel enumerations that say three channels and will now"
note "   be wrong: docs/ROADMAP.md, docs/ARCHITECTURE.md (x3),"
note "   docs/design-bn-release-skill.md, docs/design-deployment-targets.md."
note "4. Run: scripts/verify-channels.sh ${VERSION} — the copr row should be green."
echo
printf '  Review with \033[1mgit diff\033[0m, then commit. Nothing here has been committed.\n\n'
