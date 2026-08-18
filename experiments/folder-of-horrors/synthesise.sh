#!/usr/bin/env bash
# Build the synthetic half of the folder of horrors.
#
# Why synthesise rather than download: the 18 Aug 2026 survey of public corpora
# found that nobody maintains what we need. What exists is decoder-conformance
# corpora (AOMedia Argon: 7GB of raw AV1 OBU streams, no container) and
# container-parser suites (Matroska test1-8: 8 files, 21-31MB, zero VP8/VP9/
# AV1/Opus). Both answer "does my decoder produce the right pixels" — we are
# asking "does a folder of participant uploads survive ingest", which is a
# different question, so the corpus for it does not exist. Synthesis is
# reproducible, licence-free, and lets us pick durations.
#
# Every clip carries real speech via macOS `say`, so the corpus exercises
# transcription and not just demuxing. Falls back to a tone if `say` is absent.
#
# Usage: bash synthesise.sh [dest-dir]

set -uo pipefail

DEST="${1:-trial-runs/folder-of-horrors}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

die() { echo "FATAL: $*" >&2; exit 1; }
have() { ffmpeg -hide_banner -h encoder="$1" 2>&1 | head -1 | grep -q "Encoder $1"; }

command -v ffmpeg >/dev/null || die "ffmpeg not on PATH"
mkdir -p "$DEST" || die "cannot create $DEST"

# ---------------------------------------------------------------------------
# Source material: a spoken UX complaint over a moving test pattern.
# ---------------------------------------------------------------------------
LINE="The worst interface I used this year was the parking meter at the station. \
It asked for my registration before it told me the price, and the buttons \
did not respond until I pressed them twice."

if command -v say >/dev/null; then
    say -v Daniel -o "$WORK/speech.aiff" "$LINE" 2>/dev/null \
        || say -o "$WORK/speech.aiff" "$LINE" 2>/dev/null \
        || true
fi
if [ -s "$WORK/speech.aiff" ]; then
    AUDIO_IN=(-i "$WORK/speech.aiff")
    echo "==> speech track: $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WORK/speech.aiff")s"
else
    echo "==> 'say' unavailable — falling back to a tone (transcription rows will be meaningless)"
    AUDIO_IN=(-f lavfi -i "sine=frequency=300:duration=12")
fi

VIDEO_IN=(-f lavfi -i "testsrc2=size=640x360:rate=25:duration=12")

# One clip per line: <output-name> <ffmpeg args…>
# Names deliberately look like participant uploads, not like test fixtures.
emit() {
    local out="$1"; shift
    printf '  %-42s ' "$out"
    if ffmpeg -hide_banner -loglevel error -y \
        "${VIDEO_IN[@]}" "${AUDIO_IN[@]}" -shortest "$@" "$DEST/$out" 2>"$WORK/err"; then
        echo "ok  $(du -h "$DEST/$out" | cut -f1)"
    else
        echo "SKIP — $(head -1 "$WORK/err" | sed 's/\[[^]]*\] //' | cut -c1-60)"
        rm -f "$DEST/$out"
    fi
}

