# Gotchas — the full entries

Moved verbatim from the root `CLAUDE.md` on 16 Oct 2026 to cut what every session and
agent loads on every turn. The root keeps a one-line index per theme and points here.
**Read the theme's section before working in that area.** Add a new gotcha here, and
a clause to the root index only if every session needs it.

## Shell, search and scripting

### A blocked PreToolUse hook kills the WHOLE Bash call, not the offending fragment

The `leak-scan.sh` / `block-checkout.sh` PreToolUse hooks match against the
**entire command string**, and a match blocks the whole invocation — so every
other command batched into that call silently never runs. Bit twice on 8 Aug
2026. First: a call doing `sed -i '' … && grep -cE '<blocked-pattern>' … && git
add …` was refused because the *grep pattern* named a blocked path. The grep was
a leak-**check**, not a leak. The `sed` never ran, and the next command reported
the file unchanged — which reads as "my edit didn't apply" rather than "the whole
call was refused". Second, and more instructive: the attempt to write *this very
gotcha* was refused, because the explanatory text quoted the blocked string as an
example.

Three rules. **(1)** Never put a blocked pattern in a command string, even as a
search term — grep via a shell variable, or use `git check-ignore` instead.
**(2)** The hook fires on Edit/Write to public docs too, so *documentation about*
a blocked pattern must paraphrase it (this file's own convention: say "the
maintainer's private planning notes, kept outside the public tree"). **(3)** After
a refusal, assume **nothing** in that call ran; re-verify state before
re-issuing, rather than assuming the parts before the offending fragment
succeeded.

### A subagent can overwrite your scratchpad files — namespace anything you will re-read

`/usual-suspects` subagents share the session's scratchpad directory. During the
22 Sep locale review one of them built its own `Probe.app` at the same path as
mine and rewrote its `Info.plist` — so a probe I had built to read one bundle
identifier silently started reporting another, and two measurements taken after
that point were against a bundle that was not the one I thought I was testing.

The tell was a bundle id I had never written. **Nothing errored**, and the
readings were internally consistent — they were simply about a different app.

**Two habits.** Put a session-unique token in the path (`mainloop-probe-7f3a/`),
and have the probe **assert its own identity** before reporting
(`guard Bundle.main.bundleIdentifier == "…" else { exit(3) }`). The second is
what makes a clobber loud instead of plausible. Generalises past probes to any
scratchpad artefact you write, walk away from, and read back while agents are
running.

### macOS BSD userland — use GNU coreutils

macOS ships BSD versions of `sed`, `grep`, `awk`, `find`, `xargs`, `date`, `stat`, `readlink`, `tar`, and others. These differ from the GNU versions in subtle, bug-inducing ways:

- **`sed`**: no `\b` word boundary, `-i` requires backup extension arg (`sed -i '' ...`), no `\x00` hex escapes. **Use `gsed`** (installed via `brew install gnu-sed`)
- **`grep`**: BSD `-P` (PCRE) doesn't exist. Use `ggrep` or `rg` (ripgrep) for PCRE patterns. **`git grep -E` uses the same libc regex, so `\b` matches nothing there either — silently.** A context grep returning empty for a symbol a plain grep just found is this trap, not an absent symbol (12 Sep 2026). **And `grep` on this machine is ugrep:** a bounded-repeat context pattern such as `.{0,140}foo.{0,200}` fails with "exceeds complexity limits" — use `-B`/`-A` line context or Python for a windowed match
- **`date`**: BSD uses `-j -f` for parsing, GNU uses `-d`. Completely incompatible date arithmetic
- **`readlink`**: BSD has no `-f` (canonicalize). Use `greadlink -f` or `realpath`
- **`xargs`**: BSD `-r` (no-run-if-empty) doesn't exist — GNU behaviour is the default on BSD but the flag is missing
- **`stat`**: completely different flag syntax (`-f` vs `-c` for format strings)
- **`tar`**: BSD tar is `bsdtar` (libarchive), differs from GNU tar in flag handling, especially for `--transform`
- **`find`**: BSD `-regex` uses basic regex by default (GNU uses Emacs regex); `-regextype` doesn't exist
- **`awk`**: BSD awk is ancient POSIX awk — no `gensub`, no `length(array)`, no `FPAT`

**Rule: when writing shell commands that use regex or platform-specific flags, prefer `gsed`/`ggrep`/`gawk`/`greadlink` (all from `brew install coreutils gnu-sed gawk findutils grep`), or use Python/Perl for portability.** The `g`-prefixed GNU tools are always available on this machine.

### zsh does NOT word-split unquoted variables — `for f in $LIST` silently iterates once

The Bash tool runs under zsh, and zsh (unlike bash/sh) does **not** perform word-splitting on unquoted parameter expansions. So the everyday bash idiom `LIST="a.md b.md"; for f in $LIST; do …; done` treats the whole string as **one** word — `[ -f "$f" ]` then fails for the nonexistent filename `"a.md b.md"`, the loop body never runs, and **nothing errors**. The silent-no-op is the trap: a bulk `gsed -i` sweep over a file list "succeeds" (exit 0, no output) while changing zero files, and you only notice when the verification step reports the same findings you thought you'd just fixed (cost a debug cycle during the 15 Jul docs-truing sweep). Fixes: iterate an explicit literal list (`for f in a.md b.md; do`), use a real array (`files=(a.md b.md); for f in "${files[@]}"`), force splitting with zsh's `${=LIST}`, or `printf '%s\n' … | while read -r f`. Same family as the unmatched-glob gotcha below — zsh's defaults differ from bash in ways that fail *quietly*, so **verify a bulk edit actually changed files** (`git status` / re-grep) rather than trusting a clean exit. **Same family: `$PIPESTATUS` is bash.** zsh spells it `$pipestatus`, lowercase; the bash form expands to *empty* under zsh, so `echo "exit: ${PIPESTATUS[0]}"` prints `exit:` and reads as a missing verdict rather than a wrong variable (4 Sep 2026). **And a word beginning with `=` is a command lookup, not text.** zsh's `=cmd` expansion turns `=ls` into `/bin/ls`, so a separator like `echo =====` between two `cat`s fails with `(eval):1: ===== not found` — and the rest of that line does not run, so the second file is silently absent from the output rather than visibly failed. Use `---` or quote it (5 Sep 2026).

**And `path=` is the PATH array.** zsh ties the lowercase `path` to `PATH`, so a loop that sets `path="locales/$code/desktop.json"` makes every later `git` and `python3` in that call `command not found` — the variable looked like any other and the first iteration had already run (12 Oct 2026). Name it `file`. **And on a failure branch, never `git reset -q` with no paths:** the index is shared with every other session, and a bare reset unstages their `git add` along with yours. `git reset -q -- <your paths>` only.

### zsh reads `$VAR:x` as a MODIFIER — `"$BR:path"` is not "branch, colon, path"

`git show $BR:experiments/README.md` under zsh expands `$BR:e` as the
*extension* modifier, so git gets a mangled revision, prints *ambiguous
argument*, and writes nothing. When that output feeds a file, the file is empty.
On 11 Oct 2026 a plumbing commit then recorded the README as deleted, because
the next step's assert failed without stopping the chain. `:h`, `:t`, `:r`, `:e`,
`:s`, `:u`, `:l` are all modifiers. **Write `"${BR}:path"`**, braces always,
whenever a variable is followed by a colon. Same family as the two entries
around it: bash muscle memory that zsh honours differently and quietly.

### zsh unmatched-glob does NOT abort a multi-command Bash call

The Bash tool runs under zsh. When a glob matches nothing, zsh prints `zsh: no matches found: <pattern>` and — unlike `set -e` or bash's default — **skips that one command but continues to the next line in the same call.** So a "clean up, then run the payload" script whose cleanup glob matched nothing (`rm -f dir/*.json` with no files there) still runs the payload. The trap: you see the `no matches found` error, assume the whole script aborted, and **relaunch — double-running the payload.** This cost a real double-spend of LLM credits on the quote-stability experiment (3 Jul 2026: a background extraction ran twice because a guard `rm -f scratch/run_*.json` "failed" but Python ran anyway, then I relaunched). Fixes: use `find dir -name '*.json' -delete` (no-match-safe, no nomatch error), or guard with `setopt +o nomatch` / `2>/dev/null || true` **on its own line**, or just don't put a bare-glob cleanup ahead of a payload in the same call. When a Bash call errors early, verify what actually ran (check for output files) before relaunching.

**Same family, one line up the stack: an unquoted glob in a *flag argument* kills the whole call.** `grep -rn "x" dir --include=*.swift` fails with `zsh: no matches found: --include=*.swift` — zsh tries to expand `*.swift` against the *current directory* before grep ever sees it, so the flag only survives when a matching file happens to sit in `cwd`. It works from the repo root and fails from anywhere else, which reads as "grep is broken here". Bash passes the same string through untouched, so the idiom is muscle memory from everywhere else. **Quote it: `--include='*.swift'`.** Applies equally to `--exclude=`, `rsync --filter=`, `find -name`, and any tool taking a pattern as a flag value.


**Same family: an UNQUOTED heredoc runs `$(…)` inside the text it carries — and the call carries on.** `python3 - <<PY` (no quotes) whose Python inserts JavaScript like `$("span","seg")` hands that to the shell as a command substitution: zsh prints `command not found`, substitutes nothing, and the script writes `var seg = ;` into the file with exit 0 (8 Oct 2026, the release board's History toggle — caught only by the browser's fault band). **Quote the delimiter (`<<'PY'`) whenever the payload is code**, and read files in rather than interpolating shell variables into it.

### `/dev/tcp` is bash, not zsh — a port probe sourced into the Bash tool reads every port as closed

`release.sh`'s `board_link` checks the board's port with `( exec 3<>/dev/tcp/127.0.0.1/$port )`.
Sourced into the Bash tool — which is zsh — that redirection fails on every port, the
function returns silently, and "the driver prints nothing" reads as a bug in the function
(5 Sep 2026: a live, tokened server, a correct handshake, an empty result; under `bash -c`
the same call printed the link). Same family as the `log` builtin below: a shell default
that fails quietly. Prove a bash function under `bash -c`, not by sourcing it into the tool.

### `log show` never reaches the unified log — `log` is a zsh BUILTIN, so use `/usr/bin/log`

zsh ships a builtin named `log` (it lists watched users), so `log show --predicate …`
in the Bash tool never runs macOS's log CLI: zsh answers `(eval):log:1: too many
arguments`, and behind a `2>/dev/null` that is invisible — the query "returns
nothing", which reads as "launchd logged nothing". Cost four empty queries on 4 Sep
2026 while a launchd spawn failure sat in the log the whole time; `/usr/bin/log show`
with the identical predicate found it at once (`Unable to get updated LWCR …`).
**Always spell it `/usr/bin/log`**, bound the window with `--start/--end` rather
than `--last 4d` (a whole-store scan takes minutes), and predicate on `process` or
`subsystem`. Same family as the zsh word-splitting and nomatch gotchas above: a shell
default that fails quietly.

### `Path.resolve()` on a venv's `bin/python` gives you the BASE interpreter, not the venv

A venv's `bin/python` is a symlink to the base interpreter; CPython finds the
venv by looking for `pyvenv.cfg` beside the executable **as invoked**, so
resolving the symlink first (`Path.resolve()`, `realpath`, `readlink -f`) and
then running that path gives `sys.prefix == sys.base_prefix` and the base
install's site-packages — on this Mac, Homebrew's, holding one package. The
first run of the re-pointed inventory script did exactly that and wrote a
one-row `THIRD-PARTY-BINARIES.md` with exit 0 (5 Sep 2026). Use
`Path.absolute()` to keep the venv prefix — and know that this is necessary,
not sufficient: a symlink *to* the venv's python from outside its `bin/`
(`~/bin/sidecar-py -> .venv-sidecar/bin/python`) lands on the base interpreter
again, measured. The guard that survives both is semantic, not path-shaped:
refuse a target that does not carry the project's own distribution
(`scripts/check-dep-drift.py`, `generate-third-party-binaries.py`). **Tell:** an
inventory or `pip list` that is suspiciously short against an environment you
know is full.

Same family, one shell up: **`$PIPESTATUS` is bash; the Bash tool runs zsh,
where it is `$pipestatus` (lowercase) — the uppercase name expands to empty**, so
`cmd | tail -1; echo "rc=${PIPESTATUS[0]}"` prints `rc=` and reads as a
tooling glitch rather than a shell difference. Prove an exit code without a
pipe (`cmd >/dev/null 2>&1; echo $?`), or use zsh's spelling.

### `rg -rn` is NOT "recursive + line numbers" — `-r` is `--replace` and silently rewrites every match

Muscle memory from `grep -rn` is wrong for ripgrep: **rg is recursive by default**, and `-r/--replace` **takes an argument**. So `rg -rn "pattern" path/` parses as `-r n` — replace every match with the literal string `n` — and prints doctored lines with no error, no warning, and exit 0.

The trap is that the output still looks like source code. Searching for `mlx|cuda|ram` with `rg -rn` returned `import n_whisper`, `"n-community/whisper-large-v3"`, `ctranslate2.get_n_device_count()`, and `Memory: {self.n:.0f}GB` — every occurrence of the *search terms* replaced by `n`, in lines that otherwise parse as plausible Python. Bit twice in one session (2 Aug 2026); the second time the mangled hit was a real design doc (`design-gemma4-local-models.md` rendering as "n 4 model family"), which reads as a genuinely odd filename rather than a tooling artefact.

**Fix:** drop the `-r`. `rg -n "pattern" path/` is what you meant — recursion is implicit. If you genuinely want replacement it's `rg -r '<replacement>' "pattern"`, argument mandatory. **Tell:** identifiers that should be distinctive collapsing to a single repeated letter, or a match count that looks right while the matched *text* is missing the term you searched for.

Same family as the two zsh gotchas above — shell tooling whose defaults differ from the obvious analogue and fail *quietly*. When a search result looks strange, re-run the search before believing it.

### A `**/` git pathspec matches ZERO files at the top level — the sweep reports clean

`git diff --name-only -- 'dir/**/*.swift'` matches nothing for `dir/Foo.swift`.
Git's pathspec `**/` wants at least one intervening directory; it does **not**
collapse to nothing the way `.gitignore` semantics or a shell `**` would. So a
"list the files this branch added" sweep over a flat directory — which
`desktop/Bristlenose/Bristlenose/` is, 182 Swift files, no subdirectory but
`Shoal/` — returns an empty list, exit 0, no error. Measured 21 Sep 2026 while
writing the very close-out check meant to catch unenrolled i18n surfaces: it
would have shipped as a step that silently never fired.

**Fix: pass the directory and filter in the loop** — `-- desktop/Bristlenose/Bristlenose/ frontend/src/`
then `case "$f" in *.swift|*.tsx) ;; *) continue ;; esac`. Or `:(glob)` magic, if
you want the glob semantics you thought you had. **Tell:** a file-listing sweep
that returns nothing over a window you know contains matches — run the same
pathspec as a plain directory and compare the counts before believing the zero.
Same family as the zsh nomatch and `rg -rn` entries: tooling that fails quietly
and plausibly.

**Sibling: `git for-each-ref`'s `*` stops at a slash too.** `for-each-ref
'refs/heads/after-*'` matches `after-x` and *misses* `after-x/0.36.0`, so the
obvious way to list `after-<channel>/<version>` holds listed none, with exit 0
(measured 9 Oct 2026). List `refs/heads/` and filter with `grep -E '^after-'`.
`hold_refs` in `scripts/release.sh` carries the pin.

**And a deadline that kills the process but not its group still hangs `$(…)`.**
A command substitution waits for EOF on its pipe. A child of the timed-out
process that inherited stdout keeps the pipe open after its parent is killed, so
`out=$(timeout-ish cmd)` waits anyway. Fork into a new process group and kill
`-$pid`; `bounded` in `scripts/verify-channels.sh` is the working form, and the
`W3-*` scenarios in `scripts/channel-scenarios.txt` hang if either half is
removed (both mutants proved, 10 Oct 2026). macOS has no `timeout`; that is why
it is perl.

### `git ls-files` is the wrong corpus for a "does this file exist?" audit — it cannot see gitignored files

Reaching for `git ls-files` to enumerate the tree is natural and wrong for any
existence check that spans ignored paths: it lists what is **tracked**, so every
gitignored-but-present file reports as missing. Measured 12 Sep 2026 — a
cross-reference audit over the docs tree reported five files absent that were
sitting on disk, all of them in the gitignored maintainer-only notes tree. The
output is convincing because the *other* absences in the same list were real.

**Tell:** the "missing" set is suspiciously well-correlated with one directory,
and that directory is in `.gitignore`. **Fix:** resolve against the filesystem
(`Path.exists()`, `find`) and use `git ls-files` only when the question genuinely
is "is this tracked?"

**Sibling false positive from the same pass, and it fires on this very file:**
prose *about* a retired file reads as a dead pointer to a naive
`[text](path)` grep. The line above describing the retired single-page manual and
naming its archive location is correct and must not be "fixed". Before reporting a
broken link, read the sentence around it — a doc explaining that something *was*
removed is doing its job.

**The same blind spot, inverted — and this one produces a confident "nobody wrote
this down".** Searching `docs/` plus the CLAUDE.md files and concluding a decision is
unrecorded misses the gitignored maintainer-only notes, which is exactly where
planning decisions live. On 20 Sep 2026 a truing pass added a banner to
`design-locale-negotiation.md` stating the shipped language picker was an
undocumented reversal and "someone with the context should write it down" — while
the private notes already carried it as a Beta item, with the same evidence derived
independently (`I18n.swift:55`, the `?? "en"`), a decided fix (Option A, 2 Jul 2026)
and an implementation brief. The banner shipped, asking for work already planned.
**Before writing "this is recorded nowhere", say where you looked** — and if the
sentence is about a *decision* rather than code, the private notes are the first
place to look, not the last. Scope of a search is not scope of the world.

**And a path that does not resolve is not evidence the thing is gone — it may have
moved, which flips the verdict.** Testing a doc-named path with `Path.exists()`
cannot tell a deleted component from a relocated one, and the difference decides
whether a doc has a stale reference (fix the path) or describes a dead surface
(archive it). Measured in the same pass: of 51 doc-named paths that failed
`exists()`, **five had merely moved** — `components/QuoteCard.tsx` →
`islands/QuoteCard.tsx`, `layouts/SidebarLayout.tsx` → `components/SidebarLayout.tsx`,
`theme/css/tokens.css` → `theme/tokens.css`, `theme/css/organisms/transcript.css` →
`theme/templates/transcript.css`, `e2e/perf-gate.spec.ts` → `e2e/tests/perf-gate.spec.ts`
— and two of the wrong verdicts were handed to subagents before being caught. **Ask
for the basename across the tree** (`git ls-files | grep -i "/<Name>\."`), and only
call something deleted when the basename is absent everywhere. **Tell:** a "deleted"
component that the app self-evidently still renders.

Same family as the `rg -rn` and zsh entries above: tooling that fails quietly and
plausibly. An audit that produces a column of alarming findings deserves one
disconfirming check before the findings are written down.

### `set -e` does NOT fire on a failing left operand of `&&` — so `cmd && ok "passed"` is a gate that cannot fail

POSIX shells deliberately exempt any command whose status is *being tested* from `errexit`, and the left operand of `&&` is one. So this, which reads exactly like an assertion:

```bash
stapler validate "$DMG" && ok "stapler validate: passed"
```

…prints nothing on failure, raises nothing, and **falls straight through to the next line**. Verify it yourself: `bash -c 'set -euo pipefail; false && echo B; echo REACHED'` prints `REACHED` and exits `0`.

Two of `build-dmg.sh` stage 10's four final gates were written this way and were decorative through two releases (fixed 4 Aug 2026, `fc1d6ca7`). The near-miss it enabled: a complete, correctly-sized, correctly-hashed `.dmg` that `spctl` called `rejected — Unnotarized Developer ID` sat looking finished for 14 hours because the gate meant to catch that printed nothing.

**Rule: an assertion uses `|| die`, never `&& ok`.** If you want the success line too, `cmd || die "…"; ok "…"`. Applies equally to `cmd && a || b` chains — the `||` arm swallows a genuine failure of `a` as well. Audit any `check-*.sh` or build script for `&& ok`, `&& echo`, `&& printf` where the left side is a real check.

**The mirror image: two consecutive statements where the second should have been
gated.** `edit && commit` is not stylistic. On 12 Sep 2026 a `python3 - <<'PY'` edit
failed its own `assert`, and the `git commit` on the *next line* ran regardless —
committing a concurrent session's in-flight change to the same file under an unrelated
subject. A heredoc that raises exits non-zero, so `&&` would have cost nothing and
stopped it. **Any command whose input the previous command was supposed to produce must
be chained to it**, not merely written after it — including the everyday shape "rewrite
a file, then commit it".

**And it is not only a script problem — it bites hardest in a throwaway verification
command.** `git status --porcelain && echo "(clean)"` prints `(clean)` on a **dirty** tree,
because `git status` succeeds at reporting the dirt. Same for `pytest -q && echo PASSED`,
`grep -c pattern f && echo FOUND`, and every `cmd && echo "✓ …"` typed to confirm a step
during a session. These are worse than the scripted kind: nobody reviews them, they scroll
past inside a larger tool call, and the reassuring string is the part that gets read and then
reported to the user as fact. Bit on 28 Aug 2026 — a close-out reported a clean working tree
while ten files were modified by a concurrent session. **When the point of a command is to
confirm something, print the evidence and read it — `git status --porcelain` alone, then
judge — rather than appending a verdict the shell cannot withhold.**

**And inside the Bash tool, `set -e` does nothing at all** — not only for `&&`
operands. Measured 4 Oct 2026: `set -e; false; echo REACHED` prints `REACHED`.
A commit script that opened `set -e && …` and asserted each step with a bare
`[ … ]` line ran straight past a failed Python step, a failed `git update-index`
and a staged-file count of 26 against an asserted 27, and committed. It happened
to be harmless (the missing file was already in HEAD); the shape is not. In a
throwaway multi-step command, **gate every dependent step explicitly** — `cmd ||
exit 1` does stop the call (measured the same day), as does a `&&` chain that
ends at the irreversible act. Scripts run as files (`bash script.sh`) are
unaffected; this is about commands typed into the tool.

### `printf "$big" | grep -q` under `pipefail` reports NO MATCH when the match is early

`grep -q` exits on the first hit. If the writer on the other side of the pipe
still has bytes to send — anything over the 64 KB pipe buffer — it takes
SIGPIPE, and under `set -o pipefail` the pipeline's status is the writer's
141, not grep's 0. So `printf '%s' "$README" | grep -qE "$pat" && r=1` sets
`r` only when the match sits in the LAST 64 KB of a 101 KB README. Measured
22 Sep 2026 in `scripts/check-doc-surfaces.sh`: `--whisper-language`,
documented at README line 277, reported *missing from the README*, while
flags mentioned only in the changelog at the end of the file matched — which
is why the gate looked healthy through every earlier run. Same script, same
day: `is_new()` ran `grep -qxF "$1"` with a flag as the argument, so
`--version` printed grep's own version and was "new since the last tag" on
every run, and every other flag errored and was never new. **Herestrings
(`<<< "$var"`) or a file for the haystack; `--` before any argument that can
begin with a dash.** Tell: a gate whose verdict depends on *where* in the file
the evidence sits.

- **A `pgrep -f` waiter matches its own command line.** `bash -c "while pgrep -f 'build win11'; do sleep 30; done; …"` waits forever: the `bash -c` holding the loop contains the pattern, so pgrep always finds it (9 Oct 2026, a queue that would never have started the next VM build). Anchor the pattern to the real process's argv (`pgrep -f '^/bin/bash ./vbox-test.sh build'`), or put the loop in a script file whose own command line doesn't carry the pattern. **Tell:** a waiter still waiting after the thing it waits for has visibly ended. **Same trap, one shape over: `ps -eo command | grep -q '[p]ytest tests/'`.** The bracket hides the grep, not the `zsh -c` wrapper the Bash tool runs your whole command in, so a 'wait for the full-suite slot' guard placed before `pytest tests/` in the same call finds its own wrapper and reports another suite running, every time (12 Oct 2026: four refused starts while the slot was free). Match the interpreter's argv: `grep -qE '^[^ ]*python[^ ]* -m pytest tests/'`.
- **A literal no-break space (U+00A0) shows as an ordinary space in Read and grep output, so an Edit copied from it never matches.** The Edit tool then reports "String to replace not found" against a file that, on screen, plainly contains the string, which reads as a concurrent edit. On 11 Oct 2026 it also produced a false claim: `tschichold/scan.py` mapped `&nbsp;` to a literal U+00A0, the display showed a space, and the line was reported to the user as a bug that it was not. **Ask for the bytes before believing the glyph:** `python3 -c "print(repr(open(p).read().split(chr(10))[N]))"` or `od -c`. Same for U+202F, U+2009 and the zero-width characters. When writing one into source, spell it `"\u00a0"`, never the literal.
- **Never edit a bash script while a run of it is in flight.** bash reads a script as it executes, by byte offset, so a rewrite under a running copy makes it resume mid-statement in the new text — commands half-run, skipped, or run twice, with nothing to say why. A long `run` (the guest matrix, a release step, `build-all.sh`) holds its script open for minutes to hours. Stage the change in a scratch file and apply it after the run exits; `pgrep -f <script>` first. (Held off deliberately during the 8 Oct 2026 guest trials, where the fix being written was for the script running the trial.)
- **A regex import-inserter lands INSIDE a parenthesised import block, and the result looks fine.** A scripted edit that adds `from x import y` "after the last top-level `from … import` line" matched `from bristlenose.… import (` and inserted the new line between the parentheses — in `server/importer.py` and `s12_render_output.py` on 12 Sep 2026. Every line is still a plausible import; the file fails at import time with a `SyntaxError` a screen away from the edit. Anchor on the closing `)` of a multi-line import (or use `ast` to find the last import's end line), and **import the module after a scripted edit before believing it** — `python -c "import bristlenose.server.importer"` is the whole check.
- **Excluding a basename from a grep hides every file with that name, not the one you meant.** `grep -rn format_duration_human bristlenose/ | grep -v dashboard.py` was meant to drop `server/routes/dashboard.py` and also dropped `stages/s12_render/dashboard.py` — the helper's one live caller — so the helper was written up as dead code (12 Sep 2026, H7 in `docs/time-defects.md`; the "dead" helper was rendering a different duration shape on the static report's total). Exclude by path (`grep -v routes/dashboard.py`), or don't exclude at all: `grep -rlc` gives a per-file count you can read. **Tell:** a "zero callers" claim about a function that has a docstring somebody bothered to write.
- **Renaming the repo directory breaks the venv.** Fix: `find . -name __pycache__ -exec rm -rf {} +` then `.venv/bin/python -m pip install -e '.[dev]'`
- **`/sync-board` parser silently drops items with mis-positioned orthogonal tags.** The parser regex (`scripts/sync_100days.py` `_ITEM_WITH_DESC_RE`) requires `\s*[—–-]\s*` IMMEDIATELY after the closing `**` of the bold title. Anything between the closing `**` and the em-dash separator breaks the match — the line is skipped entirely (no error, no warning, just absent from the parsed items list). When adding orthogonal tags like `[Beta-must]` / `[stage-2-prereq]` / 🔴 / 🟡 alongside the standard `[Sn]` sprint tag, **place them after the em-dash, in the description**, not before. Wrong: `- [S3] **Title** [stage-2-prereq] 🔴 — desc`. Right: `- [S3] **Title** — [stage-2-prereq] 🔴 desc`. Verify with `python3 -c "from sync_100days import parse_doc; items = parse_doc(...); print(len(items))"` after edits — count should match expectations. Same trap exists for nested `**bold**` inside descriptions: if a description contains `**word**` somewhere and the title's `**...**` isn't followed by ` — `, the regex backtracks and absorbs body text into the title, producing 1500-character card titles on the board. Fix: ensure title `**...**` is always followed by ` — ` (em-dash), and avoid nested `**bold**` inside descriptions of items intended for /sync-board (use `_emphasis_` instead).
- **…and it drops a WHOLE numbered category that isn't in `KIND_MAP`.** Sibling to the entry above, one altitude up: `_CATEGORY_RE` matches any `## <n>. ` heading, but `current_kind = KIND_MAP.get(n)` returns `None` for an unregistered one, and `parse_doc`'s next guard is `if current_kind is None: continue` — so every bullet under it is skipped, **sprint-tagged ones included**, with no error. `KIND_MAP` was written 14 Apr 2026 and stops at `"14"`; `## 15. Performance` was added later, and all 39 of its bullets were invisible to the board until 22 Sep 2026. That is how a bullet in there spent eleven weeks naming a lever already pulled — nothing ever showed it to anyone. **When you add a numbered category to the doc, register it in `KIND_MAP` in the same commit** — and consider `ROLLUP_CATEGORIES` (added the same day) if the section is a standing backlog rather than a list of discrete cards: it collapses the section to one pointer card instead of dozens. **Tell:** a section you know is full, whose items never appear on the board — check `parse_doc()`'s output count against the bullets you can see, not the board. **And the board's own `Kind` field needs the matching option** or the card lands uncategorised; that is a GitHub Projects schema change, not a code one.
- **…and it joins doc to board on the exact normalised TITLE, so a strike only travels one way and a duplicate title is a trap.** Three consequences, all measured in the 27–28 Sep 2026 board triage. **(1) It rewrites only its own strike form, `**~~T~~**`.** A line struck by hand (`- ~~**T**~~`, `- [S1] ~~**T** — …~~`, `- ~~[S4] **T** …~~`) is a human's decision, so the sync never rewrites it; `report_hand_struck_open` lists any whose card is still open, and nothing moves them for you. 43 such cards had sat open for months before that report existed. **`- ~~[S3]~~ **T**` strikes only the sprint tag and means _demoted_, not done**, so don't close those. **(2) Close an exact-title duplicate by ARCHIVING it, never by moving it to Done.** A Done card strikes every doc line with that title, including the live twin's, and the line then stays struck permanently, because un-striking needs *no* Done card with that title. Archived items are invisible to the sync. **(3) A reworded doc title makes a new card and leaves the old one open.** The sync prints `possible rename of: '<old>'` under the new card; archive the old one. The warning must stay a warning: the 0.8 fuzzy match it uses suppressed 4 of 5 genuinely new items when it was briefly made a veto ("Phase 2d" swallowed by "Phase 2"). **And the board API cannot list archived items:** `items(query:"is:archived")` is accepted and ignored. Any history of the board has to come from a snapshot taken before archiving.
- **`commit-msg` hook scans for private-content leakage.** A `commit-msg` hook (`~/.bristlenose-leak-patterns`) blocks commits whose **message** references private-only patterns. The pre-commit hook only blocks the diff; this one blocks the message. Workaround: rephrase the message to drop the reference (e.g. "see the gitignored plan note" or just omit the pointer). Don't `--no-verify` — fix the message. The hook list lives at `~/.bristlenose-leak-patterns`. **The leak patterns include filename stems too**, not just paths: `road-to-alpha`, `sprint2-tracks`, `100days`, `qa-backlog`, `succession-plan` — referencing any of these in a commit message (or in a public doc, via the PreToolUse `leak-scan.sh` hook) blocks. Use indirect language: "alpha-checkpoint planning notes" instead of "road-to-alpha", "sprint planning notes" instead of "sprint2-tracks". The same `leak-scan.sh` hook also fires on Edit/Write to public docs that contain these strings — applies symmetrically. **The bare directory path `docs/private/` is itself a blocked pattern**, not just the filename stems — so a new public doc can't even name the directory when pointing at maintainer-only material. Write "the maintainer's private planning notes, kept outside the public repo/tree" instead of `docs/private/<file>` (cost two write-retries authoring `docs/ARCHITECTURE.md`, 14 Jul 2026).
- **Python 3.14's `ensurepip` is broken for `python -m venv` on some macOS installs.** If default `python3` points at 3.14 (brew-installed), `/new-branch` (or plain `python3 -m venv .venv`) fails with `ensurepip --upgrade --default-pip returned non-zero exit status 1`. Fix: use `python3.12 -m venv .venv` explicitly — 3.12 is what CI uses and what every other worktree uses. This will shake out when 3.14 tooling stabilises, but as of April 2026 it's a real papercut on fresh worktree setup

