import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CodebookV2Rail, type RailBook } from "./CodebookV2Rail";

function book(over: Partial<RailBook> = {}): RailBook {
  return {
    id: "nielsen",
    title: "10 Usability Heuristics",
    provenance: "Jakob Nielsen",
    provenanceIsPerson: true,
    floor: false,
    enabled: true,
    pending: 0,
    ...over,
  };
}

const noop = vi.fn();
function renderRail(books: RailBook[], builtin: string[] = []) {
  return render(
    <CodebookV2Rail
      books={books}
      selectedId=""
      onSelect={noop}
      onToggle={noop}
      builtinIds={new Set(builtin)}
    />,
  );
}

describe("D25 — an empty section keeps its heading", () => {
  it("shows all three headings with nothing installed but the floor", () => {
    renderRail([book({ id: "", floor: true, title: "Your tags", provenance: "" })]);
    for (const h of ["Manual tags", "Default", "Frameworks"]) {
      expect(screen.getByText(h)).toBeInTheDocument();
    }
  });

  it("keeps Frameworks even when it is empty", () => {
    // The case D25 is about: an absent heading reads as "this category does not
    // exist", not "empty". Paired with Browse Library it is what makes the
    // first-run rail self-explaining with no instructional copy.
    renderRail(
      [
        book({ id: "", floor: true, title: "Your tags", provenance: "" }),
        book({ id: "sentiment", title: "Sentiment", provenance: "On by default", provenanceIsPerson: false }),
      ],
      ["sentiment"],
    );
    expect(screen.getByText("Frameworks")).toBeInTheDocument();
    expect(screen.queryByTestId("bn-v2-rail-row-nielsen")).not.toBeInTheDocument();
  });
});

describe("D20 — three shapes, not two", () => {
  it("the floor has no enable control", () => {
    renderRail([book({ id: "", floor: true, title: "Your tags", provenance: "" })]);
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("sentiment has one, because it is toggleable even though it cannot be installed", () => {
    renderRail([book({ id: "sentiment", title: "Sentiment", provenance: "On by default", provenanceIsPerson: false })], ["sentiment"]);
    // Either the platform control or ours, depending on the browser.
    const control =
      screen.queryByRole("switch") ?? screen.queryByRole("checkbox");
    expect(control).toBeInTheDocument();
  });
});

describe("D23 — a system fact does not get the author's weight", () => {
  it("marks non-person provenance so it renders muted", () => {
    renderRail([book({ id: "uxr", title: "UXR", provenance: "Available by default", provenanceIsPerson: false })], ["uxr"]);
    expect(screen.getByText("Available by default").className).toContain("prov-system");
  });

  it("leaves a real author unmarked, keeping treatment B", () => {
    renderRail([book()]);
    expect(screen.getByText("Jakob Nielsen").className).not.toContain("prov-system");
  });
});

describe("the rail is keyboard-reachable", () => {
  it("gives every row a role and a tab stop", () => {
    // The shipped panel gives tag-add-row and new-group-placeholder role=button
    // + tabIndex; a rail that navigates must not be worse.
    renderRail([book()]);
    const row = screen.getByTestId("bn-v2-rail-row-nielsen");
    expect(row).toHaveAttribute("role", "button");
    expect(row).toHaveAttribute("tabindex", "0");
  });

  it("selects on Enter", async () => {
    const onSelect = vi.fn();
    render(
      <CodebookV2Rail
        books={[book()]}
        selectedId=""
        onSelect={onSelect}
        onToggle={noop}
        builtinIds={new Set()}
      />,
    );
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.keyDown(screen.getByTestId("bn-v2-rail-row-nielsen"), { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("nielsen");
  });
});

describe("D10 — the count badge", () => {
  it("shows undecided proposals and hides a zero", () => {
    renderRail([book({ pending: 12 })]);
    expect(screen.getByText("12")).toBeInTheDocument();
    screen.getByTestId("bn-v2-rail-row-nielsen");
  });

  it("renders no badge at zero", () => {
    renderRail([book({ pending: 0 })]);
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });
});
