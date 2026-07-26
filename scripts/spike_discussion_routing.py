#!/usr/bin/env python3
"""SPIKE — Discussion lens routing de-risk (Phase A).

Backend-only proof for docs/design-discussion-lens.md. Given a project's
extracted quotes and a discussion guide, it:

  1. parses the guide into ~5-12 TERRITORIES (LLM, parse-discussion-guide.md),
  2. routes each quote to a territory or UNROUTED (LLM, batched,
     route-quotes-to-territories.md), matching on each territory's whole field,
  3. prints a report: distilled territories, routed X of Y, per-territory
     density (signal-bar sketch), a sample of routed quotes, and the token/cost
     footprint.

It answers the only real unknown before building the lens: does real evidence
land in the right territory, at what cost, and does conservative-omission read
as honest or broken. NOT wired into the pipeline or the app — a throwaway
harness. Reuses the real LLMClient, so provider/model/keys come from your
environment exactly as the CLI/app resolve them.

Usage:
    .venv/bin/python scripts/spike_discussion_routing.py \
        --project trial-runs/project-ikea/bristlenose-output \
        --guide /path/to/discussion-guide.txt \
        [--batch 25] [--limit 0] [--out spike-report.md]

The guide may be .txt or .md (read directly) or .docx (needs python-docx).
Keep private data private: point --project at whatever you're comfortable
running through your configured provider (Ollama keeps it local).
"""

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from bristlenose.config import BristlenoseSettings
from bristlenose.llm.client import LLMClient

PROMPTS = Path(__file__).resolve().parent.parent / "bristlenose" / "llm" / "prompts"


# ── Structured-output models (spike-local; graduate to models.py if this ships) ──


# Length budgets are a CONTRACT, not a hope — the ≤2-screen sidebar depends on it.
# max_length carries into the provider's structured-output schema (maxLength) and
# validation catches violations; caps have headroom over the prompt's asks
# (terse ≤28, scaffold.terse ≤34, intent ≤100) so normal output passes but a
# runaway string is caught rather than silently blowing the sidebar.


class ScaffoldItem(BaseModel):
    terse: str = Field(max_length=34)  # sidebar disclosure sub-label (prompt: ≤24)
    verbatim: str = ""                 # hidden match material — uncapped


class Territory(BaseModel):
    nav_terse: str = Field(max_length=26)  # sidebar row — orientation (prompt: ≤18)
    heading: str = Field(max_length=56)    # content heading — fuller (prompt: ≤40)
    intent: str = Field(max_length=140)    # content one-liner (prompt: ≤100); match = intent + scaffold
    kind: Literal["questions", "task", "instruction"] = "questions"
    stance_axis: Literal["opinion", "pattern", "none"] = "pattern"
    scaffold: list[ScaffoldItem] = Field(default_factory=list)


class ParsedGuide(BaseModel):
    territories: list[Territory]


class QuoteRoute(BaseModel):
    id: str
    territory_id: str  # "t3" or "UNROUTED"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    margin: float = Field(default=0.0, ge=0.0, le=1.0)


class RouteBatch(BaseModel):
    routes: list[QuoteRoute]


# ── Prompt loading (house format: frontmatter + ## System / ## User) ──────────


def load_prompt(name: str) -> tuple[str, str]:
    """Return (system_prompt, user_template) from a house-format prompt file."""
    text = (PROMPTS / name).read_text(encoding="utf-8")
    # strip YAML frontmatter
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
    sys_m = re.search(r"\n## System\n(.*?)(?=\n## User\n)", text, flags=re.DOTALL)
    usr_m = re.search(r"\n## User\n(.*)$", text, flags=re.DOTALL)
    if not sys_m or not usr_m:
        raise SystemExit(f"prompt {name}: missing ## System / ## User sections")
    return sys_m.group(1).strip(), usr_m.group(1).strip()


def fill(template: str, **vars: str) -> str:
    for k, v in vars.items():
        template = template.replace("{" + k + "}", v)
    return template


# ── Guide + quotes loading ────────────────────────────────────────────────────


def load_guide_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            raise SystemExit("docx guide needs python-docx (pip install python-docx), "
                             "or export the guide to .txt/.md")
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    raise SystemExit(f"unsupported guide format: {suffix} (use .txt/.md/.docx)")


def load_quotes(project: Path) -> list[dict]:
    candidates = [
        project / ".bristlenose" / "intermediate" / "extracted_quotes.json",
        project / "intermediate" / "extracted_quotes.json",
        project,  # allow passing the json file directly
    ]
    for c in candidates:
        if c.is_file():
            data = json.loads(c.read_text(encoding="utf-8"))
            quotes = data.get("quotes", data) if isinstance(data, dict) else data
            if isinstance(quotes, list) and quotes:
                return quotes
    raise SystemExit(
        f"no extracted_quotes.json under {project} — run analysis first, or pass "
        "the json path directly to --project"
    )


# ── Rendering ─────────────────────────────────────────────────────────────────


def territories_block(guide: ParsedGuide) -> str:
    lines = []
    for i, t in enumerate(guide.territories):
        scaf = " · ".join(s.terse for s in t.scaffold)
        lines.append(
            f"t{i} [{t.kind}/{t.stance_axis}] {t.heading}\n"
            f"    intent: {t.intent}\n"
            f"    covers: {scaf or '(none)'}"
        )
    return "\n".join(lines)


def quotes_block(batch: list[dict], ids: list[str]) -> str:
    out = []
    for qid, q in zip(ids, batch):
        text = (q.get("text") or q.get("verbatim_excerpt") or "").replace("\n", " ").strip()
        out.append(f'{qid} | {q.get("participant_id", "?")} | "{text}"')
    return "\n".join(out)


