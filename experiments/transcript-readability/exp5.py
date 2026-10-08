import sys,re,json; sys.path.insert(0,'.')
import mlx_whisper, carry_transcribe
from mlx_whisper.audio import load_audio
A=load_audio('ja.wav')
kw=dict(path_or_hf_repo='mlx-community/whisper-large-v3-turbo',word_timestamps=True,verbose=None,condition_on_previous_text=False,no_speech_threshold=0.85,compression_ratio_threshold=1.8)
def show(name,r):
    txt=''.join(s['text'].strip() for s in r['segments'])
    print(name,'lang',r['language'],'chars',len(txt),'。',txt.count('。'),'、',txt.count('、'),'？',txt.count('？')+txt.count('?'),'spaces',sum(s['text'].strip().count(' ') for s in r['segments']), 'latin-words',len(re.findall(r'[A-Za-z]{3,}',txt)))
    print('   ',' / '.join(s['text'].strip() for s in r['segments'][1:4])[:300])
show('ja current (auto)',mlx_whisper.transcribe(A,language=None,**kw))
show('ja carry ja-prompt',carry_transcribe.transcribe(A,language='ja',initial_prompt="えーと、はい。そうですね、それでは始めましょう。",**kw))
show('ja carry EN-prompt auto',carry_transcribe.transcribe(A,language=None,initial_prompt="Hmm, okay. Well, yes, I suppose so, um, and then? Right.",**kw))
