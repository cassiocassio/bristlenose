"""Dev-only endpoints for visual parity testing.

Registered only when ``bristlenose serve --dev`` is active.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from html import escape as _esc
from pathlib import Path as _Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from bristlenose.server.journey import derive_journeys
from bristlenose.server.models import (
    Person,
    Project,
    Quote,
    SessionSpeaker,
)
from bristlenose.server.models import (
    Session as SessionModel,
)
from bristlenose.stages.s12_render.sentiment import _render_sentiment_sparkline
from bristlenose.stages.s12_render.theme_assets import _jinja_env
from bristlenose.utils.markdown import format_finder_date, format_finder_filename

router = APIRouter(prefix="/api/dev")


# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


# ---------------------------------------------------------------------------
# Helpers (mirroring sessions.py but producing Jinja2 template dicts)
# ---------------------------------------------------------------------------

_SPEAKER_PREFIX_ORDER = {"m": 0, "p": 1, "o": 2}


def _speaker_sort_key(sp: SessionSpeaker) -> tuple[int, int]:
    code = sp.speaker_code
    prefix = _SPEAKER_PREFIX_ORDER.get(code[0], 3) if code else 3
    num = int(code[1:]) if len(code) > 1 and code[1:].isdigit() else 0
    return (prefix, num)




def _aggregate_sentiments(
    db: Session,
    project_id: int,
) -> dict[str, dict[str, int]]:
    quotes = db.query(Quote).filter_by(project_id=project_id).all()
    result: dict[str, dict[str, int]] = {}
    for q in quotes:
        if q.sentiment:
            if q.session_id not in result:
                result[q.session_id] = {}
            result[q.session_id][q.sentiment] = (
                result[q.session_id].get(q.sentiment, 0) + 1
            )
    return result


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "\u2014"
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Sessions table HTML (Jinja2-rendered fragment)
# ---------------------------------------------------------------------------


@router.get("/sessions-table-html", response_class=HTMLResponse)
def sessions_table_html(
    project_id: int = Query(default=1),
    db: Session = Depends(_get_db),  # type: ignore[assignment]
) -> str:
    """Render the sessions table using the Jinja2 template.

    Returns the same HTML fragment that the ``render/`` package produces for the
    static report.  Used by the visual diff page to compare against the
    React ``SessionsTable`` component.
    """
    try:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        sessions = (
            db.query(SessionModel)
            .filter_by(project_id=project_id)
            .order_by(SessionModel.session_number)
            .all()
        )

        participant_screens = derive_journeys(db, project_id)
        sentiment_by_session = _aggregate_sentiments(db, project_id)

        # Collect all moderator/observer codes across all sessions.
        all_moderator_codes: list[str] = []
        all_observer_codes: list[str] = []
        for sess in sessions:
            for sp in sess.session_speakers:
                if sp.speaker_code.startswith("m") and sp.speaker_code not in all_moderator_codes:
                    all_moderator_codes.append(sp.speaker_code)
                elif sp.speaker_code.startswith("o") and sp.speaker_code not in all_observer_codes:
                    all_observer_codes.append(sp.speaker_code)
        all_moderator_codes.sort(
            key=lambda c: int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        )
        all_observer_codes.sort(
            key=lambda c: int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        )

        omit_moderators_from_rows = len(all_moderator_codes) == 1

        # Moderator header HTML
        def _resolve_name(sp: SessionSpeaker) -> str:
            person = db.get(Person, sp.person_id)
            if person:
                return person.short_name or person.full_name or ""
            return ""

        # Build moderator header
        moderator_header = ""
        if all_moderator_codes:
            parts: list[str] = []
            for code in all_moderator_codes:
                # Find the speaker in any session
                sp = (
                    db.query(SessionSpeaker)
                    .filter_by(speaker_code=code)
                    .first()
                )
                if sp:
                    name = _resolve_name(sp)
                    name_html = f" {_esc(name)}" if name else ""
                    parts.append(
                        f'<span class="bn-person-badge">'
                        f'<span class="badge">{_esc(code)}</span>{name_html}'
                        f"</span>"
                    )
            moderator_header = "Moderated by " + _oxford_list(parts)

        # Build observer header
        observer_header = ""
        if all_observer_codes:
            parts = []
            for code in all_observer_codes:
                sp = (
                    db.query(SessionSpeaker)
                    .filter_by(speaker_code=code)
                    .first()
                )
                if sp:
                    name = _resolve_name(sp)
                    name_html = f" {_esc(name)}" if name else ""
                    parts.append(
                        f'<span class="bn-person-badge">'
                        f'<span class="badge">{_esc(code)}</span>{name_html}'
                        f"</span>"
                    )
            noun = "Observer" if len(parts) == 1 else "Observers"
            observer_header = f"{noun}: " + _oxford_list(parts)

        now = datetime.now(tz=timezone.utc)
        rows: list[dict[str, object]] = []
        for sess in sessions:
            sid = sess.session_id
            session_num = sid[1:] if len(sid) > 1 and sid[1:].isdigit() else sid

            # Date
            start = _esc(format_finder_date(sess.session_date, now=now)) if sess.session_date else "\u2014"

            # Duration
            duration = _format_duration(sess.duration_seconds)

            # Source file
            source = "&mdash;"
            source_folder_uri = ""
            if sess.source_files:
                sf = sess.source_files[0]
                full_name = _Path(sf.path).name
                display_fname = format_finder_filename(full_name)
                title_attr = f' title="{_esc(full_name)}"' if display_fname != full_name else ""
                source = f"<span{title_attr}>{_esc(display_fname)}</span>"

            # Speakers
            speakers_list: list[dict[str, str]] = []
            for sp in sorted(sess.session_speakers, key=_speaker_sort_key):
                if omit_moderators_from_rows and sp.speaker_code.startswith("m"):
                    continue
                name = _resolve_name(sp)
                display = _esc(name) if name else ""
                speakers_list.append({"code": _esc(sp.speaker_code), "name": display})

            # Journey
            session_pids = [
                sp.speaker_code
                for sp in sess.session_speakers
                if sp.speaker_code.startswith("p")
            ]
            journey_labels: list[str] = []
            for pid in session_pids:
                for label in participant_screens.get(pid, []):
                    if label not in journey_labels:
                        journey_labels.append(label)
            journey = " &rarr; ".join(journey_labels) if journey_labels else ""

            # Sparkline
            sparkline = _render_sentiment_sparkline(sentiment_by_session.get(sid, {}))

            rows.append({
                "sid": _esc(sid),
                "num": _esc(session_num),
                "speakers_list": speakers_list,
                "start": start,
                "duration": duration,
                "source": source,
                "journey": journey,
                "sentiment_sparkline": sparkline,
                "has_media": sess.has_media,
                "source_folder_uri": source_folder_uri,
            })

        html = _jinja_env.get_template("session_table.html").render(
            rows=rows,
            moderator_header=moderator_header,
            observer_header=observer_header,
        ).rstrip("\n")
        return html
    finally:
        db.close()


# ---------------------------------------------------------------------------
# System info for About tab developer section
# ---------------------------------------------------------------------------


def _label_from_filename(name: str) -> str:
    """Turn 'mockup-codebook-panel.html' into 'Codebook panel'."""
    stem = _Path(name).stem
    for prefix in ("mockup-", "focus-", "dashboard-"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    return stem.replace("-", " ").capitalize()


def _discover_design_files() -> list[dict[str, object]]:
    """Auto-discover HTML files in mockups, experiments, design-system dirs."""
    repo_root = _Path(__file__).resolve().parent.parent.parent.parent
    design_dirs: list[tuple[str, str, _Path]] = [
        ("Mockups", "/mockups", repo_root / "docs" / "mockups"),
        ("Experiments", "/experiments", repo_root / "experiments"),
        ("Design System", "/design-system", repo_root / "docs" / "design-system"),
    ]
    sections: list[dict[str, object]] = []
    for heading, url_prefix, dir_path in design_dirs:
        if not dir_path.is_dir():
            continue
        html_files = sorted(dir_path.glob("*.html"))
        if not html_files:
            continue
        items = [
            {"label": _label_from_filename(f.name), "url": f"{url_prefix}/{f.name}"}
            for f in html_files
        ]
        sections.append({"heading": heading, "items": items})
    return sections


@router.get("/info")
def dev_info(request: Request) -> dict[str, object]:
    """System info for the About tab developer section."""
    from bristlenose.server.db import Base

    db_url: str = getattr(request.app.state, "db_url", "")
    db_path = db_url.removeprefix("sqlite:///") if db_url else "(in-memory)"

    return {
        "db_path": db_path,
        "table_count": len(Base.metadata.tables),
        "endpoints": [
            {
                "label": "Database Browser",
                "url": "/admin/",
                "description": "Browse and edit all 22 tables (SQLAdmin)",
            },
            {
                "label": "API Documentation",
                "url": "/api/docs",
                "description": "Interactive Swagger UI for all endpoints",
            },
            {
                "label": "Sessions API",
                "url": "/api/projects/1/sessions",
                "description": "Sessions list with speakers, journeys, sentiment",
            },
            {
                "label": "Sessions HTML",
                "url": "/api/dev/sessions-table-html?project_id=1",
                "description": "Jinja2-rendered sessions table (visual diff)",
            },
            {
                "label": "Visual Diff",
                "url": "http://localhost:5173/visual-diff.html",
                "description": "Side-by-side React vs Jinja2 comparison",
            },
            {
                "label": "Health Check",
                "url": "/api/health",
                "description": "System status and version",
            },
        ],
        "design_sections": _discover_design_files(),
    }


def _oxford_list(parts: list[str]) -> str:
    if len(parts) <= 1:
        return parts[0] if parts else ""
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


# ---------------------------------------------------------------------------
# Alpha telemetry stub
# ---------------------------------------------------------------------------
#
# Stands in for the real PHP endpoint at bristlenose.app/telemetry.php during
# Swift + React development.  Accepts the same batched payload the real
# endpoint will accept and appends one JSON line per event to a local file.
# Dev-only: mounted only when ``bristlenose serve --dev`` is active.
#
# The path is PID-scoped so (a) concurrent test runners don't clobber each
# other, (b) each server restart starts with a clean file. Old files orphan
# in the tempdir but the OS reaps them.

_TELEMETRY_MAX_EVENTS_PER_BATCH = 500


class TelemetryEventIn(BaseModel):
    """One tag-rejection event. Four fields only — see methodology doc."""

    model_config = ConfigDict(extra="forbid")

    tag_id: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=80)
    event_type: Literal["suggested", "accepted", "rejected", "edited"]
    researcher_id: str = Field(min_length=1, max_length=64)


class TelemetryBatchIn(BaseModel):
    """Request body for POST /api/dev/telemetry."""

    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEventIn] = Field(
        min_length=1,
        max_length=_TELEMETRY_MAX_EVENTS_PER_BATCH,
    )


def _dev_telemetry_path() -> _Path:
    return _Path(tempfile.gettempdir()) / f"bristlenose-dev-telemetry-{os.getpid()}.jsonl"


@router.post("/telemetry")
def dev_telemetry_post(batch: TelemetryBatchIn) -> dict[str, object]:
    """Append a batch of telemetry events to a local JSONL file.

    Same request shape as the real ``telemetry.php`` endpoint:
    ``{"events": [{"tag_id", "prompt_version", "event_type", "researcher_id"}, ...]}``.
    Rejects unknown fields and batches larger than
    ``_TELEMETRY_MAX_EVENTS_PER_BATCH``. Returns the JSONL path so the
    developer can tail it.
    """
    out_path = _dev_telemetry_path()
    with out_path.open("a", encoding="utf-8") as fp:
        for ev in batch.events:
            fp.write(json.dumps(ev.model_dump()) + "\n")

    return {
        "ok": True,
        "received": len(batch.events),
        "written_to": str(out_path),
    }


@router.get("/telemetry")
def dev_telemetry_get() -> dict[str, object]:
    """Return every event written to the local JSONL file (debug helper)."""
    out_path = _dev_telemetry_path()
    if not out_path.exists():
        return {"events": [], "path": str(out_path)}
    events: list[dict[str, object]] = []
    with out_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return {"events": events, "path": str(out_path)}


@router.delete("/telemetry")
def dev_telemetry_delete() -> dict[str, object]:
    """Truncate the local JSONL file (debug helper)."""
    out_path = _dev_telemetry_path()
    if out_path.exists():
        out_path.unlink()
    return {"ok": True, "path": str(out_path)}


# ---------------------------------------------------------------------------
# Codebook-lab — throwaway sandbox for the dynamic codebook builder experiment
# ---------------------------------------------------------------------------
#
# This is deliberately ugly and dev-only. It hangs the builder engine
# (server/codebook_builder.py) off a bare HTML page so we can PLAY with real
# project data — synthesise a prompt from a few quotes, hand-write one instead,
# scan for more like it, edit, re-scan — before committing to any UX. None of
# this writes to the DB; it operates on pasted text + the project's quotes.
#
# The point of the experiment (per the product conversation): from 50-word
# fragments the machine can only ever guess surface commonalities. So the lab
# makes BOTH paths first-class — "synthesise a draft" and "I'll write it myself"
# — so we can judge whether synthesis-from-fragments earns its keep against the
# researcher just writing the inclusion criteria in their own words.


class _LabPrompt(BaseModel):
    summary: str = ""
    definition: str = ""
    apply_when: str = ""
    not_this: str = ""


class _LabSynthRequest(BaseModel):
    tag_name: str = "untitled"
    example_texts: list[str] = Field(default_factory=list)


class _LabDecision(BaseModel):
    text: str
    reason: str = ""


class _LabRefineRequest(BaseModel):
    tag_name: str = "untitled"
    example_texts: list[str] = Field(default_factory=list)
    prompt: _LabPrompt = Field(default_factory=_LabPrompt)
    accepted: list[_LabDecision] = Field(default_factory=list)
    rejected: list[_LabDecision] = Field(default_factory=list)


class _LabCandidatesRequest(BaseModel):
    tag_name: str = "untitled"
    prompt: _LabPrompt = Field(default_factory=_LabPrompt)
    min_confidence: float = 0.5
    limit: int = 30
    exclude_texts: list[str] = Field(default_factory=list)


def _lab_settings():
    from bristlenose.config import load_settings

    return load_settings()


@router.get("/codebook-lab/tags")
def codebook_lab_tags(request: Request, project_id: int = 1) -> dict[str, object]:
    """List the project's tags with their coded quote texts (for picking exemplars)."""
    from bristlenose.server.models import QuoteTag, TagDefinition

    db = _get_db(request)
    try:
        rows = (
            db.query(TagDefinition.id, TagDefinition.name, Quote.text)
            .join(QuoteTag, QuoteTag.tag_definition_id == TagDefinition.id)
            .join(Quote, Quote.id == QuoteTag.quote_id)
            .filter(Quote.project_id == project_id)
            .all()
        )
        by_tag: dict[int, dict[str, object]] = {}
        for tid, name, text in rows:
            entry = by_tag.setdefault(tid, {"id": tid, "name": name, "quotes": []})
            entry["quotes"].append(text)  # type: ignore[union-attr]
        tags = sorted(by_tag.values(), key=lambda t: t["name"])  # type: ignore[index,arg-type]
        return {"tags": tags}
    finally:
        db.close()


