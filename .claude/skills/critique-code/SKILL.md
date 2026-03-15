---
name: critique-code
description: Critique changed code — find bugs, check conventions, raise design questions
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep, AskUserQuestion
---

Critique recent code changes. Find real bugs, check project conventions, and — most importantly — raise thoughtful design questions that surface competing viewpoints and tradeoffs.

This is a **thinking partner**, not a gatekeeper. The Questions section is always present, even for perfect code. Present alternatives honestly, steelman both sides, and let the developer decide.

## Step 1: Determine scope

If `$0` is a git range (e.g. `main..HEAD`, `HEAD~3..HEAD`), use it directly and skip the prompt.

Otherwise, ask the user what to critique:
- Staged changes (`git diff --cached`)
- All uncommitted changes (`git diff`)
- Last commit (`git diff HEAD~1..HEAD`)
- Custom range (user provides)

Run `git diff --stat <range>` to get the file list. If the diff exceeds 500 lines, warn the user and suggest breaking the change into smaller commits — but proceed.

## Step 2: Identify active lenses

Based on file extensions in the diff, activate conditional lenses:

- `.py` files present → activate **Python lens**
- `.ts` or `.tsx` files present → activate **TypeScript/React lens**
- `.css` files in `bristlenose/theme/` present → activate **CSS/Theme lens**

## Step 3: Read conventions

Read the root `CLAUDE.md` (always). Then read **only** the CLAUDE.md files relevant to changed paths:

| Changed path prefix | Read |
|---------------------|------|
| `bristlenose/stages/` | `bristlenose/stages/CLAUDE.md` |
| `bristlenose/llm/` | `bristlenose/llm/CLAUDE.md` |
| `bristlenose/server/` | `bristlenose/server/CLAUDE.md` |
| `bristlenose/theme/` | `bristlenose/theme/CLAUDE.md` |
| `frontend/` | `frontend/CLAUDE.md` |

Do not read all CLAUDE.md files every time — only the relevant ones.

## Step 4: Read the diff

Run `git diff <range>` to get the full diff content. If you need surrounding context to understand a function signature, type, or import — read that source file.

## Step 5: Produce the critique

Output this structure:

```
# Critique

**Scope:** <summary, e.g. "3 staged files (2 Python, 1 TypeScript)">

## Bugs & Issues

<numbered list, or "None found." if clean>

## Convention Notes

<numbered list, or "All conventions followed." if clean>

## Questions

<numbered list — always present>
```

### Bugs & Issues rules

- **HIGH SIGNAL ONLY.** If you are not certain an issue is real, do not flag it. False positives erode trust.
- No LOW severity — if it's not worth fixing, don't mention it.
- Each finding: `file:line` — [HIGH/MEDIUM] description. Why it matters. 2–4 sentences max.

### Convention Notes rules

- Cite the specific CLAUDE.md file and rule. Reference directly, don't paraphrase.
- Each note: `file:line` — what deviates. Ref: which CLAUDE.md, which rule.

### Questions rules (the core of this skill)

- **Always present**, even for perfect code. Good code still has interesting design questions.
- Present competing alternatives honestly. Steelman both sides.
- **Do not lead toward a preferred answer.** Frame as "here's what I noticed and the competing considerations."
- Each question: 2–4 sentences. Identify the tradeoff, present both sides.
- Example framings:
  - "This introduces X. Two views: (a) ... (b) ... What's the intent?"
  - "This duplicates logic from Y. Intentional (to avoid coupling) or accidental?"
  - "Alternative approach: Z. Tradeoff: simpler but less extensible. Worth considering?"

### What to NEVER flag

- Code style, formatting, import order — Ruff and ESLint handle that
- Subjective preferences without meaningful tradeoffs
- "You could also do X" suggestions that don't have real tradeoffs
- Process compliance (running tests, running linters) — hooks and CI handle that

### Language-specific lenses

**Python lens** (when `.py` files are in the diff):
- Type hint completeness (strict mypy is the standard)
- Pydantic for data structures (except `analysis/` which uses plain dataclasses)
- Test isolation — tests must not depend on local environment (API keys, Ollama, local config). The v0.6.7–v0.6.13 CI failures were caused by exactly this
- Async patterns: `asyncio.Semaphore` + `asyncio.gather` for concurrency

**TypeScript/React lens** (when `.ts`/`.tsx` files are in the diff):
- Store patterns: `useSyncExternalStore`, not Context for shared state
- `stopPropagation` on keydown handlers (known bug class in this codebase)
- Router: `<a>` or `<Link>` for clickable navigation, not `<div onClick>`
- Tests: `resetStore()` in `beforeEach`, `vi.mock` hoisting awareness

**CSS/Theme lens** (when `.css` files in `bristlenose/theme/` are in the diff):
- Token usage: `--bn-*` custom properties, never hardcoded values
- Dark mode: `light-dark()` function, no JS
- Font weights: use `--bn-weight-*` tokens, never hardcode
- Breakpoint tokens: reference token name in `@media` query comments
- The atomic CSS architecture (tokens → atoms → molecules → organisms → templates) is settled — check conventions are followed, don't question the approach

### Brevity

Be brief. Each finding or question: 2–4 sentences. The developer is smart and knows the codebase — provide the signal, not an explanation of what the code does. If the change is trivial (typo, version bump) with nothing interesting to say, say "Nothing to flag — trivial change." and stop.
