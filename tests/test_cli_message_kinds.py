"""Tests for CLI MessageKind wiring.

Locks the boundary: ``cli_prefix`` markup shape, and that the four
``_print_*`` wrappers in ``bristlenose.pipeline`` route through
``_print_stage`` with the right kind.
"""

from __future__ import annotations

import io
from unittest.mock import patch

from rich.console import Console

from bristlenose import cli, pipeline
from bristlenose.ui_kinds import CLI_COLOUR, CLI_GLYPH, MessageKind, cli_prefix


def _capture(fn, *args, **kwargs) -> str:
    """Run ``fn`` with the module's ``console`` redirected to a string buffer."""
    buf = io.StringIO()
    # highlight=False keeps numeric/keyword auto-colouring from splitting words
    # like "0.4s" across ANSI segments; force_terminal=True keeps the colour codes
    # we want to assert on.
    captured = Console(
        file=buf, force_terminal=True, width=80, color_system="truecolor", highlight=False
    )
    target = kwargs.pop("_target", pipeline)
    with patch.object(target, "console", captured):
        fn(*args, **kwargs)
    return buf.getvalue()


def test_cli_prefix_success_markup() -> None:
    """Locks the Rich markup shape so popover-mirroring changes can't drift the CLI."""
    assert cli_prefix(MessageKind.SUCCESS) == "[green]✓[/green]"
    assert cli_prefix(MessageKind.ERROR) == "[red]✗[/red]"
    assert cli_prefix(MessageKind.WARNING) == "[yellow]⚠[/yellow]"
    assert cli_prefix(MessageKind.SKIPPED) == "[dim]—[/dim]"
    assert cli_prefix(MessageKind.INFO) == "[cyan]ℹ[/cyan]"


def test_cli_prefix_uses_glyph_and_colour_tables() -> None:
    """Every kind in the enum has glyph + colour entries."""
    for kind in MessageKind:
        assert kind in CLI_GLYPH
        assert kind in CLI_COLOUR
        # cli_prefix wraps the glyph in the colour
        prefix = cli_prefix(kind)
        assert CLI_GLYPH[kind] in prefix
        assert f"[{CLI_COLOUR[kind]}]" in prefix


def test_print_stage_success_renders_green_check() -> None:
    out = _capture(pipeline._print_stage, "Did the thing", MessageKind.SUCCESS, 0.42)
    assert "✓" in out
    assert "Did the thing" in out
    assert "0.4s" in out


def test_print_stage_error_renders_red_cross() -> None:
    out = _capture(pipeline._print_stage, "Broke it", MessageKind.ERROR, 1.5)
    assert "✗" in out
    assert "Broke it" in out


def test_print_stage_skipped_renders_dim_dash() -> None:
    out = _capture(pipeline._print_stage, "Not run", MessageKind.SKIPPED)
    assert "—" in out
    assert "Not run" in out


def test_print_stage_suffix_replaces_time() -> None:
    """Cached steps render ``(cached)`` instead of a duration."""
    out = _capture(pipeline._print_stage, "Cached step", MessageKind.SUCCESS, suffix="(cached)")
    assert "(cached)" in out
    assert "Cached step" in out


def test_print_cached_step_uses_success_with_cached_suffix() -> None:
    out = _capture(pipeline._print_cached_step, "Reused step")
    assert "✓" in out
    assert "(cached)" in out
    assert "Reused step" in out


def test_print_step_wrapper_routes_to_success() -> None:
    out = _capture(pipeline._print_step, "Step done", 1.0)
    assert "✓" in out
    assert "Step done" in out


def test_print_warn_step_wrapper_routes_to_warning() -> None:
    out = _capture(pipeline._print_warn_step, "Partial", 1.0)
    assert "⚠" in out
    assert "Partial" in out


def test_print_error_step_wrapper_routes_to_error() -> None:
    out = _capture(pipeline._print_error_step, "Failed", 1.0)
    assert "✗" in out
    assert "Failed" in out


def test_cli_say_prefixes_glyph() -> None:
    out = _capture(cli._say, MessageKind.SUCCESS, "Stored", _target=cli)
    assert "✓" in out
    assert "Stored" in out


def test_cli_say_indent_is_applied() -> None:
    out = _capture(cli._say, MessageKind.WARNING, "Heads up", _target=cli, indent="  ")
    # indent precedes the glyph
    assert out.startswith("  ") or "  ⚠" in out
