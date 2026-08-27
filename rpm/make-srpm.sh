#!/bin/bash
# Build the Bristlenose source RPM.
#
# This is the half of the build that HAS network. Copr runs it via
# .copr/Makefile in a container where PyPI is reachable; mock, where the
# binary RPM is then built, has no network at all. So everything the build
# needs must be inside the SRPM by the time this script finishes.
#
# Usage: rpm/make-srpm.sh [outdir]        (default: dist/srpm)
#
# Env:
#   BN_LOCAL_DIST=<dir>   build against a locally-built sdist + wheel in <dir>
#                         instead of PyPI. The Copr build needs the version to
#                         exist on PyPI already, so this is how you prove a
#                         release candidate packages correctly BEFORE tagging
#                         it — `python -m build` then point this at dist/.
#
# Design: docs/design-fedora-packaging.md
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTDIR="$(mkdir -p "${1:-$REPO/dist/srpm}" && cd "${1:-$REPO/dist/srpm}" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The version comes from bristlenose/__init__.py and nowhere else — same rule
# the snap follows with adopt-info. Read it without importing the package, so
# this works on a builder with none of the dependencies installed.
VERSION="$(sed -n 's/^__version__ *= *["'"'"']\([^"'"'"']*\)["'"'"'].*/\1/p' \
           "$REPO/bristlenose/__init__.py" | head -1)"
[ -n "$VERSION" ] || { echo "could not read __version__ from bristlenose/__init__.py" >&2; exit 1; }
echo "==> bristlenose $VERSION"

# The vendored wheels are built for ONE Python minor and one arch, and an SRPM
# is a single artefact shared by every chroot it is built for. So a wheelhouse
# made here on 3.13 cannot satisfy a chroot running 3.14. Enable only chroots
# whose Python matches this builder's, or regenerate per release.
PYTAG="$(python3 -c 'import sys; print("cp%d%d" % sys.version_info[:2])')"
echo "==> wheelhouse for $PYTAG / x86_64 (chroots MUST match this Python)"

# --- Source0: the PyPI sdist -------------------------------------------------
# Deliberately the sdist and not a git archive: it carries the built React SPA
# (gitignored in the tree, declared as a hatch artifact and built by
# release.yml before `python -m build`), so mock needs no Node.js.
if [ -n "${BN_LOCAL_DIST:-}" ]; then
    echo "==> using local dist: $BN_LOCAL_DIST (NOT PyPI)"
    cp "$BN_LOCAL_DIST/bristlenose-$VERSION.tar.gz" "$WORK/"
else
    echo "==> fetching sdist"
    curl -fsSL --retry 3 \
      "https://pypi.io/packages/source/b/bristlenose/bristlenose-$VERSION.tar.gz" \
      -o "$WORK/bristlenose-$VERSION.tar.gz"
fi

# Fail loud if the sdist we just pulled is missing the bundle — a Copr build
# that silently ships a serve mode which 500s is worse than no package.
#
# List to a file rather than piping into grep. Under `set -o pipefail`, a
# `tar | grep -q` says FAILED when it succeeds: grep -q exits on the first
# match, tar takes SIGPIPE, and pipefail reports tar's 141 for the whole
# pipeline. That inverted this very check on its first run.
tar tzf "$WORK/bristlenose-$VERSION.tar.gz" > "$WORK/sdist.list"
if ! grep -q "bristlenose/server/static/index.html" "$WORK/sdist.list"; then
    echo "ERROR: sdist $VERSION has no bristlenose/server/static/index.html." >&2
    echo "       The release did not build the frontend before packaging." >&2
    exit 1
fi

# --- Source1: the wheelhouse -------------------------------------------------
echo "==> building wheelhouse (this is the slow part, ~2 min)"
mkdir -p "$WORK/vendor"
python3 -m pip wheel --quiet --wheel-dir="$WORK/vendor" --no-cache-dir \
    "bristlenose[serve]==$VERSION"

# A local wheel must overwrite the PyPI one pip just resolved for the
# dependency graph, or %install silently packages the published build.
if [ -n "${BN_LOCAL_DIST:-}" ]; then
    rm -f "$WORK/vendor/bristlenose-$VERSION-"*.whl
    cp "$BN_LOCAL_DIST/bristlenose-$VERSION-"*.whl "$WORK/vendor/"
    echo "    substituted the local bristlenose wheel"
fi

# spaCy's model ships from the spacy-models GitHub releases, not PyPI, so it
# has to be named by URL. Bristlenose needs it for --redact-pii; the snap
# bundles it for the same reason.
SPACY_MODEL="en_core_web_sm-3.8.0"
echo "==> adding spaCy model $SPACY_MODEL"
python3 -m pip wheel --quiet --wheel-dir="$WORK/vendor" --no-cache-dir --no-deps \
    "https://github.com/explosion/spacy-models/releases/download/${SPACY_MODEL}/${SPACY_MODEL}-py3-none-any.whl"

# %install runs `pip install --no-index`, which cannot build an sdist without
# reaching for setuptools over the network. `pip wheel` above should have left
# only wheels; assert it, rather than discovering it inside mock.
# (same pipefail caution as above — no `| grep -q`)
find "$WORK/vendor" -maxdepth 1 -type f ! -name '*.whl' > "$WORK/nonwheels"
if [ -s "$WORK/nonwheels" ]; then
    echo "ERROR: non-wheel artefacts in the wheelhouse — mock cannot build these:" >&2
    cat "$WORK/nonwheels" >&2
    exit 1
fi
echo "    $(find "$WORK/vendor" -name '*.whl' | wc -l) wheels, $(du -sh "$WORK/vendor" | cut -f1)"

tar -czf "$WORK/bristlenose-vendor-$VERSION.tar.gz" -C "$WORK" vendor

# --- the spec ----------------------------------------------------------------
sed "s/@VERSION@/$VERSION/g" "$REPO/rpm/bristlenose.spec.in" > "$WORK/bristlenose.spec"

echo "==> rpmbuild -bs"
rpmbuild -bs "$WORK/bristlenose.spec" \
    --define "_topdir $WORK/rpmbuild" \
    --define "_sourcedir $WORK" \
    --define "_srcrpmdir $OUTDIR" \
    --define "dist %{nil}" \
  | sed 's/^/    /'

ls -la "$OUTDIR"/*.src.rpm
