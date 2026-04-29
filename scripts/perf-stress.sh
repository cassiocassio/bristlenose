#!/usr/bin/env bash
#
# Orchestrate the Bristlenose stress test:
#   1. Generate synthetic fixture (or reuse with --skip-generate)
#   2. Nuke the SQLite cache so serve re-imports from scratch
#   3. Pre-flight: refuse to run if port 8153 is occupied (stale-server trap)
#   4. Start `bristlenose serve`, capturing PID + startup time
#   5. Identity guard: confirm we hit the fixture we just wrote, not a zombie
#   6. Run Playwright stress spec (DOM + API + export measurements)
#   7. Optional: Lighthouse against /report/quotes/
#   8. Print summary, clean up via a single EXIT trap
#
# Flags:
#   --quotes N          Total quote count (default 1500).
#   --skip-generate     Reuse the existing fixture directory.
#   --with-lighthouse   Also run Lighthouse against /report/quotes/.
#   --baseline          Mark this run as a baseline (reserved for future use).
#   -v, --verbose       Noisy mode: set -x, Playwright "list" reporter,
#                       response-side curl metrics + headers on the export
#                       fetch.  Server stdout stays suppressed (auth token).
#   -h, --help          Print this block and exit.
#
# Results go under trial-runs/stress-test-<N>/perf-baselines/.
# See docs/design-perf-stress-test.md for the full plan.

set -euo pipefail

# ---------------------------------------------------------------------------
# Flags + defaults
# ---------------------------------------------------------------------------

QUOTES=1500
SKIP_GENERATE=false
WITH_LIGHTHOUSE=false
BASELINE=false
VERBOSE=false
# Ephemeral port picked from the kernel at runtime.  A hardcoded port is
# race-able: between `lsof :PORT` and `bristlenose serve` binding, a
# same-UID process can sneak in and receive our bearer token.  A random
# ephemeral port closes that window for any attacker who can't read
# stdout/stderr of this script.  Filled in below after Python exists.
PORT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quotes) QUOTES="$2"; shift 2 ;;
    --skip-generate) SKIP_GENERATE=true; shift ;;
    --with-lighthouse) WITH_LIGHTHOUSE=true; shift ;;
    --baseline) BASELINE=true; shift ;;
    -v|--verbose) VERBOSE=true; shift ;;
    -h|--help)
      # Print the header comment block (lines 2 through the last doc line).
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Shell trace under --verbose.  Enable late so flag parsing isn't traced.
if [[ "$VERBOSE" == "true" ]]; then
  set -x
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

FIXTURE_DIR="trial-runs/stress-test-${QUOTES}"
RESULTS_DIR="${FIXTURE_DIR}/perf-baselines"
# Server stderr lives OUTSIDE the results tree so it can't be swept up by
# an upload-artifact rule, and so uvicorn tracebacks that happen to touch
# os.environ (which holds _BRISTLENOSE_AUTH_TOKEN) don't land in a path
# someone might archive.  The cleanup trap copies a redacted version
# into the results tree for post-run debugging.  Force umask 077 during
# creation for defence in depth against same-UID snooping.
_prev_umask=$(umask)
umask 077
SERVER_ERR_RAW="$(mktemp "${TMPDIR:-/tmp}/bristlenose-stress-server.XXXXXX")"
umask "$_prev_umask"
SERVER_ERR_REDACTED="${RESULTS_DIR}/server.err"

# ---------------------------------------------------------------------------
# Redaction helper — substitutes the actual token value (safest: no regex
# guessing at header casing or whitespace) plus the Authorization header
# case-insensitively as defence in depth.  token_urlsafe() output is
# `[A-Za-z0-9_-]` so none of its characters are sed metacharacters.
# ---------------------------------------------------------------------------

