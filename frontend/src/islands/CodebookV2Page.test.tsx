import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CodebookV2Page, type PageBook } from "./CodebookV2Page";
import type { CodebookAuthoring } from "../hooks/useCodebookAuthoring";
import type { CodebookGroupResponse } from "../utils/types";

/** Inert authoring — these tests are about D20/D26/D27, not about editing. */
const inertAuthoring: CodebookAuthoring = {
  groupProps: {
    onUpdateGroup: vi.fn(),
    onDeleteGroup: vi.fn(),
    onCreateTag: vi.fn(),
    onDeleteTag: vi.fn(),
    onRenameTag: vi.fn(),
    onDragStart: vi.fn(),
    onDragEnd: vi.fn(),
    onDropTag: vi.fn(),
    onMergeDrop: vi.fn(),
  },
  onCreateGroup: vi.fn(),
  onDropNewGroup: vi.fn(),
  pendingMerge: null,
  onConfirmMerge: vi.fn(),
  onCancelMerge: vi.fn(),
};

function book(over: Partial<PageBook> = {}): PageBook {
  return {
    id: "nielsen",
    title: "10 Usability Heuristics",
    provenance: "Jakob Nielsen",
    provenanceIsPerson: true,
    floor: false,
    installed: true,
    enabled: true,
    pending: 12,
    quotes: 72,
    ...over,
  };
}

function group(tags: number, name = "Status visibility"): CodebookGroupResponse {
  return {
    id: 1, name, subtitle: "Does the user know what's happening?",
    colour_set: "ux", order: 0, total_quotes: 4, is_default: false,
    framework_id: "nielsen",
    tags: Array.from({ length: tags }, (_, i) => ({
      id: i, name: `tag${i}`, count: i + 1, tentative_count: i, colour_index: i,
    })),
  } as CodebookGroupResponse;
}

const noop = vi.fn();
const renderPage = (b: PageBook, groups: CodebookGroupResponse[] = [group(3)]) =>
  render(
    <CodebookV2Page
      projectName="Ikea"
      book={b} groups={groups}
      onReview={noop} onInstall={noop} onUninstall={noop}
      authoring={inertAuthoring} allTagNames={[]}
    />,
  );

