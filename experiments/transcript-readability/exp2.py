import sys,json,time,re; sys.path.insert(0,'.')
import mlx_whisper
from mlx_whisper.audio import load_audio
import carry_transcribe
assert 'initial_prompt_tokens + all_tokens' in open('carry_transcribe.py').read()
A=load_audio('s1.wav'); SR=16000; clip=A[60*SR:360*SR]
M='mlx-community/whisper-large-v3-turbo'
PROMPT="Okay, so, um, tell me about it. Well, I think it's good, you know? Yeah."
def metrics(text):
    toks=text.split()
    pron=[t for t in toks if re.match(r"^i('m|'ve|'d|'ll)?[.,?!]?$",t,re.I)]
    low=sum(t[0]=='i' for t in pron); runs=[];c=0
    for t in toks:
        c+=1
        if re.search(r'[.,?!]$',t): runs.append(c);c=0
    runs.append(c); sents=len(re.findall(r'[.?!](\s|$)',text))
    return dict(words=len(toks),sentences=sents,words_per_sentence=round(len(toks)/max(1,sents),1),pronoun_i_lower=f"{low}/{len(pron)}",longest_unpunct_run=max(runs),words_in_40plus_runs=sum(r for r in runs if r>=40))
base=dict(path_or_hf_repo=M,language='en',word_timestamps=True,verbose=None,condition_on_previous_text=False,no_speech_threshold=0.85,compression_ratio_threshold=1.8)
def run(name,fn,**kw):
    o=dict(base);o.update(kw);t=time.time(); r=fn(clip,**o)
    txt=' '.join(s['text'].strip() for s in r['segments']); m=metrics(txt); m['secs']=round(time.time()-t,1); m['segments']=len(r['segments'])
    temps=[s.get('temperature',0) for s in r['segments']]; m['segs_temp_gt0']=sum(1 for x in temps if x>0)
    leak=sum(1 for s in r['segments'] if 'tell me about it' in s['text'].lower())
    m['prompt_leak_segments']=leak
    print(name,json.dumps(m)); open(f'exp_{name}.txt','w').write('\n'.join(f"{s['start']+60:7.1f} t={s.get('temperature',0)} {s['text'].strip()}" for s in r['segments']))
    return r
run('A_current',mlx_whisper.transcribe)
run('F_threshold_2.4',mlx_whisper.transcribe,compression_ratio_threshold=2.4)
run('G_carry_prompt_every_window',carry_transcribe.transcribe,initial_prompt=PROMPT)
run('H_carry_prompt_threshold_2.4',carry_transcribe.transcribe,initial_prompt=PROMPT,compression_ratio_threshold=2.4)
run('I_carry_neutral_prompt',carry_transcribe.transcribe,initial_prompt="Hello. Welcome, everyone. Let's begin.")