_redact() {
  local tok="${_BRISTLENOSE_AUTH_TOKEN:-___NO_TOKEN_YET___}"
  sed -E \
    -e "s|${tok}|[REDACTED]|g" \
    -e 's/([Aa]uthorization:[[:space:]]+[Bb]earer)[[:space:]]+[A-Za-z0-9_-]+/\1 [REDACTED]/g'
}

# ---------------------------------------------------------------------------
# Cleanup trap — one function, installed once, so later sections can extend
# the list of things to clean without clobbering prior traps.
# ---------------------------------------------------------------------------

SERVER_PID=""
EXPORT_FILE=""

cleanup() {
  local rc=$?
  if [[ -n "${EXPORT_FILE:-}" && -f "$EXPORT_FILE" ]]; then
    rm -f "$EXPORT_FILE"
  fi
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
  # Preserve a redacted copy of server stderr for post-run debugging; then
  # shred the raw file.  A failing run is precisely when the log matters.
  if [[ -n "${SERVER_ERR_RAW:-}" && -f "$SERVER_ERR_RAW" ]]; then
    if [[ -n "${RESULTS_DIR:-}" && -d "$RESULTS_DIR" ]]; then
      _redact < "$SERVER_ERR_RAW" > "$SERVER_ERR_REDACTED" 2>/dev/null || true
    fi
    rm -f "$SERVER_ERR_RAW"
  fi
  wait 2>/dev/null || true
  return "$rc"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 1. Generate fixture
# ---------------------------------------------------------------------------

t_fixture_start=$SECONDS
if [[ "$SKIP_GENERATE" == "true" ]]; then
  echo "── Using existing fixture at $FIXTURE_DIR ──"
  if [[ ! -d "$FIXTURE_DIR" ]]; then
    echo "ERROR: --skip-generate but $FIXTURE_DIR does not exist" >&2
    exit 1
  fi
else
  echo "── Generating fixture: $QUOTES quotes ──"
  .venv/bin/python scripts/generate-stress-fixture.py \
    --quotes "$QUOTES" \
    --output "$FIXTURE_DIR"
fi
t_fixture=$(( SECONDS - t_fixture_start ))

mkdir -p "$RESULTS_DIR"

# ---------------------------------------------------------------------------
# 2. Nuke the SQLite cache so the server re-imports from scratch
# ---------------------------------------------------------------------------

DB_PATH="${FIXTURE_DIR}/bristlenose-output/.bristlenose/bristlenose.db"
rm -f "$DB_PATH" "${DB_PATH}-wal" "${DB_PATH}-shm"

# ---------------------------------------------------------------------------
# 3. Pick a random ephemeral port from the kernel.
#
# The earlier hardcoded-8153 design had an lsof pre-flight check — but a
# check-then-bind pattern is inherently race-able.  A same-UID attacker
# can bind :8153 in the ~100ms window between our lsof and the server's
# bind, then harvest our bearer token from the first authenticated
# request.  Randomising to an ephemeral port closes that window for any
# attacker who can't read this script's stdout (which is where the chosen
# port surfaces).  Collision probability on a kernel-assigned free port
# is effectively zero; if it happens, `bristlenose serve` fails to bind
# and the server-exit-before-ready branch catches it.
# ---------------------------------------------------------------------------

PORT="$(.venv/bin/python -c '
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
')"
# Let the Playwright config see the chosen port (it reads $BN_STRESS_PORT).
export BN_STRESS_PORT="$PORT"

# ---------------------------------------------------------------------------
# 4. Start the server.
#
# Generate the auth token in the shell and export it so the server adopts
# it (app.py:96 reads _BRISTLENOSE_AUTH_TOKEN).  Passing via env keeps the
# token out of `ps aux`.
# ---------------------------------------------------------------------------

# Mask xtrace across the assignment so the token isn't echoed to stderr.
# The `{ ...; } 2>/dev/null` pattern suppresses the trace of `set +x` itself.
{ set +x; } 2>/dev/null
export _BRISTLENOSE_AUTH_TOKEN="$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(32))")"
if [[ "$VERBOSE" == "true" ]]; then
  set -x
