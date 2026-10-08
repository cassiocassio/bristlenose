import json,glob,re
PRON=re.compile(r"^i('m|'ve|'d|'ll)?$",re.I)
def runs(tokens):
    out=[];cur=0
    for t in tokens:
        cur+=1
        if re.search(r'[.,?!;:]$',t): out.append(cur);cur=0
    if cur: out.append(cur)
    return out
for f in sorted(glob.glob('db/*/session_segments.json')):
    d=json.load(open(f)); name=f.split('/')[-2]
    for sid,segs in sorted(d.items(), key=lambda kv:int(kv[0][1:])):
        if not segs or segs[0].get('source')=='vtt': continue
        toks=' '.join(s['text'] for s in segs).split()
        pi=[t for t in toks if PRON.match(t)]
        lowi=sum(1 for t in pi if t[0]=='i')
        r=runs(toks)
        long40=sum(x for x in r if x>=40)
        sent=len(re.findall(r'[.?!](\s|$)',' '.join(toks)))
        print(f"{name:20} {sid:4} words {len(toks):6} | pronoun-I lower {lowi:4}/{len(pi):4} ({100*lowi/max(1,len(pi)):3.0f}%) | words in 40+ runs w/o punct {100*long40/len(toks):4.0f}% | words/sentence {len(toks)/max(1,sent):5.1f}")
