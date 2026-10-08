import sys,re,json; sys.path.insert(0,'.')
import mlx_whisper
from mlx_whisper.audio import load_audio
A=load_audio('s1.wav'); SR=16000; clip=A[60*SR:360*SR]
r=mlx_whisper.transcribe(clip,path_or_hf_repo='mlx-community/whisper-large-v3-turbo',language='en',word_timestamps=True,verbose=None,condition_on_previous_text=False,no_speech_threshold=0.85,compression_ratio_threshold=1.8)
txt=' '.join(s['text'].strip() for s in r['segments']); toks=txt.split()
print(json.dumps(dict(words=len(toks),sentences=len(re.findall(r'[.?!](\s|$)',txt)),segments=len(r['segments']),fallback=sum(1 for s in r['segments'] if s['temperature']>0))))