describe("D20 — three shapes", () => {
  it("the floor has no install or uninstall", () => {
    renderPage(book({ id: "", floor: true, title: "Your tags", provenance: "" }));
    expect(screen.queryByTestId("bn-v2-install")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bn-v2-uninstall")).not.toBeInTheDocument();
  });

  it("sentiment has no install or uninstall either", () => {
    // It arrives with the pipeline: nothing to install, and uninstalling only
    // destroys tags nothing can restore (register A4, closed by deletion).
    renderPage(book({ id: "sentiment", title: "Sentiment", provenance: "On by default", provenanceIsPerson: false }));
    expect(screen.queryByTestId("bn-v2-uninstall")).not.toBeInTheDocument();
  });

  it("a framework has one", () => {
    renderPage(book());
    expect(screen.getByTestId("bn-v2-uninstall")).toBeInTheDocument();
  });

  it("offers Install when not installed", () => {
    renderPage(book({ installed: false }));
    expect(screen.getByTestId("bn-v2-install")).toBeInTheDocument();
  });
});

describe("the Review door", () => {
  it("is the verb, with the counts beside it", () => {
    renderPage(book());
    expect(screen.getByTestId("bn-v2-review")).toHaveTextContent("Review");
    expect(screen.getByText(/3 tags · applied to 72 quotes in Ikea/)).toBeInTheDocument();
    expect(screen.getByText(/12 undecided/)).toBeInTheDocument();
  });

  it("is suppressed for a codebook with no tags", () => {
    // A door onto nothing is worse than no door: without the gate this would
    // read "Review 0 tags on 0 quotes".
    renderPage(book(), []);
    expect(screen.queryByTestId("bn-v2-review")).not.toBeInTheDocument();
  });

  it("is suppressed for sentiment, which has no proposals to review", () => {
    renderPage(book({ id: "sentiment", provenance: "On by default", provenanceIsPerson: false }));
    expect(screen.queryByTestId("bn-v2-review")).not.toBeInTheDocument();
  });
});

describe("D26 — a codebook with no tags says so, bleakly", () => {
  it("states the fact and nothing else", () => {
    renderPage(book(), []);
    expect(screen.getByTestId("bn-v2-empty")).toHaveTextContent(
      "This codebook has no tags.",
    );
  });

  it("offers no call to action alongside it", () => {
    // No illustration, no button, no reframing of the absence as an
    // opportunity. The fact is the whole message.
    const { container } = renderPage(book(), []);
    expect(container.querySelector(".pg-empty button")).toBeNull();
  });
});

describe("D27 — switched off, but still uninstallable", () => {
  it("knocks the page back", () => {
    const { container } = renderPage(book({ enabled: false }));
    expect(container.querySelector(".pageoff")).toBeInTheDocument();
  });

  it("keeps Uninstall reachable", () => {
    // A blanket knock-back removes precisely the one control that must stay
    // reachable on a disabled codebook.
    renderPage(book({ enabled: false }));
    expect(screen.getByTestId("bn-v2-uninstall")).toBeInTheDocument();
  });
});

describe("nothing re-implements a tag row", () => {
  it("emits the shipped group and tag classes", () => {
    // The histogram alignment this repo has already paid for is inherited by
    // emitting .codebook-group / .tag-row / .tag-bar-area, not approximated.
    const { container } = renderPage(book());
    expect(container.querySelector(".codebook-group")).toBeInTheDocument();
    expect(container.querySelectorAll(".tag-row")).toHaveLength(3);
    expect(container.querySelector(".tag-bar-area")).toBeInTheDocument();
  });
});

describe("only the floor grows groups", () => {
  const floorGroup = (): CodebookGroupResponse => ({
    ...group(1, "Your tags"),
    framework_id: null,
    is_default: true,
  });

  it("offers the new-group card on the floor", () => {
    const { container } = renderPage(
      book({ id: "", floor: true, title: "Your tags", provenance: "" }),
      [floorGroup()],
    );
    expect(container.querySelector(".new-group-placeholder")).toBeInTheDocument();
  });

  it("does not offer it on a framework — that structure is its author's", () => {
    const { container } = renderPage(book());
    expect(container.querySelector(".new-group-placeholder")).toBeNull();
  });

  it("keeps the floor authorable when it has no tags", () => {
    // D26's bleak sentence governs "a codebook with no tags"; the floor is not
    // a codebook you installed, it is the surface you author. Replacing its
    // controls with a sentence would leave a researcher no way to begin —
    // a state the shipped lens never puts them in.
    const { container } = renderPage(
      book({ id: "", floor: true, title: "Your tags", provenance: "" }),
      [{ ...floorGroup(), tags: [] }],
    );
    expect(screen.queryByTestId("bn-v2-empty")).not.toBeInTheDocument();
    expect(container.querySelector(".new-group-placeholder")).toBeInTheDocument();
    expect(container.querySelector(".tag-add-row")).toBeInTheDocument();
  });

  it("still says so, bleakly, for a framework with no tags", () => {
    renderPage(book(), []);
    expect(screen.getByTestId("bn-v2-empty")).toBeInTheDocument();
  });
});

describe("author links are gated", () => {
  it("drops a link the URL guard refuses", () => {
    renderPage(
      book({
        template: {
          id: "nielsen", title: "T", author: "Jakob Nielsen", description: "",
          author_bio: "Bio.", enabled: true, imported: true,
          groups: [],
          author_links: [
            { label: "real", url: "https://nngroup.com/" },
            { label: "nngroup.com", url: "javascript:alert(1)" },
          ],
        },
      }),
    );
    expect(screen.getByText(/real/)).toBeInTheDocument();
    expect(screen.queryByText(/^nngroup\.com/)).not.toBeInTheDocument();
  });
});

describe("the stat line can count", () => {
  // "1 tags on 3 quotes" is wrong in the one language this lens ships in, and
  // a stat line that cannot count is not a stat line.

  it("says 'tag' and 'quote' for one of each", () => {
    renderPage(book({ quotes: 1, pending: 0 }), [group(1)]);
    const meta = screen.getByText(/applied to 1 quote/);
    expect(meta.textContent).toContain("1 tag · applied to 1 quote in Ikea");
    expect(meta.textContent).not.toContain("1 tags");
    expect(meta.textContent).not.toContain("1 quotes");
  });

  it("still says 'tags' and 'quotes' for more than one", () => {
    renderPage(book({ quotes: 4, pending: 0 }), [group(3)]);
    expect(screen.getByText(/applied to 4 quotes/).textContent).toContain(
      "3 tags · applied to 4 quotes in Ikea",
    );
  });

  it("counts in the no-review-door stat line too", () => {
    // A codebook with no review door renders a different line, and the bug
    // was in both.
    renderPage(book({ id: "sentiment", provenance: "On by default", quotes: 1 }), [group(1)]);
    expect(screen.getByText(/1 tag · applied to 1 quote in Ikea/)).toBeInTheDocument();
  });
});

describe("Q14 — export mode hides the doors it cannot honour", () => {
  // v2's other controls escape by accident of the extraction: Uninstall carries
  // `.framework-remove-btn` and the authoring carries `.tag-add-row`, both of
  // which theme/templates/export.css already hides. The Review door has no such
  // class, so nothing was hiding it — and its modal reads a SERVER_ONLY
  // endpoint and offers a write, neither of which exists in a leave-behind.

  const renderReadOnly = (b = book()) =>
    render(
      <CodebookV2Page
      projectName="Ikea"
        book={b} groups={[group(3)]}
        onReview={noop} onInstall={noop} onUninstall={noop}
        authoring={inertAuthoring} allTagNames={[]} readOnly
      />,
    );

  it("hides the Review door", () => {
    renderReadOnly();
    expect(screen.queryByTestId("bn-v2-review")).not.toBeInTheDocument();
  });

  it("hides Install and Uninstall", () => {
    renderReadOnly();
    expect(screen.queryByTestId("bn-v2-install")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bn-v2-uninstall")).not.toBeInTheDocument();
  });

  it("still shows the counts — read-only is not blank", () => {
    // Hiding the control must not hide the information. A client reading the
    // export should still see what the codebook found.
    renderReadOnly();
    expect(screen.getByText(/3 tags · applied to 72 quotes in Ikea/)).toBeInTheDocument();
  });

  it("keeps the door when NOT read-only", () => {
    // The gate must not be a mute button — without this the first three tests
    // would pass on a component that never renders a Review door at all.
    render(
      <CodebookV2Page
      projectName="Ikea"
        book={book()} groups={[group(3)]}
        onReview={noop} onInstall={noop} onUninstall={noop}
        authoring={inertAuthoring} allTagNames={[]}
      />,
    );
    expect(screen.getAllByTestId("bn-v2-review").length).toBeGreaterThan(0);
  });
});
