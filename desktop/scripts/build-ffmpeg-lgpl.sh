#!/usr/bin/env bash
# Build the Mac app's bundled ffmpeg + ffprobe: LGPL-2.1-or-later, static,
# arm64, from release tarballs pinned by SHA256.
#
# Why we build it (25 Nov 2026): the app ships under Apple's EULA, which a GPL
# binary can't go out under, and no reputable source publishes a static LGPL
# macOS arm64 build with libass (martin-riedl.de: GPL only; conda-forge's LGPL
# build is dynamic, against OpenVINO, Vulkan, SDL2, librsvg…; BtbN: no macOS).
# Until then we shipped martin-riedl's GPL build (x264, x265).
#
# What it builds, and why each piece is there:
#   ffmpeg 8.1.x  LGPL-2.1+   the programs. No --enable-gpl, --enable-nonfree or
#                             --enable-version3: version3 would make it LGPL-3.0,
#                             whose "installation information" clause a signed,
#                             sandboxed bundle can't meet (so no OpenSSL either).
#   libass        ISC         the `subtitles` filter (burnt-in clip subtitles).
#   freetype      FTL         libass's font rasteriser.
#   fribidi       LGPL-2.1+   libass's bidi text (Arabic, Hebrew cues).
#   harfbuzz      MIT         libass's shaper.
#   dav1d         BSD-2       AV1 decoding (FFmpeg has no software AV1 decoder).
# H.264 encoding for the burn is VideoToolbox (a system framework), not x264,
# which is GPL. Everything the app decodes is native FFmpeg except AV1. The
# coverage audit (every flag the code passes, against this build) is in the
# commit that added this script.
#
# --disable-autodetect: nothing on the build machine (Homebrew's SDL2, lzma…) can
# leak in; every library is named below. --disable-network: nothing we run reads
# a URL. --enable-indev=lavfi: the repo's tests make fixtures with `-f lavfi`, so
# the shipped binary can run them; it reads no device.
#
# Usage:
#   desktop/scripts/build-ffmpeg-lgpl.sh <out-dir>    build, gate, copy to <out-dir>
#   desktop/scripts/build-ffmpeg-lgpl.sh --version    print the version string
#
# Needs Xcode's clang, curl and python3.12 (for meson, ninja and pkgconf, which
# are pip-installed, hash-pinned, into a venv in the cache). About 4 minutes.
# The binary is not bit-reproducible across Xcode versions, so it is the SOURCES
# that are pinned; the gates at the end check what came out.

set -euo pipefail

FFMPEG_V=8.1.3
LIBASS_V=0.17.5
FREETYPE_V=2.14.3
FRIBIDI_V=1.0.18
HARFBUZZ_V=15.1.0
DAV1D_V=1.5.5
# Bump when a flag or a library changes, so a cached or installed binary from the
# previous recipe reads as stale (fetch-ffmpeg.sh --check compares this string).
BUILD_REV=1
VERSION="$FFMPEG_V-bristlenose-lgpl-$BUILD_REV"

if [ "${1:-}" = "--version" ]; then
    echo "$VERSION"
    exit 0
fi
OUT="${1:?usage: build-ffmpeg-lgpl.sh <out-dir> | --version}"

# name|url|sha256 — recorded 25 Nov 2026 from the projects' own release pages.
SOURCES=(
    "ffmpeg-$FFMPEG_V.tar.xz|https://ffmpeg.org/releases/ffmpeg-$FFMPEG_V.tar.xz|7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3"
    "libass-$LIBASS_V.tar.xz|https://github.com/libass/libass/releases/download/$LIBASS_V/libass-$LIBASS_V.tar.xz|2dca25c0e0c837ddf00b52011b3f82cac1e4ddd3ad018227806b0c2288864acc"
    "freetype-$FREETYPE_V.tar.xz|https://download.savannah.gnu.org/releases/freetype/freetype-$FREETYPE_V.tar.xz|36bc4f1cc413335368ee656c42afca65c5a3987e8768cc28cf11ba775e785a5f"
    "fribidi-$FRIBIDI_V.tar.xz|https://github.com/fribidi/fribidi/releases/download/v$FRIBIDI_V/fribidi-$FRIBIDI_V.tar.xz|1de5e8073d035388b71d0b2d452b1da1f8caeea8a7702997b401fe1b6250727f"
    "harfbuzz-$HARFBUZZ_V.tar.xz|https://github.com/harfbuzz/harfbuzz/releases/download/$HARFBUZZ_V/harfbuzz-$HARFBUZZ_V.tar.xz|0fc7c565443a5f4be7da65ac5ee5bd737d9b158dc908708b7689a0a5796b0c8d"
    "dav1d-$DAV1D_V.tar.xz|https://downloads.videolan.org/pub/videolan/dav1d/$DAV1D_V/dav1d-$DAV1D_V.tar.xz|ca96b1d0ba3f01f55de7231d775892b64994ba061aaeeaaa4f662a390b3abf9e"
)

