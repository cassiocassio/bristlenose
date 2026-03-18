/** Signals section — sentiment taxonomy, signal detection, academic references. */

export function SignalsSection() {
  return (
    <>
      <p>
        The analysis page surfaces signals &mdash; statistically notable
        concentrations of sentiment or codebook tags within report sections.
        Two types of signal card.
      </p>

      <h3>Sentiment signals</h3>
      <p>
        Each quote is tagged with one of seven sentiments designed for UX
        research:
      </p>
      <p>
        <strong>Frustration</strong> &mdash; difficulty, annoyance, friction.
        Points to performance or interaction problems.
      </p>
      <p>
        <strong>Confusion</strong> &mdash; not understanding, uncertainty.
        Points to information architecture or labelling problems.
      </p>
      <p>
        <strong>Doubt</strong> &mdash; scepticism, worry, distrust. Points to
        credibility or trust problems. Separated from confusion because
        understanding something and trusting it are different &mdash; they
        require different design responses.
      </p>
      <p>
        <strong>Surprise</strong> &mdash; expectation mismatch, neutral. Could
        be good or bad &mdash; only the researcher can tell from context.
      </p>
      <p>
        <strong>Satisfaction</strong> &mdash; met expectations, task success.
      </p>
      <p>
        <strong>Delight</strong> &mdash; exceeded expectations, pleasure.
      </p>
      <p>
        <strong>Confidence</strong> &mdash; trust, feeling in control.
      </p>
      <p>
        Each sentiment has an intensity scale of 1&ndash;3 (mild, moderate,
        strong). Quotes with no emotional content receive no sentiment tag.
      </p>
      <p>
        Signal detection uses three metrics. <strong>Concentration
        ratio</strong>: the observed rate of a sentiment in a section divided by
        its expected rate across the whole study &mdash; a ratio of 2&times;
        means that sentiment appears twice as often as you&rsquo;d expect.{" "}
        <strong>Agreement breadth</strong> (Simpson&rsquo;s diversity index):
        how many participants share the signal, distinguishing group consensus
        from one person&rsquo;s repeated reaction.{" "}
        <strong>Mean intensity</strong>: average strength on the 1&ndash;3
        scale. These three are normalised and multiplied into a composite signal
        score.
      </p>
      <p>
        Confidence thresholds: <strong>strong</strong> requires concentration
        above 2&times;, at least 5 participants, and at least 6 quotes;{" "}
        <strong>moderate</strong> requires above 1.5&times;, at least 3
        participants, and at least 4 quotes; everything else is classified as{" "}
        <strong>emerging</strong>.
      </p>

      <h3>Framework signals</h3>
      <p>
        Framework signals use the same concentration math, but the columns are
        codebook groups (e.g. Norman&rsquo;s Discoverability, Garrett&rsquo;s
        Structure) instead of sentiments. Tag contributions are weighted:
        researcher-accepted tags count as 1.0, autocode proposals use the
        LLM&rsquo;s confidence score, and denied proposals are excluded.
      </p>
      <p>
        For the top signals, an LLM call interprets the tagged quotes through
        each tag&rsquo;s definition to produce an interpretive name, a pattern
        classification, and a one-sentence finding. Four pattern types:{" "}
        <strong>success</strong> (positive evidence &mdash; users&rsquo;
        expectations met), <strong>gap</strong> (negative &mdash; mismatch,
        friction, hidden features), <strong>tension</strong> (mixed positive and
        negative), and <strong>recovery</strong> (negative followed by positive
        &mdash; initial confusion, but users figure it out).
      </p>

      <h3>References</h3>

      <h4>Emotion science</h4>
      <div className="bn-about-citation">
        <p>
          Russell, J. A. (2003). Core affect and the psychological construction
          of emotion. <em>Psychological Review, 110</em>(1), 145&ndash;172.{" "}
          <a href="https://doi.org/10.1037/0033-295X.110.1.145">[DOI]</a>
        </p>
        <p className="summary">
          Valence and arousal are the two fundamental dimensions underlying all
          emotional experience.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Barrett, L. F. (2017). <em>How Emotions Are Made: The Secret Life of
          the Brain.</em> Houghton Mifflin Harcourt.{" "}
          <a href="https://lisafeldmanbarrett.com/books/how-emotions-are-made/">[Publisher]</a>
        </p>
        <p className="summary">
          Emotions are constructed in the moment from core affect, conceptual
          knowledge, and context.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Scherer, K. R. (2005). What are emotions? And how can they be
          measured? <em>Social Science Information, 44</em>(4), 695&ndash;729.{" "}
          <a href="https://doi.org/10.1177/0539018405058216">[DOI]</a>
        </p>
        <p className="summary">
          The Geneva Emotion Wheel &mdash; 20 emotion families based on
          appraisal theory.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Bradley, M. M., &amp; Lang, P. J. (1994). Measuring emotion: The
          self-assessment manikin and the semantic differential.{" "}
          <em>Journal of Behavior Therapy and Experimental Psychiatry, 25</em>
          (1), 49&ndash;59.{" "}
          <a href="https://doi.org/10.1016/0005-7916(94)90063-9">[DOI]</a>
        </p>
        <p className="summary">
          Non-verbal pictorial scales for measuring pleasure, arousal, and
          dominance.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Ekman, P. (1992). An argument for basic emotions.{" "}
          <em>Cognition and Emotion, 6</em>(3&ndash;4), 169&ndash;200.{" "}
          <a href="https://doi.org/10.1080/02699939208411068">[DOI]</a>
        </p>
        <p className="summary">
          Six basic emotions universally recognised across cultures &mdash;
          influential but now contested by constructionist theories.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Plutchik, R. (1980). A general psychoevolutionary theory of emotion.
          In R. Plutchik &amp; H. Kellerman (Eds.),{" "}
          <em>Emotion: Theory, Research, and Experience</em> (Vol. 1,
          pp. 3&ndash;33). Academic Press.{" "}
          <a href="https://doi.org/10.1016/B978-0-12-558701-3.50007-7">[DOI]</a>
        </p>
        <p className="summary">
          Eight primary emotions in opposing pairs with three intensity levels.
        </p>
      </div>

      <h4>User experience research</h4>
      <div className="bn-about-citation">
        <p>
          Hassenzahl, M. (2003). The thing and I: Understanding the relationship
          between user and product. In M. A. Blythe et al. (Eds.),{" "}
          <em>Funology: From Usability to Enjoyment</em> (pp. 31&ndash;42).
          Kluwer.{" "}
          <a href="https://doi.org/10.1007/1-4020-2967-5_4">[DOI]</a>
        </p>
        <p className="summary">
          Two UX quality dimensions: pragmatic (usability) and hedonic
          (stimulation, identity).
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Laugwitz, B., Held, T., &amp; Schrepp, M. (2008). Construction and
          evaluation of a user experience questionnaire. In A. Holzinger (Ed.),{" "}
          <em>HCI and Usability for Education and Work</em> (pp. 63&ndash;76).
          Springer.{" "}
          <a href="https://doi.org/10.1007/978-3-540-89350-9_6">[DOI]</a>
        </p>
        <p className="summary">
          The UEQ measures six dimensions: attractiveness, perspicuity,
          efficiency, dependability, stimulation, novelty.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Benedek, J., &amp; Miner, T. (2002). Measuring desirability: New
          methods for evaluating desirability in a usability lab setting.{" "}
          <em>Proceedings of the Usability Professionals Association
          Conference.</em>{" "}
          <a href="https://www.microsoft.com/en-us/research/publication/measuring-desirability-new-methods-for-evaluating-desirability-in-a-usability-lab-setting/">[Microsoft Research]</a>
        </p>
        <p className="summary">
          Product Reaction Cards &mdash; 118 words users select to describe
          their experience.
        </p>
      </div>

      <h4>Trust and credibility</h4>
      <div className="bn-about-citation">
        <p>
          Fogg, B. J. (2003). Prominence-interpretation theory: Explaining how
          people assess credibility online. <em>CHI &rsquo;03 Extended
          Abstracts</em> (pp. 722&ndash;723). ACM.{" "}
          <a href="https://credibility.stanford.edu/pdf/PITheory.pdf">[PDF]</a>
        </p>
        <p className="summary">
          Users notice elements (prominence), then judge them (interpretation)
          &mdash; both steps must occur for credibility assessment.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Fogg, B. J. et al. (2001). What makes web sites credible?{" "}
          <em>CHI &rsquo;01</em> (pp. 61&ndash;68). ACM.{" "}
          <a href="https://courses.ischool.berkeley.edu/i290-10/f05/bjfogg.pdf">[PDF]</a>
        </p>
        <p className="summary">
          Users judge credibility primarily on visual design and ease of use,
          not content accuracy.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Fogg, B. J. (1999). The elements of computer credibility.{" "}
          <em>CHI &rsquo;99</em> (pp. 80&ndash;87). ACM.{" "}
          <a href="https://credibility.stanford.edu/pdf/p80-fogg.pdf">[PDF]</a>
        </p>
        <p className="summary">
          Credibility = trustworthiness + expertise. Four types: presumed,
          surface, reputed, earned.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Stanford Web Credibility Research. (2002).{" "}
          <em>Stanford Guidelines for Web Credibility.</em> Stanford Persuasive
          Technology Lab.{" "}
          <a href="https://credibility.stanford.edu/guidelines/index.html">[Web]</a>
        </p>
        <p className="summary">
          Ten research-based guidelines for building credible websites.
        </p>
      </div>

      <h4>Affective computing</h4>
      <div className="bn-about-citation">
        <p>
          Picard, R. W. (1997). <em>Affective Computing.</em> MIT Press.{" "}
          <a href="https://mitpress.mit.edu/9780262661157/affective-computing/">[Publisher]</a>
        </p>
        <p className="summary">
          The founding text &mdash; computers that recognise and respond to
          emotion create more humane interaction.
        </p>
      </div>
      <div className="bn-about-citation">
        <p>
          Demszky, D. et al. (2020). GoEmotions: A dataset of fine-grained
          emotions. <em>ACL 2020</em> (pp. 4040&ndash;4054).{" "}
          <a href="https://arxiv.org/abs/2005.00547">[arXiv]</a>
        </p>
        <p className="summary">
          58,000 comments labelled with 27 emotion categories &mdash; the
          largest fine-grained emotion dataset for NLP.
        </p>
      </div>
    </>
  );
}
