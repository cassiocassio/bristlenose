#!/bin/bash
# appmeasure.sh <label> <drag|none> : one 10 s window against the Debug app via the probe proxy.
D=$(cd "$(dirname "$0")" && pwd); open $D/opt.app; sleep 1.5
PID=$(pgrep -f "divider-lab/opt.app/Contents/MacOS/Bristlenose" | head -1)
PPS=$(lsof -nP -iTCP -sTCP:LISTEN -a -c python3 | awk 'NR>1{print $9}' | sed 's/.*://')
read SX YM <<<$($D/findsplit Bristlenose | python3 -c "import json,sys; d=json.load(sys.stdin); s=[f for f in d['found'] if f['role']=='AXSplitter'][0]; print(s['x'], s['y']+s['h']/2)")
X0=$(python3 -c "print($SX+0.5)")
if [ "$2" = drag ]; then
  R=$($D/drag2 $X0 $YM 0 45 10 120)
else
  S=$(python3 -c "import time;print(time.time()*1000)"); sleep 10; E=$(python3 -c "import time;print(time.time()*1000)"); R="{\"start_ms\":$S,\"end_ms\":$E}"
fi
echo "$R" > $D/results/app-$1.win
sleep 1.5
for p in $PPS; do curl -s -m 3 http://127.0.0.1:$p/__lab/dump; echo; done > $D/results/app-$1.raw
for p in $PPS; do curl -s -m 3 http://127.0.0.1:$p/__lab/dumpw; echo; done > $D/results/app-$1.w
python3 - "$R" "$D/results/app-$1.raw" "$1" <<'PY'
import json,sys
r=json.loads(sys.argv[1]); ts=[]
for line in open(sys.argv[2]):
    line=line.strip()
    if line: ts+=json.loads(line)
ts=sorted(t for t in ts if r['start_ms']<=t<=r['end_ms'])
g=[b-a for a,b in zip(ts,ts[1:])]; s=sorted(g); q=lambda p:s[min(len(s)-1,int(p*len(s)))] if s else 0
dur=(ts[-1]-ts[0])/1000 if len(ts)>1 else 0
o=dict(label=sys.argv[3],frames=len(ts),fps=round(len(ts)/dur,1) if dur else 0,p50=round(q(.5),1),p95=round(q(.95),1),max=round(max(g),1) if g else 0,over33=sum(x>33 for x in g),over50=sum(x>50 for x in g))
wd=[]
for line in open(sys.argv[2].replace('.raw','.w')):
    line=line.strip()
    if line.startswith('['): wd+=json.loads(line)
wd=[w for w in wd if r['start_ms']<=w[0]<=r['end_ms']]
o['inner_w_min']=min([w[1] for w in wd],default=None); o['inner_w_max']=max([w[1] for w in wd],default=None); o['width_changes']=len(wd)
open(sys.argv[2].replace('.raw','.json'),'w').write(json.dumps(o)); print(o)
PY
