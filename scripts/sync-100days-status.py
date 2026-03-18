#!/usr/bin/env python3
"""Sync 100days.md strikethrough styling from GitHub Projects board status.

Items marked Done on the board get ~~strikethrough~~ in the markdown.
Items not Done have strikethrough removed (if previously applied).

Usage:
    python scripts/sync-100days-status.py          # dry-run (show changes)
    python scripts/sync-100days-status.py --apply   # write changes to file
"""

import json
import re
import subprocess
import sys

PROJECT_ID = "PVT_kwHOAEYXlM4BORbY"
FILE = "docs/private/100days.md"


def gh_graphql(query: str) -> dict:
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"gh error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def get_done_titles() -> set[str]:
    """Fetch all item titles with Status = Done from the project board."""
    done = set()
    cursor = None

    while True:
        after = f', after: "{cursor}"' if cursor else ""
        query = f'''
        {{
          node(id: "{PROJECT_ID}") {{
            ... on ProjectV2 {{
              items(first: 100{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                  fieldValueByName(name: "Status") {{
                    ... on ProjectV2ItemFieldSingleSelectValue {{
                      name
                    }}
                  }}
                  content {{
                    ... on DraftIssue {{ title }}
                    ... on Issue {{ title }}
                    ... on PullRequest {{ title }}
                  }}
                }}
              }}
            }}
          }}
        }}
        '''
        result = gh_graphql(query)
        items = result["data"]["node"]["items"]

        for item in items["nodes"]:
            status = item.get("fieldValueByName")
            title = item.get("content", {}).get("title", "")
            if status and status.get("name") == "Done" and title:
                done.add(title)

        if items["pageInfo"]["hasNextPage"]:
            cursor = items["pageInfo"]["endCursor"]
        else:
            break

    return done


def normalize(text: str) -> str:
    """Normalize text for fuzzy matching: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")  # smart quotes
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text)


def sync_file(done_titles: set[str], apply: bool) -> int:
    """Apply/remove strikethrough on matching list items. Returns count of changes."""
    normalized_done = {normalize(t) for t in done_titles}

    with open(FILE) as f:
        lines = f.readlines()

    changes = 0
    new_lines = []

    # Pattern: "- **Title** — description" or "- **~~Title~~** — description"
    item_re = re.compile(
        r"^(\s*- \*\*)"        # prefix: "- **"
        r"(~~)?"               # optional existing strikethrough open
        r"(.+?)"               # title text
        r"(~~)?"               # optional existing strikethrough close
        r"(\*\*)"              # close bold
        r"(.*)"                # rest of line (em dash + description)
        r"$"
    )

    for line in lines:
        m = item_re.match(line)
        if not m:
            new_lines.append(line)
            continue

        prefix = m.group(1)         # "- **"
        had_strike = bool(m.group(2))
        title = m.group(3)
        bold_close = m.group(5)     # "**"
        rest = m.group(6)           # " — description..."

        # Clean title for matching (remove any residual ~~)
        clean_title = title.replace("~~", "").strip()
        is_done = normalize(clean_title) in normalized_done

        if is_done and not had_strike:
            # Add strikethrough
            new_line = f"{prefix}~~{clean_title}~~{bold_close}{rest}\n"
            changes += 1
            print(f"  + STRIKE: {clean_title}")
            new_lines.append(new_line)
        elif not is_done and had_strike:
            # Remove strikethrough (item un-done)
            new_line = f"{prefix}{clean_title}{bold_close}{rest}\n"
            changes += 1
            print(f"  - UNSTRIKE: {clean_title}")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if apply and changes > 0:
        with open(FILE, "w") as f:
            f.writelines(new_lines)
        print(f"\nApplied {changes} change(s) to {FILE}")
    elif changes > 0:
        print(f"\n{changes} change(s) found. Run with --apply to write.")
    else:
        print("\nNo changes needed — file is in sync.")

    return changes


def main():
    apply = "--apply" in sys.argv

    print("Fetching board status...")
    done_titles = get_done_titles()
    print(f"  {len(done_titles)} items marked Done\n")

    if done_titles:
        print("Done items:")
        for t in sorted(done_titles):
            print(f"  - {t}")
        print()

    print("Syncing 100days.md...")
    sync_file(done_titles, apply)


if __name__ == "__main__":
    main()