@router.post("/codebook-lab/synthesize")
async def codebook_lab_synthesize(request: Request, body: _LabSynthRequest) -> dict[str, object]:
    """Synthesise a draft prompt from pasted example quotes (no DB writes)."""
    from bristlenose.server import codebook_builder as cb

    examples = [cb.ExampleQuote(text=t) for t in body.example_texts if t.strip()]
    if len(examples) < 2:
        raise HTTPException(status_code=400, detail="Paste at least 2 example quotes")
    draft = await cb.synthesize_prompt(body.tag_name, examples, _lab_settings())
    return {
        "summary": draft.summary, "definition": draft.definition,
        "apply_when": draft.apply_when, "not_this": draft.not_this,
        "version": draft.version,
    }


@router.post("/codebook-lab/refine")
async def codebook_lab_refine(request: Request, body: _LabRefineRequest) -> dict[str, object]:
    """Refine the prompt from accept/reject-with-reasons (no DB writes)."""
    from bristlenose.server import codebook_builder as cb

    examples = [cb.ExampleQuote(text=t) for t in body.example_texts if t.strip()]
    current = cb.PromptDraft(
        summary=body.prompt.summary, definition=body.prompt.definition,
        apply_when=body.prompt.apply_when, not_this=body.prompt.not_this,
    )
    draft = await cb.synthesize_prompt(
        body.tag_name, examples, _lab_settings(),
        current=current,
        accepted=[cb.DecisionFeedback(text=d.text, reason=d.reason) for d in body.accepted],
        rejected=[cb.DecisionFeedback(text=d.text, reason=d.reason) for d in body.rejected],
    )
    return {
        "summary": draft.summary, "definition": draft.definition,
        "apply_when": draft.apply_when, "not_this": draft.not_this,
        "version": draft.version,
    }


