import { act, fireEvent, render, screen, within } from "@testing-library/react";

import { TagSpecimen } from "./TagSpecimen";

const root = () => document.documentElement;
const card = (domId: string) => document.getElementById(domId) as HTMLElement;

describe("TagSpecimen", () => {
  afterEach(() => root().removeAttribute("data-autocode-tentative"));

  it("draws every context through its production component", () => {
    render(<TagSpecimen />);
    expect(screen.getAllByTestId("bn-tag-specimen-context")).toHaveLength(5);
    // QuoteCard: tentative tags on both Quotes cards and on the Screens copy.
    expect(card("q-tag-specimen-1").querySelectorAll(".badge-proposed")).toHaveLength(2);
    expect(card("q-tag-specimen-3").closest(".screens-card")).not.toBeNull();
    // TagGroupCard inside the sidebar panel, with the two-tone bar for tentative counts.
    expect(document.querySelector(".tag-sidebar .tag-micro-bar-tentative")).not.toBeNull();
    // CodebookGroupColumn.
    expect(document.querySelector(".v2-groups .codebook-group")).not.toBeNull();
    // The review dialog's counters and its tentative row's dashed tag.
    expect(document.querySelector(".threshold-zone-counter--tentative")).not.toBeNull();
    expect(document.querySelector(".threshold-tag-tentative")).not.toBeNull();
  });

  it("sets the pulse through the playback's own switch, and clears it on leaving", () => {
    const { unmount } = render(<TagSpecimen />);
    expect(root().hasAttribute("data-autocode-tentative")).toBe(false);
    fireEvent.click(screen.getByTestId("bn-tag-specimen-pulse"));
    expect(root().getAttribute("data-autocode-tentative")).toBe("pulse");
    fireEvent.click(screen.getByTestId("bn-tag-specimen-calm"));
    expect(root().getAttribute("data-autocode-tentative")).toBe("calm");
    fireEvent.click(screen.getByTestId("bn-tag-specimen-still"));
    expect(root().hasAttribute("data-autocode-tentative")).toBe(false);
    fireEvent.click(screen.getByTestId("bn-tag-specimen-pulse"));
    unmount();
    expect(root().hasAttribute("data-autocode-tentative")).toBe(false);
  });

  it("accepting a tentative tag makes it a solid tag that flashes", () => {
    vi.useFakeTimers();
    try {
      render(<TagSpecimen />);
      const first = card("q-tag-specimen-1");
      const proposed = first.querySelector(".badge-proposed") as HTMLElement;
      const name = proposed.firstChild?.textContent ?? "";
      fireEvent.click(within(proposed).getByRole("button", { name: /accept/i }));
      expect(first.querySelectorAll(".badge-proposed")).toHaveLength(1);
      const flashing = first.querySelector(".badge-accept-flash") as HTMLElement;
      expect(flashing.textContent).toContain(name);
      act(() => {
        vi.advanceTimersByTime(600);
      });
      expect(first.querySelector(".badge-accept-flash")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("a decision in the review moves the row and its count", () => {
    render(<TagSpecimen />);
    const tentativeCount = () =>
      document.querySelector(".threshold-zone-counter--tentative .threshold-zone-counter-count")?.textContent;
    expect(tentativeCount()).toContain("2");
    const row = document.querySelector(".threshold-tag-tentative")!.closest("tr") as HTMLElement;
    fireEvent.click(within(row).getAllByRole("button")[0]);
    expect(tentativeCount()).toContain("1");
  });
});
