/**
 * AboutPanel — multi-section About page with sidebar navigation.
 *
 * Five sections: About (product guide), Signals (sentiment taxonomy +
 * academic foundations), Codebook (qualitative coding methodology),
 * Developer (dev tools, dev-only), Design (mockups/experiments, dev-only).
 *
 * Layout borrows from Claude's settings pattern: fixed left sidebar,
 * content pane on the right that swaps based on selection.
 */

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthResponse {
  status: string;
  version: string;
}

interface EndpointInfo {
  label: string;
  url: string;
  description: string;
}

interface DesignItem {
  label: string;
  url: string;
}

interface DesignSection {
  heading: string;
  items: DesignItem[];
}

interface DevInfoResponse {
  db_path: string;
  table_count: number;
  endpoints: EndpointInfo[];
  design_sections?: DesignSection[];
}

// ---------------------------------------------------------------------------
// Section: About
// ---------------------------------------------------------------------------

function AboutSection({ version }: { version: string | null }) {
  return (
    <>
      <h2>About Bristlenose</h2>
      {version && <p>Version {version}</p>}

      <p>
        Open-source interview transcript analysis. Takes a folder of interview
        recordings and produces a report of extracted quotes grouped by screen
        and theme.
      </p>

      <h3>Input</h3>
      <p>
        Video (mp4, mov, avi, mkv, webm), audio (wav, mp3, m4a, flac, ogg, wma,
        aac), or existing transcripts (vtt, srt, docx). Recordings from Zoom,
        Teams, and Google Meet are detected automatically &mdash; files from the
        same session are grouped together. Other sources (Otter.ai, Rev, Loom,
        OBS, Voice Memos) work when exported in any of these formats.
      </p>

      <h3>Transcription and analysis</h3>
      <p>
        Transcription runs locally on your machine. Analysis uses Claude,
        ChatGPT, Gemini, Azure OpenAI, or Ollama (local, free).
      </p>

      <h3>Dashboard</h3>
      <p>
        Overview of the project: participant count, session count, quote totals,
        sentiment distribution. Links to individual sessions.
      </p>

      <h3>Quotes</h3>
      <p>
        All extracted quotes, organised into sections (by screen or task) and
        themes (cross-participant patterns). Star, hide, tag, and edit quotes.
        Filter by tag, search by text, switch between section and theme view.
      </p>

      <h3>Sessions</h3>
      <p>
        List of interview sessions with duration, participant, and thumbnail.
        Click through to the full transcript with timecodes. Click a timecode to
        open the video in a popout player.
      </p>

      <h3>Analysis</h3>
      <p>
        Signal concentration grids &mdash; which themes appear in which
        sessions, and how strongly. Helps identify patterns that cut across
        participants.
      </p>

      <h3>Codebook</h3>
      <p>
        Tag definitions and auto-coded categories. Review and accept or reject
        auto-generated tags.
      </p>

      <h3>Export</h3>
      <p>
        Filter your quotes and export as CSV for use in Miro, FigJam, Mural,
        Lucidspark, or a spreadsheet.
      </p>

      <p>
        Built by Martin Storey (
        <a href="mailto:martin@cassiocassio.co.uk">martin@cassiocassio.co.uk</a>
        ). Free and open source (AGPL-3.0).
      </p>

      <div className="bn-about-footer">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "?" }));
          }}
        >
          Keyboard shortcuts
        </a>
        {" "}
        &middot;{" "}
        <a
          href="https://github.com/cassiocassio/bristlenose/issues/new"
          target="_blank"
          rel="noopener noreferrer"
        >
          Report a bug
        </a>
        {" "}
        &middot;{" "}
        <a
          href="https://github.com/cassiocassio/bristlenose"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Section: Signals
// ---------------------------------------------------------------------------