@router.post("/codebook-lab/candidates")
async def codebook_lab_candidates(
    request: Request, body: _LabCandidatesRequest, project_id: int = 1,
) -> dict[str, object]:
    """Scan the project's quotes against the (synthesised or hand-written) prompt."""
    from bristlenose.server import codebook_builder as cb

    draft = cb.PromptDraft(
        summary=body.prompt.summary, definition=body.prompt.definition,
        apply_when=body.prompt.apply_when, not_this=body.prompt.not_this,
    )
    if not (draft.definition or draft.apply_when):
        raise HTTPException(status_code=400, detail="Write or synthesise a prompt first")
    excluded = {t.strip() for t in body.exclude_texts if t.strip()}

    db = _get_db(request)
    try:
        pool = [
            cb.CandidateQuote(
                db_id=q.id, text=q.text, session_id=q.session_id,
                participant_id=q.participant_id, topic_label=q.topic_label or "",
                sentiment=q.sentiment or "",
            )
            for q in db.query(Quote).filter_by(project_id=project_id).all()
            if q.text.strip() not in excluded
        ]
    finally:
        db.close()

    scan = await cb.find_candidates(
        body.tag_name, draft, pool, _lab_settings(),
        min_confidence=body.min_confidence,
    )
    return {
        "scanned": scan.scanned,
        "errors": scan.errors,
        "candidates": [
            {"text": c.text, "confidence": round(c.confidence, 3), "rationale": c.rationale}
            for c in scan.candidates[: max(0, body.limit)]
        ],
    }


