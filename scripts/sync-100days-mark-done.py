#!/usr/bin/env python3
"""Mark items as Done on the GitHub Projects board and strike through in 100days.md.

Takes item titles (or substrings) as arguments, finds matching cards on the board,
moves them to Done, and applies strikethrough in the markdown.

Usage:
    python scripts/sync-100days-mark-done.py "Signal elaboration" "Responsive quote grid"
    python scripts/sync-100days-mark-done.py --apply "Signal elaboration" "Responsive quote grid"
"""

import json
import re
import subprocess
import sys
import time

PROJECT_ID = "PVT_kwHOAEYXlM4BORbY"
STATUS_FIELD_ID = "PVTSSF_lAHOAEYXlM4BORbYzg9Becg"
FILE = "docs/private/100days.md"


def gh_graphql(query: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if "errors" in data:
                print(f"  GraphQL error: {data['errors']}", file=sys.stderr)
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
            return data
        else:
            print(f"  gh error: {result.stderr}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(1)
    return {"errors": ["max retries exceeded"]}


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("~~", "")
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text)


def get_all_items() -> list[dict]:
    """Fetch all items from the board with their IDs, titles, and status."""
    items = []
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
                  id
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
        board_items = result["data"]["node"]["items"]

        for item in board_items["nodes"]:
            title = item.get("content", {}).get("title", "")
            status = item.get("fieldValueByName")
            if title:
                items.append({
                    "id": item["id"],
                    "title": title,
                    "normalized": normalize(title),
                    "status": status.get("name") if status else None,
                })

        if board_items["pageInfo"]["hasNextPage"]:
            cursor = board_items["pageInfo"]["endCursor"]
        else:
            break

    return items


def find_matches(board_items: list[dict], search_terms: list[str]) -> list[dict]:
    """Find board items matching search terms (substring match on normalized text)."""
    matches = []
    for term in search_terms:
        norm_term = normalize(term)
        found = [
            item for item in board_items
            if norm_term in item["normalized"]
        ]
        if not found:
            print(f"  WARNING: no match for '{term}'")
        elif len(found) > 1:
            print(f"  WARNING: '{term}' matched {len(found)} items:")
            for f in found:
                print(f"    - {f['title']} [{f['status'] or 'no status'}]")
            print(f"    Using first match: {found[0]['title']}")
            matches.append(found[0])
        else:
            matches.append(found[0])
    return matches


def set_field(item_id: str, field_id: str, option_id: str):
    query = f'''
    mutation {{
      updateProjectV2ItemFieldValue(input: {{
        projectId: "{PROJECT_ID}"
        itemId: "{item_id}"
        fieldId: "{field_id}"
        value: {{singleSelectOptionId: "{option_id}"}}
      }}) {{
        projectV2Item {{ id }}
      }}
    }}
    '''
    return gh_graphql(query)


def strike_in_doc(titles: set[str], apply: bool) -> int:
    """Add strikethrough to matching items in 100days.md."""
    normalized_titles = {normalize(t) for t in titles}

    with open(FILE) as f:
        lines = f.readlines()

    changes = 0
    new_lines = []

    item_re = re.compile(
        r"^(\s*- )"            # prefix: "- "
        r"(\[S\d+\]\s+)?"     # optional sprint tag
        r"(\*\*)"              # open bold
        r"(~~)?"               # optional existing strikethrough open
        r"(.+?)"               # title text
        r"(~~)?"               # optional existing strikethrough close
        r"(\*\*)"              # close bold
        r"(.*)"                # rest of line
        r"$"
    )

    for line in lines:
        m = item_re.match(line)
        if not m:
            new_lines.append(line)
            continue

        sprint_tag = m.group(2) or ""
        had_strike = bool(m.group(4))
        title = m.group(5).replace("~~", "").strip()

        if normalize(title) in normalized_titles and not had_strike:
            prefix = m.group(1)
            rest = m.group(8)
            new_line = f"{prefix}{sprint_tag}**~~{title}~~**{rest}\n"
            changes += 1
            print(f"  STRIKE: {title}")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if apply and changes > 0:
        with open(FILE, "w") as f:
            f.writelines(new_lines)
        print(f"\n  Applied {changes} strikethrough(s) to {FILE}")
    elif changes > 0:
        print(f"\n  {changes} strikethrough(s) to apply. Run with --apply to write.")

    return changes


def main():
    apply = "--apply" in sys.argv
    terms = [a for a in sys.argv[1:] if a != "--apply"]

    if not terms:
        print("Usage: sync-100days-mark-done.py [--apply] \"Item title\" ...")
        print("\nMarks matching items as Done on the board and strikes through in 100days.md.")
        sys.exit(1)

    print(f"Searching for {len(terms)} item(s)...\n")

    print("Fetching board items...")
    board_items = get_all_items()
    print(f"  {len(board_items)} items on board\n")

    matches = find_matches(board_items, terms)
    if not matches:
        print("\nNo matches found. Nothing to do.")
        return

    # Separate into already-done and needs-update
    to_update = [m for m in matches if m["status"] != "Done"]
    already_done = [m for m in matches if m["status"] == "Done"]

    if already_done:
        print(f"\nAlready Done ({len(already_done)}):")
        for m in already_done:
            print(f"  - {m['title']}")

    if to_update:
        print(f"\nWill move to Done ({len(to_update)}):")
        for m in to_update:
            print(f"  - {m['title']} [{m['status'] or 'no status'}]")

    # Strike through all matches in the doc (including already-done that might not be struck)
    all_titles = {m["title"] for m in matches}
    print(f"\nStrikethrough in {FILE}:")
    strike_in_doc(all_titles, apply)

    if not apply:
        if to_update:
            print(f"\nRun with --apply to move {len(to_update)} card(s) to Done and update {FILE}.")
        return

    if to_update:
        # Get Done option ID
        print("\nFetching Status field options...")
        query = f'''
        {{
          node(id: "{PROJECT_ID}") {{
            ... on ProjectV2 {{
              field(name: "Status") {{
                ... on ProjectV2SingleSelectField {{
                  id
                  options {{ id name }}
                }}
              }}
            }}
          }}
        }}
        '''
        result = gh_graphql(query)
        field = result["data"]["node"]["field"]
        status_options = {o["name"]: o["id"] for o in field["options"]}
        done_id = status_options.get("Done")

        if not done_id:
            print("ERROR: no 'Done' option found on Status field", file=sys.stderr)
            sys.exit(1)

        print(f"\nMoving {len(to_update)} card(s) to Done...")
        for m in to_update:
            set_field(m["id"], STATUS_FIELD_ID, done_id)
            print(f"  OK: {m['title']}")
            time.sleep(0.3)

    total = len(to_update) + len(already_done)
    print(f"\nDone! {total} item(s) marked as Done.")
    print("View at: https://github.com/users/cassiocassio/projects/1")


if __name__ == "__main__":
    main()
