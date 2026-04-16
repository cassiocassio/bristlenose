#!/bin/bash
# Print a table of performance results from e2e/.perf-history.jsonl
# Usage: ./scripts/perf-history.sh

HISTORY="$(dirname "$0")/../e2e/.perf-history.jsonl"

if [ ! -f "$HISTORY" ]; then
  echo "No history yet. Run: cd e2e && _BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test tests/perf-gate.spec.ts --project=chromium"
  exit 0
fi

python3 -c "
import sys, json
rows = [json.loads(l) for l in open('$HISTORY')]
print(f'{\"Date\":<17}  {\"Quotes\":>6}  {\"Trans\":>5}  {\"Dash\":>5}  {\"Sess\":>5}  {\"API q\":>6}  {\"API d\":>6}  {\"Export\":>8}')
print('-' * 78)
for r in rows:
    ts = r['timestamp'][:16].replace('T',' ')
    print(f\"{ts:<17}  {r.get('dom_quotes','—'):>6}  {r.get('dom_transcript_s1','—'):>5}  {r.get('dom_dashboard','—'):>5}  {r.get('dom_sessions','—'):>5}  {str(r.get('api_latency_quotes_ms','—'))+'ms':>6}  {str(r.get('api_latency_dashboard_ms','—'))+'ms':>6}  {r.get('export_html_bytes',0)/1024/1024:>6.2f}MB\")
"