## Git, worktrees and concurrent sessions

### A guard that gates the COMMIT does not gate the PUSH — and pre-commit's pre-push stage checks ONE ref

The 2 Jun 2026 scrub (`8a39f118`) untracked the private docs tree and added
`scripts/check-tracked-vs-gitignore.sh`, which fails a commit whose **index**
holds an ignored path. Good gate for the failure it names. It cannot see a
branch or tag committed *before* the ignore rule existed, and nothing gated
pushing one. Measured 4 Sep 2026: **four branches and twenty-three tags —
sixteen of them release tags, v0.14.3–v0.15.12, six with GitHub Releases pages
— had carried the tree on the public remote for three months after the scrub.**
Deleting the branches and the seven checkpoint tags removed those copies. The
release tags and `main`'s own history (125 commits; `git show 7229e180:<path>`
still answers) keep it, **by decision** — the private history-scrub runbook
stays unexecuted, and the reasons and measurements are under its Step 1. The
question reopens at the desktop-repo split.

The fix is `scripts/git-hooks/pre-push`, a **native** git hook, symlinked once per
clone, from any directory inside it:
`ln -sf ../../scripts/git-hooks/pre-push "$(git rev-parse --git-common-dir)/hooks/pre-push"`
— `--git-common-dir` is what makes it cwd-independent, and it names the main
repo's `.git` from a worktree too, so worktrees need nothing. A `SessionStart` hook
(`.claude/hooks/install-git-guards.sh`) runs that same install for every Claude
Code session — cloud included, where the clone is fresh each time — and installs
pre-commit's hook too when the binary is present (it is not, in a fresh cloud
clone, until deps land; it catches up on the next session). The one-liner is for
a clone no session ever opens. It reads
**every** ref git hands it and refuses the whole push if any ref's tree carries
a path the current `.gitignore` marks private. It is deliberately not a
pre-commit stage: `pre_commit/commands/hook_impl.py::_pre_push_ns` **returns
inside its loop on the first pushable ref** — read it rather than take this on
trust; every branch of the loop body is `return _ns(...)` or `continue` — so a
`--tags`, `--all`, or explicit multi-ref push is inspected one ref deep and the
rest waved through, which is precisely the push the gate exists to stop. **Do
not run `pre-commit install --hook-type pre-push`**: it overwrites the symlink
with the one-ref-deep version and the gate goes quiet with no error. Proof:
`scripts/test-pre-push.sh`; the offender-second case is the one that matters.

**Tell that you are in this trap:** a ref that `check-tracked-vs-gitignore.sh`
passes because it is not the index, while `git ls-tree -r <ref> | git
check-ignore --no-index --stdin` prints paths. Ask the tree, not the index —
and ask it of `origin`'s refs, not only `--all` locally: the remote held refs
the local no longer did.

- **Never remove a worktree from inside it.** Always `cd /Users/cassio/Code/bristlenose` first, then `git worktree remove ...`. See `docs/BRANCHES.md`
- **`git mv` after editing-but-not-staging silently drops your edits from the commit.** If you Edit a file and then `git mv old new` *without* `git add`-ing the edit first, git stages the rename against the file's **HEAD blob** (index shows `R100`, identical content) and leaves your working-tree edits as an **unstaged** modification at the new path. A naive `git commit` of the staged rename then commits the file with its OLD content — your changes vanish silently. Bit during the true-the-docs archive sweep (26 Jul 2026): five docs got front-matter + superseded banners, were `git mv`'d to `docs/archive/`, and the renames showed `R100` — the banners were unstaged. Fix: after any `git mv` of a file you edited, `git add <new-path>` to fold the edits into the rename (similarity then drops to `R<100`), or stage the edit *before* moving. Tell: `git diff --cached --name-status` shows `R100` when you know you changed the content — that's the smell.
- **`git diff --quiet` cannot see a STAGED change — it compares worktree to INDEX, so "is there anything to commit?" is the one question it cannot answer.** The 0.29.1 bump step used `git diff --quiet -- <files> && echo 'already committed' || git commit`: bump-version.py STAGES what it touches, the diff saw worktree==index, took the && arm, printed the reassuring string and committed nothing — then `git push` shipped an un-bumped main, and the tag would have landed on a version already immutable on PyPI (saved only by an unrelated failure; fixed in `00e1d683`). Ask `git diff --quiet HEAD -- <files>` when the question is "does the tree differ from the commit", and `git status --porcelain` when it's "is anything pending". Same family as `cmd && ok "passed"`: the success arm asserted a conclusion the command never established.
- **The index is SHARED between concurrent sessions — `git add` hands your files to whoever commits next.** `git add` writes to one `.git/index` for the whole repo, so a second Claude session running `git commit` picks up **your** staged files along with its own. Bit on 21 Aug 2026: six files (a dashboard fix, its tests, four trued design docs) were staged surgically, and in the seconds before `git commit` the other session committed — carrying all six into a commit whose subject was about the re-analyse sheet. Nothing was lost, but the work was attributed to an unrelated message, and the changelog entries that cited "commit subject X" now pointed at a subject that was never written. **Fix: use the pathspec form, `git commit -F- -- <paths>`, which commits those paths from the working tree and ignores the index entirely** — no staging step, so nothing of yours is ever sitting in a shared index waiting to be swept up. **Two things the pathspec form cannot see: a file git has never been told about, and a commit that does not exist yet.** `git commit -- <new-file>` fails with *pathspec did not match* — `git add` the new file in the *same* call as the commit, so the shared-index window is milliseconds, not turns. And a fresh `git clone .` holds only commits: a script under test that is still uncommitted is simply absent in the clone, and its `exit 127` reads as the script failing rather than the harness (4 Sep 2026). `cp` it in. Corollary, same incident: **don't cite a SHA while another session is active.** That commit was rewritten twice within a minute (`3c04a291` → `e583105e`, work landing in `d8399d2c`), so a SHA written into a doc was stale before the file was saved. Use `file:line` plus a `git log -S'<distinctive string>'` incantation, which survives any rewrite. And **never reach for `--amend` or a reset to "fix" the attribution** — that commit is the other session's, and rewriting it under concurrency is how work actually gets lost. **And the pathspec form cannot commit an UNTRACKED file** — `git commit -- <new-file>` fails with `pathspec did not match any file(s) known to git`. A new file needs one `git add <new-file>` immediately before the pathspec commit; that is the one legitimate use of the shared index here, and it holds the file for seconds, not a session. Bit twice on 4 Sep 2026, once per new script. **And the pathspec form protects the COMMITTER, not the FILE — it stops you sweeping up their work, and does nothing to stop them sweeping up yours. **It stops you sweeping up their work only in files they have not touched.** Pathspec commits the whole working-tree *file*, so when both sessions have uncommitted hunks in one file, yours carries theirs. 28 Sep 2026: an `app.py` allowlist fix would have committed another session's `from …middleware import LoopbackHostMiddleware` while `middleware.py` sat uncommitted, and HEAD would not have imported. **Check `git diff <file>` for hunks you did not write before a pathspec commit; if there are any, commit your hunks alone** — rebuild the file from `git show HEAD:<file>` plus your edits, `git hash-object -w` it, `git update-index --cacheinfo 100644,<blob>,<file>`, and commit in the same call after asserting `git diff --cached --name-only` held nothing else. **That commit is `git commit -F-` with NO pathspec** — adding `-- <file>` makes git re-read the working-tree file and silently undoes the blob you staged (21 Oct 2026: a burn-down brief told workers to do both, and `e381df75` carried another worker's progress hunks in `pipeline.py`; `a1b1052c` took them back out). **Build that blob in the same call as the commit, from the HEAD of that moment** — a blob built from HEAD earlier in the session reverts anything committed to the file since, and the name check cannot see it. 3 Oct 2026: a search commit built its `AppLayout.tsx` blob at edit time, the Discussion session committed a line to that file at 17:11:53, and the search commit landed at 17:12:01 with the line as a `-`; it had to be recommitted. Capture `git rev-parse HEAD` when building and assert it is unchanged at commit. The working tree keeps their hunks untouched. When it is THEIR commit that must go first, build their-only file the same way in reverse: if your edits were exact string substitutions, undo them on a copy, then prove the copy faithful before handing it over — its `diff` against HEAD must be exactly the size theirs was when you first looked (count changed lines, blank ones included; two stray blank lines were the whole gap on 29 Sep 2026), and their tests must pass in an isolated copy of the tree (`PYTHONPATH=<copy>`, import path printed). Hand them the blob paths; they `update-index --cacheinfo` and commit, and your hunks stay in the working tree for your own pathspec commit after.** An unstaged working-tree edit to a shared doc is swept by whichever session commits that path next, index or no index. 12 Sep 2026: a one-line TODO.md note, edited and pathspec-committed minutes later, was already gone — the other session had committed TODO.md in the gap, and the note landed in `c63af629` "record the swift verdict, and what it does not cover", a subject it has nothing to do with. The commit that *meant* to carry it silently listed one fewer file than it was given, which is the tell: **read the `--stat` after committing and count the paths**, because a pathspec naming an already-clean file is not an error. Nothing is lost and the content is on `main`, so the response is to note the attribution and move on — **not** to amend, per the rule above. The only real mitigation is to shrink the window: edit a shared doc and commit it in the same breath, rather than batching doc edits to the end of a session. **And the same window eats a WORKING-TREE write, before any commit is involved — a read-modify-write of a whole file is a lost-update primitive.** 22 Sep 2026: four keys were inserted into 21 locale `common.json` files and `check-locales.py --strict` passed. Twenty minutes later the full pytest run had it **red** — a concurrent session's unrelated ellipsis sweep had rewritten `zh-Hant/common.json` wholesale from a copy read *before* the insertion, so the four keys were simply gone. Nothing errored, nothing was staged, and no commit was involved: their `write_text` landed on top. **The green run was evidence about a tree that no longer existed** — which is the durable half, because a gate you ran at the moment you made the change is not a gate you have run. **Tell:** a per-file census of your own diff where one file shows *zero* of your additions while its twenty siblings show the expected count. **Fix, both halves:** re-run the gate at close-out, not only after the write; and re-apply with a *targeted* insert that asserts every pre-existing key is byte-identical afterwards, which preserves their sweep instead of reverting it — a wholesale rewrite of your own would have clobbered them back, and the two sessions would have taken turns deleting each other's work.
- **Another session's commit briefly removes YOUR uncommitted edits from the working tree.** pre-commit stashes every unstaged change in the repo while its hooks run ("Stashing unstaged files…") and restores them afterwards — so for those seconds your edited files are back at HEAD. A test run that overlaps another session's commit tests HEAD for exactly the files you have not committed, and fails on precisely your new work, with nothing in your output to say why. Measured 3 Oct 2026: six failures, every one of them a test of an uncommitted change (a stub missing a new export, a generator missing a new template), at the second of two commits by another session; both re-runs were clean. **Tell:** failures that track your uncommitted diff exactly, then vanish. **Check:** `git log --since="10 minutes ago" --format='%h %ci'` against the run's start time, then re-run before diagnosing. Your own commit does the same to the other session. **A tool that WRITES during the window is worse than a test that reads, because nothing fails afterwards.** On 17 Oct 2026 `check-locales.py --stamp` ran during another session's commit, stamped 1,931 values from the stashed tree instead of 1,934, and left a reworded English key un-pinned. The stamp printed success, and only a later `--strict` run caught it. Re-run any generator or stamper after the other session's commit has landed, and confirm the result with the gate that reads it.
- **A resumed conversation's "just now" can be six weeks old — date the session's own commits before reasoning about the log.** A 12 Sep 2026 `/end-session` closed out work whose commit (`3b698ea9`) was dated **30 Jul**: absent from `git log -12`, present per `git branch --contains main`, and `<sha>..HEAD` counted 1040 commits — which reads exactly like a concurrent session resetting or rewriting `main` under you, and nearly got recorded as that gotcha. One command dissolved it: `git show -s --format='%h %ci %s' <sha>` — the commit was simply deep in history, parented on the genuine 30 Jul tip. **Tell:** your commit missing from the recent log while `--contains` names the branch, or a `<sha>..HEAD` count in the hundreds for "this session's" work. **Corollary:** the transcript's green suite blessed the tree as it stood *then* and says nothing about HEAD today, and a fix the transcript treats as unreleased may long since have shipped — `git tag --contains <sha>` before claiming either (this one was in ten releases).
- **A bug report describes the tree its author read, not necessarily HEAD — check before you fix.** A detailed report (file, line numbers, quoted code, the contract to restore) reads as a specification and invites you to start editing. Its **line numbers are a version stamp.** On 22 Aug 2026 a report cited an ungated control at `SessionsTable.tsx:436`/`:466`; at HEAD that control sat at `:453`/`:496` and was already gated — the fix had landed two days earlier in `cb4f1e28`, together with a mechanical gate (`tests/test_export_css_selectors.py`) and three related fixes the report knew nothing about. A full cycle went into re-deriving it, down to near-identical comment wording, and it was reported back as discovery; the session's net code output was zero. **The check is two commands, before the first edit:** `git log --oneline -3 -- <file>` (has someone just been here?) and `git log -S'<distinctive string from the report>' -- <file>` (was this exact thing already changed?). **Tell:** the quoted snippet isn't at the quoted line. When that happens, stop — you and the reporter are reading different versions, and the gap is the answer. This is the concrete cost of skipping *confirm it still reproduces at HEAD*, which is not optional just because a report is specific.
- **A task to *build* a feature is a claim the feature is absent — grep HEAD before implementing, not only before fixing.** The entry above files "confirm it reproduces at HEAD" under bug reports; its costlier form is a request to build something already shipped, where there is no report to disbelieve and nothing looks stale. On 12 Sep 2026 a whole session built ⌘A select-all, ⌘C copy-selected, the Star⇄Unstar adaptive menu labels *and* a focus-sync "fix" — every line of it already on `main` in `6a10eb78` (1 Aug 2026, "native menu labels read live store state"). The frontend, Swift and locale files the session edited showed **zero diff against HEAD**, the net code output was nothing, and the "bug" in the focus plumbing had been fixed six weeks earlier. This is the **third** recorded instance of re-deriving shipped work (see the two entries above), which is why it earns its own rule rather than a cross-reference. **The tell is your own edits producing no diff:** `git diff --stat HEAD -- <files>` empty after you believe you changed them; an `Edit` whose `old_string` matches only because the `new_string` was already there; a "new" test that already exists. **The check is one command, before the first edit:** grep the feature's most distinctive symbol (`grep -rn starActionIsUnstar frontend/src`, or `git log -S'<symbol>'`) — a single hit ends the session in a line instead of a day. The unifying rule across all three entries: *any* task, fix or feature, is a statement about the current tree, and the tree is one grep away — so "is this already here?" is the first step of implementing, never a retrospective.
- **A doc comment naming a collaborator is a version stamp too — and an *audit* of the app is the report in the gotcha above, with you as its author.** Same failure, one altitude up: instead of a stale bug report you are the one producing stale claims, and a comment is what backs them. `ToastView.swift`'s header said *"Two consumers today"* and named `UndoableRemovalStore` + `RemoveToast`; that consumer was **deleted three weeks earlier** (`5598bd39`, 19 Aug 2026, "five toasts and a fuse removed" — removal-undo is now plain ⌘Z with no time limit plus `NSAnimationEffect.poof`). On 12 Sep 2026 a macOS-nativeness audit read that comment and reported to the user that the app ships an undo toast, which it does not — and in the same pass reported `File ▸ Open in New Window` as a dead menu item when it had been **retired** on 20 Aug (`8fb6abbc`) in favour of real multi-window (`WindowGroup(id: "main", for: WindowSeed.self)`, ⌥⌘N carrying a project+lens seed). Two wrong findings handed over as fact, both sourced from artefacts that outlived what they describe. **The check is one command per named type, and it is cheap: `git ls-files | grep -i <TypeName>`** — a comment's collaborator that git has never heard of is a comment describing a deleted past. For a menu command or affordance, `git log -S'<actionName>' -- <file>` answers *was this retired?* in one line. **Tell:** a comment counting its own consumers ("two consumers", "three call sites") — a number in prose is a number nothing recomputes, which is the same disease as the `_JS_FILES` count this file already documents. **Corollary for the writing half:** when you delete a collaborator, grep for the surviving side's comment in the same commit, or it becomes the next session's false evidence.
- **"Does this branch hold anything not on main?" — count commits, then patch-ids, then TREES; only the last is decisive across a history rewrite.** `git rev-list --count` counts commits, so a rebased branch reads as full of unique work while holding none. `git cherry` patch-ids see through a rebase but not through content that landed by another route — `claude/bn-strava-style` read 13-unique by patch-id while both its files sat on `main`, larger. And a pre-rewrite remote against a post-rewrite local shows *958 ahead, 958 behind* — every commit "unique" in both directions — because every SHA changed. The question that survives all three is the tree: `git rev-parse A^{tree}` vs `B^{tree}` (equal = byte-identical content), or `git diff --name-only A B` — **two-arg, not three-dot**: `A...B` diffs from the merge base, and with multiple merge bases across a rewrite it lists the entire tree (228 KB of "differences", 4 Sep 2026). `docs/BRANCHES.md` § 4 Sep carries the worked set
- **`git checkout --theirs/--ours` is blocked during merges in the main repo** — the `.claude/hooks/block-checkout.sh` PreToolUse hook intercepts every `git checkout` to prevent feature-branch checkouts in `bristlenose/`. It can't distinguish "checkout a branch" from "resolve a conflicted file via --theirs/--ours." Workaround: write the index stage directly. `git show :3:path/to/file > path/to/file` takes the branch (theirs) version; `:2:` takes HEAD (ours); `:1:` takes the merge-base. Then `git add path/to/file` to stage
- **In a worktree, double-check absolute paths in Edit/Write calls.** When the worktree's path looks like `/Users/cassio/Code/bristlenose_branch <name>/<file>` and the main repo's path is `/Users/cassio/Code/bristlenose/<file>`, an Edit call to the latter silently lands the change on `main`'s working tree, NOT this worktree. Symptom: `git status` in the worktree shows nothing changed; `git status` in main shows an unwanted modification. Particularly easy to trip when grep output uses relative paths (`../bristlenose/...` from `frontend/`) and you mentally translate to an absolute path. Always start absolute paths with the current `pwd` prefix; if in doubt run `pwd` first. Recovery: `cd /Users/cassio/Code/bristlenose && git checkout -- <file>` (safe if main is clean), then redo with the right worktree path.
- **Worktrees don't inherit gitignored binaries.** `desktop/Bristlenose/Resources/{ffmpeg,ffprobe,models/}` are large static binaries fetched once into the main repo via `desktop/scripts/fetch-ffmpeg.sh` (gitignored, won't follow worktrees). If you open a worktree's `Bristlenose.xcodeproj` and Cmd+R, Xcode's Copy Resources phase finds nothing to copy — the resulting `.app` ships *without* ffprobe and the pipeline silently can't probe video files (analysis surfaces "Failed" with no obvious cause). `/new-branch` Step 9 now symlinks these from main; if you set up a worktree by hand, do the same or run `desktop/scripts/fetch-ffmpeg.sh` from inside the worktree
- **Building bundled sidecar in a worktree only updates *that* worktree's bundle.** `desktop/scripts/build-sidecar.sh` resolves `ROOT="$DESKTOP_DIR/.."` — i.e. whatever repo holds the script you ran. If the active `.app` is launching from the main-repo's Xcode project but you ran `build-sidecar.sh` from a worktree, the active bundle is stale relative to your edits. Open the worktree's `desktop/Bristlenose.xcodeproj` (not main's) so Xcode picks up the worktree's freshly-built sidecar
- **Cloud-session `claude/...` branches: cherry-pick the docs, drop the staging dir.** When a Claude Code Cloud session (often phone-started) creates a `claude/<name>-XXXXX` branch, it tends to dump work into a staging dir like `_<name>-extract-me/` plus a design doc. The script/rules usually get installed to `~/bin/` + `~/.claude/` on the Mac during the session, so the staging dir is throwaway. Rescue pattern: `git show origin/claude/<name>-XXXXX:docs/design-<thing>.md > docs/design-<thing>.md`, then commit — **not** `git checkout <branch> -- <file>`: the `block-checkout.sh` PreToolUse hook refuses *every* `git checkout` in the main repo, file-pathspec form included (bit 30 Jul 2026 rescuing the chat-lens doc; `git show branch:path > path` is the same trick the merge-conflict gotcha uses with index stages). Then `git branch -D … && git push origin --delete …` for the branch. Don't merge the whole branch — the staging dir doesn't belong in the tree. Also: the cloud session may leave the main repo dir checked out to the feature branch with stale "modifications" that are just main's progression — `git checkout -- <files>` is safe (vs-main diff is empty)
- **Inside a cloud session, local `main` is stale — read `origin/main` instead.** The cloud env clones origin/main as the working branch at session start, then leaves the local `main` ref pointing at whatever commit it cloned from. Any subsequent commits to origin/main during the session don't update local `main`. Sitrep and "what shipped in the window" audits via `git log main --since=...` silently return a truncated view (only commits up to the cloud-clone point). Always use `origin/main` (or `HEAD` when on the working branch) for window queries from cloud: `git log origin/main --since="N days ago" --pretty=...`. Confirm at session start: `git rev-parse main` vs `git rev-parse origin/main` — if they differ, local `main` is the stale one
- **Cloud session, no `gh` CLI — use the GitHub MCP for PR + merge.** When the user asks for a merge from a cloud env, the path is `mcp__github__create_pull_request` then `mcp__github__merge_pull_request` (load via ToolSearch with `select:` query). The MCP repo scope is restricted per the system prompt (`cassiocassio/bristlenose` only) — calls to other repos are denied. After merging from cloud, the version tag should be created from the dev machine (`git tag v<X.Y.Z> <merge-sha>`) before pushing to PyPI — `scripts/bump-version.py` writes and stages the version files for the local dev flow, and the tag belongs on the merge commit, which doesn't exist until the PR lands. (This used to say the script "tags HEAD-before-commit"; it no longer tags at all — 14 Aug 2026. The advice is unchanged, the reason is simpler.)

