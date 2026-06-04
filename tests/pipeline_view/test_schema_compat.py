"""Schema-compatibility guarantees for the PipelineView payload.

These version numbers are `schema_version` values (the JSON payload contract
counter), NOT the pipeline-view feature rungs — the two number lines are
decoupled (feature v2 happens to carry schema_version 4; see
docs/design-pipeline-view.md §Schema versioning).

Schema history: schema_version 1 (read-only) → 2 (llm_summary + per-stage
alternatives) → 3 (quality fields) → 4 (per-(provider, model) grain;
llm_summary removed, rows re-keyed to provider_id/model_id/reason_key).
Schema 4 is the first *breaking* row shape — older row field names don't
survive — so these tests pin two narrower promises that still hold:

  1. A schema-1-era payload (catalogue entries with no `alternatives`) still
     validates under the current model — `alternatives` stays optional.
  2. Within schema 4, the newest optional row fields default cleanly when a
     producer omits them (forward-compatibility for partial producers).

Plus the two live scenarios round-trip byte-equal through Pydantic.
"""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.pipeline_view.render import PipelineView

_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "pipeline-view-contract.json"
)

# Row fields that are optional in schema 4 (all but the four load-bearing ones).
_OPTIONAL_ROW_FIELDS = {
    "model_id",
    "display_key",
    "provider_display_key",
    "publisher",
    "reason_key",
    "action_key",
    "quality",
    "quality_note",
    "quality_source",
    "default",
    "recommended",
    "synthesised",
}


def _scenario(name: str) -> dict:
    data = json.loads(_FIXTURE.read_text())
    return data["scenarios"][name]


def _v1_shape_payload() -> dict:
    """Strip v2+ stage fields to simulate a v1-era JSON payload.

    Removes per-stage `alternatives`, `chosen_id`, `chosen_model_id`, and the
    host probes that arrived after v1.
    """
    scenario = _scenario("claude_apple_silicon_keys_present")
    catalogue = [
        {
            k: v
            for k, v in entry.items()
            if k not in {"chosen_id", "chosen_model_id", "alternatives"}
        }
        for entry in scenario["catalogue"]
    ]
    host = {
        k: v
        for k, v in scenario["host"].items()
        if k not in {"os_version", "installed_packages", "ollama_models"}
    }
    return {"catalogue": catalogue, "host": host}


def test_v1_shape_parses_under_current_schema() -> None:
    """A v1-era payload (no alternatives) must still validate."""
    view = PipelineView.model_validate(_v1_shape_payload())
    assert view.schema_version == 4  # default at this rung
    for entry in view.catalogue:
        assert entry.alternatives == []
        assert entry.chosen_id is None
        assert entry.chosen_model_id is None
    assert view.host.os_version is None
    assert view.host.installed_packages == {}
    assert view.host.ollama_models == []


def test_optional_row_fields_default_when_omitted() -> None:
    """A schema-4 producer that emits only the load-bearing row fields still
    validates — the rest default (forward-compat for partial producers)."""
    scenario = _scenario("claude_apple_silicon_keys_present")
    catalogue = []
    for entry in scenario["catalogue"]:
        minimal_rows = [
            {k: v for k, v in row.items() if k not in _OPTIONAL_ROW_FIELDS}
            for row in entry["alternatives"]
        ]
        catalogue.append({**entry, "alternatives": minimal_rows})
    view = PipelineView.model_validate(
        {
            "schema_version": scenario["schema_version"],
            "catalogue": catalogue,
            "host": scenario["host"],
        }
    )
    for stage in view.catalogue:
        for row in stage.alternatives:
            assert row.model_id is None
            assert row.quality is None
            assert row.publisher is None
            assert row.default is False
            assert row.recommended is False
            assert row.synthesised is False


def test_current_round_trip_preserves_catalogue() -> None:
    """Full current-schema payload round-trips byte-equal through Pydantic."""
    scenario = _scenario("claude_apple_silicon_keys_present")
    view = PipelineView.model_validate(
        {
            "schema_version": scenario["schema_version"],
            "catalogue": scenario["catalogue"],
            "host": scenario["host"],
        }
    )
    reserialised = json.loads(view.model_dump_json())
    assert reserialised["schema_version"] == 4
    for orig, round_tripped in zip(
        scenario["catalogue"], reserialised["catalogue"], strict=True
    ):
        assert round_tripped == orig


def test_linux_scenario_round_trips() -> None:
    """The linux_cpu_no_keys scenario validates; every LLM cell ✗."""
    scenario = _scenario("linux_cpu_no_keys")
    view = PipelineView.model_validate(
        {
            "schema_version": scenario["schema_version"],
            "catalogue": scenario["catalogue"],
            "host": scenario["host"],
        }
    )
    assert view.host.os == "Linux"
    assert view.host.os_version is None
    for stage in (s for s in view.catalogue if s.kind == "llm"):
        assert all(not row.available for row in stage.alternatives), (
            "linux_cpu_no_keys has no provider keys + no ollama; every LLM ✗"
        )
        apple = next(r for r in stage.alternatives if r.provider_id == "apple_fm")
        assert "apple_fm_check_desktop" in (apple.reason_key or "")
