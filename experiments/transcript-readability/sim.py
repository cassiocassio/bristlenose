import sqlite3,json,re,bisect,statistics as st
HG=0.0
END=re.compile(r'[.?!…]["”’)]?$')
def pct(xs,p):
    xs=sorted(xs); return xs[min(len(xs)-1,int(p/100*len(xs)))]
def load(proj):
    c=sqlite3.connect(f'db/{proj}/bristlenose.db')
    raw=json.load(open(f'db/{proj}/session_segments.json'))
    out=[]
    for sid,psegs in raw.items():
        rows=c.execute("select t.start_time,t.speaker_code from transcript_segments t join sessions s on s.id=t.session_id where s.session_id=? order by t.start_time",(sid,)).fetchall()
        if not rows: continue
        starts=[r[0] for r in rows]
        segs=[]
        for p in sorted(psegs,key=lambda p:p['start_time']):
            k=max(0,bisect.bisect_right(starts,p['start_time']+0.5)-1)
            segs.append(dict(s=p['start_time'],e=p['end_time'],t=p['text'].strip(),spk=rows[k][1]))
        out.append(segs)
    return out
def rule(segs,max_gap=2.0,soft_words=None,hard_words=None,soft_secs=None):
    paras=[]
    for g in segs:
        if paras:
            P=paras[-1]; same=P['spk']==g['spk']; gap=g['s']-P['e']
            nw=len(P['t'].split()); dur=P['e']-P['s']
            over = (soft_words and nw>=soft_words) or (soft_secs and dur>=soft_secs)
            sent_end=bool(END.search(P['t']))
            brk = not same or gap>max_gap
            if not brk and over and sent_end: brk=True
            if not brk and hard_words and nw>=hard_words and gap>=HG: brk=True
            if not brk:
                P['e']=max(P['e'],g['e']); P['t']+=' '+g['t']; continue
        paras.append(dict(g))
    return paras
def report(name,P):
    w=[len(p['t'].split()) for p in P]; d=[p['e']-p['s'] for p in P]; tot=sum(w)
    print(f"  {name:34} n={len(P):5} words p50 {pct(w,50):3} p90 {pct(w,90):4} max {max(w):5} | secs p50 {pct(d,50):4.0f} p90 {pct(d,90):4.0f} max {max(d):5.0f} | >150w {sum(x>150 for x in w):4} ({100*sum(x for x in w if x>150)/tot:4.1f}% of words)")
for proj in ['IKEA_with_uxfriends','fossda-opensource','project-ikea']:
    S=load(proj); print(proj)
    flat=lambda f: [p for segs in S for p in f(segs)]
    report('A current: same speaker, gap<=2s',flat(lambda s:rule(s)))
    report('B + break at sentence end >=60w',flat(lambda s:rule(s,soft_words=60)))
    report('C + B, hard pause-break >=120w',flat(lambda s:rule(s,soft_words=60,hard_words=120)))
    report('D sentence end after >=30s',flat(lambda s:rule(s,soft_secs=30)))
    report('E gap<=1.0s only',flat(lambda s:rule(s,max_gap=1.0)))
print('--- extra')
for proj in ['IKEA_with_uxfriends','fossda-opensource']:
    S=load(proj); print(proj)
    flat=lambda f: [p for segs in S for p in f(segs)]
    report('F B + any seg boundary >=120w',flat(lambda s:rule(s,soft_words=60,hard_words=120,)))
    import re as _r
    def rule2(segs): 
        P=rule(segs,soft_words=60)
        return P
    P=flat(lambda s:rule(s,soft_words=60,hard_words=120))
    big=[p for p in P if len(p['t'].split())>150]
    unp=[p for p in big if len(_r.findall(r'[.?!]',p['t']))<=2]
    print('   C leftovers >150w:',len(big),'of which <=2 sentence ends:',len(unp))
    report('G break at sentence end >=40w',flat(lambda s:rule(s,soft_words=40)))
    report('H 40w soft + 100w hard',flat(lambda s:rule(s,soft_words=40,hard_words=100)))