### Work during a release freeze goes on a hold branch built in a separate CLONE

A live `release.sh run` makes the `release-freeze` hook refuse commits in this checkout **and its worktrees** (the hook resolves `.release/` from `--git-common-dir`). A separate `git clone --local` has its own `.git`, so the hook passes there, and committing there moves neither `main` nor the release's working tree, which is the whole reason for the freeze. Measured 18 Oct 2026, landing three tested Zoom commits while 0.41.0 sat at its confirm prompt:

- **Copy the house hooks in by hand** (`cp .git/hooks/pre-commit .git/hooks/commit-msg <clone>/.git/hooks/`): a clone gets no hooks, and the leak scan is the one you need.
- **Never `git switch`/`checkout` in the clone either**: the PreToolUse hook matches the command text, not the repo. Use `git clone -b <branch>`, or commit on the clone's `main` and name the branch when you bring it back.
- **Bring it back with a fetch**, `git -C <main repo> fetch <clone> main:refs/heads/after-pypi/<v>-<topic>`. That writes a ref and leaves HEAD alone. Name it `after-<channel>/<version>-…` so `release.sh verify` lists it.
- **Run Python tests from inside the clone with `python -m pytest`**, so the clone's `bristlenose/` is first on `sys.path`; check `bristlenose.__file__` once, because the venv's editable install points at the main repo.
- **The first Swift build of a fresh clone fails with `cannot find 'GeneratedBuildInfo' in scope`.** The Run Script phase writes the gitignored file after Xcode has already planned Compile Sources. Build again (or run `desktop/scripts/generate-build-info.sh` first); a normal checkout never hits it because the file is already there.
- **Land with `git merge`, not cherry-pick**, so the hold's commit ids stay the ones another session or `verify` sees as merged.
- **The freeze guards commits, not your uncommitted edits — and those are the bigger risk.** The release builds the sidecar from the main working tree, so edits you have in progress there when it starts either fail its dirty-tree check (a lost release night) or get bundled into what ships. When `.release/<v>/.lock` appears, move your uncommitted work off main before anything else: back it up (`git diff HEAD > patch`, tar the untracked files), apply it in the clone, compare byte for byte, then put each tracked file back with `git show HEAD:<path> > <path>` and delete your untracked files. Done 18 Oct 2026 for the Apple-first work, at 0.41.0's confirm prompt, before its sidecar build.
- **`git merge -F -` does not read stdin** (unlike `git commit -F -`): it fails `could not read file '-'` and merges nothing. Write the message to a file and pass its path.

## Tests, gates and verification

### Ruff F401 (unused imports) — reports only, won't auto-fix

F401 is marked `unfixable` in `pyproject.toml` so `ruff check --fix` (and the PostToolUse hook) won't delete imports during incremental edits. Ruff still *reports* unused imports — remove them manually when they're genuinely unused.

**Sibling for mypy `unused-ignore`: delete the comment, never re-target it.** On 4 Sep 2026 six of nineteen "unused" `# type: ignore[...]` comments were not stale suppressions of fixed problems — they were **mis-targeted**: `pipeline.py:511` ignored `[union-attr]` while the live error on that line is `[attr-defined]`, and the same shape sat at `client.py:83`/`:898`, `cli.py:663`, `lifecycle.py:195`. Re-targeting the code would have been *new* suppression of an error that is already visible and already counted; deleting exposes nothing. The count drops by exactly one per site either way, but only one of the two is honest.

### A gate that matches on PROXIMITY or on a NAME is a gate that drifts with the file

Two shapes, both found on 22 Sep 2026 in the same hour, and the second one
passed for a while before anyone noticed.

**Proximity.** `test_every_native_illustration_is_classified` decided "is this a
webview or a native view?" by looking for `WelcomeIllustrationHTML.` within
**2500 characters** of the `struct` declaration. Adding four locale keys and a
comment to `SignalIllustrationView`'s strings table pushed its builder call past
the cutoff, and a webview was reported as an unclassified native illustration.
That direction is loud. **The same arithmetic misclassifies silently the other
way**: a genuinely native view whose body happens to mention the builder type
within 2500 characters drops out of the gate entirely, and nothing says so. Scope
to the construct — find the next `\nstruct ` and read the body between — never to
a character count nothing recomputes.

**Name.** A test asserting the catch-all theme uses the right locale keys was
written as `assert "uncategorisedHeading" in src`. The fix replaced those keys and
the test **stayed green**, because the comment explaining why they were wrong
names them both. Assert the call expression (`t_in(locale, "common.quotes.thinThemeLabel")`),
not the identifier. Sibling of the `.innerHTML=` rule in the illustration gate,
which had to match the *assignment* so that documenting the hazard did not trip
the test that forbids it — same lesson, opposite direction: **a test a comment can
satisfy is not a test.**

**Tell for both:** a gate whose verdict changes when you add a comment.

### A new gate that contradicts a pinned contract fails the whole suite, not one test

Adding an `assert` to `I18n.t` for "namespace not loaded" turned **307 Swift tests
red at 0.000 seconds each** — a Swift `assert` traps the test host, so every class
fails instantly and the run looks like a build break rather than one bad
assertion. The cause was a single existing test,
`I18nTests.t_missingNamespace_returnsRawKey`, pinning the exact behaviour the new
assertion forbade: an **unknown** namespace returns the raw key, deliberately.

The fix was not to change the test. It was to read the contract the test states
and notice the gate was aimed at a different thing — a namespace that exists in
`bristlenose/locales/` but is not in `I18n.namespaces` (`server`, `pipeline`,
`cli`, `doctor`, `preflight`) can never resolve and *is* a bug; `bogus.some.key`
returning itself is graceful degradation and is wanted. Narrowing to the
on-disk-but-unloaded set kept both. **Tell:** a whole suite red at 0.000s after a
one-line change — look for a trap, not 307 defects, and read the one failing test
whose name describes your new rule's subject. Sibling of the default-flip entry
above: the same "read the failing test for the contract it states" move, applied
to a gate rather than a default.

### A one-line fix landing on the wrong arm of a ternary is invisible to every gate

`.foregroundStyle(a ? .tertiary : .primary)` needed `.tertiary` → `.secondary`.
What landed was `.primary` → `.secondary` — the *other* arm. Both results are
valid Swift, both are real style tokens, the file compiled, the suite stayed
green, and the finding was written up as **resolved** in the review notes kept
outside the public tree. The failing value sat on the shipped surface for a day
(22 Aug 2026), on the one row whose whole job is naming the project you just
revoked.

Nothing mechanical can catch this: a ternary's two arms are the same type, so
swapping which one you edited produces working code either way. Two habits do:

1. **The tell is a comment that argues against its own code.** The block above
   the line spent eight lines explaining why `.tertiary` fails — 1.88:1,
   unimproved by Increase Contrast, semantically Apple's *disabled* colour — and
   then applied it. When prose and code disagree at arm's length, the code
   usually lost an edit, not the argument.
2. **Re-read the diff hunk, not the file.** `git show <sha> -- <file>` on the
   fix shows `- a ? .tertiary : .primary` / `+ a ? .tertiary : .secondary` in
   two adjacent lines, where the intent was to change the first token. Reading
   the finished file instead invites you to see what you meant.

Generalises past styles to any two-branch expression where both values
typecheck: `if/else` returns, `??` defaults, dictionary fallbacks, ternaries in
JSX. **And it generalises past code: a finding marked "resolved" is a claim
about intent, not evidence about the tree.** Verify a resolution by reading the
line it names.

### Deleting a UI surface can orphan the test that was pinning a WIRE CONTRACT

`PUT /framework-states` is a **full replacement** — `put_framework_states`
(`server/routes/data.py`) deletes every row for the project and re-inserts only
what the body carried, and its own docstring says so. Two clients existed over
time. v1's `setFrameworkDisabled` sent the whole disabled set, and
`SidebarStore.test.ts` pinned that with an exact-payload assertion. The v2
navigator, written months later, sent `{[id]: enabled}` — a patch, to an
endpoint that has no patch. Switching one codebook off deleted every other
codebook's `false` row, so **only one could be off at a time**, and 0.29.0
shipped that to nine channels.

Nothing was red at any point. The server did exactly what it documents. The v2
tests asserted that the switch *renders*, never what it *sends*. And when
`baa1aa0e` deleted v1, the one test pinning the contract went on passing against
a function nothing called any more — a green assertion about dead code, guarding
a live call site it had never touched.

The second-order cost is the part to remember: absence means enabled, so every
wiped row read as an OFF→ON transition and was handed to `_start_catch_ups` —
switching one codebook off could start AutoCode runs, and LLM spend, on others.
A payload bug reached into the researcher's review queue.

**Rule: deleting a component is also deleting whatever its tests were the only
witness to.** Before removing one, list the store/helper functions it was the
last production caller of, and move any wire-contract assertion onto the
replacement's call site in the same commit. **Tell:** a `grep -rn '<helper>'
src/ | grep -v test` that returns nothing — an exported function whose only
remaining callers are tests is usually a contract that has quietly lost its
guard. Generalises to any replacement endpoint (PUT-as-replace, `set`-shaped
config writes) where a partial body is silently valid.

**That tell has a blind spot, and it is the one that fired on the sibling
deletion.** It asks whether the *helper* still has production callers — so a
helper that is alive and well passes it, and the audit stops. But coverage can
be orphaned in the other direction: `utils/autocodeFailure.ts` had a live caller
(`normaliseAutoCode`) and **no test file of its own**, so its only three
assertions anywhere in the repo sat inside `AutoCodeToast.test.tsx` — the test
file of a component nothing rendered. Deleting that component would have taken
the entire guard on "never interpolate the raw `str(exc)` into a researcher's
sentence" with it, silently, with every suite green (12 Sep 2026). **So run both
greps before deleting a component: `grep -rn '<helper>' src/ | grep -v test`
for orphaned callers, and `ls <helper>.test.*` for the helper's own coverage.**
A file the doomed tests import but do not name in their `describe` is exactly
what nobody thinks to check. And **prove the ported assertions bite** — mutate
the live code back to the pre-fix behaviour and watch precisely the new tests go
red; a port that passes on arrival has demonstrated nothing.

**The sibling that is not a deletion: inverting a DEFAULT.** A test whose name and
docstring are phrased in terms of the default is often pinning something else
underneath, and flipping the default looks like it obsoletes the test when it
does not. `test_lab_mounts_without_dev` read as "the lab is on by default" and was
really pinning *the mount is gated on the flag and **not** on `--dev`* — the reason
the desktop sidecar can serve it. Flipping `experimental_codebook_lab` to
default-off (20 Sep 2026) would have deleted that contract along with the default
had the test simply been inverted in place; it survives as
`test_lab_mounts_without_dev_when_enabled`, asserting the same non-dev mount with
the flag opted in. **Before changing a default, read each failing test for the
contract it states rather than the value it happens to use, and re-home that
contract in the same commit.**

Two more things a default-flip drags behind it, both cheap to check and expensive
to miss. **(1) Every other test that exercised the feature now exercises its
absence** — nine further tests in that class would have become nine silent 404
assertions, still green, testing nothing; an autouse fixture opting the class in
is the fix, and the survey (`grep -rn '<route>' tests/`) is what finds them before
the flip rather than after. **(2) The escape hatch inverts** — the env var that
turned this off now turns it on, so every comment describing the old direction is
actively misleading. An inverted switch documented the old way is worse than an
undocumented one. Grep the flag name repo-wide and fix the prose in the same
commit.

### Verifying only through a pipe hides the entire TTY code path

`foo | tail`, `foo | grep`, `foo > file` all make stdout a non-tty, and any well-behaved CLI *changes behaviour* accordingly: Rich/`clig.dev`-style renderers skip animation, spinners and live regions don't start, colour drops. So a bug that only exists in the animated path is **invisible to every piped run** and instantly visible to the human who runs it bare.

Bit on 4 Aug 2026: `build_report.py` forced `Console(width=92)` regardless of the real terminal, so on a narrower window every line wrapped to two rows while Rich's `Live` moved the cursor up one — each refresh smeared a new copy down the screen. Every verification run during the work was piped, `_start_live()` returns early on a non-tty, and the bug was never once exercised. The user saw it on the first real run.

**When you've verified something only through a pipe, say so** — and prefer running it bare at least once (or with a pty) before claiming it works. The related house idiom is already documented above: `Console(width=min(80, Console().width))` — never force a console wider than the terminal. **And a pty you open yourself has no size.** A `pty.fork()` child starts with a 0×0 window, so tqdm draws zero-width bars and Rich wraps at nothing: on 14 Oct 2026 a correct fix to the first-run Whisper progress bar read as "still silent" until the child set `termios.TIOCSWINSZ` (`fcntl.ioctl(1, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))`). A pty run that prints *nothing* where a bar should be is evidence about the harness before it is evidence about the code.

**The desktop analogue, and it is the more expensive one: a test suite hides the whole rendered surface.** On 20 Aug 2026 the format-torture corpus had been run through the acceptance harness repeatedly and reported clean. One screenshot of the *same corpus* in the `.app` produced three defects — diagnostic rows that named no file, refusals rendered in error red, and fifteen sessions dropped behind a `transcripts: succeeded=57` that the next bucket contradicted with `attempted=42`. None was visible to 4,037 passing tests, because a test asserts what someone thought to ask, and nobody had thought to ask what the pane *said*. **After any pipeline or diagnostic change, run the corpus through the app once and look at it** — `experiments/folder-of-horrors/synthesise.sh` builds it. The tell for that last class is generic and worth carrying: **a summary bucket whose `attempted` disagrees with the next bucket's**, which nothing in the schema forbids.

### Renaming a lookup map's KEY orphans every caller, and the fallback makes it look fine

A rename sweep greps for the old *name*. It does not ask which strings are
**keys into a map**, and a map with a default answers a missing key with a
plausible result rather than an error.

0.30.0's Analysis→Signals rename moved `TAB_ROUTES`'s key from `analysis` to
`signals` (`Dashboard.tsx:62-70`, `shims/navigation.ts:20`) and left one caller
emitting the old one: `target: "analysis:section-x-sentiment"` at
`Dashboard.tsx:230`. `TAB_ROUTES[tab] ?? "/report/"` then returned the project
dashboard, so **the AI-tags stat card put the researcher back on the page they
clicked from** — no error, no console warning, a real href, and a tab switch
that "worked". It shipped to nine channels. At `v0.29.1` the same card reached
`/report/analysis/`.

Nothing could have caught it: `tsc` cannot type a `Record<string, string>`
lookup, five stat cards had targets, and **no test anywhere asserted where a
stat card goes** — only that cards render. The suite was green on both sides of
the break.

**Rule: when a rename touches a map key, grep for the key as a STRING LITERAL in
callers, not just as an identifier** — `grep -rn '"analysis:' src/` is the whole
check, and it is a different grep from the one that renamed the symbol. **And
gate the destination, not the spelling:** `Dashboard.test.tsx`'s
*"every stat card reaches the lens its target names"* asserts the resolved href
per card, so the next key move fails loudly instead of resolving to a fallback.

**Tell:** a lookup with `?? default`, `.get(k, fallback)`, or `|| FALLBACK`
whose default is a *working* value. A fallback that throws is safe; a fallback
that navigates somewhere real is the trap. Same family as the ternary-arm entry
below — both produce valid, running, wrong code.

**Sibling, same rename:** the *sealed* static renderer was never part of it, so
its `analysis:section-x-sentiment` (`s12_render/dashboard.py:539`) is
**correct** — its panel is `data-tab="analysis"` (`report.py:396`) and its
anchor lives in `theme/templates/analysis.html`. Before "finishing" a rename on
a second surface, check whether that surface was in scope.

### A proposal's "What it touches" and "New file X" are not claims that X exists

The existing trap above — prose *about* a deleted file reading as a dead pointer
— has a second face that fires on the opposite tense, and a doc audit walks into
it just as readily. A design doc's **proposal** sections name files the work
*would* create or edit: `**What it touches**: server/database.py`,
`**What it touches**: New file bristlenose/merge.py`. A path-resolution pass
reports both as broken links. They are neither broken nor links.

Measured 21 Sep 2026: a truing pass over 27 docs reported **six** dead paths.
**One was real.** Three were prose about deleted files (*"span bars removed
(`atoms/span-bar.css` + tokens deleted)"*, *"`molecules/name-edit.css` was
deleted on …"*, *"Renamed `molecules/person-id.css` → `person-badge.css`"*) and
two were proposals naming their own future files. Each was convincing because
the one real finding sat in the same list.

**Before reporting a path as dead, read the sentence around it and the heading
above it.** Past-tense verbs (*removed*, *deleted*, *renamed*) mean the doc is
doing its job; `**What it touches**`, `### Files to create`, `New file`, and
`Maybe 10-20 lines` mean you are inside a proposal. Neither is a defect.

