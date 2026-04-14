#!/usr/bin/env python3
"""Bidirectional sync between 100days.md and the GitHub Projects board.

Default mode (no args): sync both directions —
  1. Board → doc: strike through Done items, un-strike un-Done items
  2. Doc → board: create cards for new items
  3. Doc → board: backfill Sprint field on existing cards from [SN] tags

mark-done mode: move specific items to Done on the board and strike through in the doc.

Usage:
    python scripts/sync_100days.py                          # dry-run both directions
    python scripts/sync_100days.py --apply                  # apply both directions
    python scripts/sync_100days.py mark-done "Item title"   # dry-run mark-done
    python scripts/sync_100days.py mark-done --apply "X"    # apply mark-done
"""

import json
import re
import subprocess
import sys
import time

PROJECT_ID = "PVT_kwHOAEYXlM4BORbY"
STATUS_FIELD_ID = "PVTSSF_lAHOAEYXlM4BORbYzg9Becg"
FILE = "docs/private/100days.md"

# Map ## heading numbers to Kind option names on the board
KIND_MAP = {
    "1": "1. Missing",
    "2": "2. Broken",
    "3": "3. Embarrassing",
    "4": "4. Value",
    "5": "5. Blocking",
    "6": "6. Risk",
    "7": "7. Halo",
    "8": "8. Quality of Life",
    "9": "9. Technical Debt",
    "10": "10. Documentation",
    "11": "11. Operations",
    "12": "12. Legal/Compliance",
    "13": "13. Go-to-Market",
    "14": "14. Accessibility",
}


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Normalize text for fuzzy matching: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("~~", "")
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text)


