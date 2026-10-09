"""read_pipeline_metadata returns a dict, or {} for anything it cannot use."""

from __future__ import annotations

from pathlib import Path

from bristlenose.stages.s12_render_output import read_pipeline_metadata


def _write(output_dir: Path, text: str) -> None:
    d = output_dir / ".bristlenose" / "intermediate"
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(text, encoding="utf-8")


def test_reads_object(tmp_path: Path) -> None:
    _write(tmp_path, '{"project_name": "Acme"}')
    assert read_pipeline_metadata(tmp_path) == {"project_name": "Acme"}


def test_non_object_json_is_empty(tmp_path: Path) -> None:
    # Valid JSON that is not an object used to come back as-is, and the CLI
    # caller's `meta.get(...)` then raised AttributeError on a list.
    _write(tmp_path, '["Acme"]')
    assert read_pipeline_metadata(tmp_path) == {}