### A backgrounded `pytest … | tail`'s reported exit code is `tail`'s, not pytest's

Sibling to the two above, and the one most likely to produce a **confident false
"tests passed"**. A background Bash task reports the exit status of the
*pipeline*, which in a shell without `pipefail` is the status of the **last**
stage. So `pytest tests/ -q 2>&1 | tail -15` reports **exit code 0 even when
pytest failed**, because `tail` succeeded at tailing. The completion
notification then says "completed (exit code 0)" and reads exactly like a green
run.

Hit twice on 16 Aug 2026 while verifying the docx-parser work. Both runs were
genuinely green, so nothing broke — which is precisely why it is worth writing
down: the tell only appears when the suite is red, and by then the habit of
trusting the notification is already formed.

**Rule: never report a suite result from the exit code of a piped background
task — `Read` the output file and quote the real summary line** (`N passed, M
skipped…`). If you want the exit code to mean something, either drop the pipe
(`pytest … > out.txt 2>&1`) or set `set -o pipefail` first. The same applies to
`ruff … | tail`, `npm run build | tail`, and any `cmd | head` gate.

### A reconstruction harness guarantees exactly as far as the function it cross-checks

`experiments/signal_strength/measure.py` re-derives the shipped composite from
raw cells and asserts it against `_compute_group_analysis` cell by cell — "105
cells compared, 0 mismatched", and that assertion held across 32 commits and a
week, which is what it was built for. It is also why a claim measured through
it was reported to the user as fact and was **false at HEAD**.

The measured claim was *"`classify_flag` fires on 0 of 103 cards"*. True of
`classify_flag` called with a group name, which is what the harness does. Not
true of the product: `_serialize_signal` (`server/routes/signals.py`) resolves
a Sentiment-group card to a sentiment **value** via `sentiment_label(s.quotes)`
and re-calls `classify_flag` with it, which had landed three hours earlier
(`9e9af6fd`, refined by `3c8aa63d`). Measured through the real serialiser:
**39 of 105 cards flagged**, five of six words firing. The code comment at that
site states the pre-fix position verbatim, so the file being measured said so.

The trap is structural, not careless: `_serialize_signal` is **downstream of
the assertion**, so nothing the harness checks could have caught it. A
cross-check licenses claims about the function it names and nothing past it.

**Rule: before reporting a harness measurement as a fact about shipped
behaviour, name the last function the assertion covers and confirm the quantity
is computed at or before it.** If it is computed later — in a serialiser, an
adapter, a React selector — measure through that instead, however much slower.
**Tell:** a number about what the user sees, derived from a module the user's
request never reaches.

