/**
 * The authoring apparatus, asserted against **both** lenses from one table.
 *
 * The extraction on 30 Aug 2026 moved add/rename/delete/drag/merge out of the
 * shipped island so `CodebookV2` could render it too. The risk that creates is
 * not that either lens breaks loudly — it is that they drift, one control at a
 * time, until "shared" means "looks the same". So every assertion below runs
 * twice, once per lens, and a behaviour that holds in only one is exactly the
 * bug this refactor exists to prevent.
 *
 * The details asserted here are the ones a reasonable test would not think to
 * ask for, which is why they are the ones most likely to be lost in a move:
 * the confirmation that is *skipped*, the delete button that is *absent*, and a
 * dialog's position in the DOM rather than its text.
 *
 * Note what is deliberately NOT asserted. `cursor: grab`, `.tag-row.dragging`
 * at reduced opacity and the `.merge-target` ring are visual; jsdom loads none
 * of `bristlenose/theme/`, so a `toHaveStyle` here would assert the test's own
 * inline defaults. `.merge-target` is checked as a *class*, which is the part
 * React owns; the opacity behind it is CSS's, and `.dragging` is applied only
 * by the frozen vanilla renderer (`theme/js/codebook.js`), never by React.
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CodebookPanel } from "./CodebookPanel";
import { CodebookV2 } from "./CodebookV2";
// The navigator moved to the left sidebar, so reaching a framework's page
// means rendering the pair AppLayout mounts.
import { CodebookV2Sidebar } from "../components/CodebookV2Sidebar";
import { resetSidebarStore } from "../contexts/SidebarStore";
import { resetActivityStore } from "../contexts/ActivityStore";
import type { CodebookResponse } from "../utils/types";

// One framework and one floor, because the two halves of the read-only rule
// (a framework's structure is its author's; the floor is yours) are what the
// lenses must agree about.
const CODEBOOK: CodebookResponse = {
  groups: [
    {
      id: 1,
      name: "Friction",
      subtitle: "Pain points",
      colour_set: "emo",
      order: 0,
      tags: [
        { id: 10, name: "confusion", count: 5, colour_index: 0 },
        { id: 11, name: "unused", count: 0, colour_index: 1 },
      ],
      total_quotes: 5,
      is_default: false,
      framework_id: null,
    },
    {
      id: 2,
      name: "Delight",
      subtitle: "",
      colour_set: "ux",
      order: 1,
      tags: [{ id: 20, name: "joy", count: 2, colour_index: 0 }],
      total_quotes: 2,
      is_default: false,
      framework_id: null,
    },
    {
      id: 99,
      name: "Uncategorised",
      subtitle: "Tags not yet assigned to any group",
      colour_set: "",
      order: 9999,
      tags: [{ id: 30, name: "misc", count: 1, colour_index: 0 }],
      total_quotes: 1,
      is_default: true,
      framework_id: null,
    },
    {
      id: 3,
      name: "Status visibility",
      subtitle: "Does the user know what is happening?",
      colour_set: "task",
      order: 2,
      tags: [{ id: 40, name: "feedback", count: 4, colour_index: 0 }],
      total_quotes: 4,
      is_default: false,
      framework_id: "nielsen",
    },
  ],
  ungrouped: [],
  all_tag_names: ["confusion", "unused", "joy", "misc", "feedback"],
};

const TEMPLATES = {
  templates: [
    {
      id: "nielsen",
      title: "10 Usability Heuristics",
      author: "Jakob Nielsen",
      description: "",
      author_bio: "",
      enabled: true,
      imported: true,
      groups: [],
      author_links: [],
    },
  ],
};

/** Answers every route both lenses reach on mount, by URL rather than order. */
function mockFetch(codebook: CodebookResponse = CODEBOOK) {
  const calls: { url: string; method: string; body?: string }[] = [];
  globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? "GET", body: init?.body as string });
    const ok = (data: unknown) => Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
    if (url.includes("/autocode/")) {
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
    }
    if (url.includes("/framework-states")) return ok({});
    if (url.includes("/codebook/templates")) return ok(TEMPLATES);
    if (url.includes("/codebook/groups") && init?.method === "POST") {
      return ok({
        id: 500,
        name: "New group",
        subtitle: "",
        colour_set: "trust",
        order: 3,
        tags: [],
        total_quotes: 0,
        is_default: false,
        framework_id: null,
      });
    }
    return ok(codebook);
  });
  return calls;
}

type Calls = ReturnType<typeof mockFetch>;

interface Lens {
  name: string;
  /** Render the lens and wait until the floor's groups are on screen. */
  floor: () => Promise<void>;
  /** Render the lens and wait until the framework's group is on screen. */
  framework: () => Promise<void>;
}

