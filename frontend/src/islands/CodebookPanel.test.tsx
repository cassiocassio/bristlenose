import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CodebookPanel } from "./CodebookPanel";
import type { CodebookResponse } from "../utils/types";

const MOCK_CODEBOOK: CodebookResponse = {
  groups: [
    {
      id: 1,
      name: "Friction",
      subtitle: "Pain points",
      colour_set: "emo",
      order: 0,
      tags: [
        { id: 10, name: "confusion", count: 5, colour_index: 0 },
        { id: 11, name: "frustration", count: 3, colour_index: 1 },
      ],
      total_quotes: 7,
      is_default: false,
      framework_id: null,
    },
    {
      id: 2,
      name: "Delight",
      subtitle: "",
      colour_set: "ux",
      order: 1,
      tags: [
        { id: 20, name: "joy", count: 2, colour_index: 0 },
      ],
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
      tags: [
        { id: 30, name: "misc", count: 1, colour_index: 0 },
      ],
      total_quotes: 1,
      is_default: true,
      framework_id: null,
    },
  ],
  ungrouped: [],
  all_tag_names: ["confusion", "frustration", "joy", "misc"],
};

function mockFetchOk(data: unknown): void {
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    // AutoCode status calls return 404 (no job) by default.
    if (typeof url === "string" && url.includes("/autocode/")) {
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(data),
    });
  });
}

function mockFetchSequence(...responses: unknown[]): void {
  const queue = [...responses];
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    // AutoCode status calls return 404 (no job) by default.
    if (typeof url === "string" && url.includes("/autocode/")) {
      return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
    }
    const data = queue.shift();
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(data),
    });
  });
}

