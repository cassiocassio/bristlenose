#!/usr/bin/env python3
"""Design-token compliance auditor for bristlenose/theme/.

Computes the two-axis token-compliance metric the compliance-catalogue documents,
straight from the CSS source — so the numbers are reproducible instead of a hand
tally. See docs/design-system/compliance-catalogue.html ("How the score works").

    Coverage = (inside + 0.5*fixable) / themeable declarations * 100
    Health   = (1 - sum(severity*violations) / (3*themeable)) * 100

"Themeable" = declarations whose property should answer to the design system
(colour, font, spacing, radius, shadow, z-index, transition). Structural geometry
(display, position, flex, grid, width/height, …) is excluded from the denominator.
A small ignore-set (0, transparent, currentColor, inherit, 1px hairlines, 50/100%)
is never a violation.

Each themeable declaration is classified:
    inside   — value flows through a var(--bn-*) token (or light-dark/color-mix over tokens)
    fixable  — a literal that already equals an existing token value (one-line swap)
    outside  — a literal with no token; severity high (colour → breaks theming + dark
               mode) or low (off-scale spacing/radius/duration, magic z-index, shadow geometry)

Usage:
    python3 scripts/audit-css.py                # per-file + per-lens table
    python3 scripts/audit-css.py --by-lens      # lens summary only
    python3 scripts/audit-css.py --json         # machine-readable per-file records
    python3 scripts/audit-css.py --fail-under 60 # exit 1 if overall coverage < 60 (CI gate)

Limitations: a pragmatic regex parser (not a full CSS AST) and a per-file (not
per-component) granularity — a couple of components share one file. Good enough
to track the number release-over-release and gate regressions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

THEME = Path(__file__).resolve().parent.parent / "bristlenose" / "theme"

# ── metric weights (match the catalogue) ──────────────────────────────────────
FIX_CREDIT = 0.5
S_HIGH, S_LOW, S_FIX, S_MAX = 3, 1, 1, 3

# ── themeable property allowlist ──────────────────────────────────────────────
COLOUR_PROPS = {
    "color", "background", "background-color", "border-color", "outline-color",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "fill", "stroke", "caret-color", "text-decoration-color", "column-rule-color",
}
BORDER_PROPS = {  # shorthands that may carry a colour
    "border", "border-top", "border-right", "border-bottom", "border-left",
    "outline", "column-rule",
}
RADIUS_PROPS = {
    "border-radius", "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
}
SPACING_PROPS = {
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "gap", "row-gap", "column-gap",
}
TYPE_PROPS = {"font-size", "font-weight", "line-height", "letter-spacing"}
TRANSITION_PROPS = {"transition", "transition-duration", "animation", "animation-duration"}
SHADOW_PROPS = {"box-shadow"}
ZINDEX_PROPS = {"z-index"}

IGNORE_VALUES = {
    "0", "0px", "0rem", "0em", "none", "transparent", "currentcolor", "inherit",
    "initial", "unset", "auto", "50%", "100%", "1px", "1", "0 0", "1px 1px 0 0",
}
HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FUNC_COLOUR_RE = re.compile(r"\b(rgb|rgba|hsl|hsla)\(")
KEYWORD_COLOURS = {"white", "black", "red", "green", "blue", "gray", "grey", "silver"}
NUM_RE = re.compile(r"-?\d*\.?\d+(px|rem|em|%|s|ms)?")
DUR_RE = re.compile(r"(\d*\.?\d+)(ms|s)\b")


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def parse_token_values() -> dict[str, set[str]]:
    """Build value-sets for fixable-drift detection, straight from the token files."""
    text = ""
    for f in ("tokens.css", "tokens-typography.css", "tokens-desktop.css"):
        p = THEME / f
        if p.exists():
            text += strip_comments(p.read_text(encoding="utf-8"))
    vals = {"space": set(), "radius": set(), "dur": set(), "text": set(), "weight": set()}
    for name, value in re.findall(r"(--bn-[\w-]+)\s*:\s*([^;{}]+);", text):
        v = value.strip().lower()
        if name.startswith("--bn-space-"):
            vals["space"].add(v)
        elif name.startswith("--bn-radius-"):
            vals["radius"].add(v)
        elif name.startswith("--bn-transition-") or name == "--bn-overlay-duration":
            for num, unit in DUR_RE.findall(v):
                vals["dur"].add(f"{float(num):g}{unit}")
        elif re.match(r"--bn-text-[a-z]+$", name):  # size stops, not -lh
            vals["text"].add(v)
        elif name.startswith("--bn-weight-"):
            vals["weight"].add(v)
    return vals


def norm_durs(value: str) -> list[str]:
    return [f"{float(n):g}{u}" for n, u in DUR_RE.findall(value.lower())]


def has_token(value: str) -> bool:
    return "var(--bn-" in value


def has_literal_colour(value: str) -> bool:
    if HEX_RE.search(value) or FUNC_COLOUR_RE.search(value):
        return True
    tokens = re.split(r"[\s,()]+", value.lower())
    return any(t in KEYWORD_COLOURS for t in tokens)


def classify(prop: str, value: str, tv: dict[str, set[str]]) -> tuple[str, str, str] | None:
    """Return (state, severity, category) or None if the declaration is not themeable.

    state ∈ {good, fixable, bad}; severity ∈ {high, low, ''}; category is a slug.
    """
    prop = prop.lower().strip()
    v = value.strip().lower()
    if prop.startswith("--"):
        return None
    if v in IGNORE_VALUES or v == "":
        # still themeable but a legit non-value → count as inside (neutral)
        if prop in (COLOUR_PROPS | BORDER_PROPS | RADIUS_PROPS | SPACING_PROPS
                    | TYPE_PROPS | TRANSITION_PROPS | SHADOW_PROPS | ZINDEX_PROPS):
            return ("good", "", "inside")
        return None

    if prop in ZINDEX_PROPS:
        return ("good", "", "inside") if has_token(v) else ("bad", "low", "z-index")

    if prop in SHADOW_PROPS:
        if has_token(v) and not HEX_RE.search(v) and not FUNC_COLOUR_RE.search(v):
            return ("good", "", "inside")
        # tokenised colour but literal geometry, or fully literal → shadow geometry gap
        return ("bad", "low", "shadow")

    if prop in COLOUR_PROPS:
        if has_token(v):
            return ("good", "", "inside")
        if has_literal_colour(v):
            return ("bad", "high", "hardcoded-colour")
        return ("good", "", "inside")  # e.g. currentColor handled above; else non-colour keyword

    if prop in BORDER_PROPS:
        if has_token(v):
            return ("good", "", "inside")
        if has_literal_colour(v):
            return ("bad", "high", "hardcoded-colour")
        return ("good", "", "inside")  # width/style only, no colour → not a violation

    if prop in RADIUS_PROPS:
        if has_token(v):
            return ("good", "", "inside")
        parts = v.split()
        if all(p in tv["radius"] or p in IGNORE_VALUES for p in parts):
            return ("fixable", "low", "scale-gap")
        return ("bad", "low", "scale-gap")

    if prop in SPACING_PROPS:
        if has_token(v):
            return ("good", "", "inside")
        parts = [p for p in v.split() if p not in ("0",)]
        if not parts:
            return ("good", "", "inside")
        if all(p in tv["space"] for p in parts):
            return ("fixable", "low", "scale-gap")
        return ("bad", "low", "scale-gap")

    if prop in TYPE_PROPS:
        if has_token(v):
            return ("good", "", "inside")
        if prop == "font-weight":
            return ("fixable", "low", "scale-gap") if v in tv["weight"] else ("bad", "low", "scale-gap")
        if prop == "font-size":
            return ("fixable", "low", "scale-gap") if v in tv["text"] else ("bad", "low", "scale-gap")
        # line-height / letter-spacing literal
        return ("bad", "low", "scale-gap")

    if prop in TRANSITION_PROPS:
        if has_token(v):
            return ("good", "", "inside")
        durs = norm_durs(v)
        if durs and all(d in tv["dur"] for d in durs):
            return ("fixable", "low", "scale-gap")
        if not durs:  # e.g. "transform" with no duration listed
            return ("good", "", "inside")
        return ("bad", "low", "scale-gap")

    return None  # structural property → excluded from denominator


# ── file → lens map (mirrors the catalogue) ───────────────────────────────────
LENS_OF = {
    # quotes
    "organisms/blockquote.css": "quotes", "atoms/badge.css": "quotes",
    "atoms/timecode.css": "quotes", "atoms/span-bar.css": "quotes",
    "molecules/person-badge.css": "quotes", "molecules/quote-actions.css": "quotes",
    "molecules/editable-text.css": "quotes", "molecules/tag-input.css": "quotes",
    # sessions
    "atoms/thumbnail.css": "sessions", "atoms/journey-label.css": "sessions",
    "molecules/sparkline.css": "sessions", "organisms/coverage.css": "sessions",
    # themes
    "atoms/context-expansion.css": "themes", "molecules/badge-row.css": "themes",
    "organisms/toc.css": "themes", "organisms/responsive-grid.css": "themes",
    "organisms/uncategorised-floor.css": "themes",
    # analysis
    "atoms/bar.css": "analysis", "molecules/bar-group.css": "analysis",
    "organisms/sentiment-chart.css": "analysis", "organisms/analysis.css": "analysis",
    # codebook
    "atoms/autocode-toast.css": "codebook", "atoms/activity-chip.css": "codebook",
    "atoms/moderator-question.css": "codebook", "molecules/tag-filter.css": "codebook",
    "molecules/threshold-review.css": "codebook", "molecules/autocode-report.css": "codebook",
    "organisms/codebook-panel.css": "codebook", "organisms/sidebar-tags.css": "codebook",
}
LENS_ORDER = ["quotes", "sessions", "themes", "analysis", "codebook", "shell"]

# component CSS lives in these dirs; token/palette files are the DEFINITIONS (excluded)
SCAN_DIRS = ["atoms", "molecules", "organisms", "templates"]


def audit_file(path: Path, tv: dict[str, set[str]]) -> dict:
    css = strip_comments(path.read_text(encoding="utf-8"))
    good = warn = bad = high = low = 0
    cats: dict[str, int] = {}
    for prop, value in re.findall(r"([\w-]+)\s*:\s*([^;{}]+);", css):
        res = classify(prop, value, tv)
        if res is None:
            continue
        state, sev, cat = res
        if state == "good":
            good += 1
        elif state == "fixable":
            warn += 1
        else:
            bad += 1
            if sev == "high":
                high += 1
            else:
                low += 1
            cats[cat] = cats.get(cat, 0) + 1
    return {"good": good, "warn": warn, "bad": bad, "high": high, "low": low, "cats": cats}


def metric(good: int, warn: int, bad: int, high: int, low: int) -> tuple[float, float, int]:
    n = good + warn + bad
    if n == 0:
        return (100.0, 100.0, 0)
    cov = 100 * (good + FIX_CREDIT * warn) / n
    pen = S_HIGH * high + S_LOW * low + S_FIX * warn
    health = 100 * (1 - pen / (S_MAX * n))
    return (cov, health, n)


def grade(cov: float) -> str:
    for thr, g in [(90, "A"), (85, "A-"), (80, "B+"), (70, "B"), (60, "C+"), (50, "C"), (40, "D+")]:
        if cov >= thr:
            return g
    return "D"


def main() -> int:
    ap = argparse.ArgumentParser(description="Design-token compliance auditor.")
    ap.add_argument("--json", action="store_true", help="emit per-file JSON records")
    ap.add_argument("--by-lens", action="store_true", help="lens summary only")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="exit 1 if overall coverage is below this percentage")
    args = ap.parse_args()

    tv = parse_token_values()
    files = sorted(
        p for d in SCAN_DIRS for p in (THEME / d).glob("*.css")
    )
    records = []
    for p in files:
        rel = f"{p.parent.name}/{p.name}"
        r = audit_file(p, tv)
        cov, health, n = metric(r["good"], r["warn"], r["bad"], r["high"], r["low"])
        if n == 0:
            continue  # no themeable declarations (pure layout file)
        records.append({
            "file": rel, "lens": LENS_OF.get(rel, "shell"), **r,
            "themeable": n, "coverage": round(cov, 1), "health": round(health, 1),
            "grade": grade(cov),
        })

    if args.json:
        print(json.dumps(records, indent=2))
        return 0

    # per-lens aggregation
    lens_tot: dict[str, dict] = {k: {"good": 0, "warn": 0, "bad": 0, "high": 0, "low": 0} for k in LENS_ORDER}
    for r in records:
        t = lens_tot[r["lens"]]
        for k in ("good", "warn", "bad", "high", "low"):
            t[k] += r[k]

    if not args.by_lens:
        print(f"{'file':38} {'lens':9} {'cov':>5} {'health':>7} {'grade':>6}  in/fix/out")
        print("-" * 88)
        for r in sorted(records, key=lambda x: (LENS_ORDER.index(x["lens"]), -x["coverage"])):
            print(f"{r['file']:38} {r['lens']:9} {r['coverage']:5.0f} {r['health']:7.0f} "
                  f"{r['grade']:>6}  {r['good']}/{r['warn']}/{r['bad']}")
        print()

    print(f"{'LENS':9} {'files':>5} {'cov':>5} {'health':>7}  in/fix/out")
    print("-" * 48)
    tot_g = tot_w = tot_b = tot_h = tot_l = 0
    for k in LENS_ORDER:
        t = lens_tot[k]
        n = t["good"] + t["warn"] + t["bad"]
        if n == 0:
            continue
        cov, health, _ = metric(t["good"], t["warn"], t["bad"], t["high"], t["low"])
        nf = sum(1 for r in records if r["lens"] == k)
        print(f"{k:9} {nf:5} {cov:5.0f} {health:7.0f}  {t['good']}/{t['warn']}/{t['bad']}")
        tot_g += t["good"]
        tot_w += t["warn"]
        tot_b += t["bad"]
        tot_h += t["high"]
        tot_l += t["low"]
    ov_cov, ov_health, _ = metric(tot_g, tot_w, tot_b, tot_h, tot_l)
    print("-" * 48)
    print(f"{'OVERALL':9} {len(records):5} {ov_cov:5.0f} {ov_health:7.0f}  {tot_g}/{tot_w}/{tot_b}")

    if args.fail_under is not None and ov_cov < args.fail_under:
        print(f"\nFAIL: overall coverage {ov_cov:.1f}% < --fail-under {args.fail_under}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
