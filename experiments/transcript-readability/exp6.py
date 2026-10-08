import sys,re; sys.path.insert(0,'.')
import carry_transcribe
from mlx_whisper.audio import load_audio
A=load_audio('ja.wav')
r=carry_transcribe.transcribe(A,path_or_hf_repo='mlx-community/whisper-large-v3-turbo',word_timestamps=True,verbose=None,condition_on_previous_text=False,no_speech_threshold=0.85,compression_ratio_threshold=1.8,language=None,initial_prompt="Hmm, okay. Well, yes, I suppose so, um, and then? Right.")
for s in r['segments']:
    if re.search(r'[A-Za-z]{3,}',s['text']): print(round(s['start']),s['text'][:200])
