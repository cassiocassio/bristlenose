/**
 * ZoneCounters — the review dialog's three zone counts: Exclude, Tentative, Accept.
 *
 * Drawn by ThresholdReviewModal under the histogram, and by the Tag Specimen
 * page (islands/TagSpecimen.tsx), so the specimen shows the counters through the
 * code the dialog ships rather than a copy of its markup. The Tentative counter
 * wears the tentative tag's dotted outline and pulses
 * (the --bn-tentative-* tokens, drawn by molecules/threshold-review.css).
 */

import { useTranslation } from "react-i18next";
import { RollingNumber } from "./RollingNumber";

interface ZoneCountersProps {
  excluded: number;
  tentative: number;
  accepted: number;
}

export function ZoneCounters({ excluded, tentative, accepted }: ZoneCountersProps) {
  const { t } = useTranslation();
  return (
    <div className="threshold-zone-counters">
      <span className="threshold-zone-counter threshold-zone-counter--exclude">
        {t("autocode.review.zoneExclude")}{" "}
        <span className="threshold-zone-counter-count">
          <RollingNumber value={excluded} />
        </span>
      </span>
      <span className="threshold-zone-counter threshold-zone-counter--tentative">
        {t("autocode.review.zoneTentative")}{" "}
        <span className="threshold-zone-counter-count">
          <RollingNumber value={tentative} />
        </span>
      </span>
      <span className="threshold-zone-counter threshold-zone-counter--accept">
        {t("autocode.review.zoneAccept")}{" "}
        <span className="threshold-zone-counter-count">
          <RollingNumber value={accepted} />
        </span>
      </span>
    </div>
  );
}
