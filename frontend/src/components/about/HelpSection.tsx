/**
 * HelpSection — landing page for the Help modal.
 *
 * Teaches researchers how to read and interpret their analysis output.
 * Not a feature catalogue — an orientation guide.
 *
 * @module HelpSection
 */

import { useTranslation } from "react-i18next";

export function HelpSection() {
  const { t } = useTranslation();
  return (
    <>
      <p>{t("help.guide.intro")}</p>

      <h4>{t("help.guide.sectionsTitle")}</h4>
      <p>{t("help.guide.sectionsBody")}</p>

      <h4>{t("help.guide.sentimentTitle")}</h4>
      <p>{t("help.guide.sentimentBody")}</p>

      <h4>{t("help.guide.signalsTitle")}</h4>
      <p>{t("help.guide.signalsBody")}</p>

      <h4>{t("help.guide.starsTitle")}</h4>
      <p>{t("help.guide.starsBody")}</p>

      <h4>{t("help.guide.exportTitle")}</h4>
      <p>{t("help.guide.exportBody")}</p>
    </>
  );
}
