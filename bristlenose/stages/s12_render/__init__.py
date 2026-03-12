"""Render package — HTML report generation (deprecated static path).

Public API:
    render_html()             — Generate the full static HTML report
    render_transcript_pages() — Generate per-session transcript HTML pages
"""

from bristlenose.stages.s12_render.report import render_html
from bristlenose.stages.s12_render.transcript_pages import render_transcript_pages

__all__ = ["render_html", "render_transcript_pages"]
