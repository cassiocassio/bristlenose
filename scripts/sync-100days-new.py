#!/usr/bin/env python3
"""DEPRECATED: use sync_100days.py instead (bidirectional sync).

Create GitHub Projects cards for items in 100days.md that don't exist on the board.

Parses the markdown to extract Kind (from ## headings) and Priority (from ### headings),
then diffs against existing board titles and creates missing cards.

Usage:
    python scripts/sync-100days-new.py          # dry-run (show what would be created)
    python scripts/sync-100days-new.py --apply   # create the cards
"""

import json
import re
import subprocess
import sys
import time

PROJECT_ID = "PVT_kwHOAEYXlM4BORbY"
STATUS_FIELD_ID = "PVTSSF_lAHOAEYXlM4BORbYzg9Becg"
FILE = "docs/private/100days.md"

# Map ## heading numbers to Kind option names
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

PRIORITY_HEADINGS = {"Must", "Should", "Could", "Won't"}


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


def parse_doc() -> list[dict]:
    """Parse 100days.md into structured items with kind, priority, title, description."""
    with open(FILE) as f:
        lines = f.readlines()

    items = []
    current_kind = None
    current_priority = None

    # ## N. Category name
    category_re = re.compile(r"^## (\d+)\.\s+")
    # ### Must / Should / Could / Won't
    priority_re = re.compile(r"^### (Must|Should|Could|Won't)")
    # - [S1] **Title** — description  (with optional sprint tag and ~~strikethrough~~)
    item_re = re.compile(
        r"^\s*-\s+"
        r"(?:\[S(\d+)\]\s+)?"   # optional sprint tag [S1]-[S6]
        r"\*\*(~~)?"           # ** with optional ~~
        r"(.+?)"               # title
        r"(~~)?\*\*"           # optional ~~ then **
        r"\s*[—–-]\s*"         # em dash, en dash, or hyphen separator
        r"(.*)"                # description
    )
    # Items without description
    item_no_desc_re = re.compile(
        r"^\s*-\s+"
        r"(?:\[S(\d+)\]\s+)?"   # optional sprint tag
        r"\*\*(~~)?"
        r"(.+?)"
        r"(~~)?\*\*\s*$"
    )

    # Supplementary sections
    supplementary_re = re.compile(r"^## (Active feature branches|Items needing design|Investigations|Dependency maintenance)")

    for line in lines:
        # Check for numbered category heading
        m = category_re.match(line)
        if m:
            num = m.group(1)
            current_kind = KIND_MAP.get(num)
            current_priority = None
            continue

        # Check for supplementary section heading
        m = supplementary_re.match(line)
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

        # Check for priority heading
        m = priority_re.match(line)
        if m:
            current_priority = m.group(1)
            continue

        # Check for non-category ## heading (resets context)
        if line.startswith("## ") and not category_re.match(line) and not supplementary_re.match(line):
            current_kind = None
            current_priority = None
            continue

        if current_kind is None:
            continue

        # Check for item with description
        m = item_re.match(line)
        if m:
            sprint = m.group(1)  # "1"-"6" or None
            title = m.group(3).replace("~~", "").strip()
            description = m.group(5).strip()
            items.append({
                "kind": current_kind,
                "priority": current_priority,
                "title": title,
                "description": description,
                "sprint": f"Sprint {sprint}" if sprint else None,
            })
            continue

        # Check for item without description
        m = item_no_desc_re.match(line)
        if m:
            sprint = m.group(1)
            title = m.group(3).replace("~~", "").strip()
            items.append({
                "kind": current_kind,
                "priority": current_priority,
                "title": title,
                "description": "",
                "sprint": f"Sprint {sprint}" if sprint else None,
            })

    return items


def get_board_titles() -> set[str]:
    """Fetch all item titles from the project board."""
    titles = set()
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
            title = item.get("content", {}).get("title", "")
            if title:
                titles.add(normalize(title))

        if items["pageInfo"]["hasNextPage"]:
            cursor = items["pageInfo"]["endCursor"]
        else:
            break

    return titles


def get_field_options(field_name: str) -> tuple[str, dict[str, str]]:
    """Get field ID and option name->ID map."""
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


def main():
    apply = "--apply" in sys.argv

    print("Parsing 100days.md...")
    doc_items = parse_doc()
    print(f"  {len(doc_items)} items in doc\n")

    print("Fetching board titles...")
    board_titles = get_board_titles()
    print(f"  {len(board_titles)} items on board\n")

    # Find items in doc but not on board
    new_items = []
    for item in doc_items:
        if normalize(item["title"]) not in board_titles:
            new_items.append(item)

    if not new_items:
        print("No new items — doc and board are in sync.")
        return

    print(f"{len(new_items)} new item(s) to create:\n")
    for item in new_items:
        pri = item["priority"] or "-"
        sprint = item.get("sprint") or "-"
        print(f"  [{item['kind']}] [{pri}] [{sprint}] {item['title']}")
        if item["description"]:
            print(f"    {item['description'][:80]}...")

    if not apply:
        print(f"\nRun with --apply to create {len(new_items)} card(s).")
        return

    # Fetch field options
    print("\nFetching field options...")
    kind_field_id, kind_map = get_field_options("Kind")
    priority_field_id, priority_map = get_field_options("Priority")
    sprint_field_id, sprint_map = get_field_options("Sprint")
    _, status_map = get_field_options("Status")
    todo_id = status_map["Todo"]

    print(f"\nCreating {len(new_items)} cards...")
    for i, item in enumerate(new_items):
        safe_title = item["title"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        safe_body = item["description"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

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
            print(f"  FAIL [{i+1}/{len(new_items)}]: {item['title']}")
            continue

        item_id = result["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]

        # Set Status = Todo
        set_field(item_id, STATUS_FIELD_ID, todo_id)

        # Set Kind
        kind_option_id = kind_map.get(item["kind"])
        if kind_option_id:
            set_field(item_id, kind_field_id, kind_option_id)

        # Set Priority
        if item["priority"] and item["priority"] in priority_map:
            set_field(item_id, priority_field_id, priority_map[item["priority"]])

        # Set Sprint
        sprint = item.get("sprint")
        if sprint and sprint in sprint_map:
            set_field(item_id, sprint_field_id, sprint_map[sprint])

        pri = item["priority"] or "-"
        sprint_label = sprint or "-"
        print(f"  OK [{i+1}/{len(new_items)}]: {item['title']} -> {item['kind']} / {pri} / {sprint_label}")
        time.sleep(0.3)

    print(f"\nDone! {len(new_items)} cards created.")
    print("View at: https://github.com/users/cassiocassio/projects/1")


if __name__ == "__main__":
    main()
