#!/bin/zsh
# Sequential local runs on one Ollama version. Each run gets its own ollama-ps sampler.
S=/private/tmp/claude-501/-Users-cassio-Code-bristlenose/75b06500-a0fe-45b5-9b72-ace8e62f9869/scratchpad/olq
BN=/Users/cassio/Code/bristlenose/.venv/bin/bristlenose

sample() {  # $1 = name, $2 = host
  while true; do echo "$(date +%T) $(OLLAMA_HOST=$2 ollama ps | tail -n +2)"; sleep 10; done > $S/$1.ps.log 2>&1
}

run() {  # $1 = name, $2 = model, $3 = url, $4 = host
  ollama stop llama3.2:3b >/dev/null 2>&1; ollama stop gemma4:e4b >/dev/null 2>&1
  sample $1 $4 &
  local sp=$!
  cd $S/$1
  date -u +%FT%TZ > $S/$1.start
  BRISTLENOSE_LOCAL_MODEL=$2 BRISTLENOSE_LOCAL_URL=$3 /usr/bin/time -p $BN analyze transcripts-raw --llm local -p talismanic-$1 > $S/$1.log 2>&1
  echo "exit $?" >> $S/$1.log
  date -u +%FT%TZ > $S/$1.end
  kill $sp
  echo "RUN-DONE $1 $(grep -E 'Done in|exit' $S/$1.log | tr '\n' ' ')"
}

run llama llama3.2:3b http://localhost:11434/v1 127.0.0.1:11434
run gemma gemma4:e4b http://localhost:11434/v1 127.0.0.1:11434

# A 16 GB Mac falls in Ollama's <24 GiB tier: 4k context. Second server on 11435,
# same flash-attention / KV-cache settings as the Homebrew service, same model store.
ollama stop gemma4:e4b >/dev/null 2>&1
OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=4096 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 \
  /opt/homebrew/opt/ollama/bin/ollama serve > $S/server4k.log 2>&1 &
SRV=$!
for i in {1..30}; do curl -s 127.0.0.1:11435/api/version >/dev/null && break; sleep 1; done
run gemma4k gemma4:e4b http://127.0.0.1:11435/v1 127.0.0.1:11435
OLLAMA_HOST=127.0.0.1:11435 ollama stop gemma4:e4b >/dev/null 2>&1
kill $SRV
echo ALL-DONE
