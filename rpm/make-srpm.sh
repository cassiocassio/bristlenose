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
#   BN_PYTHON=python3.14  the interpreter to build the wheelhouse WITH. This
#                         must match the TARGET chroot's python, not the
#                         builder's — see the note by the wheelhouse below.
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
# The wheelhouse is built for ONE python minor and one arch, and an SRPM is a
# single artefact shared by every chroot it is built for. A cp313 wheelhouse
# cannot satisfy a chroot running 3.14 — pip fails to resolve every heavy
# dependency at once, inside mock, where it is least convenient to discover.
#
# So the interpreter is chosen deliberately rather than inherited. Fedora 43
# ships python 3.14 and Copr no longer offers a fedora-42 chroot at all, so
# BN_PYTHON must name the target's python and .copr/Makefile installs it.
BN_PYTHON="${BN_PYTHON:-python3}"
command -v "$BN_PYTHON" >/dev/null 2>&1 || {
    echo "ERROR: BN_PYTHON=$BN_PYTHON not found." >&2
    echo "       It must be the TARGET chroot's python (Fedora 43 = python3.14)," >&2
    echo "       not whatever this builder happens to run." >&2
    exit 1
}
PYTAG="$("$BN_PYTHON" -c 'import sys; print("cp%d%d" % sys.version_info[:2])')"
echo "==> wheelhouse for $PYTAG / x86_64, built with $BN_PYTHON"
echo "    ONLY enable chroots whose python matches $PYTAG — fedora-43 is 3.14."

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
#
# THE ARCH IS PINNED TO THE TARGET, NOT INHERITED FROM THE BUILDER.
#
# This was `pip wheel`, which builds for whatever machine happens to run it.
# That held only while Copr scheduled the SRPM job on the same architecture as
# the chroot. On 31 Aug 2026 it did not: the 0.29.0 SRPM stage ran on aarch64
# (159 aarch64 references in its log, 2 x86_64) and produced a wheelhouse of
# `linux_aarch64` wheels, while the RPM stage ran in fedora-43-x86_64. Pure
# Python wheels are arch-agnostic and resolved fine; the first dependency with
# a compiled extension did not:
#
#     ERROR: Could not find a version that satisfies the requirement pyyaml>=6.0
#            (from bristlenose) (from versions: none)
#
# "from versions: none" rather than a version conflict is the signature: the
# package was present and no wheel was COMPATIBLE. Nothing in the tree changed
# — 0.28.0 built three days earlier — Copr simply moved the job. PyYAML was
# only the first of several binary wheels behind it.
#
# `pip download --platform` cannot compile, so it must find a wheel matching the
# target triple or fail. That is the point: a dependency with no manylinux
# x86_64 wheel cannot be vendored for that chroot by any means, and failing here
# — in a two-minute SRPM step with a readable log — beats failing inside mock.
# `--only-binary=:all:` is mandatory with `--platform`; pip refuses otherwise.
#
# Platform tags are listed newest-first; pip takes the best match and pure
# `py3-none-any` wheels satisfy all of them. Widen this list, do not remove the
# pin, if a chroot for another arch is ever enabled — and note the SRPM is ONE
# artefact shared by every chroot, so a second arch needs a second wheelhouse,
# not a longer list.
BN_TARGET_PY="${BN_TARGET_PY:-3.14}"
echo "==> building wheelhouse for cp${BN_TARGET_PY//./} / x86_64 (the slow part, ~2 min)"
mkdir -p "$WORK/vendor"

# PASS A — the sdist-only dependencies, built here.
#
# `--only-binary=:all:` below cannot install what PyPI publishes as an sdist and
# nothing else, and pysrt is exactly that (1.1.2: sdist, no wheel). It is pure
# Python, so building it locally yields `py3-none-any`, which satisfies every
# arch — the thing that is NOT true of a compiled extension, and the whole
# reason pass B exists.
#
# This list is deliberately explicit rather than derived. When a new dependency
# is sdist-only, pass B fails naming it, and the choice — add it here if pure
# Python, or reconsider the dependency if it compiles — is one a human should
# make. A compiled sdist added here would silently reintroduce the arch bug.
BN_SDIST_ONLY=("pysrt>=1.1")
echo "    pass A: ${#BN_SDIST_ONLY[@]} sdist-only package(s) built locally"
"$BN_PYTHON" -m pip wheel --quiet --wheel-dir="$WORK/vendor" --no-cache-dir --no-deps \
    "${BN_SDIST_ONLY[@]}"
for _w in "${BN_SDIST_ONLY[@]}"; do
    _n="${_w%%[<>=!]*}"
    ls "$WORK/vendor/${_n//-/_}"-*-py3-none-any.whl >/dev/null 2>&1 \
        || ls "$WORK/vendor/${_n}"-*-py3-none-any.whl >/dev/null 2>&1 \
        || { echo "error: $_n did not build to py3-none-any — it is not pure Python," >&2
             echo "       so vendoring it here would ship the builder's arch." >&2; exit 1; }
done

# PASS B — everything else, for the TARGET platform, satisfying pass A from
# --find-links so pip does not try to fetch pysrt from an index that has no
# wheel for it.
echo "    pass B: the rest, as x86_64 wheels"
"$BN_PYTHON" -m pip download --quiet --dest="$WORK/vendor" --no-cache-dir \
    --find-links="$WORK/vendor" \
    --only-binary=:all: \
    --python-version "$BN_TARGET_PY" \
    --implementation cp \
    --platform manylinux_2_28_x86_64 \
    --platform manylinux_2_17_x86_64 \
    --platform manylinux2014_x86_64 \
    "bristlenose[serve]==$VERSION" || {
        echo "error: could not vendor every dependency as an x86_64 wheel." >&2
        echo "       A 'from versions: none' here means the package has no" >&2
        echo "       manylinux x86_64 wheel for cp${BN_TARGET_PY//./} — it cannot be" >&2
        echo "       vendored for that chroot at all. Check the named package on" >&2
        echo "       PyPI before widening the platform list." >&2
        exit 1
    }

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
"$BN_PYTHON" -m pip wheel --quiet --wheel-dir="$WORK/vendor" --no-cache-dir --no-deps \
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

# Sibling assertion, and the one 0.29.0 needed. Every wheel must target the
# CHROOT, not the builder: pure Python (`-any`) or glibc x86_64. `musllinux` is
# x86_64 with the wrong libc, so it is named out explicitly rather than trusted
# to the suffix. This runs after the spaCy and BN_LOCAL_DIST additions so it
# covers the whole wheelhouse, and it costs milliseconds — the alternative is
# finding out inside mock, where the message is a resolution error naming one
# arbitrary dependency and nothing about architecture at all.
find "$WORK/vendor" -maxdepth 1 -name '*.whl' \
    \( \( ! -name '*-any.whl' ! -name '*x86_64.whl' \) -o -name '*musllinux*' \) \
    > "$WORK/wrongarch"
if [ -s "$WORK/wrongarch" ]; then
    echo "ERROR: wheels are built for the wrong platform. The SRPM job and the" >&2
    echo "       chroot disagree about architecture; these cannot install in" >&2
    echo "       fedora-43-x86_64:" >&2
    cat "$WORK/wrongarch" >&2
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
