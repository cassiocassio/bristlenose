/**
 * The Quotes lens's grouping control: Sections & themes / Sessions.
 *
 * docs/design-progressive-lenses.md §2 and Phase 2. During a first analysis
 * the quotes arrive session by session, before any section or theme exists, so
 * the lens shows them by session and there is no control. Once sections and
 * themes exist the control appears and stays: both groupings are useful after
 * the run too. The choice is a per-viewer convenience, remembered per project
 * in `localStorage` (and the page works without it). Serve always names the
 * project "1", so in practice it is one choice per viewer, which the Mac app
 * keeps across relaunches (R89).
 *
 * It is the shipped split control (`.dimension-toggle`, as in the Signals
 * inspector and the person picker), default first. It sits at the top of the
 * content sidebar while that sidebar is showing, and in the zone heading's
 * action slot when it is not (docs/mockups/quote-grouping-sidebar.html).
 */

import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { storePref } from "../utils/nativePrefs";

export type QuoteGrouping = "sections" | "session";

const KEY = (projectId: string) => `bristlenose-quote-grouping-${projectId}`;

function readGrouping(projectId: string): QuoteGrouping {
  try {
    return localStorage.getItem(KEY(projectId)) === "session" ? "session" : "sections";
  } catch {
    return "sections";
  }
}

/** The remembered grouping for this project, and a setter that remembers. */
export function useQuoteGrouping(projectId: string): [QuoteGrouping, (g: QuoteGrouping) => void] {
  const [grouping, setGrouping] = useState<QuoteGrouping>(() => readGrouping(projectId));
  const choose = useCallback(
    (g: QuoteGrouping) => {
      setGrouping(g);
      // Through storePref, so the Mac app keeps it past a relaunch (R89).
      storePref(KEY(projectId), g);
    },
    [projectId],
  );
  return [grouping, choose];
}

export function QuoteGroupingToggle({
  grouping,
  onChange,
}: {
  grouping: QuoteGrouping;
  onChange: (g: QuoteGrouping) => void;
}) {
  const { t } = useTranslation();
  const button = (value: QuoteGrouping, label: string) => (
    <button
      type="button"
      className={`dimension-btn${grouping === value ? " active" : ""}`}
      aria-pressed={grouping === value}
      onClick={() => onChange(value)}
      data-testid={`bn-quote-grouping-${value}`}
    >
      {label}
    </button>
  );
  return (
    <span role="group" aria-label={t("quotes.groupBy.label")} className="dimension-toggle bn-quote-grouping">
      {button("sections", t("quotes.groupBy.sectionsAndThemes"))}
      {button("session", t("quotes.groupBy.session"))}
    </span>
  );
}