echo "==> containers and codecs"
emit "VID_20260818_142007.mp4"        -c:v libx264  -c:a aac
emit "IMG_0042.MOV"                   -c:v libx265 -tag:v hvc1 -c:a aac
emit "Screen Recording 2026-08-18.mov" -c:v prores_ks -profile:v 0 -c:a pcm_s16le
emit "obs-capture.mkv"                -c:v libx264  -c:a libopus
emit "recording.webm"                 -c:v libvpx   -c:a libopus -b:v 400k
emit "browser-capture.webm"           -c:v libvpx-vp9 -c:a libopus -b:v 400k
emit "pixel-9-clip.mp4"               -c:v libsvtav1 -preset 8 -c:a libopus
# native vorbis encoder is stereo-only, and `say` gives mono — upmix for this one
emit "vorbis-track.mkv"               -c:v libx264  -c:a vorbis -ac 2 -strict -2
emit "old-camcorder.avi"              -c:v mpeg4 -vtag XVID -c:a libmp3lame
emit "usability-lab-cam.avi"          -c:v mjpeg -q:v 6 -c:a pcm_s16le
emit "skype-for-business.wmv"         -c:v wmv2 -c:a wmav2
emit "feature-phone.3gp"              -c:v h263 -s 352x288 -c:a aac -ar 8000 -b:a 12k
emit "adobe-connect-webinar.flv"      -c:v flv -c:a libmp3lame -ar 44100
emit "avchd-camcorder.mts"            -c:v libx264 -c:a aac -f mpegts
emit "dvd-era-archive.mpg"            -c:v mpeg2video -c:a mp2 -f vob
emit "tape-capture.dv"                -c:v dvvideo -s 720x576 -pix_fmt yuv420p -r 25 -ar 48000 -ac 2 -c:a pcm_s16le -f dv
emit "audio-only-upload.m4a"          -vn -c:a aac
emit "voice-memo.mp3"                 -vn -c:a libmp3lame
emit "dictaphone.wav"                 -vn -c:a pcm_s16le -ar 16000 -ac 1
emit "lossless.flac"                  -vn -c:a flac

echo "==> the rough-up"
: > "$DEST/p07 failed download.mp4"                      # zero bytes, as found in the wild
echo "  p07 failed download.mp4                    ok  0B (zero-byte)"

if [ -f "$DEST/VID_20260818_142007.mp4" ]; then
    # truncated mid-transfer: keep the header, lose the moov atom at the tail
    full=$(stat -f %z "$DEST/VID_20260818_142007.mp4")
    dd if="$DEST/VID_20260818_142007.mp4" of="$DEST/interview half sent.mp4" \
       bs=1 count=$((full * 60 / 100)) 2>/dev/null
    echo "  interview half sent.mp4                   ok  $(du -h "$DEST/interview half sent.mp4" | cut -f1) (truncated to 60%)"
    # the extension lies: a QuickTime file wearing .mp4 is fine; a *text* file is not
    cp "$DEST/Screen Recording 2026-08-18.mov" "$DEST/actually-a-mov.mp4" 2>/dev/null \
        && echo "  actually-a-mov.mp4                        ok  (container/extension mismatch)"
fi
printf 'This is my write-up, not the video. Sorry!\n' > "$DEST/notes-not-video.mp4"
echo "  notes-not-video.mp4                       ok  (text wearing .mp4)"

# name collisions: six participants, one camera-default filename
for n in 2 3 4; do
    [ -f "$DEST/IMG_0042.MOV" ] && cp "$DEST/IMG_0042.MOV" "$DEST/IMG_0042 ($n).MOV"
done
echo "  IMG_0042 (2..4).MOV                       ok  (near-collision set)"

# non-ASCII and emoji names — the filesystem accepts them, our pipeline must too
[ -f "$DEST/VID_20260818_142007.mp4" ] && {
    cp "$DEST/VID_20260818_142007.mp4" "$DEST/Ana's worst UX 🙃.mp4"
    cp "$DEST/VID_20260818_142007.mp4" "$DEST/ユーザー調査 08.mp4"
    echo "  Ana's worst UX 🙃.mp4 / ユーザー調査 08.mp4     ok  (non-ASCII + emoji)"
}

# a silent video: the participant forgot to describe anything
ffmpeg -hide_banner -loglevel error -y "${VIDEO_IN[@]}" -an "$DEST/forgot-to-talk.mp4" 2>/dev/null \
    && echo "  forgot-to-talk.mp4                        ok  (no audio stream at all)"
# a zero-length video: pressed record and stop
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "testsrc2=size=640x360:rate=25:duration=0.04" \
    -f lavfi -i "sine=frequency=300:duration=0.04" -shortest -c:v libx264 -c:a aac \
    "$DEST/oops.mp4" 2>/dev/null && echo "  oops.mp4                                  ok  (0.04s)"

echo
echo "==> $(ls -1 "$DEST" | grep -vc 'manifest\|probe-all') files in $DEST ($(du -sh "$DEST" | cut -f1))"
echo "    known gaps needing a real download: AMR-NB/WB (no encoder), Theora (no libtheora), TSCC (decode-only)"
