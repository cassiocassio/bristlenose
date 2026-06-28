"""Dev-only "Run Inspector" — infoviz over instrumentation the pipeline already
captures.

Pure, stdlib-only data readers + shapers + a self-contained HTML builder. This
module deliberately imports nothing from FastAPI / SQLAlchemy / the heavy
pipeline so it can be unit-tested in isolation (and so the ``--dev`` endpoint in
``routes/dev.py`` stays a thin wrapper).

Data sources, all already on disk after a run:
  * ``<output>/.bristlenose/llm-calls.jsonl``      (telemetry.LLMCallEvent rows)
  * ``<output>/.bristlenose/pipeline-events.jsonl`` (events.* rows)
  * ``~/.config/bristlenose/timing.json``          (timing.WelfordStat profiles)

Honesty rule: every panel reads real data. Where a layer can't be backed (e.g.
per-run convergence history isn't stored), it's omitted rather than faked.

See ``docs/design-debug-menu.md``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

JSONL_LLM = "llm-calls.jsonl"
JSONL_EVENTS = "pipeline-events.jsonl"
TIMING_FILENAME = "timing.json"

# gen_ai.system (internal) -> product name (per CLAUDE.md provider-naming rule).
PROVIDER_NAMES = {
    "anthropic": "Claude",
    "openai": "ChatGPT",
    "azure": "Azure OpenAI",
    "google": "Gemini",
    "gemini": "Gemini",
    "ollama": "Local",
    "local": "Local",
}

# Pipeline stage id -> (display label, is_llm). Order matters for the gantt.
STAGE_LABELS: list[tuple[str, str, bool]] = [
    ("ingest", "Ingest", False),
    ("extract_audio", "Extract audio", False),
    ("transcribe", "Transcribe", False),
    ("identify_speakers", "Identify speakers", False),
    ("merge_transcript", "Merge transcript", False),
    ("pii_removal", "PII removal", False),
    ("topic_segmentation", "Topic segmentation", True),
    ("quote_extraction", "Quote extraction", True),
    ("cluster_and_group", "Cluster & group", True),
    ("render", "Render", False),
]
_STAGE_ORDER = {sid: i for i, (sid, _, _) in enumerate(STAGE_LABELS)}
_STAGE_LABEL = {sid: lbl for sid, lbl, _ in STAGE_LABELS}
_STAGE_LLM = {sid: llm for sid, _, llm in STAGE_LABELS}

# Stable colour per LLM-bearing telemetry stage (telemetry uses its own stage
# vocabulary — topics/quotes/cluster/etc — keyed off the contextmanager name).
_STAGE_COLOURS = ["#b07cff", "#5fa0ff", "#2bb6c4", "#ffb454", "#46c98b", "#ff8db0"]


# ---------------------------------------------------------------------------
# Low-level readers
# ---------------------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file tolerantly. Missing file → []. Bad lines skipped."""
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _first(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-None key (handles OTel dotted aliases)."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(v: Any, default: float | None = None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------


def load_llm_calls(internal_dir: Path) -> list[dict[str, Any]]:
    """Normalise llm-calls.jsonl rows into flat, display-ready dicts."""
    out: list[dict[str, Any]] = []
    for r in read_jsonl(internal_dir / JSONL_LLM):
        cache = _int(_first(r, "gen_ai.usage.cache_read_input_tokens", "cache_read_input_tokens")) + _int(
            _first(r, "gen_ai.usage.cache_creation_input_tokens", "cache_creation_input_tokens")
        )
        system = (_first(r, "gen_ai.system", "gen_ai_system", default="") or "").lower()
        model = _first(r, "gen_ai.response.model", "gen_ai.request.model", "gen_ai_request_model", default="") or ""
        out.append(
            {
                "ts": r.get("ts", ""),
                "run_id": r.get("run_id", ""),
                "stage": r.get("stage", "") or "?",
                "provider": PROVIDER_NAMES.get(system, system or "?"),
                "system": system,
                "model": _short_model(model),
                "model_full": model,
                "in": _int(_first(r, "gen_ai.usage.input_tokens", "input_tokens")),
                "out": _int(_first(r, "gen_ai.usage.output_tokens", "output_tokens")),
                "cache": cache,
                "ms": _int(r.get("elapsed_ms")),
                "retries": _int(r.get("retry_count")),
                "finish": r.get("finish_reason") or "—",
                "cost": _float(r.get("cost_usd_actual_estimate")),
                "cost_pred": _float(r.get("cost_usd_predicted")),
            }
        )
    return out


def _short_model(model: str) -> str:
    """`claude-opus-4-8-20260101` → `opus-4-8`; `gpt-4o` → `gpt-4o`."""
    m = model
    for prefix in ("claude-", "models/"):
        if m.startswith(prefix):
            m = m[len(prefix) :]
    # Trim a trailing date stamp (-YYYYMMDD or -YYYY-MM-DD).
    parts = m.split("-")
    if parts and parts[-1].isdigit() and len(parts[-1]) == 8:
        parts = parts[:-1]
    return "-".join(parts) or model


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile. q in [0,1]. Empty → 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def summarise_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats over the call set."""
    n = len(calls)
    lat = [c["ms"] for c in calls if c["ms"]]
    tin = sum(c["in"] for c in calls)
    tout = sum(c["out"] for c in calls)
    tcache = sum(c["cache"] for c in calls)
    cost = sum(c["cost"] for c in calls if c["cost"] is not None)
    cost_pred = sum(c["cost_pred"] for c in calls if c["cost_pred"] is not None)
    stages = sorted({c["stage"] for c in calls})
    fresh_in = tin  # input_tokens excludes cache reads in the OTel schema
    cache_ratio = (tcache / (fresh_in + tcache)) if (fresh_in + tcache) else 0.0
    return {
        "n": n,
        "cost": round(cost, 4),
        "cost_pred": round(cost_pred, 4),
        "in": tin,
        "out": tout,
        "cache": tcache,
        "p50_ms": round(percentile(lat, 0.5)),
        "p95_ms": round(percentile(lat, 0.95)),
        "retries": sum(c["retries"] for c in calls),
        "cache_ratio": round(cache_ratio, 4),
        "stage_count": len(stages),
    }


def cost_by_stage(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-stage cost split (input / output / cache → derived from totals)."""
    agg: dict[str, dict[str, float]] = {}
    for c in calls:
        a = agg.setdefault(c["stage"], {"cost": 0.0, "in": 0, "out": 0, "cache": 0})
        a["cost"] += c["cost"] or 0.0
        a["in"] += c["in"]
        a["out"] += c["out"]
        a["cache"] += c["cache"]
    rows = []
    for i, (stage, a) in enumerate(sorted(agg.items(), key=lambda kv: -kv[1]["cost"])):
        rows.append(
            {
                "stage": stage,
                "label": _STAGE_LABEL.get(stage, stage.replace("_", " ").title()),
                "colour": _STAGE_COLOURS[i % len(_STAGE_COLOURS)],
                "cost": round(a["cost"], 4),
                "in": a["in"],
                "out": a["out"],
                "cache": a["cache"],
            }
        )
    return rows


def calibration(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Predicted vs actual cost per call (real forecast-accuracy data)."""
    colours = {r["stage"]: r["colour"] for r in cost_by_stage(calls)}
    out = []
    for c in calls:
        if c["cost"] is None or c["cost_pred"] is None:
            continue
        out.append(
            {
                "stage": c["stage"],
                "label": _STAGE_LABEL.get(c["stage"], c["stage"]),
                "colour": colours.get(c["stage"], "#5fa0ff"),
                "pred": round(c["cost_pred"], 5),
                "act": round(c["cost"], 5),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Pipeline events → provenance, gantt, event stream
# ---------------------------------------------------------------------------


def _event_type(e: dict[str, Any]) -> str:
    """Canonical event-type string for one event record, e.g. ``"run_completed"``.

    The pipeline (``bristlenose/events.py``) writes the discriminator in the
    ``event`` field (``EventTypeEnum``: ``run_started`` / ``run_progress`` /
    ``run_completed`` / ``run_cancelled`` / ``run_failed``); ``kind`` is the
    *level* (``KindEnum``: ``run`` / ``analyze`` / ``transcribe-only``), NOT the
    event name. Earlier code here read a non-existent ``event_type`` field and
    matched ``kind`` against event names, so on real data every lifecycle lookup
    silently missed. Accept the legacy shapes too — an ``event_type`` field, or a
    bare event name in ``kind`` (``"started"``) as the synthetic fixtures used —
    so this is robust to both.
    """
    et = e.get("event") or e.get("event_type") or ""
    if et:
        return et
    k = e.get("kind", "")
    if k and k not in ("run", "analyze", "transcribe-only"):
        return k if k.startswith("run_") else f"run_{k}"
    return ""


def reconstruct_stages(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """Rebuild a stage timeline from the RunProgress ``elapsed_seconds`` stream.

    RunProgress events carry ``stage`` + ``elapsed_seconds``; a stage's duration
    is the elapsed delta until the next distinct stage (or run end). Returns
    ``(stages, total_seconds)``. Empty when no progress was recorded.
    """
    marks: list[tuple[str, float]] = []
    end_elapsed = 0.0
    for e in events:
        if _event_type(e) == "run_progress" or "stage_fraction" in e:
            stage = e.get("stage")
            el = _float(e.get("elapsed_seconds"))
            if stage and el is not None:
                marks.append((stage, el))
                end_elapsed = max(end_elapsed, el)
    if not marks:
        return [], 0.0
    # Collapse consecutive same-stage marks to first-seen elapsed.
    boundaries: list[tuple[str, float]] = []
    for stage, el in marks:
        if not boundaries or boundaries[-1][0] != stage:
            boundaries.append((stage, el))
    stages: list[dict[str, Any]] = []
    for i, (stage, start) in enumerate(boundaries):
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else end_elapsed
        dur = max(end - start, 0.0)
        stages.append(
            {
                "id": stage,
                "name": _STAGE_LABEL.get(stage, stage.replace("_", " ").title()),
                "start": round(start, 2),
                "dur": round(dur, 2),
                "status": "llm" if _STAGE_LLM.get(stage) else "ran",
                "order": _STAGE_ORDER.get(stage, 99),
            }
        )
    stages.sort(key=lambda s: (s["start"], s["order"]))
    return stages, round(end_elapsed, 2)


def _terminus(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for e in reversed(events):
        if _event_type(e) in ("run_completed", "run_cancelled", "run_failed"):
            return e
    return None


def _run_started(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for e in events:
        if _event_type(e) == "run_started":
            return e
    return None


def _duration_seconds(started: dict[str, Any] | None, terminus: dict[str, Any] | None) -> float | None:
    if not started or not terminus:
        return None
    try:
        from datetime import datetime

        a = datetime.fromisoformat(started.get("started_at", "").replace("Z", "+00:00"))
        b = datetime.fromisoformat(terminus.get("ended_at", "").replace("Z", "+00:00"))
        return max((b - a).total_seconds(), 0.0)
    except (ValueError, TypeError):
        return None


def event_stream(events: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    """Tail of the event log for the inspector's event panel."""
    glyphs = {"started": ("ℹ", "info"), "progress": ("◐", "run"), "completed": ("✓", "ok"), "cancelled": ("⚠", "warn"), "failed": ("✗", "fail")}
    out = []
    for e in events[-limit:]:
        kind = _event_type(e).replace("run_", "") or "?"
        glyph, cls = glyphs.get(kind, ("·", "info"))
        ts = (e.get("ts") or "").split("T")[-1][:8]
        if kind == "progress":
            msg = f"progress · {e.get('stage','?')} · {e.get('stage_fraction', '')}"
        elif kind == "started":
            msg = "run_started"
        else:
            msg = f"run_{kind}"
        out.append({"t": ts, "glyph": glyph, "cls": cls, "msg": msg})
    return out


# ---------------------------------------------------------------------------
# Timing (Welford) vs this-run actuals
# ---------------------------------------------------------------------------

# timing.json metric name -> the manifest stage id it corresponds to.
_TIMING_METRIC_STAGE = {
    "transcribe": "transcribe",
    "speakers": "identify_speakers",
    "topics": "topic_segmentation",
    "quotes": "quote_extraction",
    "cluster": "cluster_and_group",
    "render": "render",
}


def load_timing(config_dir: Path) -> dict[str, Any]:
    path = config_dir / TIMING_FILENAME
    if not path.is_file():
        return {"version": 1, "profiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "profiles": {}}
    if not isinstance(data, dict) or "profiles" not in data:
        return {"version": 1, "profiles": {}}
    return data


def timing_compare(
    timing: dict[str, Any], stage_actuals: dict[str, float]
) -> list[dict[str, Any]]:
    """Per-stage Welford μ ± σ (over n runs) vs this run's actual seconds.

    The timing store keeps rate metrics, not absolute seconds, so μ/σ here are
    only meaningful for metrics whose unit is whole-stage seconds. We surface
    whichever metrics have both a stored stat and a measured actual this run.
    Wide σ relative to μ is itself the signal (low forecast confidence).
    """
    profiles = timing.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        return []
    # Use the profile with the most observations (this machine's richest).
    best = max(profiles.values(), key=lambda p: sum(_int(s.get("n")) for s in p.values()) if isinstance(p, dict) else 0)
    rows = []
    for metric, stat in best.items():
        if not isinstance(stat, dict):
            continue
        stage = _TIMING_METRIC_STAGE.get(metric)
        act = stage_actuals.get(stage) if stage else None
        if act is None:
            continue
        n = _int(stat.get("n"))
        mean = _float(stat.get("mean"), 0.0) or 0.0
        m2 = _float(stat.get("m2"), 0.0) or 0.0
        var = (m2 / (n - 1)) if n >= 2 else 0.0
        rows.append(
            {
                "name": _STAGE_LABEL.get(stage, metric.title()),
                "mu": round(mean, 2),
                "sig": round(var**0.5, 2),
                "n": n,
                "act": round(act, 2),
            }
        )
    rows.sort(key=lambda r: -r["act"])
    return rows


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_run_data(
    internal_dir: Path,
    config_dir: Path,
    *,
    version: str,
    sha: str = "",
    build_date: str = "",
    project_name: str = "",
    db_path: str = "",
) -> dict[str, Any]:
    """Assemble the full inspector payload from on-disk instrumentation."""
    calls = load_llm_calls(internal_dir)
    events = load_events_safe(internal_dir)
    stages, total = reconstruct_stages(events)
    stage_actuals = {s["id"]: s["dur"] for s in stages}

    started = _run_started(events)
    terminus = _terminus(events)
    duration = _duration_seconds(started, terminus) or (total or None)
    status = "—"
    if terminus:
        status = _event_type(terminus).replace("run_", "") or "—"
    elif started:
        status = "running"

    provider = model = "—"
    if calls:
        provider = calls[0]["provider"]
        model = calls[0]["model"]

    proc = (started or {}).get("process") or (terminus or {}).get("process") or {}
    hardware = proc.get("os", "—")
    run_id = (terminus or started or {}).get("run_id", "—")

    summary = summarise_calls(calls)
    cbs = cost_by_stage(calls)
    # attach colours to call rows + calibration via stage→colour
    colour_for = {r["stage"]: r["colour"] for r in cbs}
    for c in calls:
        c["colour"] = colour_for.get(c["stage"], "#5fa0ff")
        c["stage_label"] = _STAGE_LABEL.get(c["stage"], c["stage"])

    return {
        "ok": bool(calls or events),
        "prov": {
            "project": project_name or "—",
            "version": version,
            "sha": sha or "unknown",
            "build_date": build_date,
            "provider": provider,
            "model": model,
            "hardware": hardware,
            "run_id": run_id,
            "status": status,
            "duration_s": round(duration, 1) if duration else None,
            "db_path": db_path or "—",
        },
        "stages": stages,
        "total": total,
        "calls": calls,
        "summary": summary,
        "cost_by_stage": cbs,
        "timing": timing_compare(load_timing(config_dir), stage_actuals),
        "calibration": calibration(calls),
        "events": event_stream(events),
    }


def load_events_safe(internal_dir: Path) -> list[dict[str, Any]]:
    return read_jsonl(internal_dir / JSONL_EVENTS)


def resolve_internal_dir(project_dir: Path) -> Path:
    """Mirror app.py: project_dir/bristlenose-output/.bristlenose, with fallback."""
    out = project_dir / "bristlenose-output"
    if not out.is_dir():
        out = project_dir
    return out / ".bristlenose"


# ---------------------------------------------------------------------------
# HTML (self-contained; data injected as JSON)
# ---------------------------------------------------------------------------

_DATA_TOKEN = "/*__RUN_DATA__*/null"


def build_run_inspector_html(data: dict[str, Any]) -> str:
    """Return the full self-contained inspector page with ``data`` injected.

    The JSON is embedded in a ``<script>`` block, so ``<``/``>``/``&`` and the
    JS line separators must be escaped to prevent a ``</script>`` breakout —
    ``ensure_ascii=True`` alone does NOT escape ``<`` (it's ASCII). The result
    stays valid JSON (``JSON.parse`` decodes the ``\\uXXXX`` escapes).
    """
    blob = json.dumps(data, ensure_ascii=True)
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return _HTML.replace(_DATA_TOKEN, blob)


# The page template lives next to the code so the dev endpoint is a thin caller.
# CSS/JS are inline (dev-only, no build step, offline-safe). Mirrors the mockup
# in docs/mockups/debug-inspector-mockup.html, driven by injected DATA.
_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bristlenose — Run Inspector</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--border:#272d3a;--ink:#d8dde6;--muted:#828c9c;--faint:#5a6373;
--ran:#4c8dff;--llm:#b07cff;--cached:#4b5363;--skip:#363d4c;--fail:#ff5d5d;--good:#46c98b;--warn:#ffb454;--cache:#2bb6c4;
--mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,Inter,system-ui,sans-serif;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:13px;line-height:1.45}
code,.mono{font-family:var(--mono)}.wrap{max-width:1180px;margin:0 auto;padding:18px 22px 60px}
header.prov{display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px;background:linear-gradient(180deg,#1a1e27,#14171f);
border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin-bottom:14px}
header.prov h1{font-size:14px;margin:0 18px 0 0;font-weight:600}
.tag{display:inline-block;background:#222838;border:1px solid var(--border);border-radius:6px;padding:1px 7px;font-family:var(--mono);font-size:11px}
.kv{display:flex;flex-direction:column;gap:1px}.kv .k{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--faint)}
.kv .v{font-family:var(--mono);font-size:12px}.pill{padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600}
.pill.ok{background:rgba(70,201,139,.16);color:var(--good)}.pill.warn{background:rgba(255,180,84,.16);color:var(--warn)}
.pill.fail{background:rgba(255,93,93,.16);color:var(--fail)}
nav.tabs{display:flex;gap:4px;margin-bottom:14px;border-bottom:1px solid var(--border)}
nav.tabs button{background:none;border:0;color:var(--muted);font:inherit;font-weight:600;padding:9px 14px;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
nav.tabs button:hover{color:var(--ink)}nav.tabs button.active{color:var(--ink);border-bottom-color:var(--llm)}
.view{display:none}.view.active{display:block}.grid{display:grid;gap:14px}.g-2{grid-template-columns:1fr 320px}
@media(max-width:920px){.g-2{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.card h2{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);margin:0 0 12px;font-weight:600}
.card h2 .sub{text-transform:none;letter-spacing:0;color:var(--faint);font-weight:400;margin-left:8px}
.stats{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:14px}
@media(max-width:920px){.stats{grid-template-columns:repeat(3,1fr)}}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:11px 13px}
.stat .n{font-family:var(--mono);font-size:20px;font-weight:600}.stat .l{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.stat .d{font-size:11px;margin-top:4px;color:var(--faint)}
.gantt-axis{position:relative;height:16px;margin:0 0 4px 150px;color:var(--faint);font-family:var(--mono);font-size:10px}
.gantt-axis span{position:absolute;transform:translateX(-50%)}
.grow{display:flex;align-items:center;height:24px}.grow .lab{width:150px;flex:0 0 150px;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px}
.grow .lab .sid{color:var(--faint);font-family:var(--mono);font-size:10px;margin-right:5px}
.track{position:relative;flex:1;height:14px;background:repeating-linear-gradient(90deg,transparent,transparent 9.9%,#20252f 10%,#20252f 10%)}
.bar{position:absolute;top:0;height:14px;border-radius:3px}.bar.ran{background:var(--ran)}.bar.llm{background:linear-gradient(90deg,var(--llm),#8e5cff)}
.bar.cached{background:var(--cached)}.bar.skipped{background:var(--skip)}.bar.failed{background:var(--fail)}
.bar .dur{position:absolute;left:calc(100% + 5px);top:-1px;font-family:var(--mono);font-size:10px;color:var(--muted);white-space:nowrap}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:11px;color:var(--muted)}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.donut-wrap{display:flex;align-items:center;gap:16px}.donut{width:118px;height:118px;border-radius:50%;flex:0 0 118px;position:relative}
.donut::after{content:"";position:absolute;inset:21px;background:var(--panel);border-radius:50%}
.donut .ctr{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1}
.donut .ctr b{font-family:var(--mono);font-size:17px}.donut .ctr span{font-size:10px;color:var(--muted)}
.dleg{font-size:11px;display:flex;flex-direction:column;gap:5px}.dleg div{display:flex;align-items:center;gap:6px}
.dleg i{width:9px;height:9px;border-radius:2px}.dleg .amt{margin-left:auto;font-family:var(--mono);color:var(--muted)}
.ev{display:flex;gap:10px;padding:5px 0;border-bottom:1px solid #1f2530;font-family:var(--mono);font-size:11.5px}
.ev:last-child{border-bottom:0}.ev .t{color:var(--faint);flex:0 0 78px}.ev .g{flex:0 0 16px;text-align:center}
.g-ok{color:var(--good)}.g-info{color:var(--ran)}.g-warn{color:var(--warn)}.g-run{color:var(--llm)}.g-fail{color:var(--fail)}
table{width:100%;border-collapse:collapse;font-size:11.5px}th{text-align:left;color:var(--faint);font-weight:600;text-transform:uppercase;letter-spacing:.5px;font-size:10px;padding:6px 8px;border-bottom:1px solid var(--border)}
td{padding:6px 8px;border-bottom:1px solid #1d222c;font-family:var(--mono);font-size:11px}tr:hover td{background:#1b202a}td.num{text-align:right}
.chip{font-family:var(--mono);font-size:10px;padding:1px 6px;border-radius:5px;background:#222838;border:1px solid var(--border)}
.retry{color:var(--warn)}.miss{color:var(--faint)}.cache-hit{color:var(--cache)}
.viz{width:100%;overflow:visible}.axislbl{fill:var(--faint);font-family:var(--mono);font-size:9px}.stagelbl{fill:var(--ink);font-size:10.5px}.gridline{stroke:#222834;stroke-width:1}.dot-r{fill:none;stroke:var(--warn);stroke-width:1.5}
.empty{text-align:center;color:var(--muted);padding:60px 20px}.empty b{color:var(--ink)}
.banner{font-size:11px;color:var(--faint);margin-bottom:12px}.banner b{color:var(--warn)}
</style></head><body><div class="wrap">
<div class="banner"><b>RUN INSPECTOR</b> · dev-only (<code>/api/dev/run</code>) · reads <code>.bristlenose/llm-calls.jsonl</code> + <code>pipeline-events.jsonl</code> + <code>~/.config/bristlenose/timing.json</code>. <a href="/api/dev/run.json" style="color:var(--ran)">raw JSON</a></div>
<div id="app"></div>
</div>
<script id="run-data" type="application/json">/*__RUN_DATA__*/null</script>
<script>
const DATA=JSON.parse(document.getElementById('run-data').textContent);
const $=s=>document.querySelector(s);
const el=(t,c,h)=>{const e=document.createElement(t);if(c)e.className=c;if(h!=null)e.innerHTML=h;return e;};
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const fmtS=s=>s==null?'—':(s>=60?`${Math.floor(s/60)}m ${Math.round(s%60)}s`:`${(+s).toFixed(s<10?1:0)}s`);
const fmtK=n=>n>=1000?(n/1000).toFixed(1)+'k':String(n);

function render(){
  if(!DATA||!DATA.ok){document.getElementById('app').innerHTML=
    '<div class="card"><div class="empty"><b>No run data yet.</b><br>Run the pipeline (or open a project that has), then reload.<br><span style="font-size:11px">Expected files under the project\'s <code>.bristlenose/</code>.</span></div></div>';return;}
  const p=DATA.prov;
  const statusCls=p.status==='completed'?'ok':(p.status==='failed'?'fail':(p.status==='cancelled'?'warn':'ok'));
  const kv=(k,v)=>`<div class="kv"><span class="k">${esc(k)}</span><span class="v">${v}</span></div>`;
  document.getElementById('app').innerHTML=`
  <header class="prov"><h1>Run Inspector</h1>
    ${kv('project',esc(p.project))}
    ${kv('version',esc(p.version)+(p.sha&&p.sha!=='unknown'?` <span class="tag">${esc(p.sha)}${p.build_date?' @'+esc(p.build_date):''}</span>`:''))}
    ${kv('provider',esc(p.provider)+' · '+esc(p.model))}
    ${kv('hardware',esc(p.hardware))}
    ${kv('run_id',esc(String(p.run_id).slice(0,10)))}
    ${kv('db',esc(p.db_path))}
    ${kv('status',`<span class="pill ${statusCls}">${esc(p.status)}${p.duration_s?' · '+fmtS(p.duration_s):''}</span>`)}
  </header>
  <nav class="tabs"><button data-v="run" class="active">Run overview</button><button data-v="llm">LLM calls</button><button data-v="timing">Timing &amp; forecast</button></nav>
  <section class="view active" id="v-run"></section>
  <section class="view" id="v-llm"></section>
  <section class="view" id="v-timing"></section>`;
  renderRun();renderLLM();renderTiming();
  document.querySelectorAll('nav.tabs button').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('nav.tabs button').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');$('#v-'+b.dataset.v).classList.add('active');});
}

function renderRun(){
  const host=$('#v-run');const stages=DATA.stages||[],total=DATA.total||1;
  let gantt='';
  if(stages.length){
    let axis='';[0,.25,.5,.75,1].forEach(f=>{axis+=`<span style="left:${f*100}%">${fmtS(total*f)}</span>`;});
    let rows='';stages.forEach(s=>{
      const w=Math.max(s.dur/total*100,.5),left=s.start/total*100;
      rows+=`<div class="grow"><div class="lab"><span class="sid">${esc(s.id).slice(0,3)}</span>${esc(s.name)}</div>
        <div class="track"><div class="bar ${s.status}" style="left:${left}%;width:${w}%" title="${esc(s.name)} — ${fmtS(s.dur)}">${s.dur>total*.04?`<span class="dur">${fmtS(s.dur)}</span>`:''}</div></div></div>`;});
    gantt=`<div class="gantt-axis">${axis}</div>${rows}
      <div class="legend"><span><i style="background:var(--ran)"></i>ran (local)</span><span><i style="background:var(--llm)"></i>ran (LLM)</span><span><i style="background:var(--cached)"></i>cached</span></div>`;
  }else gantt='<div class="empty">No per-stage progress recorded for this run.</div>';

  const cbs=DATA.cost_by_stage||[];const totCost=cbs.reduce((a,r)=>a+r.cost,0);
  let donut='',dleg='';
  if(totCost>0){let acc=0,stops=[];cbs.forEach(r=>{const p0=acc/totCost*360,p1=(acc+r.cost)/totCost*360;acc+=r.cost;stops.push(`${r.colour} ${p0}deg ${p1}deg`);
    dleg+=`<div><i style="background:${r.colour}"></i>${esc(r.label)}<span class="amt">$${r.cost.toFixed(3)}</span></div>`;});
    donut=`<div class="donut-wrap"><div class="donut" style="background:conic-gradient(${stops.join(',')})"><div class="ctr"><b>$${totCost.toFixed(2)}</b><span>${DATA.summary.n} calls</span></div></div><div class="dleg">${dleg}</div></div>`;
  }else donut='<div class="empty">No LLM cost recorded.</div>';

  const s=DATA.summary;const tot=s.in+s.out+s.cache||1;
  const seg=(v,col,lbl)=>`<div style="width:${v/tot*100}%;background:${col};height:26px;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:10px;color:#0b0d11;font-weight:600">${v/tot>.09?lbl:''}</div>`;
  const tokenbar=`<div style="display:flex;border-radius:6px;overflow:hidden;border:1px solid var(--border)">${seg(s.in,'#5fa0ff','in '+fmtK(s.in))}${seg(s.out,'#b07cff','out '+fmtK(s.out))}${seg(s.cache,'#2bb6c4','cache '+fmtK(s.cache))}</div>
    <div style="display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin-top:8px"><span>total ${fmtK(s.in+s.out+s.cache)} tokens</span><span>${(s.cache_ratio*100).toFixed(0)}% of input cached</span></div>`;

  let evs='';(DATA.events||[]).forEach(e=>{evs+=`<div class="ev"><span class="t">${esc(e.t)}</span><span class="g g-${e.cls}">${e.glyph}</span><span>${esc(e.msg)}</span></div>`;});

  host.innerHTML=`<div class="grid g-2">
    <div class="card"><h2>Pipeline <span class="sub">reconstructed from run_progress · ▦ LLM</span></h2>${gantt}</div>
    <div class="grid" style="gap:14px"><div class="card"><h2>Cost by stage</h2>${donut}</div><div class="card"><h2>Tokens</h2>${tokenbar}</div></div></div>
    <div class="card" style="margin-top:14px"><h2>Event stream <span class="sub">pipeline-events.jsonl</span></h2>${evs||'<div class="empty">No events.</div>'}</div>`;
}

function renderLLM(){
  const host=$('#v-llm');const calls=DATA.calls||[];const s=DATA.summary;
  if(!calls.length){host.innerHTML='<div class="card"><div class="empty">No LLM calls recorded for this run.</div></div>';return;}
  const cards=[[String(s.n),'calls',s.stage_count+' stages'],
    ['$'+s.cost.toFixed(2),'total cost',s.cost_pred?('forecast $'+s.cost_pred.toFixed(2)):''],
    [(s.p50_ms/1000).toFixed(1)+'s','p50 latency','p95 '+(s.p95_ms/1000).toFixed(1)+'s'],
    [fmtK(s.in+s.cache),'input tokens',fmtK(s.cache)+' cached'],
    [String(s.retries),'retries',''],[(s.cache_ratio*100).toFixed(0)+'%','cache hit','re-run lever']];
  let stats='';cards.forEach(c=>stats+=`<div class="stat"><div class="n">${c[0]}</div><div class="l">${c[1]}</div><div class="d">${c[2]||'&nbsp;'}</div></div>`);

  // latency scatter
  const W=560,H=210,pl=42,pb=24,pt=8,pr=10;
  const maxMs=Math.max(...calls.map(c=>c.ms),1)*1.1,maxTok=Math.max(...calls.map(c=>c.out),1);
  const x=i=>pl+(calls.length>1?i/(calls.length-1):0.5)*(W-pl-pr),y=ms=>pt+(1-ms/maxMs)*(H-pt-pb);
  let lp=`<svg class="viz" viewBox="0 0 ${W} ${H}">`;
  [0,.25,.5,.75,1].forEach(f=>{const yy=y(f*maxMs);lp+=`<line class="gridline" x1="${pl}" y1="${yy}" x2="${W-pr}" y2="${yy}"/><text class="axislbl" x="${pl-6}" y="${yy+3}" text-anchor="end">${(f*maxMs/1000).toFixed(0)}s</text>`;});
  calls.forEach((c,i)=>{const r=4+(c.out/maxTok)*7;lp+=`<circle cx="${x(i)}" cy="${y(c.ms)}" r="${r}" fill="${c.colour}" fill-opacity="0.85"><title>${esc(c.stage_label)} · ${(c.ms/1000).toFixed(1)}s · out ${c.out} · ${c.retries} retries</title></circle>`;if(c.retries>0)lp+=`<circle class="dot-r" cx="${x(i)}" cy="${y(c.ms)}" r="${r+4}"/>`;});
  lp+=`<text class="axislbl" x="${pl}" y="${H-6}">call order →</text></svg>`;

  // cache donut
  const cr=s.cache_ratio*100;
  const cacheDonut=`<div class="donut-wrap"><div class="donut" style="background:conic-gradient(var(--cache) 0deg ${cr/100*360}deg,#2a3038 ${cr/100*360}deg 360deg)"><div class="ctr"><b>${cr.toFixed(0)}%</b><span>cached in</span></div></div>
    <div class="dleg"><div><i style="background:var(--cache)"></i>cached<span class="amt">${fmtK(s.cache)}</span></div><div><i style="background:#2a3038"></i>fresh<span class="amt">${fmtK(s.in)}</span></div></div></div>`;

  // stage cost bars
  const cbs=DATA.cost_by_stage,maxC=Math.max(...cbs.map(r=>r.cost),0.0001);
  let bars='';cbs.forEach(r=>{const w=v=>v/maxC*100;
    bars+=`<div style="display:flex;align-items:center;gap:10px;margin:7px 0"><span style="flex:0 0 120px;font-size:11.5px">${esc(r.label)}</span>
      <div style="flex:1;display:flex;height:18px;border-radius:4px;overflow:hidden;background:#10131a"><div style="width:${w(r.cost)}%;background:${r.colour}"></div></div>
      <span class="mono" style="flex:0 0 56px;text-align:right;color:var(--muted);font-size:11px">$${r.cost.toFixed(3)}</span></div>`;});

  // table
  let rows='';calls.forEach(c=>{rows+=`<tr><td>${esc((c.ts||'').split('T').pop().slice(0,8))}</td><td><span class="chip" style="color:${c.colour}">${esc(c.stage_label)}</span></td><td>${esc(c.model)}</td>
    <td class="num">${c.in}</td><td class="num">${c.out}</td><td class="num ${c.cache?'cache-hit':'miss'}">${c.cache||'—'}</td>
    <td class="num">${(c.ms/1000).toFixed(1)}s</td><td class="${c.retries?'retry':'miss'}">${c.retries?'×'+c.retries:'—'}</td>
    <td class="${c.finish==='length'?'retry':''}">${esc(c.finish)}</td><td class="num">${c.cost!=null?'$'+c.cost.toFixed(4):'—'}</td></tr>`;});

  host.innerHTML=`<div class="stats">${stats}</div>
    <div class="grid g-2"><div class="card"><h2>Latency × tokens <span class="sub">y=latency · ◯=retried · colour=stage</span></h2>${lp}</div>
      <div class="card"><h2>Cache hit ratio</h2>${cacheDonut}<p style="color:var(--muted);font-size:11px;margin:12px 0 0">Cached input is billed ~10× cheaper — the biggest re-run cost lever.</p></div></div>
    <div class="card" style="margin-top:14px"><h2>Cost by stage</h2>${bars}</div>
    <div class="card" style="margin-top:14px"><h2>Calls <span class="sub">llm-calls.jsonl · ${calls.length} rows</span></h2><div style="overflow:auto"><table><thead><tr><th>time</th><th>stage</th><th>model</th><th class="num">in</th><th class="num">out</th><th class="num">cache</th><th class="num">latency</th><th>retry</th><th>finish</th><th class="num">cost</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function renderTiming(){
  const host=$('#v-timing');const tm=DATA.timing||[],cal=DATA.calibration||[];
  let dumbbell='';
  if(tm.length){const W=560,rowH=34,pl=130,pr=58,H=tm.length*rowH+24,max=Math.max(...tm.map(t=>Math.max(t.act,t.mu+t.sig)),1)*1.08,x=v=>pl+v/max*(W-pl-pr);
    let sv=`<svg class="viz" viewBox="0 0 ${W} ${H}">`;tm.forEach((t,i)=>{const cy=18+i*rowH,col=t.act>t.mu?'#ffb454':'#46c98b';
      sv+=`<text class="stagelbl" x="0" y="${cy+4}">${esc(t.name)} <tspan class="axislbl">n=${t.n}</tspan></text>`;
      sv+=`<rect x="${x(Math.max(t.mu-t.sig,0))}" y="${cy-7}" width="${Math.max(x(t.mu+t.sig)-x(Math.max(t.mu-t.sig,0)),0)}" height="14" rx="3" fill="#2a3142" fill-opacity="0.7"/>`;
      sv+=`<line x1="${x(t.mu)}" y1="${cy}" x2="${x(t.act)}" y2="${cy}" stroke="${col}" stroke-width="2"/>`;
      sv+=`<circle cx="${x(t.mu)}" cy="${cy}" r="5" fill="#7d8694"><title>μ ${fmtS(t.mu)} ± ${t.sig}s (n=${t.n})</title></circle>`;
      sv+=`<rect x="${x(t.act)-1.5}" y="${cy-8}" width="3" height="16" fill="${col}"><title>actual ${fmtS(t.act)}</title></rect>`;
      sv+=`<text class="axislbl" x="${W-pr+6}" y="${cy+3}">${fmtS(t.act)}</text>`;});
    dumbbell=sv+'</svg>';
  }else dumbbell='<div class="empty">No timing history yet.<br><span style="font-size:11px">Welford stats appear after a few runs on this machine.</span></div>';

  let calib='';
  if(cal.length){const W=560,H=300,pad=44;const all=cal.flatMap(d=>[d.pred,d.act]),max=Math.max(...all,0.0001)*1.1;
    const x=v=>pad+v/max*(W-pad-12),y=v=>H-pad-v/max*(H-pad-12);
    let sv=`<svg class="viz" viewBox="0 0 ${W} ${H}">`;
    sv+=`<line x1="${x(0)}" y1="${y(0)}" x2="${x(max)}" y2="${y(max)}" stroke="#3a4252" stroke-dasharray="4 4"/><text class="axislbl" x="${x(max)-4}" y="${y(max)+12}" text-anchor="end">perfect forecast</text>`;
    [0,.5,1].forEach(f=>{sv+=`<text class="axislbl" x="${x(f*max)}" y="${H-pad+14}" text-anchor="middle">$${(f*max).toFixed(3)}</text><text class="axislbl" x="${pad-6}" y="${y(f*max)+3}" text-anchor="end">$${(f*max).toFixed(3)}</text>`;});
    cal.forEach(d=>{sv+=`<circle cx="${x(d.pred)}" cy="${y(d.act)}" r="5" fill="${d.colour}" fill-opacity="0.8"><title>${esc(d.label)} · pred $${d.pred} · actual $${d.act}</title></circle>`;});
    sv+=`<text class="axislbl" x="${(pad+W)/2}" y="${H-6}" text-anchor="middle">predicted cost →</text>`;
    calib=sv+'</svg>';
  }else calib='<div class="empty">No predicted-vs-actual cost pairs recorded.</div>';

  host.innerHTML=`<div class="grid g-2">
    <div class="card"><h2>Estimate vs actual <span class="sub">Welford μ ± σ · ● estimate ▎ actual</span></h2>${dumbbell}</div>
    <div class="card"><h2>Why this matters <span class="sub"></span></h2><p style="color:var(--muted);font-size:12px;line-height:1.6">Wide σ relative to μ = low forecast confidence for that stage — the signal that drives whether the progress ETA shows a number or a spinner. Stats are keyed per hardware profile; <code>n</code> is how many runs trained each estimate.</p></div></div>
    <div class="card" style="margin-top:14px"><h2>Forecast calibration <span class="sub">predicted vs actual cost · each LLM call · on the dashed line = perfect</span></h2>${calib}</div>`;
}
render();
</script></body></html>
"""
