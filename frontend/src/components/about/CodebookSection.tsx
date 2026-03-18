/** Codebook section — qualitative coding methodology, framework codebooks, references. */

export function CodebookSection() {
  return (
    <>
      <h3>Sections and themes</h3>
      <p>
        Each quote is classified as either <strong>screen-specific</strong>{" "}
        (about a particular screen or task) or{" "}
        <strong>general context</strong> (about the participant&rsquo;s broader
        situation). Screen-specific quotes are grouped by screen; general-context
        quotes are grouped by emergent theme. Every quote appears in exactly one
        section of the report &mdash; no duplicates.
      </p>
      <p>
        Themes are inductive: they emerge from the data rather than being
        imposed from a fixed taxonomy, following Braun &amp; Clarke&rsquo;s
        (2006) thematic analysis. A theme requires at least two quotes &mdash;
        a single quote is an observation, not a pattern.
      </p>
      <p>
        Quotes follow a principle of &ldquo;dignity without distortion&rdquo;
        &mdash; filler words are removed, light grammar fixes applied, but
        meaning and emotional register are never changed. Clarifying context
        is added in [square brackets] only when needed. Researcher questions
        that precede a quote are preserved as context prefixes.
      </p>

      <h3>Sentiment tags</h3>
      <p>
        Seven sentiment categories are applied during quote extraction:
        frustration, confusion, doubt, surprise, satisfaction, delight, and
        confidence. Each has an intensity scale of 1&ndash;3. Quotes with no
        emotional content receive no sentiment tag. See the Signals section for
        the full taxonomy and how sentiment concentration is computed.
      </p>

      <h3>Framework codebooks</h3>
      <p>
        Four codebooks are available for autocode tagging. Each defines a set
        of code groups with tag definitions that an LLM uses to classify quotes.
        Tags are applied with a confidence score; the researcher reviews and
        accepts or rejects proposals.
      </p>

      <h4>The Elements of User Experience (Garrett)</h4>
      <p>
        Five-layer model from abstract strategy to concrete surface design:
        Strategy, Scope, Structure, Skeleton, Surface. Each layer depends on the
        one below &mdash; a top-down hierarchy of UX decisions. 5 code groups,
        20 tags.
      </p>
      <div className="bn-about-citation">
        <p>
          Garrett, J. J. (2010). <em>The Elements of User Experience:
          User-Centered Design for the Web and Beyond</em> (2nd ed.).
          New Riders.{" "}
          <a href="https://www.jjg.net/elements/">[Author]</a>
        </p>
      </div>

      <h4>The Design of Everyday Things (Norman)</h4>
      <p>
        Seven interaction design principles: Discoverability, Feedback,
        Conceptual Model, Signifiers, Mapping, Constraints, Slips vs Mistakes.
        A bottom-up diagnostic framework that names the moment of interaction
        failure. 7 code groups, 26 tags.
      </p>
      <div className="bn-about-citation">
        <p>
          Norman, D. (2013). <em>The Design of Everyday Things</em>
          (Rev. ed.). Basic Books.{" "}
          <a href="https://mitpress.mit.edu/9780262525671/the-design-of-everyday-things/">[Publisher]</a>
        </p>
      </div>

      <h4>Platonic Ontology &amp; Epistemology</h4>
      <p>
        Six domains of Platonic philosophy: Theory of Forms, Knowledge &amp;
        Opinion, Dialectic Method, Soul &amp; Psychology, Ethics &amp; Virtue,
        Argumentation &amp; Irony. For analysing philosophical texts rather
        than product interviews. 6 code groups, 30 tags.
      </p>
      <div className="bn-about-citation">
        <p>
          Composite framework drawing on Vlastos (elenchus, irony), Fine
          (epistemology, Forms), Kraut (ethics, Republic), Sedley
          (cosmology), and Irwin (moral psychology).
        </p>
      </div>

      <h4>Bristlenose UXR Codebook</h4>
      <p>
        Eight universal qualitative research patterns: Behaviour, Pain points,
        Needs &amp; desires, Mental models, Motivation, Emotion &amp; trust,
        Context, Learning. Domain-agnostic practitioner vocabulary that works
        across any research study. 8 code groups, 45 tags.
      </p>

      <h3>References</h3>
      <div className="bn-about-citation">
        <p>
          Braun, V., &amp; Clarke, V. (2006). Using thematic analysis in
          psychology. <em>Qualitative Research in Psychology, 3</em>(2),
          77&ndash;101.{" "}
          <a href="https://doi.org/10.1191/1478088706qp063oa">[DOI]</a>
        </p>
        <p className="summary">
          Flexible six-phase method for identifying patterns in qualitative
          data &mdash; inductive (data-driven) or deductive (theory-driven).
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Salda&ntilde;a, J. (2021). <em>The Coding Manual for Qualitative
          Researchers</em> (4th ed.). SAGE.{" "}
          <a href="https://us.sagepub.com/en-us/nam/the-coding-manual-for-qualitative-researchers/book273583">[Publisher]</a>
        </p>
        <p className="summary">
          The standard reference for qualitative coding &mdash; descriptive,
          in vivo, process, emotion, values, and evaluation coding.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Ericsson, K. A., &amp; Simon, H. A. (1993).{" "}
          <em>Protocol Analysis: Verbal Reports as Data</em> (Rev. ed.). MIT
          Press.{" "}
          <a href="https://mitpress.mit.edu/9780262550239/protocol-analysis/">[Publisher]</a>
        </p>
        <p className="summary">
          The foundational text on think-aloud protocols &mdash; establishes
          when verbal reports provide valid data about cognitive processes.
        </p>
      </div>
    </>
  );
}
