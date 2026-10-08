import sqlite3,glob,json,re,statistics as st
def pct(xs,p):
    xs=sorted(xs); 
    return xs[min(len(xs)-1,int(p/100*len(xs)))] if xs else 0
LABEL=re.compile(r'^\(Speaker [^)]*\)\s*')
print(f"{'project':22} {'paras':>5} {'sess':>4} | dur s: p50 p90 p99 max | words: p50 p90 max | >60s  >150w | %words in >150w paras | lowstart")
for db in sorted(glob.glob('db/*/bristlenose.db')):
    name=db.split('/')[-2]
    c=sqlite3.connect(db)
    rows=c.execute("select s.session_id,t.speaker_code,t.start_time,t.end_time,t.text from transcript_segments t join sessions s on s.id=t.session_id").fetchall()
    d=[r[3]-r[2] for r in rows]; w=[len(LABEL.sub('',r[4]).split()) for r in rows]
    tot=sum(w); big=sum(x for x in w if x>150)
    low=sum(1 for r in rows if LABEL.sub('',r[4])[:1].islower())
    print(f"{name:22} {len(rows):5} {len(set(r[0] for r in rows)):4} | {pct(d,50):5.0f} {pct(d,90):4.0f} {pct(d,99):4.0f} {max(d):4.0f} | {pct(w,50):4} {pct(w,90):4} {max(w):4} | {sum(x>60 for x in d):4} {sum(x>150 for x in w):5} | {100*big/tot:5.1f}% | {low}/{len(rows)}")
