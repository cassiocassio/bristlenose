---
name: add-todo
description: Add a new item to 100days.md and create a matching card on the GitHub Projects board
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash, Read, Edit
---

Add a new to-do item to the 100-day launch inventory and the GitHub Projects board.

## Usage

```
/add-todo <title>
```

The user may also provide kind, priority, and description inline or conversationally. If not provided, ask.

## Step 1: Gather details

You need four pieces of information:

1. **Title** — short name for the item (from `$0`, or ask)
2. **Kind** — which category (one of the 14 numbered categories, or Active Branches / Needs Design Doc / Investigations). If the user gives a number or keyword, match it:
   - 1/missing, 2/broken, 3/embarrassing, 4/value, 5/blocking, 6/risk, 7/halo, 8/qol/quality, 9/debt/tech, 10/docs/documentation, 11/ops/operations, 12/legal, 13/gtm/marketing, 14/a11y/accessibility
3. **Priority** — Must / Should / Could / Won't
4. **Description** — one-line description (goes after the em dash in the doc, and into the card body)

## Step 2: Add to 100days.md

Read `docs/private/100days.md`. Find the correct section:
- Match the Kind to `## N. Category name` heading
- Match the Priority to `### Must` / `### Should` / `### Could` / `### Won't` subheading
- Append the new item at the end of that priority block (before the next `###` or `##` or `---`)

Format:
```
- **Title** — description
```

Use an em dash (—), not a hyphen. Match the style of surrounding entries.

## Step 3: Create card on the board

Use the GitHub GraphQL API via `gh` to:

1. Create a draft issue on the project
2. Set Status = Todo
3. Set Kind to the matching category
4. Set Priority to the matching level

Project details:
- Project ID: `PVT_kwHOAEYXlM4BORbY`
- Status field ID: `PVTSSF_lAHOAEYXlM4BORbYzg9Becg`

To get Kind and Priority field IDs and option IDs, query the project:

```bash
gh api graphql -f query='
{
  node(id: "PVT_kwHOAEYXlM4BORbY") {
    ... on ProjectV2 {
      field(name: "Kind") {
        ... on ProjectV2SingleSelectField {
          id
          options { id name }
        }
      }
    }
  }
}'
```

(Same pattern for "Priority" and "Status" fields.)

Then create and configure the card:

```bash
# Create draft issue
gh api graphql -f query='mutation { addProjectV2DraftIssue(input: { projectId: "PVT_kwHOAEYXlM4BORbY" title: "TITLE" body: "DESCRIPTION" }) { projectItem { id } } }'

# Set Status = Todo
gh api graphql -f query='mutation { updateProjectV2ItemFieldValue(input: { projectId: "PVT_kwHOAEYXlM4BORbY" itemId: "ITEM_ID" fieldId: "STATUS_FIELD_ID" value: {singleSelectOptionId: "TODO_OPTION_ID"} }) { projectV2Item { id } } }'

# Set Kind (same pattern)
# Set Priority (same pattern)
```

## Step 4: Report

Tell the user:
- What was added to 100days.md (section and priority)
- Card created on the board with a link

## Step 5: Offer sync

After creating the card, offer to run `/sync-board done` to pick up any items the user has moved to Done on the board since the last sync. This keeps the doc and board in step naturally.

## Notes

- 100days.md is in `docs/private/` (gitignored)
- Don't commit 100days.md changes — the file is private
- If the item already exists in the doc (fuzzy title match), warn the user instead of duplicating
- Em dash is — (Unicode U+2014), not -- or -
