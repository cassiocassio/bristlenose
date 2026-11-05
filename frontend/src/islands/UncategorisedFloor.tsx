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

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "../components/Badge";
import { PersonBadge } from "../components/PersonBadge";
import { getTagBg } from "../utils/colours";
import { useQuotesStore } from "../contexts/QuotesContext";
import { useDisplayBreaks } from "../contexts/DisplayPrefsStore";
import { breakIntoBlocks } from "../utils/breakParagraphs";

export function UncategorisedFloor() {
  const { t } = useTranslation();
  const { uncategorised } = useQuotesStore();
  const breaksOn = useDisplayBreaks() === "on";

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
                <QuoteWords text={q.edited_text || q.text} breaksOn={breaksOn} />
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

/** The quote's words with their quote marks. With Break long paragraphs on, a long quote is
 *  blocks (the marks inside the first and last, as QuoteCard draws them; display-prefs.css
 *  styles `.quote-text .bn-block`); otherwise the text as it was. */
function QuoteWords({ text, breaksOn }: { text: string; breaksOn: boolean }) {
  const blocks = useMemo(() => (breaksOn ? breakIntoBlocks(text) : [text]), [breaksOn, text]);
  if (blocks.length < 2) {
    return (
      <>
        <span className="smart-quote">{"\u201c"}</span>
        {text}
        <span className="smart-quote">{"\u201d"}</span>
      </>
    );
  }
  const last = blocks.length - 1;
  return (
    <span className="quote-text">
      {blocks.map((block, i) => (
        <span key={i} className="bn-block">
          {i === 0 && <span className="smart-quote">{"\u201c"}</span>}
          {block}
          {i === last && <span className="smart-quote">{"\u201d"}</span>}
        </span>
      ))}
    </span>
  );
}
