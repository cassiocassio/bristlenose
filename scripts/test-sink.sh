#!/usr/bin/env bash
# test-sink.sh — prove the event sink writes what the board will read.
#
# WHY THIS SHAPE
#
# The sink is a tee on lines the build scripts already emit (report.sh's @bn
# protocol) into a file the release board reads. Every assertion here is a way
# the file could be silently wrong: a value that printf %q renders in ANSI-C
# quoting that shlex cannot decode (measured 5 Sep 2026 — a newline plus an
# apostrophe made parse_event drop the whole line), a relative sink path that
# resolves against a child's cwd, a BN_REPORT=0 run whose parent and child both
# write, a nested child that should be silent. The parser under test is the one
# the board imports (desktop/scripts/bn_events.py), so the contract is proven at
# both ends in one place.
#
# Every assertion is proven to fail on its own violation — see meta_check in
# test-lib.sh (docs/design-test-philosophy.md).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$(dirname "$0")/test-lib.sh"

PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
SINK="$WORK/bn-events.log"

# A fake build script that sources report.sh and emits the four kinds.
cat > "$WORK/fake.sh" <<'EOF'
#!/usr/bin/env bash
set -u
# SCRIPT_DIR must be report.sh's own dir: bn_autowrap finds the renderer there,
# and only then is this the real renderer path (outer re-exec → inner owner).
SCRIPT_DIR="$(cd "$(dirname "$REPORT_SH")" && pwd)"
source "$REPORT_SH"
bn_autowrap "$0" "$@"
bn_step_start 1 Build "Pre-flight"
bn_check 1 ok "logging hygiene" "$EVIDENCE"
bn_gate a ok "Notarisation staple" "stapled"
bn_step_ok 1 elapsed=3 detail="fine"
bn_done ok
EOF
chmod +x "$WORK/fake.sh"
export REPORT_SH="$ROOT/desktop/scripts/report.sh"

# parse every @bn line in $1 with the board's parser; print "<events> <unparsed> <partial>"
parse_counts() {
    ROOTP="$ROOT" "$PY" - "$1" <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOTP"], "desktop", "scripts"))
from bn_events import parse_stream
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
events, unparsed, partial = parse_stream(text)
print(len(events), len(unparsed), int(partial))
PYEOF
}
field_of() { # field_of <file> <kind> <field> — first match
    ROOTP="$ROOT" "$PY" - "$1" "$2" "$3" <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOTP"], "desktop", "scripts"))
from bn_events import parse_stream
events, _, _ = parse_stream(open(sys.argv[1], encoding="utf-8", errors="replace").read())
for _, kind, f in events:
    if kind == sys.argv[2] and sys.argv[3] in f:
        print(f[sys.argv[3]]); break
PYEOF
}

head_ "1 · a standalone run under the renderer writes once, and every line parses"
rm -f "$SINK"
EVIDENCE="no credential-shaped log calls" BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1
rc=$?
eq "fake script exits 0" 0 "$rc"
[ -f "$SINK" ] && ok "sink file created" || bad "no sink file"
set -- $(parse_counts "$SINK")
eq "five events parsed (step start, check, gate, step ok, done)" 5 "${1:-0}"
eq "zero unparsed" 0 "${2:-1}"
eq "no partial trailing line" 0 "${3:-1}"
ts="$(field_of "$SINK" step ts)"
case "$ts" in *Z) ok "ts is UTC ISO-8601 ($ts)" ;; *) bad "ts is not UTC ISO-8601: '$ts'" ;; esac
run="$(field_of "$SINK" step run)"
case "$run" in standalone-*) ok "run id minted for a standalone sink ($run)" ;; *) bad "run id missing: '$run'" ;; esac
mode="$(stat -f '%Lp' "$SINK" 2>/dev/null || stat -c '%a' "$SINK")"
eq "sink is 0600" 600 "$mode"

head_ "2 · values that used to break the parser round-trip after normalisation"
rm -f "$SINK"
NL=$'No errors uploading \'/Users/x/a.pkg\'.\nDelivery UUID: abc'
EVIDENCE="$NL" BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1
set -- $(parse_counts "$SINK")
eq "newline + apostrophe: line still parses" 0 "${2:-1}"
got="$(field_of "$SINK" check evidence)"
case "$got" in *"'/Users/x/a.pkg'."*"Delivery UUID: abc"*) ok "newline became a space, apostrophes kept" ;; *) bad "value mangled: '$got'" ;; esac
rm -f "$SINK"
EVIDENCE=$'col1\tcol2 "quoted" back\\slash <tag> & amp' BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1
got="$(field_of "$SINK" check evidence)"
eq "tab → space; quotes, backslash, <, & intact" 'col1 col2 "quoted" back\slash <tag> & amp' "$got"
rm -f "$SINK"
EVIDENCE="notarised — stapled ✓" LC_ALL=C BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1
set -- $(parse_counts "$SINK")
eq "non-ASCII under LC_ALL=C: line still parses" 0 "${2:-1}"
got="$(field_of "$SINK" check evidence)"
eq "non-ASCII under LC_ALL=C round-trips (the parser decodes ANSI-C quoting)" "notarised — stapled ✓" "$got"
rm -f "$SINK"
LONG="$(printf 'x%.0s' $(seq 1 500))"
EVIDENCE="$LONG" BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1
got="$(field_of "$SINK" check evidence)"
eq "a 500-byte value is capped at 200" 200 "${#got}"

