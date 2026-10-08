"""Write carry_transcribe.py: mlx-whisper's transcribe.py with the initial prompt
carried to every 30 s window (openai-whisper's carry_initial_prompt form)."""
import mlx_whisper.transcribe as t

s = open(t.__file__).read().replace("from .", "from mlx_whisper.")
old = 'decode_options["prompt"] = all_tokens[prompt_reset_since:]'
assert s.count(old) == 1, "mlx-whisper moved the line; re-read transcribe.py"
s = s.replace(old, 'decode_options["prompt"] = initial_prompt_tokens + '
              'all_tokens[max(len(initial_prompt_tokens), prompt_reset_since):]')
open("carry_transcribe.py", "w").write(s)
