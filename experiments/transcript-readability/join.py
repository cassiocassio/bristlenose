import sqlite3,json,re,bisect,sys
sys.path.insert(0,'/Users/cassio/Code/bristlenose')
from bristlenose.server.importer import _words_read_as
LABEL=re.compile(r'^\([^)]*\)\s*')
for proj in ['IKEA_with_uxfriends','project-ikea','fossda-opensource']:
    c=sqlite3.connect(f'db/{proj}/bristlenose.db')
    raw=json.load(open(f'db/{proj}/session_segments.json'))
    tot=ok=lowW=lowT=edge=0; punctW=0
    for sid,psegs in raw.items():
        rows=c.execute("select t.start_time,t.end_time,t.text,t.speaker_code from transcript_segments t join sessions s on s.id=t.session_id where s.session_id=? order by t.start_time",(sid,)).fetchall()
        if not rows: continue
        starts=[r[0] for r in rows]; buckets=[[] for _ in rows]
        for p in sorted((p for p in psegs if p.get('words')),key=lambda p:p['start_time']):
            k=bisect.bisect_right(starts,p['start_time'])-1
            if k>=0: buckets[k].extend(w for w in p['words'] if w.get('text'))
        for r,ws in zip(rows,buckets):
            tot+=1
            if not ws or not _words_read_as(ws,r[2]): continue
            ok+=1
            wt=' '.join(w['text'] for w in ws); tt=LABEL.sub('',r[2])
            if wt[:1].islower(): lowW+=1
            if tt[:1].islower(): lowT+=1
            if re.search(r'[.?!,]',wt): punctW+=1
            a=re.findall(r"\w+",wt.lower()); b=re.findall(r"\w+",tt.lower())
            if a[:3]!=b[:3] or a[-3:]!=b[-3:]: edge+=1
    print(f"{proj:20} paras {tot} words-kept {ok} | of kept: words lower-start {lowW}, text lower-start {lowT}, words w/ punct {punctW}, edge-differs {edge}")
