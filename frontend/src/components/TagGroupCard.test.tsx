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

describe("TagGroupCard bar colours", () => {
  beforeEach(() => {
    resetSidebarStore();
  });

  // Sentiment bars wear each sentiment's colour, as everywhere else sentiment is
  // charted; a codebook's bars keep its group's one colour (23 Nov 2026).
  it("draws a sentiment's bar in that sentiment's colour", () => {
    const { container } = render(
      <TagGroupCard
        name="Sentiment"
        subtitle=""
        colourSet="sentiment"
        tags={[
          { id: 1, name: "frustration", count: 0, colour_index: 0 },
          { id: 2, name: "delight", count: 0, colour_index: 5 },
        ]}
        groupBg="#fff"
        tagCounts={{ frustration: 4, delight: 1 }}
        uncheckedSet={new Set()}
        clearAll={false}
        onToggleTag={vi.fn()}
      />,
    );
    const bars = [...container.querySelectorAll(".tag-micro-bar")].map((b) => b.getAttribute("style") ?? "");
    expect(bars[0]).toContain("--bn-sentiment-frustration");
    expect(bars[1]).toContain("--bn-sentiment-delight");
  });

  it("keeps one group colour for a codebook's bars", () => {
    const { container } = renderCard({ "jargon barrier": 1, "risky default": 2 });
    const bars = [...container.querySelectorAll(".tag-micro-bar")].map((b) => b.getAttribute("style") ?? "");
    bars.forEach((b) => expect(b).toContain("--bn-bar-ux"));
  });
});
