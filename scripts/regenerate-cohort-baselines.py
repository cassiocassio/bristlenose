#!/usr/bin/env python3
"""Regenerate ``bristlenose/llm/cohort-baselines.json`` from run telemetry.

The baselines are what a *new* user's pre-run cost forecast is built on —
they have no local ``llm-calls.jsonl``, so with an empty file
``estimate_pipeline_cost`` returns ``None`` and the forecast never fires.
That was the shipped state from Slice C (2026-04-28) until 2026-09-21.

Usage::

    .venv/bin/python scripts/regenerate-cohort-baselines.py trial-runs/
    .venv/bin/python scripts/regenerate-cohort-baselines.py trial-runs/ --dry-run

**Privacy.** The inputs are re-identification keys: every row carries a
session id, a prompt sha and a timing fingerprint. This script emits
**aggregates only** — per-(family, major, stage) medians and a sample
count — and asserts before writing that no session id, run id, timestamp
or prompt sha reached the output. Point it at a gitignored corpus and
commit the result; never commit the inputs.

Rows are filtered to pipeline stages (``s<digit>…``) with
``outcome == "ok"`` and ``usage_source == "reported"``: serve-mode rows
(``serve_autocode``, ``serve_signal_elaboration``) would inflate a pre-run
estimate with spend that a run does not incur.
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "bristlenose" / "llm" / "cohort-baselines.json"

SCHEMA_VERSION = 1

# Pooled fallback cohort — see _GENERIC_COHORT in pricing.py.
GENERIC = "*"

# Fields that must never reach the output file.
_FORBIDDEN_KEYS = frozenset({
    "session_id", "run_id", "ts", "prompt_sha", "elapsed_ms",
    "input_chars", "gen_ai.response.model", "gen_ai.request.model",
})


def _is_pipeline_stage(stage: object) -> bool:
    """True for pipeline-stage rows (``s05b_…``), false for serve-mode rows."""
    return (
        isinstance(stage, str)
        and len(stage) >= 2
        and stage[0] == "s"
        and stage[1].isdigit()
    )


def load_rows(root: Path) -> list[dict[str, Any]]:
    """Read every ``llm-calls.jsonl`` under ``root``, keeping usable rows."""
    kept: list[dict[str, Any]] = []
    files = sorted(root.glob("**/llm-calls.jsonl"))
    if not files:
        print(f"no llm-calls.jsonl found under {root}", file=sys.stderr)
    for path in files:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("outcome") != "ok":
                    continue
                if row.get("usage_source") != "reported":
                    continue
                if not _is_pipeline_stage(row.get("stage")):
                    continue
                if not isinstance(row.get("gen_ai.usage.input_tokens"), int):
                    continue
                if not isinstance(row.get("gen_ai.usage.output_tokens"), int):
                    continue
                kept.append(row)
    return kept


def build_cohorts(rows: list[dict[str, Any]], min_samples: int) -> list[dict[str, Any]]:
    """Aggregate rows into per-(family, major, stage) baseline entries.

    Also emits a pooled ``("*", "*")` cohort across every family, which is
    what an unmeasured model resolves to. Three of the four cloud providers'
    current defaults normalise to a family with no measured rows.
    """
    buckets: dict[tuple[str, str, str], dict[str, list[int]]] = collections.defaultdict(
        lambda: {"in": [], "out": []},
    )
    prompt_ids: dict[tuple[str, str, str], str | None] = {}
    versions: dict[tuple[str, str, str], collections.Counter[str]] = (
        collections.defaultdict(collections.Counter)
    )

    for row in rows:
        family = str(row.get("model_family", ""))
        major = str(row.get("model_major", ""))
        stage = str(row.get("stage", ""))
        if not family or not stage:
            continue
        for key in ((family, major, stage), (GENERIC, GENERIC, stage)):
            buckets[key]["in"].append(row["gen_ai.usage.input_tokens"])
            buckets[key]["out"].append(row["gen_ai.usage.output_tokens"])
            prompt_ids.setdefault(key, row.get("prompt_id"))
            version = row.get("prompt_version")
            if version:
                versions[key][str(version)] += 1

    cohorts: list[dict[str, Any]] = []
    for (family, major, stage), vals in sorted(buckets.items()):
        n = len(vals["in"])
        if n < min_samples:
            print(
                f"  skip {family}/{major} {stage}: n={n} < {min_samples}",
                file=sys.stderr,
            )
            continue
        key = (family, major, stage)
        seen = versions[key]
        # A median over a mix of prompt versions is a real number about a
        # blend, so name the blend. Recording only the first version seen
        # would claim a calibration the medians do not have.
        contributing = sorted(seen)
        cohorts.append({
            "stage_id": stage,
            "prompt_id": prompt_ids[key],
            "prompt_version": seen.most_common(1)[0][0] if seen else None,
            "prompt_versions_contributing": contributing,
            "model_family": family,
            "model_major": major,
            "median_input_tokens": int(statistics.median(vals["in"])),
            "median_output_tokens": int(statistics.median(vals["out"])),
            "sample_count": n,
        })
        if len(contributing) > 1:
            print(
                f"  note {family}/{major} {stage}: median blends prompt "
                f"versions {', '.join(contributing)} "
                f"({dict(seen)}) — re-run the corpus to re-calibrate",
                file=sys.stderr,
            )
    return cohorts


def assert_no_identifiers(payload: dict[str, Any]) -> None:
    """Fail loudly if any re-identifying field reached the output.

    A silent leak here would put session ids on the public repo. The check
    is on the *serialised* form so a nested value cannot slip past a
    key-only scan.
    """
    blob = json.dumps(payload)
    for cohort in payload.get("cohorts", []):
        for key in cohort:
            if key in _FORBIDDEN_KEYS:
                msg = f"cohort entry carries forbidden field {key!r}"
                raise AssertionError(msg)
    for needle in ("session_id", "run_id", "prompt_sha", '"ts"'):
        if needle in blob:
            msg = f"output contains {needle!r} — refusing to write"
            raise AssertionError(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "corpus", type=Path,
        help="directory to scan recursively for llm-calls.jsonl",
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT,
        help=f"output path (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--min-samples", type=int, default=3,
        help="minimum rows before a cohort cell is emitted (default: 3)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the result without writing",
    )
    args = parser.parse_args()

    rows = load_rows(args.corpus)
    print(f"read {len(rows)} usable pipeline rows from {args.corpus}", file=sys.stderr)
    if not rows:
        return 1

    cohorts = build_cohorts(rows, args.min_samples)
    if not cohorts:
        print("no cohort cleared --min-samples; nothing written", file=sys.stderr)
        return 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source": (
            "aggregated by scripts/regenerate-cohort-baselines.py from "
            "maintainer dogfood runs; medians and counts only, no per-call rows"
        ),
        "cohorts": cohorts,
    }
    assert_no_identifiers(payload)

    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if args.dry_run:
        sys.stdout.write(text)
        return 0

    args.out.write_text(text, encoding="utf-8")
    families = {(c["model_family"], c["model_major"]) for c in cohorts}
    print(
        f"wrote {len(cohorts)} rows across {len(families)} cohorts to {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