# Build tools, from PyPI, hash-pinned (no dependencies of their own).
TOOLS_REQUIREMENTS='meson==1.12.1 --hash=sha256:930bc7542cbd9f57009e182fd014eba48cf1a0180a7b9006d2d32d8f168d8b02
ninja==1.13.2 --hash=sha256:fd82e26c0706ad4ab88e5fdd26f3fab0a987a90f810160f6c322e752c6af298b
pkgconf==3.0.7.post0 --hash=sha256:47cbf6889d84297b9a4e1741ae016daa4e198f3ec8bab7ce74554cc50b77cce4'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CACHE="$DESKTOP_DIR/build/ffmpeg-cache"
SRC="$CACHE/src"
TOOLS="$CACHE/tools-venv"
# A fixed, neutral path: ffmpeg embeds its configure line, prefix included, in
# both binaries, so building under the checkout would ship the builder's home
# directory in every copy of the app.
WORK="/private/tmp/bn-ffmpeg-lgpl-$VERSION"
BLD="$WORK/build"
P="$WORK/prefix"
LOG="$CACHE/build-$VERSION.log"

mkdir -p "$SRC" "$OUT"

# One build at a time: two would `rm -rf` each other's $WORK mid-compile (a
# Cmd+R during a terminal build, or two sessions in one checkout). A lock whose
# holder has died is taken over.
LOCK="$WORK.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    holder="$(cat "$LOCK/pid" 2>/dev/null || true)"
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        echo "error: another FFmpeg build is running (pid $holder; lock $LOCK)" >&2
        exit 1
    fi
    echo "==> Taking over a stale build lock ($LOCK)"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT
: > "$LOG"
echo "==> FFmpeg $VERSION (log: $LOG)"

# --- sources: download once, verify every time ------------------------------
for entry in "${SOURCES[@]}"; do
    IFS='|' read -r name url sha <<<"$entry"
    if [ ! -f "$SRC/$name" ]; then
        echo "==> Downloading $name"
        curl -fL --retry 3 --connect-timeout 30 --speed-time 60 --speed-limit 1024 \
            -o "$SRC/$name.tmp" "$url"
        mv "$SRC/$name.tmp" "$SRC/$name"
    fi
    actual="$(shasum -a 256 "$SRC/$name" | awk '{print $1}')"
    if [ "$actual" != "$sha" ]; then
        echo "error: SHA256 mismatch for $name" >&2
        echo "  expected: $sha" >&2
        echo "  actual:   $actual" >&2
        rm -f "$SRC/$name"
        exit 1
    fi
done

# --- build tools --------------------------------------------------------------
PYTHON="${PYTHON:-python3.12}"
if [ ! -x "$TOOLS/bin/meson" ] || [ ! -x "$TOOLS/bin/ninja" ] || [ ! -x "$TOOLS/bin/pkgconf" ]; then
    echo "==> Installing build tools (meson, ninja, pkgconf) into $TOOLS"
    rm -rf "$TOOLS"
    "$PYTHON" -m venv "$TOOLS" >>"$LOG" 2>&1
    "$TOOLS/bin/pip" install --quiet --require-hashes --no-deps --only-binary=:all: \
        -r /dev/stdin <<<"$TOOLS_REQUIREMENTS" >>"$LOG" 2>&1
fi

export PATH="$TOOLS/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PKG_CONFIG="$TOOLS/bin/pkgconf"
export PKG_CONFIG_LIBDIR="$P/lib/pkgconfig"   # only our prefix's .pc files
export PKG_CONFIG_PATH=""
export MACOSX_DEPLOYMENT_TARGET=15.0          # the app's floor
export CFLAGS="-arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET -O2"
export CXXFLAGS="$CFLAGS"
export LDFLAGS="-arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"
JOBS="$(sysctl -n hw.ncpu)"

rm -rf "$WORK"
mkdir -p "$BLD" "$P"
unpack() { tar -xJf "$SRC/$1.tar.xz" -C "$BLD"; }
step() { echo "==> $1"; echo "=== $1" >>"$LOG"; }

step "freetype $FREETYPE_V"
unpack "freetype-$FREETYPE_V"
(cd "$BLD/freetype-$FREETYPE_V" \
    && ./configure --prefix="$P" --enable-static --disable-shared --with-zlib=no \
        --with-bzip2=no --with-png=no --with-harfbuzz=no --with-brotli=no \
    && make -j"$JOBS" && make install) >>"$LOG" 2>&1

step "fribidi $FRIBIDI_V"
unpack "fribidi-$FRIBIDI_V"
(meson setup "$BLD/fribidi-$FRIBIDI_V/_b" "$BLD/fribidi-$FRIBIDI_V" --prefix="$P" \
    --libdir=lib --buildtype=release -Ddefault_library=static \
    -Ddocs=false -Dbin=false -Dtests=false \
    && ninja -C "$BLD/fribidi-$FRIBIDI_V/_b" install) >>"$LOG" 2>&1

