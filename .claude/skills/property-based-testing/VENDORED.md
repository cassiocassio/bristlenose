# property-based-testing — vendored third-party skill

**Not ours.** This is Trail of Bits' `property-based-testing` skill.

- **Source:** https://github.com/trailofbits/skills
  (`plugins/property-based-testing/skills/property-based-testing/`)
- **Pinned commit:** `442fc9d6c8` (fetched 11 Oct 2026)
- **Author / licence:** Trail of Bits / **CC-BY-SA-4.0** (see `LICENSE`)

## What was taken, and what changed (CC-BY-SA §3(a)(1)(B))

Taken verbatim: `SKILL.md`, `README.md` and `references/*.md`.

Left out:
- `agents/openai.yaml`, an OpenAI agent stub;
- `assets/trail-of-bits-mark.svg`, a logo;
- the plugin wrapper (`.claude-plugin/plugin.json`);
- `evals/` and `evals-extra/`, the authors' grading harness.

No file was modified. These files stay under CC-BY-SA-4.0; nothing from them
is copied into the AGPL code.

## Why it is here

It is the one third-party skill that measurably helped in the 11 Oct 2026
review (`experiments/skills-research/README.md`). Hypothesis tests written with
it killed **6 of 11** hidden mutants reliably, against **4** for tests written
without it. They also killed two mutants the existing example suite let through
(a slug ending in `-` after truncation, and hyphens not collapsed). Both
versions found the same two real defects, so the technique carries most of the
value and the skill improves its quality. What it changed in practice: domain
limits went into strategies rather than `assume()`, and properties were chosen
not to restate the code.

## House rules that win on conflict

- **When to use it** is `docs/design-test-philosophy.md`'s placement rule:
  Hypothesis where a function has an algebra (round trip, idempotence,
  ordering, bounds) *and* a parsed or rendered contract. Otherwise, examples.
  The skill says the same ("code with no such shape gets example tests").
- **Determinism:** CI loads the `ci` Hypothesis profile (`tests/conftest.py`,
  derandomised). Never register or load a profile inside a test module; it
  overrides conftest silently.
- **Pin each kill that matters with `@example`.** Under a fixed seed, a
  generator either always finds a counterexample or never does, so a property
  that only kills a mutant on some seeds kills it on none in CI.
- Project hard rules (`MEMORY.md`, `CLAUDE.md`) and `what-would-james-bach-say`'s
  proportion review win over the skill's enthusiasm.

## Updating

```sh
D=.claude/skills/property-based-testing
R=plugins/property-based-testing/skills/property-based-testing
SHA=<new commit>
for f in SKILL.md README.md references/generating.md references/interpreting-failures.md \
         references/libraries.md references/refactoring.md references/reviewing.md; do
  gh api "repos/trailofbits/skills/contents/$R/$f?ref=$SHA" --jq .content | base64 -d > "$D/$f"
done
gh api "repos/trailofbits/skills/contents/LICENSE?ref=$SHA" --jq .content | base64 -d > "$D/LICENSE"
```

Then update the pinned commit above, and read the diff before committing.