const LENSES: Lens[] = [
  {
    name: "v1 (CodebookPanel)",
    floor: async () => {
      render(<CodebookPanel projectId="1" />);
      await screen.findByText("Friction");
    },
    framework: async () => {
      // v1 renders every codebook on one page, so the framework is already
      // there — that long scrolling page is the thing v2's rail replaces.
      render(<CodebookPanel projectId="1" />);
      await screen.findByText("Status visibility");
    },
  },
  {
    name: "v2 (CodebookV2)",
    floor: async () => {
      render(<><CodebookV2Sidebar /><CodebookV2 projectId="1" /></>);
      await screen.findByText("Friction");
    },
    framework: async () => {
      render(<><CodebookV2Sidebar /><CodebookV2 projectId="1" /></>);
      await screen.findByTestId("bn-v2-nav-row-nielsen");
      await userEvent.click(screen.getByTestId("bn-v2-nav-row-nielsen"));
      await screen.findByText("Status visibility");
    },
  },
];

/** A drag payload jsdom does not supply and the handlers do use. */
function dataTransfer() {
  return {
    effectAllowed: "",
    dropEffect: "",
    setData: vi.fn(),
    getData: vi.fn(),
    setDragImage: vi.fn(),
  };
}

/**
 * The one live element with this text, ignoring any drag ghost.
 *
 * `TagRow`'s drag-start clones the badge into `document.body` as `.drag-ghost`
 * and removes it on the next animation frame — real behaviour, and the reason
 * a dragged badge keeps its own shape under the cursor instead of dragging the
 * whole row. Testing-library's cleanup unmounts its container, not a node the
 * component appended beside it, so a ghost outlives the assertion that follows
 * a drag and `getByText` finds two.
 */
function live(name: string): HTMLElement {
  const hits = screen
    .getAllByText(name)
    .filter((el) => !el.closest(".drag-ghost"));
  if (hits.length !== 1) {
    throw new Error(`expected exactly one live "${name}", found ${hits.length}`);
  }
  return hits[0];
}

/** The card whose title is `name` — the drop target for a tag move. */
function groupCard(name: string): HTMLElement {
  const el = live(name).closest(".codebook-group");
  if (!el) throw new Error(`no .codebook-group for ${name}`);
  return el as HTMLElement;
}

/** The row for a tag — the drag source, and the merge target. */
function tagRow(name: string): HTMLElement {
  const el = live(name).closest(".tag-row");
  if (!el) throw new Error(`no .tag-row for ${name}`);
  return el as HTMLElement;
}

function sent(calls: Calls, fragment: string, method: string) {
  return calls.find((c) => c.url.includes(fragment) && c.method === method);
}

beforeEach(() => {
  resetSidebarStore();
  resetActivityStore();
  mockFetch();
});

afterEach(() => {
  vi.restoreAllMocks();
  // Deliberately NOT sweeping `.drag-ghost` here: the component removes its own
  // clone on the next animation frame, and taking it first makes that call
  // throw NotFoundError out of a rAF callback nothing is awaiting. `live()`
  // filters ghosts instead, which is the non-racing half of the same fix.
});