fi

echo "── Starting bristlenose serve on :$PORT ──"
startup_start=$(date +%s)
t_startup_start=$SECONDS

# stdout → /dev/null (suppresses the 'auth-token: ...' print from app.py —
# do NOT un-redirect under --verbose; the token would leak to the terminal)
# stderr → $SERVER_ERR_RAW in $TMPDIR.  The cleanup trap writes a redacted
# copy into $RESULTS_DIR afterwards.
.venv/bin/bristlenose serve "$FIXTURE_DIR" --port "$PORT" --no-open \
  > /dev/null 2> "$SERVER_ERR_RAW" &
SERVER_PID=$!

# Poll /api/health (exempt from auth) until ready or timeout.
# Progress dots close the silent-gap problem: at 1,500 quotes SQLite import
# can take 20+ seconds, and the user needs to see the orchestrator is alive.
printf "   Waiting for server"
READY=false
for _ in $(seq 1 60); do
  if curl -sSf "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
    READY=true
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    printf "\n"
    echo "ERROR: server exited before becoming ready. Redacted tail of server.err:" >&2
    tail -20 "$SERVER_ERR_RAW" | _redact >&2 || true
    exit 1
  fi
  printf "."
  sleep 0.5
done
printf "\n"

startup_elapsed=$(( $(date +%s) - startup_start ))
t_startup=$(( SECONDS - t_startup_start ))

if [[ "$READY" != "true" ]]; then
  echo "ERROR: server did not respond on /api/health within 30s" >&2
  exit 1
fi

echo "   Startup + SQLite import: ${startup_elapsed}s"
if [[ $startup_elapsed -gt 20 && $QUOTES -ge 1500 ]]; then
  echo "   ⚠  >20s at $QUOTES quotes — consider batch inserts in importer.py"
fi

# ---------------------------------------------------------------------------
# 5. Identity guard — confirm we hit OUR fixture, not a different project
# ---------------------------------------------------------------------------

EXPECTED_NAME="Stress Test (${QUOTES} quotes)"
# Pass the bearer token via stdin config (curl -K -) so the token does not
# appear in `ps aux` output.  Mask xtrace around the printf so `set -x`
# doesn't expand and echo the token.
{ set +x; } 2>/dev/null
PROJECT_NAME="$(
  printf 'header = "Authorization: Bearer %s"\n' "$_BRISTLENOSE_AUTH_TOKEN" \
    | curl -sSf -K - "http://127.0.0.1:$PORT/api/projects/1/info" \
    | .venv/bin/python -c "import json, sys; print(json.load(sys.stdin)['project_name'])"
)"
if [[ "$VERBOSE" == "true" ]]; then
  set -x
fi

if [[ "$PROJECT_NAME" != "$EXPECTED_NAME" ]]; then
  echo "ERROR: connected to wrong project: '$PROJECT_NAME' (expected '$EXPECTED_NAME')" >&2
  exit 1
fi

echo "   Project identity OK: $PROJECT_NAME"

# ---------------------------------------------------------------------------
# 5b. Augment DB with realistic tag fanout.
#
# The server's importer only auto-applies the sentiment codebook (1 tag
# per quote).  Real AutoCode-processed projects have several codebook
# groups with 3-5 tags per quote — the sidebar endpoint returns ~10x
# the payload a sentiment-only fixture produces, and the DOM carries
# multiple badge rows per quote-card.  Skip this at very small quote
# counts (smoke runs) where augmentation noise would dwarf the signal.
# ---------------------------------------------------------------------------

t_augment_start=$SECONDS
if [[ $QUOTES -ge 20 ]]; then
  echo "── Augmenting DB with synthetic tag groups ──"
  .venv/bin/python scripts/stress-tag-fixture.py --db "$DB_PATH" --seed 0
fi
t_augment=$(( SECONDS - t_augment_start ))

