/**
 * HelpSection — landing page for the Help modal.
 *
 * Teaches researchers how to read and interpret their analysis output.
 * Not a feature catalogue — an orientation guide.
 *
 * Stubbed with headings; prose content to be written in a separate pass.
 *
 * @module HelpSection
 */

export function HelpSection() {
  return (
    <>
      <p>
        This guide explains how to read and work with your Bristlenose analysis.
      </p>

      <h4>Sections and themes</h4>
      <p>
        Each quote is classified as screen-specific (about a particular screen
        or task) or general context (about the participant&rsquo;s broader
        situation). Screen-specific quotes are grouped into sections; general
        quotes are grouped into emergent themes. Every quote appears in exactly
        one place.
      </p>

      <h4>Sentiment tagging</h4>
      <p>
        Seven sentiment tags designed for UX research: frustration, confusion,
        doubt, surprise, satisfaction, delight, and confidence. Each quote
        receives one tag based on the participant&rsquo;s expressed emotion.
      </p>

      <h4>Signals</h4>
      <p>
        The analysis page surfaces signals &mdash; statistically notable
        concentrations of sentiment within report sections. Strong and moderate
        signals highlight where participant experience clusters.
      </p>

      <h4>Stars, tags, and filters</h4>
      <p>
        Star quotes to mark important findings. Add tags to build your own
        coding scheme. Use the tag filter and search to focus on what matters.
        All changes are saved automatically.
      </p>

      <h4>Export</h4>
      <p>
        Download a self-contained HTML report that works offline. The export
        preserves all your stars, tags, and edits.
      </p>
    </>
  );
}
