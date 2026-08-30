/**
 * Tests for CodebookSidebar — codebook-level navigation sidebar.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { CodebookSidebar } from "./CodebookSidebar";

// ── Mocks ──────────────────────────────────────────────────────────

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  getCodebook: vi.fn(),
  getCodebookTemplates: vi.fn(),
  getFrameworkStates: vi.fn(),
  putFrameworkStates: vi.fn(),
  putHiddenTagGroups: vi.fn(),
}));

import {
  apiGet,
  getCodebook,
  getCodebookTemplates,
  getFrameworkStates,
} from "../utils/api";
import { resetSidebarStore } from "../contexts/SidebarStore";

const mockApiGet = vi.mocked(apiGet);
const mockGetCodebook = vi.mocked(getCodebook);
const mockGetCodebookTemplates = vi.mocked(getCodebookTemplates);
const mockGetFrameworkStates = vi.mocked(getFrameworkStates);

// ── Test data ──────────────────────────────────────────────────────

const PROJECT_INFO = {
  project_name: "Project Ikea",
  session_count: 5,
  participant_count: 5,
};

const CODEBOOK_RESPONSE = {
  groups: [
    { id: 1, name: "User tags", framework_id: null, subtitle: "", colour_set: "ux", order: 0, tags: [], total_quotes: 22, is_default: false },
    { id: 2, name: "Emotions", framework_id: "sentiment", subtitle: "", colour_set: "emo", order: 0, tags: [], total_quotes: 50, is_default: false },
    { id: 3, name: "Honeycomb", framework_id: "morville", subtitle: "", colour_set: "task", order: 0, tags: [], total_quotes: 41, is_default: false },
  ],
  ungrouped: [],
  all_tag_names: [],
};

const TEMPLATES_RESPONSE = {
  templates: [
    {
      id: "sentiment",
      title: "Emotional and cognitive signals",
      author: "",
      description: "Built-in sentiment",
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
      description: "UXR codebook",
      author_bio: "",
      author_links: [],
      groups: [],
      enabled: true,
      imported: false,
    },
    {
      id: "morville",
      title: "The User Experience Honeycomb",
      author: "Peter Morville",
      description: "Honeycomb",
      author_bio: "",
      author_links: [],
      groups: [],
      enabled: true,
      imported: true,
    },
    {
      id: "garrett",
      title: "The Elements of User Experience",
      author: "Jesse James Garrett",
      description: "Elements",
      author_bio: "",
      author_links: [],
      groups: [],
      enabled: true,
      imported: false,
    },
  ],
};

// ── Setup ──────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  resetSidebarStore();
  mockApiGet.mockResolvedValue(PROJECT_INFO);
  mockGetCodebook.mockResolvedValue(CODEBOOK_RESPONSE);
  mockGetCodebookTemplates.mockResolvedValue(TEMPLATES_RESPONSE);
  mockGetFrameworkStates.mockResolvedValue({});
});

/** The label text is wrapped in a `.codebook-toc-label` span; classes
 * (active / not-imported / codebook-disabled) live on the parent anchor. */
function rowByLabel(label: string): HTMLAnchorElement {
  const el = screen.getByText(label).closest("a");
  if (!el) throw new Error(`no anchor for row "${label}"`);
  return el as HTMLAnchorElement;
}

// ── Tests ──────────────────────────────────────────────────────────

