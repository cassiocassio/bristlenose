/**
 * SectionHeading — the zone title on a lens page.
 *
 * One h1 per top-level content zone, named for the zone, never the lens
 * (docs/design-lens-template.md § "The h1 scheme"). Quotes has two
 * ("Sections" / "Themes"), Analysis two, Codebook and Sessions one each.
 *
 * WHY A COMPONENT and not just the `.section-heading` class: a class you have
 * to remember to type will eventually be forgotten. Codebook's h1 carried no
 * class at all in any of its three render states, so it rendered with correct
 * type (inherited) and no horizontal rule, and nothing caught it — the type
 * being right is exactly what makes the missing rule easy to miss. Rendering
 * a zone title through this component makes the treatment structural rather
 * than remembered.
 *
 * Size and weight are NOT set here or in the atom — they inherit from `h1`,
 * so the semantic level and the graphic size stay separate knobs.
 *
 * THE MARKUP IS A WRAPPER, ALWAYS (20 Aug 2026) — a div carrying the class
 * and the keyline, with the h1 inside and an optional action beside it. The
 * shape does not vary with `action`, deliberately: one DOM shape and one CSS
 * path for every zone title in the app means a change to the title treatment
 * lands on all five lenses identically, and a lens that grows an action later
 * gets exactly the geometry the others already have. See the atom
 * (bristlenose/theme/atoms/section-heading.css) for why the row — rather than
 * the text — has to be the box that carries the rule.
 *
 * The action is a SIBLING of the h1, not a child. Nesting a <button> inside a
 * heading is legal HTML but makes the whole thing one accessible name —
 * VoiceOver would read "Codebooks Codebook Library, heading level 1".
 */

interface SectionHeadingProps {
  children: React.ReactNode;
  /** Anchor target — TOC links and scrollToAnchor() resolve against this. */
  id?: string;
  /**
   * Optional zone-level action, rendered right-aligned on the title's row and
   * bottom-aligned to the keyline. Pass `null`/`undefined` for no action; the
   * row's height and the keyline's position are identical either way.
   */
  action?: React.ReactNode;
  "data-testid"?: string;
}

export function SectionHeading({
  children,
  id,
  action,
  "data-testid": testId,
}: SectionHeadingProps) {
  return (
    <div className="section-heading">
      <h1 id={id} data-testid={testId}>
        {children}
      </h1>
      {action ? <div className="section-heading-action">{action}</div> : null}
    </div>
  );
}
