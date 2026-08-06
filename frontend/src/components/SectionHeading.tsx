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
 */

interface SectionHeadingProps {
  children: React.ReactNode;
  /** Anchor target — TOC links and scrollToAnchor() resolve against this. */
  id?: string;
  "data-testid"?: string;
}

export function SectionHeading({
  children,
  id,
  "data-testid": testId,
}: SectionHeadingProps) {
  return (
    <h1 id={id} className="section-heading" data-testid={testId}>
      {children}
    </h1>
  );
}
