import { render, fireEvent, waitFor } from "@testing-library/react";
import { TagFilterDropdown } from "./TagFilterDropdown";
import { EMPTY_TAG_FILTER } from "../utils/filter";
import type { TagFilterState } from "../utils/filter";

vi.mock("../utils/api", () => ({
  getCodebook: vi.fn().mockResolvedValue({
    groups: [
      {
        id: 1,
        name: "UX",
        subtitle: "",
        colour_set: "ux",
        order: 0,
        tags: [
          { id: 10, name: "Navigation", count: 5, colour_index: 0 },
          { id: 11, name: "Usability", count: 3, colour_index: 1 },
        ],
        total_quotes: 8,
        is_default: false,
        framework_id: null,
      },
      {
        id: 2,
        name: "Emotion",
        subtitle: "",
        colour_set: "emo",
        order: 1,
        tags: [{ id: 20, name: "Frustration", count: 4, colour_index: 0 }],
        total_quotes: 4,
        is_default: false,
        framework_id: null,
      },
    ],
    ungrouped: [{ id: 30, name: "Other", count: 2, colour_index: 0 }],
    all_tag_names: ["Navigation", "Usability", "Frustration", "Other"],
  }),
}));

const tagCounts: Record<string, number> = {
  navigation: 5,
  usability: 3,
  frustration: 4,
  other: 2,
};

function renderFilter(overrides: Partial<{
  tagFilter: TagFilterState;
  onTagFilterChange: ReturnType<typeof vi.fn>;
  isOpen: boolean;
  onToggle: ReturnType<typeof vi.fn>;
}> = {}) {
  const onTagFilterChange = overrides.onTagFilterChange ?? vi.fn();
  return {
    onTagFilterChange,
    ...render(
      <TagFilterDropdown
        tagFilter={overrides.tagFilter ?? EMPTY_TAG_FILTER}
        onTagFilterChange={onTagFilterChange}
        tagCounts={tagCounts}
        noTagCount={7}
        isOpen={overrides.isOpen}
        onToggle={overrides.onToggle}
        data-testid="tf"
      />,
    ),
  };
}

describe("TagFilterDropdown", () => {
  it("renders the trigger button with 'Tags' label", () => {
    const { getByTestId } = renderFilter();
    expect(getByTestId("tf-btn").textContent).toContain("Tags");
  });

  it("opens menu on button click and fetches codebook", async () => {
    const { getByTestId, queryByTestId } = renderFilter();
    expect(queryByTestId("tf-menu")).toBeNull();

    fireEvent.click(getByTestId("tf-btn"));
    await waitFor(() => expect(queryByTestId("tf-menu")).not.toBeNull());
  });

  it("renders codebook groups with tags", async () => {
    const { getByTestId, getByText } = renderFilter({ isOpen: true, onToggle: vi.fn() });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());

    expect(getByText("UX")).toBeDefined();
    expect(getByText("Navigation")).toBeDefined();
    expect(getByText("Usability")).toBeDefined();
    expect(getByText("Emotion")).toBeDefined();
    expect(getByText("Frustration")).toBeDefined();
  });

  it("renders ungrouped tags", async () => {
    const { getByText, getByTestId } = renderFilter({ isOpen: true, onToggle: vi.fn() });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());
    expect(getByText("Other")).toBeDefined();
  });

  it("renders '(No tags)' option with count", async () => {
    const { getByText, getByTestId } = renderFilter({ isOpen: true, onToggle: vi.fn() });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());
    expect(getByText("(No tags)")).toBeDefined();
    expect(getByText("7")).toBeDefined(); // noTagCount
  });

  it("unchecking a tag calls onTagFilterChange", async () => {
    const { getByTestId, onTagFilterChange } = renderFilter({
      isOpen: true,
      onToggle: vi.fn(),
    });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());

    // Find the Navigation checkbox and uncheck it
    const labels = getByTestId("tf-menu").querySelectorAll(".tag-filter-item");
    // labels[0] is "(No tags)", labels in groups follow
    const navCheckbox = Array.from(labels).find(
      (l) => l.textContent?.includes("Navigation"),
    )?.querySelector("input");
    expect(navCheckbox).toBeDefined();

    fireEvent.click(navCheckbox!);
    expect(onTagFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ unchecked: ["Navigation"] }),
    );
  });

  it("Select all restores empty filter", async () => {
    const { getByTestId, onTagFilterChange } = renderFilter({
      tagFilter: { unchecked: ["Navigation"], noTagsUnchecked: false, clearAll: false },
      isOpen: true,
      onToggle: vi.fn(),
    });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());

    fireEvent.click(getByTestId("tf-select-all"));
    expect(onTagFilterChange).toHaveBeenCalledWith(EMPTY_TAG_FILTER);
  });

  it("Clear unchecks everything", async () => {
    const { getByTestId, onTagFilterChange } = renderFilter({
      isOpen: true,
      onToggle: vi.fn(),
    });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());

    fireEvent.click(getByTestId("tf-clear"));
    expect(onTagFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ clearAll: true, noTagsUnchecked: true }),
    );
  });

  it("shows tag counts", async () => {
    const { getByTestId } = renderFilter({ isOpen: true, onToggle: vi.fn() });
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());

    const counts = getByTestId("tf-menu").querySelectorAll(".tag-filter-count");
    const countTexts = Array.from(counts).map((el) => el.textContent);
    expect(countTexts).toContain("5"); // Navigation
    expect(countTexts).toContain("3"); // Usability
    expect(countTexts).toContain("4"); // Frustration
  });

  it("updates label when tags are unchecked (after codebook load)", async () => {
    const onToggle = vi.fn();
    const { getByTestId } = renderFilter({
      tagFilter: { unchecked: ["Navigation", "Usability"], noTagsUnchecked: false, clearAll: false },
      isOpen: true,
      onToggle,
    });
    // Wait for codebook to load so total tag count is known
    await waitFor(() => expect(getByTestId("tf-menu")).toBeDefined());
    // 4 total tags - 2 unchecked = 2 checked
    expect(getByTestId("tf-btn").textContent).toContain("2 tags");
  });

  it("shows 'No tags' label when clearAll", () => {
    const { getByTestId } = renderFilter({
      tagFilter: { unchecked: [], noTagsUnchecked: true, clearAll: true },
    });
    expect(getByTestId("tf-btn").textContent).toContain("No tags");
  });
});