head_ "3 · the no-ops: no sink, unwritable sink, relative sink"
rm -f "$SINK"
EVIDENCE=e "$WORK/fake.sh" >/dev/null 2>&1; rc=$?
eq "no sink set → exit 0" 0 "$rc"
[ ! -e "$SINK" ] && ok "no sink set → no file" || bad "a file appeared without a sink"
EVIDENCE=e BN_EVENT_SINK="/nonexistent-dir-$$/x.log" "$WORK/fake.sh" >/dev/null 2>&1; rc=$?
eq "unwritable sink → caller still exits 0" 0 "$rc"
( cd "$WORK" && EVIDENCE=e BN_EVENT_SINK="relative.log" "$WORK/fake.sh" >/dev/null 2>&1 )
[ ! -e "$WORK/relative.log" ] && ok "relative sink → refused, nothing written" || bad "relative sink was written"
rm -f "$SINK"
( cd /tmp && EVIDENCE=e BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1 )
[ -f "$SINK" ] && ok "a child that cd'd elsewhere still lands in the absolute sink" || bad "cwd change lost the sink"

head_ "4 · ownership: BN_REPORT=0 writes once; a nested child writes nothing"
rm -f "$SINK"
EVIDENCE=e BN_REPORT=0 BN_EVENT_SINK="$SINK" "$WORK/fake.sh" >/dev/null 2>&1
set -- $(parse_counts "$SINK")
eq "plain mode records the five events exactly once" 5 "${1:-0}"
# a parent that renders, then runs the fake as a child: the child must be silent
cat > "$WORK/parent.sh" <<'EOF'
#!/usr/bin/env bash
set -u
SCRIPT_DIR="$(cd "$(dirname "$REPORT_SH")" && pwd)"
source "$REPORT_SH"
bn_autowrap "$0" "$@"
bn_step_start 9 Build "parent step"
"$CHILD" >/dev/null 2>&1
bn_step_ok 9 elapsed=1
bn_done ok
EOF
chmod +x "$WORK/parent.sh"
rm -f "$SINK"
EVIDENCE=e CHILD="$WORK/fake.sh" BN_EVENT_SINK="$SINK" "$WORK/parent.sh" >/dev/null 2>&1
set -- $(parse_counts "$SINK")
eq "renderer mode: parent's 3 events only, child silent" 3 "${1:-0}"
rm -f "$SINK"
EVIDENCE=e CHILD="$WORK/fake.sh" BN_REPORT=0 BN_EVENT_SINK="$SINK" "$WORK/parent.sh" >/dev/null 2>&1
set -- $(parse_counts "$SINK")
eq "plain mode: parent's 3 events only, child silent (the 5 Sep 2026 double-write)" 3 "${1:-0}"

head_ "5 · the stream parser: a half-written last line is partial, not an event"
printf '@bn step ts=2026-09-05T00:00:00Z run=x id=1 status=ok\n@bn step ts=2026-09-05T00:00:01Z run=x id=2 status=st' > "$WORK/partial.log"
set -- $(parse_counts "$WORK/partial.log")
eq "one complete event" 1 "${1:-0}"
eq "the unterminated line is reported partial" 1 "${3:-0}"
printf "@bn check ts=t run=x evidence=\$'a\\\\nb it\\\\'s'\n" > "$WORK/bad.log"
set -- $(parse_counts "$WORK/bad.log")
eq "a legacy ANSI-C-quoted line (pre-normalisation writer) still parses" 0 "${2:-1}"
got="$(field_of "$WORK/bad.log" check evidence)"
eq "…and decodes to the original bytes" "$(printf 'a\nb it'"'"'s')" "$got"
printf '@bn check ts=t run=x evidence="unterminated\n' > "$WORK/bad2.log"
set -- $(parse_counts "$WORK/bad2.log")
eq "a line shlex cannot read is COUNTED as unparsed, not dropped" 1 "${2:-0}"

head_ "6 · bash 3.2 safety — the sink is sourced by a /bin/bash 3.2 build phase"
for f in desktop/scripts/sink.sh desktop/scripts/report.sh; do
    # comments stripped first: both headers SAY "no \${var,,}" and would match
    if sed 's/[[:space:]]*#.*$//' "$ROOT/$f" | grep -nE 'declare -A|\$\{[a-zA-Z_]+,,\}|mapfile' >/dev/null; then
        bad "$f uses a bash-4 construct"
    else
        ok "$f free of declare -A / \${var,,} / mapfile"
    fi
done

finish
