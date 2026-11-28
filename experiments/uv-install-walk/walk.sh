#!/usr/bin/env bash
# Follow the website's Linux install page (docs-src/install.md) to the letter,
# in a fresh container, as a non-root user with sudo. One container per
# (image, route). Plan and results: docs/design-uv-install-route.md.
#
#   walk.sh <image> <route> <family> <wheel-dir> <log-dir> [pii]
#     route:  pipx | uv
#     family: apt | dnf | pacman
#     wheel-dir: holds a bristlenose wheel of the checkout, for the fix pass (uv only)
#     pii:    "pii" to redact the real transcripts (fetches the 400 MB model)
#   env: WALK_PLATFORM=linux/amd64 to emulate; WALK_MEDIA=<dir> real media to
#        transcribe (a project folder); WALK_HF_CACHE=<docker volume> to share
#        downloaded Whisper models between runs.
#
# What is NOT from the page (a desktop install already has it): sudo, a user
# with sudo rights, synced package lists, CA certificates, wget on Debian and
# Ubuntu, and SHELL set as a terminal sets it. Package-manager prompts are
# answered yes (-y / --noconfirm), as a person would. Each step runs in a fresh
# login shell, like a new terminal.
set -u
image=$1 route=$2 family=$3 wheel_dir=$4 log_dir=$5 pii=${6:-}
platform=${WALK_PLATFORM:-}
media=${WALK_MEDIA:-}
here=$(cd "$(dirname "$0")" && pwd)
name="walk-$(printf '%s' "$image" | tr ':/.' '---')-$route"
log="$log_dir/$name.log"
mkdir -p "$log_dir"
: >"$log"

say() { printf '%s\n' "$*" | tee -a "$log"; }

as_root() {
  docker exec "$name" bash -c "$1" >>"$log" 2>&1
}

# Run one documented command as the user, in a new login shell; log it and its exit.
step() {
  say "== STEP: $1"
  docker exec -u walker -e HOME=/home/walker -e SHELL=/bin/bash -w /home/walker \
    "$name" bash -lc "$1" >>"$log" 2>&1
  local rc=$?
  say "== EXIT: $rc"
  return $rc
}

mounts=(-v "$wheel_dir":/dist:ro -v "$here":/walk:ro)
[ -n "$media" ] && mounts+=(-v "$media":/media:ro)
[ -n "${WALK_HF_CACHE:-}" ] && mounts+=(-v "$WALK_HF_CACHE":/hf)

docker rm -f "$name" >/dev/null 2>&1
docker run -d ${platform:+--platform "$platform"} --name "$name" "${mounts[@]}" \
  "$image" sleep infinity >/dev/null || { say "== RUN FAILED"; exit 1; }

say "== IMAGE: $image ($route, $family) $(docker exec "$name" uname -m)"
case $family in
  # wget: Debian and Ubuntu desktops ship it (not curl); the Docker images ship neither.
  apt)    as_root "apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q sudo ca-certificates wget" ;;
  dnf)    as_root "dnf install -y -q sudo" ;;
  # Under x86_64 emulation pacman's download sandbox fails (seccomp: 22); a
  # container artifact, so it is switched off there only.
  pacman) [ -n "$platform" ] && as_root "sed -i '/^\[options\]/a DisableSandbox' /etc/pacman.conf"
          as_root "pacman -Syu --noconfirm sudo" ;;
esac
as_root "useradd -m -s /bin/bash walker && echo 'walker ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/walker"
if [ -n "${WALK_HF_CACHE:-}" ]; then
  as_root "chown walker /hf && mkdir -p /home/walker/.cache && ln -s /hf /home/walker/.cache/huggingface && chown -h walker /home/walker/.cache /home/walker/.cache/huggingface"
fi

# --- the page's commands ---------------------------------------------------
case "$family/$route" in
  apt/pipx)    step "sudo apt install -y ffmpeg pipx" ;;
  apt/uv)      step "sudo apt install -y ffmpeg"
               # "then uv with Astral's installer": the command on Astral's page,
               # with its wget form if curl is missing.
               step "if command -v curl; then curl -LsSf https://astral.sh/uv/install.sh | sh; else wget -qO- https://astral.sh/uv/install.sh | sh; fi" ;;
  dnf/pipx)    step "sudo dnf install -y ffmpeg-free pipx" ;;
  dnf/uv)      step "sudo dnf install -y ffmpeg-free uv" ;;
  pacman/pipx) step "sudo pacman -S --noconfirm ffmpeg python-pipx" ;;
  pacman/uv)   step "sudo pacman -S --noconfirm ffmpeg uv" ;;
esac

if [ "$route" = pipx ]; then
  step "pipx install bristlenose"
else
  step "uv tool install --python 3.14 bristlenose"
fi

if ! step "bristlenose --version"; then
  say "== NOTE: not found; following the page's next line, then a new terminal"
  if [ "$route" = uv ]; then step "uv tool update-shell"; else step "pipx ensurepath"; fi
  step "bristlenose --version"
fi
step "bristlenose doctor"

if [ "$route" = uv ]; then
  py='"$(uv tool dir)/bristlenose/bin/python"'
else
  # pipx 1.0 (Ubuntu 22.04) has no `environment`; its venvs are under ~/.local/pipx.
  py='"$(pipx environment --value PIPX_LOCAL_VENVS 2>/dev/null || echo ~/.local/pipx/venvs)/bristlenose/bin/python"'
fi

step "$py -c 'from bristlenose.utils.install_channel import install_channel as c, add_extra_command as a; print(c(), \"|\", a(\"voice\"))'"

# --- the fix pass (uv only): the PyPI release, then this checkout ------------
if [ "$route" = uv ]; then
  say "== FIX PASS: what stage 7 runs on the released version (spacy download, no pip)"
  step "$py -m pip --version"
  step "$py -m spacy download en_core_web_lg"
  wheel=$(cd "$wheel_dir" && ls bristlenose-*.whl | head -1)
  # --python named: --force re-resolves the interpreter otherwise (an Intel
  # Mac went 3.12 -> 3.14 and broke), which is why our hints name it too.
  step "uv tool install --force /dist/$wheel --python 3.14"
  step "$py -c 'import sys; print(\"python\", sys.version.split()[0])'"
  step "$py -c 'from bristlenose.stages import s07_pii_removal as s; print(\"needs_user_cache\", s.spacy_model_needs_user_cache())'"
  step "$py -c 'from bristlenose.doctor_fixes import get_mlx_install_command as g; print(g()[1])'"
  step "$py -c 'from bristlenose.utils.install_channel import install_channel as c, add_extra_command as a; print(c(), \"|\", a(\"voice\"))'"
fi

# --- real media: transcribe, then FFmpeg thumbnails, PII and serve -----------
if [ -n "$media" ]; then
  say "== MEDIA: transcribe a real project, then probe"
  step "rm -rf ~/project && cp -r /media ~/project"
  step "bristlenose transcribe ~/project -w tiny 2>&1 | tail -25; test -d ~/project/bristlenose-output/transcripts-raw"
  step "$py /walk/probe.py ~/project $pii"
fi

if [ "$route" = uv ]; then
  # The voice hint uv users get from doctor, word for word, from this checkout's code.
  step "cmd=\$($py -c 'from bristlenose.utils.install_channel import add_extra_command as a; print(a(\"voice\"))'); echo \"\$cmd\"; eval \"\$cmd\" && $py -c 'import sys, kaldi_native_fbank; print(\"voice on python\", sys.version.split()[0])'"
fi

say "== DONE"
docker rm -f "$name" >/dev/null 2>&1
