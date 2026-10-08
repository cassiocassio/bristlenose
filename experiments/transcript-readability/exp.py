import mlx_whisper, numpy as np, re, json, time, sys
from mlx_whisper.audio import load_audio
A=load_audio('s1.wav'); SR=16000
clip=A[60*SR:360*SR]   # 1:00–6:00
M='mlx-community/whisper-large-v3-turbo'
PROMPT="Okay, so, um, tell me about it. Well, I think it's good, you know? Yeah."
def metrics(text):
    toks=text.split()
    pron=[t for t in toks if re.match(r"^i('m|'ve|'d|'ll)?[.,?!]?$",t,re.I)]
    low=sum(t[0]=='i' for t in pron)
    runs=[];c=0
    for t in toks:
        c+=1
        if re.search(r'[.,?!]$',t): runs.append(c);c=0
    runs.append(c)
    sents=len(re.findall(r'[.?!](\s|$)',text))
    return dict(words=len(toks),sentences=sents,words_per_sentence=round(len(toks)/max(1,sents),1),pronoun_i_lower=f"{low}/{len(pron)}",longest_unpunct_run=max(runs),words_in_40plus_runs=sum(r for r in runs if r>=40))
base=dict(path_or_hf_repo=M,language='en',word_timestamps=True,verbose=None,condition_on_previous_text=False,no_speech_threshold=0.85,compression_ratio_threshold=1.8)
def run(name,audio=clip,**kw):
    o=dict(base);o.update(kw); t=time.time()
    r=mlx_whisper.transcribe(audio,**o)
    txt=' '.join(s['text'].strip() for s in r['segments'])
    m=metrics(txt); m['secs']=round(time.time()-t,1); m['segments']=len(r['segments'])
    print(name, json.dumps(m)); open(f'exp_{name}.txt','w').write('\n'.join(f"{s['start']+60:7.1f} {s['text'].strip()}" for s in r['segments']))
    return r
run('A_current')
run('A_current_again')
run('B_condition_true',condition_on_previous_text=True)
run('C_prompt_first_window',initial_prompt=PROMPT)
run('D_prompt_and_condition',initial_prompt=PROMPT,condition_on_previous_text=True)
# E: prompt on every window, by cutting 30 s chunks ourselves
segs=[]; t=time.time()
for k in range(0,len(clip),30*SR):
    r=mlx_whisper.transcribe(clip[k:k+30*SR],**{**base,'initial_prompt':PROMPT})
    segs+= [s['text'].strip() for s in r['segments']]
txt=' '.join(segs); m=metrics(txt); m['secs']=round(time.time()-t,1); print('E_prompt_every_30s_chunk',json.dumps(m)); open('exp_E.txt','w').write('\n'.join(segs))
