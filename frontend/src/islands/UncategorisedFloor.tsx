/**
 * UncategorisedFloor — read-only surface for pinned quotes (starred / edited /
 * tagged) the current analysis left in no section or theme.
 *
 * The persistence layer freezes these quotes so a re-run can't delete them, and
 * `GET /quotes` returns them in `uncategorised`. This island makes them
 * *visible* — the safety net that keeps "nothing the researcher kept vanishes"
 * true on screen, not just in the API. Read-only for now; re-filing is Phase 0
 * (manual re-assignment). Renders nothing when the floor is empty (the common
 * case), so a healthy report pays nothing for it.
 */

import { useTranslation } from "react-i18next";
import { Badge, PersonBadge } from "../components";
import { getTagBg } from "../utils/colours";
import { useQuotesStore } from "../contexts/QuotesContext";

export function UncategorisedFloor() {
  const { t } = useTranslation();
  const { uncategorised } = useQuotesStore();

  if (uncategorised.length === 0) return null;

  return (
    <section className="bn-uncategorised-floor" data-testid="bn-uncategorised-floor">
      <h2 id="uncategorised">{t("quotes.uncategorisedHeading")}</h2>
      <p className="description">
        {t("quotes.uncategorisedIntro", { count: uncategorised.length })}
      </p>
      <div className="quote-group">
        {uncategorised.map((q) => (
          <blockquote
            key={q.dom_id}
            id={q.dom_id}
            className={`quote-card${q.is_starred ? " starred" : ""}`}
            data-testid={`bn-uncategorised-${q.dom_id}`}
          >
            <div className="quote-body">
              <span className="quote-text-wrapper">
                <span className="smart-quote">{"“"}</span>
                {q.edited_text || q.text}
                <span className="smart-quote">{"”"}</span>
              </span>{" "}
              <span className="speaker">
                <PersonBadge
                  code={q.participant_id}
                  role="participant"
                  name={q.speaker_name !== q.participant_id ? q.speaker_name : undefined}
                  data-testid={`bn-uncategorised-${q.dom_id}-speaker`}
                />
              </span>
              {q.tags.length > 0 && (
                <div className="badges">
                  {q.tags.map((tag) => (
                    <Badge
                      key={tag.name}
                      text={tag.name}
                      variant="readonly"
                      colour={
                        tag.colour_set
                          ? getTagBg(tag.colour_set, tag.colour_index)
                          : undefined
                      }
                      data-testid={`bn-uncategorised-${q.dom_id}-badge-${tag.name}`}
                    />
                  ))}
                </div>
              )}
            </div>
          </blockquote>
        ))}
      </div>
    </section>
  );
}
