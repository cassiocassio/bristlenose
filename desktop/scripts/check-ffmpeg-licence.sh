#!/usr/bin/env bash
# Gate: is each FFmpeg binary given an LGPL-2.1-or-later build?
#
# The Mac app ships under Apple's EULA, which a GPL binary can't go out under.
# Until 25 Nov 2026 the bundle carried martin-riedl.de's GPL build (--enable-gpl,
# libx264, libx265), and THIRD-PARTY-BINARIES.md called it LGPL; nothing checked.
# build-ffmpeg-lgpl.sh gates what it builds and fetch-ffmpeg.sh --check what sits
# in Resources/, but neither looks at the bundle that ships. This does: build-all.sh
# runs it on the exported .app and check-pkg-shippable.sh on the .pkg's payload.
#
# It reads what `ffmpeg -buildconf` and `ffmpeg -L` would print, from the binary's
# strings: a binary signed with the sandbox entitlements exits 133 with no output
# when run outside the app. Two independent readings, both must pass:
#   1. every embedded configure line (the one holding --prefix=) is free of
#      --enable-gpl, --enable-nonfree, --enable-version3, --enable-libx264 and
#      --enable-libx265, and there is at least one such line;
#   2. every "lib<name> license:" string, which configure derives from those
#      flags, says "LGPL version 2.1 or later", and there is at least one.
# A binary that has neither is refused: unreadable is not the same as clean.
#
# Usage:   check-ffmpeg-licence.sh <binary> [<binary>...]
# Exit:    0 all LGPL-2.1+, 1 at least one is not (the reason is printed), 2 usage.
set -euo pipefail

if [ $# -eq 0 ]; then
    echo "usage: $(basename "$0") <ffmpeg-binary> [<binary>...]" >&2
    exit 2
fi

FORBIDDEN_FLAG='--enable-(gpl|nonfree|version3|libx264|libx265)'
WANT_LICENCE='LGPL version 2.1 or later'
bad=0

for bin in "$@"; do
    name="${bin##*/}"
    if [ ! -f "$bin" ]; then
        echo "✗ $name: not found at $bin" >&2; bad=1; continue
    fi
    # Herestrings, not pipes: under pipefail `strings | grep -q` can read a found
    # match as a failure once grep closes the pipe early.
    text="$(strings -a "$bin")"
    cfgs="$(grep -e '--prefix=' <<<"$text" || true)"
    if [ -z "$cfgs" ]; then
        echo "✗ $name: no embedded configure line; can't tell how it was built" >&2; bad=1; continue
    fi
    # One flag per line, quotes stripped, so adjacent flags can't share a separator.
    hit="$(tr -s "[:space:]'\"" '\n' <<<"$cfgs" | grep -xE -e "$FORBIDDEN_FLAG" | sort -u | paste -sd' ' - || true)"
    if [ -n "$hit" ]; then
        echo "✗ $name: configured with $hit" >&2; bad=1; continue
    fi
    lic="$(grep -E '^lib[a-z0-9_]+ license: ' <<<"$text" | sort -u || true)"
    if [ -z "$lic" ]; then
        echo "✗ $name: no embedded licence strings; can't tell its licence" >&2; bad=1; continue
    fi
    other="$(grep -v -F -- "license: $WANT_LICENCE" <<<"$lic" || true)"
    if [ -n "$other" ]; then
        echo "✗ $name: $(head -1 <<<"$other")" >&2; bad=1; continue
    fi
    echo "✓ $name: $WANT_LICENCE"
done

exit "$bad"
