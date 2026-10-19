import { render } from "@testing-library/react";
import { TagGroupCard } from "./TagGroupCard";
import { resetSidebarStore } from "../contexts/SidebarStore";

const TAGS = [
  { id: 1, name: "Jargon barrier", count: 0, colour_index: 0 },
  { id: 2, name: "Risky default", count: 0, colour_index: 1 },
];

function renderCard(tagCounts: Record<string, number>, tentativeCounts: Record<string, number> = {}) {
  return render(
    <TagGroupCard
      name="Norman"
      subtitle=""
      colourSet="ux"
      tags={TAGS}
      groupBg="#fff"
      tagCounts={tagCounts}
      tentativeCounts={tentativeCounts}
      uncheckedSet={new Set()}
      clearAll={false}
      onToggleTag={vi.fn()}
    />,
  );
}

describe("TagGroupCard total", () => {
  beforeEach(() => {
    resetSidebarStore();
  });

  it("shows the total when the group has accepted quotes", () => {
    const { container } = renderCard({ "jargon barrier": 1, "risky default": 2 });
    expect(container.querySelector(".group-total-count")).toHaveTextContent("3");
  });

  it("drops the whole total row at zero, even with proposals pending", () => {
    const { container } = renderCard({}, { "jargon barrier": 4, "risky default": 2 });
    expect(container.querySelector(".group-total-row")).not.toBeInTheDocument();
  });
});
