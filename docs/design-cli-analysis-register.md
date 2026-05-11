# CLI-UX Analysis Output: Register, Audience, Voice

**Phase 1 of 2** — the codebook + analysis register. The asciinema
session-matching work is Phase 2, deferred until after this lands and
gets cohort feedback. See `docs/design-cli-session-matching.md`.

**Status:** Companion to `bristlenose/server/codebook/cli-ux.yaml`.
Shippable as soon as the cli-ux codebook has run against a real
session and we can A/B the prompt variants.

## Who is reading this report?

The reader of a CLI-tool research report is rarely a classically-
trained UX researcher. It is usually:

- An **API designer** or **DX engineer** on the team that maintains
  the tool, taking the report to inform the next release.
- An **OSS maintainer** who built the tool and wants to know which
  bits of the surface are tripping people.
- A **PM or tech lead** scoping the next quarter of work.

These people share a set of biases worth naming:

- They have not read Nielsen, Norman, Krug, or Garrett. If they
  have, they think those authors wrote about GUI design and have
  nothing to say to API or CLI work. They would rather not be
  told otherwise mid-report.
- They speak fluently about *API surface*, *ergonomics*,
  *footguns*, *composability*, *idempotency*, *breaking changes*,
  *deprecation paths*, *semver*, *backwards compatibility*. They
  speak haltingly (or with disdain) about *information
  architecture*, *cognitive load*, *mental models*, *affordances*.
- They want **evidence, not opinion**. A finding that quotes a
  participant verbatim and counts how many other participants hit
  the same wall reads as data. A finding that summarises five
  participants as "experiencing friction in the documentation
  pathway" reads as fluff.
- They reach for **comparisons to tools they already know**
  (`git`, `kubectl`, `gh`, `brew`, `apt`, `snap`, `docker`,
  `terraform`) as the fastest way to anchor an unfamiliar
  observation. The report should anchor itself the same way when
  the evidence allows.

This is the audience the CLI-UX codebook earns its keep with — and
the audience whose register the analysis output must match. It is
not the audience the rest of Bristlenose was built for. That gap is
the design problem.

## Register rules

These are the rules a Bristlenose report on a CLI study should
follow when emitted to this audience. They apply to LLM-generated
theme summaries, friction descriptions, and dashboard copy.

1. **No discipline names, no framework citations.** Don't say
   "Nielsen's heuristics," "Norman's gulf of execution," "Garrett's
   five planes," or anything that sounds like it came from a UX
   textbook. The tags from `cli-ux.yaml` are the only vocabulary
   the report needs.
2. **Quote the artifact verbatim.** Commands, flags, error
   messages, output excerpts, prompt strings — all in
   `monospace`, never paraphrased. If the participant typed `git
   push --force-with-lease`, the report says that, not "a
   force-push variant." If the error was `error: pathspec 'foo'
   did not match any file(s) known to git`, the report quotes
   that string, not "an error about the pathspec."
3. **Counts before prose.** Whenever the evidence supports it,
   lead with the count: "5 of 6 participants reached for
   `--help` before `man`," not "most participants preferred
   --help." Engineers read tables; they tolerate prose; they
   skim narrative.
4. **Engineering vocabulary, not UX vocabulary.** Prefer the word
   the reader would reach for. *Surface* over *interface*.
   *Ergonomics* over *usability*. *Footgun* over *risk of error*.
   *Composability* over *combinability*. *Discoverability* is
   borderline — engineers do use the word in API design, so it's
   fine. *Mental model* is borderline — used widely enough in
   engineering blogs that it's tolerable, but only with concrete
   anchor ("the participant's mental model of `kubectl` is
   verb-first, but the tool wants noun-first").
5. **Comparisons to known tools when the evidence allows.** If
   participants explicitly compared the tool under study to
   `git`, `kubectl`, `gh`, `brew`, etc., surface that. If the
   inference comes from the codebook (e.g. verb-noun mismatch
   patterns mirroring a different tool's), tie it to the named
   tool rather than to an abstract pattern.
6. **Findings as actionable engineering work where possible.** A
   strong finding should be reproducible and fileable. The
   report's "high-confidence" findings emit a bug-report stub —
   title, reproduction (the actual commands), the verbatim
   error, the participant count. Not "we recommend better
   discoverability" but "consider replacing the bare-`tool`
   usage stub with a `tool quickstart` subcommand; 4 of 5
   participants typed the bare command expecting onboarding."
7. **Voice: terse, declarative, no hedging.** "Three of five
   participants typed `juju add-unit foo` and got `no such
   command`." Not "Some participants seemed to encounter
   difficulty with the add-unit command, possibly due to…"
8. **Negative findings count too.** If a friction tag from the
   codebook *didn't* fire across the cohort, that's evidence
   about the surface (the docs work, or the error messages are
   fine). Worth a one-line "didn't see this" section so
   engineers reading the report know the codebook looked.

## Worked examples

### A theme summary

**Before** (generic Bristlenose voice):

> Participants experienced significant friction in the
> documentation pathway. Several individuals expressed
> confusion when attempting to discover the correct command
> syntax, and the man pages were perceived as difficult to
> navigate. Multiple participants resorted to external
> resources, suggesting an opportunity to improve in-tool
> documentation.

**After** (CLI register):

> 5 of 6 participants ran `--help` first. 3 of those then ran
> `man <tool>` and quit `less` within 20 seconds without
> finding what they needed. 4 ended up in a browser tab —
> two on Stack Overflow, two in a Claude chat. The
> participant quoted as saying "this man page is just a wall
> of flags, alphabetised, no examples" (S3 14:22) matches
> the pattern: every man page in the cohort lacks an
> `EXAMPLES` section. Consider: add `EXAMPLES` to the man
> page; add a top-of-`--help` example block.

### A friction finding

**Before:**

> The error messaging was identified as a usability issue.
> Participants reported difficulty understanding error
> output, which led to frustration and task abandonment in
> several cases.

**After:**

> The error `Error: cannot determine kind of pod "foo":
> object has no kind` lost 3 of 5 participants. Two
> abandoned the task; one pasted the message into a search
> engine and recovered after 4 minutes. The error names two
> internal concepts ("kind", "object") without defining
> them. Compare `kubectl`'s
> `error: resource(s) were provided, but no name was
> specified` — names the missing input. Suggested fix:
> rewrite to "specify --kind=<pod|deployment|...>; see
> `tool create --help`."

### A dashboard headline

**Before:**

> Documentation Issues: HIGH

**After:**

> man page abandoned in <20s: 3 of 6
> `--help` consulted first: 5 of 6
> Browser tab opened to read docs: 5 of 6

### A bug-report stub (high-confidence finding)

```
Title: `juju add-unit` returns "no such command"; participants type
this first