describe("CodebookSidebar", () => {
  it("renders three section headings", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Manual tags")).toBeInTheDocument();
    });
    expect(screen.getByText("Default")).toBeInTheDocument();
    expect(screen.getByText("Library")).toBeInTheDocument();
  });

  it("renders project name under Manual tags", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Project Ikea")).toBeInTheDocument();
    });
  });

  it("renders imported templates as normal toc-link", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Emotional and cognitive signals")).toBeInTheDocument();
    });
    const link = rowByLabel("Emotional and cognitive signals");
    expect(link).toHaveClass("toc-link");
    expect(link).not.toHaveClass("not-imported");
  });

  it("renders not-imported templates with not-imported class", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("The Elements of User Experience")).toBeInTheDocument();
    });
    const link = rowByLabel("The Elements of User Experience");
    expect(link).toHaveClass("toc-link");
    expect(link).toHaveClass("not-imported");
  });

  it("renders imported framework as normal toc-link", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("The User Experience Honeycomb")).toBeInTheDocument();
    });
    const link = rowByLabel("The User Experience Honeycomb");
    expect(link).toHaveClass("toc-link");
    expect(link).not.toHaveClass("not-imported");
  });

  // The sidebar's "Codebook Library →" button was removed 14 Aug 2026 — it
  // duplicated the primary button already in the Codebooks panel header. The
  // browse event it fired is still covered below, via the not-imported row
  // (the surviving in-sidebar path to the same modal).
  it("has no browse button of its own", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Library")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("defaults active to project entry", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Project Ikea")).toBeInTheDocument();
    });
    const projectLink = rowByLabel("Project Ikea");
    expect(projectLink).toHaveClass("active");
  });

  it("sets active on click of imported entry", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Emotional and cognitive signals")).toBeInTheDocument();
    });

    // Mock scrollIntoView since it doesn't exist in jsdom
    const mockScrollIntoView = vi.fn();
    const mockEl = document.createElement("div");
    mockEl.scrollIntoView = mockScrollIntoView;
    mockEl.id = "codebook-fw-sentiment";
    document.body.appendChild(mockEl);

    fireEvent.click(screen.getByText("Emotional and cognitive signals"));

    expect(rowByLabel("Emotional and cognitive signals")).toHaveClass("active");
    expect(rowByLabel("Project Ikea")).not.toHaveClass("active");
    expect(mockScrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });

    document.body.removeChild(mockEl);
  });

  it("dispatches bn:codebook-browse on not-imported click", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("The Elements of User Experience")).toBeInTheDocument();
    });

    const handler = vi.fn();
    window.addEventListener("bn:codebook-browse", handler);

    fireEvent.click(screen.getByText("The Elements of User Experience"));

    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toEqual({ templateId: "garrett" });

    window.removeEventListener("bn:codebook-browse", handler);
  });

  it("re-fetches data on codebook-changed event", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Project Ikea")).toBeInTheDocument();
    });

    // Initial fetch: 3 calls (apiGet + getCodebook + getCodebookTemplates)
    expect(mockGetCodebook).toHaveBeenCalledTimes(1);

    // Dispatch codebook-changed
    window.dispatchEvent(new Event("codebook-changed"));

    await waitFor(() => {
      expect(mockGetCodebook).toHaveBeenCalledTimes(2);
    });
  });

  it("returns null while loading", () => {
    // Never resolve the promises
    mockApiGet.mockReturnValue(new Promise(() => {}));
    mockGetCodebook.mockReturnValue(new Promise(() => {}));
    mockGetCodebookTemplates.mockReturnValue(new Promise(() => {}));

    const { container } = render(<CodebookSidebar />);
    expect(container.innerHTML).toBe("");
  });

  it("splits built-in and framework templates correctly", async () => {
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("Emotional and cognitive signals")).toBeInTheDocument();
    });

    // Built-in (author === ""): sentiment (imported), uxr (not imported)
    // Frameworks (author !== ""): morville (imported), garrett (not imported)
    const allLinks = screen.getAllByRole("link");
    const labels = allLinks.map((el) => el.textContent);
    expect(labels).toContain("Emotional and cognitive signals");
    expect(labels).toContain("Bristlenose UXR Codebook");
    expect(labels).toContain("The User Experience Honeycomb");
    expect(labels).toContain("The Elements of User Experience");
  });

  it("status dot: blue for enabled, grey for disabled, none for available/floor", async () => {
    // Honeycomb (morville) is imported but switched OFF.
    mockGetFrameworkStates.mockResolvedValue({ morville: false });
    render(<CodebookSidebar />);
    await waitFor(() => {
      expect(screen.getByText("The User Experience Honeycomb")).toBeInTheDocument();
    });
    // Wait for the async hydrate to flip the disabled set.
    await waitFor(() => {
      expect(
        rowByLabel("The User Experience Honeycomb").querySelector(".codebook-dot"),
      ).toHaveClass("codebook-dot-off");
    });

    const dot = (label: string) =>
      rowByLabel(label).querySelector(".codebook-dot") as HTMLElement;

    // Enabled + imported → blue dot.
    expect(dot("Emotional and cognitive signals")).toHaveClass("codebook-dot-on");
    // Disabled + imported → grey dot; the row also gets the muted class.
    expect(dot("The User Experience Honeycomb")).toHaveClass("codebook-dot-off");
    expect(rowByLabel("The User Experience Honeycomb")).toHaveClass("codebook-disabled");
    // Not imported → transparent slot (no colour modifier).
    expect(dot("The Elements of User Experience")).not.toHaveClass("codebook-dot-on");
    expect(dot("The Elements of User Experience")).not.toHaveClass("codebook-dot-off");
    // Floor (project) → bare slot, no switch, no colour modifier.
    expect(dot("Project Ikea")).not.toHaveClass("codebook-dot-on");
    expect(dot("Project Ikea")).not.toHaveClass("codebook-dot-off");
  });
});
