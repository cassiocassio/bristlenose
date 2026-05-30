"""Schema-additive guarantee: v1-shape JSON parses cleanly under v2 Pydantic.

The plan claims `schema_version: 1 → 2` is additive — v1 consumers can read
v2 payloads (ignoring the new fields), and v1-shape payloads can still be
parsed by the v2 Pydantic model. This test makes that promise load-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

from bristlenose.pipeline_view.render import PipelineView

_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "pipeline-view-contract.json"
)


def _v1_shape_payload() -> dict:
    """Strip v1.5-only fields to simulate a v1-era JSON payload.

    Removes: schema_version, llm_summary, per-stage alternatives, chosen_id,
    host.os_version, host.installed_packages.
    """
    data = json.loads(_FIXTURE.read_text())
    scenario = data["scenarios"]["claude_apple_silicon_keys_present"]
    catalogue = []
    for entry in scenario["catalogue"]:
        v1_entry = {
            k: v
            for k, v in entry.items()
            if k not in {"chosen_id", "alternatives"}
        }
        catalogue.append(v1_entry)
    host = {
        k: v
        for k, v in scenario["host"].items()
        if k not in {"os_version", "installed_packages"}
    }
    return {"catalogue": catalogue, "host": host}


def test_v1_shape_parses_under_v2_schema() -> None:
    """A v1-era payload (no alternatives, no llm_summary) must still validate."""
    payload = _v1_shape_payload()
    view = PipelineView.model_validate(payload)
    assert view.schema_version == 2  # default
    assert view.llm_summary == []
    for entry in view.catalogue:
        assert entry.alternatives == []
        assert entry.chosen_id is None
    # host fields default to None for missing optional ones
    assert view.host.os_version is None
    assert view.host.installed_packages == {}


def test_v2_round_trip_preserves_alternatives_and_summary() -> None:
    """Full v2 payload round-trips byte-equal through the Pydantic model."""
    data = json.loads(_FIXTURE.read_text())
    scenario = data["scenarios"]["claude_apple_silicon_keys_present"]
    view = PipelineView.model_validate(
        {
            "schema_version": scenario["schema_version"],
            "catalogue": scenario["catalogue"],
            "llm_summary": scenario["llm_summary"],
            "host": scenario["host"],
        }
    )
    reserialised = json.loads(view.model_dump_json())
    assert reserialised["schema_version"] == 2
    assert reserialised["llm_summary"] == scenario["llm_summary"]
    for orig, round_tripped in zip(
        scenario["catalogue"], reserialised["catalogue"], strict=True
    ):
        assert round_tripped == orig


def test_linux_scenario_round_trips() -> None:
    """The linux_cpu_no_keys scenario validates as a complete v2 payload."""
    data = json.loads(_FIXTURE.read_text())
    scenario = data["scenarios"]["linux_cpu_no_keys"]
    view = PipelineView.model_validate(
        {
            "schema_version": scenario["schema_version"],
            "catalogue": scenario["catalogue"],
            "llm_summary": scenario["llm_summary"],
            "host": scenario["host"],
        }
    )
    assert view.host.os == "Linux"
    assert view.host.os_version is None
    by_id = {a.id: a for a in view.llm_summary}
    assert all(not e.available for e in view.llm_summary), (
        "linux_cpu_no_keys has no provider keys + no ollama; every LLM ✗"
    )
    assert "apple_fm_check_desktop" in (by_id["apple_fm"].reason or "")
