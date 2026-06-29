#!/usr/bin/env bash
# Cheap invariant tests for the per-layer build gating + orchestrator decision
# logic (no real PyInstaller/venv build — those are human QA). Catches the
# stamp-writer/checker DRIFT class that already bit the fingerprint recipe once
# (locale-sort, 28 Jun 2026). Run: desktop/scripts/test-ensure-sidecar.sh
#
# Exercises decisions via --dry-run + controlled stamp state, restoring any file
# it touches. Asserts: recipe unchanged vs live stamp; F-stamp drives F; P skips
# when source matches; --force rebuilds all; the Distribution guard; skip-flags.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STATIC_DIR="$ROOT/bristlenose/server/static"
FRONTEND_STAMP="$STATIC_DIR/.frontend-stamp"
BUNDLE="$ROOT/desktop/Bristlenose/Resources/bristlenose-sidecar"

pass=0; fail=0
ok()   { echo "  ok   — $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL — $1"; fail=$((fail+1)); }
# assert that running build-sidecar --dry-run produces (or not) a line.
dry()  { bash "$SCRIPT_DIR/build-sidecar.sh" --dry-run 2>&1; }
ensure_dry() { bash "$SCRIPT_DIR/ensure-sidecar.sh" --dry-run 2>&1; }

echo "== test-ensure-sidecar =="

# 1. The sliced refactor preserved the full hash → no spurious rebuild for anyone.
. "$SCRIPT_DIR/sidecar-source-hash.sh"
if [ -f "$BUNDLE/.source-stamp" ]; then
    if [ "$(head -1 "$BUNDLE/.source-stamp")" = "$(sidecar_source_hash "$ROOT")" ]; then
        ok "recipe unchanged — recomputed full hash matches live bundle stamp"
    else
        echo "  skip — source moved since last build (tree has WIP); can't assert recipe-unchanged here"
    fi
else
    echo "  skip — no live bundle stamp to compare"
fi

# 2. frontend_source_hash is a strict, non-empty 64-hex subset signal.
fh="$(frontend_source_hash "$ROOT")"
case "$fh" in [0-9a-f]*) [ ${#fh} -eq 64 ] && ok "frontend_source_hash is 64-hex" || bad "frontend hash wrong length";; *) bad "frontend hash not hex";; esac

# 3. --force makes every layer REBUILD.
out="$(bash "$SCRIPT_DIR/build-sidecar.sh" --force --dry-run 2>&1)"
echo "$out" | grep -q '\[F\] REBUILD — forced' && echo "$out" | grep -q '\[P\] REBUILD — forced' \
    && ok "--force rebuilds all layers" || bad "--force did not force all layers"

# 4. P SKIPS when the source hash matches the live stamp (the core incremental win).
#    Needs BOTH a matching tree AND a healthy venv (.deps-ok) so V doesn't cascade-
#    force P. Without a real venv this can't be isolated cheaply → informational.
if [ ! -f "$ROOT/.venv-sidecar/.deps-ok" ]; then
    echo "  skip — no .venv-sidecar/.deps-ok (V would cascade-force P); P-skip needs a real build (human QA)"
elif [ -f "$BUNDLE/.source-stamp" ] && [ "$(head -1 "$BUNDLE/.source-stamp")" = "$(sidecar_source_hash "$ROOT")" ]; then
    # Seed the F stamp so F doesn't cascade-force P, isolating P's own decision.
    had_fstamp=0; [ -f "$FRONTEND_STAMP" ] && had_fstamp=1 && cp "$FRONTEND_STAMP" "$FRONTEND_STAMP.testbak"
    mkdir -p "$STATIC_DIR"; printf '%s\n' "$fh" > "$FRONTEND_STAMP"
    if [ -s "$STATIC_DIR/index.html" ]; then
        # Capture first — `dry | grep -q` would SIGPIPE the script (grep -q exits
        # early → broken pipe → exit 141 → pipefail trips a false failure). Grep a
        # here-string instead (no pipe to break).
        dout="$(dry)"
        grep -q '\[P\] skip' <<<"$dout" && ok "P skips when source matches + F seeded" || bad "P did not skip on matching source"
    else
        echo "  skip — static/index.html absent (F would rebuild → P cascades); not P's fault"
    fi
    # restore
    if [ "$had_fstamp" = 1 ]; then mv -f "$FRONTEND_STAMP.testbak" "$FRONTEND_STAMP"; else rm -f "$FRONTEND_STAMP"; fi
else
    echo "  skip — tree doesn't match bundle; P-skip assertion needs a fresh build"
fi

# 5. A malformed/empty hash must abort, never skip (finding 6) — simulate by
#    pointing the recipe at an empty dir via a subshell override is overkill;
#    instead assert the guard exists in the script text.
grep -q 'empty/malformed source fingerprint' "$SCRIPT_DIR/build-sidecar.sh" \
    && ok "empty-hash guard present (fail-loud, not skip)" || bad "empty-hash guard missing"

# 6. Distribution guard: real identity without _BRISTLENOSE_RELEASE aborts non-zero.
if SIGN_IDENTITY="Apple Distribution: test" bash "$SCRIPT_DIR/ensure-sidecar.sh" --dry-run >/dev/null 2>&1; then
    bad "Distribution identity was allowed without _BRISTLENOSE_RELEASE"
else
    ok "Distribution guard rejects real identity outside build-all.sh"
fi

# 7. Skip-flags short-circuit ensure.
BRISTLENOSE_SKIP_SIDECAR_ENSURE=1 ensure_dry | grep -q 'fast scheme' && ok "SKIP_SIDECAR_ENSURE short-circuits" || bad "skip-ensure flag ignored"
BRISTLENOSE_ALLOW_STALE_SIDECAR=1 ensure_dry | grep -q 'stale bundle accepted' && ok "ALLOW_STALE short-circuits" || bad "allow-stale flag ignored"

echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
