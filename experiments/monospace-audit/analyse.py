"""Summarise probe output: ink relative to 400, averaged over sizes. Usage: python3 analyse.py <dir with res-pw.json, res-sb.json>"""
import json,sys,statistics as st
S=sys.argv[1]
pw=json.load(open(S+'/res-pw.json')); import os
sb=json.load(open(S+'/res-sb.json')) if os.path.exists(S+'/res-sb.json') else []
rows=[r for r in pw if 'stack' in r]+[dict(r,engine='wkwebview-sandboxed') for r in sb]
I={(r['engine'],r['scale'],r['stack'],r['size'],r['weight']):r['ink'] for r in rows}
W=[300,370,400,420,490,500,520,590,600,700]; SZ=['micro','badge','caption','label','body']
out=[]
for sc in ['web','desktop','desktop_inter']:
  for stk in ['token','web_nodl','desk_nodl','proposed','rogue_inspector']:
    for e in (['wkwebview-sandboxed'] if sb else [])+['pw-webkit','pw-chromium']:
      cells=[];spread=0
      for w in W:
        v=[I[(e,sc,stk,s,w)]/I[(e,sc,stk,s,400)]-1 for s in SZ]; cells.append(st.mean(v)); spread=max(spread,max(v)-min(v))
      out.append((sc,stk,e,cells,spread))
      print(f"{sc:13s} {stk:15s} {e:20s} "+' '.join(f"{w}:{c*100:+4.0f}" for w,c in zip(W,cells))+f"  spread±{spread*50:.1f}pt")
json.dump([dict(scale=a,stack=b,engine=c,ink_vs_400={str(w):round(x*100,1) for w,x in zip(W,d)},size_spread_pts=round(f*100,1)) for a,b,c,d,f in out],open(S+'/summary.json','w'),indent=1)

