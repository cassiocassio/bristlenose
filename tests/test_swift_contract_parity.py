"""Optionality parity between the Python event models and their Swift mirror.

`desktop/Bristlenose/Bristlenose/PipelineSummary.swift` is a hand-maintained
mirror of `bristlenose/events.py`. Hand-maintained mirrors drift, and one
particular drift is silently catastrophic:

    Python:  duration_ms: int | None = None      # null on the wire
    Swift:   var durationMs: Int                 # non-optional

`JSONDecoder` throws on `null -> Int`, and `EventLogReader` decodes at **event**
level with `try?`, so the whole `run_completed` line became undecodable. The
reader then fell back to that run's `run_started`, found the PID gone, and
reported a *completed* run as `.failed("Analysis stopped unexpectedly.")` —
which `applyScanResult` then protected across relaunch, while the report sat
there complete and correct. It fired on the everyday path (any stage that was
fully cached emits a null duration) and hid for months because every scenario in
`tests/fixtures/pipeline-summary-contract.json` happened to carry a real value.

Round-trip fixtures only catch the shapes they contain. This catches the class:
for every field both sides decode, optionality must agree. Sibling of
`test_cause_category_matches_swift_enum`, which pins the enum the same way.

Deliberately NOT a codegen step — one contract, four structs. If a third mirror
appears, revisit.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel

from bristlenose.events import Cause, PipelineSummary, StageFailure, StageOutcome

SWIFT_MIRROR = (
    Path(__file__).resolve().parents[1]
    / "desktop/Bristlenose/Bristlenose/PipelineSummary.swift"
)

# Swift struct name -> Python model. Names differ where the two sides chose
# different words for the same wire shape (`StageFailure` / `SessionFailure`).
PAIRS: list[tuple[str, type[BaseModel]]] = [
    ("PipelineSummary", PipelineSummary),
    ("StageOutcome", StageOutcome),
    ("SessionFailure", StageFailure),
    ("Cause", Cause),
]

# `var name: Type` — but NOT computed properties, which open a brace instead of
# ending the line (`var allBuckets: [...] { ... }`).
_STORED_PROP = re.compile(r"^\s*var\s+(\w+)\s*:\s*([^{=\n]+?)\s*$", re.MULTILINE)
_CODING_KEY = re.compile(r"^\s*case\s+(.+)$", re.MULTILINE)
# Anchored to line start so English prose in a doc comment ("...this struct is
# the full per-session shape...") can't be mistaken for a declaration. That
# exact sentence broke the first version of this parser: the bogus match's
# `[^{]*` ran on to the NEXT struct's brace, so `struct Cause` was swallowed and
# silently never checked. Comments are stripped as well — belt and braces.
_STRUCT_DECL = re.compile(r"^[ \t]*(?:public\s+|final\s+)*struct\s+(\w+)[^{]*\{", re.MULTILINE)


def _strip_comments(source: str) -> str:
    """Blank out `//` comment tails, leaving string literals intact.

    Length-preserving (spaces, not deletion) so brace-matching offsets computed
    on the stripped text stay valid against it.
    """
    out = list(source)
    in_string = False
    i = 0
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
            while i < len(source) and source[i] != "\n":
                out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def _swift_structs(source: str) -> dict[str, str]:
    """Split the file into `struct Name { ... }` bodies by brace-matching."""
    source = _strip_comments(source)
    out: dict[str, str] = {}
    for match in _STRUCT_DECL.finditer(source):
        name = match.group(1)
        depth, i = 1, match.end()
        while i < len(source) and depth:
            depth += {"{": 1, "}": -1}.get(source[i], 0)
            i += 1
        out[name] = source[match.end():i - 1]
    return out


def _coding_keys(body: str) -> dict[str, str]:
    """Swift property name -> wire key, from the `enum CodingKeys` block.

    Absent mapping means the property name *is* the wire key.
    """
    block = re.search(r"enum\s+CodingKeys[^{]*\{([^}]*)\}", body)
    if not block:
        return {}
    mapping: dict[str, str] = {}
    for line in _CODING_KEY.findall(block.group(1)):
        # `case durationMs = "duration_ms"` or `case attempted, succeeded`
        for part in line.split(","):
            part = part.strip().rstrip(",")
            if not part:
                continue
            if "=" in part:
                prop, wire = part.split("=", 1)
                mapping[prop.strip()] = wire.strip().strip('"')
            else:
                mapping[part] = part
    return mapping


def _swift_optionality(body: str) -> dict[str, bool]:
    """Wire key -> is the Swift declaration optional."""
    keys = _coding_keys(body)
    fields: dict[str, bool] = {}
    for prop, type_str in _STORED_PROP.findall(body):
        type_str = type_str.strip()
        # Trailing `?` on the *whole* type is what makes it decode-tolerant of
        # null. `[Thing]?` counts; `[Thing?]` (optional elements) does not.
        fields[keys.get(prop, prop)] = type_str.endswith("?")
    return fields


def _python_optionality(model: type[BaseModel]) -> dict[str, bool]:
    """Wire key -> does the annotation admit None (i.e. can emit/accept null)."""
    out: dict[str, bool] = {}
    for name, field in model.model_fields.items():
        # `get_args` covers BOTH union spellings. `get_origin(x) is Union` does
        # NOT: a PEP-604 `str | None` has origin `types.UnionType`, so the
        # typing.Union check silently reported every modern optional field as
        # required — a test that would have passed while checking nothing.
        out[field.alias or name] = type(None) in get_args(field.annotation)
    return out


@pytest.fixture(scope="module")
def structs() -> dict[str, str]:
    assert SWIFT_MIRROR.is_file(), f"Swift mirror moved? {SWIFT_MIRROR}"
    return _swift_structs(SWIFT_MIRROR.read_text(encoding="utf-8"))


def test_parser_actually_finds_the_structs(structs: dict[str, str]) -> None:
    """Guard against the parser silently matching nothing.

    Without this, a regex that stops working turns every assertion below into a
    vacuous pass — the exact "test passes because it tested nothing" failure this
    file exists to prevent elsewhere.
    """
    for swift_name, _ in PAIRS:
        assert swift_name in structs, f"no `struct {swift_name}` found in the mirror"


@pytest.mark.parametrize(("swift_name", "model"), PAIRS, ids=[p[0] for p in PAIRS])
def test_optionality_matches(
    structs: dict[str, str], swift_name: str, model: type[BaseModel]
) -> None:
    swift = _swift_optionality(structs[swift_name])
    python = _python_optionality(model)

    shared = sorted(set(swift) & set(python))
    # A field Swift doesn't declare is fine — the contract is schema-additive and
    # Swift ignores what it doesn't need. What must never diverge is the
    # optionality of anything Swift *does* decode.
    assert shared, (
        f"{swift_name}: no fields in common with {model.__name__} — the parse or "
        f"the pairing is broken. Swift saw {sorted(swift)}, Python {sorted(python)}."
    )

    mismatches = [
        f"  {key}: Python {'| None' if python[key] else 'required'} "
        f"vs Swift {'optional' if swift[key] else 'non-optional'}"
        for key in shared
        if swift[key] != python[key]
    ]
    assert not mismatches, (
        f"{swift_name} ↔ {model.__name__} optionality drift:\n"
        + "\n".join(mismatches)
        + "\n\nA Python field typed `| None` writes a literal null (terminus "
        "events are written with exclude_none=False). A non-optional Swift "
        "property cannot decode that null, and because EventLogReader decodes "
        "whole events with `try?`, the failure takes the entire event with it. "
        "Make the Swift property optional, and add a fixture scenario in "
        "tests/fixtures/pipeline-summary-contract.json that actually carries "
        "the null."
    )


def test_duration_ms_specifically_admits_null(structs: dict[str, str]) -> None:
    """The field that taught us this lesson. Named so a future edit trips here
    with the history attached rather than rediscovering it in the field."""
    assert _swift_optionality(structs["StageOutcome"])["duration_ms"], (
        "StageOutcome.durationMs must stay optional: a fully-cached stage emits "
        "duration_ms: null (null means 'didn't run', distinct from 0 = 'ran "
        "instantly'), and a non-optional Int silently broke every diagnostic on "
        "the everyday re-analyse path."
    )