describe.each(LENSES)("codebook authoring — $name", (lens) => {
  it("deletes a zero-count tag with no confirmation at all", async () => {
    // The detail most likely to be lost in a move, because it is an absence:
    // a tag nobody used is not a loss worth a dialog.
    const calls = mockFetch();
    await lens.floor();
    await userEvent.click(screen.getByLabelText("Delete unused"));
    expect(screen.queryByText(/Delete "unused"/)).not.toBeInTheDocument();
    await waitFor(() => expect(sent(calls, "/codebook/tags/11", "DELETE")).toBeTruthy());
  });

  it("confirms before deleting a tag that is on quotes", async () => {
    await lens.floor();
    await userEvent.click(screen.getByLabelText("Delete confusion"));
    expect(screen.getByText(/Delete "confusion"/)).toBeInTheDocument();
    expect(screen.getByText(/This tag is on 5 quotes/)).toBeInTheDocument();
  });

  it("puts the delete confirmation inside the card, not over the lens", async () => {
    // `.codebook-group .confirm-dialog` is `position: absolute; inset: 0` — it
    // covers the group it is about. A modal would be a different design.
    await lens.floor();
    await userEvent.click(screen.getByLabelText("Delete confusion"));
    const card = groupCard("Friction");
    expect(within(card).getByText(/Delete "confusion"/)).toBeInTheDocument();
    expect(document.querySelector(".merge-overlay")).toBeNull();
  });

  it("gives the floor group no delete button", async () => {
    // Uncategorised is not a group you can remove — it is where tags land.
    await lens.floor();
    expect(screen.getByLabelText("Delete group Friction")).toBeInTheDocument();
    expect(screen.queryByLabelText("Delete group Uncategorised")).not.toBeInTheDocument();
  });

  it("enters inline rename from the badge text", async () => {
    // Not a dialog, not a pencil icon: the name is the affordance.
    await lens.floor();
    await userEvent.click(screen.getByText("confusion"));
    const editing = document.querySelector(".tag-edit-inline");
    expect(editing).not.toBeNull();
    expect(editing).toHaveAttribute("contenteditable", "true");
  });

  it("renames a tag through PATCH", async () => {
    const calls = mockFetch();
    await lens.floor();
    await userEvent.click(screen.getByText("confusion"));
    const editing = document.querySelector(".tag-edit-inline") as HTMLElement;
    editing.textContent = "bewilderment";
    editing.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await waitFor(() => {
      const patch = sent(calls, "/codebook/tags/10", "PATCH");
      expect(patch).toBeTruthy();
      expect(JSON.parse(patch!.body!).name).toBe("bewilderment");
    });
  });

  it("adds a tag to a group", async () => {
    const calls = mockFetch();
    await lens.floor();
    const card = groupCard("Delight");
    await userEvent.click(within(card).getByText("+ tag"));
    const input = within(card).getByRole("textbox");
    await userEvent.type(input, "elation{Enter}");
    await waitFor(() => {
      const post = sent(calls, "/codebook/tags", "POST");
      expect(post).toBeTruthy();
      expect(JSON.parse(post!.body!)).toMatchObject({ name: "elation", group_id: 2 });
    });
  });

  it("creates a group from the new-group card", async () => {
    const calls = mockFetch();
    await lens.floor();
    await userEvent.click(screen.getByText("New group"));
    await waitFor(() => expect(sent(calls, "/codebook/groups", "POST")).toBeTruthy());
  });

  it("moves a tag by dropping it on another group", async () => {
    const calls = mockFetch();
    await lens.floor();
    const dt = dataTransfer();
    fireEvent.dragStart(tagRow("joy"), { dataTransfer: dt });
    fireEvent.dragOver(groupCard("Friction"), { dataTransfer: dt });
    fireEvent.drop(groupCard("Friction"), { dataTransfer: dt });
    await waitFor(() => {
      const patch = sent(calls, "/codebook/tags/20", "PATCH");
      expect(patch).toBeTruthy();
      expect(JSON.parse(patch!.body!)).toMatchObject({ group_id: 1 });
    });
  });

  it("rings the row a tag is dragged over, and unrings it on leave", async () => {
    await lens.floor();
    const dt = dataTransfer();
    fireEvent.dragStart(tagRow("joy"), { dataTransfer: dt });
    fireEvent.dragEnter(tagRow("confusion"), { dataTransfer: dt });
    expect(tagRow("confusion").className).toContain("merge-target");
    fireEvent.dragLeave(tagRow("confusion"), { dataTransfer: dt });
    expect(tagRow("confusion").className).not.toContain("merge-target");
  });

  it("confirms a merge by naming both tags, and says it cannot be undone", async () => {
    const calls = mockFetch();
    await lens.floor();
    const dt = dataTransfer();
    fireEvent.dragStart(tagRow("joy"), { dataTransfer: dt });
    fireEvent.dragEnter(tagRow("confusion"), { dataTransfer: dt });
    fireEvent.drop(tagRow("confusion"), { dataTransfer: dt });
    expect(await screen.findByText(/Merge "joy" into "confusion"\?/)).toBeInTheDocument();
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    // The merge alone is centred over the lens: it names two tags that may sit
    // in different cards, so there is no one card to cover.
    expect(document.querySelector(".merge-overlay")).not.toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Merge" }));
    await waitFor(() => {
      const post = sent(calls, "/codebook/merge-tags", "POST");
      expect(post).toBeTruthy();
      expect(JSON.parse(post!.body!)).toMatchObject({ source_id: 20, target_id: 10 });
    });
  });

  it("creates the group and moves the tag when dropped on the new-group card", async () => {
    // One gesture, two calls — the placeholder does not know it is doing two
    // things, which is why the handler owns both.
    const calls = mockFetch();
    await lens.floor();
    const dt = dataTransfer();
    fireEvent.dragStart(tagRow("joy"), { dataTransfer: dt });
    const placeholder = screen.getByText("New group").closest(".new-group-placeholder")!;
    fireEvent.drop(placeholder, { dataTransfer: dt });
    await waitFor(() => expect(sent(calls, "/codebook/groups", "POST")).toBeTruthy());
    await waitFor(() => {
      const patch = sent(calls, "/codebook/tags/20", "PATCH");
      expect(patch).toBeTruthy();
      expect(JSON.parse(patch!.body!)).toMatchObject({ group_id: 500 });
    });
  });

  it("leaves a framework's groups read-only", async () => {
    // You do not edit an installed framework's structure: no close button, no
    // add-tag row, and the badges carry no delete.
    await lens.framework();
    const card = groupCard("Status visibility");
    expect(within(card).queryByLabelText(/^Delete group /)).not.toBeInTheDocument();
    expect(within(card).queryByText("+ tag")).not.toBeInTheDocument();
    expect(within(card).queryByLabelText("Delete feedback")).not.toBeInTheDocument();
  });
});