def escape_graphql(text: str) -> str:
    """Escape a string for embedding in a GraphQL query."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

# Regex components shared by parse_doc and line-rewriting
_SPRINT_RE = r"(?:\[S(\d+)\]\s+)?"  # optional sprint tag — group captures the number
_ITEM_WITH_DESC_RE = re.compile(
    r"^\s*-\s+"
    + _SPRINT_RE
    + r"\*\*(~~)?"       # ** with optional ~~
    r"(.+?)"             # title
    r"(~~)?\*\*"         # optional ~~ then **
    r"\s*[—–-]\s*"       # em dash, en dash, or hyphen separator
    r"(.*)"              # description
)
_ITEM_NO_DESC_RE = re.compile(
    r"^\s*-\s+"
    + _SPRINT_RE
    + r"\*\*(~~)?"
    r"(.+?)"
    r"(~~)?\*\*\s*$"
)
_LINE_RE = re.compile(
    r"^(\s*- )"            # prefix: "- "
    r"(\[S\d+\]\s+)?"     # optional sprint tag (preserved as-is)
    r"(\*\*)"              # open bold
    r"(~~)?"               # optional strikethrough open
    r"(.+?)"               # title text
    r"(~~)?"               # optional strikethrough close
    r"(\*\*)"              # close bold
    r"(.*)"                # rest of line
    r"$"
)
_CATEGORY_RE = re.compile(r"^## (\d+)\.\s+")
_PRIORITY_RE = re.compile(r"^### (Must|Should|Could|Won't)")
_SUPPLEMENTARY_RE = re.compile(
    r"^## (Active feature branches|Items needing design|Investigations|Dependency maintenance)"
)


def parse_doc(filepath: str = FILE) -> list[dict]:
    """Parse 100days.md into structured items.

    Returns list of dicts with keys: kind, priority, title, description, sprint.
    Sprint is e.g. "Sprint 3" or None.
    """
    with open(filepath) as f:
        lines = f.readlines()

    items: list[dict] = []
    current_kind = None
    current_priority = None

    for line in lines:
        # Category heading: ## N. ...
        m = _CATEGORY_RE.match(line)
        if m:
            current_kind = KIND_MAP.get(m.group(1))
            current_priority = None
            continue

        # Supplementary heading
        m = _SUPPLEMENTARY_RE.match(line)
        if m:
            section = m.group(1)
            if "Active" in section:
                current_kind = "Active Branches"
            elif "design" in section.lower():
                current_kind = "Needs Design Doc"
            elif "Investigations" in section or "Dependency" in section:
                current_kind = "Investigations"
            current_priority = None
            continue

        # Priority heading: ### Must / Should / Could / Won't
        m = _PRIORITY_RE.match(line)
        if m:
            current_priority = m.group(1)
            continue

        # Non-category ## heading resets context
        if line.startswith("## ") and not _CATEGORY_RE.match(line) and not _SUPPLEMENTARY_RE.match(line):
            current_kind = None
            current_priority = None
            continue

        if current_kind is None:
            continue

        # Item with description
        m = _ITEM_WITH_DESC_RE.match(line)
        if m:
            sprint_num = m.group(1)
            title = m.group(3).replace("~~", "").strip()
            description = m.group(5).strip()
            items.append({
                "kind": current_kind,
                "priority": current_priority,
                "title": title,
                "description": description,
                "sprint": f"Sprint {sprint_num}" if sprint_num else None,
            })
            continue

        # Item without description
        m = _ITEM_NO_DESC_RE.match(line)
        if m:
            sprint_num = m.group(1)
            title = m.group(3).replace("~~", "").strip()
            items.append({
                "kind": current_kind,
                "priority": current_priority,
                "title": title,
                "description": "",
                "sprint": f"Sprint {sprint_num}" if sprint_num else None,
            })

    return items


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

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


def get_all_board_items() -> list[dict]:
    """Fetch all items from the board with id, title, normalized title, status, sprint."""
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
                  sprintValue: fieldValueByName(name: "Sprint") {{
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
            sprint = item.get("sprintValue")
            if title:
                items.append({
                    "id": item["id"],
                    "title": title,
                    "normalized": normalize(title),
                    "status": status.get("name") if status else None,
                    "sprint": sprint.get("name") if sprint else None,
                })

        if board_items["pageInfo"]["hasNextPage"]:
            cursor = board_items["pageInfo"]["endCursor"]
        else:
            break

    return items


def get_field_options(field_name: str) -> tuple[str, dict[str, str]]:
    """Get field ID and option name→ID map for a single-select field."""
    query = f'''
    {{
      node(id: "{PROJECT_ID}") {{
        ... on ProjectV2 {{
          field(name: "{field_name}") {{
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
    return field["id"], {o["name"]: o["id"] for o in field["options"]}


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


# ---------------------------------------------------------------------------
# Sync operations
# ---------------------------------------------------------------------------

def sync_done_to_doc(board_items: list[dict], filepath: str = FILE, apply: bool = False) -> int:
    """Board → doc: strike through Done items, un-strike un-Done items."""
    done_normalized = {item["normalized"] for item in board_items if item["status"] == "Done"}

    with open(filepath) as f:
        lines = f.readlines()

    changes = 0
    new_lines = []

    for line in lines:
        m = _LINE_RE.match(line)
        if not m:
            new_lines.append(line)
            continue

        prefix = m.group(1)
        sprint_tag = m.group(2) or ""
        had_strike = bool(m.group(4))
        title = m.group(5).replace("~~", "").strip()
        rest = m.group(8)

        is_done = normalize(title) in done_normalized

        if is_done and not had_strike:
            new_line = f"{prefix}{sprint_tag}**~~{title}~~**{rest}\n"
            changes += 1
            print(f"  + STRIKE: {title}")
            new_lines.append(new_line)
        elif not is_done and had_strike:
            new_line = f"{prefix}{sprint_tag}**{title}**{rest}\n"
            changes += 1
            print(f"  - UNSTRIKE: {title}")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if apply and changes > 0:
        with open(filepath, "w") as f:
            f.writelines(new_lines)

    return changes


def sync_new_to_board(
    doc_items: list[dict],
    board_items: list[dict],
    apply: bool = False,
) -> list[dict]:
    """Doc → board: create cards for items not yet on the board. Returns list of new items."""
    board_titles = {item["normalized"] for item in board_items}
    new_items = [item for item in doc_items if normalize(item["title"]) not in board_titles]

    if not new_items:
        return []

    print(f"\n  {len(new_items)} new card(s) to create:")
    for item in new_items:
        pri = item["priority"] or "-"
        sprint = item.get("sprint") or "-"
        print(f"    [{item['kind']}] [{pri}] [{sprint}] {item['title']}")

    if not apply:
        return new_items

    # Fetch field options
    kind_field_id, kind_map = get_field_options("Kind")
    priority_field_id, priority_map = get_field_options("Priority")
    sprint_field_id, sprint_map = get_field_options("Sprint")
    _, status_map = get_field_options("Status")
    todo_id = status_map["Todo"]

    print(f"\n  Creating {len(new_items)} cards...")
    for i, item in enumerate(new_items):
        safe_title = escape_graphql(item["title"])
        safe_body = escape_graphql(item["description"])

        query = f'''
        mutation {{
          addProjectV2DraftIssue(input: {{
            projectId: "{PROJECT_ID}"
            title: "{safe_title}"
            body: "{safe_body}"
          }}) {{
            projectItem {{ id }}
          }}
        }}
        '''
        result = gh_graphql(query)
        if result.get("data") is None:
            print(f"    FAIL [{i+1}/{len(new_items)}]: {item['title']}")
            continue

        item_id = result["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]

        set_field(item_id, STATUS_FIELD_ID, todo_id)

        kind_option_id = kind_map.get(item["kind"])
        if kind_option_id:
            set_field(item_id, kind_field_id, kind_option_id)

        if item["priority"] and item["priority"] in priority_map:
            set_field(item_id, priority_field_id, priority_map[item["priority"]])

        sprint = item.get("sprint")
        if sprint and sprint in sprint_map:
            set_field(item_id, sprint_field_id, sprint_map[sprint])

        sprint_label = sprint or "-"
        print(f"    OK [{i+1}/{len(new_items)}]: {item['title']} -> {sprint_label}")
        time.sleep(0.3)

    return new_items


def sync_sprints_to_board(
    doc_items: list[dict],
    board_items: list[dict],
    apply: bool = False,
) -> int:
    """Doc → board: backfill Sprint field on cards whose doc item has a [SN] tag."""
    # Build lookup: normalized title → sprint from doc
    doc_sprints = {}
    for item in doc_items:
        if item.get("sprint"):
            doc_sprints[normalize(item["title"])] = item["sprint"]

    # Find board items that have no sprint or a different sprint
    to_update = []
    for item in board_items:
        doc_sprint = doc_sprints.get(item["normalized"])
        if doc_sprint and item.get("sprint") != doc_sprint:
            to_update.append((item, doc_sprint))

    if not to_update:
        return 0

    print(f"\n  {len(to_update)} card(s) need Sprint update:")
    for item, sprint in to_update:
        old = item.get("sprint") or "(none)"
        print(f"    {item['title']}: {old} → {sprint}")

    if not apply:
        return len(to_update)

    sprint_field_id, sprint_map = get_field_options("Sprint")
    updated = 0
    for item, sprint in to_update:
        option_id = sprint_map.get(sprint)
        if option_id:
            set_field(item["id"], sprint_field_id, option_id)
            updated += 1
            time.sleep(0.2)

    print(f"  Updated {updated} card(s)")
    return updated


# ---------------------------------------------------------------------------
# mark-done (explicit)
# ---------------------------------------------------------------------------

def mark_done(terms: list[str], apply: bool = False) -> None:
    """Move specific items to Done on the board and strike through in the doc."""
    print(f"Searching for {len(terms)} item(s)...\n")

    print("Fetching board items...")
    board_items = get_all_board_items()
    print(f"  {len(board_items)} items on board\n")

    # Find matches
    matches = []
    for term in terms:
        norm_term = normalize(term)
        found = [item for item in board_items if norm_term in item["normalized"]]
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

    if not matches:
        print("\nNo matches found. Nothing to do.")
        return

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

    # Strike through in doc
    all_titles = {m["title"] for m in matches}
    normalized_titles = {normalize(t) for t in all_titles}

    with open(FILE) as f:
        lines = f.readlines()

    doc_changes = 0
    new_lines = []

    for line in lines:
        m = _LINE_RE.match(line)
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
            doc_changes += 1
            print(f"  STRIKE: {title}")
            new_lines.append(new_line)
        else:
            new_lines.append(line)

    if not apply:
        if to_update or doc_changes:
            print(f"\nRun with --apply to move {len(to_update)} card(s) to Done "
                  f"and apply {doc_changes} strikethrough(s).")
        return

    # Write doc
    if doc_changes > 0:
        with open(FILE, "w") as f:
            f.writelines(new_lines)
        print(f"\n  Applied {doc_changes} strikethrough(s) to {FILE}")

    # Move cards to Done
    if to_update:
        _, status_map = get_field_options("Status")
        done_id = status_map.get("Done")
        if not done_id:
            print("ERROR: no 'Done' option found on Status field", file=sys.stderr)
            sys.exit(1)

        print(f"\n  Moving {len(to_update)} card(s) to Done...")
        for m in to_update:
            set_field(m["id"], STATUS_FIELD_ID, done_id)
            print(f"    OK: {m['title']}")
            time.sleep(0.3)

    total = len(to_update) + len(already_done)
    print(f"\nDone! {total} item(s) marked as Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    # mark-done mode
    if args and args[0] == "mark-done":
        apply = "--apply" in args
        terms = [a for a in args[1:] if a != "--apply"]
        mark_done(terms, apply)
        return

    # Default: bidirectional sync
    apply = "--apply" in args

    print("=" * 60)
    print("Bidirectional sync: 100days.md ↔ GitHub Projects board")
    print("=" * 60)

    print("\nFetching board items...")
    board_items = get_all_board_items()
    print(f"  {len(board_items)} items on board")

    print("\nParsing 100days.md...")
    doc_items = parse_doc()
    print(f"  {len(doc_items)} items in doc")

    # 1. Board → doc: strikethrough
    print("\n--- Board → Doc: strikethrough sync ---")
    done_changes = sync_done_to_doc(board_items, FILE, apply)
    if done_changes == 0:
        print("  No strikethrough changes needed")

    # 2. Doc → board: new cards
    print("\n--- Doc → Board: new cards ---")
    new_items = sync_new_to_board(doc_items, board_items, apply)
    if not new_items:
        print("  No new cards needed — doc and board are in sync")

    # 3. Doc → board: sprint backfill
    print("\n--- Doc → Board: sprint backfill ---")
    sprint_updates = sync_sprints_to_board(doc_items, board_items, apply)
    if sprint_updates == 0:
        print("  No sprint updates needed")

    # Summary
    print("\n" + "=" * 60)
    if not apply:
        total = done_changes + len(new_items) + sprint_updates
        if total > 0:
            print(f"Dry run complete. {total} change(s) pending. Run with --apply.")
        else:
            print("Everything is in sync!")
    else:
        print("Sync complete!")
    print("Board: https://github.com/users/cassiocassio/projects/1")


if __name__ == "__main__":
    main()
