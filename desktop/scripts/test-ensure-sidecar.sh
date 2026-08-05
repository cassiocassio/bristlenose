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

# 8. Race gate: the build must notice the tree moving under it (a hashed file
#    saved mid-build → the bundle silently lacks that edit). Firing it needs a
#    real multi-minute build, so assert the guard exists — plus, behaviourally,
#    the precondition it rests on: the fingerprint must IGNORE the generated
#    bristlenose/_build_info.py, which is on disk from the PyInstaller step until
#    build-sidecar.sh's EXIT trap removes it. If that ever counted again, the gate
#    would cry wolf on every single build.
grep -q 'source changed while the sidecar was building' "$SCRIPT_DIR/build-sidecar.sh" \
    && ok "race gate present (entry vs end-of-build fingerprint)" || bad "race gate missing"

BUILD_INFO="$ROOT/bristlenose/_build_info.py"
if [ -e "$BUILD_INFO" ]; then
    echo "  skip — bristlenose/_build_info.py on disk (killed build?); can't isolate its effect"
else
    before="$(sidecar_source_hash "$ROOT")"
    printf 'GIT_SHA = "test"\nBUILD_DATE = "test"\n' > "$BUILD_INFO"
    after="$(sidecar_source_hash "$ROOT")"
    rm -f "$BUILD_INFO"
    [ "$before" = "$after" ] \
        && ok "fingerprint ignores generated _build_info.py (race gate can't false-positive)" \
        || bad "generated _build_info.py drifts the fingerprint — race gate would fire on every build"
fi

# Case 9 — every repo-rooted `datas` entry in the spec is covered by the
# fingerprint recipe.
#
# This is the assertion whose ABSENCE let two false-green gates ship. The
# fingerprint hashed `bristlenose/**/*.py` plus a hand-maintained list of data
# dirs, and `bristlenose/theme` (5 Aug) then `llm/prompts`, `server/codebook`,
# `data` and `cohort-baselines.json` (same day) were each missing from it — so
# editing a stylesheet or an LLM prompt left the hash unmoved,
# check-sidecar-freshness.sh said "✓ matches source", Xcode skipped the
# rebuild, and the .app served the old file. Nothing failed; the gate simply
# answered wrongly.
#
# Every other case here tests the machinery's *behaviour*. This one tests its
# *coverage* — the mirror of check-bundle-manifest.sh's source→spec direction,
# closing spec→fingerprint. Written as "for each thing the spec bundles, prove
# a change to it moves the hash", because that is the property that matters and
# it cannot be satisfied by a recipe that merely looks complete.
echo "-- case 9: fingerprint covers every bundled data path"
spec_paths="$(
    grep -oE 'os\.path\.join\(PROJECT_ROOT, "bristlenose"(, "[a-z_-]+")*(, "[a-zA-Z0-9_.-]+")?\)' \
        "$ROOT/desktop/bristlenose-sidecar.spec" \
    | sed -e 's/os\.path\.join(PROJECT_ROOT, //' -e 's/)$//' -e 's/"//g' -e 's/, /\//g' \
    | sort -u
)"
if [ -z "$spec_paths" ]; then
    bad "case 9 could not parse any PROJECT_ROOT datas paths out of the spec"
else
    uncovered=""
    for rel in $spec_paths; do
        target="$ROOT/$rel"
        [ -e "$target" ] || continue
        # `server/static*` are BUILD OUTPUT (gitignored, regenerated by
        # `npm run build` inside build-sidecar.sh), not source — the frontend
        # slice already fingerprints their inputs, and hashing the output would
        # move the hash on every build. Everything else must be covered.
        case "$rel" in bristlenose/server/static*) continue ;; esac
        probe="$target"
        [ -d "$target" ] && probe="$(find "$target" -type f -not -name '.DS_Store' -not -name '._*' | head -1)"
        [ -n "$probe" ] && [ -f "$probe" ] || continue
        before="$(sidecar_source_hash "$ROOT")"
        cp "$probe" "$probe.bnprobe"
        printf '\n' >> "$probe"
        after="$(sidecar_source_hash "$ROOT")"
        mv "$probe.bnprobe" "$probe"
        [ "$before" = "$after" ] && uncovered="$uncovered $rel"
    done
    [ -z "$uncovered" ] \
        && ok "every bundled data path moves the fingerprint when edited" \
        || bad "spec bundles these but the fingerprint ignores them —"$'\n'"      editing one ships stale while the gate reports fresh:$uncovered"
fi

echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
