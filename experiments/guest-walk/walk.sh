#!/bin/bash
# walk.sh <run-name> — one walk through the app in the guest, from the host.
#
# Every step is: do something by element name, wait for the state, capture.
# A step that fails HALTS the walk with a screenshot and the reason, so the
# morning shows "stopped at step N because X", never a silent partial walk.
# Output lands in the guest at ~/walk/out/<run-name>/ and is pulled to
# $OUT/<run-name>/ on the host: NN-name.png, NN-name.menus.jsonl, walk.log.
set -uo pipefail
RUN="${1:?run name}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OUT:-/private/tmp/bn-walk}"
B=app.bristlenose
GD="/Users/admin/walk/out/$RUN"
W=/Users/admin/walk/bin/walker
N=0
log() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$OUT/$RUN/walk.log"; }
g() { "$HERE/g.sh" "$@"; }

rm -rf "$OUT/$RUN"; mkdir -p "$OUT/$RUN"; : > "$OUT/$RUN/walk.log"
g rm -rf "$GD"; g mkdir -p "$GD"

halt() {
  log "HALT at step $N: $*"
  g "$W" shot "$B" "$GD" "halt" >/dev/null 2>&1
  g screencapture -x "$GD/halt-screen.png" >/dev/null 2>&1
  "$HERE/pull.sh" "$GD" "$OUT/$RUN" >/dev/null
  echo "HALTED step $N: $*" > "$OUT/$RUN/verdict.txt"
  exit 1
}
# do <description> <walker args…>: an action that must succeed
do_() { local d="$1"; shift; g "$W" "$@" >>"$OUT/$RUN/walk.log" 2>&1 || halt "$d ($*)"; }
# shot <name> [window-sub]: capture, with the menu tree for the same state
shot() {
  N=$((N + 1)); local name; name=$(printf '%02d-%s' "$N" "$1")
  sleep "${SETTLE:-1.5}"   # let animations finish; a capture mid-animation is noise
  g "$W" shot "$B" "$GD" "$name" ${2:+"$2"} >>"$OUT/$RUN/walk.log" 2>&1 || halt "capture $name"
  g sh -c "$W menus $B > $GD/$name.menus.jsonl" || halt "menus $name"
  log "step $N: $1"
}

if [ "${PROVIDER:-}" = ollama ]; then
  GUEST="${GUEST:-bn-walk}" "$HERE/tunnel.sh" up >>"$OUT/$RUN/walk.log" 2>&1 || { echo "HALTED: Ollama tunnel" > "$OUT/$RUN/verdict.txt"; exit 1; }
  trap 'GUEST="${GUEST:-bn-walk}" "$HERE/tunnel.sh" down >/dev/null 2>&1' EXIT
fi
T0=$(date +%s)
log "walk $RUN: $(g sw_vers -productVersion) guest, app $(g defaults read /Applications/Bristlenose.app/Contents/Info CFBundleShortVersionString) ($(g defaults read /Applications/Bristlenose.app/Contents/Info CFBundleVersion))"

# --- First launch -------------------------------------------------------------
# Fresh state every walk: the .dmg build keeps everything in its sandbox
# container (no app group), so removing it is a first launch. Guest only.
g sh -c 'pkill -x Bristlenose; sleep 1; rm -rf ~/Library/Containers/app.bristlenose ~/Documents/smoke-project/bristlenose-output ~/Documents/smoke-project/bristlenose-study.txt ~/Documents/"New Project"' >/dev/null 2>&1
g open -a /Applications/Bristlenose.app
do_ "app window appears" wait "$B" "Bristlenose" 60
shot first-launch

# The AI consent sheet is first-launch only; a re-walk on the same guest skips it.
if g "$W" tree "$B" "Bristlenose" 2>/dev/null | grep -q '"Continue"'; then
  do_ "accept AI consent" press "$B" AXButton "Continue" "Bristlenose"
  shot consent-accepted
fi
if g "$W" windows "$B" | grep -q "Welcome to Bristlenose"; then
  do_ "close Welcome" press "$B" AXCloseButton "" "Welcome"
fi
shot empty-main

# --- Settings, every tab ------------------------------------------------------
do_ "open Settings" menu "$B" "Bristlenose>Settings…"
do_ "Settings window" wait "$B" "General" 10
for tab in General Appearance "LLM Provider" Transcription Accounts "MCP Agents"; do
  do_ "Settings tab $tab" press "$B" AXButton "$tab" ""
  do_ "Settings shows $tab" wait "$B" "$tab" 10
  # CHANGE=1 stands in for "new work landed": one deliberate change on one screen,
  # so the diff can be checked to catch exactly that screen and nothing else.
  if [ "${CHANGE:-0}" = 1 ] && [ "$tab" = "LLM Provider" ]; then
    do_ "raise concurrency" action "$B" AXSlider "" AXIncrement "$tab"
    do_ "raise concurrency" action "$B" AXSlider "" AXIncrement "$tab"
  fi
  shot "settings-$(echo "$tab" | tr 'A-Z ' 'a-z-')" "$tab"
