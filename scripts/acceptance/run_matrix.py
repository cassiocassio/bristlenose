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
    assert_sessions_accounted,
    assert_terminus_completed,
    assert_transcripts_present,
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
        # "-" is the no-provider column: nothing to configure, so it never skips.
        # That is the whole point of it — see TRANSCRIBE_CELL.
        if self.provider == "-":
            return True
        if self.provider == "local":
            return _ollama_up()
        # Resolve the key the SAME way bristlenose does — Keychain → env → .env — not a
        # bare os.environ check. A Mac dev's key lives in the Keychain, so an env-only
        # check would wrongly SKIP a runnable cloud cell (found live, 7 Jul 2026).
        try:
            from bristlenose.credentials import get_credential

            return get_credential(self.provider) is not None
        except Exception:
            return bool(os.environ.get(self.key_env or ""))


def _ollama_up() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2):
            return True
    except Exception:
        return False


# The provider column runs a subtitle fixture through `run` (not `analyze`): a `.vtt`
# skips transcription anyway (no Whisper cost), and `run` discovers the input where
# `analyze` — which expects pre-transcribed text — did not (found live, 7 Jul 2026).
PROVIDER_CELLS = [
    Cell("run:local", "local", None, "run"),
    Cell("run:anthropic", "anthropic", "BRISTLENOSE_ANTHROPIC_API_KEY", "run"),
    Cell("run:openai", "openai", "BRISTLENOSE_OPENAI_API_KEY", "run"),
    Cell("run:azure", "azure", "BRISTLENOSE_AZURE_API_KEY", "run"),
    Cell("run:google", "google", "BRISTLENOSE_GOOGLE_API_KEY", "run"),
]

# The only cell that needs no provider at all. Every entry above is gated on a
# configured key or a running Ollama, so on a machine with neither — a fresh clone, a
# contributor's laptop, CI — the matrix's other free cell validates a *committed
# fixture* and exercises no pipeline code. This is the first live run that needs no
# credentials, and `transcribe` is also the only command with no downstream bucket, so
# cross-bucket continuity can never reach it. What watches it is `assert_sessions_
# accounted`, which is a tautology nearly everywhere else and has teeth here because
# this rollup measures success independently rather than by subtracting failures.
TRANSCRIBE_CELL = Cell("transcribe:no-key", "-", None, "transcribe")


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
        assert_sessions_accounted(event)
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
        m.expected.append("validate:smoke")
        m.record(validate_output_dir("validate:smoke", _SMOKE_OUTPUT, quote_floor=3))

    if args.run_transcribe:
        # Free and live: no key, no Whisper, ~3s. The only cell that drives real
        # pipeline code on a machine with nothing configured.
        m.expected.append(TRANSCRIBE_CELL.cell_id)
        m.record(_run_transcribe_cell(artifact_dir))

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
                prereq = "ollama not running" if cell.provider == "local" else "no key (Keychain/env/.env)"
                m.record(CellResult(cell.cell_id, outcome, prereq))
                continue
            # A configured cell with no --input is a declared skip, not a silent pass.
            if not args.input:
                m.record(CellResult(cell.cell_id, CellOutcome.SKIP, "configured but no --input given"))
                continue
            m.record(_run_provider_cell(cell, Path(args.input), artifact_dir))

    post_run_key_grep(artifact_dir)
    ok, msg = m.verdict()
    _write_summary(artifact_dir, m, ok, msg)
    _print_summary(m, ok, msg)
    return 0 if ok else 1


def _run_provider_cell(cell: Cell, input_dir: Path, artifact_dir: Path) -> CellResult:
    out = artifact_dir / cell.cell_id.replace(":", "_")
    exe = bristlenose_exe()
    # `run --no-serve`: full pipeline (a subtitle fixture skips Whisper), and `--no-serve`
    # so the cell exits instead of blocking on the auto-started dev server. Keys resolve
    # via bristlenose's own Keychain/env cascade — never passed on argv (ps/history visible).
    proc = subprocess.run(
        [exe, "run", str(input_dir), "--llm", cell.provider, "--output", str(out), "--no-serve"],
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


# Two subtitle files, written here rather than committed so the cell is self-
# describing and coupled to nothing. One carries cues — a session that succeeds
# without Whisper ever loading. One carries none, which is a session that produces no
# words: the shape this cell exists to watch. A `.wav` of silence would be the
# faithful article but drags in a model download; a zero-cue `.vtt` reaches the same
# orchestrator state — segments absent, nothing raised — for free. Measured 2.6s.
_FIXTURE_WITH_SPEECH = """WEBVTT

00:00:02.000 --> 00:00:09.000
<v Moderator>Talk me through what you were trying to do on the checkout page.

00:00:10.000 --> 00:00:18.000
<v Participant>I kept looking for the total. It was below the fold the whole time.
"""

# Valid WebVTT, zero cues. A recording of an empty room reaches the pipeline the same
# way: it decodes, it transcribes, and nobody said anything.
_FIXTURE_SILENT = "WEBVTT\n\n"


def build_transcribe_fixture(dest: Path) -> Path:
    """Write the two-session fixture and return the input dir."""
    input_dir = dest / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "Session 1.vtt").write_text(_FIXTURE_WITH_SPEECH, encoding="utf-8")
    (input_dir / "Session 2.vtt").write_text(_FIXTURE_SILENT, encoding="utf-8")
    return input_dir