beforeEach(() => {
  // Default: return mock codebook
  mockFetchOk(MOCK_CODEBOOK);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("CodebookPanel", () => {
  it("shows loading state initially", () => {
    // Never resolve fetch
    globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
    render(<CodebookPanel projectId="1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders groups and tags from API data", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Friction")).toBeInTheDocument();
    });
    expect(screen.getByText("Delight")).toBeInTheDocument();
    expect(screen.getByText("confusion")).toBeInTheDocument();
    expect(screen.getByText("frustration")).toBeInTheDocument();
    expect(screen.getByText("joy")).toBeInTheDocument();
  });

  it("renders Uncategorised default group", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Uncategorised")).toBeInTheDocument();
    });
    expect(screen.getByText("Tags not yet assigned to any group")).toBeInTheDocument();
    expect(screen.getByText("misc")).toBeInTheDocument();
  });

  it("Uncategorised group has no delete button", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Uncategorised")).toBeInTheDocument();
    });
    expect(screen.queryByLabelText("Delete group Uncategorised")).not.toBeInTheDocument();
  });

  it("renders tag counts", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("confusion")).toBeInTheDocument();
    });
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("renders group total", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("7")).toBeInTheDocument();
    });
  });

  it("renders new group placeholder", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("New group")).toBeInTheDocument();
    });
  });

  it("renders + tag button per group", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      // 2 user groups + 1 Uncategorised = 3
      expect(screen.getAllByText("+ tag")).toHaveLength(3);
    });
  });

  it("shows error state on fetch failure", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network error"));
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText(/Error loading codebook/)).toBeInTheDocument();
    });
  });

  it("renders delete button for tags", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Delete confusion")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Delete frustration")).toBeInTheDocument();
    expect(screen.getByLabelText("Delete joy")).toBeInTheDocument();
  });

  it("renders delete button for groups (non-default only)", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Delete group Friction")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Delete group Delight")).toBeInTheDocument();
    // Uncategorised (default) has no delete button
    expect(screen.queryByLabelText("Delete group Uncategorised")).not.toBeInTheDocument();
  });

  it("clicking delete tag shows confirmation dialog", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Delete confusion")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByLabelText("Delete confusion"));
    expect(screen.getByText(/Delete "confusion"/)).toBeInTheDocument();
    expect(screen.getByText(/This tag is on 5 quotes/)).toBeInTheDocument();
  });

  it("confirming tag delete calls API", async () => {
    mockFetchSequence(MOCK_CODEBOOK, { status: "ok" }, MOCK_CODEBOOK);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Delete confusion")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByLabelText("Delete confusion"));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });
    // Second call should be DELETE to the tag endpoint
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[1][0]).toContain("/codebook/tags/10");
    expect(calls[1][1]?.method).toBe("DELETE");
  });

  it("deleting zero-count tag skips confirmation", async () => {
    const zeroCountData: CodebookResponse = {
      ...MOCK_CODEBOOK,
      groups: [
        {
          ...MOCK_CODEBOOK.groups[0],
          tags: [
            { id: 10, name: "confusion", count: 5, colour_index: 0 },
            { id: 12, name: "empty-tag", count: 0, colour_index: 2 },
          ],
        },
        MOCK_CODEBOOK.groups[1],
        MOCK_CODEBOOK.groups[2],
      ],
    };
    mockFetchSequence(zeroCountData, { status: "ok" }, zeroCountData);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Delete empty-tag")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByLabelText("Delete empty-tag"));
    // No confirmation dialog — should immediately call DELETE API
    expect(screen.queryByText(/Delete "empty-tag"/)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[1][0]).toContain("/codebook/tags/12");
    expect(calls[1][1]?.method).toBe("DELETE");
  });

  it("clicking delete group shows confirmation dialog", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByLabelText("Delete group Friction")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByLabelText("Delete group Friction"));
    expect(screen.getByText(/Delete "Friction"/)).toBeInTheDocument();
    expect(screen.getByText(/2 tags will move to Uncategorised/)).toBeInTheDocument();
  });

  it("shows placeholder text for empty subtitle", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Add subtitle…")).toBeInTheDocument();
    });
    // Delight group has empty subtitle — should show placeholder with italic style
    const placeholder = screen.getByText("Add subtitle…");
    expect(placeholder.classList.contains("placeholder")).toBe(true);
  });

  it("renders Uncategorised group first in the grid", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Uncategorised")).toBeInTheDocument();
    });
    // Uncategorised should appear before Friction in DOM order
    const groups = screen.getAllByText(/^(Uncategorised|Friction|Delight)$/);
    expect(groups[0].textContent).toBe("Uncategorised");
    expect(groups[1].textContent).toBe("Friction");
    expect(groups[2].textContent).toBe("Delight");
  });

  it("clicking tag badge text enters edit mode", async () => {
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("confusion")).toBeInTheDocument();
    });
    // Click the badge text (not the delete button)
    await userEvent.click(screen.getByText("confusion"));
    // Should show a contenteditable element with the tag name
    const editEl = document.querySelector(".tag-edit-inline");
    expect(editEl).not.toBeNull();
    expect(editEl).toHaveAttribute("contenteditable", "true");
  });

  it("renaming tag calls PATCH API", async () => {
    mockFetchSequence(MOCK_CODEBOOK, undefined, MOCK_CODEBOOK);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("confusion")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("confusion"));
    const editEl = document.querySelector(".tag-edit-inline") as HTMLElement;
    editEl.textContent = "bewilderment";
    editEl.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[1][0]).toContain("/codebook/tags/10");
    expect(calls[1][1]?.method).toBe("PATCH");
    const body = JSON.parse(calls[1][1]?.body as string);
    expect(body.name).toBe("bewilderment");
  });

  it("clicking new group calls create API", async () => {
    mockFetchSequence(MOCK_CODEBOOK, { id: 3, name: "New group", subtitle: "", colour_set: "task", order: 2, tags: [], total_quotes: 0, is_default: false }, MOCK_CODEBOOK);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("New group")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByText("New group"));
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });
    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls[1][0]).toContain("/codebook/groups");
    expect(calls[1][1]?.method).toBe("POST");
  });
});

// ---------------------------------------------------------------------------
// Per-framework sections
// ---------------------------------------------------------------------------

const MOCK_WITH_FRAMEWORKS: CodebookResponse = {
  groups: [
    {
      id: 99,
      name: "Uncategorised",
      subtitle: "Tags not yet assigned to any group",
      colour_set: "",
      order: 9999,
      tags: [],
      total_quotes: 0,
      is_default: true,
      framework_id: null,
    },
    {
      id: 10,
      name: "Strategy",
      subtitle: "Goals and objectives",
      colour_set: "ux",
      order: 1,
      tags: [
        { id: 100, name: "user need", count: 3, colour_index: 0 },
        { id: 101, name: "business objective", count: 1, colour_index: 1 },
      ],
      total_quotes: 3,
      is_default: false,
      framework_id: "garrett",
    },
    {
      id: 11,
      name: "Scope",
      subtitle: "Features and content",
      colour_set: "ux",
      order: 2,
      tags: [
        { id: 102, name: "feature request", count: 2, colour_index: 0 },
      ],
      total_quotes: 2,
      is_default: false,
      framework_id: "garrett",
    },
    {
      id: 20,
      name: "Usability",
      subtitle: "Ease of use",
      colour_set: "task",
      order: 3,
      tags: [
        { id: 200, name: "learnability", count: 0, colour_index: 0 },
      ],
      total_quotes: 0,
      is_default: false,
      framework_id: "uxr",
    },
  ],
  ungrouped: [],
  all_tag_names: ["business objective", "feature request", "learnability", "user need"],
};

