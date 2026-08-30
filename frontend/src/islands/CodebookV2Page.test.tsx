import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CodebookV2Page, type PageBook } from "./CodebookV2Page";
import type { CodebookGroupResponse } from "../utils/types";

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
      book={b} groups={groups}
      onReview={noop} onInstall={noop} onUninstall={noop}
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
    expect(screen.getByText(/3 tags on 72 quotes/)).toBeInTheDocument();
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
