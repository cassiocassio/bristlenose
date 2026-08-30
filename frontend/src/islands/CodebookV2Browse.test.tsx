import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CodebookV2Browse, type BrowseBook, _shortDescription } from "./CodebookV2Browse";

function tpl(over: Record<string, unknown> = {}) {
  return {
    id: "nielsen", title: "10 Usability Heuristics", author: "Jakob Nielsen",
    description: "Ten broad rules of thumb. Refined from a factor analysis of 249 problems.",
    author_bio: "", author_links: [], groups: [{ name: "G", tags: [{ name: "a" }, { name: "b" }] }],
    enabled: true, imported: true, ...over,
  } as unknown as BrowseBook["template"];
}

function book(over: Partial<BrowseBook> = {}): BrowseBook {
  return {
    id: "nielsen", title: "10 Usability Heuristics", provenance: "Jakob Nielsen",
    provenanceIsPerson: true, installed: true, enabled: true, quotes: 72, tags: 36,
    template: tpl(), ...over,
  };
}

// Typed rather than Record<string, Mock>: vitest does not type-check, but
// `npm run build` runs `tsc -b` over the test files, so a loose signature here
// passes the suite and then fails the build.
type Handlers = {
  onOpen?: (id: string) => void;
  onInstall?: (id: string) => void;
  onUninstall?: (id: string) => void;
  onBack?: () => void;
};

const noop = () => {};
const renderGrid = (books: BrowseBook[], on: Handlers = {}) =>
  render(
    <CodebookV2Browse
      books={books}
      onOpen={on.onOpen ?? noop}
      onInstall={on.onInstall ?? noop}
      onUninstall={on.onUninstall ?? noop}
      onBack={on.onBack ?? noop}
    />,
  );

describe("D12 — one button that swaps its verb", () => {
  it("says Uninstall when installed", () => {
    renderGrid([book()]);
    expect(screen.getByTestId("bn-v2-card-action-nielsen")).toHaveTextContent("Uninstall");
  });

  it("says Install when not", () => {
    renderGrid([book({ installed: false })]);
    expect(screen.getByTestId("bn-v2-card-action-nielsen")).toHaveTextContent("Install");
  });

  it("gives sentiment no button at all", () => {
    // D20: it arrives with the pipeline, so there is nothing to install and
    // uninstalling only destroys tags nothing can restore.
    renderGrid([book({ id: "sentiment", provenance: "On by default", provenanceIsPerson: false })]);
    expect(screen.queryByTestId("bn-v2-card-action-sentiment")).not.toBeInTheDocument();
    // And nothing stands in for it: the provenance line already says what the
    // card needs to say, so a second copy in the button slot would be the
    // absence of a control pretending to be one.
    expect(screen.getAllByText("On by default")).toHaveLength(1);
  });

  it("carries no enable toggle — that lives in the rail (D11)", () => {
    renderGrid([book()]);
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});

describe("the whole card navigates; the button does not", () => {
  it("opens on a card click", () => {
    const onOpen = vi.fn();
    renderGrid([book()], { onOpen });
    fireEvent.click(screen.getByTestId("bn-v2-card-nielsen"));
    expect(onOpen).toHaveBeenCalledWith("nielsen");
  });

  it("opens on Enter", () => {
    const onOpen = vi.fn();
    renderGrid([book()], { onOpen });
    fireEvent.keyDown(screen.getByTestId("bn-v2-card-nielsen"), { key: "Enter" });
    expect(onOpen).toHaveBeenCalledWith("nielsen");
  });

  it("does NOT open when the button is clicked", () => {
    // The one region of the card that does not navigate. Without
    // stopPropagation an uninstall would also change the page under you.
    const onOpen = vi.fn();
    const onUninstall = vi.fn();
    renderGrid([book()], { onOpen, onUninstall });
    fireEvent.click(screen.getByTestId("bn-v2-card-action-nielsen"));
    expect(onUninstall).toHaveBeenCalledWith("nielsen");
    expect(onOpen).not.toHaveBeenCalled();
  });
});

describe("D12 — version renders only if present", () => {
  it("shows it when there is one", () => {
    renderGrid([book({ template: tpl({ version: "2.0" }) })]);
    expect(screen.getByText(/v2\.0/)).toBeInTheDocument();
  });

  it("shows nothing at all when there is not — no dash, no placeholder", () => {
    const { container } = renderGrid([book()]);
    expect(container.querySelector(".picker-card-version")).toBeNull();
  });
});

describe("D27 — switched off, still uninstallable", () => {
  it("knocks the card back", () => {
    const { container } = renderGrid([book({ enabled: false })]);
    expect(container.querySelector(".picker-card.off2")).toBeInTheDocument();
  });

  it("does not use the shipped .disabled class", () => {
    // That one sets pointer-events:none, and a switched-off codebook is still
    // fully interactive — you open it, you read it, you uninstall it.
    const { container } = renderGrid([book({ enabled: false })]);
    expect(container.querySelector(".picker-card.disabled")).toBeNull();
  });

  it("keeps the card openable when switched off", () => {
    const onOpen = vi.fn();
    renderGrid([book({ enabled: false })], { onOpen });
    fireEvent.click(screen.getByTestId("bn-v2-card-nielsen"));
    expect(onOpen).toHaveBeenCalled();
  });
});

describe("the short description is an interim", () => {
  it("takes the first sentence", () => {
    expect(_shortDescription("Ten broad rules. Refined from 249 problems.")).toBe(
      "Ten broad rules.",
    );
  });

  it("returns a single-sentence description whole", () => {
    expect(_shortDescription("Seven sentiment categories")).toBe(
      "Seven sentiment categories",
    );
  });
});

describe("the card can count", () => {
  // Found by looking at it: the page's stat line was fixed and the card's was
  // not, so a codebook with one coded quote read "31 tags on 1 quotes" in the
  // Library while reading correctly one screen away.

  it("says 'quote' for one", () => {
    renderGrid([book({ tags: 31, quotes: 1 })]);
    expect(screen.getByText(/31 tags on 1 quote$/)).toBeInTheDocument();
  });

  it("says 'tag' for one", () => {
    renderGrid([book({ tags: 1, quotes: 5 })]);
    expect(screen.getByText(/^1 tag on 5 quotes$/)).toBeInTheDocument();
  });

  it("still pluralises more than one", () => {
    renderGrid([book({ tags: 36, quotes: 72 })]);
    expect(screen.getByText(/36 tags on 72 quotes/)).toBeInTheDocument();
  });

  it("counts in the not-installed line too", () => {
    renderGrid([book({ installed: false, tags: 1, quotes: 0 })]);
    expect(screen.getByText(/^1 tag$/)).toBeInTheDocument();
  });
});
