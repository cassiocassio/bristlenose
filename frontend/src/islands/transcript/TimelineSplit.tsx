/**
 * The split control at the end of the transcript's sticky row
 * (docs/mockups/transcript-timeline-toggle.html, iteration 2).
 *
 * The button half toggles the slot between the journey chain and the session timeline; the
 * pulldown half says the same toggle in words, then picks the timeline's detail. A Mac split
 * button (a SwiftUI `Menu` with a `primaryAction`), drawn as two segments of the house segmented
 * control (`.dimension-toggle`) inside the Export menu's wrapper, with the Export menu's classes
 * and check gutter. The label hides on a narrow row (a container query, templates/transcript.css).
 */

import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../../components/Icon";
import { useDropdown } from "../../hooks/useDropdown";
import { useMenuKeyboard } from "../../hooks/useMenuKeyboard";
import {
  TIMELINE_LANES,
  setTimelineLanes,
  setTimelineOn,
  toggleTimeline,
  useTranscriptTimeline,
  type TimelineLanes,
} from "../../contexts/TranscriptTimelineStore";

const DETAIL_KEY: Record<TimelineLanes, string> = {
  2: "sessions.tapestry.compact",
  3: "sessions.tapestry.standard",
  5: "sessions.tapestry.full",
};

export function TimelineSplit() {
  const { t } = useTranslation();
  const { on, lanes } = useTranscriptTimeline();
  const moreRef = useRef<HTMLButtonElement | null>(null);
  const { open, setOpen, toggle, containerRef } = useDropdown();
  const { menuRef } = useMenuKeyboard({ open, onClose: () => setOpen(false), triggerRef: moreRef });

  // What each detail adds, in the timeline's own lane words.
  const hint: Record<TimelineLanes, string> = {
    2: [t("quotes.sections"), t("sessions.speakerPlaceholder.moderator"), t("sessions.speakerPlaceholder.participant")].join(" · "),
    3: `+ ${t("sessions.colSentiment")}`,
    5: `+ ${t("quotes.themes")}`,
  };
  const pick = (fn: () => void) => () => {
    fn();
    setOpen(false);
  };
  const item = (key: string, checked: boolean, label: string, onPick: () => void, sub?: string) => (
    <li
      key={key}
      role="menuitemradio"
      aria-checked={checked}
      tabIndex={-1}
      className="export-dropdown-item export-dropdown-scope"
      data-testid={`timeline-menu-${key}`}
      onClick={pick(onPick)}
      // useMenuKeyboard handles the keys (Return and Space become a click); this handler is for
      // jsx-a11y, which cannot see a listener attached by a hook.
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") e.preventDefault();
      }}
    >
      <span className="export-dropdown-check" aria-hidden="true">
        {checked && <Icon name="check" size="menu" decorative />}
      </span>
      {label}
      {sub && <span className="bn-timeline-menu-hint">{sub}</span>}
    </li>
  );

  return (
    <div ref={containerRef} className="bn-timeline-split export-dropdown-wrapper" data-testid="timeline-split">
      {/* No group name: the button inside already says "Session timeline". */}
      <span className="dimension-toggle" role="group">
        <button
          type="button"
          className={`dimension-btn bn-timeline-split__main${on ? " active" : ""}`}
          aria-pressed={on}
          // A name of its own: on a narrow row the visible word is hidden, and with it the
          // button's text. "Session timeline" contains the visible "Timeline" (label in name).
          aria-label={t("sessions.tapestry.label")}
          title={t("sessions.tapestry.label")}
          onClick={toggleTimeline}
          data-testid="timeline-toggle"
        >
          <Icon name="timeline" decorative />
          <span className="bn-timeline-split__label">{t("sessions.tapestry.timeline")}</span>
        </button>
        <button
          ref={moreRef}
          type="button"
          className="dimension-btn bn-timeline-split__more"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={t("sessions.tapestry.detail")}
          title={t("sessions.tapestry.detail")}
          onClick={toggle}
          data-testid="timeline-more"
        >
          <Icon name="caret" decorative />
        </button>
      </span>
      {open && (
        <ul ref={menuRef} role="menu" className="export-dropdown-menu" aria-label={t("sessions.tapestry.detail")}>
          {item("chain", !on, t("sessions.colJourney"), () => setTimelineOn(false))}
          {item("timeline", on, t("sessions.tapestry.label"), () => setTimelineOn(true))}
          <li role="separator" className="export-dropdown-separator" />
          {TIMELINE_LANES.map((n) => item(`lanes-${n}`, lanes === n, t(DETAIL_KEY[n]), () => setTimelineLanes(n), hint[n]))}
        </ul>
      )}
    </div>
  );
}
