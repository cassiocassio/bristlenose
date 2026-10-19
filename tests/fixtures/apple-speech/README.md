# The speech helper's JSON contract

`helper-output.json` is what `bristlenose-speech transcribe` writes: the contract
between the Swift helper (`desktop/speech-helper/`) and the Python backend
(`bristlenose/apple_speech.py`). Both sides read this file in their tests, so a
change to either side that breaks the other fails a test. The text is invented.

Fields (schema 1):

- `schema` — integer, bumped on any incompatible change.
- `engine` — always `"speech-transcriber"`.
- `locale` — the BCP 47 locale the model actually ran (Apple's equivalent of the one asked for).
- `asset_version` — the model asset's version string when the helper can read it, else `null`.
- `os_version` — `ProcessInfo.operatingSystemVersionString`.
- `audio_s`, `install_s` (null when nothing was fetched), `analyse_s` — seconds.
- `results` — one per final result, in order: `start`, `end`, `text`, and `words`
  (`start`, `end`, `text`, `conf`; `conf` may be null).

`bristlenose-speech probe` prints one line of JSON: `{"schema":1,"available":bool,
"reason":str|null,"os_version":str,"supported":[bcp47...],"installed":[bcp47...]}`.

Exit codes: 0 done; 2 usage or failure (message on stderr); 3 unavailable (below
macOS 26); 4 locale not supported; 5 model not installed and the fetch failed.
While analysing, stderr carries `@progress <seconds_done> <audio_s>` lines.