Repro:
  $ juju add-unit foo

Observed:
  ERROR no such command "add-unit", maybe you meant "add-unit"?

Expected:
  Either the command works (it's the natural verb-noun ordering),
  or the error suggests the correct invocation: `juju unit add foo`

Evidence:
  4 of 5 cohort participants typed `juju add-unit ...` as their
  first attempt at adding a unit. 3 then ran `juju --help` to find
  the correct verb. 1 gave up and asked in chat.

Sessions:
  S1 03:42, S2 11:18, S3 07:55, S4 14:02
```

## Where this lands in Bristlenose

The register-shift is mostly a prompt-engineering pass — the
codebook is already the right vocabulary, the report templates are
already capable of holding the right shape. The work:

1. **Codebook-aware prompt variants in `bristlenose/llm/prompts/`.**
   Add a `cli-register` variant of:
   - `extract_quotes` — must treat command mentions as first-class
     quotable evidence.
   - `generate_themes` / `summarise_friction` — must follow the
     register rules above. The prompt itself encodes the rules so
     the LLM doesn't need a separate "be terse, be technical"
     instruction at runtime.
   - A new `emit_bug_stub` prompt for high-confidence findings,
     gated by an evidence threshold (e.g. ≥3 participants hit the
     same pattern with consistent verbatim text).
2. **Codebook-aware prompt selection.** A small hook in the LLM
   client that, when the project's primary codebook is `cli-ux`,
   reaches for the `cli-register` variants. Falls back to the
   default variants for non-CLI studies. Could be a flag on the
   `CodebookTemplate` (`prompt_register: "cli" | "default"`) or a
   lookup map alongside the loader.
3. **Command/flag entity recognition.** A small pre-pass during
   quote extraction that detects shell-shaped strings — anything
   matching a prompt+command pattern — and tags them as commands
   in the quote model. Lets the report rank by command frequency
   later. Probably belongs in `bristlenose/utils/cli_entities.py`
   alongside the (future) terminal-paste parser from the
   session-matching design note.
4. **Report template tweaks** for CLI studies — a top-of-report
   block with the four ranked headlines (top commands attempted,
   top errors hit, top docs-discovery failures, top verb-noun
   mismatches), driven by the entity recognition pass. These can
   start as static React panels filtered to the project's
   active codebook IDs and become richer as the pipeline learns
   the entity types.

The first two are a single sandpit-sized week. The third and
fourth are full features and deserve their own design notes
before implementation.

## What this is not

- This is not a separate report format. It is the same Bristlenose
  report with a different voice, driven by which codebook the
  project leans on.
- This is not a rewrite of the existing UX-research codebooks.
  Nielsen, Norman, Morville, Garrett etc. remain the right
  vocabulary for product / consumer research, and the default
  Bristlenose voice serves them correctly. The register shift is
  gated on `cli-ux` being the active codebook (or, later,
  whichever domain-specific codebook declares its own register).
- This is not an LLM personality change. The rules are encoded in
  the prompts themselves, not in a system-message tone shift. A
  prompt that asks for "5 of N participants did X" gets that;
  a prompt that asks for "an executive summary" gets fluff.

## Open questions

1. **Codebook-as-register.** Should the register rules be a
   property of the codebook (each codebook declares the voice for
   reports about projects that use it), or a separate axis the
   project sets independently? Codebook-as-register is simpler —
   one fewer config to think about — but couples vocabulary to
   voice. Worth picking deliberately before any of this ships.
2. **Bug-stub threshold.** What's the right evidence bar for
   emitting a bug-report stub vs leaving the finding as prose?
   Tentative: ≥3 participants exhibit the pattern AND ≥2 of them
   have consistent verbatim command/error text. Tunable.
3. **Engineer-as-participant.** Some studies will have engineers
   on *both* sides of the call — researcher and participant alike
   speak the same vocabulary. Does the report register need to
   adapt further when the cohort is all-technical? Probably not
   — the register is about the *reader*, not the participants —
   but worth noticing.
4. **i18n.** Engineering vocabulary borrows heavily from English
   (`footgun`, `surface`, `ergonomics` are American-engineering
   terms with no clean equivalent in some locales). The cli-ux
   codebook ships English-only for now; localising the *register
   rules* is a separate, harder problem and not in scope here.
