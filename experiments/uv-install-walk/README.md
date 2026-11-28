# uv install walk

Follows the website's Linux install page (`docs-src/install.md` in the website
repo) to the letter in fresh containers, for both self-managed routes (pipx and
uv), then exercises the installed tool with real media. Plan, evidence and
decisions: `docs/design-uv-install-route.md`.

## Run it

```bash
# 1. A wheel of this checkout (the fix pass installs it over the PyPI release)
uv build --wheel -o /tmp/bn-walk/dist

# 2. A project folder of real media (see "Media" below)

# 3. The matrix: Arm images natively on an Apple-silicon Mac, Arch as x86_64
bash experiments/uv-install-walk/matrix.sh /tmp/bn-walk/dist /path/to/media /tmp/bn-walk/logs
grep -H '== EXIT\|PROBE' /tmp/bn-walk/logs/*.log
```

One distro and route on its own:

```bash
WALK_PLATFORM=linux/arm64 WALK_MEDIA=/path/to/media \
  bash experiments/uv-install-walk/walk.sh debian:trixie uv apt /tmp/bn-walk/dist /tmp/bn-walk/logs pii
```

## What each run does

1. Root setup a desktop already has: `sudo`, a user with sudo rights, package
   lists, CA certificates, `wget` on Debian and Ubuntu, `SHELL` as a terminal
   sets it. Nothing else.
2. The page's commands for that distro and route, prompts answered yes, each
   in a new login shell. If `bristlenose` is not found, the page's next line
   (`uv tool update-shell` or `pipx ensurepath`), then a new shell.
3. `bristlenose --version` and `bristlenose doctor`. Doctor exits 1 when the
   only failure is the missing API key; that is expected.
4. uv only, the fix pass: the released version's `spacy download` (fails with
   no pip), then this checkout's wheel, the PII route it chooses, and the MLX
   fix command it would run.
5. With media: `bristlenose transcribe -w tiny`, then `probe.py`, which checks
   the transcripts, cuts a thumbnail from every video with FFmpeg, redacts PII
   on the real transcripts (with `pii`), and starts `bristlenose serve` and
   fetches `/api/health` and `/report/`.
6. uv only: the voice hint uv users get from doctor, word for word.

No LLM call is made anywhere, so no key is needed and nothing is billed.

## Media

The project folder used on 28 Nov 2026 was cut from the Talismanic study (the
public test data, used with the participants' agreement): 90 s clips of the
two Teams recordings and the Google Meet recording with their original file
names, the Teams Word transcript, a phone-style HEVC `.MOV`, M4A, MP3 and WAV
audio, a silent WAV, and the named cloud VTT from
`tests/fixtures/platform-transcripts/`. The media is not committed.

## Not covered

- The Snap (needs systemd) and the Copr package (not uv).
- Windows (the one-liner and the uv route have their own CI job and walk).
- Linux Mint has no official image; Ubuntu 24.04 is its base.
- Arch runs under emulation; pacman's download sandbox is switched off there
  only, because seccomp fails under emulation.
- Analysis (`run`, `analyze`): it needs an LLM key.