step "harfbuzz $HARFBUZZ_V"
unpack "harfbuzz-$HARFBUZZ_V"
(meson setup "$BLD/harfbuzz-$HARFBUZZ_V/_b" "$BLD/harfbuzz-$HARFBUZZ_V" --prefix="$P" \
    --libdir=lib --buildtype=release -Ddefault_library=static -Dfreetype=enabled \
    -Dglib=disabled -Dgobject=disabled -Dcairo=disabled -Dicu=disabled -Dchafa=disabled \
    -Dcoretext=disabled -Dtests=disabled -Ddocs=disabled -Dutilities=disabled \
    -Dintrospection=disabled \
    && ninja -C "$BLD/harfbuzz-$HARFBUZZ_V/_b" install) >>"$LOG" 2>&1

step "libass $LIBASS_V"
unpack "libass-$LIBASS_V"
# CoreText finds fonts, not fontconfig; the burn passes fontsdir= with Inter
# beside the .ass file, so ours are the fonts libass reads.
(cd "$BLD/libass-$LIBASS_V" \
    && ./configure --prefix="$P" --enable-static --disable-shared --disable-fontconfig \
        --disable-libunibreak --enable-coretext \
    && make -j"$JOBS" && make install) >>"$LOG" 2>&1

step "dav1d $DAV1D_V"
unpack "dav1d-$DAV1D_V"
(meson setup "$BLD/dav1d-$DAV1D_V/_b" "$BLD/dav1d-$DAV1D_V" --prefix="$P" \
    --libdir=lib --buildtype=release -Ddefault_library=static \
    -Denable_tools=false -Denable_tests=false \
    && ninja -C "$BLD/dav1d-$DAV1D_V/_b" install) >>"$LOG" 2>&1

step "ffmpeg $FFMPEG_V"
unpack "ffmpeg-$FFMPEG_V"
# FFmpeg picks its own optimisation level, so no -O here. pkgconf by name, not
# path: the configure line is embedded in the binary (PATH finds ours first).
(cd "$BLD/ffmpeg-$FFMPEG_V" \
    && ./configure --prefix="$P" --pkg-config=pkgconf --pkg-config-flags=--static \
        --extra-version="bristlenose-lgpl-$BUILD_REV" --arch=arm64 --cc=clang --cxx=clang++ \
        --extra-cflags="-arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET" \
        --extra-ldflags="$LDFLAGS" \
        --enable-static --disable-shared --disable-ffplay --disable-doc --disable-debug \
        --disable-autodetect --disable-network \
        --disable-indevs --enable-indev=lavfi --disable-outdevs \
        --enable-videotoolbox --enable-audiotoolbox --enable-zlib --enable-bzlib --enable-iconv \
        --enable-libass --enable-libfreetype --enable-libharfbuzz --enable-libfribidi \
        --enable-libdav1d \
    && make -j"$JOBS") >>"$LOG" 2>&1
FF="$BLD/ffmpeg-$FFMPEG_V/ffmpeg"
FP="$BLD/ffmpeg-$FFMPEG_V/ffprobe"
strip -x "$FF" "$FP"

# --- gates: what came out, not what we asked for ------------------------------
step "checking the build"
fail() { echo "error: $1" >&2; exit 1; }
# Herestrings, not pipes: `cmd | grep -q` closes the pipe at the first match,
# and under pipefail the SIGPIPE makes a found match read as a failure.
for bin in "$FF" "$FP"; do
    text="$(strings -a "$bin")"
    cfg="$(grep -m1 -e '--prefix=' <<<"$text")" || fail "no configure line in $bin"
    for flag in --enable-gpl --enable-nonfree --enable-version3; do
        case " $cfg " in *" $flag "*) fail "$bin was configured with $flag" ;; esac
    done
    grep -qx -- "$VERSION" <<<"$text" || fail "$bin does not carry version $VERSION"
    # Only the OS's own libraries: nothing from Homebrew or the build tree.
    others="$(otool -L "$bin" | tail -n +2 | awk '{print $1}' | grep -v -E '^/(usr/lib|System/Library)/' || true)"
    [ -z "$others" ] || fail "$bin links outside the OS: $others"
    if grep -q -F -- "$HOME" <<<"$text"; then fail "$bin embeds the builder's home directory"; fi
done
grep -q "GNU Lesser General Public" <<<"$("$FF" -hide_banner -L 2>&1)" || fail "ffmpeg -L does not say LGPL"
grep -q -E '^ *[A-Z.]+ +subtitles ' <<<"$("$FF" -hide_banner -filters 2>/dev/null)" \
    || fail "no subtitles filter (libass)"
encoders="$("$FF" -hide_banner -encoders 2>/dev/null)"
grep -q -E ' h264_videotoolbox ' <<<"$encoders" || fail "no h264_videotoolbox encoder"
if grep -q -E ' lib(x264|x265) ' <<<"$encoders"; then fail "a GPL encoder is present"; fi
grep -q -E ' libdav1d ' <<<"$("$FF" -hide_banner -decoders 2>/dev/null)" || fail "no libdav1d decoder"

cp "$FF" "$FP" "$OUT/"
rm -rf "$WORK"
echo "==> Built $VERSION into $OUT"
(cd "$OUT" && shasum -a 256 ffmpeg ffprobe)
