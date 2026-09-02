#!/usr/bin/env python3
"""Generate the testing/gate inventory from source. Never hand-write it.

WHY THIS IS A GENERATOR

Every wrong claim found in the 2 Sep 2026 audit was load-bearing in the same
way: it made a cheap fix look expensive, and so bought weeks of delay.

  * desktop/CLAUDE.md  "CI does not build the Swift target"  -- false when
    written, three months after the workflow landed. Made a one-step fix read
    as "stand up macOS CI".
  * docs/design-ci.md  "~$0.20/push at 10x rate"  -- the private-repo rate on a
    public repo. Free. Hung a price on work that had none.
  * docs/design-ci.md  "already has 5 test files"  -- there are 106.
  * docs/testing/README.md  "16 ingest formats"  -- while naming
    coverage-inventory.md as its single source, which says 27.

None of those were careless. They were true once, or nearly true, and nothing
was ever obliged to revisit them. So: anything derivable from the tree is
derived here, and `--check` fails the moment the committed doc disagrees.

TWO TIERS, DELIBERATELY

  structure     What runs, when, where, and what happens when it fails.
                Changes only when someone changes the system. `--check`
                compares this, so drift is a hard failure.

  measurements  Suite sizes. These move on every commit that adds a test, so
                checking them would make the gate cry wolf until someone
                switched it off -- the failure mode this repo has paid for
                twice. Reported with a date, never gated.

Usage:
  scripts/gen-test-inventory.py            write docs/testing/inventory.{json,md}
  scripts/gen-test-inventory.py --check    exit 1 if structure has drifted
  scripts/gen-test-inventory.py --stdout   print the markdown, write nothing
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "docs/testing/inventory.json"
OUT_MD = ROOT / "docs/testing/inventory.md"

# A step is a test run if its shell mentions one of these.
TEST_CMD = re.compile(
    r"\bpytest\b|\bvitest\b|npm (?:run )?test|playwright test|test-swift\.sh"
    r"|xcodebuild\s+(?:test|build-for-testing)|test-without-building",
    re.I,
)


def sh(*args: str) -> str:
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=180).stdout
    except Exception:
        return ""


def load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text()) or {}


def triggers(wf: dict) -> list[str]:
    # YAML 1.1 parses a bare `on:` key as the BOOLEAN True. Every naive reader
    # of a GitHub workflow hits this and concludes the file has no triggers.
    raw = wf.get("on", wf.get(True, {}))
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return list(raw)
    out = []
    for event, cfg in (raw or {}).items():
        detail = ""
        if isinstance(cfg, dict):
            if "branches" in cfg:
                detail = f" [{','.join(cfg['branches'])}]"
            elif "tags" in cfg:
                detail = f" [{','.join(cfg['tags'])}]"
            elif "cron" in str(cfg):
                crons = [c.get("cron") for c in cfg] if isinstance(cfg, list) else []
                detail = f" ({';'.join(filter(None, crons))})"
            if isinstance(cfg, dict) and "paths" in cfg:
                detail += f" paths={','.join(cfg['paths'])}"
        elif isinstance(cfg, list):
            crons = [c.get("cron") for c in cfg if isinstance(c, dict)]
            detail = f" ({';'.join(filter(None, crons))})" if crons else ""
        out.append(f"{event}{detail}")
    return out


def colour(step: dict) -> str:
    """hard = a failure fails the job. soft = it does not. conditional = depends."""
    coe = step.get("continue-on-error")
    if coe is None:
        return "hard"
    if coe is True:
        return "soft"
    if coe is False:
        return "hard"
    return f"conditional: {str(coe).strip()}"


def scan_workflows() -> list[dict]:
    out = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        wf = load_yaml(path)
        jobs = []
        for jid, job in (wf.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            steps = []
            for st in job.get("steps") or []:
                if not isinstance(st, dict):
                    continue
                run = st.get("run") or ""
                if not (TEST_CMD.search(run) or st.get("continue-on-error") is not None):
                    continue
                piped = bool(re.search(r"\|\s*\w", run)) and "pipefail" not in run
                steps.append(
                    {
                        "name": st.get("name") or (st.get("uses") or "")[:40],
                        "runs_tests": bool(TEST_CMD.search(run)),
                        "colour": colour(st),
                        "piped": piped,
                    }
                )
            jobs.append(
                {
                    "id": jid,
                    "runs_on": str(job.get("runs-on", "")),
                    "job_colour": colour(job),
                    "calls": str(job.get("uses", "")) or None,
                    "notable_steps": steps,
                }
            )
        has_shell = bool(((wf.get("defaults") or {}).get("run") or {}).get("shell"))
        piped_steps = []
        if not has_shell:
            for job in (wf.get("jobs") or {}).values():
                if not isinstance(job, dict):
                    continue
                for st in job.get("steps") or []:
                    if not isinstance(st, dict):
                        continue
                    run = st.get("run") or ""
                    if "pipefail" in run:
                        continue
                    if re.search(r"^(?!\s*if\b).*\|\s*(tee|head|tail|grep|xcpretty)\b", run, re.M):
                        piped_steps.append(st.get("name") or "(unnamed)")
        out.append(
            {
                "piped_steps": sorted(set(piped_steps)),
                "file": path.name,
                "name": wf.get("name", path.stem),
                "triggers": triggers(wf),
                "default_shell": ((wf.get("defaults") or {}).get("run") or {}).get("shell"),
                "jobs": jobs,
            }
        )
    return out


def scan_build_gates() -> list[dict]:
    """The numbered steps of BOTH shipping entry points.

    Two scripts, two certificates, two channels — build-all.sh signs the App
    Store archive under Apple Distribution, build-dmg.sh signs the notarised
    direct download under Developer ID. They are not interchangeable and neither
    covers the other, which is how the .dmg went without a Swift gate until
    3 Sep 2026. A map that showed only one of them would hide that class again.
    """
    gates = []

    src = (ROOT / "desktop/scripts/build-all.sh").read_text()
    seen: dict[str, dict] = {}
    # Two call shapes, and missing the second is not cosmetic: bn_step_skip is
    # written `bn_step_skip 1c phase=Verify name="..."`, which the positional
    # pattern cannot match — so every skippable gate reported as unskippable.
    # Caught by this file's own output on 3 Sep 2026, which is the point of it.
    for m in re.finditer(
        r'bn_step_(start|skip)\s+(\S+)\s+(?:(\w+)\s+"([^"]+)"'
        r'|phase=(\w+)\s+name="([^"]+)")',
        src,
    ):
        kind, sid = m.group(1), m.group(2)
        phase = m.group(3) or m.group(5) or ""
        name = m.group(4) or m.group(6) or ""
        g = seen.setdefault(
            sid,
            {"script": "build-all.sh", "id": sid, "phase": phase, "name": name, "can_skip": False},
        )
        if kind == "skip":
            g["can_skip"] = True
        if not g["phase"]:
            g["phase"], g["name"] = phase, name
    gates += sorted(seen.values(), key=lambda g: g["id"])

    # build-dmg.sh predates report.sh and announces stages with `say "..."`,
    # numbered by the `# N.` banner above each.
    dmg = (ROOT / "desktop/scripts/build-dmg.sh").read_text()
    for m in re.finditer(r'^# (\d+[a-z]?)\. ([^\n]+)\n(?:#[^\n]*\n)*?.*?^say "([^"]+)"',
                         dmg, re.M | re.S):
        sid, banner, name = m.groups()
        gates.append(
            {
                "script": "build-dmg.sh",
                "id": sid,
                "phase": banner.split("—")[0].strip(),
                "name": name,
                "can_skip": "SKIP_SWIFT_TESTS" in dmg.split(f'say "{name}"')[1][:400],
            }
        )
    return gates


def scan_local_hooks() -> dict:
    out: dict[str, list[str]] = {"pre_commit": [], "agent_hooks": []}
    pc = ROOT / ".pre-commit-config.yaml"
    if pc.exists():
        cfg = load_yaml(pc)
        for repo in cfg.get("repos", []):
            for hook in repo.get("hooks", []):
                out["pre_commit"].append(hook.get("name") or hook.get("id"))
    st = ROOT / ".claude/settings.json"
    if st.exists():
        hooks = json.loads(st.read_text()).get("hooks", {})
        for event, entries in hooks.items():
            for e in entries:
                for h in e.get("hooks", []):
                    cmd = Path(h.get("command", "").split()[0]).name if h.get("command") else "?"
                    out["agent_hooks"].append(f"{event}:{e.get('matcher','*')} -> {cmd}")
    return out


def scan_suites(sizes: bool = True) -> list[dict]:
    py = None if not sizes else re.search(r"(\d+) tests collected", sh(".venv/bin/python", "-m", "pytest", "tests/", "--collect-only", "-q"))
    swift_files = list((ROOT / "desktop/Bristlenose/BristlenoseTests").glob("*.swift"))
    # DECLARED, not executed. A parameterised `@Test(arguments:)` expands into
    # one case per argument at runtime, so this is a floor: 1382 declared ran as
    # 1406 on 3 Sep 2026. Reporting it as "tests" would be a number that looks
    # authoritative and is short — the exact defect this file exists to prevent.
    swift_src = [f.read_text(errors="ignore") for f in swift_files] if sizes else []
    swift_n = sum(len(re.findall(r"@Test\b", t)) for t in swift_src) + sum(
        len(re.findall(r"func test[A-Za-z0-9_]*\(", t)) for t in swift_src
    )
    vitest_files = list((ROOT / "frontend/src").rglob("*.test.*"))
    e2e = sorted(p.name for p in (ROOT / "e2e/tests").glob("*.spec.ts"))
    return [
        {"suite": "pytest", "kind": "python unit/integration", "runner": "pytest",
         "files": None, "tests": int(py.group(1)) if py else None,
         "basis": "collected (expands parametrize — authoritative)",
         "source": "tests/"},
        {"suite": "vitest", "kind": "frontend unit", "runner": "vitest",
         "files": len(vitest_files), "tests": None, "basis": "test files",
         "source": "frontend/src/**/*.test.*"},
        {"suite": "BristlenoseTests", "kind": "swift unit", "runner": "xcodebuild",
         "files": len(swift_files), "tests": swift_n,
         "basis": "declared — a floor; parameterised cases expand at runtime",
         "source": "desktop/Bristlenose/BristlenoseTests/"},
        {"suite": "playwright", "kind": "browser e2e", "runner": "playwright",
         "files": len(e2e), "tests": None, "basis": "spec files",
         "source": "e2e/tests/ (" + ", ".join(e2e) + ")"},
    ]


def build(structure_only: bool = False) -> dict:
    # --check compares `structure`, so skip `measurements` there: it costs a
    # pytest collect against a .venv that CI has no reason to create.
    if structure_only:
        return {
            "structure": {
                "workflows": scan_workflows(),
                "build_gates": scan_build_gates(),
                "local_hooks": scan_local_hooks(),
                "suites": [
                    {k: v for k, v in s.items() if k not in ("tests", "files")}
                    for s in scan_suites(sizes=False)
                ],
            }
        }
    return {
        "structure": {
            "workflows": scan_workflows(),
            "build_gates": scan_build_gates(),
            "local_hooks": scan_local_hooks(),
            "suites": [{k: v for k, v in s.items() if k not in ("tests", "files")} for s in scan_suites()],
        },
        "measurements": {"suites": scan_suites()},
    }


def render(data: dict) -> str:
    st = data["structure"]
    lines = [
        "# Testing & gates — generated inventory",
        "",
        "> **Generated by `scripts/gen-test-inventory.py`. Do not edit.**",
        "> `--check` fails when the *structure* below drifts from the tree.",
        "> Suite sizes are reported, never gated — they move on every commit, and a",
        "> gate that cries wolf is a gate someone switches off.",
        "",
        "## Suites",
        "",
        "| suite | kind | size | what the number counts | source |",
        "|---|---|---|---|---|",
    ]
    for s in data["measurements"]["suites"]:
        size = f"{s['tests']}" if s["tests"] else ""
        if s["files"]:
            size = f"{size + ' in ' if size else ''}{s['files']} files"
        lines.append(f"| `{s['suite']}` | {s['kind']} | {size or '—'} | {s.get('basis','—')} | `{s['source']}` |")

    lines += ["", "## When they run — and what happens when they fail", ""]
    for wf in st["workflows"]:
        shell = wf["default_shell"]
        lines.append(f"### {wf['name']} (`{wf['file']}`)")
        lines.append("")
        lines.append(f"- **Triggers:** {'; '.join(wf['triggers']) or '—'}")
        if shell:
            lines.append(f"- **Default shell:** `{shell}` (pipefail on)")
        elif wf["piped_steps"]:
            lines.append("- **Default shell:** GitHub default (`bash -e`, **no pipefail**). "
                     "Piped steps below report the LAST stage's exit status, not the command's — "
                     "check each is not load-bearing. (This is what hid 16 compile errors behind "
                     "a green Mac Build, 20 May – 2 Sep 2026.)")
            for n in wf["piped_steps"]:
                lines.append(f"  - piped: _{n}_")
        else:
            lines.append("- **Default shell:** GitHub default (`bash -e`, no pipefail) — no piped steps")
        for j in wf["jobs"]:
            bits = [f"`{j['id']}`"]
            if j["runs_on"]:
                bits.append(f"on `{j['runs_on']}`")
            if j["calls"]:
                bits.append(f"calls `{j['calls']}`")
            if j["job_colour"] != "hard":
                bits.append(f"**{j['job_colour']}**")
            lines.append(f"  - {' · '.join(bits)}")
            for s in j["notable_steps"]:
                tag = "runs tests" if s["runs_tests"] else "gate"
                lines.append(f"    - {s['name']} — {tag}, **{s['colour']}**")
        lines.append("")

    lines += ["## Build gates — both shipping entry points, in order", "",
          "Two scripts, two certificates, two channels. Neither covers the other.", "",
          "| script | step | phase | gate | skippable |", "|---|---|---|---|---|"]
    for g in st["build_gates"]:
        lines.append(f"| `{g['script']}` | {g['id']} | {g['phase']} | {g['name']} "
                     f"| {'yes' if g['can_skip'] else 'no'} |")

    lines += ["", "## Local gates", "",
          "**pre-commit:** " + ", ".join(st["local_hooks"]["pre_commit"] or ["—"]), ""]
    for h in st["local_hooks"]["agent_hooks"]:
        lines.append(f"- `{h}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    if "--check" in sys.argv:
        if not OUT_JSON.exists():
            print("inventory.json missing — run scripts/gen-test-inventory.py", file=sys.stderr)
            return 1
        if json.loads(OUT_JSON.read_text()).get("structure") != build(structure_only=True)["structure"]:
            print("STRUCTURE DRIFT — regenerate: scripts/gen-test-inventory.py", file=sys.stderr)
            return 1
        print("inventory structure current")
        return 0
    data = build()
    md = render(data)
    if "--stdout" in sys.argv:
        print(md)
        return 0
    OUT_JSON.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    OUT_MD.write_text(md)
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
