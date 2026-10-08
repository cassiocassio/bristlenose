import sys,re,json,time,collections; sys.path.insert(0,'.')
import mlx_whisper, carry_transcribe
from mlx_whisper.audio import load_audio
A=load_audio('s1.wav')
P="Okay, so, um, tell me about it. Well, I think it's good, you know? Yeah."
cfg=sys.argv[1]
kw=dict(path_or_hf_repo='mlx-community/whisper-large-v3-turbo',language='en',word_timestamps=True,verbose=None,condition_on_previous_text=False,no_speech_threshold=0.85)
fn=mlx_whisper.transcribe
if cfg=='current': kw['compression_ratio_threshold']=1.8
elif cfg=='H': kw['compression_ratio_threshold']=2.4; kw['initial_prompt']=P; fn=carry_transcribe.transcribe
elif cfg=='J': kw['compression_ratio_threshold']=1.8; kw['initial_prompt']="Hmm, okay. Well, yes, I suppose so, um, and then? Right."; fn=carry_transcribe.transcribe
elif cfg=='G': kw['compression_ratio_threshold']=1.8; kw['initial_prompt']=P; fn=carry_transcribe.transcribe
t=time.time(); r=fn(A,**kw)
txt=' '.join(s['text'].strip() for s in r['segments']); toks=txt.split()
runs=[];c=0
for x in toks:
    c+=1
    if re.search(r'[.,?!]$',x): runs.append(c);c=0
runs.append(c)
low=[x for x in toks if re.match(r"^i('m|'ve|'d|'ll)?[.,?!]?$",x,re.I)]
# repeated 4-gram adjacent loops
rep=0
for n in (3,4,5,6):
    for i in range(len(toks)-2*n):
        if [w.lower().strip('.,?!') for w in toks[i:i+n]]==[w.lower().strip('.,?!') for w in toks[i+n:i+2*n]]: rep+=1
leak=sum(any(p in s['text'].lower() for p in ('tell me about it. tell','i suppose so','and then? right')) for s in r['segments'])
print(cfg,json.dumps(dict(secs=round(time.time()-t),words=len(toks),sentences=len(re.findall(r'[.?!](\s|$)',txt)),i_lower=f"{sum(x[0]=='i' for x in low)}/{len(low)}",longest_unpunct=max(runs),pct_words_in_40plus=round(100*sum(r for r in runs if r>=40)/len(toks)),adjacent_ngram_repeats=rep,fallback_segs=sum(s['temperature']>0 for s in r['segments']),segs=len(r['segments']),prompt_leak=leak)))
json.dump(r['segments'],open(f'full_{cfg}_{int(time.time())}.json','w'))
