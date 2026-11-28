#!/usr/bin/env bash
# Run walk.sh across the distro matrix, four containers at a time.
#
#   matrix.sh <wheel-dir> <media-dir> <log-dir>
#
# Arm images run natively on an Apple-silicon Mac; Arch has no Arm image, so it
# runs as x86_64 under emulation. Results: grep '== EXIT\|PROBE' <log-dir>/*.log
set -u
wheel_dir=$1 media=$2 log_dir=$3
here=$(cd "$(dirname "$0")" && pwd)
docker volume create bn-walk-hf >/dev/null

# image route family platform pii
cat <<'EOF' | grep -v '^#' | xargs -P 4 -L 1 bash -c '
  WALK_PLATFORM=$4 WALK_MEDIA="'"$media"'" WALK_HF_CACHE=bn-walk-hf \
    bash "'"$here"'/walk.sh" "$1" "$2" "$3" "'"$wheel_dir"'" "'"$log_dir"'" "$5" >/dev/null 2>&1
  echo "finished $1 $2"' _
debian:trixie uv apt linux/arm64 pii
debian:trixie pipx apt linux/arm64 -
debian:bookworm uv apt linux/arm64 -
debian:bookworm pipx apt linux/arm64 -
ubuntu:22.04 uv apt linux/arm64 -
ubuntu:22.04 pipx apt linux/arm64 -
ubuntu:24.04 uv apt linux/arm64 -
ubuntu:24.04 pipx apt linux/arm64 -
ubuntu:26.04 uv apt linux/arm64 -
ubuntu:26.04 pipx apt linux/arm64 -
fedora:43 uv dnf linux/arm64 -
fedora:43 pipx dnf linux/arm64 -
fedora:44 uv dnf linux/arm64 pii
fedora:44 pipx dnf linux/arm64 -
archlinux:latest uv pacman linux/amd64 pii
archlinux:latest pipx pacman linux/amd64 -
EOF