- **A mutation run you kill leaves its mutant in the tree.** The reverse lives in the harness's `finally`, and SIGTERM to the harness skips it: on 20 Oct 2026 a stalled mutation run was killed and `if True:  # MUTANT` sat in `cli.py`'s report put-back block, where the next commit would have carried it. Put a unique marker in every mutant (`# MUTANT-<name>`), and after any interrupted run `grep -rn MUTANT bristlenose/ tests/` before committing. A suite stuck behind a mutant is a hang to diagnose, not a run to kill: wait for it, or reverse by hand first.
- **A test that probes a shared lock from a helper thread must release it in that thread.** `threading.RLock` raises when released by a thread that does not own it, so a probe that acquired in a helper and released in the main thread left the lock held by a dead thread, and every later `restore()` in that pytest process waited for ever (20 Oct 2026, `run_lifecycle._exit_hold`; `sample <pid>` showed `rlock_acquire`). The hung suite then ignored SIGTERM, because a CLI test had left `run_lifecycle`'s signal handlers installed: the CLI keeps them for its lifetime by design, and pytest outlived the test. `tests/conftest.py::no_run_signal_handlers_left_behind` now restores them after every test. **Tell:** a suite at low CPU for many minutes with no child processes; sample it before killing it.
- **`gen-test-inventory.py` run in a scratch worktree writes `"tests": null` for pytest.** It counts by collecting, and a worktree has no installed package, so the count silently becomes unknown while `--check` stays green. Preparing a gate change on a branch (9 Oct 2026) committed exactly that. After regenerating anywhere but the main checkout, `git diff docs/testing/inventory.*` and keep only the lines your change caused; rebuild the file from the base commit rather than `sed`-restoring a value, because vitest and playwright are `null` on purpose.
- **E2E allowlists must be registered.** Every `if (...) return;`-style suppression inside a Playwright spec (e.g. "this 404 is expected") needs (a) a matching entry in `e2e/ALLOWLIST.md` and (b) a `// ci-allowlist: CI-A<N>` comment marker above the code. Categories: `infra` (stack artefact, never fixable) / `by-design` (intentional correct behaviour) / `deferred-fix` (real bug, must link to 100days.md tracker). Prevents the e2e gate from accumulating silent suppressions nobody can audit six months later. See the register header for schema, retired IDs, and v2 tooling (validator + staleness gate, deferred until ~10 entries).
- **`from __future__ import annotations` doesn't satisfy ruff F821 if the annotated name isn't imported.** Type annotations become strings at runtime, but ruff's F821 still validates that the name is reachable in the module scope. So `def foo() -> Path:` with a per-function `from pathlib import Path` inside the body fails F821. Move the import to top-of-file
- **E2E tests: stale server on port 8150 gives wrong results** — `playwright.config.ts` uses `reuseExistingServer: !process.env.CI`. If a previous `bristlenose serve` is running locally on port 8150 (e.g. from `bristlenose serve trial-runs/project-ikea`), Playwright silently connects to it instead of starting the smoke-test fixture. This produces completely wrong measurements (353 quotes instead of 4). Always check `lsof -i :8150` before running E2E tests locally. In CI this can't happen (`reuseExistingServer: false`). The perf-gate spec has a server identity guard (`project_name === "Smoke Test"`) to catch this
- **E2E Node-side `fetch()` needs auth token explicitly** — Playwright's `extraHTTPHeaders` only applies to browser contexts (page navigation). Node-side `fetch()` in test fixtures gets 401'd without the bearer token. `e2e/fixtures/routes.ts` reads `_BRISTLENOSE_AUTH_TOKEN` from env and passes it via `authHeaders()`. Set the env var when running E2E tests: `_BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test`
- **E2E: `waitForLoadState('networkidle')` is too fragile for SPAs** — fires after a 500ms idle window, which can beat deferred `useEffect` mounts on slow CI runners. Missed nodes look like "passed" tests and you measure the wrong state. In `perf-gate.spec.ts` the pattern is a `waitForPageReady()` helper that chains: `networkidle` → wait for `#bn-app-root` children → wait for `document.querySelectorAll('*').length` to be stable across two 200ms polls. Copy this pattern for any E2E spec that measures DOM state
- **E2E: in-browser `fetch()` in `page.evaluate` can silently 401** — a dropped auth token turns into 1ms latency and a ~50-byte error body. Without `res.ok` assertions this registers as "excellent latency" and sails past size thresholds. Always assert `res.ok` inside the evaluate (`expect(ok).toBe(true)`) AND add a sanity floor for payload sizes (`expect(sizeBytes).toBeGreaterThan(500_000)` when real size is ~1.6 MB). The server identity guard (first test, serial mode) catches most cases but defence-in-depth matters
- **`patch.dict(sys.modules, …)` around code that reaches `detect_hardware()` aborts the interpreter on Apple Silicon — and a full-suite run hides it.** `detect_hardware` imports `mlx_whisper`; a native module first imported *inside* the swap is dropped when the swap is undone, and the next import initialises mlx's extension twice: `Fatal Python error: Aborted`, the whole file dead. `e3537132` made `check_whisper_model` resolve the backend, so `tests/test_doctor.py` died this way on this Mac and on CI's macOS cells (fixed `45fc42dc` — stub `bristlenose.utils.hardware.detect_hardware` for the class). Two full-suite runs here passed regardless, because an earlier file had already imported mlx outside any swap. **After a change that makes a function reach hardware detection, run each touched test file alone** — that is the order CI's per-cell runs and a developer's `pytest tests/test_x.py` use. **Tell:** a file that is green inside the suite and aborts on its own. **Sibling, same tool: a `MagicMock` standing in for a package makes its submodule imports order-dependent.** `patch.dict(sys.modules, {"huggingface_hub": MagicMock()})` leaves `import huggingface_hub.utils.tqdm` failing ("not a package") when the real submodule has never been imported, and succeeding when an earlier test already imported it, so a test passed alone and failed in the full suite (15 Oct 2026, `test_returns_snapshot_path`). When the code under test imports a submodule, put the real module in the same patch dict, or assert only what does not depend on it.
- **Tests must not depend on local environment** — CI runs with no API keys, no Ollama, no local config. Always mock environment-dependent functions. The v0.6.7–v0.6.13 release failures were caused by tests that passed locally but failed in CI. **The LLM-config half is now automatic:** the autouse `no_local_llm_config` in `tests/conftest.py` keeps every test off the repo's `.env`, the user-level config `.env` (the stored current provider), the keychain and the provider/model/key env vars. Until 4 Oct 2026 nothing did — 1376 tests in 69 files read both `.env` files and most queried the real Keychain via `security`, and three passed only because the repo-root `.env` named the provider they expected (from a worktree they failed). Three things it cannot do for you: **(1)** patching `config._find_env_files` isolates nothing on its own — pydantic reads `BristlenoseSettings.model_config["env_file"]`, computed **once at import**, which is why the fixture pins it; **(2)** a module- or session-scoped fixture that builds settings (a live serve, `create_app`) runs *before* any per-test fixture, so it must call `isolate_machine_config` itself (`tests/test_mcp_helper_behaviour.py`); **(3)** a test that genuinely needs the real store opts out with `@pytest.mark.machine_config` (`slow` is exempt already). **Installed tools are the half it does not cover.** A test that asks the machine whether `winget`, `brew`, `ffmpeg` or `ollama` exists (`shutil.which`, `platform.system`) passes wherever the answer happens to suit it: three Ollama-on-Windows tests assumed winget was absent, which is true on every Mac, and failed on CI's Windows runner, which has it (5 Oct 2026, held 0.34.0; fixed `1fab2650`). Stub the tool's presence explicitly, and test both answers. **Tell:** a test green on the Mac and red on exactly one runner OS. **Tell:** a test green from the repo root and red from a worktree. Mechanism and remaining gap: `docs/design-keychain.md` §Testability, Python post-script. Sibling trap from building it: a sweep over `sys.modules` must read `module.__dict__`, never `getattr` — `torch.classes` answers every name with a proxy that raises on attribute access, which errored all 6151 tests the first time torch was loaded
- **A test that runs `git commit` in a scratch repo must give that repo an identity.** macOS invents one from the hostname, so the test passes on every Mac; the Linux CI runner has none, `commit` and `commit-tree` fail, the fixture repo is empty, and every assertion on it reads `''`. That was seven release-suite failures on 11–12 Oct 2026 (`scripts/test-release-sh.sh`, the hold fixture). Set `user.email`/`user.name` per scratch repo, as the suite's other blocks do. **Reproduce on the Mac** by pointing `GIT_CONFIG_GLOBAL` at a file holding `[user] useConfigOnly = true`; an empty global config is not enough, because git still guesses.
- **On Windows, a test that moves or renames an output folder after a pipeline run must call `bristlenose.logging.release_log_file()` first.** The root handler holds `<output>/.bristlenose/bristlenose.log` open, and Windows refuses the rename (WinError 5) or the move (WinError 32). The CLI already does this before its own renames. Green on every Mac and Linux cell, red only on `windows-latest` (fixed `6d91f9cb`).
- **`os.stat_result(tuple(st), {...})`'s second dict is PLATFORM-GATED — it silently drops fields the OS doesn't declare.** Faking a macOS-only stat field this way (`st_flags`, `st_birthtime`) works on macOS and becomes a **no-op on Linux**: the attribute never lands, the code under test correctly takes its Linux branch, and the assertion fails there while passing on every local run. No error, no warning — the fake just isn't there. Cost the v0.23.0 release a full 30-minute cycle (3 failures in `tests/test_cloud_materialisation.py`, both ubuntu matrix cells red, both macOS cells green). **Fake platform-specific stat fields with a proxy object**, never with `os.stat_result`'s optional dict: `class _Stat: def __init__(self, st): self._st = st; self.st_flags = …` plus `__getattr__` forwarding. The proxy carries the attribute on any OS, and production code reads it by name. Same file's `test_linux_without_st_flags_is_false` already used the proxy shape to prove the *opposite* case — copy that, not the dict. Generalises to any `os.*_result` (`statvfs_result`, `times_result`): construct a proxy, not the real type
- **Presidio slow tests need spaCy model** — `@pytest.mark.slow` tests in `test_pii_audit.py` require `presidio-analyzer` + `spacy` + `en_core_web_lg` (400MB download). They're deselected by default everywhere (`addopts`), not just in CI. Run with `pytest -m slow`
- **Red-first proves each new test can fail; it does not prove each fix is pinned.** After the 12 Oct 2026 lifecycle work landed with every test proved red first, a pass that reverted each *fix* on its own (scratch `git archive` of HEAD, `PYTHONPATH`, import path asserted) found four of ten guards that no test noticed: `db.py`'s path rule was masked because `create_app`'s log setup creates the same folder one call earlier, two handler branches only run when a second project row exists and no test made one, and a registry guard sat behind a request path no test reached under a live run. **When several fixes land together, mutate each one alone**, and treat a survivor as an unpinned fix even when the behaviour is right. **Tell:** a fix that is one of a pair, or a branch that only runs in the state the fix prevents. **And a test that pins the callee does not pin the caller:** `aliveOwnedRunPID` kept the PID file on an indeterminate check and its test proved it, while `performScan` swept the file on any nil one frame up — green suite, fix undone (found in review, 12 Oct 2026). Pin the function the incident's path goes through, not the helper you wrote.
- **`_thread.interrupt_main()` is not Ctrl+C, and a test built on it can prove the wrong cause.** It sets the interrupt flag without waking a thread blocked in a lock or `Event.wait()`; a real SIGINT does wake it. On 14 Oct 2026 a Ctrl+C test built on `interrupt_main` went red on the old code for exactly that reason, and the bug was written up as "the interrupt cannot land" — a review measured a real SIGINT landing in 0.3 s; the true blocker was `ThreadPoolExecutor.__exit__` waiting for a worker still downloading. Simulate Ctrl+C with `signal.pthread_kill(threading.main_thread().ident, signal.SIGINT)` from a timer. **Sibling:** once a Ctrl+C has interrupted a `Thread.join()`, CPython 3.12 can report the thread stopped while it still runs (measured, same review), so wait on your own `threading.Event` set in the worker's `finally`, never on `is_alive()` after an interrupt. `ensure_hf_model` in `bristlenose/utils/package_install.py` is the worked form.
- **A script loaded with `importlib.util.spec_from_file_location` must be put in `sys.modules` before `exec_module` if it defines a `@dataclass`.** The decorator looks its module up there, gets `None`, and collection fails with `'NoneType' object has no attribute '__dict__'`, which names neither the dataclass nor the loader. `sys.modules[spec.name] = module` first; `tests/test_check_whisper_sizes.py` is the worked form (15 Oct 2026).
- **A hand-rolled mutation harness gives a convincing wrong number in two ways.** Measured 11 Oct 2026, both on the same harness. (1) **Running pytest from the repo root imports the repo, not the mutated copy.** With cwd first on `sys.path`, every mutant "survived" (12 of 12) because the unmutated code was what ran. Run from inside the mutant copy, and assert `module.__file__` points into it before trusting a verdict. (2) **`*failed*` matches `2 xfailed`.** Pytest's summary line reads `27 passed, 2 xfailed` on a clean run, so a substring check scored the *unmutated* baseline as killed. Match `*[0-9]" failed"*`. Both are the "prove the mutation landed / a verdict the shell cannot withhold" family: check the baseline reads clean before reading any mutant. The working harness is `experiments/skills-research/pbt/run_mutants.sh`.
- **Stale `__pycache__` can serve old CSS after theme edits.** Stage 12's static-render code reads CSS files at runtime, but stale `.pyc` bytecode can interfere with the import chain. If theme CSS changes aren't appearing in the byproduct HTML on disk (or in `bristlenose serve`'s auto-rendered output), run `find . -name __pycache__ -exec rm -rf {} +` before re-running. For daily dev, set `export PYTHONDONTWRITEBYTECODE=1` in your shell profile to prevent `.pyc` creation entirely. **And the freshness check is (mtime-in-whole-seconds, size) — so a same-size edit inside the same second as the last compile is invisible.** That is not an exotic case: it is the exact shape of a mutation test, which this file's own doctrine asks for (*prove the assertions bite*). Swapping `item.pop(` for `item.get(` and restoring seconds later left the restored source byte-identical to its backup — `diff -q` said so — while pytest went on failing against the mutant, which reads as *the restore silently didn't happen* and invites you to go hunting a concurrent session. It is the `.pyc`. **Tell:** a test failing against source you have just read and confirmed correct. **Fix:** run mutation passes under `PYTHONDONTWRITEBYTECODE=1`, or clear the cache between mutation and verification — and note that a bare `python3` (3.10 here) and `.venv/bin/python` (3.12) keep **separate** caches, so clearing one proves nothing about the other. **And a mutation that did not land reads as a mutation that passed.** Three times on 22 Sep 2026 a text-replace mutation against a locale JSON matched nothing — the value was stored `\u`-escaped where the pattern was literal, or appeared twice where a uniqueness guard refused — the file was written unchanged, the suite stayed green, and “green under mutation” was about to be reported as proof. **Assert the mutation landed before running the test** (`json.loads` the file and compare the value), and prove a gate red on the mutant, never merely green on the original. **A mutation that lands can still change nothing:** renaming a cache key (`"transcripts"` → `"_transcripts"`) renames it at the writer and the reader alike, so the behaviour is identical and the test rightly stays green — remove the guard, don't rename it (3 Oct 2026). **And a mutation can land on the wrong line.** An indented line is a substring of the same text indented deeper, so `replace(old, new, 1)` with a 12-space `attached["files"] = now` hit the 16-space line in an earlier branch, and a mutant meant to kill a fix "survived" (17 Oct 2026). Assert `s.count(old) == 1`, not `old in s`, and widen the pattern with a neighbouring line until it is unique
- **A `KeyboardInterrupt` that escapes a test aborts the whole pytest session, and the summary still reads green-ish.** Mutating `run_lifecycle._signal_handler` (R19, 20 Oct 2026) made a unit test's second handler call raise; pytest stopped the run, printed `!!! KeyboardInterrupt !!!` and `2 passed, 57 deselected` — no `FAILED` line, so a mutation pass filtering on `FAILED|failed` read it as survived, and every later test was never run. A test that calls a signal handler (or anything that may raise `KeyboardInterrupt`) catches it and calls `pytest.fail(...)` (`tests/test_hosted_run_quit.py`). Tell: a suite count far below the selection, or a `KeyboardInterrupt` banner, with no failure listed.
- **A mutation harness that backs a file up and restores the whole copy erases a concurrent session's edit.** 20 Oct 2026: a frontend mutation pass copied `utils/api.ts` to `.mutbak`, mutated it, ran vitest and moved the backup back; the curation session saved an edit to the same file during the run, and the restore wiped it, with nothing failing. In this shared checkout another session can write any file between your backup and your restore. Mutate by replacing the anchor and undo by the reverse replacement (assert `count == 1` both ways), so a concurrent hunk elsewhere in the file survives; and tell the file's other owners before mutating a file they are editing. **Tell:** a session reporting that an edit it made has vanished from a file you were mutating.
- **A test timeout that keeps needing doubling is a hang, not a slow path — and here it was a real bug.** `tests/test_run_lifecycle.py`'s SIGINT/SIGTERM tests failed on ubuntu-latest only, and were "fixed" three times by raising the deadline (15s `proc.wait` → poll at 120s → 240s), each time diagnosed as matrix CPU contention. It was never slowness. `run_lifecycle` appended `run_started` at one statement and only opened its `try:` several statements later, leaving the pid-file write, the log line and `telemetry.set_run_context` **outside every handler**. A signal landing in that window raised `KeyboardInterrupt` straight out of `__enter__`, **no terminus event was ever written**, and the run read as *stranded* — reconciled to `run_failed` on the next start. A researcher who pressed Ctrl-C during startup was told their run had **failed**. The test aimed straight at the window because it signalled as soon as `run_started` appeared; on a loaded runner the subprocess was still inside it. Fixed 8 Aug 2026: the guard now opens on the statement after `append_event(started_event)`, and the tests wait on a **readiness sentinel** the subprocess writes just before `signal.pause()`, so the signal reaches a genuinely paused process. Deadlines came back to 60s. Three lessons: (1) polling the events file rather than `proc.wait` is still right — keep `_wait_for_event`; (2) **wait for the state you are about to act on, not a proxy that merely precedes it** — `run_started` is written during startup, several statements before the body runs; (3) when a flaky test only fails under load, suspect an unguarded window before you suspect the clock, and prove it by *widening* the window deterministically (patch the slow call) rather than racing it. Pinned by `test_subprocess_sigint_during_startup_is_cancelled`, which fails on the old code while the original test still passes — the reason it had to be added rather than just relaxing the deadline
- **CI `test` job doesn't `npm run build` the frontend** — `bristlenose/server/static/` is empty in pytest CI, so `_mount_prod_report` returns the C3 fail-loud "Build incomplete" 500 page instead of an SPA HTML response. Any new pytest test that hits a `/report/*` route in prod mode (`create_app(..., dev=False)`) fails with `AssertionError: …Build incomplete…`. Two ways out: (1) build the frontend in CI test job (~30-60s/cell — recommended long-term); (2) use the existing `prod_app_factory` pattern in `tests/test_server_status_page.py` which monkeypatches `_STATIC_DIR` to a tmp dir containing a synthetic Vite-shaped `index.html` with `<div id="bn-app-root">`. **`dev=True` on `create_app` does NOT route to `_mount_dev_report`** — mount selection reads the `_BRISTLENOSE_DEV` env var (named `hmr` inside `create_app`), not the `dev=` param. Setting `dev=True` only enables playground/admin/debug-500 features; for the dev mount you'd need to set env-var before calling. Use the `_STATIC_DIR` monkeypatch instead
- **CI fires on push-to-main and pull_request-to-main only, not on feature branch pushes** — `.github/workflows/ci.yml` `on:` block has no `push.branches: [<feature>]`. Pushing to a non-main branch updates origin but triggers nothing. To get CI signal before merging, open the PR. (Counter-intuitive coming from projects that run CI on every branch push.) `release.yml` fires only on `push.tags: ["v*"]`
- **Smoke fixture must include a `pipeline-events.jsonl` with a `RunCompletedEvent`** — `tests/fixtures/smoke-test/input/bristlenose-output/.bristlenose/pipeline-events.jsonl` carries a hand-crafted terminus event so `app.state.last_run[1]` populates on server startup, so `status_page.detect_status` returns `None`, so `/report/*` falls through to the SPA mount. Without it the server-rendered status page intercepts ("Nothing to see here, yet.") and every SPA-based test against the fixture fails on `#bn-app-root` being absent. Run_id and timestamps are stable strings — don't regenerate them on whim, or perf-history will see git-noise as a perf change. Regression-pinned by `tests/test_server_status_page.py::TestSmokeFixtureMountsSPA` + `e2e/tests/spa-mounts.spec.ts`. **Any new test fixture that boots `bristlenose serve` against it inherits this contract** — give it a terminus event or the SPA never mounts. **This committed `.bristlenose/` dir LOOKS like runtime detritus but is a deliberate contract — don't delete it or assume the gitignore should swallow it.** Everywhere else `.bristlenose/` is a per-run state dir (db, log, llm-calls.jsonl) carrying re-identification keys and is gitignored; this one fixture is the sole tracked exception, re-included via a surgical negation in `.gitignore` (the dir + `pipeline-events.jsonl` + `intermediate/*.json` are tracked; logs/db stay ignored even inside it). If a future cleanup proposes synthesizing it at test-time, that's a legitimate option — but until then, keeping it committed is the intended resting state (7 Jun 2026)

## Python, CLI and code conventions

- **Rich's `console.print()` eats `[name]` as markup tags.** Square-bracket sequences are parsed as Rich style markup; unknown style names (e.g. `[serve]`, `[apple]`) are silently consumed, so `pip install bristlenose[serve]` renders as `pip install bristlenose`. Two fixes by site type: (1) plain-text output (doctor fix messages, log lines) → `console.print(text, markup=False)`; (2) sites with intentional Rich markup interpolating user-supplied text → `from rich.markup import escape; console.print(f"[bold]{escape(value)}[/bold]")`. Audit any new `console.print` that interpolates package-spec / file-glob / version-range text
- **Export filenames: use `safe_filename()` not `slugify()`** — `slugify()` lowercases and hyphenates (`"Acme Research"` → `"acme-research"`). `safe_filename()` preserves spaces and case for human-readable Finder names. Both are in `bristlenose/utils/text.py`. Use `safe_filename()` for all export naming (zip folders, transcript files, clip files, download filenames)
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only
- **Auditing CLI flag deletion: grep Swift call sites too.** A3 deleted `--static` from `bristlenose run` because the static-render naming was a conflation — but the same Typer option was aliased as `--no-serve` and the macOS sidecar's `PipelineRunner.swift:957` was passing it to suppress auto-serve so Swift's ServeManager can manage the serve port separately. Deleting both spellings broke the desktop alpha path. Caught during the doc-sweep verification before any cohort tester saw it; restored as `--no-serve` (without the misleading `--static` alias). Rule for future: when deleting a CLI flag, `grep -rn '"--<flag>"' desktop/` *before* the Python edit, not after. Aliases are typically there because two semantically-distinct concerns share a single option declaration — separate the concerns at deletion time, don't just drop both names. **This extends to whole commands, and to CI workflows as a call site.** `bristlenose render` was removed (`7258cdb`) but `.github/workflows/install-test.yml` kept invoking it at four job sites, reddening `Install & Smoke Test` on every run for ~11 days (24 May–4 Jun 2026) — and it went unnoticed because the machine-local CI monitor (`~/.claude/scripts/ci-status-check.sh`) was watching a stale workflow `name:`. When deleting a CLI command or flag, `grep -rn` **both** `desktop/` **and** `.github/workflows/` before the Python edit
- `doctor.py` imports `platform` and `urllib` locally inside function bodies (not at module level). When testing, patch at stdlib level (`patch("platform.system")`) not module level
- `check_backend()` catches `Exception` (not just `ImportError`) for faster_whisper import — torch native libs can raise `OSError` on some machines
- **`Console(width=min(80, Console().width))`** — the `Console()` inside `min()` is a throwaway instance that auto-detects the real terminal width. This is the intended pattern; don't cache it
- **`BRISTLENOSE_FAKE_THUMBNAILS=1`** env var — layout testing only. Defined as `_FAKE_THUMBNAILS` in `bristlenose/stages/s12_render/dashboard.py`
- **Logging**: two independent knobs — `-v` controls terminal (WARNING/DEBUG), `BRISTLENOSE_LOG_LEVEL` env var controls log file (default INFO). Log file lives at `<output_dir>/.bristlenose/bristlenose.log` — **not** at `.bristlenose/bristlenose.log` relative to cwd. When grepping per-project logs, always prefix with the output dir. See `docs/design-logging.md`
- **A log message is always one line.** Both handlers use `_OneLineFormatter` (`bristlenose/logging.py`), which escapes newlines and control characters in the message as visible `\n`, `\x1b` and so on, so a request value cannot start a forged record. A message built with embedded `\n` (a banner, a traceback passed as `%s`) prints as one run-on line: log one record per line, and pass a traceback as `exc_info=`, which `format()` appends over its own lines (`dfb935cf`, 19 Oct 2026).
- **LLM request latency**: every `LLMClient.analyze()` call emits one INFO line `llm_request | provider=X | model=Y | elapsed_ms=N | schema=Z` (added Apr 2026 for perf baselining). Greppable for median/p95 analysis — see `docs/design-perf-fossda-baseline.md` step 6. New providers get this automatically (wrapping is in the dispatcher, not per-provider)

## Pipeline, data and participant privacy

### `attempted == succeeded + failed` is a TAUTOLOGY in most rollups — it cannot catch a silent drop

The obvious guard against "a session vanished" is per-bucket conservation. It is
the wrong one nearly everywhere, and it fails in the most flattering way: green on
the very incident it was written for. Wherever `succeeded` is **derived by
subtracting** failures — every rollup in `Pipeline.run`, before *and* after
`6497711a` — the identity holds by construction. The 20 Aug loss reported
`transcripts: attempted=57 succeeded=57 failed=0`, and `57 == 57 + 0` passes.
`ingest` is worse still: `pipeline.py` builds it as `attempted=succeeded +
len(failed)` **literally**. And it false-*positives* where `_record_parse_failure`
fires per **file** inside `for f in session.files` while the counters are per
**session** — one session with two bad subtitles gives `1 == 0 + 2`, red on a
correct run.

It has teeth in exactly one place: **`run_transcription_only`**, whose rollup
measures success independently (a session counts when it produced segments), so a
silent recording really does fall out of the sum. That is also the only command
with **no downstream bucket**, so the cross-bucket check below cannot reach it —
which is why `scripts/acceptance/invariants.py::assert_sessions_accounted` exists
and why the `transcribe:no-key` cell drives that command specifically.

**The check that does catch the general case is cross-bucket**, not within-bucket:
`transcripts → topics → quotes` are all denominated in *sessions* (`s08:51`,
`s09:128`), so `topics.attempted == transcripts.succeeded` fails on the real bug
(42 ≠ 57). `themes` is `1 + 1` LLM calls (`s10:49`, `s11:49`) — the chain ends
before it. Any such check must also be truncation-aware: `_truncate_failed` caps
`failed` at `STAGE_FAILED_MAX + 1` without touching the counters.

**Naming trap in the same area:** the CLI verb is **`bristlenose transcribe`**.
`transcribe-only` is the *run kind* (`KindEnum.TRANSCRIBE_ONLY`, what the desktop
reads from the events log) and is **not** a command — `bristlenose transcribe-only`
exits with "No such command". The internal function is `run_transcription_only`,
which makes all three names differ.

### The pipeline speaks THREE stage vocabularies, and two of them overlap on exactly two ids

A "stage id" is not one thing. `manifest.py STAGE_ORDER` has ten
(`identify_speakers`, `topic_segmentation`, `quote_extraction`,
`cluster_and_group`, `pii_removal`); `timing.py ALL_STAGES` has seven coarse
ones and is what **`run_progress.stage` actually carries** (`speakers`,
`topics`, `quotes`, `cluster`, `pii`); and `_llm_telemetry.stage(...)` uses a
third — the module name (`s08_topic_segmentation`).

The first two **coincide on `transcribe` and `render`**, which is what makes
crossing them survive review: the two you spot-check are right and the other
five fall through to a default. In the run inspector (13 Sep 2026 — a dev-only
surface, `serve --dev` or the DEBUG desktop build, so no release shipped it) that
default was `.title()` for the label, `order=99`, and `is_llm=False` — so the
gantt lost LLM colouring on all three LLM bars, and `pii` rendered as **"Pii"**.
Downstream, `_TIMING_METRIC_STAGE` translated coarse→manifest and then indexed a
dict keyed by *coarse* ids, so four of six μ±σ rows were silently dropped.

**The unit test could not catch it, because the fixture was written in the wrong
vocabulary** — it fed `stage: "quote_extraction"`, a value no pipeline has ever
emitted, and so asserted `status == "llm"` against the manifest names the labels
happen to use. Green throughout. Same family as the degenerate-fixture trap
above: *a fixture that does not speak the producer's language tests the reader
against itself.*

**Rule:** when consuming `run_progress`, translate at the boundary, once, and
drive the test from `ALL_STAGES` itself rather than a hand-written list — a new
estimator stage then fails loudly instead of shipping unlabelled. **Tell:** a
stage rendering as a `.title()`d guess (`"Pii"`, `"Cluster"`), or a per-stage
table that is mysteriously missing rows whose data you know exists.

### A coarse cache record silently overrides the fine one — so fixing per-session state can change nothing

The manifest carries a **stage** status and a **per-session** map, and the stage
status is checked first. `_is_stage_verified` returns at `status == COMPLETE`
and takes the full-cache read; `get_completed_session_ids` is never consulted.
So a per-session record can be perfectly honest and still be **unread**.
*(Fixed for s08/s09 on 12 Sep 2026 — `mark_stage_complete` now derives from its
own session map; s05 followed on 18 Oct and s05b on 20 Oct 2026. The lesson below
is the durable part.)*

Measured 12 Sep 2026, and it cost a wrong claim to the user. `6277eabe` stopped
s09 marking *failed* sessions complete — correct, tested, proved red against the
pre-fix tree — and was reported as "the failed session is retried on the next
run". It is not. `mark_stage_complete` runs unconditionally after the
`succeeded == 0` abandon check (`pipeline.py:1747`), so one failure out of ten
still yields a `COMPLETE` stage. Two-run probe, 3 sessions with 1 failing and
**non-empty** output: run 2 called `extract_quotes` not at all, and reported
`attempted=8 succeeded=8 failed=[]`.

**Two things generalise.**

**(1) Absence is not a state.** The fix made the failed session *absent* from
the session map, and absent is indistinguishable from *not yet attempted* —
which is why `_derive_stage_status` (a tested helper that returns `PARTIAL` for
exactly this case, and is used by `bristlenose status` but not by
`mark_stage_complete`) sees `{COMPLETE}` and says `COMPLETE`. Record the failure
(`StageStatus.FAILED` is in the schema and nothing writes it) rather than
omitting it. Whenever you "fix" something by *not writing a record*, ask what
reads the absence.

**(2) A fixture that makes the guard you are testing unreachable.** The test
added with that fix returns `[]` quotes, so `mark_stage_complete` is refused by
its own empty-content guard and the stage never reaches `COMPLETE` — the suite
passes and never exercises the short-circuit. **A fixture whose values are the
degenerate case can disable the very code path under test.** The demo that
caught it differed in one respect: four quotes per session instead of zero.

**(3) The manifest is built fresh each run, so a cache hit must write itself
forward.** `create_manifest` starts empty; cluster calls `mark_stage_complete`
after both its cached and its fresh branch for exactly this reason. The
Discussion stage first returned early on a hit, so the next run found no record
and paid again: measured 5, 0, 5, 0 calls over four identical runs (3 Oct 2026).
**And a failure that belongs to no session cannot be carried by the session
map** — a failed guide parse or cross-session call left every session COMPLETE,
so the stage cached the gap for good. Such a stage must decline
`mark_stage_complete` itself (`Pipeline._run_discussion`).

**Tell:** two readers of the same record disagreeing, one of them ticked green.
Here `bristlenose status` prints `✓ Quotes  8 quotes (2 sessions)` directly under
`✓ Transcribe  3 sessions` — the loss visible in plain sight, unmarked, while the
resume logic reads `COMPLETE` from the same file and skips the stage entirely.

### AppleDouble files on external drives

When macOS copies files to a filesystem that can't store xattrs/resource forks natively (ExFAT, FAT32, SMB shares, some NFS exports), Finder creates a `._<name>` sidecar alongside every user file to carry the metadata. These are **binary blobs that share the user file's extension** — `._foo.mp4` looks like a video to anything that classifies by suffix; `._s1.txt` looks like a transcript and crashes utf-8 decode (`UnicodeDecodeError: byte 0xb0`).

Any directory scanner that walks a user-supplied folder must filter these. Use `is_os_metadata(path)` from `bristlenose/utils/fs.py` — it catches `._*` AND `.DS_Store`. Already applied at `discover_files` (s01_ingest), `load_transcripts_from_dir` (pipeline.py), and the server importer scan sites. **When adding a new scan site that walks a project folder, call `is_os_metadata` first.** The Swift `ProjectFolderWatcher` already filters via `.skipsHiddenFiles` + `name.hasPrefix(".")`.

### macOS claims `.ts` and `.mts` as VIDEO — never accept a media extension by suffix alone

macOS's UTI table maps `.ts` to `public.mpeg-2-transport-stream` and `.mts` to
AVCHD, so Spotlight indexes them as `public.movie`. On a dev machine that is
catastrophically wrong: `mdfind 'kMDItemContentTypeTree == "public.movie"'`
returned **33,381 `.ts` files** on this Mac, every one of them TypeScript, plus
268 `.mts` that were all `.d.mts` declaration files. Not a single real transport
stream among them.

Consequence: `.ts` is **deliberately excluded** from `AUDIO_EXTENSIONS` /
`VIDEO_EXTENSIONS` in `models.py`, and must stay excluded. Accepting it by
suffix would make `bristlenose run frontend/` ingest the source tree as
recordings. `.mts` *is* accepted (AVCHD camcorders genuinely write it and the
`.d.mts` collision only bites inside `node_modules`, which no researcher drops
on us) — but if transport streams ever need first-class support, gate on
content sniffing, never on the extension.

Generalises: any time you reach for Spotlight or a UTI to classify user media,
sanity-check the result against `file`/`ffprobe` before believing it. The
system's answer is about *the extension*, not about the bytes.

### A fixed number of tags per group is the tell of an invented taxonomy

Every February 2026 framework codebook shipped with exactly four tags per
group — Norman 7×4, Garrett 5×4, Morville 7×4 — and the Norman audit on
22 Sep 2026 found why: the origin document had one tag per principle in
the author's words, and the extraction commit padded each group to four,
inventing where the book ran out (`system model`, `logical layout`,
`exploration`, `first-time use`; Garrett's `task flow`, `component
placement`, `wireframe issue`; seventeen of Morville's twenty-eight, from
a one-page essay with seven facets and no sub-facets). Nielsen, whose
source has real sub-structure, was 4/4/4/3/4/4/3/3/4/3 and mostly sound.
**A codebook that claims an author must carry only that author's terms and
concepts, cited to the page**; a useful tag that is not theirs is rescued
into the Bristlenose UXR codebook, which is ours to extend. Every authored
codebook now has a decision register (`docs/design-codebook-*.md`) and
`tests/test_codebook_registers.py` gates it. **Tell:** identical tag counts
across groups whose sources are of very different sizes; a tag name you
cannot find in the author's table of contents or index.

- **Probing the user's media for research can download their iCloud files.** `mdfind` over `~` returns evicted placeholders alongside real files, and `ffprobe` (or any read) on a dataless file makes the File Provider fetch it — gigabytes, silently, for a metadata survey. Filter first: `os.stat(p).st_flags & 0x40000000` (SF_DATALESS), or `utils.fs.is_dataless`, exactly as ingest does. Bit 11 Oct 2026 measuring recorder timestamps: the first probe ran unfiltered for two minutes before it was stopped (46 of 3,027 hits were placeholders). Same family as the scan-site rule for `is_os_metadata`: any walk over a user folder decides first what it must not touch.
- **Export JSON embedded in a `<script>` block: `ensure_ascii=True` is NOT enough — you MUST also escape `<` `>` `&`.** The long-standing belief that "`ensure_ascii=True` escapes `<` as `\u003c`" is **FALSE** (verified 26 Jul 2026): `ensure_ascii` only escapes code points **> 127**; `<` `>` `&` `/` are ASCII and pass through **unchanged**, so a literal `</script>` in untrusted embedded content (transcript text from third-party files, participant/tag/project names) breaks out of the data `<script>` → **stored XSS** in a shared artifact. After `json.dumps(..., ensure_ascii=True)`, chain `.replace("<","\u003c").replace(">","\u003e").replace("&","\u0026")`. Fixed in `export.py:_build_export_html` + regression test `test_embedded_data_cannot_break_out_of_script`. **Sibling sites audited 28 Sep 2026, all closed.** Neither site this line used to name was vulnerable (serve `/report` embeds only the URL-safe token; the quote exports are CSV/XLSX, no script). The real sibling was the sealed static renderer: six bare `json.dumps` in `<script>`, with `BN_PARTICIPANTS` taking `full_name` from speaker labels in client .docx/.vtt — all now go through `s12_render/html_helpers.script_json`, and `tests/test_static_render_script_escape.py` fails on any bare `json.dumps` in that package. The run inspector and status page already escaped. **A new embed of anything user- or transcript-derived uses `script_json` (or the same three replaces), never `json.dumps` alone** — outside `s12_render/` no gate will catch it
- **PII redaction: `model_copy()` is shallow** — when redacting transcript segments, `seg.model_copy()` copies the Pydantic model but `words` (a list of `Word` objects) still references the original unredacted words. Always clear `clean_seg.words = []` after replacing `clean_seg.text`. Same caution applies to any field that might contain PII (`speaker_label`, `source_file`)
- **`CredentialStore.set()` returning cleanly is NOT evidence anything was stored — read it back.** `MacOSCredentialStore.set()` catches `CalledProcessError`/`FileNotFoundError`/`PermissionError`/`OSError` and returns normally, **by design**: under App Sandbox `/usr/bin/security` is unreachable, so the write is a silent no-op and the CLI Mac path stays graceful. The consequence is that a clean return says only that nothing raised. Any caller that reports success off the back of a `set()` is reporting something it never checked — the Miro OAuth callback did exactly this, printing "Connected to Miro ✓" while the token existed in **no** store at all (it also lacked the paste path's in-session fallback, so there was no second copy). The Swift side has the identical shape one layer over: `KeychainHelper.serviceNames` is an **allowlist**, and `CloudGrantStore` shipped against an unregistered key persisting nothing, with no error anywhere. Both were invisible for the same reason — nobody read back. Fixed 18 Aug 2026 (`d3c5f572`): `_store_token_verified` in `server/routes/miro.py` stores then `get()`s, and a mismatch is a WARNING, not a shrug. Note a read-back returning a *different* value is also failure — an env var shadows both the file and keychain reads, so the value just written is then not the one that will be used. **When wiring any new credential write, verify the round-trip; when a "saved" state disagrees with a later read, suspect the write, not the reader.** The helper is `credentials.set_verified()` (4 Sep 2026); `bristlenose configure` uses it and exits 1 rather than print "Stored in Keychain" for a key it could not read back, and Swift's `KeychainHelper.set` reads back both of a shared key's copies — the same day's find was that the CLI and the Mac app wrote same-named items to *different* keychains and neither read the other's (`docs/design-keychain.md` § "One keyspace, two keychains").
- **PII summary is a re-identification key** — `pii_summary.txt` lists every original PII value with timecodes. It lives in `.bristlenose/` (hidden), NOT in the shareable output root. Never move it back to the output directory
- **`record_call` needs THREE contextvars, and binding two of them looks exactly like binding all three.** `_run_dir`, `_run_id` and `_stage_id` — a missing one of any is the same silent return with a DEBUG line, indistinguishable from telemetry being switched off. **Signal elaboration bound `telemetry.stage("serve_signal_elaboration")` and nothing else, so every call it ever made was dropped** (fixed 20 Sep 2026). It survived because a *convincingly partial* wiring is worse than an absent one: `with telemetry.stage(...)` reads as "telemetry is handled here" and is true — it does bind a contextvar — so it passes the glance that would have caught a missing call outright. Found only by going to the log for elaboration latency and reading 260 rows across 11 projects with none of that stage among them. **Serve mode is where this bites, structurally:** a pipeline run binds the context once in `run_lifecycle` and every stage inherits it; a request inherits nothing, so each serve-time LLM caller must bind its own. Use `telemetry.serve_run_context(project_dir, run_id)` — it takes the project root *or* the output dir, because callers hold one or the other and guessing wrong writes the file where nobody looks, which is the same outcome as not writing it. `server/autocode.py` still inlines the same dance; a third caller should not. **Tell:** a surface whose spend you cannot find in `llm-calls.jsonl` — look for its `stage` string, not for the feature name.
- **The transcription-quality record carries a timeline of each recording** — `<output_dir>/.bristlenose/intermediate/transcription-quality/<sid>.json` holds gap spans and a 10-second series (no words, no names). Like the LLM call log below, never in an export or support bundle; a telemetry payload sends `transcription_quality.summary(record)` only
- **LLM call log is a re-identification key** — `<output_dir>/.bristlenose/llm-calls.jsonl` carries session ids, prompt shas, and timing fingerprints (sibling to `pii_summary.txt`). Never include in any export, support bundle, or shareable archive. Mode `0o600` + `O_NOFOLLOW` enforced by `bristlenose/llm/telemetry.py`. Kill switch: `BRISTLENOSE_LLM_TELEMETRY=0`
- **`pii_score_threshold` is the only PII config that's wired** — `pii_llm_pass` and `pii_custom_names` are declared in `config.py` but unimplemented; since `fa78e936` (14 Aug 2026) setting either makes `s07_pii_removal.py` **refuse the run** (fail-loud — an unimplemented privacy control must not warn-and-continue). Don't write code that reads them without implementing the feature first. **And `pii_score_threshold` is the bar for PERSON, not for everything** — pattern-matched entities (phone, email, NHS, card, IBAN, IP, the US identifiers) take a 0.40 floor via `score_bar()`, because Presidio scores a bare phone match **0.4** and only reaches ~0.75 when a context word ("call", "mobile") happens to sit nearby. At a flat 0.7 a participant reading their number aloud was **not redacted** — measured 2 of 8 on the planted corpus, 7 of 8 after the split. **Do not quote the corpus's "false positives unchanged at 9 of 32" as the safety evidence** — every one of its 32 negatives is a word and none contains a digit, so it could not have shown a phone, NHS or card false positive at any threshold (the degenerate-fixture trap, caught in review the same day). The evidence that can speak: 16 number-dense non-PII sentences, where the floor adds exactly one detection, `10.0.0.1` as `IP_ADDRESS` — a genuine IP. Consequence that surprises people: **raising the threshold to 0.9 does not make phones conservative and cannot** (they cap around 0.75, so honouring it would disable them); it makes PERSON conservative, which is where the false positives actually are. The floor may only ever *relax* a bar, so lowering the setting still lowers everything. **Tell you are about to be fooled here: a detector test whose sentence contains the word "phone" or "call"** — the context boost carries it over 0.7 and the bug is invisible

## i18n

### A locale key that fits is not a locale key that MEANS the same thing

`s11`'s thin-theme bucket reused the Quotes lens's `uncategorisedHeading` /
`uncategorisedIntro` — same concept, apparently, and it bought 21 reviewed
translations free. It was wrong in all 21 at once. Those keys belong to the
**floor**: pinned quotes the persistence layer froze. The sentence reads *"quotes
you kept aren't in any section or theme"*, and for the thin-theme bucket both
halves are false — these were never kept, and they **are** in a theme, the one the
sentence is the description of.

Two further hazards in the same move. The floor's copy interpolates a count the
SPA **recomputes live** from its own array; a theme description is persisted and
rendered raw, so borrowing it froze a number that nothing recomputes — hide one
quote and the prose contradicts the cards under it. And root `CLAUDE.md` already
warns that rewording an `en` value is a 21-file change no gate can see: sharing a
key across two surfaces in two languages of the codebase means a future copy tweak
to one silently rewords the other, with nothing connecting them.

**Rule: before reusing a key, read the value in full and ask what surface wrote
it.** Two concepts that share a word are still two concepts, and a new key pair
costs one seeding pass. **Tell:** borrowed copy that interpolates a count, or a
value whose subject is named in the sentence rather than implied.

### i18n — single source of truth

- **Which surfaces are targets is settled — `docs/design-i18n.md` §"Which surfaces are targets".** Browser SPA and macOS app UI are localised; CLI terminal chrome, public-facing docs, App-Store-hidden diagnostic chrome, and forensic/wire records are English. **Each row is a property of the surface, never a stage of the project** — "not yet, we're in alpha" is the absence of a reason, and it is how three stale policies accumulated. **The authoring failure the table exists to prevent is a sentence filed as data:** a `String` property on a type that models a *thing* rather than a *screen* — `errorDescription` on an error, `signInTitle` on a platform, `humanSummary` on a category. Every one of the ~100 gaps the 21 Sep 2026 Swift audit found had that shape. Errors carry a **case**, not a sentence; non-View types take `I18n` as a parameter (`CloudPlatform.windowTitle` is the worked example)
- **Locale files live in `bristlenose/locales/` only** — `frontend/src/locales/` was deleted. The frontend imports via Vite alias `@locales`. Don't create locale files in the frontend tree. `I18n.swift` (desktop) reads the same JSON at runtime
- **`useTranslation()` is the hook; `i18n.t()` is the direct import** — use the hook inside React components; use `import i18n from "../i18n"` + `i18n.t()` in stores, announce utilities, and other non-component code
- **New keys must go in every locale directory** — currently 22: en, es, ca, ja, fr, de, ko, cs, it, pl, ru, uk, da, sv, nb, tr, nl, fi, pt-BR, pt-PT, zh-Hant, zh-Hant-HK (pl/ru/uk/da/sv/nb/tr/nl/fi/ca are machine-seeded — **a resting state, not debt**: a native pass happens when a real user in that language turns up or a multilingual friend offers, not on a schedule. Czech was the first language users asked for and that is the model. Don't list these as an outstanding gap; the seeds are grounded in the Apple and Microsoft loctable corpora, `glossary.csv`, and the per-language QDA terminology research in `docs/design-i18n.md` — better than nothing by a distance, and the correction arrives with the user). **`zh-Hant-HK` is the one exception — a thin *override* fork, not a full locale:** it carries only genuine HK-idiom differences (e.g. `軟件` vs Taiwan `軟體`) and inherits everything else via the deliberate `zh-Hant-HK → zh-Hant → en` fallback (spec: `docs/design-i18n.md` §"the Traditional pair"). **Do NOT add ordinary new keys to it** — absent = inherits `zh-Hant`; an English placeholder there would pin it and *break* that inheritance once `zh-Hant` is translated. So "every locale directory" means the 21 full locales; HK gets only real HK overrides. Every `t("key")` call needs an entry in each of the 21. If using `dt()`, the desktop override must also go in each `desktop.json`
- **Rewording an `en` value is a 21-file change, not a one-file change.** _There is now a gate for it: `check-locales.py --strict` fails on any `en` value whose hash differs from `bristlenose/locales/en-value-pins.json`, naming the keys, and `--stamp` accepts the reword once every locale is updated (it fired correctly on 3 Oct 2026). The history below is why it exists._ Before that gate, every gate asked *is the key there?*, so changing an English string and leaving the translations on the old words is invisible: the key is present in all 21 files and `check-locales.py` passes. That is failure class 3 in `docs/i18n-defects.md`, and the Signals rename shipped it twice in two days — five reworded strings (three of which its own close-out listed, so even the record undercounted) sat in 20 locales describing *the analysis page* under a lens labelled Signals. **Reword and propagate in the same commit, or you have created drift that nothing will report.** Two cheap habits: look for the already-translated clause before translating anything (the pre-reword value usually carries it, reviewed — the definition in all 20 locales was a lift, not a translation), and check whether a pronoun's nearest antecedent survived the edit, because `en`'s *"apply codebook tags to generate them"* put the tags in the pronoun's path in thirteen languages, five of them with a form that matches the tags noun exactly.
- **A locale *value* edit is a frontend-suite change — vitest is the only witness, and no i18n gate can be.** Tests assert on rendered text, so changing what a key renders can redden assertions that quote it while every locale gate stays green: the keys never moved, `check-locales.py` is key-shaped, `tsc` cannot type a regex literal, and pytest does not render React. Measured 22 Sep 2026 — repairing straight quotes to each locale's own pair (`afdfaccb`, a *correct* fix) broke **eight** matchers in `CodebookAuthoringParity.test.tsx` that spelled the titles back as `/Delete "confusion"/`, and it was committed red because vitest had not been re-run after the sweep. Two of the eight were negative assertions (`queryByText(…).not.toBeInTheDocument()`) which went on passing for the wrong reason and could no longer fail at all. **Before a value sweep, `grep -rln '<the old English value>' frontend/src --include='*.test.tsx'`; after it, run vitest** — not just `check-locales.py`. Deliberately not gated: a mechanical check would have to know which strings a test quotes, which is the assertion itself. Register row 53.
- **`glossary.csv` is read by nothing but Weblate and humans, so it had no gate until 21 Sep 2026.** Twenty rows with an unquoted comma in the note field shipped green — they parse one field wide, and a translator sees the note truncated at the comma. `check-locales.py` now asserts the header's field width per row. When you add a row, quote any field containing a comma; when you add a *file* like this one, ask what reads it.
- **Deleting a locale FILE rather than a key is invisible to every gate we own, because all of them are key-shaped.** On 22 Sep 2026 `zh-Hant-HK/common.json` was deleted — correctly: it held nothing but overrides of a help modal retired in July, and the fork's whole design is that it ships a file only where it overrides something and inherits the rest. `doctor.py`'s `Bundle: locales` check nonetheless demanded `common.json` from all 22 codes, so **every desktop build failed** at the pre-sign self-test with *"missing or truncated"*. Nothing else was red and nothing else could be: `check-locales.py --strict` honours the `zh-Hant-HK → zh-Hant → en` chain, so an absent file is *correct* by its rules; the locale-key tests classify the fork in `_FALLBACK_ONLY_LOCALES`; and an orphan-key gate built the same night was blind **by construction**, because it asks who reads a *key* and this is an assertion about a *file*. **The check is one grep, on the filename:** `grep -rn "common.json" bristlenose/ scripts/ desktop/scripts/ | grep -v server/static` — the exclusion is load-bearing, since a built JS bundle carries the string and turns the output into 46 KB of noise. Two further traps the same incident carried, both general: the error text blamed a missing `datas` entry when the spec ships the whole tree as **one** entry, so it was a source-state assertion wearing a packaging error's clothes; and the gate had silently not run at all from 14 Jul to 14 Aug (`sign-sidecar.sh` made app-sandbox unconditional, and a sandbox-signed binary aborts at exit 133 when exec'd standalone), so its first words in five weeks were a false positive — which is how a revived gate gets switched off again. **Tell:** a build that fails on a data file you deliberately removed, with every test and every locale gate green.
- **No test enforces en→locale key parity — don't assume a green suite means the locales are complete.** `tests/test_pipeline_diagnostic_locale_keys.py` looks like that gate but isn't: it checks *hardcoded allow-lists* (`_REQUIRED_PILL_CATEGORIES`, `_REQUIRED_HEADERS`, `_CHROME_COUNT_PREFIXES`), so adding a key to `en` never obliges anyone to extend them and the gap ships silently. That is exactly how two gaps survived until an `i18n-review` agent pass found them (30 Jul 2026): `export.scope.*` sat in `en/common.json` alone, and 19 `desktop.json` keys were missing from **all** 19 non-en locales — `menu.project.analyse` had been rendering English "Analyse" in every locale's project context menu. **When you add a key that the allow-lists cover, extend them in the same commit; when you add one they don't, no *test* will fail.** Cheapest audit: `.venv/bin/python scripts/check-locales.py` already does the flattened-key diff. **Run it with `--strict`**, which is what CI does — bare, it reports missing keys as *warnings* and exits 0, so a local run can look clean while CI fails. For the judgement calls neither can make, an `i18n-review` agent pass.
- **…and the gate is blind in the other direction too: an ABSENT en key can never be reported missing.** `check-locales.py` flattens `en/<ns>.json` and diffs each locale *against it*, so a surface that was never enrolled in English has nothing to be missing **from** — it is invisible by construction, not by oversight. This is a distinct hole from the allow-list one above: that one misses keys the *tests* don't enumerate; this one misses keys *English* doesn't have, and no amount of `--strict` closes it. Both `check-locales.py` and `test_pipeline_diagnostic_locale_keys.py` read a locale as complete when the whole feature is absent from every file including `en`. **Worked example (18 Aug 2026):** the macOS Settings ▸ Accounts pane shipped with zero `i18n.t` call sites — every string a Swift literal, `SettingsView.swift` hardcoding the pane title `"Accounts"` while the other five panes read `desktop.settingsTabs.*`. `check-locales.py` was green throughout. Worse, the source comment justified it as *"English-only, like the rest of the cloud-import surface"* — which was **already false when written**: that debt was paid two days earlier (`49ec8a50`, 16 Aug), and `docs/design-cloud-import.md:1320` had predicted this exact recurrence in writing ("the gap that reappears will do so silently"). It did, in 48 hours. **The only gate is the diff:** a new user-facing surface is reviewed for `i18n.t` call sites at the point it lands, because after that nothing mechanical will ever ask again. Tell: grep a newly-added `.swift`/`.tsx` view for `i18n.t(` / `t("` and get zero hits.
- **…and a THIRD gate is blind, this one on the wire: `test_swift_contract_parity.py` compares only the *intersection* of the two sides' fields.** Its docstring says so plainly — *"A field Swift doesn't declare is fine — the contract is schema-additive"* — which is correct for the drift it was built to catch (optionality disagreeing on a field **both** sides decode) and useless for the one that follows. **Adding a field to `bristlenose/events.py` and forgetting the Swift mirror passes every test in the repo.** No import fails, no decode breaks, nothing is red; the field simply never reaches the Mac, and the surface that needed it goes on rendering whatever it did before. **Worked example (22 Aug 2026):** `Cause` grew `reason` so the diagnostic popover could localise refusals instead of rendering `Cause.message` raw in all 21 non-en locales. Python-only would have shipped green — 4143 passing tests, `check-locales.py` clean, a popover still in English. Note the shape: this hole and the two above are the *same* failure at three altitudes — every gate we own asks "do the things I was told to enumerate agree?", none asks "is anything missing that nobody enumerated?" **Rule: a new field on `Cause` / `StageFailure` / `StageOutcome` / `PipelineSummary` is a two-file change plus the fixture, always — `desktop/Bristlenose/Bristlenose/PipelineSummary.swift` and `tests/fixtures/pipeline-summary-contract.json` (bump `version`, and add a scenario that *uses* the field, or the Swift round-trip proves nothing about it). Note `EventLogReader.swift` holds a **second, partial** `Cause` mirror that the parity test never sees at all — check whether your field belongs there too; terminus-level causes are the only thing it decodes.**
- **Seeding an existing key into the other locales? Look for an already-translated twin first.** Bristlenose forks text across surfaces (`dt()`, and the native menu mirrors much of the web UI), so the string you're about to machine-translate often already exists, reviewed, under a different key. `export.scope.{all,selected,starred}` was a verbatim match for `menu.quotes.copyScope{All,Selected,Starred}` in all 19 locales — reused with `{{count}}`→`{{n}}`, which beat translating and made the web dropdown read identically to the macOS menu. Grep the *English* value across `en/*.json` before writing any new translation.
- **Seeding a value that names a glossary term? Read the term's `glossary.csv` row first — the glossary gates nobody.** A row is advice to a translator; no gate reads it, so a new value is checked against no term list. Measured: a 30-string sweep settled the Russian codebook noun on 20 Sep 2026 (`docs/i18n-defects.md` item 20), and `codebook.noTagsInCodebook` was seeded **two days later** as *кодовая книга* — the crypto/telecom form the sweep had just removed — green under every gate until a close-out re-measured it on 6 Oct. Before writing a value that contains Codebook, Code, Quote, Session or Signal in a locale you don't read, copy the term from the row and its declension from a sibling key that already carries it; and at any locale close-out, re-run the check that found it: every `en` key whose value says the term, read in each locale for the established stem.
- **Adding a whole new language = 5 JSON files + 9 registration sites across THREE surfaces (web, Python, native Swift).** Create `bristlenose/locales/<code>/` with all 5 namespace files (`common, desktop, enums, server, settings`) — **not** `preflight`, which is English-only (`ENGLISH_ONLY_NAMESPACES` in `bristlenose/i18n.py`, 14 Oct 2026; `check-locales.py` refuses a copy) — then register the code in all of:  
  _Was 9 until 22 Sep 2026, when `cli`, `doctor` and `pipeline` were deleted in every locale. All three describe surfaces that are **English by decision** (`docs/design-i18n.md` §"Which surfaces are targets"), so their translations could never be read — 27 keys that had never had a call site in any commit. Deleting them also shrinks the HTML export's embed, which `docs/design-export-locale.md` cares about._
  - **Web/Python (6):** `SUPPORTED_LOCALES` in [frontend/src/i18n/index.ts](frontend/src/i18n/index.ts) **and** [bristlenose/i18n.py](bristlenose/i18n.py); the `expected` set in [bristlenose/doctor.py](bristlenose/doctor.py) (`Bundle: locales` check) — **and `FALLBACK_ONLY_LOCALES` in [bristlenose/i18n.py](bristlenose/i18n.py) if the new code is a thin override fork, or `doctor --self-test` will demand a full locale's `common.json` from it and fail every desktop build**; the `LOCALE_LABELS` map in [frontend/src/i18n/localeLabels.ts](frontend/src/i18n/localeLabels.ts) (native name, e.g. `it: "Italiano"`) — **one** site, not two: it was duplicated in `SettingsPanel.tsx` and `SettingsModal.tsx` until `30f9305d` extracted it, and the panel was deleted as unreachable on 22 Sep 2026; the mock list in [LocaleStore.test.ts](frontend/src/i18n/LocaleStore.test.ts); and the locale tuples in [tests/test_pipeline_diagnostic_locale_keys.py](tests/test_pipeline_diagnostic_locale_keys.py) — `_ALL_LOCALES` (every full locale) **plus** exactly one CLDR-shape tuple: `_PLURAL_LOCALES` if the language inflects by count (the common case — one/other like it/es/de, and four-form cs/pl/ru/uk go here too since they carry `one`+`other`), or `_SINGLE_FORM_LOCALES` if it's ja/ko/zh-shaped (`_other` only). A thin fallback override goes in `_FALLBACK_ONLY_LOCALES` instead of `_ALL_LOCALES` (zh-Hant-HK is the only one) — and that tuple now **derives** from `FALLBACK_ONLY_LOCALES` in `bristlenose/i18n.py`, which is the single home for the distinction. It was a test-local constant from 3 Jul until 22 Sep 2026, which is precisely why `doctor.py` — enrolled three days before the concept existed, and unreachable from a test module at self-test time — went on requiring a full locale's files from a fork for twelve weeks. Don't skip this on the theory that the four-form tests will catch it — those derive from the presence of `_few` and need no edit; the tuples do. `test_every_locale_dir_is_classified` fails the moment a locale dir isn't in one of these lists, so the suite tells you — but only after you've added the directory.
  - **Native Swift desktop (3) — EASY TO MISS, the desktop Settings window has its OWN picker, NOT the React one:** `supportedLocales` in [desktop/Bristlenose/Bristlenose/I18n.swift](desktop/Bristlenose/Bristlenose/I18n.swift); the `Picker` `Text("…").tag("…")` list in [AppearanceSettingsView.swift](desktop/Bristlenose/Bristlenose/AppearanceSettingsView.swift); and the `expected` set in [I18nTests.swift](desktop/Bristlenose/BristlenoseTests/I18nTests.swift). The desktop reads the locale JSON from the bundle via `Bundle.main` (the xcodeproj `Copy Sidecar Resources` phase rsyncs all of `bristlenose/locales/`, so the data ships automatically — only the Swift code lists above need the edit). A plain Cmd+R self-heals the sidecar (touching `bristlenose/locales/` moves the freshness fingerprint).
  - The web runtime loader needs NO edit — it's a Vite dynamic-import glob (`import(\`.../locales/${locale}/${ns}.json\`)`), so files are picked up automatically. Lazy locale chunks are **excluded from the bundle-size budget** (the `size-limit` glob negates `common-*`/`settings-*`/`desktop-*`/`enums-*`/etc.), so a new language is size-neutral on the web bundle. **It is NOT size-neutral on the HTML export** — that is a separate single-file build (`inlineDynamicImports: true`), and because the loader's import is a template literal, Vite's glob matches `locales/*/*.json` and inlines **all 192 files**: every locale, every namespace, including `cli`, `doctor`, `preflight`, `server` and `pipeline`, which a browser report cannot use. Measured 23 Aug 2026: 1,802 KB of a 3.38 MB export, ~half the file a researcher hands to a client, and the reason Perf's export-size gate has been red since 21 Aug. Adding a language taxed every exported report ever produced. **Fixed in 0.28.0** — the export embeds one language, and the measured file went 3.38 → 1.55 MB; `docs/design-export-locale.md` is `status: shipped`. The 192-file measurement above is the 23 Aug baseline, kept because it is what the fix was sized against.
  - **Run `.venv/bin/python scripts/check-locales.py` after seeding** — it needs no edit for a new language (it iterates whatever dirs exist) and is the gate that reads the seeded *content*, not just the enrolment lists. It flattens every `en/<ns>.json` key and diffs against each locale, honouring the runtime fallback chain and CLDR plural suffixes. **Errors** (exit 1): invalid JSON, placeholder mismatch (`{{var}}` sets must match en — plural forms only have to stay within the en group's union), and a ru/uk `_one` that omits `{{count}}` when `_other` carries it. **Warnings** (exit 0 unless `--strict`): genuine missing keys, orphan keys, empty values. So a green run does **not** mean the locale is complete — read the `missing key(s)` warnings, they're the drift list. Also runs in CI on any `bristlenose/locales/**` change (`.github/workflows/i18n-check.yml`), **and has been `--strict` there since 3 Sep 2026** (`8cae1527`) — so a missing key turns that job red instead of printing a warning nobody reads. Note it is not in the branch-protection required set, and that set is itself broken (`docs/testing/gaps.md` G9), so red does not stop a push on trunk; the value is that the signal exists and is honest. `flatten()` drops `_comment_*` pseudo-keys (the locale files' stand-in for JSON comments), so a note lives in `en` alone instead of being demanded from all 21 — added 21 Aug 2026 after one had been duplicated into 20 files. The tree went warning-free on 21 Aug 2026, which is what made `--strict` free to take; it was taken on 3 Sep. Decision 2 in `docs/i18n-defects.md` is **closed** — do not re-open it as an available promotion.
  - Register Apple-HIG + QDA terms for the language in `bristlenose/locales/glossary.csv` so Weblate shows translators the agreed taxonomy. Translate in the language's **Apple-HIG register** (imperative for buttons/commands, impersonal for body text — match the platform, don't invent a register). If `pluralCategory` in `I18n.swift` doesn't handle the language explicitly, it falls through to the `one`/`other` default (correct for it/es/de; check CLDR for others).
- **Platform text forking** — `dt(t, key)` checks `desktop:` namespace first (falls back to base key). `ct(t, key)` returns `null` on desktop (hides CLI-only text). Both in `frontend/src/utils/platformTranslation.ts`. See `docs/platform-text-map.md`
- **SwiftUI `CommandMenu` titles CAN use runtime strings** — corrected 21 Sep 2026. `CommandMenu(LocalizedStringKey(i18n.t(key)))` renders the translated value, because a `LocalizedStringKey` built from a runtime string falls back to its own content when the bundle lookup misses, and this bundle ships no `Localizable.strings`. Project / Codes / Quotes / Video follow the locale; **Diagnostics stays English** (App-Store-hidden chrome). The idiom interprets **markdown and `%`**, so menu titles must stay plain nouns — pinned by `tests/test_menu_title_keys.py`, which also pins the four keys as *read* (they are Swift string literals, invisible to every other gate). **File / Edit / View / Window / Help are AppKit's, not ours**, and they follow the locale **at HEAD but not in 0.30.0**: `knownRegions` plus 22 `.lproj` landed 21 Sep 2026 (`b9ba08f2`, 17:15), eleven hours after that release's archive was cut. Measured 22 Sep — the main bundle's declared localisations gate every other bundle in the process, AppKit's included, and each `.lproj` holds nothing but a comment, so the declaration is the whole payload. The `.lproj` set is a **23rd-language registration site that `docs/adding-a-language.md` does not list and no test gates** — `docs/design-i18n.md` §"The *standard* menus are a different mechanism" and `docs/design-locale-negotiation.md` §5
- **The pipeline-view CLI keeps its own English mirror of the pipeline reason/note strings.** `bristlenose/pipeline_view/cli.py` is i18n-free because it is terminal chrome, which is English by design (`docs/design-i18n.md` §"Which surfaces are targets"), so it hardcodes `_REASON_TEXT` / `_NOTE_TEXT` dicts keyed by the *same* locale keys the JSON uses. **Those keys live in the `settings` namespace — `settings.pipeline.reasons.*` / `settings.pipeline.quality.*` — not `pipeline.*`**, which this line said until 21 Aug 2026 and which sends a grep to a 4-key file that has none of them. (`_PROVIDER_DISPLAY` is *not* a mirror: it is built from the provider registry at import time and cannot drift.) When you touch one of those strings, grep `cli.py` for the same key and update both. **But first read `docs/i18n-defects.md` item 5:** measured 21 Aug, 3 of 23 mirrored strings diverge, and all three are a technical name in the terminal against a plain name in the SPA (`spaCy en_core_web_lg not installed` vs `language model not installed`). That is a deliberate **register fork**, not drift — the terminal names the package, the SPA names the thing — so "keep both in sync" is the wrong instruction and no equality check should be written. Settled 21 Sep 2026 by the surface rule; `docs/i18n-defects.md` Decision 3 is closed.
- **The locale corpus carries TWO placeholder conventions, and Python's `format_map` renders the wrong one as literal braces.** `preflight` was authored for Python and spells a variable `{size}`; everything the SPA reads is i18next and spells it `{{size}}` — **249 double-brace values against 17 single-brace**, measured 22 Sep 2026. `str.format_map` reads `{{` as an *escaped literal brace*, so a Python caller reading an i18next key renders `{count} quotes` — the variable name, in braces, in a researcher's deliverable. This was latent for months rather than broken, because until the Miro board no Python caller had ever read an SPA key; `bristlenose/i18n.py`'s `_interpolate` now substitutes the i18next form first and then `format_map`s, so both work from either side. **Tell:** a rendered string containing `{` where you expected a number.
- **Server-side callers use `t_in(locale, key)`, never `set_locale` + `t`.** `set_locale` mutates a module global and clears a cache — right for the CLI (one run, one language) and wrong for a server, where two concurrent requests can want two languages and the loser silently gets the winner's. `t` is now defined in terms of `t_in`, so there is one resolver; the global is just the CLI's convenience. Same file carries `plural_in(locale, base, count)` for CLDR-pluralised keys — **don't hand-roll `f"{base}_{'one' if n == 1 else 'other'}"`**, which is wrong in fourteen of the twenty-one languages and catastrophically wrong in cs/pl/ru/uk.
- **`check-locales.py --stamp` re-pins EVERY unpinned key in the tree, not just yours.** It records the current English value for all keys missing from `bristlenose/locales/en-value-pins.json` — on 3 Oct 2026 that was 55 lines for a 2-key change, pinning other sessions' in-flight keys at whatever their English said that minute. No existing pin moved, so no drift was hidden, but it takes a decision that belongs to those keys' authors. After stamping, keep only your own lines and read the `git diff` before committing. **Do it by editing your lines in the working-tree file, never by rebuilding the file from `git show HEAD:` plus your keys** — that was this line's advice until 4 Oct 2026, and it wiped another session's uncommitted re-pins the same night (they had to re-commit them, `522f15e4`): a whole-file rewrite from HEAD is a lost-update primitive under concurrency. Take the file as it stands, put back any line `--stamp` changed that is not yours (`git diff` shows them), and leave the rest.
- **Don't round-trip locale JSON through `json.load`/`json.dump` to add a key.** The 7 `common.json` files mix literal Unicode (`…`, `—`) with `\u` escapes (mostly in non-ASCII locales). `json.dump(ensure_ascii=False)` rewrites every `\u` → literal; `ensure_ascii=True` rewrites every literal → `\u`. Either way you get a 1000-line diff for a 2-line change. Use a targeted text replace (find an anchor unique to each locale — `}\n  },\n  "feedback":` works for inserting at end of `export`) and `json.dumps(value, ensure_ascii=True)` per-value to escape only the new strings. **Repeat-pass corollary:** when a second pass replaces a value inserted by an earlier pass (e.g. fixing ja `やり直す` → `取り消す`), the in-file form is the `\u` escape because the first pass used `ensure_ascii=True`. A literal Japanese match-string won't find it. Re-encode the match string via `json.dumps(..., ensure_ascii=True)` before `text.replace(...)` **Same trap on a test fixture:** `tests/fixtures/shared-format-contract.json` holds literal `—` and `…`; a `json.load` → `json.dump(ensure_ascii=True)` pass to add one case re-escaped every one of them — 33 deleted lines for a two-line change (12 Sep 2026). Text-replace on an anchor, `json.dumps` per value, then `json.loads` the result to prove it still parses.

- **The map from our locale codes to Apple's is GENERATED, never written down** — `scripts/apple-locale-map.py` probes the `.loctable` corpus and writes `scripts/apple-locale-map.json`; `tests/test_apple_locale_map.py` fails if a locale we ship has no resolvable Apple code, so it is a registration site a new language cannot skip (`docs/adding-a-language.md` Step 1, now five places). It exists because the map *was* prose, in `desktop/CLAUDE.md` and the i18n-review agent, and `pt-BR`→`pt` was wrong there for months **without ever failing**. Apple's codes are underscored and territory-based (`pt_BR`, `pt_PT`, `zh_TW`, `zh_HK`, and Norwegian is `no`) — the once-documented belief that "Apple uses the hyphen form; we match" is false in both directions. **Existence is not the test; coverage is:** `nb`, `zh-Hant` and `pt-PT` all exist verbatim as Apple codes carrying **~75 keys** against ~211,000 for the correct alias, so a naive lookup resolves to a real table, returns nothing, and reads as *"Apple ships no translation here"* — a clean audit. Bare `pt` is the same shape: Brazilian in Apple's legacy spelling (454 tables to `pt_BR`'s 2,589, never both in one file), which hid **91 of the 264** English strings Apple answers in Brazilian Portuguese. **Counting caveat:** a framework's Resources dir is reachable twice, so `find -L` says 10,448 where **3,275** distinct files exist — don't follow symlinks. Full record: `.claude/agents/i18n-review.md` §6c
- **CJK punctuation is SETTLED — measure the platform, don't reason from a style guide.** Japanese labels take a **halfwidth** `:` + space (`名前:` is Apple's own Save dialog); Japanese prose lead-ins `注：` / `例：` take **fullwidth**, no space; Chinese takes fullwidth throughout. Measured: Apple ja 431 halfwidth vs 2 fullwidth, Microsoft ja 38,041 vs 88, Apple zh-Hant 239 fullwidth vs 0. The JTF translation-industry guide says fullwidth for Japanese and is the wrong authority for macOS chrome — both vendors treat `:` as an international symbol, not Japanese 約物. A sweep on 20 Aug 2026 got this backwards in both directions and was reverted (`4bd85ff4`). Details + reproduce command: `.claude/agents/i18n-review.md` §6a.
See `docs/design-i18n.md` for implementation gotchas (Apple glossary cross-check, `useMemo` deps, sentiment tag translation, Intl.DateTimeFormat quirks, Korean plurals, data vs chrome translation, German typographic quote JSON escaping, test mocking requirements). **For a whole new language, `docs/adding-a-language.md` is the canonical step-by-step** — the summary above is a lossy index over it and has drifted before (it undercounted the registration sites while that guide's Step 8 was correct, 3 Aug 2026). When the two disagree, **reconcile them and record which won** — read both, fix both, and say in the commit which was right and why. There is no precedence rule: "trust the guide" was one, and row 47 falsified it (the guide had no concept of a thin override fork in either language-addition step, while the summary carried the exception, so following it would have propagated the defect into the next fork).

### A file-wide regex over locale JSON deletes same-named keys in other namespaces

Pruning a retired key with `re.sub(r'^\s*"undo":\s*.*?,\s*\n', "", s, flags=re.M)`
across a whole `desktop.json` also deletes `menu.edit.undo` — same key name, different
namespace, and the pattern has no idea which block it is in. Done 19 Aug 2026 while
removing `toast.undo`; it took `menu.edit.undo` ("Undo") out of all 21 locales, and the
Edit-menu fallback label with it. `check-locales.py` stayed **green**, because English
lost the key too and the gate diffs each locale *against English* (the blind spot the
i18n section above already documents from the other direction).

Two more traps in the same family, both hit in that pass: a key that is **last in its
block has no trailing comma**, so a `,\s*\n`-anchored pattern silently skips it (the
prune "succeeded" and the key was still there); and removing the last key of a block
leaves `"toast": {}`, which is valid JSON and invisible to every gate.

**Rule: scope the prune to the block.** Parse, locate the namespace, and rewrite only
within it — or match the fully-qualified path, never the bare key name. Verify with
`git diff` on one locale and read every `-` line before repeating across 21;
`json.load` + key-list comparison before/after is the cheap check that catches all
three.

**And scoping to the block is not enough if the namespace name repeats.**
`en/common.json` carries two `"codebook"` blocks — a nested prose/methodology one
(`sectionsTitle`/`sectionsBody`/`themesBody`) and the real top-level namespace, the one
that holds `codebook.frameworks`. A first-match `^\s*"codebook"\s*:\s*\{` plus
brace-matching selects the *prose* block, and the key you came for simply isn't in it
(measured 21 Aug 2026). How that fails depends on the tool: assert "exactly one match
inside the block" and it fails loudly; reach for a bare `re.sub` and it changes nothing,
reports success, and joins the silent-no-op family above. **Select the block by
*content* — the one that actually carries the key, asserted unique — or by
fully-qualified path, never by first match on the name.**

## macOS app, Xcode, signing and sandbox

### Only Mach-O EXECUTABLES carry entitlements — bundles and dylibs never do

The `.app` holds ~227 Mach-Os but only **4 are executables** (the host, ffmpeg,
ffprobe, the sidecar). The rest are Python `.so` extension **bundles** and
**dylibs**, which carry no entitlements at all — they inherit from the loading
process. So `find -perm -111` plus "assert app-sandbox" reports **223 of 227
missing it** against a correctly-signed, ASC-accepted package. Filter on
`file -b "$b" | grep -qE 'Mach-O.*executable'`, never bare `Mach-O`.

Those 4 are exactly the set the 14 Jul 2026 nested-signing rejections were about,
so the gate is worth having — but a gate that cries wolf gets switched off, which
is worse than no gate. `desktop/scripts/check-pkg-shippable.sh` has the working
form with the reasoning inline.

**Release-channel mechanics** (five channels, their triggers, and the two
different expiry clocks — `.dmg` 30 days from the *build*, TestFlight 90 from the
*upload*) are mapped in `docs/release-channels.md`. The measured `altool`
contract — including that `--list-providers` refuses API-key auth while
`--list-apps` accepts it, and that `--show-progress` must be TTY-gated or it
bloats a log 12,000× — is in `docs/design-testflight-upload.md` § Observed
contract. Don't re-derive either.

### An unsigned `.xctest` in shared DerivedData fails the APP's signing, and deleting the bundle does not fix it

`desktop/scripts/test-swift.sh` refuses with `BUILD FAILED (xcodebuild exit 65)`
and, several hundred lines up the log:

```
…/Bristlenose.app: code object is not signed at all
In subcomponent: …/Bristlenose.app/Contents/PlugIns/BristlenoseTests.xctest
```

The message blames the **app**, and the fix is in the **test target**. Xcode's
incremental build decided the `.xctest` was up to date and emitted **no `CodeSign`
step for it at all** — grep the log for `CodeSign .*xctest` and find nothing —
so the parent's signing then refuses an unsigned subcomponent. This is release
incident #1 of 0.30.0 (`docs/release-premortem.md`), recorded there without a
remedy; here is the remedy.

**Deleting the `.xctest` is NOT enough.** It rebuilds from cached intermediates
and comes back unsigned, which reads as a genuine signing failure rather than a
cache one — that is the second cycle you lose. Invalidate **both**:

```bash
DD=~/Library/Developer/Xcode/DerivedData/Bristlenose-<hash>/Build
rm -rf "$DD/Intermediates.noindex/Bristlenose.build/Debug/BristlenoseTests.build" \
       "$DD/Products/Debug/Bristlenose.app/Contents/PlugIns"
```

**And if the rebuild comes back unsigned again, clear Xcode's cached build
description too** — `rm -rf "$DD/Intermediates.noindex/XCBuildData"` with the two
paths above. On 26 Sep 2026, after the test target's floor changed, deleting the two
directories alone produced a second unsigned `.xctest` with no `CodeSign` step; only
dropping `XCBuildData` made Xcode re-plan and sign it (1525 passed). Check nothing
else is building first: another session's build reads the same description.

**Tell that this is what you are in, and not a real break: the same source builds
and tests clean against a fresh `-derivedDataPath`.** That is also the workaround
when another session is using the shared DerivedData and you would rather not
touch it — the isolated-worktree recipe in `desktop/CLAUDE.md` already passes
one. Cost three build cycles on 22 Sep 2026, two of them spent looking for a
Swift defect that was never there.

### "Is this Swift file in the Xcode project?" is not a question `project.pbxproj` can answer

`Bristlenose.xcodeproj` uses **`PBXFileSystemSynchronizedRootGroup`** (Xcode 16+),
which references the *folder*, not the files. Membership is by living on disk
under `Bristlenose/` or `BristlenoseTests/` — so no individual `.swift` filename
appears in `project.pbxproj` at all, and the obvious audit

```
grep -q "$(basename "$f")" project.pbxproj || echo "MISSING FROM PROJECT: $f"
```

reports **every** Swift file as missing. On 21 Aug 2026 that was 250 files,
printed as a wall of `MISSING FROM PROJECT:` against a project that builds
clean — alarming, entirely false, and it cost a cycle to disbelieve.

The check the grep was reaching for is real but different: a file can be
*written and never committed*, which is how `main` stopped building on 18 Aug
(`c837f8b5` — `CloudPlatform.swift:52` read a flag whose file was untracked).
**Ask git, not the pbxproj:** `git status --porcelain -- 'desktop/**/*.swift'`.
An untracked `.swift` is the actual failure mode; an unlisted one is the norm.

Tell that you are in this trap: the "missing" list is *all* of them, or the
count matches `ls desktop/Bristlenose/Bristlenose/*.swift | wc -l`. Confirm with
`grep -c PBXFileSystemSynchronizedRootGroup project.pbxproj` — non-zero means
filenames were never going to be in there.

**Nor can it answer "what is the deployment target?" — and that one fails
*plausibly*.** The file holds several `XCBuildConfiguration` blocks; which one a
scheme resolves to is decided by the build system, not by reading order. The
project carried **two** floors until 25 Sep 2026 — production at
`MACOSX_DEPLOYMENT_TARGET = 15.0` on all four app schemes, and `BristlenoseTests` at
26.1 — and both are now 15.0 (`docs/design-platform-policy.md` §"Pillar 3"; pinned by
`desktop/scripts/check-deployment-floors.sh`). The trap outlives the gap: any build
setting a test target overrides can be misread the same way.
Hand-parsing therefore returns a real number that is nonetheless the wrong one for
the scheme you meant, with nothing to signal the error.

On 3 Sep 2026 three successive parses of that file gave three different answers —
first 15.0, then "26.1 everywhere", then a contradiction — and **two of them reached
a committed doc** before `xcodebuild` settled it. The same pass also reported
`SWIFT_APPROACHABLE_CONCURRENCY = YES` when the resolved value is `NO`.

**Ask the build system, and name the scheme:**

```
xcodebuild -showBuildSettings -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -target Bristlenose -configuration Release | grep -E 'SWIFT_|DEPLOYMENT'
```

Tell that you are in this trap: two different values for the same setting, and a
story forming about which is "stale". Both are probably live. Policy already
flags the underlying hazard as unfixed — Pillar 3 carries an open action to add a
comment block to the pbxproj naming which scheme uses which target, precisely
because it is "easy to bump one without the other".

**Nor can the `.entitlements` file answer "is this build sandboxed?" — and it
answers *no* when the truth is yes.** `BristlenoseDebug.entitlements` contains
exactly one key, `keychain-access-groups`. There is no `com.apple.security.app-sandbox`
in it, and `grep -l app-sandbox desktop/**/*.entitlements` matches nothing — so
reading the file, or grepping for the entitlement, concludes the Debug build runs
unsandboxed. It does not: the sandbox comes from **`ENABLE_APP_SANDBOX = YES` as a
build setting**, which Xcode 15+ merges into the synthesised entitlements at sign
time. The file is a *supplement*, not the manifest.

Cost two silent write failures on 3 Sep 2026 while measuring Settings pane
heights: a test writing to `~/Documents` and then to `/private/tmp/...` produced
no file and no error either time (`try?` swallowing a sandbox denial that the
tree said could not happen), and the payload only landed once it was pointed at
`NSTemporaryDirectory()` — i.e. `~/Library/Containers/app.bristlenose/Data/tmp/`.
**Same fix as the paragraph above:** ask the build system, name the scheme.

```
xcodebuild -showBuildSettings -project desktop/Bristlenose/Bristlenose.xcodeproj \
  -target Bristlenose -configuration Debug | grep -E 'ENABLE_APP_SANDBOX|ENABLE_HARDENED'
```

Tell that you are in this trap: a file write that neither succeeds nor raises, on
a path the entitlements file says nothing forbids.

### `Bundle.preferredLocalizations(from:forPreferences: nil)` LATCHES on its first call

Passing `nil` does not mean "read the user's languages now" — CoreFoundation
resolves the preference list on the **first call anywhere in the process** and
caches it for the process lifetime. `Locale.preferredLanguages` and
`CFPreferencesCopyValue` both stay live; only the `nil` form freezes.

**And the cache is primed before any of our code runs**, because AppKit resolves
the main bundle's localisations during `NSApplicationMain`. Measured 22 Sep 2026
with a bundled probe: write `AppleLanguages` then read → fresh; read
`Bundle.main.preferredLocalizations` first, then write, then read → **stale**.
So a migration cannot read back what it just wrote, no matter how early it runs,
and a "live" resolver answers with the launch-time language for the rest of the
session.

**Fix: pass the list explicitly** — `forPreferences: Locale.preferredLanguages`.
Measured live through `ja`, `pt-BR`, `zh-Hant-HK`, `nn-NO`→`nb`, and back to `en`
on clear. `I18n.systemPreferredLocale` carries the reasoning inline.

**Tell:** a language change that updates the chrome and not the report, or a
value that reads back as its pre-write self in the same process. **The related
trap:** `UserDefaults.standard.array(forKey: "AppleLanguages")` searches the
global domain too, so it cannot distinguish "this app has an override" from
"inheriting the system list" — use `CFPreferencesCopyValue(…,
kCFPreferencesCurrentApplication, kCFPreferencesCurrentUser,
kCFPreferencesAnyHost)`, which reads the app domain alone. That distinction is
what stops a write-back reverting a language the user set in System Settings.

**Sibling, same family:** `@AppStorage("k") = "default"` is a **Swift-side
fallback, not a registered default**. The key stays absent until something
writes it, so a view bound to it displays the literal while the rest of the app
resolves something else — the Settings picker read "English" on a fresh install
whose Mac was German, and selecting the row it showed would have *written* the
key and switched the app. Seed such a control from the real resolver as `@State`;
do **not** seed the key, because its absence is usually what carries the
follow-the-system behaviour.

- **Xcode subprocess leakage → `[forkpty: Device not configured]` / `[Could not create a new process and open a pseudo-tty.]` in Terminal.app.** Symptom: Terminal.app refuses to open new windows with the forkpty dialog; Nova/iTerm2 crash on opening local terminals; new shell processes can't spawn. Cause: per-user process limit (`sysctl kern.maxprocperuid`, typically 1064–2128) hit by leaking subprocesses. **Xcode is the usual culprit** — SourceKitService, swift-frontend, lldb-rpc-server, dispatch helpers, indexing workers accumulate, especially across multiple worktrees or when indexing wedges. Diagnose via Activity Monitor → sort by Process Name → look for one app with 100+ entries (often `claude` workers post-`/usual-suspects`, often Xcode helpers, often both). **Fix:** quit Xcode (not always full reboot needed); if Activity Monitor reveals leaked headless `claude` workers, bulk-Force-Quit them. `killall SourceKitService` respawns clean and is gentler than restarting Xcode. Re-baseline: `ps -u "$USER" \| wc -l` should be < 500 on idle.
- **Transitive bare-name shellouts from PyPI deps break under macOS App Sandbox.** `bundled_binary_path("ffmpeg")` only helps callers we control — but PyPI deps like `mlx_whisper.audio.load_audio` shell out to bare `"ffmpeg"` via `subprocess.run(["ffmpeg", …])`, bypassing our helper. Under the sandbox the inherited PATH excludes Homebrew, so the bare lookup fails with `[Errno 2] No such file or directory: 'ffmpeg'` and transcription silently produces empty transcripts. Fix: `prepend_bundled_to_path()` in `bristlenose/utils/bundled_binary.py` is called from `bristlenose/__init__.py` before any submodule loads. No-op outside the bundle. Same fix transparently covers `faster_whisper` and any other transitive bare-name shellout. **When adding a new PyPI dep that processes media files, audit it for bare-name shellouts** — `grep -r 'subprocess.*\["ffmpeg"\|"sox"\|"mediainfo"' .venv/lib/python*/site-packages/<dep>` will catch the common ones. The PATH-prepend already handles ffmpeg/ffprobe; for other binaries you'd need to add them to the bundle datas list and extend `bundled_binaries_dir()`.
- **Python 3.12+ `mimetypes.init([])` doesn't skip system files.** Intuition says "pass empty list = skip system walk." Wrong. CPython 3.12.13 `mimetypes.py:378` does `files = knownfiles + list(files)` when `files` is non-None — so `init([])` reads `knownfiles + []` = the full system list. Under macOS App Sandbox those reads raise `PermissionError`, which `init()` doesn't catch — `mimetypes._db` stays poisoned and every subsequent `guess_type()` raises, surfacing as HTTP 500 on `/static/*.js`. The reliable escape hatch is `mimetypes.knownfiles = []` *before* any init (lazy or explicit) fires. Done in `bristlenose/__init__.py:8-22` so it lands before any submodule import. See `docs/design-desktop-asset-serving.md` "Shipped upstream fix" subsection
- **Status-bar `-dirty` ≠ source dirty.** `desktop/Bristlenose/Bristlenose/GeneratedBuildInfo.swift` is regenerated every Xcode compile, so `git describe`-style status strings show `<sha>-dirty` even on a clean source tree. Don't use the `-dirty` suffix as evidence of "build is from uncommitted source"; check `git status --porcelain | grep -v GeneratedBuildInfo` if you need to know whether the bundle reflects committed code
- **QA-ing a *frontend/CSS* change in the bundled `.app`: the JS half is now automatic, the CSS half still isn't.** The bundled `.app` (`sidecar=bundled` in the footer = prod serve, not `--dev`) gets the SPA from two baked sources. (1) **JS — automatic since 29 Jun 2026.** `desktop/scripts/build-sidecar.sh` now runs `npm run build` itself before bundling (and the sidecar source-fingerprint covers `frontend/src` + `bristlenose/locales`, so the Xcode "Copy Sidecar Resources" freshness gate, `check-sidecar-freshness.sh`, **fails loudly** if the bundle predates a frontend edit). So you no longer hand-run `npm run build` for the `.app` — just rebuild the sidecar (`desktop/scripts/build-sidecar.sh` [+ `sign-sidecar.sh` + clean build]) and the React bundle inside `…/bristlenose-sidecar/_internal/bristlenose/server/static/` is current. This also closes the `/new-branch --from-cloud` trap (it `ditto`s **main's** sidecar in; the next sidecar build now rebuilds the worktree's frontend and re-stamps, so the gate flags the stale ditto'd bundle until you do). The PostToolUse hook `frontend-stale-reminder.sh` nudges after any frontend/locale edit. (2) **CSS — fixed 17 Oct 2026; the rest of this paragraph is the history.** `serve_theme_css` and the HTML export now always use the running version's theme (`get_default_css` / `load_default_css`), never the baked copy, pinned by `test_baked_theme_css_is_not_served`; the four palettes added that day matched nothing in the app on every analysed project until then. _Was:_ **CSS — still manual.** `bristlenose/theme/organisms/sidebar.css` is **not** in the Vite output; it's served as `/report/assets/bristlenose-theme.css`, which in prod (`serve_theme_css_with_fallback`, `app.py`) *prefers the per-project baked copy* `<output_dir>/assets/bristlenose-theme.css` and only falls back to the bundled source when the project has none. So an already-rendered project serves its **stale** baked CSS even after a correct sidecar rebuild. Fix: test against a **freshly-imported** project (no baked copy → fallback serves the rebuilt source) or regenerate the baked file — `.venv/bin/python -c "from bristlenose.stages.s12_render.theme_assets import load_default_css; open('<proj>/bristlenose-output/assets/bristlenose-theme.css','w').write(load_default_css())"` run from the **worktree venv** (reads branch source). Dev mode (`serve --dev` + `?embedded` for embedded-only features) sidesteps both — live JS from Vite, live CSS from source — but it's a browser, not the WKWebView; for a feature whose whole point is the native context, the `.app` pass is the real acceptance test

## Release, CI and packaging

- **A dependency's minor bump can start phoning home, and its `disable_*()` API may not be the off switch.** onnxruntime 1.29 began 1DS telemetry on macOS and Linux — a persistent device id, a queue under `~/Library/Application Support/Microsoft/DeveloperTools/.onnxruntime`, uploads to Microsoft — and its uploader SIGABRTs Python at exit (`std::system_error` from `recursive_mutex::lock` in a crash report naming `Microsoft::Applications::Events`). `onnxruntime.disable_telemetry_events()` was measured and still queued events and started the uploader; only `ORT_DISABLE_TELEMETRY`, set before the first session, latches it off — now in `bristlenose/__init__.py`, pinned by `tests/test_onnxruntime_telemetry.py`. **When a native dep moves, `strings` its `.so` for a collector URL** (`events.data.microsoft.com`, `/collect`, `telemetry`), and prove an opt-out by watching the queue on disk, not by trusting the API's name. CI hides this class: onnxruntime suppresses itself when `CI` is set (5 Oct 2026)
- **A release pushes `main` and dispatches strict CI, so ONE commit gets TWO `ci.yml` runs, and they can disagree.** `release.sh`'s ci-green reads only the `workflow_dispatch` run; the `push` run beside it is not the gate. On 0.36.0 the push run at the tagged commit was red on Windows while the dispatched run was green, and reading `gh run list --limit 1` (which returned the push run) nearly called a passed gate failed. Select by event: `gh run list --workflow=ci.yml --json event,headSha,conclusion`. The red push run still matters, as a flake the tag's own PyPI CI can hit; that one was xdist workers sharing the committed smoke fixture's log file, fixed in `tests/conftest.py` (`no_log_file_in_committed_fixtures`). **Sibling, same night:** a test that picks what is installed by stubbing `shutil.which` stops working the moment production gains its own resolver; on Windows `safe_which` walks PATH itself, so 20 tests read the runner's Chocolatey ffmpeg (`which_is_shutil_which` fixture). When you add a resolver, grep the tests for stubs of the thing it replaced.
- **The sidecar is built from `.venv-sidecar`, NOT `.venv` — so `.venv` is the wrong control for any bundle question.** `build-sidecar.sh` (`SIDECAR_EXTRAS`) uses a dedicated venv carrying only `.[serve,apple,desktop,mcp,voice]` (voice since 4 Oct 2026), and its contents genuinely differ: on 30 Aug 2026 `.venv` held numba 0.66.0 / llvmlite 0.48.0 / mlx 0.32.0 while `.venv-sidecar` held 0.67.0 / 0.49.0 / 0.32.2. Nothing pins that stack, so **any `pyproject.toml` edit invalidates the deps fingerprint (`_deps_fingerprint`: the extras list, `shasum pyproject.toml` and `pip freeze`), recreates the venv from scratch, and re-resolves every transitive dependency to whatever is newest** — a pin on `anthropic` moved numba two minors sideways three days later. The trap when debugging: "it works fine in the venv, so the library is not the problem" is a **non-comparison**, and it cost a full session on the SIGILL investigation. Reach for `.venv-sidecar/bin/python`, and read the shipped versions out of the bundle (`_internal/*.dist-info`) or out of `THIRD-PARTY-BINARIES.md`, which is regenerated from the sidecar venv (since 5 Sep 2026 — before that it read `.venv`, the wrong one, and recorded starlette 1.3.1 against a bundle carrying 1.6.0) and is the only tracked record of what actually shipped. Two caveats on the dist-info route: pure-Python packages are bytecompiled into the archive and leave **no** dist-info unless the spec `copy_metadata`s them (starlette does now), and a dist-info can be present for a package whose code is **excluded** — `presidio_analyzer-2.2.364.dist-info` sits in `_internal/` with no package directory. A dist-info proves metadata shipped, not code.
- **Auditing wheel availability by grepping `cp3XX` out of the filename is WRONG — `abi3` wheels are forward-compatible.** A wheel tagged `cp311-abi3` installs on 3.11 *and every later CPython*, so the obvious `cp3XX in filename` scan reports it missing everywhere except 3.11. Measured 3 Sep 2026 during the Python-floor audit: that check claimed `cryptography` ships **no** wheels for 3.10, 3.12 or 3.13 — it ships one covering all of them — and said the same of `tokenizers`, `psutil`, `hf-xet` and `safetensors`. The output is convincing because it looks like a finding: a column of `—NONE—` against packages that self-evidently do ship wheels. **Tell:** a package you know is universally available showing gaps on scattered, non-adjacent versions. **Fix:** parse the whole `(python, abi, platform)` tag triple — `py3-none-any` is universal, `cp3X-cp3X` is exact, `cp3X-abi3` is 3.X *and later*. Better, don't infer at all: `pip install --dry-run --report --python-version X --only-binary=:all: --platform …` answers it with the real resolver, and the result can be diffed against a CI install log to prove the model before you trust it. Same family as the `rg -rn` and zsh gotchas above — tooling that fails *quietly* and plausibly. Reusable method: `docs/design-python-floor.md` § Method.
- **A build gate that checks a file is PRESENT has not checked it is INTACT — and `codesign` will happily bless a corrupt binary.** PyInstaller shells out to `strip` per collected binary and never checks its exit status. On 30 Aug 2026 `strip` died of SIGBUS mid-`writeout` on the 128 MB `libllvmlite.dylib`, leaving a file of exactly the right size with **16 KB of zeros inside `__TEXT,__text`**; signing ran afterwards, so `codesign -v --strict` passed, `otool -L` was unchanged, and every build gate was green. On arm64 an all-zero word is `udf #0`, so the first numba JIT to reach that page raised SIGILL — every run died seconds into transcription, wrote no terminus event, and therefore **no lens would open in that project either**, which reads as an unrelated frontend bug. `strip=False` now (it saved 48 KB of a 479 MB bundle across a 14-binary sample, because wheels already ship stripped), and `desktop/scripts/check-bundle-integrity.py` fails the build on any zero-run ≥4096 bytes in executable code — ~4s over 224 Mach-Os, wired into `build-sidecar.sh` on **every** real invocation, since a bundle already corrupt when cached would otherwise be skipped forever. Full post-mortem: `docs/sidecar-transcription-crash.md`. **And that gate has a floor it cannot see under:** it scans `__TEXT,__text` for a zero-run of at least one page, because the incident left 16 KB of zeros in a 128 MB dylib — so **42 of the bundle's 224 Mach-Os, whose `__text` is smaller than a page, are unscannable by construction.** A page-sized probe on one of those stays green and reads as a mute gate; it is a gate looking somewhere else (found 4 Sep 2026 while proving it red; recorded in `docs/testing/gaps.md` G7). Don't lower `--min-run` to reach them — it would fire on legitimate padding.
- **PyInstaller bundle datas: source dir present ≠ bundle dir present.** Non-`.py` runtime files (YAML, JSON, Markdown, JS, CSS, etc.) only ship if they're in `desktop/bristlenose-sidecar.spec`'s `datas=[...]` list. Python packages get bytecompiled into `base_library.zip` automatically; data files don't. Two gates catch this class: `desktop/scripts/check-bundle-manifest.sh` (source→spec, ~60ms, runs in `build-all.sh` step 1b) and `bristlenose doctor --self-test` (spec→bundle, ~2-3s, runs in step 2a). The source→spec gate is per-file: each runtime file must be matched by a datas entry that's the file itself or a directory ancestor — so single-file `(file_path, parent_dir)` entries are accepted alongside whole-directory ones. Unit tests can't catch this — they run against `pip install -e .` where data files live at their real paths
- **A CSS class audited by substring silently matches a LONGER class — audit selectors on whole tokens.** `theme/templates/export.css` is the read-only gate for the HTML export (every rule is `.bn-export-mode <sel> {display:none}`), and it is pure CSS, so renaming a control in `frontend/src` defeats a rule with **no error** — it just stops matching, and the affordance reappears in every exported report from then on. The mechanical stop is `tests/test_export_css_selectors.py`. **Two traps it had to be built around, both of which a naive version fails.** (1) **Whole-token matching is mandatory:** `badge-accept-flash` is a live animation class, so a substring search reports the stale `.badge-accept` as *found* — the very bug the gate exists to catch would have passed it. Match `(?<![\w-])name(?![\w-])`; `-` is a class-name character, so `\b` is not enough. (2) **`frontend/src` is the whole corpus, deliberately:** `bn-export-mode` is written in exactly one place (`server/routes/export.py`, onto a body holding only `<div id="bn-app-root">` plus the single-file React bundle), so the frozen vanilla renderer in `theme/js/` never receives it and a rule naming a vanilla-only class can **never fire**. Widening the search to `bristlenose/theme/` would green-light exactly the dead rules the gate exists to catch. Five selectors were stale at once on 15 Aug 2026, three of them live leaks (`.bn-counter` → the real class is `.bn-hidden-badge`; `.codebook-add-tag` → `.tag-add-row`; `.codebook-picker-btn` → no class existed at all). **When repointing one, cross-check `templates/print.css`** — it is the sibling read-only surface, it names the same controls, and it had not drifted. **(Fixed 17 Oct 2026: the export now inlines the running version's theme, so this last trap is history.)** **And QA the result against a FRESH project:** the export inlined the *per-project baked* `<output_dir>/assets/bristlenose-theme.css` in preference to the bundled source (`routes/export.py`), so exporting from an already-rendered project embeds the OLD export.css and shows the controls still visible, with no error — same baked-CSS staleness trap as serve mode, one layer further out.
- **bristlenose.app has TWO privacy pages, and a fix to one is not a fix.** `content/privacy.html` is the legal permalink (the URL App Store Connect and third parties hold); `docs-src/privacy.md` renders to `/docs/privacy.html`. Both live in the website repo, outside this tree. The 0.29.0 changelog announced the "there is no Bristlenose server" claim corrected (website `ad98272`, 31 Aug 2026), and it was — on the docs page only; the legal page went on denying a server, in its body and its meta description, until 3 Oct. `content/terms.html` made the same claim twice. **Any change to what leaves the machine is an edit to all three**, and the check is to fetch each live page, not to read the commit. Tell: two pages answering the same question differently.
- **Homebrew tap repo must be named `homebrew-bristlenose`** (not `bristlenose-homebrew`). See `docs/design-homebrew-packaging.md`
- **Homebrew formula uses `post_install` pip to avoid dylib relinking failures.** See `docs/design-homebrew-packaging.md`
- **Anything installed in brew `post_install` skips the auto-link phase.** Homebrew runs `def install` → link phase → `def post_install`. Files placed in the Cellar by `post_install` (pip-installed scripts, generated configs, man pages from wheel data scheme) land *after* link has run, so brew never symlinks them into `/opt/homebrew/bin/`, `/opt/homebrew/share/man/`, etc. Symptom seen: pip's wheel-data scheme placed `bristlenose.1` at `<cellar>/share/man/man1/` during `post_install`, but `man bristlenose` silently didn't resolve because the auto-link symlink was never created. **Fix pattern:** install the file in `def install` from a stable path. The sdist source is unpacked into `buildpath` before `def install`, so `man1.install "bristlenose/data/bristlenose.1"` (canonical path inside the package) works — `man/bristlenose.1` is a symlink to the same file. Install in `def install`, not `post_install`, for anything that needs auto-linking
- **Homebrew 6.0 tap trust: `brew install` works, bare `brew upgrade` silently skips us.** Since 6.0 (11 Jun 2026) non-official taps must be trusted before their Ruby is evaluated, and the gate is **ARGV-based** (`explicitly_allowed?` in Homebrew's `trust.rb`): a tap is allowed only when its name appears in the typed command. So `brew install cassiocassio/bristlenose/bristlenose` still works (fully-qualified name is in ARGV, self-trusts for that invocation, auto-taps a clean machine) — but bare `brew upgrade` never names us, drops the formula from the plan, and emits an `opoo` **warning, not an error**. `brew outdated` likewise omits us. Net effect: an existing install goes stale indefinitely with nothing a user would notice. Mitigations, all shipped: the tap formula's `caveats` prints the trust command on every fresh install; README / INSTALL / the website install + welcome pages carry it; `bristlenose doctor`'s `check_brew_tap_trust` catches installs that predate the change — and note it gates on the **Cellar keg path**, deliberately *not* `doctor_fixes.detect_install_method()`, which returns `"brew"` for any `sys.executable` under a Homebrew prefix and so also matches `pip install` into a Homebrew *Python*; reuse the loose detector for phrasing a fix message, never for deciding whether the brew *formula* is installed (pinned by `test_pip_into_homebrew_python_skips`). **Don't** reach for `HOMEBREW_NO_REQUIRE_TAP_TRUST=1` — documented as a temporary opt-out slated for removal. Note trust from a qualified install is per-invocation and **not** persisted (nothing written to `trust.json`); only an explicit `brew trust` persists, and the on-disk key is `trustedformulae` while `brew trust --json=v1` normalises it to `formulae` — read the JSON, don't parse the file. **Two corollaries that bit us in the same audit:** (1) **never print a short-name brew command for our own formula** — `brew upgrade bristlenose` is *refused* when the tap is untrusted, i.e. it fails for exactly the users being told to run it; always the fully-qualified `brew upgrade cassiocassio/bristlenose/bristlenose` (pinned by `test_serve_deps_missing_brew`). (2) **Programmatic `brew install` shellouts need `env={**os.environ, "HOMEBREW_NO_ASK": "1"}`** — 6.0's ask mode prompts whenever the plan pulls in dependencies, and both our shellouts (`preflight/ffmpeg.py`, `ollama.py`) run *after* our own Confirm prompt on a TTY, so without it the user confirms one decision twice. Full failure mode: `docs/design-homebrew-packaging.md` §Known tradeoffs
- **Release-to-PyPI workflow doesn't always fire on tag push via `--tags`** — `git push origin main --tags` triggers the branch-push workflows (CI, CodeQL, Snap) but the tag-driven `Release to PyPI` workflow can silently miss the event. Workaround: `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` — same SHA, fresh trigger, semantic no-op. Root cause appears to be GitHub Actions debouncing tag-push events bundled with branch-push events. Future fix: add `workflow_dispatch:` to `release.yml` so it can be re-triggered without tag surgery
- **A failed release run and a release run that never fired need different fixes — don't reach for the tag-redelivery workaround reflexively.** Two distinct failure modes: (1) the workflow *never fired* (debounce) → the `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` redelivery above. (2) the workflow *fired and a job failed* (e.g. e2e stalled on the Playwright browser CDN) → NOT a redelivery case. Critically, **`gh run rerun <id> --failed` replays the *tagged commit*, not `main`'s latest** — so if a later commit on `main` already fixed the failing step, re-running the old run just fails again on the unfixed code. The fix is to move the tag to the fixed commit (`git tag -f v<X.Y.Z> <fixed-sha> && git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`), which triggers a fresh run on the fix. Diagnose first with `gh run view <id>` (did it fire? which job failed?) before choosing. Worked example 4 Jun 2026: v0.15.13's run failed on the e2e Playwright-browser CDN stall; a `--failed` rerun of the stale-commit run failed identically, while moving the tag to `14af414` (which bumped `@playwright/test` 1.59.1→1.60.0 to fix the chromium-install hang on Node 24) published cleanly. Ground truth is always `curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version`, not the run's conclusion
- **Test-only fixes re-use the existing tag; they don't bump the version** — when a fix touches only `tests/`, `e2e/`, fixtures, `CLAUDE.md`, `docs/`, `.claude/` agent tooling, `.github/`, or workflow files (anything excluded from the sdist/wheel — the wheel ships only `bristlenose/` per `[tool.hatch.build.targets.wheel] packages`, and the sdist `exclude`s `.claude/`), the shipped wheel is byte-identical with or without the fix. This covers whole *features* that live outside `bristlenose/` (e.g. the Cassandra agent + `/cassandra` skill + dependency register, 5 Jun 2026) — "new in the repo" ≠ "new in the package"; the version labels the PyPI/Homebrew/Snap artifact, not git state. Re-use the existing tag by force-moving it to the fix-merge SHA (`git tag -f v<X.Y.Z> <merge-sha>`) and re-pushing (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`). Don't bump to <X.Y.Z+1> — adds bookkeeping (CHANGELOG entry, README snippet, homebrew tap dispatch) for no semantic gain and forks the version line for cosmetic reasons. Counter-rule: PyPI immutability — if the version ever successfully published, you can't re-upload, and a bump IS required. Verify with `curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version` before deciding
