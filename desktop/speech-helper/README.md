# bristlenose-speech

Transcribes one WAV with Apple's on-device `SpeechTranscriber` (macOS 26+) and writes JSON.
The bundled sidecar launches it. Plan: `docs/design-apple-first-transcription.md` §3 A;
evidence: `experiments/apple-speech/README.md`.

```
bristlenose-speech probe                                   # one JSON line on stdout
bristlenose-speech transcribe <wav> <bcp47-locale> <out.json>
```

The JSON contract, the exit codes and the `@progress` lines are in
`tests/fixtures/apple-speech/README.md`, with `helper-output.json` as the fixture both sides
read. In short: exit 0 done, 2 usage or failure, 3 unavailable, 4 locale not supported, 5
model fetch failed. Keys are written sorted, `null` is never omitted, and `asset_version` is
always `null`, because no public API reports the model's version.

`transcribe` fetches the locale's model if this executable hasn't got it, and records
`install_s` only when something was actually downloaded. It then releases every reservation
it holds for that locale, matched by BCP 47, so it never keeps more than one of the five a
process may hold.

## Build and gate

```sh
SIGN_IDENTITY="-" HELPER_VERSION="0.40.0+5150" desktop/speech-helper/build-helper.sh <out-dir>
desktop/scripts/check-speech-helper.sh <binary>...
```

It is built like `desktop/mcp-helper/`: an embedded Info.plist, `minos` set to the app's floor
read from the pbxproj, compiled in a directory of its own, and a stamp file so an unchanged
build is skipped. It is **signed like ffmpeg**: app-sandbox + inherit and nothing else, with
Hardened Runtime and the identifier `app.bristlenose.speech` for every signer kind. Ad-hoc
signing is allowed. The gate checks for arm64 only, the floor, the Info.plist id, a signature
that verifies, exactly those two entitlements, and the runtime flag.

**Run standalone, the signed binary traps (exit 133).** `inherit` needs a sandboxed parent.
To try it by hand, re-sign a copy without entitlements
(`codesign --force --sign - --identifier app.bristlenose.speech <copy>`), or launch it from a
sandboxed app's `Contents/Helpers`, which is how it ships.

No `PrivacyInfo.xcprivacy`: neither `mcp-helper` nor ffmpeg ships one for a bare tool, and
this one calls no required-reason API. That is for the app-store-police pass to confirm.