done
# PROVIDER=ollama: the run uses the host's Ollama through tunnel.sh (no key, no
# spend, nothing installed in the guest). Asserted from the app's stored
# preference, not from what the pane looks like.
if [ "${PROVIDER:-}" = ollama ]; then
  do_ "LLM Provider tab" press "$B" AXButton "LLM Provider" ""
  do_ "Settings shows LLM Provider" wait "$B" "LLM Provider" 10
  do_ "select Ollama" select "$B" "Ollama" "LLM Provider"
  sleep 1
  do_ "turn on Ollama" press "$B" AXSwitch "" "LLM Provider"
  sleep 1
  # The Ollama row must carry the selected checkmark. (Reading the sandboxed
  # app's preference file from outside returned '' while the pane showed
  # Ollama selected: cfprefsd had not flushed it. The tree is what is true now.)
  g "$W" tree "$B" "LLM Provider" | python3 -c '
import sys
rows, cur = [], []
for line in sys.stdin:
    if line.strip().startswith("AXRow"):
        rows.append(cur); cur = []
    cur.append(line)
rows.append(cur)
ok = any(any("\"Ollama\"" in l for l in r) and any("checkmark.circle.fill" in l for l in r) for r in rows)
sys.exit(0 if ok else 1)' || halt "Ollama row is not the selected provider"
  log "provider: ollama (selected row checked in the accessibility tree)"
  shot settings-ollama "LLM Provider"
fi
do_ "close Settings" key "$B" "cmd+w"

# --- About --------------------------------------------------------------------
do_ "open About" menu "$B" "Bristlenose>About Bristlenose"
sleep 1
shot about
do_ "close About" key "$B" "cmd+w"

# --- A project from the smoke fixture, through the Open and Save panels ---------
# Every step asserts the state it should produce: a key that was "sent" proves
# nothing (run1 reported success with the Open panel still up and nothing added).
do_ "New Project" menu "$B" "File>New Project"
sleep 1.5
shot new-project-rename
do_ "accept the name" key "$B" "return"
do_ "Add Files" menu "$B" "File>Add Files…"
do_ "Open panel up" wait "$B" "Open" 10
shot open-panel "Open"
do_ "Go to Folder" key "$B" "cmd+shift+g"
do_ "Go-to sheet up" has "$B" "Open" "GoToWindow" 5
sleep 0.5
if [ "${FIXTURE:-smoke}" = screens ]; then
  # The screens fixture is a video and its same-named transcript: open the folder,
  # select both, so the pipeline pairs them and skips Whisper.
  # Go to the .mp4 itself, then extend one row down to its .vtt. (Going to the
  # folder selects the folder in the left column; cmd+a then selects nothing and
  # Add stays disabled.)
  do_ "set the path" set "$B" "/Users/admin/Documents/screens-project/Session 1.mp4"
  sleep 0.8
  do_ "confirm path" key "$B" "return"
  sleep 1.5
  do_ "extend to the transcript" key "$B" "shift+down"
else
  do_ "set the path" set "$B" "/Users/admin/Documents/smoke-project/Session 1.vtt"
  sleep 0.8
  do_ "confirm path" key "$B" "return"
  do_ "file selected" has "$B" "Open" "Session 1.vtt" 5
fi
sleep 1
shot open-panel-file-selected "Open"
do_ "press Add" press "$B" AXButton "Add" "Open"
do_ "save sheet up" has "$B" "New Project" "save-panel" 10
shot create-project-folder
do_ "press Create" press "$B" AXButton "Create" "New Project"
g sh -c 'for i in $(seq 1 80); do test -f "$HOME/Documents/New Project/Session 1.vtt" && exit 0; sleep 0.25; done; exit 1' \
  || halt "interview was not copied into the project folder within 10 s"
log "interview copied into ~/Documents/New Project"
# The run starts by itself. Its end is the pipeline's own terminus event in
# pipeline-events.jsonl, an exact key, not a reading of the sidebar's wording.
EV="/Users/admin/Documents/New Project/bristlenose-output/.bristlenose/pipeline-events.jsonl"
end=""
for i in $(seq 1 120); do   # 10 min
  end=$(g sh -c "grep -E '\"event\":\"run_(completed|failed|cancelled)\"' \"$EV\" 2>/dev/null | tail -1")
  [ -n "$end" ] && break
  sleep 5
done
[ -n "$end" ] || halt "run reached no terminus event in 10 min"
echo "$end" > "$OUT/$RUN/run-end.json"
log "run ended: $(python3 "$HERE/run_summary.py" < "$OUT/$RUN/run-end.json")"
sleep 3
shot run-outcome

# --- Every lens ----------------------------------------------------------------
for lens in Project Sessions Quotes Codebooks Signals Discussion; do
  g "$W" menu "$B" "View>$lens" >>"$OUT/$RUN/walk.log" 2>&1 || { log "lens $lens: menu item not enabled (recorded, walk continues)"; continue; }
  shot "lens-$(echo "$lens" | tr 'A-Z' 'a-z')"
done

log "walk done in $(( $(date +%s) - T0 ))s, $N screens"
"$HERE/pull.sh" "$GD" "$OUT/$RUN" >/dev/null || { echo "pull failed"; exit 1; }
echo "COMPLETED $N screens in $(( $(date +%s) - T0 ))s" > "$OUT/$RUN/verdict.txt"
