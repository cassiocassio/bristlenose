/** Signals section — sentiment taxonomy, signal detection, academic references. */

import { useTranslation } from "react-i18next";

export function SignalsSection() {
  const { t } = useTranslation(["common", "enums"]);
  return (
    <>
      <p>{t("help.signals.intro")}</p>

      <h3>{t("help.signals.sentimentHeading")}</h3>
      <p>{t("help.signals.sentimentIntro")}</p>
      <p>
        <strong>{t("enums:sentiment.frustration")}</strong>
        {" \u2014 "}
        {t("help.signals.frustrationDesc")}
      </p>
      <p>
        <strong>{t("enums:sentiment.confusion")}</strong>
        {" \u2014 "}
        {t("help.signals.confusionDesc")}
      </p>
      <p>
        <strong>{t("enums:sentiment.doubt")}</strong>
        {" \u2014 "}
        {t("help.signals.doubtDesc")}
      </p>
      <p>
        <strong>{t("enums:sentiment.surprise")}</strong>
        {" \u2014 "}
        {t("help.signals.surpriseDesc")}
      </p>
      <p>
        <strong>{t("enums:sentiment.satisfaction")}</strong>
        {" \u2014 "}
        {t("help.signals.satisfactionDesc")}
      </p>
      <p>
        <strong>{t("enums:sentiment.delight")}</strong>
        {" \u2014 "}
        {t("help.signals.delightDesc")}
      </p>
      <p>
        <strong>{t("enums:sentiment.confidence")}</strong>
        {" \u2014 "}
        {t("help.signals.confidenceDesc")}
      </p>
      <p>{t("help.signals.intensityScale")}</p>
      <p dangerouslySetInnerHTML={{ __html: t("help.signals.concentrationDesc") }} />
      <p dangerouslySetInnerHTML={{ __html: t("help.signals.agreementDesc") }} />
      <p dangerouslySetInnerHTML={{ __html: t("help.signals.intensityMetricDesc") }} />
      <p dangerouslySetInnerHTML={{ __html: t("help.signals.thresholds") }} />

      <h3>{t("help.signals.frameworkHeading")}</h3>
      <p>{t("help.signals.frameworkBody")}</p>
      <p dangerouslySetInnerHTML={{ __html: t("help.signals.patternTypesBody") }} />

      <h3>{t("help.signals.referencesHeading")}</h3>

      <h4>{t("help.signals.refEmotionScience")}</h4>
      <div className="bn-about-citation">
        <p lang="en">
          Russell, J. A. (2003). Core affect and the psychological construction
          of emotion. <em>Psychological Review, 110</em>(1), 145&ndash;172.{" "}
          <a href="https://doi.org/10.1037/0033-295X.110.1.145">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citRussell2003")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Barrett, L. F. (2017). <em>How Emotions Are Made: The Secret Life of
          the Brain.</em> Houghton Mifflin Harcourt.{" "}
          <a href="https://lisafeldmanbarrett.com/books/how-emotions-are-made/">[Publisher]</a>
        </p>
        <p className="summary">{t("help.signals.citBarrett2017")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Scherer, K. R. (2005). What are emotions? And how can they be
          measured? <em>Social Science Information, 44</em>(4), 695&ndash;729.{" "}
          <a href="https://doi.org/10.1177/0539018405058216">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citScherer2005")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Bradley, M. M., &amp; Lang, P. J. (1994). Measuring emotion: The
          self-assessment manikin and the semantic differential.{" "}
          <em>Journal of Behavior Therapy and Experimental Psychiatry, 25</em>
          (1), 49&ndash;59.{" "}
          <a href="https://doi.org/10.1016/0005-7916(94)90063-9">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citBradley1994")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Ekman, P. (1992). An argument for basic emotions.{" "}
          <em>Cognition and Emotion, 6</em>(3&ndash;4), 169&ndash;200.{" "}
          <a href="https://doi.org/10.1080/02699939208411068">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citEkman1992")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Plutchik, R. (1980). A general psychoevolutionary theory of emotion.
          In R. Plutchik &amp; H. Kellerman (Eds.),{" "}
          <em>Emotion: Theory, Research, and Experience</em> (Vol. 1,
          pp. 3&ndash;33). Academic Press.{" "}
          <a href="https://doi.org/10.1016/B978-0-12-558701-3.50007-7">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citPlutchik1980")}</p>
      </div>

      <h4>{t("help.signals.refUxResearch")}</h4>
      <div className="bn-about-citation">
        <p lang="en">
          Hassenzahl, M. (2003). The thing and I: Understanding the relationship
          between user and product. In M. A. Blythe et al. (Eds.),{" "}
          <em>Funology: From Usability to Enjoyment</em> (pp. 31&ndash;42).
          Kluwer.{" "}
          <a href="https://doi.org/10.1007/1-4020-2967-5_4">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citHassenzahl2003")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Laugwitz, B., Held, T., &amp; Schrepp, M. (2008). Construction and
          evaluation of a user experience questionnaire. In A. Holzinger (Ed.),{" "}
          <em>HCI and Usability for Education and Work</em> (pp. 63&ndash;76).
          Springer.{" "}
          <a href="https://doi.org/10.1007/978-3-540-89350-9_6">[DOI]</a>
        </p>
        <p className="summary">{t("help.signals.citLaugwitz2008")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Benedek, J., &amp; Miner, T. (2002). Measuring desirability: New
          methods for evaluating desirability in a usability lab setting.{" "}
          <em>Proceedings of the Usability Professionals Association
          Conference.</em>{" "}
          <a href="https://www.microsoft.com/en-us/research/publication/measuring-desirability-new-methods-for-evaluating-desirability-in-a-usability-lab-setting/">[Microsoft Research]</a>
        </p>
        <p className="summary">{t("help.signals.citBenedek2002")}</p>
      </div>

      <h4>{t("help.signals.refTrustCredibility")}</h4>
      <div className="bn-about-citation">
        <p lang="en">
          Fogg, B. J. (2003). Prominence-interpretation theory: Explaining how
          people assess credibility online. <em>CHI &rsquo;03 Extended
          Abstracts</em> (pp. 722&ndash;723). ACM.{" "}
          <a href="https://credibility.stanford.edu/pdf/PITheory.pdf">[PDF]</a>
        </p>
        <p className="summary">{t("help.signals.citFogg2003")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Fogg, B. J. et al. (2001). What makes web sites credible?{" "}
          <em>CHI &rsquo;01</em> (pp. 61&ndash;68). ACM.{" "}
          <a href="https://courses.ischool.berkeley.edu/i290-10/f05/bjfogg.pdf">[PDF]</a>
        </p>
        <p className="summary">{t("help.signals.citFogg2001")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Fogg, B. J. (1999). The elements of computer credibility.{" "}
          <em>CHI &rsquo;99</em> (pp. 80&ndash;87). ACM.{" "}
          <a href="https://credibility.stanford.edu/pdf/p80-fogg.pdf">[PDF]</a>
        </p>
        <p className="summary">{t("help.signals.citFogg1999")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Stanford Web Credibility Research. (2002).{" "}
          <em>Stanford Guidelines for Web Credibility.</em> Stanford Persuasive
          Technology Lab.{" "}
          <a href="https://credibility.stanford.edu/guidelines/index.html">[Web]</a>
        </p>
        <p className="summary">{t("help.signals.citStanford2002")}</p>
      </div>

      <h4>{t("help.signals.refAffectiveComputing")}</h4>
      <div className="bn-about-citation">
        <p lang="en">
          Picard, R. W. (1997). <em>Affective Computing.</em> MIT Press.{" "}
          <a href="https://mitpress.mit.edu/9780262661157/affective-computing/">[Publisher]</a>
        </p>
        <p className="summary">{t("help.signals.citPicard1997")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Demszky, D. et al. (2020). GoEmotions: A dataset of fine-grained
          emotions. <em>ACL 2020</em> (pp. 4040&ndash;4054).{" "}
          <a href="https://arxiv.org/abs/2005.00547">[arXiv]</a>
        </p>
        <p className="summary">{t("help.signals.citDemszky2020")}</p>
      </div>
    </>
  );
}
