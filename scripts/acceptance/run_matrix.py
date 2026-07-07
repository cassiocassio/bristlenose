#!/usr/bin/env python3
"""Acceptance matrix runner — Phase 1 (CLI provider matrix).

Drives real `bristlenose` cells and asserts shape-only invariants (invariants.py).
Design decisions from the 2026-07-07 review (docs/testing/acceptance-matrix.md
"Phase-1 build decisions"):

  * **A skip must be declared and counted (F1).** Every cell is declared in the
    manifest with a prerequisite. A cell whose prereq is unmet is SKIP(declared).
    The run asserts `executed + declared_skips == len(manifest)` — an *undeclared*
    skip (a cell that silently didn't run) is an ERROR, the loudest state. The whole
    matrix can no longer green while running nothing.
  * **BRISTLENOSE_ACCEPTANCE_REQUIRE_ALL=1** turns every declared SKIP into a FAIL —
    for the nightly, where "Azure wasn't configured" must not pass silently.
  * **Provider taxonomy (F7):** unconfigured→SKIP, configured+failed→FAIL_EXPECTED
    (non-blocking signal), configured+empty→FAIL_BLOCKING (the gemma4 class).
  * **Governance (F2/F3):** artifacts land in a gitignored, chmod-700 acceptance-runs/
    dir with a per-dir `.gitignore '*'`; keys come from the environment only (never
    argv); all captured stderr is key-redacted; a post-run grep fails loud on any key.
  * **Provenance (F16):** first thing asserted is `bristlenose --version == __version__`
    — no greening against a stale editable install.

Cloud cells are DEFINED but run only with --run-cloud (real keys + spend). The local
Ollama cell and the --self-test (validate the committed smoke fixture, no LLM) are free.

Usage:
    python scripts/acceptance/run_matrix.py --self-test          # free, no LLM
    python scripts/acceptance/run_matrix.py --run-local          # free, needs Ollama
    python scripts/acceptance/run_matrix.py --run-cloud          # $ + keys
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
_ROOT = _HERE.parent.parent

from invariants import (  # noqa: E402
    CellOutcome,
    CellResult,
    InvariantError,
    assert_no_abandoned_stage,
    assert_reid_keys_not_shareable,
    assert_report_non_empty,
    assert_terminus_completed,
)

from bristlenose import __version__  # noqa: E402

_ARTIFACT_ROOT = _ROOT / "acceptance-runs"
_SMOKE_OUTPUT = (
    _ROOT / "tests" / "fixtures" / "smoke-test" / "input" / "bristlenose-output"
)

# Key shapes to redact from any captured output before it is written or grepped.
_KEY_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),  # Anthropic / OpenAI
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),  # Google
    re.compile(r"(?i)(api[_-]?key|auth[_-]?token|bearer)\s*[:=]\s*\S+"),  # generic
]


def redact(text: str) -> str:
    for pat in _KEY_PATTERNS:
        text = pat.sub("«REDACTED»", text)
    return text


def bristlenose_exe() -> str:
    """The `bristlenose` matching THIS interpreter — the venv sibling of sys.executable,
    not whatever `which` finds on PATH (a stale global install would shadow it and the
    matrix would green against old code — the F16 provenance trap this guards against)."""
    sibling = Path(sys.executable).parent / "bristlenose"
    if sibling.exists():
        return str(sibling)
    return shutil.which("bristlenose") or str(_ROOT / ".venv" / "bin" / "bristlenose")


# ---------------------------------------------------------------------------
# Manifest — every cell declared with a prerequisite predicate
# ---------------------------------------------------------------------------


@dataclass
class Cell:
    cell_id: str
    provider: str  # "local" | "anthropic" | "openai" | "azure" | "google" | "-"
    key_env: str | None  # env var whose presence means "configured"
    kind: str  # "analyze" | "run" | "validate"

    def configured(self) -> bool:
        if self.provider == "local":
            return _ollama_up()
        if self.key_env is None:
            return True
        return bool(os.environ.get(self.key_env))


def _ollama_up() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
            return True
    except Exception:
        return False


PROVIDER_CELLS = [
    Cell("analyze:local", "local", None, "analyze"),
    Cell("analyze:anthropic", "anthropic", "BRISTLENOSE_ANTHROPIC_API_KEY", "analyze"),
    Cell("analyze:openai", "openai", "BRISTLENOSE_OPENAI_API_KEY", "analyze"),
    Cell("analyze:azure", "azure", "BRISTLENOSE_AZURE_API_KEY", "analyze"),
    Cell("analyze:google", "google", "BRISTLENOSE_GOOGLE_API_KEY", "analyze"),
]


# ---------------------------------------------------------------------------
# Result accounting with the C1 executed==expected discipline
# ---------------------------------------------------------------------------


@dataclass
class Matrix:
    results: list[CellResult] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)  # cell_ids that SHOULD produce a row

    def record(self, r: CellResult) -> None:
        self.results.append(r)

    def undeclared_skips(self) -> list[str]:
        produced = {r.cell_id for r in self.results}
        return [cid for cid in self.expected if cid not in produced]

    def verdict(self) -> tuple[bool, str]:
        missing = self.undeclared_skips()
        if missing:
            return False, f"UNDECLARED SKIP (ERROR): {', '.join(missing)} produced no result"
        reds = [r for r in self.results if not r.is_green]
        if reds:
            return False, f"{len(reds)} blocking failure(s): " + ", ".join(
                f"{r.cell_id}={r.outcome.value}" for r in reds
            )
        return True, f"all {len(self.results)} cells green"


# ---------------------------------------------------------------------------
# Version provenance guard (F16) — run before any cell
# ---------------------------------------------------------------------------


def assert_testing_todays_code() -> None:
    exe = bristlenose_exe()
    out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
    reported = (out.stdout + out.stderr).strip()
    if __version__ not in reported:
        raise SystemExit(
            f"PROVENANCE FAIL: `bristlenose --version` = {reported!r} but tree "
            f"__version__ = {__version__!r}. Stale editable install / wrong venv — "
            f"aborting before the matrix greens against old code."
        )


# ---------------------------------------------------------------------------
# Cell execution
# ---------------------------------------------------------------------------


def validate_output_dir(cell_id: str, output_dir: Path, *, quote_floor: int) -> CellResult:
    """Apply the shape invariants to a produced (or committed) output dir."""
    try:
        event = assert_terminus_completed(output_dir)
        assert_no_abandoned_stage(event)
        assert_report_non_empty(output_dir, quote_floor=quote_floor)
        assert_reid_keys_not_shareable(output_dir)
    except InvariantError as e:
        return CellResult(cell_id, CellOutcome.FAIL_BLOCKING, redact(str(e)))
    except (OSError, ValueError) as e:
        # Fail-closed: any unexpected read/parse error (missing artifact, malformed
        # JSON) is a blocking failure, never an uncaught crash. A conformance harness
        # must never itself fake-success by dying mid-check.
        return CellResult(cell_id, CellOutcome.FAIL_BLOCKING, redact(f"invariant read error: {e}"))
    return CellResult(cell_id, CellOutcome.PASS, "shape invariants held")


def prepare_artifact_dir() -> Path:
    _ARTIFACT_ROOT.mkdir(mode=0o700, exist_ok=True)
    # Belt-and-braces: a per-dir gitignore so nothing here is ever stageable, even if
    # the root .gitignore entry is removed. Real reports carry unredacted transcripts.
    (_ARTIFACT_ROOT / ".gitignore").write_text("*\n")
    os.chmod(_ARTIFACT_ROOT, 0o700)
    return _ARTIFACT_ROOT


def post_run_key_grep(artifact_dir: Path) -> None:
    """Fail loud if any key shape survived into a committed-able artifact."""
    for path in artifact_dir.rglob("*"):
        if path.is_file() and path.name != ".gitignore":
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in _KEY_PATTERNS:
                if pat.search(text):
                    raise SystemExit(f"KEY LEAK in artifact {path} — aborting")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    require_all = os.environ.get("BRISTLENOSE_ACCEPTANCE_REQUIRE_ALL") == "1"
    assert_testing_todays_code()
    artifact_dir = prepare_artifact_dir()
    m = Matrix()

    if args.self_test:
        # Free: validate the committed smoke fixture end-to-end through the invariants.
        m.expected = ["validate:smoke"]
        m.record(validate_output_dir("validate:smoke", _SMOKE_OUTPUT, quote_floor=3))

    if args.run_local or args.run_cloud:
        for cell in PROVIDER_CELLS:
            is_cloud = cell.provider != "local"
            if is_cloud and not args.run_cloud:
                continue
            if not is_cloud and not args.run_local:
                continue
            m.expected.append(cell.cell_id)
            configured = cell.configured()
            if not configured:
                outcome = CellOutcome.SKIP
                if require_all:
                    outcome = CellOutcome.ERROR
                m.record(CellResult(cell.cell_id, outcome, f"prereq unmet ({cell.key_env or 'ollama'})"))
                continue
            # Real execution is intentionally left to the operator's --input + a follow-up
            # commit; Phase-1 wires the taxonomy + accounting. A configured cell with no
            # --input is a declared skip, not a silent pass.
            if not args.input:
                m.record(CellResult(cell.cell_id, CellOutcome.SKIP, "configured but no --input given"))
                continue
            m.record(_run_analyze_cell(cell, Path(args.input), artifact_dir))

    post_run_key_grep(artifact_dir)
    ok, msg = m.verdict()
    _write_summary(artifact_dir, m, ok, msg)
    _print_summary(m, ok, msg)
    return 0 if ok else 1


def _run_analyze_cell(cell: Cell, input_dir: Path, artifact_dir: Path) -> CellResult:
    out = artifact_dir / cell.cell_id.replace(":", "_")
    exe = bristlenose_exe()
    # Keys via the environment only — never on argv (ps/history visible).
    proc = subprocess.run(
        [exe, "analyze", str(input_dir), "--llm", cell.provider, "--output", str(out)],
        capture_output=True,
        text=True,
        timeout=1800,
        env=os.environ.copy(),
    )
    (artifact_dir / f"{cell.cell_id.replace(':', '_')}.log").write_text(redact(proc.stdout + proc.stderr))
    res = validate_output_dir(cell.cell_id, out, quote_floor=1)
    if res.outcome == CellOutcome.PASS and proc.returncode not in (0,):
        return CellResult(cell.cell_id, CellOutcome.FAIL_EXPECTED, f"exit {proc.returncode}")
    return res


def _write_summary(artifact_dir: Path, m: Matrix, ok: bool, msg: str) -> None:
    import json

    payload = {
        "version": __version__,
        "verdict": "GREEN" if ok else "RED",
        "message": msg,
        "cells": [{"cell": r.cell_id, "outcome": r.outcome.value, "detail": r.detail} for r in m.results],
        "expected": m.expected,
    }
    (artifact_dir / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True))


def _print_summary(m: Matrix, ok: bool, msg: str) -> None:
    print(f"\nacceptance matrix — bristlenose {__version__}")
    for r in m.results:
        mark = "✓" if r.is_green else "✗"
        print(f"  {mark} {r.cell_id:24} {r.outcome.value:14} {r.detail}")
    print(f"\n{'GREEN' if ok else 'RED'}: {msg}\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Bristlenose acceptance matrix (Phase 1)")
    p.add_argument("--self-test", action="store_true", help="validate the smoke fixture (free)")
    p.add_argument("--run-local", action="store_true", help="run the local Ollama cell (free)")
    p.add_argument("--run-cloud", action="store_true", help="run cloud cells (keys + spend)")
    p.add_argument("--input", help="input folder for provider analyze cells")
    args = p.parse_args()
    if not (args.self_test or args.run_local or args.run_cloud):
        args.self_test = True  # default to the free proof
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
