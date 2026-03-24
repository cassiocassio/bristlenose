/** Codebook section — qualitative coding methodology, framework codebooks, references. */

import { useTranslation } from "react-i18next";

export function CodebookSection() {
  const { t } = useTranslation();
  return (
    <>
      <h3>{t("help.codebook.sectionsTitle")}</h3>
      <p dangerouslySetInnerHTML={{ __html: t("help.codebook.sectionsBody") }} />
      <p>{t("help.codebook.themesBody")}</p>
      <p>{t("help.codebook.quoteEthicsBody")}</p>

      <h3>{t("help.codebook.sentimentTitle")}</h3>
      <p>{t("help.codebook.sentimentBody")}</p>

      <h3>{t("help.codebook.frameworkTitle")}</h3>
      <p>{t("help.codebook.frameworkBody")}</p>

      <h4>The Elements of User Experience (Garrett)</h4>
      <p>{t("help.codebook.garrettDesc")}</p>
      <div className="bn-about-citation">
        <p lang="en">
          Garrett, J. J. (2010). <em>The Elements of User Experience:
          User-Centered Design for the Web and Beyond</em> (2nd ed.).
          New Riders.{" "}
          <a href="https://www.jjg.net/elements/">[Author]</a>
        </p>
      </div>

      <h4>The Design of Everyday Things (Norman)</h4>
      <p>{t("help.codebook.normanDesc")}</p>
      <div className="bn-about-citation">
        <p lang="en">
          Norman, D. (2013). <em>The Design of Everyday Things</em>
          (Rev. ed.). Basic Books.{" "}
          <a href="https://mitpress.mit.edu/9780262525671/the-design-of-everyday-things/">[Publisher]</a>
        </p>
      </div>

      <h4>Platonic Ontology &amp; Epistemology</h4>
      <p>{t("help.codebook.platonicDesc")}</p>
      <div className="bn-about-citation">
        <p lang="en">
          Composite framework drawing on Vlastos (elenchus, irony), Fine
          (epistemology, Forms), Kraut (ethics, Republic), Sedley
          (cosmology), and Irwin (moral psychology).
        </p>
      </div>

      <h4>Bristlenose UXR Codebook</h4>
      <p>{t("help.codebook.bristlenoseDesc")}</p>

      <h3>{t("help.codebook.referencesTitle")}</h3>
      <div className="bn-about-citation">
        <p lang="en">
          Braun, V., &amp; Clarke, V. (2006). Using thematic analysis in
          psychology. <em>Qualitative Research in Psychology, 3</em>(2),
          77&ndash;101.{" "}
          <a href="https://doi.org/10.1191/1478088706qp063oa">[DOI]</a>
        </p>
        <p className="summary">{t("help.codebook.citBraun2006")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Salda&ntilde;a, J. (2021). <em>The Coding Manual for Qualitative
          Researchers</em> (4th ed.). SAGE.{" "}
          <a href="https://us.sagepub.com/en-us/nam/the-coding-manual-for-qualitative-researchers/book273583">[Publisher]</a>
        </p>
        <p className="summary">{t("help.codebook.citSaldana2021")}</p>
      </div>
      <div className="bn-about-citation">
        <p lang="en">
          Ericsson, K. A., &amp; Simon, H. A. (1993).{" "}
          <em>Protocol Analysis: Verbal Reports as Data</em> (Rev. ed.). MIT
          Press.{" "}
          <a href="https://mitpress.mit.edu/9780262550239/protocol-analysis/">[Publisher]</a>
        </p>
        <p className="summary">{t("help.codebook.citEricsson1993")}</p>
      </div>
    </>
  );
}