def _assert_silence_was_named(event: dict) -> None:
    """The fixture's silent session must be named, not merely counted out.

    The arithmetic guard alone would pass a run that recorded the shortfall as an
    anonymous failure. What a researcher needs is *which file*, so this cell asserts
    the thing the arithmetic cannot: a `source_file` on the row.
    """
    summary = event.get("summary") or {}
    bucket = summary.get("transcripts")
    if not isinstance(bucket, dict):
        raise InvariantError("terminus carried no transcripts bucket")
    failed = [f for f in bucket.get("failed") or [] if isinstance(f, dict)]
    if len(failed) != 1:
        raise InvariantError(
            f"expected exactly 1 stated silent session, got {len(failed)}: {failed!r}"
        )
    named = failed[0].get("source_file")
    if not named:
        raise InvariantError(
            "the silent session was recorded but not named — a count with extra steps"
        )
    if named != "Session 2.vtt":
        raise InvariantError(f"named the wrong file: {named!r}")


def _run_transcribe_cell(artifact_dir: Path) -> CellResult:
    cell_id = TRANSCRIBE_CELL.cell_id
    work = artifact_dir / cell_id.replace(":", "_")
    out = work / "output"
    try:
        input_dir = build_transcribe_fixture(work)
    except OSError as e:
        return CellResult(cell_id, CellOutcome.FAIL_BLOCKING, redact(f"fixture setup failed: {e}"))

    proc = subprocess.run(
        [bristlenose_exe(), "transcribe", str(input_dir), "--output", str(out)],
        capture_output=True,
        text=True,
        timeout=600,
        env=os.environ.copy(),
    )
    (artifact_dir / f"{cell_id.replace(':', '_')}.log").write_text(
        redact(proc.stdout + proc.stderr)
    )

    try:
        event = assert_terminus_completed(out)
        assert_no_abandoned_stage(event)
        assert_sessions_accounted(event)
        # NOT assert_report_non_empty — `transcribe` writes no report, and letting a
        # report check pass vacuously here is exactly the fake-success this tier exists
        # to catch. Its deliverable is the transcripts.
        assert_transcripts_present(out, floor=1)
        _assert_silence_was_named(event)
        assert_reid_keys_not_shareable(out)
    except InvariantError as e:
        return CellResult(cell_id, CellOutcome.FAIL_BLOCKING, redact(str(e)))
    except (OSError, ValueError) as e:
        return CellResult(cell_id, CellOutcome.FAIL_BLOCKING, redact(f"invariant read error: {e}"))

    if proc.returncode != 0:
        return CellResult(cell_id, CellOutcome.FAIL_EXPECTED, f"exit {proc.returncode}")
    return CellResult(cell_id, CellOutcome.PASS, "1 transcribed, 1 silent session named")


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
    p.add_argument(
        "--run-transcribe",
        action="store_true",
        help="run the no-key transcribe cell (free, live, ~3s)",
    )
    p.add_argument("--run-local", action="store_true", help="run the local Ollama cell (free)")
    p.add_argument("--run-cloud", action="store_true", help="run cloud cells (keys + spend)")
    p.add_argument("--input", help="input folder for provider analyze cells")
    args = p.parse_args()
    if not (args.self_test or args.run_transcribe or args.run_local or args.run_cloud):
        # The free proof is both: a committed fixture read, and one live run that needs
        # no credentials. Before the second existed, a keyless machine's whole matrix
        # exercised no pipeline code at all.
        args.self_test = True
        args.run_transcribe = True
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
