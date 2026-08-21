import { render, screen } from "@testing-library/react";
import { SectionHeading } from "./SectionHeading";

/**
 * These pin the two properties the atom exists to guarantee, not its CSS.
 *
 * Codebook is the only lens with a zone-level action, and before 20 Aug 2026 it
 * got one by wrapping the h1 in its own flex column. That wrapper silently cost
 * two things a reader would notice — the title sat 40px below the datum every
 * other lens flushes to, and the keyline stopped short of the pane by the
 * button's width — because the h1 was no longer the child the page's datum rule
 * looked for, nor the box that spanned the pane. Neither was visible to any
 * test, because nothing asserted the shape.
 */
describe("SectionHeading", () => {
  it("puts the class on one wrapper whether or not there is an action", () => {
    // The shape must not vary with `action`: a lens with a zone action and a
    // lens without must present the same box to the page's layout rules, or
    // their keylines land at different heights.
    const plain = render(<SectionHeading>Sessions</SectionHeading>).container;
    const acted = render(
      <SectionHeading action={<button>Codebook Library</button>}>Codebooks</SectionHeading>,
    ).container;

    for (const c of [plain, acted]) {
      expect(c.querySelectorAll(".section-heading")).toHaveLength(1);
      // The heading is INSIDE the box that carries the class, never the box
      // itself — that is what lets the keyline span the pane rather than the
      // title's own column.
      expect(c.querySelector(".section-heading > h1")).toBeInTheDocument();
      expect(c.querySelector("h1.section-heading")).not.toBeInTheDocument();
    }
  });

  it("keeps the action out of the heading's accessible name", () => {
    // A <button> nested inside an <h1> is legal HTML but folds into the
    // heading's name — VoiceOver would read "Codebooks Codebook Library,
    // heading level 1". The action is a sibling, so it does not.
    render(
      <SectionHeading action={<button>Codebook Library</button>}>Codebooks</SectionHeading>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveAccessibleName("Codebooks");
    expect(screen.getByRole("button", { name: "Codebook Library" })).toBeInTheDocument();
  });

  it("keeps the anchor id on the heading so TOC links still resolve", () => {
    const { container } = render(<SectionHeading id="themes">Themes</SectionHeading>);
    expect(container.querySelector("h1#themes")).toBeInTheDocument();
  });
});
