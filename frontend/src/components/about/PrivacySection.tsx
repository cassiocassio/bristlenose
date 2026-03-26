/** Privacy section — how data is handled, PII redaction limits, what to do. */

import { useTranslation } from "react-i18next";
import { dt } from "../../utils/desktopTranslation";

export function PrivacySection() {
  const { t } = useTranslation();
  return (
    <>
      <h3>{t("help.privacy.localTitle")}</h3>
      <p>{t("help.privacy.localBody")}</p>
      <p>{t("help.privacy.localOllama")}</p>
      <p>{t("help.privacy.localAnon")}</p>

      <h3>{t("help.privacy.redactionTitle")}</h3>
      <p>{dt(t, "help.privacy.redactionIntro")}</p>

      <h4>{t("help.privacy.catchesTitle")}</h4>
      <p>{t("help.privacy.catchesBody")}</p>

      <h4>{t("help.privacy.missesTitle")}</h4>
      <p>{t("help.privacy.missesBody")}</p>

      <h4>{t("help.privacy.cannotTitle")}</h4>
      <p>{t("help.privacy.cannotBody")}</p>
      <p>{t("help.privacy.cannotIndirect")}</p>
      <p>{t("help.privacy.speakerIdNote")}</p>

      <h3>{t("help.privacy.actionTitle")}</h3>
      <p>{t("help.privacy.actionReview")}</p>
      <p>{dt(t, "help.privacy.actionThreshold")}</p>
      <p>{t("help.privacy.actionSharing")}</p>
      <p>{t("help.privacy.actionRetention")}</p>
      <p>{t("help.privacy.actionNames")}</p>
      <p dangerouslySetInnerHTML={{ __html: t("help.privacy.actionAudit") }} />
    </>
  );
}
