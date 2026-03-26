/** Contributing section — how to contribute, links, licence. */

import { useTranslation } from "react-i18next";
import { dt } from "../../utils/platformTranslation";

export function ContributingSection() {
  const { t } = useTranslation();
  return (
    <>
      <p>{t("help.contributing.licence")}</p>

      <h3>{t("help.contributing.beforeTitle")}</h3>
      <p dangerouslySetInnerHTML={{ __html: dt(t, "help.contributing.beforeBody") }} />

      <h3>{t("help.contributing.translateTitle")}</h3>
      <p dangerouslySetInnerHTML={{ __html: t("help.contributing.translateBody") }} />

      <h3>{t("help.contributing.linksTitle")}</h3>
      <ul>
        <li>
          <a
            href="https://github.com/cassiocassio/bristlenose/blob/main/CONTRIBUTING.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("help.contributing.linkGuide")}
          </a>
        </li>
        <li>
          <a
            href="https://github.com/cassiocassio/bristlenose/issues/new"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("help.contributing.linkBug")}
          </a>
        </li>
        <li>
          <a
            href="https://github.com/cassiocassio/bristlenose"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("help.contributing.linkSource")}
          </a>
        </li>
      </ul>
    </>
  );
}
