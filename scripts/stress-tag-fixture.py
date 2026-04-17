#!/usr/bin/env python3
"""Augment a stress fixture's SQLite DB with realistic tag fanout.

The serve-mode importer only auto-applies the sentiment codebook (one
tag per quote).  Real AutoCode-processed projects have several
codebook groups with multiple tags per quote — the sidebar endpoint
returns ~10x the payload a sentiment-only fixture produces.

This script opens the per-project SQLite directly (WAL mode means
running concurrently with the server is safe) and adds:
    - Two codebook groups: "User goals" and "Friction types"
    - 6 tag definitions per group
    - 1-2 randomly assigned tags per group per quote, source="autocode"

Run AFTER ``bristlenose serve`` has completed its initial import.
The script is idempotent — re-running adds no duplicate rows.

Usage:
    python scripts/stress-tag-fixture.py --db <path-to-bristlenose.db> [--seed N]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Path juggling so the script can import from the bristlenose package
# without `pip install -e .` assumptions.  The orchestrator always uses
# the repo venv so bristlenose is importable there, but the explicit
# sys.path insert keeps this script self-contained.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from bristlenose.server.models import (  # noqa: E402
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    Quote,
    QuoteTag,
    TagDefinition,
)

# Two synthetic codebook groups.  framework_id uses a `stress-` prefix so
# these never collide with real frameworks (garrett/norman/uxr/plato)
# and the orchestrator's cleanup can find them later if needed.
_GROUPS = [
    {
        "name": "User goals",
        "subtitle": "Synthetic — stress fixture",
        "framework_id": "stress-goals",
        "colour_set": "cool",
        "tags": [
            "discoverability",
            "speed",
            "reliability",
            "control",
            "clarity",
            "learning",
        ],
    },
    {
        "name": "Friction types",
        "subtitle": "Synthetic — stress fixture",
        "framework_id": "stress-friction",
        "colour_set": "warm",
        "tags": [
            "missing-cue",
            "hidden-affordance",
            "wrong-mental-model",
            "unclear-feedback",
            "destructive-default",
            "lost-context",
        ],
    },
]


def augment(db_path: Path, seed: int = 0) -> None:
    """Add synthetic codebook groups and apply tags to every quote."""
    random.seed(seed)

    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        project = db.query(Project).first()
        if project is None:
            raise SystemExit(f"No Project row in {db_path}")

        # --- Create (or find) the synthetic groups + tag definitions
        tag_defs_by_group: dict[int, list[TagDefinition]] = {}
        for g in _GROUPS:
            group = (
                db.query(CodebookGroup)
                .filter_by(framework_id=g["framework_id"])
                .first()
            )
            if group is None:
                group = CodebookGroup(
                    name=g["name"],
                    subtitle=g["subtitle"],
                    colour_set=g["colour_set"],
                    framework_id=g["framework_id"],
                )
                db.add(group)
                db.flush()
            defs = (
                db.query(TagDefinition)
                .filter_by(codebook_group_id=group.id)
                .all()
            )
            existing_names = {d.name for d in defs}
            for name in g["tags"]:
                if name not in existing_names:
                    td = TagDefinition(
                        name=name,
                        codebook_group_id=group.id,
                    )
                    db.add(td)
                    defs.append(td)
            db.flush()
            tag_defs_by_group[group.id] = defs

            # Activate the group on this project (idempotent)
            link = (
                db.query(ProjectCodebookGroup)
                .filter_by(project_id=project.id, codebook_group_id=group.id)
                .first()
            )
            if link is None:
                db.add(
                    ProjectCodebookGroup(
                        project_id=project.id,
                        codebook_group_id=group.id,
                        sort_order=10,
                    )
                )
        db.flush()

        # --- Apply tags per quote.  Deterministic given seed + row order.
        quotes = (
            db.query(Quote)
            .filter_by(project_id=project.id)
            .order_by(Quote.id)
            .all()
        )
        if not quotes:
            print("No quotes found — nothing to tag.")
            return

        # Prefetch existing (quote_id, tag_definition_id) pairs for the
        # tags we're about to add.  Keeps idempotency cheap at 1500+ quotes.
        candidate_tag_ids = [
            td.id for defs in tag_defs_by_group.values() for td in defs
        ]
        existing_pairs = {
            (row.quote_id, row.tag_definition_id)
            for row in db.query(QuoteTag).filter(
                QuoteTag.tag_definition_id.in_(candidate_tag_ids)
            )
        }

        created = 0
        for quote in quotes:
            for defs in tag_defs_by_group.values():
                # 1 or 2 tags per group per quote — realistic AutoCode
                # density.  Combined with the existing sentiment tag
                # that's 3-5 tags total per quote.
                k = random.randint(1, 2)
                for td in random.sample(defs, k):
                    if (quote.id, td.id) in existing_pairs:
                        continue
                    db.add(
                        QuoteTag(
                            quote_id=quote.id,
                            tag_definition_id=td.id,
                            source="autocode",
                        )
                    )
                    existing_pairs.add((quote.id, td.id))
                    created += 1

        db.commit()

    print(
        f"Augmented {len(quotes)} quotes with {created} additional "
        f"tag rows across {len(_GROUPS)} codebook groups"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="Path to the per-project bristlenose.db SQLite file.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed (default 0 for deterministic fixtures).",
    )
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"DB not found: {args.db}")

    augment(args.db, seed=args.seed)


if __name__ == "__main__":
    main()
