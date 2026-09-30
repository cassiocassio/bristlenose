"""Build the hand-labelling page from a run.py result.

    .venv/bin/python experiments/speaker_split_full/build_page.py \
        trial-runs/speaker-split/<name>.json trial-runs/speaker-split/<name>.html

The page embeds the transcript text, so it belongs in trial-runs/ (gitignored),
never in the tracked tree. Videos play from their file:// paths.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

TEMPLATE = (Path(__file__).parent / "page.html").read_text()


def main(run_path: Path, out: Path) -> None:
    run = json.loads(run_path.read_text())
    output_dir = Path(run["output_dir"])
    people = yaml.safe_load((output_dir / "people.yaml").read_text())["participants"]
    sources = {
        p["computed"]["session_id"]: p["computed"]["source_file"]
        for p in people.values()
        if p["computed"].get("source_file")
    }
    for s in run["sessions"]:
        src = sources.get(s["session_id"])
        s["video"] = (output_dir.parent / src).as_uri() if src else None
        s["source"] = src or ""
        s.pop("split_raw", None)
    data = (
        json.dumps({"run": run_path.stem, "sessions": run["sessions"]}, ensure_ascii=True)
        .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    out.write_text(TEMPLATE.replace("/*DATA*/null", data))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
