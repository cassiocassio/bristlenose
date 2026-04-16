#!/bin/bash
# Print a table of performance results from e2e/.perf-history.jsonl.
# Usage: ./scripts/perf-history.sh
set -euo pipefail

HISTORY="$(dirname "$0")/../e2e/.perf-history.jsonl"

if [ ! -f "$HISTORY" ]; then
  echo "No history yet. Run: cd e2e && _BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test tests/perf-gate.spec.ts --project=chromium"
  exit 0
fi

# Pass the path via argv + quoted heredoc — no shell expansion into Python.
python3 - "$HISTORY" <<'PY'
import sys, json

path = sys.argv[1]
with open(path) as fh:
    rows = []
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # Skip corrupt lines rather than aborting the whole report.
            pass

header = (
    f"{'Date':<17}  {'SHA':<8}  {'Runner':<18}  "
    f"{'Quotes':>6}  {'Trans':>5}  {'Dash':>5}  {'Sess':>5}  "
    f"{'API q':>7}  {'API d':>7}  {'Export':>8}"
)
print(header)
print("-" * len(header))

for r in rows:
    ts = r["timestamp"][:16].replace("T", " ")
    sha = (r.get("git_sha") or "—")[:7]
    runner = (r.get("runner") or "—")[:18]
    export = r.get("export_html_bytes", 0) / 1024 / 1024 if r.get("export_html_bytes") else 0
    print(
        f"{ts:<17}  {sha:<8}  {runner:<18}  "
        f"{r.get('dom_quotes','—'):>6}  {r.get('dom_transcript_s1','—'):>5}  "
        f"{r.get('dom_dashboard','—'):>5}  {r.get('dom_sessions','—'):>5}  "
        f"{str(r.get('api_latency_quotes_ms','—'))+'ms':>7}  "
        f"{str(r.get('api_latency_dashboard_ms','—'))+'ms':>7}  "
        f"{export:>6.2f}MB"
    )
PY
