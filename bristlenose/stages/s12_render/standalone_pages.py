"""Standalone HTML pages — codebook and analysis."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from bristlenose.stages.s12_render.html_helpers import (
    _document_shell_open,
    _esc,
    _footer_html,
    _report_header_html,
)
from bristlenose.stages.s12_render.theme_assets import (
    _get_analysis_js,
    _get_codebook_js,
    _jinja_env,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Codebook page
# ---------------------------------------------------------------------------


def _render_codebook_page(
    project_name: str,
    output_dir: Path,
    color_scheme: str = "auto",
) -> Path:
    """Render the codebook page as a standalone HTML file.

    The codebook page sits at the output root (same level as the report),
    opened in a new window via the toolbar Codebook button.
    """
    from bristlenose.output_paths import OutputPaths
    from bristlenose.utils.text import slugify

    paths = OutputPaths(output_dir, project_name)
    slug = slugify(project_name)

    parts: list[str] = []
    _w = parts.append

    _w(_document_shell_open(
        title=f"Codebook \u2014 {_esc(project_name)}",
        css_href="assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    # Header (same layout as report — logos at assets/)
    _w(_report_header_html(
        assets_prefix="assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Codebook",
    ))

    # Back link to report
    report_filename = f"bristlenose-{slug}-report.html"
    _w('<nav class="transcript-back">')
    _w(f'<a href="{report_filename}">')
    _w(f"&larr; {_esc(project_name)} Research Report</a>")
    _w("</nav>")

    _w("<h1>Codebook</h1>")

    # Description and interactive grid container (populated by codebook.js)
    _w('<p class="codebook-description">')
    _w("Drag tags between groups to reclassify. ")
    _w("Drag onto another tag to merge. Sorted by frequency.")
    _w("</p>")
    _w('<div class="codebook-grid" id="codebook-grid"></div>')

    _w("</article>")
    _w(_footer_html())

    # JavaScript — codebook data model + modal + storage for cross-window sync
    _w("<script>")
    _w("(function() {")
    _w(_get_codebook_js())
    _w("initCodebook();")
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    page_path = paths.codebook_file
    page_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Wrote codebook page: %s", page_path)
    return page_path


# ---------------------------------------------------------------------------
# Analysis page
# ---------------------------------------------------------------------------


def _serialize_matrix(matrix: object) -> dict:
    """Convert a Matrix dataclass to a JSON-friendly dict."""
    cells_dict: dict[str, dict] = {}
    for key, cell in matrix.cells.items():  # type: ignore[attr-defined]
        cells_dict[key] = {
            "count": cell.count,
            "participants": cell.participants,
            "intensities": cell.intensities,
        }
    return {
        "cells": cells_dict,
        "rowTotals": matrix.row_totals,  # type: ignore[attr-defined]
        "colTotals": matrix.col_totals,  # type: ignore[attr-defined]
        "grandTotal": matrix.grand_total,  # type: ignore[attr-defined]
        "rowLabels": matrix.row_labels,  # type: ignore[attr-defined]
    }


def _serialize_analysis(analysis: object) -> str:
    """Serialize AnalysisResult for JS injection."""
    # Collect all participant IDs across all signals
    all_pids: set[str] = set()
    for s in analysis.signals:  # type: ignore[attr-defined]
        all_pids.update(s.participants)
    # Sort participant IDs naturally (p1, p2, ..., p10)
    sorted_pids = sorted(all_pids, key=lambda p: (p[0], int(p[1:]) if p[1:].isdigit() else 0))

    data = {
        "signals": [
            {
                "location": s.location,
                "sourceType": s.source_type,
                "sentiment": s.sentiment,
                "count": s.count,
                "participants": s.participants,
                "nEff": round(s.n_eff, 2),
                "meanIntensity": round(s.mean_intensity, 2),
                "concentration": round(s.concentration, 2),
                "compositeSignal": round(s.composite_signal, 4),
                "confidence": s.confidence,
                "flag": s.flag,
                "quotes": [
                    {
                        "text": q.text,
                        "pid": q.participant_id,
                        "sessionId": q.session_id,
                        "startSeconds": q.start_seconds,
                        "intensity": q.intensity,
                        "segmentIndex": q.segment_index,
                    }
                    for q in s.quotes
                ],
            }
            for s in analysis.signals  # type: ignore[attr-defined]
        ],
        "sectionMatrix": _serialize_matrix(analysis.section_matrix),  # type: ignore[attr-defined]
        "themeMatrix": _serialize_matrix(analysis.theme_matrix),  # type: ignore[attr-defined]
        "totalParticipants": analysis.total_participants,  # type: ignore[attr-defined]
        "sentiments": analysis.sentiments,  # type: ignore[attr-defined]
        "participantIds": sorted_pids,
    }
    return json.dumps(data, separators=(",", ":"))


def _render_analysis_page(
    project_name: str,
    output_dir: Path,
    analysis: object,
    color_scheme: str = "auto",
) -> Path:
    """Render the analysis page as a standalone HTML file.

    The analysis page sits at the output root (same level as the report),
    opened in a new window via the toolbar Analysis button.
    """
    from bristlenose.output_paths import OutputPaths
    from bristlenose.utils.text import slugify

    paths = OutputPaths(output_dir, project_name)
    slug = slugify(project_name)

    parts: list[str] = []
    _w = parts.append

    _w(_document_shell_open(
        title=f"Analysis \u2014 {_esc(project_name)}",
        css_href="assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    _w(_report_header_html(
        assets_prefix="assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Analysis",
    ))

    # Back link to report
    report_filename = f"bristlenose-{slug}-report.html"
    _w('<nav class="transcript-back">')
    _w(f'<a href="{report_filename}">')
    _w(f"&larr; {_esc(project_name)} Research Report</a>")
    _w("</nav>")

    # Template body
    _w(_jinja_env.get_template("analysis.html").render())

    _w("</article>")
    _w(_footer_html())

    # JavaScript with injected data
    _w("<script>")
    _w("(function() {")
    _w(f"var BRISTLENOSE_ANALYSIS = {_serialize_analysis(analysis)};")
    report_fn_js = report_filename.replace("'", "\\'")
    _w(f"var BRISTLENOSE_REPORT_FILENAME = '{report_fn_js}';")
    _w(_get_analysis_js())
    _w("initAnalysis();")
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    page_path = paths.analysis_file
    page_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Wrote analysis page: %s", page_path)
    return page_path