@router.get("/codebook-lab", include_in_schema=False)
def codebook_lab_page() -> HTMLResponse:
    """Redirect helper — the page itself lives at /codebook-lab (auth-exempt)."""
    raise HTTPException(status_code=404, detail="Page is served at /codebook-lab")


def build_codebook_lab_html(auth_token: str = "") -> str:
    """Return the bare codebook-lab experiment page (dev-only, ugly on purpose).

    Served at ``/codebook-lab`` (outside ``/api`` so a plain browser navigation
    isn't blocked by the bearer-token middleware); the embedded token lets the
    page's own fetch() calls authenticate against the ``/api/dev`` endpoints.
    """
    token_js = json.dumps(auth_token)
    return (
        _CODEBOOK_LAB_HTML.replace("__TOKEN__", token_js)
    )


_CODEBOOK_LAB_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codebook lab (experiment)</title>
<style>
  body { font: 14px/1.5 system-ui, sans-serif; margin: 0; padding: 16px; color: #111; }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .muted { color: #666; font-size: 12px; }
  .wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
  fieldset { border: 1px solid #ccc; border-radius: 6px; margin: 0 0 12px; padding: 10px 12px; }
  legend { font-weight: 600; padding: 0 6px; }
  label { display: block; font-size: 12px; color: #444; margin: 8px 0 2px; }
  textarea, input, select { width: 100%; box-sizing: border-box; font: inherit; padding: 6px; border: 1px solid #bbb; border-radius: 4px; }
  textarea { resize: vertical; }
  button { font: inherit; padding: 6px 12px; border: 1px solid #888; border-radius: 4px; background: #f3f3f3; cursor: pointer; }
  button.primary { background: #1f6feb; color: #fff; border-color: #1f6feb; }
  button:disabled { opacity: .5; cursor: default; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .cand { border: 1px solid #ddd; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }
  .cand .q { font-weight: 500; }
  .cand .r { font-size: 12px; color: #555; margin: 4px 0; }
  .conf { font-variant-numeric: tabular-nums; color: #1f6feb; font-weight: 600; }
  .acc { background: #e6ffed; } .rej { background: #ffeef0; }
  pre { background: #0d1117; color: #c9d1d9; padding: 10px; border-radius: 6px; overflow: auto; font-size: 12px; }
  .pill { display:inline-block; font-size: 11px; background:#eee; border-radius: 10px; padding: 1px 8px; }
  .warn { background: #fff8c5; border: 1px solid #d4a72c; padding: 6px 10px; border-radius: 6px; font-size: 12px; margin: 8px 0; }
</style>
</head>
<body>
<h1>Codebook lab <span class="pill">experiment</span></h1>
<div class="muted">Ugly throwaway sandbox for the dynamic-codebook-builder idea. Nothing here is saved. Real workflow/UX is TBD (Figma). Uses your configured LLM provider.</div>
<div class="warn">From a few short fragments the machine can only guess <em>surface</em> commonalities — it can't know what the tag means to you. Try both: let it <b>synthesise a draft</b>, and <b>write the criteria yourself</b>, then compare whose "find more like this" set is better.</div>

<div class="wrap">
  <div>
    <fieldset>
      <legend>1 · Exemplars</legend>
      <label>Pick a tag from this project (fills examples), or just paste below</label>
      <select id="tagPick"><option value="">— loading tags —</option></select>
      <label>Tag name</label>
      <input id="tagName" value="prescription cost">
      <label>Example quotes (one per line) — the quotes you'd code with this tag</label>
      <textarea id="examples" rows="6" placeholder="It's just too expensive to keep filling it every month..."></textarea>
      <div class="row" style="margin-top:8px">
        <button class="primary" id="btnSynth">Synthesise draft →</button>
        <span class="muted">or skip this and write the prompt yourself ↓</span>
      </div>
    </fieldset>

    <fieldset>
      <legend>2 · The prompt <span id="ver" class="pill"></span></legend>
      <label>Summary (what these share)</label>
      <textarea id="f_summary" rows="2"></textarea>
      <label>Definition</label>
      <textarea id="f_definition" rows="2"></textarea>
      <label>Apply when (inclusion)</label>
      <textarea id="f_apply" rows="3"></textarea>
      <label>Not this (exclusion)</label>
      <textarea id="f_not" rows="3"></textarea>
      <div class="row" style="margin-top:8px">
        <button class="primary" id="btnScan">Find candidates →</button>
        <label style="margin:0">min conf</label>
        <input id="minConf" type="number" step="0.05" min="0" max="1" value="0.5" style="width:80px">
        <label style="margin:0"><input type="checkbox" id="excl" checked style="width:auto"> exclude my examples</label>
      </div>
    </fieldset>
  </div>

  <div>
    <fieldset>
      <legend>3 · Candidates <span id="scanInfo" class="muted"></span></legend>
      <div id="cands"></div>
      <div class="row">
        <button id="btnRefine">Refine prompt from my accept/reject reasons →</button>
      </div>
    </fieldset>
    <fieldset>
      <legend>Raw / log</legend>
      <pre id="log">ready.</pre>
    </fieldset>
  </div>
</div>

<script>
const TOKEN = __TOKEN__;
const H = { "Content-Type": "application/json", "Authorization": "Bearer " + TOKEN };
const $ = id => document.getElementById(id);
const log = (x) => { $("log").textContent = (typeof x === "string" ? x : JSON.stringify(x, null, 2)); };
function setBusy(b){ document.querySelectorAll("button").forEach(x=>x.disabled=b); }
function getPrompt(){ return { summary:$("f_summary").value, definition:$("f_definition").value, apply_when:$("f_apply").value, not_this:$("f_not").value }; }
function setPrompt(p){ $("f_summary").value=p.summary||""; $("f_definition").value=p.definition||""; $("f_apply").value=p.apply_when||""; $("f_not").value=p.not_this||""; $("ver").textContent = p.version ? ("v "+p.version) : ""; }
function examples(){ return $("examples").value.split("\n").map(s=>s.trim()).filter(Boolean); }
async function post(path, body){
  const r = await fetch(path, { method:"POST", headers:H, body: JSON.stringify(body) });
  const j = await r.json().catch(()=>({detail:"(no json)"}));
  if(!r.ok) throw new Error(j.detail || r.status);
  return j;
}

let TAGS = [];
async function loadTags(){
  try {
    const r = await fetch("/api/dev/codebook-lab/tags", { headers: H });
    const j = await r.json();
    TAGS = j.tags || [];
    const sel = $("tagPick");
    sel.innerHTML = '<option value="">— '+TAGS.length+' tags in project —</option>';
    TAGS.forEach((t,i)=>{ const o=document.createElement("option"); o.value=i; o.textContent=t.name+" ("+t.quotes.length+")"; sel.appendChild(o); });
  } catch(e){ $("tagPick").innerHTML = '<option>— no project / '+e.message+' —</option>'; }
}
$("tagPick").onchange = () => {
  const i = $("tagPick").value; if(i==="") return;
  const t = TAGS[i]; $("tagName").value = t.name; $("examples").value = t.quotes.join("\n");
};

$("btnSynth").onclick = async () => {
  setBusy(true); log("synthesising…");
  try { const p = await post("/api/dev/codebook-lab/synthesize", { tag_name:$("tagName").value, example_texts: examples() }); setPrompt(p); log(p); }
  catch(e){ log("ERROR: "+e.message); } finally { setBusy(false); }
};

$("btnScan").onclick = async () => {
  setBusy(true); log("scanning project quotes…");
  try {
    const j = await post("/api/dev/codebook-lab/candidates", {
      tag_name:$("tagName").value, prompt:getPrompt(),
      min_confidence: parseFloat($("minConf").value), limit: 50,
      exclude_texts: $("excl").checked ? examples() : []
    });
    renderCands(j); log(j);
  } catch(e){ log("ERROR: "+e.message); } finally { setBusy(false); }
};

function renderCands(j){
  $("scanInfo").textContent = "scanned "+j.scanned+", "+j.candidates.length+" matched"+(j.errors?(", "+j.errors+" batch errors"):"");
  const box = $("cands"); box.innerHTML = "";
  if(!j.candidates.length){ box.innerHTML = '<div class="muted">no matches at this threshold.</div>'; return; }
  j.candidates.forEach((c,i)=>{
    const d = document.createElement("div"); d.className="cand"; d.dataset.idx=i; d.dataset.text=c.text;
    d.innerHTML = '<div class="q">“'+esc(c.text)+'”</div>'
      + '<div class="r"><span class="conf">'+c.confidence+'</span> · '+esc(c.rationale)+'</div>'
      + '<div class="row"><button data-v="accept">✓ great</button><button data-v="reject">✗ no</button>'
      + '<input placeholder="why? (the gold — your reason)" data-reason style="flex:1"></div>';
    d.querySelectorAll("button").forEach(b=> b.onclick = ()=>{ d.dataset.v=b.dataset.v; d.className="cand "+(b.dataset.v==="accept"?"acc":"rej"); });
    box.appendChild(d);
  });
}
function esc(s){ return (s||"").replace(/[&<>]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }

$("btnRefine").onclick = async () => {
  const acc=[], rej=[];
  document.querySelectorAll(".cand").forEach(d=>{
    if(!d.dataset.v) return;
    const item = { text: d.dataset.text, reason: d.querySelector("[data-reason]").value };
    (d.dataset.v==="accept"?acc:rej).push(item);
  });
  if(!acc.length && !rej.length){ log("mark some candidates ✓/✗ first (reasons optional but valuable)"); return; }
  setBusy(true); log("refining from "+acc.length+" accepted / "+rej.length+" rejected…");
  try {
    const p = await post("/api/dev/codebook-lab/refine", {
      tag_name:$("tagName").value, example_texts: examples(),
      prompt: getPrompt(), accepted: acc, rejected: rej
    });
    setPrompt(p); log(p);
  } catch(e){ log("ERROR: "+e.message); } finally { setBusy(false); }
};

loadTags();
</script>
</body>
</html>
"""