def bar(n: int, peak: int, width: int = 18) -> str:
    if peak <= 0:
        return ""
    filled = round(width * n / peak)
    return "▓" * filled + "░" * (width - filled)


# ── Orchestration ─────────────────────────────────────────────────────────────


async def run(args: argparse.Namespace) -> str:
    settings = BristlenoseSettings()
    client = LLMClient(settings)
    report: list[str] = []

    def emit(line: str = "") -> None:
        print(line)
        report.append(line)

    emit(f"# Discussion-routing spike — {args.project}")
    emit(f"provider={settings.llm_provider}  guide={Path(args.guide).name}")
    emit()

    # 1. parse the guide -------------------------------------------------------
    guide_text = load_guide_text(Path(args.guide))
    p_sys, p_usr = load_prompt("parse-discussion-guide.md")
    t0 = time.monotonic()
    guide = await client.analyze(
        system_prompt=p_sys,
        user_prompt=fill(p_usr, guide_text=guide_text),
        response_model=ParsedGuide,
        max_tokens=8000,
    )
    parse_s = time.monotonic() - t0
    routable = [i for i, t in enumerate(guide.territories) if t.kind != "instruction"]
    emit(f"## Distilled guide — {len(guide.territories)} territories "
         f"({len(routable)} routable) in {parse_s:.1f}s")
    for i, t in enumerate(guide.territories):
        tag = "  (instruction — quarantined)" if t.kind == "instruction" else ""
        emit(f"  t{i}  {t.heading}  [{t.kind}/{t.stance_axis}]  ·{len(t.scaffold)} folded{tag}")
    emit()

    # 2. route quotes in batches ----------------------------------------------
    quotes = load_quotes(Path(args.project))
    if args.limit:
        quotes = quotes[: args.limit]
    r_sys, r_usr = load_prompt("route-quotes-to-territories.md")
    tblock = territories_block(guide)
    ids = [f"q{i}" for i in range(len(quotes))]

    counts: dict[str, int] = {f"t{i}": 0 for i in range(len(guide.territories))}
    counts["UNROUTED"] = 0
    routed_samples: dict[str, list[str]] = {}
    low_margin = 0

    t0 = time.monotonic()
    batches = [
        (ids[i : i + args.batch], quotes[i : i + args.batch])
        for i in range(0, len(quotes), args.batch)
    ]
    for n, (bids, bq) in enumerate(batches, 1):
        result: RouteBatch = await client.analyze(
            system_prompt=r_sys,
            user_prompt=fill(r_usr, territories_block=tblock, quotes_block=quotes_block(bq, bids)),
            response_model=RouteBatch,
            max_tokens=4000,
        )
        by_id = {r.id: r for r in result.routes}
        for qid, q in zip(bids, bq):
            r = by_id.get(qid)
            dest = r.territory_id if (r and r.territory_id in counts) else "UNROUTED"
            counts[dest] += 1
            if r and dest != "UNROUTED" and r.margin and r.margin < 0.15:
                low_margin += 1
            if dest != "UNROUTED":
                text = (q.get("text") or "").replace("\n", " ").strip()
                routed_samples.setdefault(dest, [])
                if len(routed_samples[dest]) < 3:
                    routed_samples[dest].append(f'{q.get("participant_id","?")}: "{text[:120]}"')
        print(f"  … routed batch {n}/{len(batches)}", file=sys.stderr)
    route_s = time.monotonic() - t0

    # 3. report ---------------------------------------------------------------
    total = len(quotes)
    unrouted = counts["UNROUTED"]
    routed = total - unrouted
    peak = max((counts[f"t{i}"] for i in routable), default=0)
    emit(f"## Routing — {routed} of {total} quotes routed "
         f"({100*routed//max(total,1)}%), {unrouted} UNROUTED, in {route_s:.1f}s")
    emit(f"   near-ties (margin<0.15): {low_margin}   ·   batches: {len(batches)}")
    emit()
    emit("## Evidence density by territory (the signal bars)")
    for i, t in enumerate(guide.territories):
        if t.kind == "instruction":
            continue
        c = counts[f"t{i}"]
        emit(f"  {c:>4}  {bar(c, peak)}  {t.heading}")
    emit(f"  {unrouted:>4}  {'·'*0}  UNROUTED (stay in the Quotes lens)")
    emit()
    emit("## Sample routed quotes (eyeball precision — are these in-territory?)")
    for i, t in enumerate(guide.territories):
        s = routed_samples.get(f"t{i}")
        if not s:
            continue
        emit(f"### t{i} {t.heading}")
        for line in s:
            emit(f"  - {line}")
    emit()
    emit(f"## Cost footprint\n  {client.tracker.summary() if hasattr(client.tracker, 'summary') else client.tracker}")
    emit(f"  parse {parse_s:.1f}s · route {route_s:.1f}s · {len(batches)+1} LLM calls")

    return "\n".join(report)


def main() -> None:
    ap = argparse.ArgumentParser(description="Discussion lens routing spike")
    ap.add_argument("--project", required=True,
                    help="path to <project>/bristlenose-output (or an extracted_quotes.json)")
    ap.add_argument("--guide", required=True, help="discussion guide .txt/.md/.docx")
    ap.add_argument("--batch", type=int, default=25, help="quotes per routing call")
    ap.add_argument("--limit", type=int, default=0, help="cap number of quotes (0 = all)")
    ap.add_argument("--out", default="", help="write the full report to this markdown file")
    args = ap.parse_args()

    report = asyncio.run(run(args))
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"\nreport → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