# ---------------------------------------------------------------------------
# 6. Playwright stress spec
# ---------------------------------------------------------------------------

echo "── Running Playwright stress spec ──"
# STRESS_RESULTS_PATH tells the spec where to write its JSON output.
# _BRISTLENOSE_AUTH_TOKEN is already exported above.
export STRESS_RESULTS_PATH="${REPO_ROOT}/${RESULTS_DIR}/stress-results.json"
export STRESS_QUOTES="$QUOTES"
export STRESS_STARTUP_S="$startup_elapsed"

PW_REPORTER="line"
if [[ "$VERBOSE" == "true" ]]; then
  PW_REPORTER="list"
fi

t_playwright_start=$SECONDS
(
  cd "$REPO_ROOT/e2e"
  npx playwright test --config playwright.stress.config.ts \
    --reporter="$PW_REPORTER" tests/perf-stress.spec.ts
)
t_playwright=$(( SECONDS - t_playwright_start ))

# ---------------------------------------------------------------------------
# 7. Optional: Lighthouse
# ---------------------------------------------------------------------------

if [[ "$WITH_LIGHTHOUSE" == "true" ]]; then
  echo "── Running Lighthouse (may time out on large fixtures) ──"
  LH_OUT="${RESULTS_DIR}/lighthouse.json"
  # Use the pinned version from e2e/package.json — scoring weights change
  # between majors (v10→v12 deprecated TTI etc).  `npx lighthouse` without
  # --yes prefers the local install; we change into e2e/ so it resolves.
  # Lighthouse needs no auth (it hits /report/quotes/ which isn't behind
  # the bearer middleware); unset the token to shrink the exposure window.
  if ( cd "$REPO_ROOT/e2e" && \
       env -u _BRISTLENOSE_AUTH_TOKEN npx lighthouse \
         "http://127.0.0.1:$PORT/report/quotes/" \
         --quiet --chrome-flags="--headless" \
         --output json --output-path "$REPO_ROOT/$LH_OUT" \
         --only-categories=performance \
         --throttling-method=provided 2> "$REPO_ROOT/${RESULTS_DIR}/lighthouse.err" ); then
    echo "   Lighthouse results: $LH_OUT"
  else
    echo "   ⚠  Lighthouse timed out or errored — see lighthouse.err"
  fi
fi

# ---------------------------------------------------------------------------
# 8. Export endpoint — measure the production export size at scale
# ---------------------------------------------------------------------------

echo "── Measuring export endpoint ──"
t_export_start=$SECONDS
# Portable mktemp template (full path with XXXXXX).  BSD mktemp -t takes
# a prefix, GNU mktemp -t takes a full template — the explicit path form
# works on both.  See CLAUDE.md BSD-vs-GNU rule.  Also force umask 077
# before creation: mktemp already sets mode 0600 but umask is defence in
# depth against any temp file created by the python helpers below.
_prev_umask=$(umask)
umask 077
EXPORT_FILE="$(mktemp "${TMPDIR:-/tmp}/bristlenose-export.XXXXXX")"
EXPORT_HEADERS="$(mktemp "${TMPDIR:-/tmp}/bristlenose-export-headers.XXXXXX")"
umask "$_prev_umask"

# Deliberately NOT using `curl -v` under --verbose.  `curl -v` can echo
# stdin-config content ("* Setting 'header' = 'Authorization: Bearer …'")
# and HTTP/2 lowercase `authorization:` lines that our sed redaction
# wouldn't reliably catch.  Instead we use -w to print response metrics
# (no request-side echo) and cat the response headers — both are safe.
CURL_WRITEOUT=()
if [[ "$VERBOSE" == "true" ]]; then
  CURL_WRITEOUT=(-w '   export: HTTP %{http_code}  %{size_download} bytes  %{time_total}s total  %{time_starttransfer}s TTFB\n')
fi

