#!/bin/bash
# usage: run_mutants.sh <abs-testfile>  -> per-mutant KILLED/SURVIVED, imports verified
SP=/private/tmp/claude-501/-Users-cassio-Code-bristlenose/8528b534-261d-4ea1-acff-5b1010e18cc8/scratchpad/skills-research
PY=/Users/cassio/Code/bristlenose/.venv/bin/python; T="$1"; export PYTHONDONTWRITEBYTECODE=1
for id in BASE M1 M2 M3 M4 M5 M6 M7 M8 M9 M10 M11 M12; do
  W=$SP/mut-work-$$; rm -rf $W; mkdir -p $W; cp -R $SP/tree/bristlenose $W/
  if [ $id != BASE ]; then $PY - "$id" "$W" <<'PY2' || { echo "$id APPLY-FAILED"; continue; }
import sys; sys.path.insert(0, '/private/tmp/claude-501/-Users-cassio-Code-bristlenose/8528b534-261d-4ea1-acff-5b1010e18cc8/scratchpad/skills-research/pbt-keys')
from mutants import MUTANTS
mid, w = sys.argv[1], sys.argv[2]
_, f, old, new, _ = next(m for m in MUTANTS if m[0] == mid)
p = f"{w}/{f}"; s = open(p).read(); assert s.count(old)==1; open(p, "w").write(s.replace(old, new))
PY2
  fi
  where=$(cd $W && PYTHONPATH="$W:$SP/pydeps" $PY -c "import bristlenose.utils.timecodes as t;print(t.__file__)")
  case $where in $W/*) ;; *) echo "$id WRONG-IMPORT $where"; continue;; esac
  kills=0; last=""
  for seed in 0 1 2; do
    rm -rf $W/.hypothesis
    last=$(cd $W && PYTHONPATH="$W:$SP/pydeps" $PY -m pytest -q -c /dev/null -p no:cacheprovider --rootdir=$W --hypothesis-seed=$seed "$T" 2>&1 | tail -1)
    case "$last" in *[0-9]" failed"*|*[0-9]" error"*) kills=$((kills+1));; esac
  done
  echo "$id kills=$kills/3  last: $last"
done; rm -rf $SP/mut-work-$$
