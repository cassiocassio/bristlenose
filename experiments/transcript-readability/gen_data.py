import json, re, sqlite3, bisect, glob, html, sys
sys.path.insert(0,'/Users/cassio/Code/bristlenose')
from bristlenose.server.importer import _words_read_as
PFX=re.compile(r'^\([^)]*\)\s*')
END=re.compile(r'[.?!…]["”’)]?$')
FILL=re.compile(r"^(um+|uh+|er|erm|hmm+|mm+)([,.?!…]*)$", re.I)

# ---- today: DB paragraphs + time-joined words (as importer does) ----
c=sqlite3.connect('db/IKEA_with_uxfriends/bristlenose.db')
rows=c.execute("select t.start_time,t.end_time,t.text,t.speaker_code from transcript_segments t join sessions s on s.id=t.session_id where s.session_id='s1' order by t.start_time").fetchall()
raw=json.load(open('db/IKEA_with_uxfriends/session_segments.json'))['s1']
starts=[r[0] for r in rows]; buckets=[[] for _ in rows]
for p in sorted((p for p in raw if p.get('words')),key=lambda p:p['start_time']):
    k=bisect.bisect_right(starts,p['start_time'])-1
    if k>=0: buckets[k].extend(w for w in p['words'] if w.get('text'))
today=[]
for r,ws in zip(rows,buckets):
    drawn=' '.join(w['text'] for w in ws) if ws and _words_read_as(ws,r[2]) else r[2]
    today.append(dict(s=r[0],e=r[1],code=r[3],text=drawn,stored=PFX.sub('',r[2]),fromWords=drawn!=r[2]))

def spk(s,e):
    best=None;bo=-1
    for r in rows:
        o=min(e,r[1])-max(s,r[0])
        if o>bo: bo=o;best=r[3]
    return best

def load_full(pat, sentences=True):
    segs=json.load(open(sorted(glob.glob(pat))[0]))
    out=[]
    for x in segs:
        if not x['text'].strip(): continue
        ws=x.get('words') or []
        if not sentences or not ws:
            out.append(dict(s=x['start'],e=x['end'],t=x['text'].strip(),code=spk(x['start'],x['end']))); continue
        cur=[]
        for w in ws:
            cur.append(w)
            if END.search(w['word'].strip()):
                out.append(dict(s=cur[0]['start'],e=cur[-1]['end'],t=' '.join(c['word'].strip() for c in cur),code=spk(cur[0]['start'],cur[-1]['end']))); cur=[]
        if cur: out.append(dict(s=cur[0]['start'],e=cur[-1]['end'],t=' '.join(c['word'].strip() for c in cur),code=spk(cur[0]['start'],cur[-1]['end'])))
    return out
def load_txt(fn,offset=0.0):
    out=[];L=[l for l in open(fn).read().splitlines() if l.strip()]
    for i,l in enumerate(L):
        m=re.match(r'\s*([\d.]+)\s+t=\S+\s+(.*)',l); s=float(m.group(1))
        nxt=float(re.match(r'\s*([\d.]+)',L[i+1]).group(1)) if i+1<len(L) else s+5
        out.append(dict(s=s,e=nxt,t=m.group(2).strip(),code=spk(s,nxt)))
    return out

def merge(segs,soft=None):
    P=[]
    for g in segs:
        if P:
            q=P[-1]
            same=q['code']==g['code'] and g['s']-q['e']<=2.0
            if same and soft and len(q['text'].split())>=soft and END.search(q['text']): same=False
            if same:
                q['e']=max(q['e'],g['e']); q['text']+=' '+g['t']; continue
        P.append(dict(s=g['s'],e=g['e'],code=g['code'],text=g['t']))
    return P

def softbreak(paras,soft=60):
    """display-only: break a stored paragraph at sentence ends every ~soft words"""
    out=[]
    for p in paras:
        sents=re.split(r'(?<=[.?!])\s+',p['text']); cur=[]; first=True
        for s_ in sents:
            cur.append(s_)
            if len(' '.join(cur).split())>=soft:
                out.append(dict(p,text=' '.join(cur),cont=not first)); cur=[]; first=False
        if cur: out.append(dict(p,text=' '.join(cur),cont=not first))
    return out

V={}
V['today']=[dict(p) for p in today]
J=load_full('full_J_*.json'); H=load_full('full_H_*.json')
I=load_txt('exp_I_carry_neutral_prompt.txt')  # 1:00–6:00 only; starts already absolute
V['v1']=merge(J,soft=60)
V['v2']=merge(load_full('full_J_*.json',sentences=False))
V['v3']=softbreak([dict(p,text=p['stored']) for p in today])
V['v4']=merge(I,soft=60)
V['v5']=merge(H,soft=60)
for k,ps in V.items():
    w=[len(p['text'].split()) for p in ps]
    print(k,'paras',len(ps),'max words',max(w))
json.dump(V,open('mock_data.json','w'))
