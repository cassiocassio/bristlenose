#!/bin/bash
# The local arms, one after another (one Ollama model loaded at a time).
# Uses installed models only; never pulls. run_arm.py waits before every
# session until no other `bristlenose analyze` or `ollama pull` runs on this Mac.
#   experiments/discussion-prompt-eval/run_local.sh EVAL_DIR [DONE_FLAG]
E="$1"; FLAG="${2:-}"
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python; R=experiments/discussion-prompt-eval/run_arm.py
ALL=talismanic-noguide,talismanic,synthetic-gold,rockclimbing,fossda
TAL=talismanic-noguide,talismanic
arm() { "$PY" "$R" "$E" "$@" --done-flag "$FLAG" >> "$E/log-local.txt" 2>&1; }
arm gemma-v100  --prompt 1.0.0  --llm local --model gemma4:e4b --studies $ALL
arm gemma-v110  --prompt 1.1.0  --llm local --model gemma4:e4b --studies $ALL
arm gemma-v110b --prompt 1.1.0b --llm local --model gemma4:e4b --studies $TAL,synthetic-gold
arm gemma-v100r --prompt 1.0.0  --llm local --model gemma4:e4b --studies $TAL
arm gemma-v110r --prompt 1.1.0  --llm local --model gemma4:e4b --studies $TAL
ollama stop gemma4:e4b >/dev/null 2>&1
arm qwen-v100   --prompt 1.0.0  --llm local --model qwen3.5:9b --studies $ALL
arm qwen-v110   --prompt 1.1.0  --llm local --model qwen3.5:9b --studies $ALL
ollama stop qwen3.5:9b >/dev/null 2>&1
echo "local arms done $(date +%H:%M)" >> "$E/log-local.txt"