# Mask xtrace across the printf so the bearer token doesn't hit stderr.
{ set +x; } 2>/dev/null
printf 'header = "Authorization: Bearer %s"\n' "$_BRISTLENOSE_AUTH_TOKEN" \
  | curl -sSf "${CURL_WRITEOUT[@]}" -K - \
      -D "$EXPORT_HEADERS" -o "$EXPORT_FILE" \
      "http://127.0.0.1:$PORT/api/projects/1/export"
if [[ "$VERBOSE" == "true" ]]; then
  echo "   response headers:"
  sed 's/^/     /' "$EXPORT_HEADERS"
  set -x
fi

# curl -sSf aborts on non-2xx, so reaching here means we have the payload.
if ! head -1 "$EXPORT_HEADERS" | grep -q "200"; then
  echo "ERROR: export returned non-200. Headers:" >&2
  cat "$EXPORT_HEADERS" >&2
  rm -f "$EXPORT_HEADERS"
  exit 1
fi
rm -f "$EXPORT_HEADERS"

export_bytes=$(wc -c < "$EXPORT_FILE" | tr -d ' ')
export_mb=$(.venv/bin/python -c "print(f'{$export_bytes/1024/1024:.2f}')")
t_export=$(( SECONDS - t_export_start ))

# Nothing downstream needs the auth token any more (Playwright + export
# + lighthouse are all done).  Drop it from the environment so the merge
# python child process and any other descendants can't read it via
# /proc/<pid>/environ.  Mask xtrace so the unset line itself doesn't
# trace the value as it's being cleared.
{ set +x; } 2>/dev/null
unset _BRISTLENOSE_AUTH_TOKEN
if [[ "$VERBOSE" == "true" ]]; then
  set -x
fi

# Sanity floor — a 401 body is ~50 bytes and would trivially look like a
# tiny "efficient" export.
if [[ $export_bytes -lt 500000 ]]; then
  echo "ERROR: export payload $export_bytes bytes is implausibly small (auth?)" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 9. Merge shell-side metrics into stress-results.json
# ---------------------------------------------------------------------------

export STRESS_EXPORT_BYTES="$export_bytes"
export STRESS_EXPORT_MB="$export_mb"

# Quoted heredoc delimiter ('PY') disables shell interpolation inside the
# body, so a surprise-empty variable can no longer become a SyntaxError
# inside the Python source.  All values flow via os.environ instead.
.venv/bin/python - <<'PY'
import json, os
from pathlib import Path

path = Path(os.environ["STRESS_RESULTS_PATH"])
data = json.loads(path.read_text()) if path.exists() else {}
data["quotes"] = int(os.environ["STRESS_QUOTES"])
data["startup_seconds"] = int(os.environ["STRESS_STARTUP_S"])
data["export_bytes"] = int(os.environ["STRESS_EXPORT_BYTES"])
data["export_mb"] = float(os.environ["STRESS_EXPORT_MB"])
path.write_text(json.dumps(data, indent=2) + "\n")
PY

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

# The box holds fixed-width metrics only; the results path (often 80+
# chars absolute) is printed *outside* so it never overflows the border.
echo ""
echo "┌─ Stress test summary ─────────────────────────────┐"
printf "│  Quotes           %6d                          │\n" "$QUOTES"
printf "│  Startup          %6ds                         │\n" "$startup_elapsed"
printf "│  Export HTML      %8s MB                      │\n" "$export_mb"
echo "│                                                   │"
echo "│  Stage timings (wall-clock):                      │"
printf "│    fixture      %4ds                            │\n" "$t_fixture"
printf "│    startup      %4ds                            │\n" "$t_startup"
printf "│    augment      %4ds                            │\n" "${t_augment:-0}"
printf "│    playwright   %4ds                            │\n" "$t_playwright"
printf "│    export       %4ds                            │\n" "$t_export"
echo "└───────────────────────────────────────────────────┘"
echo ""
echo "  Full results: $STRESS_RESULTS_PATH"
echo ""