function SignalsSection() {
  return (
    <>
      <h2>Signals</h2>

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

// ---------------------------------------------------------------------------
// Section: Codebook
// ---------------------------------------------------------------------------

function CodebookSection() {
  return (
    <>
      <h2>Codebook</h2>

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

// ---------------------------------------------------------------------------
// Section: Developer
// ---------------------------------------------------------------------------

function DeveloperSection({ info }: { info: DevInfoResponse | null }) {
  return (
    <>
      <h2>Developer</h2>

      <h3>Architecture</h3>
      <p>
        Twelve-stage pipeline: ingest &rarr; audio extraction &rarr; transcript
        parsing &rarr; transcription &rarr; speaker identification &rarr;
        transcript merge &rarr; PII removal &rarr; topic segmentation &rarr;
        quote extraction &rarr; quote clustering &rarr; thematic grouping &rarr;
        render. Transcription runs locally (Whisper via MLX or faster-whisper).
        Analysis stages call the configured LLM provider. Analysis page metrics
        are pure math &mdash; no LLM calls.
      </p>

      <h3>Stack</h3>
      <dl>
        <dt>CLI &amp; pipeline</dt>
        <dd>Python 3.10+, Pydantic, FFmpeg, Whisper</dd>
        <dt>Serve mode</dt>
        <dd>FastAPI, SQLAlchemy, SQLite (WAL mode), Uvicorn</dd>
        <dt>Frontend</dt>
        <dd>React 18, TypeScript, Vite, React Router</dd>
        <dt>Desktop</dt>
        <dd>SwiftUI macOS shell, PyInstaller sidecar</dd>
        <dt>Linting &amp; types</dt>
        <dd>Ruff, mypy, Vitest, tsc</dd>
        <dt>Packaging</dt>
        <dd>PyPI, Homebrew, Snap</dd>
      </dl>

      <h3>Key APIs</h3>
      <p>
        Serve mode exposes a project-scoped REST API. Sessions, quotes, tags,
        people, and autocode endpoints support the React SPA. The analysis
        module computes signal concentration, agreement breadth, and composite
        scores as plain dataclasses &mdash; ephemeral, never persisted. Static
        render produces a self-contained HTML file with JSON data in an IIFE.
      </p>

      <h3>Contributing</h3>
      <p>
        AGPL-3.0 with CLA. Before committing: <code>ruff check .</code>,{" "}
        <code>pytest tests/</code>, <code>npm run build</code> (tsc catches
        type errors Vitest misses). Version lives in{" "}
        <code>bristlenose/__init__.py</code> &mdash; bump with{" "}
        <code>scripts/bump-version.py</code>.
      </p>
      <p>
        <a
          href="https://github.com/cassiocassio/bristlenose/blob/main/CONTRIBUTING.md"
          target="_blank"
          rel="noopener noreferrer"
        >
          Contributing guide
        </a>
        {" "}&middot;{" "}
        <a
          href="https://github.com/cassiocassio/bristlenose"
          target="_blank"
          rel="noopener noreferrer"
        >
          Source code
        </a>
      </p>

      {info && (
        <>
          <h3>Dev tools</h3>
          <dl>
            <dt>Database</dt>
            <dd>
              <code>{info.db_path}</code>
            </dd>
            <dt>Schema</dt>
            <dd>{info.table_count} tables</dd>
            <dt>Renderer overlay</dt>
            <dd>
              Press <kbd>&sect;</kbd> to colour-code regions by renderer
              (blue&nbsp;=&nbsp;Jinja2, green&nbsp;=&nbsp;React,
              amber&nbsp;=&nbsp;Vanilla&nbsp;JS)
            </dd>
          </dl>
          <ul>
            {info.endpoints.map((ep) => (
              <li key={ep.url}>
                <a href={ep.url} target="_blank" rel="noopener noreferrer">
                  {ep.label}
                </a>{" "}
                &mdash; {ep.description}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Section: Design
// ---------------------------------------------------------------------------

function DesignSection({ sections }: { sections: DesignSection[] | undefined }) {
  return (
    <>
      <h2>Design</h2>

      <h3>Design system</h3>
      <p>
        Atomic CSS architecture with five layers: <strong>tokens</strong>{" "}
        (colours, spacing, typography as CSS custom properties),{" "}
        <strong>atoms</strong> (badge, button, input, timecode, toggle,
        thumbnail), <strong>molecules</strong> (person badge, tag input,
        editable text, sparkline), <strong>organisms</strong> (quote card,
        toolbar, codebook panel, analysis grid), and{" "}
        <strong>templates</strong> (report, transcript, print layouts). All
        values flow from tokens &mdash; nothing is hardcoded.
      </p>

      <h3>Dark mode</h3>
      <p>
        All-CSS via the <code>light-dark()</code> function on every colour
        token. No JavaScript toggle &mdash; follows the system preference
        (<code>prefers-color-scheme</code>). Every component inherits both
        themes automatically.
      </p>

      <h3>Component library</h3>
      <p>
        Sixteen React primitives: Badge, PersonBadge, TimecodeLink,
        EditableText, Toggle, Modal, Toast, TagInput, Sparkline, Metric,
        JourneyChain, Annotation, Counter, Thumbnail, MicroBar, and
        ConfirmDialog. Seven of these cover 80% of the app surface. Each React
        component name matches its CSS file (e.g. <code>Badge.tsx</code> &rarr;{" "}
        <code>atoms/badge.css</code>).
      </p>

      <h3>Typography</h3>
      <p>
        Inter Variable with four semantic weights: normal (420), emphasis (490),
        starred (520), strong (700). Tabular numbers for timecodes and
        statistics. System serif fallback for academic citations.
      </p>

      {sections && sections.length > 0 && (
        <>
          <h3>Mockups &amp; experiments</h3>
          {sections.map((section) => (
            <div key={section.heading}>
              <h4>{section.heading}</h4>
              <ul>
                {section.items.map((item) => (
                  <li key={item.url}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Sidebar item definition
// ---------------------------------------------------------------------------

const SIDEBAR_ITEMS = [
  { id: "about", label: "About" },
  { id: "signals", label: "Signals" },
  { id: "codebook", label: "Codebook" },
  { id: "developer", label: "Developer" },
  { id: "design", label: "Design" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AboutPanel() {
  const [activeSection, setActiveSection] = useState("about");
  const [version, setVersion] = useState<string | null>(null);
  const [devInfo, setDevInfo] = useState<DevInfoResponse | null>(null);

  useEffect(() => {
    const apiBase = (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
    if (typeof apiBase !== "string") return;

    fetch("/api/health")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: HealthResponse) => setVersion(data.version))
      .catch(() => {
        // Silent — version just won't display
      });

    fetch("/api/dev/info")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: DevInfoResponse) => setDevInfo(data))
      .catch(() => {
        // Silent — dev sections won't appear
      });
  }, []);

  const handleNav = useCallback(
    (id: string) => (e: React.MouseEvent) => {
      e.preventDefault();
      setActiveSection(id);
    },
    [],
  );

  return (
    <div className="bn-about">
      <nav className="bn-about-sidebar">
        {SIDEBAR_ITEMS.map((item) => (
          <button
            key={item.id}
            className={activeSection === item.id ? "active" : ""}
            onClick={handleNav(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="bn-about-content">
        {activeSection === "about" && <AboutSection version={version} />}
        {activeSection === "signals" && <SignalsSection />}
        {activeSection === "codebook" && <CodebookSection />}
        {activeSection === "developer" && (
          <DeveloperSection info={devInfo} />
        )}
        {activeSection === "design" && (
          <DesignSection sections={devInfo?.design_sections} />
        )}
      </div>
    </div>
  );
}