const MOCK_TEMPLATES = {
  templates: [
    {
      id: "garrett",
      title: "The Elements of User Experience",
      author: "Jesse James Garrett",
      description: "A framework for UX design",
      author_bio: "",
      author_links: [],
      groups: [],
      enabled: true,
      imported: true,
    },
    {
      id: "uxr",
      title: "Bristlenose UXR Codebook",
      author: "",
      description: "A general UX research codebook",
      author_bio: "",
      author_links: [],
      groups: [],
      enabled: true,
      imported: true,
    },
  ],
};

describe("CodebookPanel — per-framework sections", () => {
  it("renders separate separator per framework", async () => {
    // First call: codebook, second: templates (fetched on mount for labels)
    mockFetchOk(MOCK_WITH_FRAMEWORKS);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Strategy")).toBeInTheDocument();
    });
    // Framework groups should be rendered
    expect(screen.getByText("Scope")).toBeInTheDocument();
    expect(screen.getByText("Usability")).toBeInTheDocument();
  });

  it("renders Remove from Codebook button per framework section", async () => {
    mockFetchOk(MOCK_WITH_FRAMEWORKS);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Strategy")).toBeInTheDocument();
    });
    // There should be 2 Remove buttons — one for garrett, one for uxr
    const removeButtons = screen.getAllByText("Remove from Codebook");
    expect(removeButtons).toHaveLength(2);
  });

  it("framework groups have no delete/close button", async () => {
    mockFetchOk(MOCK_WITH_FRAMEWORKS);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Strategy")).toBeInTheDocument();
    });
    expect(screen.queryByLabelText("Delete group Strategy")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete group Scope")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete group Usability")).not.toBeInTheDocument();
  });

  it("framework tags are readonly (no delete badge button)", async () => {
    mockFetchOk(MOCK_WITH_FRAMEWORKS);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("user need")).toBeInTheDocument();
    });
    // Framework tags should not have delete buttons
    expect(screen.queryByLabelText("Delete user need")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete business objective")).not.toBeInTheDocument();
  });

  it("clicking Remove opens confirmation dialog with impact stats", async () => {
    const impactResp = { tag_count: 7, quote_count: 4 };
    mockFetchSequence(MOCK_WITH_FRAMEWORKS, impactResp);
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Strategy")).toBeInTheDocument();
    });
    const removeButtons = screen.getAllByText("Remove from Codebook");
    await userEvent.click(removeButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/7 tags across 4 quotes will be removed/)).toBeInTheDocument();
    });
  });

  it("confirming Remove calls DELETE API and refreshes", async () => {
    const codebookAfterRemove: CodebookResponse = {
      groups: [MOCK_WITH_FRAMEWORKS.groups[0], MOCK_WITH_FRAMEWORKS.groups[3]],
      ungrouped: [],
      all_tag_names: ["learnability"],
    };
    const impactResp = { tag_count: 3, quote_count: 2 };
    // Sequence: initial codebook, impact, DELETE response, templates refresh
    mockFetchSequence(
      MOCK_WITH_FRAMEWORKS,
      impactResp,
      codebookAfterRemove,
      MOCK_TEMPLATES,
    );
    render(<CodebookPanel projectId="1" />);
    await waitFor(() => {
      expect(screen.getByText("Strategy")).toBeInTheDocument();
    });
    const removeButtons = screen.getAllByText("Remove from Codebook");
    await userEvent.click(removeButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/will be removed/)).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      // The DELETE call should have been made
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
      const deleteCall = calls.find(
        (c: unknown[]) =>
          typeof c[0] === "string"
          && (c[0] as string).includes("/remove-framework/")
          && (c[1] as { method?: string })?.method === "DELETE",
      );
      expect(deleteCall).toBeDefined();
    });
  });
});
